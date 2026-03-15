"""Carousel slide parsing and headline extraction."""

import re


_SLIDE_RE = re.compile(r"Slide\s*\d+\s*[:\-–]\s*", re.IGNORECASE)


def _parse_slide_descriptions(caption: str, max_slides: int = 10) -> list[str]:
    """Extract per-slide text from a carousel-formatted caption."""
    parts = _SLIDE_RE.split(caption)
    # First part is usually empty or preamble text before "Slide 1:"
    slides = [p.strip() for p in parts[1:] if p.strip()]
    return slides[:max_slides]


def _extract_slide_headline(slide_text: str) -> str:
    """Extract the first sentence (short headline) from a slide's text for overlay.

    Prefers a clean sentence break within 80 chars; falls back to word-boundary
    truncation. Never cuts mid-word.
    """
    # Try to find the first sentence end within a generous limit
    for sep in ['. ', '! ', '? ', '.\n', '!\n', '?\n']:
        idx = slide_text.find(sep)
        if idx != -1 and idx <= 80:
            return slide_text[:idx + 1].strip()
    # Also try colon, em-dash, semicolon, or ellipsis as natural break points
    for sep in [': ', ' — ', '; ', '… ', '... ', '...\n']:
        idx = slide_text.find(sep)
        if idx != -1 and idx <= 60:
            if sep == ': ' and idx < 15:
                continue  # Skip label prefix like "Technique: ..."
            return slide_text[:idx].strip()
    if len(slide_text) <= 60:
        return slide_text
    # Truncate at last word boundary, never mid-word
    truncated = slide_text[:60]
    last_space = truncated.rfind(' ')
    return (truncated[:last_space] if last_space > 0 else truncated) + '…'
