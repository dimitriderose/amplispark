"""Unit tests for backend/tools/brand_tools.py."""

from backend.tools.brand_tools import analyze_brand_colors, extract_brand_voice

# ---------------------------------------------------------------------------
# analyze_brand_colors tests
# ---------------------------------------------------------------------------


def test_analyze_brand_colors_returns_dict_with_keys():
    """analyze_brand_colors returns dict with primary/secondary/accent/background."""
    colors = ["#3a86ff", "#ff6b6b", "#8b5cf6", "#2ecc71"]
    result = analyze_brand_colors(colors)

    assert "primary" in result
    assert "secondary" in result
    assert "accent" in result
    assert "background" in result


def test_analyze_brand_colors_returns_most_frequent_as_primary():
    """Most frequent color becomes primary."""
    # #3a86ff appears 3 times, #ff6b6b once
    colors = ["#3a86ff", "#3a86ff", "#3a86ff", "#ff6b6b"]
    result = analyze_brand_colors(colors)
    assert result["primary"] == "#3a86ff"


def test_analyze_brand_colors_empty_list_returns_defaults():
    """Empty colors list returns default brand colors."""
    result = analyze_brand_colors([])
    assert result["primary"] == "#5B5FF6"
    assert result["secondary"] == "#8B5CF6"
    assert result["accent"] == "#FF6B6B"
    assert result["background"] == "#FFFFFF"


def test_analyze_brand_colors_filters_near_whites():
    """Near-white colors are excluded from brand palette selection."""
    colors = ["#fafafa", "#f8f8f8", "#3a86ff"]
    result = analyze_brand_colors(colors)
    assert result["primary"] == "#3a86ff"


def test_analyze_brand_colors_filters_near_blacks():
    """Near-black colors are excluded from brand palette selection."""
    colors = ["#111111", "#0a0a0a", "#3a86ff"]
    result = analyze_brand_colors(colors)
    assert result["primary"] == "#3a86ff"


def test_analyze_brand_colors_only_neutrals_returns_defaults():
    """When all colors are neutrals, defaults are used."""
    colors = ["#ffffff", "#f0f0f0", "#111111"]
    result = analyze_brand_colors(colors)
    assert result["primary"] == "#5B5FF6"  # default fallback


def test_analyze_brand_colors_background_always_white():
    """background key is always #FFFFFF regardless of input."""
    colors = ["#3a86ff", "#ff6b6b"]
    result = analyze_brand_colors(colors)
    assert result["background"] == "#FFFFFF"


def test_analyze_brand_colors_single_color():
    """Single brand color fills primary; secondary and accent use defaults."""
    colors = ["#3a86ff"]
    result = analyze_brand_colors(colors)
    assert result["primary"] == "#3a86ff"
    assert result["secondary"] == "#8B5CF6"  # default
    assert result["accent"] == "#FF6B6B"  # default


def test_analyze_brand_colors_invalid_hex_handled():
    """Invalid hex colors don't crash — they are treated as neutral and filtered."""
    colors = ["#ZZZZGG", "#3a86ff"]
    # Should not raise; #ZZZZGG triggers exception in is_neutral → treated as neutral
    result = analyze_brand_colors(colors)
    assert result["primary"] == "#3a86ff"


# ---------------------------------------------------------------------------
# extract_brand_voice tests
# ---------------------------------------------------------------------------


def test_extract_brand_voice_returns_dict_with_keys():
    """extract_brand_voice returns dict with detected_tones, word_count, reading_level."""
    text = "We are a professional enterprise solution provider with proven expertise."
    result = extract_brand_voice(text)

    assert "detected_tones" in result
    assert "word_count" in result
    assert "approximate_reading_level" in result


def test_extract_brand_voice_detects_professional_tone():
    """Professional keywords trigger 'professional' in detected_tones."""
    text = "We provide professional enterprise solutions with expertise."
    result = extract_brand_voice(text)
    assert "professional" in result["detected_tones"]


def test_extract_brand_voice_detects_friendly_tone():
    """Friendly keywords trigger 'friendly' in detected_tones."""
    text = "Welcome to our community! Join us and love the experience together."
    result = extract_brand_voice(text)
    assert "friendly" in result["detected_tones"]


def test_extract_brand_voice_detects_playful_tone():
    """Playful keywords trigger 'playful' in detected_tones."""
    text = "This is amazing and so cool! Wow, what a fun experience!"
    result = extract_brand_voice(text)
    assert "playful" in result["detected_tones"]


def test_extract_brand_voice_caps_at_three_tones():
    """detected_tones is capped at 3 entries."""
    text = (
        "professional expertise proven trusted welcome love fun amazing cool innovative transform"
    )
    result = extract_brand_voice(text)
    assert len(result["detected_tones"]) <= 3


def test_extract_brand_voice_defaults_on_no_signals():
    """Text with no tone signals returns default tones."""
    text = "The cat sat on the mat by the river."
    result = extract_brand_voice(text)
    assert result["detected_tones"] == ["professional", "approachable"]


def test_extract_brand_voice_word_count_is_correct():
    """word_count matches the actual number of words."""
    text = "one two three four five"
    result = extract_brand_voice(text)
    assert result["word_count"] == 5


def test_extract_brand_voice_conversational_for_short_sentences():
    """Short average sentence length → conversational reading level."""
    # Few sentences, many words per sentence → avg > 20 → formal
    # Many short sentences → avg < 20 → conversational
    text = "Hello. Hi. Yes. No. Great. OK. Sure. Fine."  # avg ~1 word per sentence
    result = extract_brand_voice(text)
    assert result["approximate_reading_level"] == "conversational"


def test_extract_brand_voice_formal_for_long_sentences():
    """Long sentences produce 'formal' reading level.

    The implementation computes avg_sentence_len = word_count / sentence_count
    where sentences are split on '.'.  A 50-word single clause with no internal
    periods splits into ["<words>", ""] → 2 elements, so avg = 50/2 = 25 > 20.
    """
    # 50 words, no internal periods → word_count=50, sentence_count=2, avg=25 → formal
    long_sentence = " ".join(["word"] * 50) + "."
    result = extract_brand_voice(long_sentence)
    assert result["approximate_reading_level"] == "formal"


def test_extract_brand_voice_empty_string():
    """Empty string input does not crash and returns word_count=0."""
    result = extract_brand_voice("")
    assert "word_count" in result
    # "".split() returns [] → len([]) = 0
    assert result["word_count"] == 0
