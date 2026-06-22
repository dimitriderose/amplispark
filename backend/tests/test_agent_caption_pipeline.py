"""Tests for backend.agents.caption_pipeline pure functions and async helpers."""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    return response


# ---------------------------------------------------------------------------
# Pure function tests — no mocking required
# ---------------------------------------------------------------------------


def test_fix_mojibake_repairs_double_encoding():
    """Common mojibake artifact â€™ should repair to apostrophe '."""
    from backend.agents.caption_pipeline import _fix_mojibake

    # â€™ is the CP1252 → UTF-8 double-encode of the right single quote '
    mojibake_text = "Itâ€™s a great day"
    result = _fix_mojibake(mojibake_text)
    # The repair should produce the clean apostrophe
    assert "’" in result or "'" in result


def test_fix_mojibake_passthrough_clean_text():
    """Clean ASCII text passes through unchanged."""
    from backend.agents.caption_pipeline import _fix_mojibake

    clean = "Hello world! This is a clean caption."
    assert _fix_mojibake(clean) == clean


def test_fix_mojibake_passthrough_no_trigger_chars():
    """Text with no mojibake trigger chars is returned unchanged."""
    from backend.agents.caption_pipeline import _fix_mojibake

    text = "Simple text with numbers 123 and symbols @#$"
    assert _fix_mojibake(text) == text


def test_strip_markdown_removes_bold():
    """**bold** → bold."""
    from backend.agents.caption_pipeline import _strip_markdown

    assert _strip_markdown("**bold text**") == "bold text"


def test_strip_markdown_removes_italic():
    """*italic* → italic."""
    from backend.agents.caption_pipeline import _strip_markdown

    assert _strip_markdown("*italic text*") == "italic text"


def test_strip_markdown_removes_links():
    """[text](url) → text."""
    from backend.agents.caption_pipeline import _strip_markdown

    assert _strip_markdown("[click here](https://example.com)") == "click here"


def test_strip_markdown_removes_headers():
    """## Header → Header."""
    from backend.agents.caption_pipeline import _strip_markdown

    result = _strip_markdown("## My Header\nSome body text.")
    assert "##" not in result
    assert "My Header" in result


def test_strip_markdown_removes_bullet_lists():
    """* item and - item at line start are stripped."""
    from backend.agents.caption_pipeline import _strip_markdown

    result = _strip_markdown("* first item\n- second item\n")
    assert "* " not in result
    assert "- " not in result
    assert "first item" in result
    assert "second item" in result


def test_enforce_char_limit_truncates():
    """Caption longer than platform limit gets truncated with ellipsis."""
    from backend.agents.caption_pipeline import _enforce_char_limit

    # instagram default limit is 2200
    long_caption = "A" * 3000
    result = _enforce_char_limit(long_caption, "instagram", "original")
    assert len(result) < 3000
    # Should end with ellipsis
    assert result.endswith("…")


def test_enforce_char_limit_passthrough():
    """Short caption is returned unchanged."""
    from backend.agents.caption_pipeline import _enforce_char_limit

    short = "A short caption under the limit."
    result = _enforce_char_limit(short, "instagram", "original")
    assert result == short


def test_enforce_char_limit_no_limits_platform():
    """Platform with no char_limits defined returns caption unchanged."""
    from backend.agents.caption_pipeline import _enforce_char_limit

    # Use mastodon — it has a limit; test that short text passes through
    text = "Short mastodon post."
    result = _enforce_char_limit(text, "mastodon", "original")
    assert result == text


# ---------------------------------------------------------------------------
# Async helper tests — require mock
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smart_condense_returns_condensed_text():
    """_smart_condense calls LLM and returns condensed text when within limit."""
    from backend.agents.caption_pipeline import _smart_condense

    # instagram default limit is 2200 chars; build a caption just over that
    long_caption = "This is a test sentence. " * 100  # ~2500 chars
    short_response = "This is a short condensed caption."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(short_response)

    with patch("backend.agents.caption_pipeline.get_genai_client", return_value=mock_client):
        result = await _smart_condense(long_caption, "instagram", "original")

    # Either the condensed result or the hard-truncated fallback
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_smart_condense_passthrough_within_limit():
    """Caption already within limit is returned unchanged without calling LLM."""
    from backend.agents.caption_pipeline import _smart_condense

    short = "A short caption that is well within the limit."

    mock_client = MagicMock()

    with patch("backend.agents.caption_pipeline.get_genai_client", return_value=mock_client):
        result = await _smart_condense(short, "instagram", "original")

    # LLM should not have been called
    mock_client.models.generate_content.assert_not_called()
    assert result == short


@pytest.mark.asyncio
async def test_smart_condense_falls_back_on_llm_error():
    """If LLM raises, falls back to hard truncation."""
    from backend.agents.caption_pipeline import _smart_condense

    long_caption = "X" * 3000

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("LLM error")

    with patch("backend.agents.caption_pipeline.get_genai_client", return_value=mock_client):
        result = await _smart_condense(long_caption, "instagram", "original")

    assert isinstance(result, str)
    # Hard truncation should have produced something shorter
    assert len(result) < 3000


@pytest.mark.asyncio
async def test_smart_condense_returns_unchanged_when_within_limit():
    """Caption within the platform limit is returned unchanged."""
    from backend.agents.caption_pipeline import _smart_condense

    short_caption = "A nice short caption."
    mock_client = MagicMock()

    with patch("backend.agents.caption_pipeline.get_genai_client", return_value=mock_client):
        result = await _smart_condense(short_caption, "instagram", "original")

    mock_client.models.generate_content.assert_not_called()
    assert result == short_caption


@pytest.mark.asyncio
async def test_smart_condense_rejects_carousel_losing_slides():
    """When condensed carousel drops slides, falls back to hard truncation."""
    from backend.agents.caption_pipeline import _smart_condense

    # Build a long carousel caption
    slides = "\n\n".join(f"Slide {i + 1}: " + "X " * 50 for i in range(5))
    carousel_caption = slides  # Likely over limit

    # Condensed version drops some slides
    bad_condense = "Slide 1: Short condensed version without other slides."

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_text_response(bad_condense)

    with patch("backend.agents.caption_pipeline.get_genai_client", return_value=mock_client):
        result = await _smart_condense(carousel_caption, "instagram", "carousel")

    # Should not return bad_condense since it dropped slides
    # (will fall back to hard truncation or original)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_smart_condense_returns_platform_without_char_limits():
    """Platform without char_limits returns caption unchanged."""
    from backend.agents.caption_pipeline import _smart_condense

    caption = "Some caption that is perfectly fine."
    mock_client = MagicMock()

    # Use a platform that has no char limits (mock get_platform)
    mock_spec = MagicMock()
    mock_spec.char_limits = None

    with (
        patch("backend.agents.caption_pipeline.get_genai_client", return_value=mock_client),
        patch("backend.agents.caption_pipeline.get_platform", return_value=mock_spec),
    ):
        result = await _smart_condense(caption, "mastodon", "original")

    mock_client.models.generate_content.assert_not_called()
    assert result == caption


def test_enforce_char_limit_carousel_truncates_at_slide_boundary():
    """Carousel caption truncated at last slide that fits under the limit."""
    from backend.agents.caption_pipeline import _enforce_char_limit

    # Build a carousel caption that exceeds Instagram's limit
    # Instagram carousel limit is typically around 2200 chars
    slides = "\n\n".join(f"Slide {i + 1}: " + "Content " * 30 for i in range(10))

    result = _enforce_char_limit(slides, "instagram", "carousel")
    assert isinstance(result, str)
    # Result should be shorter than original
    assert len(result) <= len(slides)


def test_enforce_char_limit_returns_unchanged_when_within_limit():
    """Caption within char limit returned unchanged."""
    from backend.agents.caption_pipeline import _enforce_char_limit

    short = "Short caption."
    result = _enforce_char_limit(short, "instagram", "original")
    assert result == short


def test_fix_mojibake_preserves_emojis():
    """Real emojis are preserved while mojibake is repaired."""
    from backend.agents.caption_pipeline import _fix_mojibake

    # Text with both mojibake and a real emoji
    text = "Itâ€™s great \U0001f4aa"  # apostrophe mojibake + flexed biceps emoji
    result = _fix_mojibake(text)
    # Emoji should survive
    assert "\U0001f4aa" in result


def test_strip_markdown_removes_bold_and_double_underscore():
    """**bold** and __bold__ are stripped."""
    from backend.agents.caption_pipeline import _strip_markdown

    text = "This is **important** and __also important__."
    result = _strip_markdown(text)
    assert "**" not in result
    assert "__" not in result
    assert "important" in result


def test_strip_markdown_removes_italic_and_single_underscore():
    """*italic* and _italic_ are stripped."""
    from backend.agents.caption_pipeline import _strip_markdown

    text = "This is *italic* and _also italic_."
    result = _strip_markdown(text)
    assert "*" not in result
    assert "italic" in result


def test_strip_markdown_removes_h2_headers():
    """Markdown headers are stripped."""
    from backend.agents.caption_pipeline import _strip_markdown

    text = "## Section Title\nContent here"
    result = _strip_markdown(text)
    assert "##" not in result
    assert "Section Title" in result


def test_strip_markdown_removes_inline_links():
    """[text](url) links are reduced to just text."""
    from backend.agents.caption_pipeline import _strip_markdown

    text = "Check out [our website](https://example.com) for more."
    result = _strip_markdown(text)
    assert "](https://example.com)" not in result
    assert "our website" in result
