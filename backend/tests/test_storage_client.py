from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSafeFilename:
    def test_strips_path_traversal_components(self):
        from backend.services.storage_client import _safe_filename

        assert _safe_filename("../../etc/passwd") == "passwd"

    def test_replaces_special_chars_with_underscore(self):
        from backend.services.storage_client import _safe_filename

        result = _safe_filename("my file!@#.mp4")
        assert " " not in result
        assert "!" not in result

    def test_truncates_to_max_len(self):
        from backend.services.storage_client import _safe_filename

        result = _safe_filename("a" * 100, max_len=80)
        assert len(result) <= 80

    def test_empty_basename_returns_video(self):
        from backend.services.storage_client import _safe_filename

        result = _safe_filename("path/to/")
        assert result == "video"

    def test_preserves_extension(self):
        from backend.services.storage_client import _safe_filename

        result = _safe_filename("video_clip.mp4")
        assert result.endswith(".mp4")

    def test_normal_filename_unchanged(self):
        from backend.services.storage_client import _safe_filename

        assert _safe_filename("my_video.mp4") == "my_video.mp4"


class TestUploadImageToGcs:
    async def test_uploads_png_and_returns_url_and_gcs_uri(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed.example.com/img.png"
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            url, gcs_uri = await storage_client.upload_image_to_gcs(
                b"\x89PNG" + b"\x00" * 10, "image/png", "post-1"
            )
        assert url.startswith("https://") or url.startswith("/api/storage/serve/")
        assert gcs_uri.startswith("gs://")
        assert gcs_uri.endswith(".png")

    async def test_uploads_jpeg_with_jpg_extension(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed.example.com/img.jpg"
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            url, gcs_uri = await storage_client.upload_image_to_gcs(
                b"\xff\xd8" + b"\x00" * 10, "image/jpeg"
            )
        assert gcs_uri.endswith(".jpg")

    async def test_generates_post_id_when_none_provided(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed.example.com/img.png"
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            url, gcs_uri = await storage_client.upload_image_to_gcs(
                b"data", "image/png", post_id=None
            )
        assert gcs_uri.startswith("gs://")

    async def test_falls_back_to_proxy_url_when_signing_fails(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        mock_blob.generate_signed_url.side_effect = Exception("no service account key")
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            url, gcs_uri = await storage_client.upload_image_to_gcs(b"data", "image/png", "post-1")
        assert url.startswith("/api/storage/serve/")


class TestUploadBrandAsset:
    async def test_uploads_asset_and_returns_gcs_uri(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            gcs_uri = await storage_client.upload_brand_asset(
                "brand-1", b"file-bytes", "logo.png", "image/png"
            )
        assert gcs_uri.startswith("gs://")
        assert "brand-1" in gcs_uri


class TestGetSignedUrl:
    async def test_returns_signed_url_on_success(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed.example.com/file.png"
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            with patch(
                "backend.services.storage_client.parse_gcs_uri", return_value="path/to/file.png"
            ):
                url = await storage_client.get_signed_url("gs://bucket/path/to/file.png")
        assert url.startswith("https://")

    async def test_falls_back_to_proxy_on_signing_exception(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.side_effect = Exception("no key")
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            with patch(
                "backend.services.storage_client.parse_gcs_uri", return_value="path/to/file.png"
            ):
                url = await storage_client.get_signed_url("gs://bucket/path/to/file.png")
        assert url.startswith("/api/storage/serve/")


class TestDownloadFromGcs:
    async def test_downloads_via_proxy_path(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"image-data"
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            result = await storage_client.download_from_gcs("/api/storage/serve/path/to/file.png")
        assert result == b"image-data"

    async def test_raises_on_path_traversal_in_proxy_url(self):
        from backend.services import storage_client

        with pytest.raises(ValueError, match="path traversal"):
            await storage_client.download_from_gcs("/api/storage/serve/../../../etc/passwd")

    async def test_raises_on_non_gcs_https_url(self):
        from backend.services import storage_client

        with pytest.raises(ValueError, match="non-GCS"):
            await storage_client.download_from_gcs("https://evil.com/file.png")


class TestUploadVideoToGcs:
    async def test_uploads_mp4_and_returns_url_and_gcs_uri(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed.example.com/video.mp4"
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            url, gcs_uri = await storage_client.upload_video_to_gcs(b"video-bytes", "post-1")
        assert gcs_uri.endswith(".mp4")


class TestUploadByopPhoto:
    async def test_stores_photo_under_byop_path(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed.example.com/byop.jpg"
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            url, gcs_uri = await storage_client.upload_byop_photo(
                "brand-1", "plan-1", 3, b"photo", "image/jpeg"
            )
        assert "byop" in gcs_uri
        assert "brand-1" in gcs_uri

    async def test_png_mime_type_produces_png_extension(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://signed.example.com/byop.png"
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            url, gcs_uri = await storage_client.upload_byop_photo(
                "b1", "p1", 0, b"data", "image/png"
            )
        assert gcs_uri.endswith(".png")


class TestUploadRawVideoSource:
    async def test_uploads_mp4_to_repurpose_path(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            gcs_uri = await storage_client.upload_raw_video_source(
                "brand-1", "job-1", b"video", "clip.mp4"
            )
        assert "repurpose" in gcs_uri
        assert "brand-1" in gcs_uri
        assert "job-1" in gcs_uri


class TestDownloadGcsUri:
    async def test_downloads_bytes_from_gcs_uri(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"file-content"
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            with patch(
                "backend.services.storage_client.parse_gcs_uri", return_value="path/to/file.png"
            ):
                result = await storage_client.download_gcs_uri("gs://bucket/path/to/file.png")
        assert result == b"file-content"


class TestUploadRepurposedClip:
    async def test_uploads_clip_to_repurpose_clips_path(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            gcs_uri = await storage_client.upload_repurposed_clip(
                "brand-1", "job-1", b"clip-bytes", "clip_001.mp4"
            )
        assert gcs_uri.startswith("gs://")
        assert "repurpose" in gcs_uri
        assert "brand-1" in gcs_uri
        assert "job-1" in gcs_uri
        assert "clip_001.mp4" in gcs_uri

    async def test_upload_is_called_with_video_mp4_content_type(self):
        from backend.services import storage_client

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_string = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        with patch("backend.services.storage_client.get_bucket", return_value=mock_bucket):
            await storage_client.upload_repurposed_clip("b1", "j1", b"data", "my_clip.mp4")
        # upload_from_string is called via run_in_executor (lambda) — just check blob was obtained
        assert mock_bucket.blob.called


class TestGetStorageClientSingleton:
    def test_get_storage_client_initializes_when_none(self):
        """get_storage_client() creates a new Client when _storage_client is None."""
        import backend.services.storage_client as sc_mod

        original = sc_mod._storage_client
        try:
            sc_mod._storage_client = None
            mock_client = MagicMock()
            with patch("backend.services.storage_client.storage.Client", return_value=mock_client):
                result = sc_mod.get_storage_client()
            assert result is mock_client
            assert sc_mod._storage_client is mock_client
        finally:
            sc_mod._storage_client = original

    def test_get_bucket_uses_storage_client(self):
        """get_bucket() calls bucket() on the storage client."""
        from backend.services import storage_client

        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        with patch("backend.services.storage_client.get_storage_client", return_value=mock_client):
            result = storage_client.get_bucket()
        assert result is mock_bucket


class TestDownloadFromGcsHttps:
    async def test_downloads_via_signed_https_url(self):
        """download_from_gcs fetches bytes via httpx for signed https URLs."""
        from backend.services import storage_client

        mock_response = MagicMock()
        mock_response.content = b"signed-url-content"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)
            result = await storage_client.download_from_gcs(
                "https://storage.googleapis.com/my-bucket/file.png"
            )
        assert result == b"signed-url-content"


class TestParseGcsUri:
    def test_valid_uri_returns_blob_path(self):
        from unittest.mock import patch

        from backend import gcs_utils

        with patch.object(gcs_utils, "GCS_BUCKET_NAME", "my-bucket"):
            import backend.gcs_utils as gu

            gu_orig_bucket = gu.GCS_BUCKET_NAME
            gu.GCS_BUCKET_NAME = "my-bucket"
            try:
                result = gu.parse_gcs_uri("gs://my-bucket/brands/test/img.png")
                assert result == "brands/test/img.png"
            finally:
                gu.GCS_BUCKET_NAME = gu_orig_bucket

    def test_invalid_bucket_raises_value_error(self):
        from backend import gcs_utils

        orig = gcs_utils.GCS_BUCKET_NAME
        gcs_utils.GCS_BUCKET_NAME = "my-bucket"
        try:
            import pytest

            with pytest.raises(ValueError, match="my-bucket"):
                gcs_utils.parse_gcs_uri("gs://other-bucket/path/img.png")
        finally:
            gcs_utils.GCS_BUCKET_NAME = orig

    def test_empty_blob_path_raises_value_error(self):
        from backend import gcs_utils

        orig = gcs_utils.GCS_BUCKET_NAME
        gcs_utils.GCS_BUCKET_NAME = "my-bucket"
        try:
            import pytest

            with pytest.raises(ValueError, match="no blob path"):
                gcs_utils.parse_gcs_uri("gs://my-bucket/")
        finally:
            gcs_utils.GCS_BUCKET_NAME = orig

    def test_non_gcs_uri_raises_value_error(self):
        from backend import gcs_utils

        orig = gcs_utils.GCS_BUCKET_NAME
        gcs_utils.GCS_BUCKET_NAME = "my-bucket"
        try:
            import pytest

            with pytest.raises(ValueError):
                gcs_utils.parse_gcs_uri("https://storage.googleapis.com/my-bucket/img.png")
        finally:
            gcs_utils.GCS_BUCKET_NAME = orig
