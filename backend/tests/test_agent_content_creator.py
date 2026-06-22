"""Unit tests for backend/agents/content_creator.py — pure helper functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.content_creator import _build_dedup_block, _validate_format

# ---------------------------------------------------------------------------
# _validate_format tests
# ---------------------------------------------------------------------------


def test_validate_format_carousel_requires_slides():
    """Carousel caption without 'Slide 1' and 'Slide 2' returns False."""
    caption = "Just a plain caption with no slide structure."
    assert _validate_format(caption, "carousel") is False


def test_validate_format_carousel_passes_with_slides():
    """Carousel caption with 'Slide 1' and 'Slide 2' returns True."""
    caption = "Slide 1: Hook line here\nSlide 2: More content here"
    assert _validate_format(caption, "carousel") is True


def test_validate_format_thread_requires_numbering_slash():
    """Thread caption with '1/' present returns True."""
    caption = "1/ Here is my first tweet in the thread."
    assert _validate_format(caption, "thread_hook") is True


def test_validate_format_thread_requires_numbering_paren():
    """Thread caption with '1)' present also returns True."""
    caption = "1) Here is the first post in the thread."
    assert _validate_format(caption, "thread_hook") is True


def test_validate_format_thread_fails_without_numbering():
    """Thread caption without '1/' or '1)' returns False."""
    caption = "Just a plain post with no numbering."
    assert _validate_format(caption, "thread_hook") is False


def test_validate_format_pin_requires_labels_title():
    """Pin caption with 'PIN TITLE' present returns True."""
    caption = "PIN TITLE: How to Grow Your Business\nPIN DESCRIPTION: Tips and tricks."
    assert _validate_format(caption, "pin") is True


def test_validate_format_pin_requires_labels_description():
    """Pin caption with 'PIN DESCRIPTION' (case-insensitive) returns True."""
    caption = "pin description: All about growing your business online."
    assert _validate_format(caption, "pin") is True


def test_validate_format_pin_fails_without_labels():
    """Pin caption without PIN TITLE or PIN DESCRIPTION returns False."""
    caption = "Just a plain caption with no pin labels."
    assert _validate_format(caption, "pin") is False


def test_validate_format_other_types_return_true():
    """Any other derivative_type always returns True."""
    for dtype in ("original", "story", "blog_snippet", "video_first", "reel"):
        assert _validate_format("Any caption text here.", dtype) is True


def test_validate_format_non_string_caption_returns_false():
    """Non-string caption returns False regardless of derivative_type."""
    assert _validate_format(None, "original") is False  # type: ignore[arg-type]
    assert _validate_format(123, "carousel") is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _build_dedup_block tests
# ---------------------------------------------------------------------------


def test_build_dedup_block_empty_list():
    """No prior hooks → empty string."""
    assert _build_dedup_block([]) == ""


def test_build_dedup_block_none():
    """None prior hooks → empty string."""
    assert _build_dedup_block(None) == ""


def test_build_dedup_block_with_hooks():
    """Prior hooks → string contains 'CRITICAL' and each hook text."""
    hooks = ["Stop scrolling and read this", "You won't believe this tip"]
    result = _build_dedup_block(hooks)

    assert "CRITICAL" in result
    assert "Stop scrolling and read this" in result
    assert "You won't believe this tip" in result


def test_build_dedup_block_single_hook():
    """Single hook → included in output."""
    hooks = ["Only one hook this week"]
    result = _build_dedup_block(hooks)
    assert "Only one hook this week" in result
    assert "CRITICAL" in result


def test_build_dedup_block_format():
    """Block ends with newline after instruction."""
    hooks = ["Hook A", "Hook B"]
    result = _build_dedup_block(hooks)
    # Must end with trailing newline(s) and contain the DIFFERENT directive
    assert "COMPLETELY DIFFERENT" in result
    assert result.endswith("\n")


# ---------------------------------------------------------------------------
# _generate_image_with_retry tests
# ---------------------------------------------------------------------------


def _make_image_response(data: bytes, mime: str = "image/png") -> MagicMock:
    part = MagicMock()
    part.inline_data = MagicMock()
    part.inline_data.data = data
    part.inline_data.mime_type = mime
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    resp = MagicMock()
    resp.candidates = [candidate]
    return resp


@pytest.mark.asyncio
async def test_generate_image_with_retry_returns_bytes_on_success():
    from backend.agents.content_creator import _generate_image_with_retry

    fake_bytes = b"PNG" + b"\x00" * 6000
    fake_resp = _make_image_response(fake_bytes)
    with patch("backend.agents.content_creator.get_genai_client") as mock_get:
        mock_get.return_value.models.generate_content.return_value = fake_resp
        data, mime = await _generate_image_with_retry(["prompt text"])
    assert data == fake_bytes
    assert "png" in mime


@pytest.mark.asyncio
async def test_generate_image_with_retry_returns_none_on_empty_candidates():
    from backend.agents.content_creator import _generate_image_with_retry

    resp = MagicMock()
    resp.candidates = []
    with patch("backend.agents.content_creator.get_genai_client") as mock_get:
        mock_get.return_value.models.generate_content.return_value = resp
        data, mime = await _generate_image_with_retry(["prompt"], max_retries=0)
    assert data is None


@pytest.mark.asyncio
async def test_generate_image_with_retry_retries_on_exception():
    from backend.agents.content_creator import _generate_image_with_retry

    fake_bytes = b"PNG" + b"\x00" * 6000
    fake_resp = _make_image_response(fake_bytes)
    call_count = 0

    def _side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("transient error")
        return fake_resp

    with patch("backend.agents.content_creator.get_genai_client") as mock_get:
        mock_get.return_value.models.generate_content.side_effect = _side_effect
        with patch("asyncio.sleep", new_callable=AsyncMock):
            data, _ = await _generate_image_with_retry(["prompt"], max_retries=1)
    assert data == fake_bytes


# ---------------------------------------------------------------------------
# _generate_alt_text tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_alt_text_returns_none_for_non_alt_text_platform():
    from backend.agents.content_creator import _generate_alt_text

    # Instagram does not require alt text — should return None without calling genai
    with patch("backend.agents.content_creator.get_genai_client") as mock_get:
        result = await _generate_alt_text(b"imgbytes", "tech tips", "instagram")
    assert result is None
    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_generate_alt_text_returns_none_on_exception():
    from backend.agents.content_creator import _generate_alt_text

    with patch("backend.agents.content_creator.get_genai_client") as mock_get:
        mock_get.return_value.models.generate_content.side_effect = RuntimeError("api down")
        # mastodon requires alt text — but if it fails, should return None gracefully
        with patch("backend.agents.content_creator.get_platform") as mock_plat:
            mock_spec = MagicMock()
            mock_spec.alt_text_required = True
            mock_plat.return_value = mock_spec
            result = await _generate_alt_text(b"imgbytes", "topic", "mastodon")
    assert result is None


# ---------------------------------------------------------------------------
# _generate_carousel_images tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_carousel_images_returns_empty_for_no_slides():
    from backend.agents.content_creator import _generate_carousel_images

    result = await _generate_carousel_images(
        slide_descriptions=[],
        business_name="Brand",
        visual_style="clean",
        color_hint="#fff",
        image_style_directive="minimal",
        style_ref_block="",
        platform="instagram",
        post_id="pid",
        cover_image_bytes=None,
    )
    assert result == []


@pytest.mark.asyncio
async def test_generate_carousel_images_skips_cover_slide_when_provided():
    from backend.agents.content_creator import _generate_carousel_images

    # Only 1 slide + cover provided → start=1 → slides_to_generate=[] → empty
    result = await _generate_carousel_images(
        slide_descriptions=["Cover slide text"],
        business_name="Brand",
        visual_style="clean",
        color_hint="#fff",
        image_style_directive="minimal",
        style_ref_block="",
        platform="instagram",
        post_id="pid",
        cover_image_bytes=b"coverimg",
    )
    assert result == []
