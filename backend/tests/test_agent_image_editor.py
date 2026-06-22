"""Tests for backend.agents.image_editor."""

from unittest.mock import MagicMock, patch

import pytest


def _make_edit_response(image_bytes: bytes, mime: str = "image/png") -> MagicMock:
    part = MagicMock()
    part.inline_data = MagicMock()
    part.inline_data.data = image_bytes
    part.inline_data.mime_type = mime
    part.text = None
    resp = MagicMock()
    resp.parts = [part]
    return resp


@pytest.fixture
def mock_gcs_storage():
    """Patch google.cloud.storage.Client used inside image_editor."""
    with patch("google.cloud.storage.Client") as MockClient:
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        # Return a minimal 1x1 PNG as the "current image"
        import io

        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (100, 100), color=(128, 64, 32)).save(buf, format="PNG")
        mock_blob.download_as_bytes.return_value = buf.getvalue()
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket
        MockClient.return_value = mock_client
        yield mock_client, mock_bucket, mock_blob


@pytest.mark.asyncio
async def test_edit_image_returns_new_gcs_uri(mock_gcs_storage):
    from backend.agents.image_editor import edit_image

    mock_client, mock_bucket, mock_blob = mock_gcs_storage
    fake_edited = b"PNG" + b"\x00" * 200
    fake_resp = _make_edit_response(fake_edited)

    mock_genai = MagicMock()
    mock_genai.models.generate_content.return_value = fake_resp

    result = await edit_image(
        image_gcs_uri="gs://mybucket/posts/img.png",
        edit_prompt="Make it brighter",
        brand_profile={"tone": "bold", "visual_style": "vibrant"},
        edit_history=[],
        gcs_bucket="mybucket",
        gemini_client=mock_genai,
        aspect_ratio="1:1",
        platform="instagram",
    )
    assert result.startswith("gs://mybucket/posts/edited_")
    assert result.endswith(".png")


@pytest.mark.asyncio
async def test_edit_image_raises_when_no_image_in_response(mock_gcs_storage):
    from backend.agents.image_editor import edit_image

    # Response with no inline_data
    part = MagicMock()
    part.inline_data = None
    part.text = "Sorry, I can't edit that."
    resp = MagicMock()
    resp.parts = [part]

    mock_genai = MagicMock()
    mock_genai.models.generate_content.return_value = resp

    with pytest.raises(ValueError, match="no image data"):
        await edit_image(
            image_gcs_uri="gs://mybucket/posts/img.png",
            edit_prompt="Make it darker",
            brand_profile={},
            edit_history=[],
            gcs_bucket="mybucket",
            gemini_client=mock_genai,
        )


@pytest.mark.asyncio
async def test_edit_image_decodes_base64_string_response(mock_gcs_storage):
    import base64

    from backend.agents.image_editor import edit_image

    fake_bytes = b"PNG" + b"\x00" * 100
    b64_data = base64.b64encode(fake_bytes).decode()

    part = MagicMock()
    part.inline_data = MagicMock()
    part.inline_data.data = b64_data  # string, not bytes
    part.inline_data.mime_type = "image/png"
    resp = MagicMock()
    resp.parts = [part]

    mock_genai = MagicMock()
    mock_genai.models.generate_content.return_value = resp

    result = await edit_image(
        image_gcs_uri="gs://mybucket/posts/img.png",
        edit_prompt="Recolor",
        brand_profile={},
        edit_history=[],
        gcs_bucket="mybucket",
        gemini_client=mock_genai,
    )
    assert result.startswith("gs://mybucket/")


@pytest.mark.asyncio
async def test_edit_image_uses_jpeg_extension_for_jpeg_mime(mock_gcs_storage):
    from backend.agents.image_editor import edit_image

    fake_resp = _make_edit_response(b"JFIF" + b"\x00" * 100, mime="image/jpeg")
    mock_genai = MagicMock()
    mock_genai.models.generate_content.return_value = fake_resp

    result = await edit_image(
        image_gcs_uri="gs://mybucket/posts/img.png",
        edit_prompt="Make it pop",
        brand_profile={},
        edit_history=[],
        gcs_bucket="mybucket",
        gemini_client=mock_genai,
    )
    assert result.endswith(".jpg")
