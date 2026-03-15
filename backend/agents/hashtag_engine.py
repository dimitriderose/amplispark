"""Hashtag sanitization and validation."""

import re

from backend.platforms import get as get_platform


# Common English stopwords that should never be hashtags
_HASHTAG_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "is", "it", "by", "as", "be", "was", "are", "has", "had", "do",
    "if", "my", "me", "we", "he", "she", "no", "so", "up", "out", "not",
    "you", "your", "our", "its", "his", "her", "this", "that", "with",
    "from", "here", "heres", "image", "post", "caption",
})

_VALID_HASHTAG_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _sanitize_hashtags(raw_tags: list[str], platform: str) -> list[str]:
    """Clean and validate hashtags, enforcing per-platform limits."""
    limit = get_platform(platform).hashtag_limit
    clean = []
    for tag in raw_tags:
        tag = tag.strip().lstrip("#").strip()
        if len(tag) < 3:
            continue
        if tag.lower() in _HASHTAG_STOPWORDS:
            continue
        if not _VALID_HASHTAG_RE.match(tag):
            continue
        # Mastodon: CamelCase hashtags for screen reader accessibility
        if platform == "mastodon":
            tag = ''.join(word.capitalize() for word in re.findall(r'[a-zA-Z][a-z]*|[0-9]+', tag))
        clean.append(tag)
    return clean[:limit]
