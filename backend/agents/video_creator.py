"""Veo 3.1 video generation agent.

Generates a short video clip from the post's hero image using the Veo API,
uploads the MP4 to GCS, and returns the signed URL.
"""

import asyncio
import logging
import uuid
from google import genai
from google.genai import types

from backend.config import GOOGLE_API_KEY
from backend.platforms import get as get_platform
from backend.services.storage_client import upload_video_to_gcs

logger = logging.getLogger(__name__)

# Veo polling ceiling: 20 minutes
_VEO_POLL_TIMEOUT_S = 20 * 60


def _get_model_and_aspect(
    platform: str, tier: str, has_image: bool = False,
) -> tuple[str, str]:
    # Image-to-video only works on the full model — the fast variant rejects it
    if has_image:
        model = "veo-3.1-generate-preview"
    elif tier == "fast":
        model = "veo-3.1-fast-generate-preview"
    else:
        model = "veo-3.1-generate-preview"
    aspect_ratio = "9:16" if get_platform(platform).is_portrait_video else "16:9"
    return model, aspect_ratio


def _build_prompt(caption: str, brand_profile: dict, platform: str,
                   has_brand_refs: bool = False, edit_prompt: str | None = None) -> str:
    brand_name = brand_profile.get("business_name", "")
    tone = brand_profile.get("tone", "professional and engaging")
    niche = brand_profile.get("industry", "")
    colors = brand_profile.get("colors", [])
    visual_style = brand_profile.get("visual_style", "")
    image_style_directive = brand_profile.get("image_style_directive", "")

    if edit_prompt:
        parts = [
            f"Re-create this {platform}-optimized social media video clip with the following change: {edit_prompt}.",
        ]
    else:
        parts = [
            f"Create a dynamic, eye-catching {platform}-optimized social media video clip.",
        ]
    if brand_name:
        parts.append(f"Brand: {brand_name}.")
    if niche:
        parts.append(f"Industry: {niche}.")
    if tone:
        parts.append(f"Tone: {tone}.")
    if colors:
        parts.append(f"Brand colors: {', '.join(colors[:4])}.")
    if visual_style:
        parts.append(f"Visual style: {visual_style}.")
    if image_style_directive:
        short_directive = image_style_directive[:200]
        parts.append(f"Style guide: {short_directive}.")
    if caption:
        short_caption = caption[:200] + "..." if len(caption) > 200 else caption
        parts.append(f"Post context: {short_caption}")

    if has_brand_refs:
        parts.append(
            "The video should be visually compelling, smooth, and brand-consistent. "
            "Use the provided brand reference assets (logo, product images) faithfully — "
            f"the brand name is exactly \"{brand_name}\". "
            "Do NOT add any other text, watermarks, or made-up logos beyond what is in "
            "the reference assets. Cinematic quality with smooth motion."
        )
    else:
        parts.append(
            "The video should be visually compelling, smooth, and brand-consistent. "
            "CRITICAL: Do NOT include any text, words, brand names, logos, watermarks, "
            "or written content in the video. Pure visual content only — no typography. "
            "Cinematic quality with smooth motion."
        )
    return " ".join(parts)


async def generate_video_clip(
    hero_image_bytes: bytes | None,
    caption: str,
    brand_profile: dict,
    platform: str,
    post_id: str,
    tier: str = "fast",
    edit_prompt: str | None = None,
) -> dict:
    """Generate a video clip using Veo 3.1, upload to GCS, and return metadata.

    Args:
        hero_image_bytes: Image bytes for image-to-video, or None for text-to-video.

    Returns:
        {
            "video_url": str,           # signed GCS URL
            "video_gcs_uri": str,       # gs:// URI
            "duration_seconds": 8,
            "model": str,
            "aspect_ratio": str,
        }
    """
    has_image = hero_image_bytes is not None
    model_name, aspect_ratio = _get_model_and_aspect(platform, tier, has_image=has_image)

    client = genai.Client(api_key=GOOGLE_API_KEY)

    hero_image = None
    if has_image:
        mime = "image/png" if hero_image_bytes[:4] == b'\x89PNG' else "image/jpeg"
        hero_image = types.Image(image_bytes=hero_image_bytes, mime_type=mime)

    prompt = _build_prompt(caption, brand_profile, platform, has_brand_refs=False, edit_prompt=edit_prompt)

    logger.info(
        "Starting Veo video generation: model=%s aspect=%s has_image=%s post_id=%s",
        model_name, aspect_ratio, has_image, post_id,
    )

    loop = asyncio.get_running_loop()

    config = types.GenerateVideosConfig(
        aspect_ratio=aspect_ratio,
        number_of_videos=1,
    )

    if has_image:
        # Try with image first; if Veo rejects it, fall back to text-only.
        try:
            operation = await loop.run_in_executor(
                None,
                lambda: client.models.generate_videos(
                    model=model_name,
                    prompt=prompt,
                    image=hero_image,
                    config=config,
                ),
            )
        except Exception as img_err:
            logger.warning(
                "Veo rejected image-to-video (%s), retrying text-only: %s",
                model_name, img_err,
            )
            operation = await loop.run_in_executor(
                None,
                lambda: client.models.generate_videos(
                    model=model_name,
                    prompt=prompt,
                    config=config,
                ),
            )
    else:
        # Text-to-video (video_first posts with no hero image)
        operation = await loop.run_in_executor(
            None,
            lambda: client.models.generate_videos(
                model=model_name,
                prompt=prompt,
                config=config,
            ),
        )

    logger.info("Veo operation started, polling for completion...")

    # Poll until the operation is complete, with a hard timeout ceiling
    import time as _time
    poll_start = _time.monotonic()
    while not operation.done:
        if _time.monotonic() - poll_start > _VEO_POLL_TIMEOUT_S:
            raise TimeoutError(
                f"Veo video generation timed out after {_VEO_POLL_TIMEOUT_S}s "
                f"for post {post_id}"
            )
        await asyncio.sleep(10)
        operation = await loop.run_in_executor(
            None,
            lambda: client.operations.get(operation),
        )
        logger.info("Veo operation status: done=%s", operation.done)

    logger.info("Veo operation complete, downloading video via files API...")

    # Use client.files.download() — Veo doesn't populate video_bytes directly
    if (
        operation.response is None
        or operation.response.generated_videos is None
        or len(operation.response.generated_videos) == 0
    ):
        raise RuntimeError(
            f"Veo completed but returned no video for post {post_id}. "
            "This usually means the prompt was filtered or the generation failed silently."
        )
    gen_video = operation.response.generated_videos[0]
    video_bytes = await loop.run_in_executor(
        None,
        lambda: client.files.download(file=gen_video),
    )

    # Upload MP4 to GCS and get signed URL + GCS URI
    video_url, video_gcs_uri = await upload_video_to_gcs(video_bytes, post_id)

    logger.info("Video uploaded to GCS: %s", video_gcs_uri)

    return {
        "video_url": video_url,
        "video_gcs_uri": video_gcs_uri,
        "duration_seconds": 8,
        "model": model_name,
        "aspect_ratio": aspect_ratio,
    }
