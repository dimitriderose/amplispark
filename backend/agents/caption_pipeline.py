"""Caption text processing: condensing, encoding fixes, markdown stripping."""

import asyncio
import logging
import re

from google.genai import types

from backend.agents.carousel_builder import _SLIDE_RE
from backend.clients import get_genai_client
from backend.config import GEMINI_MODEL
from backend.platforms import get as get_platform

logger = logging.getLogger(__name__)


def _fix_mojibake(text: str) -> str:
    """Detect and repair UTF-8→CP1252 double-encoding artifacts (quotes, dashes, emojis).

    Works by reversing the double-encoding: encode mojibake chars back to CP1252
    bytes, then decode as UTF-8. Characters that aren't CP1252-encodable (real emojis)
    are preserved as-is. Non-mojibake Latin chars (é, ñ, etc.) survive via surrogate
    round-trip back to their original CP1252 character.
    """
    # Quick check: mojibake from CP1252 always involves these starter chars
    if not any(c in text for c in "âÃðÂ"):
        return text

    result: list[str] = []
    buf: list[str] = []

    for ch in text:
        try:
            ch.encode("cp1252")
            buf.append(ch)
        except UnicodeEncodeError:
            # Non-CP1252 char (e.g. real emoji U+1F4xx) — flush buffer, keep char
            if buf:
                result.append(_roundtrip_cp1252(buf))
                buf = []
            result.append(ch)

    if buf:
        result.append(_roundtrip_cp1252(buf))

    return "".join(result)


def _roundtrip_cp1252(buf: list[str]) -> str:
    """Reverse CP1252 mojibake in a buffer of CP1252-encodable chars."""
    chunk = "".join(buf)
    try:
        raw = chunk.encode("cp1252")
        decoded = raw.decode("utf-8", errors="surrogateescape")
        # Surrogates represent bytes that weren't valid UTF-8 — map them back
        # to the original CP1252 character (e.g. 0xE9 → é)
        out: list[str] = []
        for ch in decoded:
            if "\udc80" <= ch <= "\udcff":
                byte_val = ord(ch) - 0xDC00
                out.append(bytes([byte_val]).decode("cp1252"))
            else:
                out.append(ch)
        return "".join(out)
    except (UnicodeDecodeError, UnicodeEncodeError):
        return chunk


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting that social platforms can't render."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Strip markdown bullet lists: "* item" or "- item" at line start
    text = re.sub(r'^\s*[\*\-]\s+', '', text, flags=re.MULTILINE)
    return text


def _enforce_char_limit(caption: str, platform: str, derivative_type: str = "") -> str:
    """Hard-truncate caption to platform char limit. Final safety net only."""
    spec = get_platform(platform)
    limits = spec.char_limits
    if not limits:
        return caption
    limit = limits.get(derivative_type) or limits.get("default")
    if not limit or len(caption) <= limit:
        return caption
    # Carousel-aware: cut at last complete slide boundary
    if derivative_type == "carousel":
        slide_starts = [m.start() for m in _SLIDE_RE.finditer(caption)]
        for pos in reversed(slide_starts):
            if pos <= limit - 1:
                truncated = caption[:pos].rstrip()
                if len(truncated) > limit // 3:
                    return truncated
                break
    # Default: word-boundary truncation
    truncated = caption[: limit - 1]
    last_space = truncated.rfind(" ")
    if last_space > limit // 2:
        truncated = truncated[:last_space]
    return truncated + "…"


async def _smart_condense(caption: str, platform: str, derivative_type: str) -> str:
    """If caption exceeds the char limit, ask the LLM to shorten it intelligently.

    Falls back to hard truncation if the LLM condense fails.
    Returns the caption unchanged if already within limits.
    """
    spec = get_platform(platform)
    limits = spec.char_limits
    if not limits:
        return caption
    limit = limits.get(derivative_type) or limits.get("default")
    if not limit or len(caption) <= limit:
        return caption

    logger.info(
        "Caption over limit (%d/%d) for %s/%s — smart condensing",
        len(caption), limit, platform, derivative_type,
    )
    condense_prompt = (
        f"Shorten this {platform} {derivative_type} caption to UNDER {limit} characters. "
        f"Current length: {len(caption)} characters.\n\n"
        f"RULES:\n"
        f"- Keep the hook (first sentence) intact or make it punchier\n"
        f"- Cut from the middle, never the hook or closing thought\n"
        f"- For carousel captions: PRESERVE all Slide N: labels and the same number of slides. "
        f"Shorten each slide's body, do NOT remove entire slides.\n"
        f"- The result must be a COMPLETE thought — no trailing '...' or cut-off sentences\n"
        f"- Do NOT add hashtags, explanations, or meta-commentary\n"
        f"- Output ONLY the shortened caption\n\n"
        f"CAPTION:\n{caption}"
    )
    try:
        resp = await asyncio.to_thread(
            get_genai_client().models.generate_content,
            model=GEMINI_MODEL,
            contents=condense_prompt,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        condensed = _strip_markdown(resp.text.strip())
        if len(condensed) <= limit and len(condensed) > limit // 3:
            # For carousels, verify slide count preserved
            if derivative_type == "carousel":
                original_count = len(_SLIDE_RE.findall(caption))
                condensed_count = len(_SLIDE_RE.findall(condensed))
                if condensed_count < original_count:
                    logger.warning(
                        "Smart condense dropped slides (%d→%d) — rejecting",
                        original_count, condensed_count,
                    )
                    return _enforce_char_limit(caption, platform, derivative_type)
            logger.info("Smart condense: %d → %d chars", len(caption), len(condensed))
            return condensed
        logger.warning(
            "Smart condense out of range (%d chars, limit %d) — hard truncating",
            len(condensed), limit,
        )
    except Exception as e:
        logger.warning("Smart condense failed: %s — hard truncating", e)
    return _enforce_char_limit(caption, platform, derivative_type)
