"""Tests for backend.services.brand_assets."""

from unittest.mock import AsyncMock, patch

import pytest

# Clear the module-level cache before each test so tests are isolated
import backend.services.brand_assets as _brand_assets_mod


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the in-memory cache between tests."""
    _brand_assets_mod._cache.clear()
    yield
    _brand_assets_mod._cache.clear()


# ---------------------------------------------------------------------------
# _guess_mime — pure function
# ---------------------------------------------------------------------------


def test_guess_mime_png():
    from backend.services.brand_assets import _guess_mime

    assert _guess_mime("gs://bucket/logo.png") == "image/png"


def test_guess_mime_webp():
    from backend.services.brand_assets import _guess_mime

    assert _guess_mime("gs://bucket/logo.WEBP") == "image/webp"


def test_guess_mime_jpeg_default():
    from backend.services.brand_assets import _guess_mime

    assert _guess_mime("gs://bucket/photo.jpg") == "image/jpeg"
    assert _guess_mime("gs://bucket/photo.jpeg") == "image/jpeg"
    assert _guess_mime("gs://bucket/photo.gif") == "image/jpeg"  # unknown → default


def test_guess_mime_uppercase_png():
    from backend.services.brand_assets import _guess_mime

    assert _guess_mime("gs://bucket/LOGO.PNG") == "image/png"


# ---------------------------------------------------------------------------
# _download_safe — async, mocks download_gcs_uri
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_safe_returns_bytes_and_mime():
    from backend.services.brand_assets import _download_safe

    fake_bytes = b"x" * 200  # > 100 bytes sanity check
    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        return_value=fake_bytes,
    ):
        result = await _download_safe("gs://bucket/logo.png")

    assert result is not None
    data, mime = result
    assert data == fake_bytes
    assert mime == "image/png"


@pytest.mark.asyncio
async def test_download_safe_returns_none_for_tiny_file():
    from backend.services.brand_assets import _download_safe

    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        return_value=b"tiny",  # < 100 bytes
    ):
        result = await _download_safe("gs://bucket/logo.png")

    assert result is None


@pytest.mark.asyncio
async def test_download_safe_returns_none_on_exception():
    from backend.services.brand_assets import _download_safe

    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        side_effect=Exception("network error"),
    ):
        result = await _download_safe("gs://bucket/logo.png")

    assert result is None


@pytest.mark.asyncio
async def test_download_safe_returns_none_for_empty_response():
    from backend.services.brand_assets import _download_safe

    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        return_value=b"",
    ):
        result = await _download_safe("gs://bucket/logo.png")

    assert result is None


# ---------------------------------------------------------------------------
# get_brand_reference_images — async, full path tests
# ---------------------------------------------------------------------------


FAKE_IMAGE_BYTES = b"x" * 200


def _mock_download(uri: str) -> bytes:
    """Return fake bytes for any URI."""
    return FAKE_IMAGE_BYTES


@pytest.mark.asyncio
async def test_get_brand_reference_images_with_logo():
    from backend.services.brand_assets import get_brand_reference_images

    profile = {
        "brand_id": "brand-logo-test",
        "logo_url": "gs://bucket/logo.png",
    }

    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        return_value=FAKE_IMAGE_BYTES,
    ):
        result = await get_brand_reference_images(profile)

    assert len(result) == 1
    data, mime = result[0]
    assert data == FAKE_IMAGE_BYTES
    assert mime == "image/png"


@pytest.mark.asyncio
async def test_get_brand_reference_images_max_images_respected():
    from backend.services.brand_assets import get_brand_reference_images

    profile = {
        "brand_id": "brand-max-test",
        "logo_url": "gs://bucket/logo.jpg",
        "product_photos": [
            "gs://bucket/photo1.jpg",
            "gs://bucket/photo2.jpg",
            "gs://bucket/photo3.jpg",
        ],
    }

    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        return_value=FAKE_IMAGE_BYTES,
    ):
        result = await get_brand_reference_images(profile, max_images=2)

    assert len(result) <= 2


@pytest.mark.asyncio
async def test_get_brand_reference_images_uses_cache():
    from backend.services.brand_assets import get_brand_reference_images

    brand_id = "brand-cache-test"
    profile = {"brand_id": brand_id, "logo_url": "gs://bucket/logo.jpg"}

    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        return_value=FAKE_IMAGE_BYTES,
    ) as mock_dl:
        # First call — populates cache
        result1 = await get_brand_reference_images(profile)
        call_count_after_first = mock_dl.call_count

        # Second call — should hit cache, no new download calls
        result2 = await get_brand_reference_images(profile)
        call_count_after_second = mock_dl.call_count

    assert result1 == result2
    # Cache means no additional downloads on second call
    assert call_count_after_second == call_count_after_first


@pytest.mark.asyncio
async def test_get_brand_reference_images_fallback_to_uploaded_assets():
    from backend.services.brand_assets import get_brand_reference_images

    profile = {
        "brand_id": "brand-assets-test",
        # No logo_url
        "uploaded_assets": [
            {"type": "image", "url": "gs://bucket/asset1.jpg"},
            {"type": "document", "url": "gs://bucket/doc.pdf"},  # non-image, should be skipped
        ],
    }

    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        return_value=FAKE_IMAGE_BYTES,
    ):
        result = await get_brand_reference_images(profile)

    # Only the image asset should be downloaded
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_brand_reference_images_includes_style_reference():
    from backend.services.brand_assets import get_brand_reference_images

    profile = {
        "brand_id": "brand-style-test",
        "style_reference_gcs_uri": "gs://bucket/style_ref.jpg",
    }

    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        return_value=FAKE_IMAGE_BYTES,
    ):
        result = await get_brand_reference_images(profile)

    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_brand_reference_images_skips_duplicate_uris():
    from backend.services.brand_assets import get_brand_reference_images

    # Same URI appears as both logo AND in uploaded_assets
    uri = "gs://bucket/logo.png"
    profile = {
        "brand_id": "brand-dedup-test",
        "logo_url": uri,
        "uploaded_assets": [
            {"type": "image", "url": uri},  # duplicate — should be deduplicated
        ],
    }

    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        return_value=FAKE_IMAGE_BYTES,
    ) as mock_dl:
        result = await get_brand_reference_images(profile)

    # URI should only be downloaded once
    assert mock_dl.call_count == 1
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_brand_reference_images_returns_empty_when_all_fail():
    from backend.services.brand_assets import get_brand_reference_images

    profile = {
        "brand_id": "brand-fail-test",
        "logo_url": "gs://bucket/logo.jpg",
        "product_photos": ["gs://bucket/photo.jpg"],
    }

    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        side_effect=Exception("all downloads failed"),
    ):
        result = await get_brand_reference_images(profile)

    assert result == []


@pytest.mark.asyncio
async def test_get_brand_reference_images_empty_profile():
    from backend.services.brand_assets import get_brand_reference_images

    profile = {"brand_id": "brand-empty-test"}

    with patch(
        "backend.services.brand_assets.download_gcs_uri",
        new_callable=AsyncMock,
        return_value=FAKE_IMAGE_BYTES,
    ):
        result = await get_brand_reference_images(profile)

    assert result == []
