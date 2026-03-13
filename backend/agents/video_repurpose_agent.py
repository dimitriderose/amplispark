import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import uuid

from google import genai
from google.genai import types

from backend.config import GEMINI_MODEL, GOOGLE_API_KEY

logger = logging.getLogger(__name__)

# Platform aspect-ratio configurations
_PLATFORM_CONFIGS: dict[str, dict] = {
    "reels":          {"width": 1080, "height": 1920},
    "tiktok":         {"width": 1080, "height": 1920},
    "youtube_shorts": {"width": 1080, "height": 1920},
    "linkedin":       {"width": 1080, "height": 1080},
}

# Gemini Files API polling ceiling (10 minutes for very large videos)
_GEMINI_POLL_TIMEOUT_S = 600
_GEMINI_POLL_INTERVAL_S = 4

# FFmpeg subprocess timeout per command (5 minutes)
_FFMPEG_TIMEOUT_S = 300

# Platform-specific max clip duration (seconds) — used for timestamp validation
_PLATFORM_MAX_S: dict[str, float] = {
    "reels": 60, "tiktok": 60, "youtube_shorts": 60, "linkedin": 90,
}


# ── FFmpeg helpers ─────────────────────────────────────────────────────────────

def _run_ffmpeg(args: list[str]) -> None:
    """Run an FFmpeg command; raises RuntimeError on non-zero exit or timeout."""
    cmd = ["ffmpeg", "-y"] + args
    logger.debug("FFmpeg: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=_FFMPEG_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"FFmpeg timed out after {_FFMPEG_TIMEOUT_S}s")
    if result.returncode != 0:
        logger.error("FFmpeg stderr: %s", result.stderr[-2000:])
        raise RuntimeError(f"FFmpeg failed (exit {result.returncode})")


def _extract_and_format_clip(
    input_path: str,
    output_path: str,
    start: float,
    end: float,
    platform: str,
) -> None:
    """Extract a time range and reformat to the target platform aspect ratio in one pass."""
    cfg = _PLATFORM_CONFIGS.get(platform, _PLATFORM_CONFIGS["reels"])
    w, h = cfg["width"], cfg["height"]
    duration = end - start
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
    )
    # Place -ss before -i for fast keyframe seek; -t is relative to seek point
    _run_ffmpeg([
        "-ss", str(start),
        "-i", input_path,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264", "-c:a", "aac",
        output_path,
    ])


# ── Gemini video analysis ──────────────────────────────────────────────────────

async def _upload_to_gemini_files(video_path: str, mime_type: str) -> tuple:
    """Upload a video file to the Gemini Files API and wait until ACTIVE.

    Returns:
        (video_file, client) tuple ready for generate_content.

    Raises:
        TimeoutError: Gemini did not process the file within _GEMINI_POLL_TIMEOUT_S.
        ValueError: Gemini returned a non-ACTIVE final state.
    """
    client = genai.Client(api_key=GOOGLE_API_KEY)

    video_file = await asyncio.to_thread(
        client.files.upload,
        path=video_path,
        config={"mime_type": mime_type},
    )

    # Poll with a hard timeout ceiling
    elapsed = 0.0
    while getattr(video_file.state, "name", str(video_file.state)) == "PROCESSING":
        if elapsed >= _GEMINI_POLL_TIMEOUT_S:
            raise TimeoutError(
                f"Gemini did not finish processing the video within "
                f"{_GEMINI_POLL_TIMEOUT_S}s (file: {video_file.name})"
            )
        await asyncio.sleep(_GEMINI_POLL_INTERVAL_S)
        elapsed += _GEMINI_POLL_INTERVAL_S
        video_file = await asyncio.to_thread(client.files.get, name=video_file.name)

    state_name = getattr(video_file.state, "name", str(video_file.state))
    if state_name != "ACTIVE":
        raise ValueError(f"Gemini file processing failed (state={state_name})")

    return video_file, client


async def _analyze_video(video_file: object, client: object, brand_profile: dict) -> list[dict]:
    """Ask Gemini to identify the top 3 clip-worthy moments in the video."""
    # Sanitize brand fields to prevent prompt injection
    business = (brand_profile.get("business_name") or brand_profile.get("name") or "this brand")[:80]
    tone = str(brand_profile.get("tone", "professional"))[:40]
    industry = str(brand_profile.get("industry", "business"))[:40]
    caption_hint = str(brand_profile.get("caption_style_directive", ""))[:120]

    content_themes = brand_profile.get("content_themes", [])
    themes_str = ", ".join(t[:60] for t in content_themes[:6]) if content_themes else ""
    competitors = brand_profile.get("competitors", [])
    competitors_str = ", ".join(c[:40] for c in competitors[:3]) if competitors else ""

    caption_note = f" Write captions in this style: {caption_hint}" if caption_hint else ""

    # Build strategy context block (only if data exists)
    strategy_lines = ""
    if themes_str or competitors_str:
        parts = []
        if themes_str:
            parts.append(f"Content pillars: {themes_str}")
        if competitors_str:
            parts.append(f"Key competitors: {competitors_str}")
        parts.append("For each clip, tag it to the most relevant content pillar from the list above. Prioritize clips covering DIFFERENT pillars.")
        strategy_lines = "\n".join(parts) + "\n"

    # Build platform list from known keys
    platform_keys = list(_PLATFORM_CONFIGS.keys())

    prompt = f"""Analyze this video for a {industry} brand called "{business}" (tone: {tone}).
{strategy_lines}
Identify the TOP 3 most clip-worthy moments for social media short-form content.

For each clip, choose the most suitable platform from: {platform_keys}
- "reels" or "tiktok": 15–60 seconds, hook in first 3 seconds, high energy
- "linkedin": 30–90 seconds, insight-driven, professional
- "youtube_shorts": 15–60 seconds, fast-paced

Return ONLY a valid JSON array with this exact structure:
[
  {{
    "start_time": 12.5,
    "end_time": 42.0,
    "platform": "reels",
    "hook": "The verbatim opening line or moment that immediately grabs attention",
    "suggested_caption": "A ready-to-post caption in the brand voice.{caption_note}",
    "reason": "2-3 sentences: (1) why this moment stops the scroll, (2) what makes it right for this platform specifically, (3) the audience emotion it targets",
    "content_theme": "The content pillar this clip best represents"
  }}
]

Rules:
- Timestamps must be in seconds (floats), accurate to the video content.
- Do NOT overlap clips.
- Sort by engagement potential (best first).
- Each clip MUST have a strong opening hook."""

    response = await asyncio.to_thread(
        client.models.generate_content,
        model=GEMINI_MODEL,
        contents=[video_file, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        specs = json.loads(raw.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse Gemini clip analysis: {e}") from e

    if not isinstance(specs, list) or len(specs) == 0:
        raise ValueError("Gemini found no clip-worthy moments in this video")

    return specs


def _validate_clip_spec(spec: dict, index: int) -> tuple[float, float, str]:
    """Return validated (start, end, platform) or raise ValueError."""
    try:
        start = float(spec["start_time"])
        end = float(spec["end_time"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"Clip {index + 1}: invalid timestamps ({e})") from e

    if start < 0:
        raise ValueError(f"Clip {index + 1}: start_time must be >= 0 (got {start})")
    if end <= start:
        raise ValueError(f"Clip {index + 1}: end_time must be > start_time ({start}–{end})")

    platform = str(spec.get("platform", "reels")).lower()
    if platform not in _PLATFORM_CONFIGS:
        logger.warning("Clip %d: unknown platform %r from Gemini, defaulting to 'reels'", index + 1, platform)
        platform = "reels"

    max_dur = _PLATFORM_MAX_S.get(platform, 90)
    if (end - start) > max_dur:
        logger.warning(
            "Clip %d: duration %.1fs exceeds %s max (%ds), trimming",
            index + 1, end - start, platform, max_dur,
        )
        end = start + max_dur

    return start, end, platform


# ── Public API ─────────────────────────────────────────────────────────────────

async def analyze_and_repurpose(
    video_bytes: bytes,
    brand_profile: dict,
    mime_type: str = "video/mp4",
) -> list[dict]:
    """
    Analyze a raw video using Gemini and extract up to 3 platform-ready short clips.

    Args:
        video_bytes: Raw MP4/MOV video bytes.
        brand_profile: Brand Firestore document (needs business_name, tone, industry, etc.)
        mime_type: MIME type of the uploaded video ("video/mp4" or "video/quicktime").

    Returns:
        List of clip dicts, each with keys:
          platform, start_time, end_time, duration_seconds,
          hook, suggested_caption, reason, clip_bytes, filename

    Raises:
        ValueError: Gemini analysis failed or no clips found.
        RuntimeError: FFmpeg not installed or processing failed.
        TimeoutError: Gemini file processing exceeded the timeout ceiling.
    """
    ext = ".mp4" if mime_type == "video/mp4" else ".mov"
    tmpdir = tempfile.mkdtemp(prefix="vrepurpose_")
    try:
        # 1 ─ Write source video to disk
        source_path = os.path.join(tmpdir, f"source_{uuid.uuid4().hex[:8]}{ext}")
        with open(source_path, "wb") as f:
            f.write(video_bytes)

        # 2 ─ Upload to Gemini Files API
        logger.info("Uploading %d-byte video (%s) to Gemini Files API…", len(video_bytes), mime_type)
        video_file, client = await _upload_to_gemini_files(source_path, mime_type)
        logger.info("Gemini file ready: %s", video_file.name)

        # 3 ─ Analyze for clip-worthy moments
        clip_specs = await _analyze_video(video_file, client, brand_profile)
        logger.info("Gemini identified %d clips", len(clip_specs))

        # 4 ─ Clean up Gemini file (awaited, so errors don't swallow silently)
        try:
            await asyncio.to_thread(client.files.delete, name=video_file.name)
        except Exception as e:
            logger.warning("Failed to delete Gemini file %s: %s", video_file.name, e)

        # 5 ─ Extract, format, and collect each clip with FFmpeg
        clips = []
        for i, spec in enumerate(clip_specs[:3]):
            start, end, platform = _validate_clip_spec(spec, i)
            clip_tag = f"clip_{i + 1}_{platform}"
            final_path = os.path.join(tmpdir, f"{clip_tag}.mp4")

            logger.info("Extracting clip %d: %.1f–%.1f → %s", i + 1, start, end, platform)
            await asyncio.to_thread(
                _extract_and_format_clip, source_path, final_path, start, end, platform
            )

            with open(final_path, "rb") as f:
                clip_bytes_data = f.read()

            if len(clip_bytes_data) == 0:
                raise RuntimeError(f"FFmpeg produced an empty file for clip {i + 1}")

            clips.append({
                "platform": platform,
                "start_time": start,
                "end_time": end,
                "duration_seconds": round(end - start, 1),
                "hook": spec.get("hook", ""),
                "suggested_caption": spec.get("suggested_caption", ""),
                "reason": spec.get("reason", ""),
                "content_theme": spec.get("content_theme", ""),
                "clip_bytes": clip_bytes_data,
                "filename": f"{clip_tag}.mp4",
            })

        return clips

    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception as cleanup_err:
            logger.warning("Failed to clean up tmpdir %s: %s", tmpdir, cleanup_err)
