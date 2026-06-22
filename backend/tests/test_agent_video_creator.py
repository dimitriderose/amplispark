"""Unit tests for backend/agents/video_creator.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _get_model_and_aspect tests (pure function — no mocking needed)
# ---------------------------------------------------------------------------


def test_get_model_and_aspect_image_always_uses_full_model():
    """Image-to-video path always selects the full Veo model regardless of tier."""
    from backend.agents.video_creator import _get_model_and_aspect

    model, _ = _get_model_and_aspect("instagram", tier="fast", has_image=True)
    assert "fast" not in model


def test_get_model_and_aspect_fast_tier_no_image():
    """Fast tier without image selects the fast Veo model."""
    from backend.agents.video_creator import _get_model_and_aspect

    model, _ = _get_model_and_aspect("instagram", tier="fast", has_image=False)
    assert "fast" in model


def test_get_model_and_aspect_portrait_platform():
    """Portrait video platforms (e.g. tiktok) use 9:16 aspect ratio."""
    from backend.agents.video_creator import _get_model_and_aspect

    _, aspect = _get_model_and_aspect("tiktok", tier="fast", has_image=False)
    assert aspect == "9:16"


# ---------------------------------------------------------------------------
# _build_prompt tests (pure function)
# ---------------------------------------------------------------------------


def test_build_prompt_contains_brand_name():
    """_build_prompt includes the brand name from brand_profile."""
    from backend.agents.video_creator import _build_prompt

    brand = {"business_name": "Acme Corp", "tone": "friendly", "industry": "tech"}
    result = _build_prompt("caption text", brand, "instagram")
    assert "Acme Corp" in result


def test_build_prompt_contains_no_text_rule_when_no_text_overlay():
    """Platforms without text overlays get the strict no-text rule."""
    from backend.agents.video_creator import _build_prompt

    brand = {"business_name": "Brand X"}
    result = _build_prompt("caption", brand, "instagram")
    assert "NO" in result.upper()


def test_build_prompt_with_edit_prompt():
    """Edit prompt is incorporated into the video prompt."""
    from backend.agents.video_creator import _build_prompt

    brand = {"business_name": "Brand X"}
    result = _build_prompt("caption", brand, "instagram", edit_prompt="Make it warmer")
    assert "Make it warmer" in result


# ---------------------------------------------------------------------------
# generate_video_clip integration tests (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_video_clip_returns_metadata():
    """generate_video_clip returns dict with video_url and video_gcs_uri on success."""
    from backend.agents.video_creator import generate_video_clip

    # Build mock operation
    mock_video = MagicMock()
    mock_operation = MagicMock()
    mock_operation.done = True
    mock_operation.response = MagicMock()
    mock_operation.response.generated_videos = [mock_video]

    mock_client = MagicMock()
    mock_client.models.generate_videos = MagicMock(return_value=mock_operation)
    mock_client.files.download = MagicMock(return_value=b"fake-video-bytes")

    with (
        patch("backend.agents.video_creator.get_genai_client", return_value=mock_client),
        patch(
            "backend.agents.video_creator.upload_video_to_gcs",
            new_callable=AsyncMock,
            return_value=("https://example.com/video.mp4", "gs://bucket/video.mp4"),
        ),
    ):
        result = await generate_video_clip(
            hero_image_bytes=None,
            caption="Test caption",
            brand_profile={"business_name": "Test Brand"},
            platform="instagram",
            post_id="post-123",
            tier="fast",
        )

    assert "video_url" in result
    assert "video_gcs_uri" in result
    assert result["video_url"] == "https://example.com/video.mp4"


@pytest.mark.asyncio
async def test_generate_video_clip_no_videos_raises():
    """generate_video_clip raises RuntimeError when Veo returns no generated videos."""
    from backend.agents.video_creator import generate_video_clip

    mock_operation = MagicMock()
    mock_operation.done = True
    mock_operation.response = MagicMock()
    mock_operation.response.generated_videos = []

    mock_client = MagicMock()
    mock_client.models.generate_videos = MagicMock(return_value=mock_operation)

    with patch("backend.agents.video_creator.get_genai_client", return_value=mock_client):
        with pytest.raises(RuntimeError, match="no video"):
            await generate_video_clip(
                hero_image_bytes=None,
                caption="Caption",
                brand_profile={},
                platform="instagram",
                post_id="post-456",
            )


@pytest.mark.asyncio
async def test_generate_video_clip_image_fallback_on_rejection():
    """When Veo rejects image-to-video, it retries text-only generation."""
    from backend.agents.video_creator import generate_video_clip

    call_count = 0

    mock_video = MagicMock()
    mock_operation = MagicMock()
    mock_operation.done = True
    mock_operation.response = MagicMock()
    mock_operation.response.generated_videos = [mock_video]

    def generate_videos_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1 and kwargs.get("image") is not None:
            raise Exception("Veo rejected image input")
        return mock_operation

    mock_client = MagicMock()
    mock_client.models.generate_videos = MagicMock(side_effect=generate_videos_side_effect)
    mock_client.files.download = MagicMock(return_value=b"video-bytes")

    with (
        patch("backend.agents.video_creator.get_genai_client", return_value=mock_client),
        patch(
            "backend.agents.video_creator.upload_video_to_gcs",
            new_callable=AsyncMock,
            return_value=("https://example.com/v.mp4", "gs://b/v.mp4"),
        ),
    ):
        result = await generate_video_clip(
            hero_image_bytes=b"\x89PNG\r\n\x1a\n" + b"\x00" * 10,
            caption="Caption",
            brand_profile={"business_name": "Brand"},
            platform="instagram",
            post_id="post-789",
        )

    assert result["video_url"] == "https://example.com/v.mp4"
