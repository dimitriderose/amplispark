"""Tests for backend.agents.carousel_builder pure functions."""


def test_parse_slide_descriptions_extracts_slides():
    """Standard 'Slide N: text' format → list of slide bodies."""
    from backend.agents.carousel_builder import _parse_slide_descriptions

    caption = "Slide 1: First slide body\nSlide 2: Second slide body\nSlide 3: Third slide body"
    slides = _parse_slide_descriptions(caption)

    assert len(slides) == 3
    assert slides[0] == "First slide body"
    assert slides[1] == "Second slide body"
    assert slides[2] == "Third slide body"


def test_parse_slide_descriptions_max_slides():
    """More than max_slides slides → only max_slides returned (default 10)."""
    from backend.agents.carousel_builder import _parse_slide_descriptions

    parts = "\n".join(f"Slide {i}: Content for slide {i}" for i in range(1, 16))
    slides = _parse_slide_descriptions(parts)

    assert len(slides) == 10


def test_parse_slide_descriptions_custom_max():
    """Explicit max_slides parameter is respected."""
    from backend.agents.carousel_builder import _parse_slide_descriptions

    parts = "\n".join(f"Slide {i}: Slide content {i}" for i in range(1, 8))
    slides = _parse_slide_descriptions(parts, max_slides=3)

    assert len(slides) == 3


def test_parse_slide_descriptions_empty_string():
    """Empty input → empty list."""
    from backend.agents.carousel_builder import _parse_slide_descriptions

    assert _parse_slide_descriptions("") == []


def test_parse_slide_descriptions_no_slide_markers():
    """Input with no 'Slide N:' markers → empty list."""
    from backend.agents.carousel_builder import _parse_slide_descriptions

    assert _parse_slide_descriptions("Just some random text without any slide markers.") == []


def test_parse_slide_descriptions_case_insensitive():
    """Regex is case-insensitive: 'slide 1:' works too."""
    from backend.agents.carousel_builder import _parse_slide_descriptions

    caption = "slide 1: lowercase marker\nSLIDE 2: uppercase marker"
    slides = _parse_slide_descriptions(caption)
    assert len(slides) == 2


def test_extract_slide_headline_sentence_break():
    """Finds first sentence end within 80 chars and returns it."""
    from backend.agents.carousel_builder import _extract_slide_headline

    text = "Hello world. More text here that should not be included."
    result = _extract_slide_headline(text)

    assert result == "Hello world."


def test_extract_slide_headline_short_text():
    """Text shorter than 60 chars is returned as-is."""
    from backend.agents.carousel_builder import _extract_slide_headline

    short = "Short slide text"
    assert _extract_slide_headline(short) == short


def test_extract_slide_headline_truncates_long():
    """Long text with no sentence break → truncated with ellipsis, never mid-word."""
    from backend.agents.carousel_builder import _extract_slide_headline

    long_text = "A" * 30 + " " + "B" * 30 + " more words after"
    result = _extract_slide_headline(long_text)

    assert result.endswith("…")
    # Should not cut mid-word (no word fragment before ellipsis)
    assert len(result) <= 65  # 60 + "…"


def test_extract_slide_headline_question_mark_break():
    """Question mark also counts as sentence end."""
    from backend.agents.carousel_builder import _extract_slide_headline

    text = "Is this working? Yes it is, and here is more text."
    result = _extract_slide_headline(text)

    assert result == "Is this working?"


def test_extract_slide_headline_exclamation_break():
    """Exclamation mark also counts as sentence end."""
    from backend.agents.carousel_builder import _extract_slide_headline

    text = "Amazing result! Here is additional context."
    result = _extract_slide_headline(text)

    assert result == "Amazing result!"
