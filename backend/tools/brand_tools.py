from collections import Counter


def analyze_brand_colors(css_colors: list[str], logo_path: str | None = None) -> dict:
    """Analyze extracted colors to determine brand palette.

    Returns primary, secondary, accent color suggestions.
    """
    if not css_colors:
        return {
            "primary": "#5B5FF6",
            "secondary": "#8B5CF6",
            "accent": "#FF6B6B",
            "background": "#FFFFFF",
        }

    # Count color frequency
    color_counts = Counter(css_colors)
    sorted_colors = [c for c, _ in color_counts.most_common()]

    # Filter out near-whites and near-blacks
    def is_neutral(hex_color: str) -> bool:
        try:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            brightness = (r + g + b) / 3
            return brightness > 230 or brightness < 25
        except Exception:
            return True

    brand_colors = [c for c in sorted_colors if not is_neutral(c)]

    return {
        "primary": brand_colors[0] if len(brand_colors) > 0 else "#5B5FF6",
        "secondary": brand_colors[1] if len(brand_colors) > 1 else "#8B5CF6",
        "accent": brand_colors[2] if len(brand_colors) > 2 else "#FF6B6B",
        "background": "#FFFFFF",
    }


def extract_brand_voice(text_content: str) -> dict:
    """Analyze text content to extract brand voice characteristics."""
    word_count = len(text_content.split())
    avg_sentence_len = len(text_content.split(".")) and word_count / max(
        len(text_content.split(".")), 1
    )

    # Very basic heuristic analysis
    tone_signals = {
        "professional": ["professional", "expertise", "solution", "enterprise", "leading"],
        "friendly": ["welcome", "hello", "join", "together", "community", "love"],
        "playful": ["fun", "exciting", "amazing", "cool", "awesome", "wow"],
        "authoritative": ["proven", "trusted", "established", "authority", "expert"],
        "innovative": ["innovative", "cutting-edge", "modern", "transform", "future"],
    }

    text_lower = text_content.lower()
    detected_tones = []
    for tone, signals in tone_signals.items():
        if any(s in text_lower for s in signals):
            detected_tones.append(tone)

    return {
        "detected_tones": detected_tones[:3]
        if detected_tones
        else ["professional", "approachable"],
        "word_count": word_count,
        "approximate_reading_level": "conversational" if avg_sentence_len < 20 else "formal",
    }
