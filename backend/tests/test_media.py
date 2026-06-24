"""Tests for backend.routers.media — storage proxy, video generation, and video repurposing."""

import io
import struct
from unittest.mock import AsyncMock, MagicMock, patch

from backend.tests.conftest import TEST_BRAND_ID, TEST_UID

_MEDIA_FC = "backend.routers.media.firestore_client"
_MIDDLEWARE_FC = "backend.middleware.firestore_client"


def _make_mp4_header() -> bytes:
    """Produce a minimal valid MP4 header (ftyp box) sufficient to pass _is_valid_video_header."""
    box = struct.pack(">I", 20) + b"ftyp" + b"isom" + struct.pack(">I", 0) + b"isom"
    return box + b"\x00" * 100


def _mock_brand(brand_id: str = TEST_BRAND_ID, owner_uid: str = TEST_UID) -> dict:
    return {
        "brand_id": brand_id,
        "owner_uid": owner_uid,
        "business_name": "Test Brand",
        "description": "A test brand",
    }


class TestServeStorageObject:
    def test_returns_blob_content_on_success(self, client, auth_headers, mock_gcs_bucket):
        mock_bucket, mock_blob = mock_gcs_bucket
        mock_blob.content_type = "image/png"
        expected_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_blob.download_as_bytes.return_value = expected_bytes

        with patch("backend.routers.media.get_bucket", return_value=mock_bucket):
            response = client.get("/api/storage/serve/brands/abc/image.png", headers=auth_headers)

        assert response.status_code == 200
        assert response.content == expected_bytes
        assert response.headers["content-type"].startswith("image/png")

    def test_returns_octet_stream_when_content_type_is_none(
        self, client, auth_headers, mock_gcs_bucket
    ):
        mock_bucket, mock_blob = mock_gcs_bucket
        mock_blob.content_type = None
        mock_blob.download_as_bytes.return_value = b"\x00\x01\x02"

        with patch("backend.routers.media.get_bucket", return_value=mock_bucket):
            response = client.get("/api/storage/serve/some/blob/path", headers=auth_headers)

        assert response.status_code == 200
        assert "application/octet-stream" in response.headers["content-type"]

    def test_returns_404_when_blob_download_raises(self, client, auth_headers, mock_gcs_bucket):
        mock_bucket, mock_blob = mock_gcs_bucket
        mock_blob.download_as_bytes.side_effect = Exception("blob not found")

        with patch("backend.routers.media.get_bucket", return_value=mock_bucket):
            response = client.get("/api/storage/serve/missing/blob.png", headers=auth_headers)

        assert response.status_code == 404

    def test_nested_path_segments_are_preserved(self, client, auth_headers, mock_gcs_bucket):
        mock_bucket, mock_blob = mock_gcs_bucket
        mock_blob.content_type = "video/mp4"
        mock_blob.download_as_bytes.return_value = b"\x00"

        with patch("backend.routers.media.get_bucket", return_value=mock_bucket):
            response = client.get(
                "/api/storage/serve/brands/test/videos/clip.mp4", headers=auth_headers
            )

        assert response.status_code == 200
        mock_bucket.blob.assert_called_once_with("brands/test/videos/clip.mp4")


class TestStartVideoGeneration:
    def test_returns_job_id_when_post_exists(self, client, auth_headers, sample_post, sample_brand):
        sample_post["image_gcs_uri"] = None
        mock_task = MagicMock()
        mock_task.add_done_callback = MagicMock()

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.bt.budget_tracker.can_generate_video",
                new=AsyncMock(return_value=True),
            ),
            patch("backend.routers.media.download_gcs_uri", new=AsyncMock(return_value=b"")),
            patch("backend.routers.media.asyncio.create_task", return_value=mock_task),
        ):
            fc.get_post = AsyncMock(return_value=sample_post)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.create_video_job = AsyncMock(return_value="job-id-1")
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                f"/api/posts/{sample_post['post_id']}/generate-video",
                params={"brand_id": TEST_BRAND_ID, "tier": "fast"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "processing"

    def test_returns_404_when_post_not_found(self, client, auth_headers, sample_brand):
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.bt.budget_tracker.can_generate_video",
                new=AsyncMock(return_value=True),
            ),
        ):
            fc.get_post = AsyncMock(return_value=None)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                "/api/posts/nonexistent-post/generate-video",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert "Post not found" in response.json()["detail"]

    def test_returns_404_when_brand_not_found(
        self, client, auth_headers, sample_post, sample_brand
    ):
        sample_post["image_gcs_uri"] = None

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.bt.budget_tracker.can_generate_video",
                new=AsyncMock(return_value=True),
            ),
        ):
            fc.get_post = AsyncMock(return_value=sample_post)
            fc.get_brand = AsyncMock(return_value=None)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                f"/api/posts/{sample_post['post_id']}/generate-video",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert "Brand not found" in response.json()["detail"]

    def test_returns_429_when_budget_exhausted(self, client, auth_headers, sample_brand):
        with (
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.bt.budget_tracker.can_generate_video",
                new=AsyncMock(return_value=False),
            ),
            patch("backend.routers.media.bt.budget_tracker.get_status", return_value={}),
        ):
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                "/api/posts/any-post/generate-video",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 429


class TestGetVideoJobStatus:
    def test_returns_job_when_found(self, client, auth_headers, sample_brand):
        job = {"job_id": "job-id-1", "status": "complete", "video_url": "https://example.com/v.mp4"}

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_video_job = AsyncMock(return_value=job)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get("/api/video-jobs/job-id-1", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["job_id"] == "job-id-1"
        assert response.json()["status"] == "complete"

    def test_returns_queued_status(self, client, auth_headers, sample_brand):
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_video_job = AsyncMock(return_value={"job_id": "job-id-1", "status": "queued"})
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get("/api/video-jobs/job-id-1", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["status"] == "queued"

    def test_returns_404_when_job_not_found(self, client, auth_headers, sample_brand):
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_video_job = AsyncMock(return_value=None)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get("/api/video-jobs/nonexistent-job", headers=auth_headers)

        assert response.status_code == 404
        assert "Video job not found" in response.json()["detail"]


class TestUploadVideoForRepurpose:
    def test_accepts_valid_mp4_and_returns_job_id(self, client, auth_headers, sample_brand):
        mp4_bytes = _make_mp4_header()
        mock_task = MagicMock()
        mock_task.add_done_callback = MagicMock()

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.upload_raw_video_source",
                new=AsyncMock(return_value="gs://bucket/raw/job/video.mp4"),
            ),
            patch("backend.routers.media.asyncio.create_task", return_value=mock_task),
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.create_repurpose_job = AsyncMock(return_value="repurpose-job-id")
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/video-repurpose",
                headers=auth_headers,
                files={"file": ("test.mp4", io.BytesIO(mp4_bytes), "video/mp4")},
            )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_rejects_non_mp4_extension(self, client, auth_headers, sample_brand):
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/video-repurpose",
                headers=auth_headers,
                files={"file": ("clip.avi", io.BytesIO(b"\x00" * 50), "video/avi")},
            )

        assert response.status_code == 400
        detail = response.json()["detail"].lower()
        assert "mp4" in detail or "mov" in detail

    def test_rejects_empty_file(self, client, auth_headers, sample_brand):
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/video-repurpose",
                headers=auth_headers,
                files={"file": ("empty.mp4", io.BytesIO(b""), "video/mp4")},
            )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_rejects_invalid_video_header(self, client, auth_headers, sample_brand):
        not_a_video = b"This is not a video file at all" + b"\x00" * 50

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/video-repurpose",
                headers=auth_headers,
                files={"file": ("fake.mp4", io.BytesIO(not_a_video), "video/mp4")},
            )

        assert response.status_code == 400
        assert "valid" in response.json()["detail"].lower()

    def test_returns_404_when_brand_not_found(self, client, auth_headers, sample_brand):
        mp4_bytes = _make_mp4_header()

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_brand = AsyncMock(return_value=None)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/video-repurpose",
                headers=auth_headers,
                files={"file": ("test.mp4", io.BytesIO(mp4_bytes), "video/mp4")},
            )

        assert response.status_code == 404
        assert "Brand not found" in response.json()["detail"]


class TestGetVideoRepurposeJob:
    def test_returns_job_for_matching_brand(self, client, auth_headers, sample_brand):
        job = {
            "job_id": "repurpose-job-id",
            "brand_id": TEST_BRAND_ID,
            "status": "processing",
            "source_gcs_uri": "gs://bucket/raw.mp4",
        }

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_repurpose_job = AsyncMock(return_value=job)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                "/api/video-repurpose-jobs/repurpose-job-id",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "repurpose-job-id"
        assert "source_gcs_uri" not in data

    def test_returns_403_when_brand_id_mismatches(self, client, auth_headers, sample_brand):
        job = {
            "job_id": "repurpose-job-id",
            "brand_id": "different-brand-id",
            "status": "processing",
        }

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_repurpose_job = AsyncMock(return_value=job)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                "/api/video-repurpose-jobs/repurpose-job-id",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 403

    def test_returns_404_when_job_not_found(self, client, auth_headers, sample_brand):
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_repurpose_job = AsyncMock(return_value=None)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                "/api/video-repurpose-jobs/nonexistent",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert "Repurpose job not found" in response.json()["detail"]

    def test_complete_job_strips_source_gcs_uri(self, client, auth_headers, sample_brand):
        job = {
            "job_id": "repurpose-job-id",
            "brand_id": TEST_BRAND_ID,
            "status": "complete",
            "source_gcs_uri": "gs://bucket/raw.mp4",
            "clips": [],
        }

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_repurpose_job = AsyncMock(return_value=job)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                "/api/video-repurpose-jobs/repurpose-job-id",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "source_gcs_uri" not in response.json()

    def test_complete_job_generates_signed_urls_for_clips(self, client, auth_headers, sample_brand):
        job = {
            "job_id": "repurpose-job-id",
            "brand_id": TEST_BRAND_ID,
            "status": "complete",
            "clips": [
                {
                    "platform": "instagram",
                    "clip_gcs_uri": "gs://bucket/clip1.mp4",
                    "hook": "Great hook",
                },
            ],
        }

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.get_signed_url",
                new=AsyncMock(return_value="https://signed.example.com/clip1.mp4"),
            ),
        ):
            fc.get_repurpose_job = AsyncMock(return_value=job)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                "/api/video-repurpose-jobs/repurpose-job-id",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        clips = response.json()["clips"]
        assert clips[0]["clip_url"] == "https://signed.example.com/clip1.mp4"


class TestEditPostMedia:
    """HTTP tests for POST /api/brands/{brand_id}/posts/{post_id}/edit-media."""

    TEST_POST_ID = "test-post-id-789"

    def _sample_post_with_image(self, sample_brand):
        return {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "platform": "instagram",
            "status": "complete",
            "caption": "Original caption",
            "image_gcs_uri": "gs://bucket/brands/test/img.png",
            "edit_count": 0,
        }

    def test_edit_image_returns_new_signed_url(self, client, auth_headers, sample_brand):
        post = self._sample_post_with_image(sample_brand)
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.agents.image_editor.edit_image",
                new=AsyncMock(return_value="gs://bucket/brands/test/edited.png"),
            ),
            patch(
                "backend.routers.media.get_signed_url",
                new=AsyncMock(return_value="https://signed.example.com/edited.png"),
            ),
            patch("backend.routers.media.get_genai_client", return_value=MagicMock()),
            patch("backend.platforms.get", return_value=MagicMock(image_aspect="1:1")),
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post)
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media",
                json={"edit_prompt": "Make it brighter"},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["image_url"] == "https://signed.example.com/edited.png"
        assert response.json()["edit_count"] == 1

    def test_edit_returns_422_when_edit_limit_reached(self, client, auth_headers, sample_brand):
        post = {**self._sample_post_with_image(sample_brand), "edit_count": 8}
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media",
                json={"edit_prompt": "Make it darker"},
                headers=auth_headers,
            )
        assert response.status_code == 422
        assert "limit" in response.json()["detail"].lower()

    def test_edit_returns_404_when_post_missing(self, client, auth_headers, sample_brand):
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=None)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/nonexistent/edit-media",
                json={"edit_prompt": "Brighten it"},
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_edit_returns_404_when_brand_missing(self, client, auth_headers, sample_brand):
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_brand = AsyncMock(return_value=None)
            fc.get_post = AsyncMock(return_value=None)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media",
                json={"edit_prompt": "Brighten it"},
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_edit_returns_422_when_no_image_uri(self, client, auth_headers, sample_brand):
        post = {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "platform": "instagram",
            "status": "complete",
            "caption": "No image",
            "image_gcs_uri": None,
            "image_gcs_uris": None,
            "video": None,
            "edit_count": 0,
        }
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media",
                json={"edit_prompt": "Brighten it"},
                headers=auth_headers,
            )
        assert response.status_code == 422


class TestResetPostMedia:
    """HTTP tests for POST /api/brands/{brand_id}/posts/{post_id}/edit-media/reset."""

    TEST_POST_ID = "test-post-id-789"

    def test_reset_restores_original_image(self, client, auth_headers, sample_brand):
        post = {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "original_image_gcs_uri": "gs://bucket/brands/test/original.png",
            "image_gcs_uri": "gs://bucket/brands/test/edited.png",
            "edit_count": 3,
            "edit_history": ["brighter", "contrast", "saturation"],
        }
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.get_signed_url",
                new=AsyncMock(return_value="https://signed.example.com/original.png"),
            ),
        ):
            fc.get_post = AsyncMock(return_value=post)
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media/reset",
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["image_url"] == "https://signed.example.com/original.png"
        update_args = fc.update_post.call_args[0][2]
        assert update_args["edit_count"] == 0
        assert update_args["edit_history"] == []

    def test_reset_returns_404_when_post_missing(self, client, auth_headers, sample_brand):
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_post = AsyncMock(return_value=None)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/nonexistent/edit-media/reset",
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_reset_returns_422_when_no_original_image(self, client, auth_headers, sample_brand):
        post = {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "image_gcs_uri": "gs://bucket/brands/test/edited.png",
            "edit_count": 2,
        }
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_post = AsyncMock(return_value=post)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media/reset",
                headers=auth_headers,
            )
        assert response.status_code == 422
        assert "original" in response.json()["detail"].lower()

    def test_reset_thumbnail_restores_original_thumbnail(self, client, auth_headers, sample_brand):
        post = {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "original_thumbnail_gcs_uri": "gs://bucket/brands/test/thumb_orig.png",
            "thumbnail_gcs_uri": "gs://bucket/brands/test/thumb_edit.png",
            "edit_count": 1,
            "edit_history": ["crop"],
        }
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.get_signed_url",
                new=AsyncMock(return_value="https://signed.example.com/thumb_orig.png"),
            ),
        ):
            fc.get_post = AsyncMock(return_value=post)
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media/reset?target=thumbnail",
                headers=auth_headers,
            )
        assert response.status_code == 200
        update_args = fc.update_post.call_args[0][2]
        assert update_args["thumbnail_gcs_uri"] == "gs://bucket/brands/test/thumb_orig.png"

    def test_reset_thumbnail_returns_422_when_no_original_thumbnail(
        self, client, auth_headers, sample_brand
    ):
        post = {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "thumbnail_gcs_uri": "gs://bucket/brands/test/thumb_edit.png",
            "edit_count": 1,
        }
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_post = AsyncMock(return_value=post)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media/reset?target=thumbnail",
                headers=auth_headers,
            )
        assert response.status_code == 422


class TestEditPostMediaThumbnailAndSlide:
    """Tests for thumbnail editing, slide editing, and video post editing paths in edit-media."""

    TEST_POST_ID = "test-post-id-789"

    def test_edit_thumbnail_returns_new_signed_url(self, client, auth_headers, sample_brand):
        post = {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "platform": "instagram",
            "status": "complete",
            "caption": "Caption",
            "thumbnail_gcs_uri": "gs://bucket/brands/test/thumb.png",
            "edit_count": 0,
        }
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.agents.image_editor.edit_image",
                new=AsyncMock(return_value="gs://bucket/brands/test/thumb_edited.png"),
            ),
            patch(
                "backend.routers.media.get_signed_url",
                new=AsyncMock(return_value="https://signed.example.com/thumb_edited.png"),
            ),
            patch("backend.routers.media.get_genai_client", return_value=MagicMock()),
            patch("backend.platforms.get", return_value=MagicMock(image_aspect="1:1")),
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post)
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media",
                json={"edit_prompt": "Make it darker", "target": "thumbnail"},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["image_url"] == "https://signed.example.com/thumb_edited.png"
        update_args = fc.update_post.call_args_list
        written = update_args[-1][0][2]
        assert "thumbnail_gcs_uri" in written

    def test_edit_thumbnail_returns_422_when_no_thumbnail_gcs_uri(
        self, client, auth_headers, sample_brand
    ):
        post = {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "platform": "instagram",
            "status": "complete",
            "caption": "Caption",
            "image_gcs_uri": "gs://bucket/brands/test/img.png",
            "edit_count": 0,
        }
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media",
                json={"edit_prompt": "Crop it", "target": "thumbnail"},
                headers=auth_headers,
            )
        assert response.status_code == 422
        assert "thumbnail" in response.json()["detail"].lower()

    def test_edit_carousel_slide_by_index(self, client, auth_headers, sample_brand):
        post = {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "platform": "instagram",
            "status": "complete",
            "caption": "Carousel",
            "image_gcs_uris": ["gs://bucket/s0.png", "gs://bucket/s1.png"],
            "edit_count": 0,
        }
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.agents.image_editor.edit_image",
                new=AsyncMock(return_value="gs://bucket/s1_edited.png"),
            ),
            patch(
                "backend.routers.media.get_signed_url",
                new=AsyncMock(return_value="https://signed.example.com/s1_edited.png"),
            ),
            patch("backend.routers.media.get_genai_client", return_value=MagicMock()),
            patch("backend.platforms.get", return_value=MagicMock(image_aspect="1:1")),
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post)
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media",
                json={"edit_prompt": "Brighten slide 1", "slide_index": 1},
                headers=auth_headers,
            )
        assert response.status_code == 200
        update_args = fc.update_post.call_args_list[-1][0][2]
        assert "image_gcs_uris" in update_args
        assert update_args["image_gcs_uris"][1] == "gs://bucket/s1_edited.png"

    def test_edit_video_post_regenerates_via_veo(self, client, auth_headers, sample_brand):
        post = {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "platform": "instagram",
            "status": "complete",
            "caption": "Video caption",
            "image_gcs_uri": None,
            "video": {
                "url": "https://example.com/video.mp4",
                "video_gcs_uri": "gs://bucket/video.mp4",
                "tier": "fast",
            },
            "edit_count": 0,
        }
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.generate_video_clip",
                new=AsyncMock(
                    return_value={
                        "video_url": "https://example.com/video_edited.mp4",
                        "video_gcs_uri": "gs://bucket/video_edited.mp4",
                        "model": "veo-3.1",
                    }
                ),
            ),
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post)
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media",
                json={"edit_prompt": "Make it more dramatic"},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert "video_edited" in response.json()["image_url"]

    def test_edit_video_post_raises_500_when_veo_fails(self, client, auth_headers, sample_brand):
        post = {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "platform": "instagram",
            "status": "complete",
            "caption": "Video caption",
            "image_gcs_uri": None,
            "video": {
                "url": "https://example.com/video.mp4",
                "video_gcs_uri": "gs://bucket/video.mp4",
                "tier": "fast",
            },
            "edit_count": 0,
        }
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.generate_video_clip",
                new=AsyncMock(side_effect=RuntimeError("Veo exploded")),
            ),
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post)
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media",
                json={"edit_prompt": "Make it dramatic"},
                headers=auth_headers,
            )
        assert response.status_code == 500

    def test_edit_image_raises_500_when_agent_fails(self, client, auth_headers, sample_brand):
        post = {
            "post_id": self.TEST_POST_ID,
            "brand_id": TEST_BRAND_ID,
            "platform": "instagram",
            "status": "complete",
            "caption": "Caption",
            "image_gcs_uri": "gs://bucket/img.png",
            "edit_count": 0,
        }
        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.agents.image_editor.edit_image",
                new=AsyncMock(side_effect=RuntimeError("Gemini failed")),
            ),
            patch("backend.routers.media.get_genai_client", return_value=MagicMock()),
            patch("backend.platforms.get", return_value=MagicMock(image_aspect="1:1")),
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post)
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{self.TEST_POST_ID}/edit-media",
                json={"edit_prompt": "Make it brighter"},
                headers=auth_headers,
            )
        assert response.status_code == 500


class TestStartVideoGenerationWithHeroImage:
    """Tests for start_video_generation with existing image_gcs_uri."""

    def test_returns_500_when_hero_image_download_fails(
        self, client, auth_headers, sample_post, sample_brand
    ):
        sample_post["image_gcs_uri"] = "gs://bucket/hero.png"

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.bt.budget_tracker.can_generate_video",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "backend.routers.media.download_gcs_uri",
                new=AsyncMock(side_effect=RuntimeError("GCS error")),
            ),
        ):
            fc.get_post = AsyncMock(return_value=sample_post)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                f"/api/posts/{sample_post['post_id']}/generate-video",
                params={"brand_id": TEST_BRAND_ID, "tier": "fast"},
                headers=auth_headers,
            )

        assert response.status_code == 500

    def test_downloads_hero_image_and_queues_job(
        self, client, auth_headers, sample_post, sample_brand
    ):
        sample_post["image_gcs_uri"] = "gs://bucket/hero.png"
        mock_task = MagicMock()
        mock_task.add_done_callback = MagicMock()

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.bt.budget_tracker.can_generate_video",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "backend.routers.media.download_gcs_uri",
                new=AsyncMock(return_value=b"\xff\xd8\xff" + b"\x00" * 50),
            ),
            patch("backend.routers.media.asyncio.create_task", return_value=mock_task),
        ):
            fc.get_post = AsyncMock(return_value=sample_post)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.create_video_job = AsyncMock(return_value="job-id-hero")
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                f"/api/posts/{sample_post['post_id']}/generate-video",
                params={"brand_id": TEST_BRAND_ID, "tier": "fast"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert response.json()["job_id"] == "job-id-hero"


class TestRunVideoGenerationBackgroundTask:
    """Unit tests for _run_video_generation background task."""

    async def test_successful_generation_updates_firestore(self, sample_post, sample_brand):
        import backend.routers.media as media_module
        from backend.routers.media import _run_video_generation
        from backend.tests.conftest import TEST_BRAND_ID

        video_result = {
            "video_url": "https://example.com/video.mp4",
            "video_gcs_uri": "gs://bucket/video.mp4",
            "model": "veo-3.1",
        }

        mock_fc = MagicMock()
        mock_fc.update_video_job = AsyncMock()
        mock_fc.update_post = AsyncMock()

        with (
            patch.object(media_module, "firestore_client", mock_fc),
            patch.object(media_module, "generate_video_clip", AsyncMock(return_value=video_result)),
            patch("backend.routers.media.bt.budget_tracker.record_video", new=AsyncMock()),
        ):
            await _run_video_generation(
                "job-id-1",
                sample_post["post_id"],
                TEST_BRAND_ID,
                None,
                sample_post,
                sample_brand,
                "fast",
            )

        mock_fc.update_video_job.assert_called()
        mock_fc.update_post.assert_called()

    async def test_failed_generation_marks_job_failed(self, sample_post, sample_brand):
        import backend.routers.media as media_module
        from backend.routers.media import _run_video_generation
        from backend.tests.conftest import TEST_BRAND_ID

        mock_fc = MagicMock()
        mock_fc.update_video_job = AsyncMock()
        mock_fc.update_post = AsyncMock()

        with (
            patch.object(media_module, "firestore_client", mock_fc),
            patch.object(
                media_module,
                "generate_video_clip",
                AsyncMock(side_effect=RuntimeError("Veo error")),
            ),
        ):
            await _run_video_generation(
                "job-id-1",
                sample_post["post_id"],
                TEST_BRAND_ID,
                None,
                sample_post,
                sample_brand,
                "fast",
            )

        calls = [str(c) for c in mock_fc.update_video_job.call_args_list]
        assert any("failed" in c for c in calls)


class TestRunVideoRepurposingBackgroundTask:
    """Unit tests for _run_video_repurposing background task."""

    async def test_successful_repurposing_uploads_clips_and_completes(self, sample_brand):
        import backend.routers.media as media_module
        from backend.routers.media import _run_video_repurposing
        from backend.tests.conftest import TEST_BRAND_ID

        clip_result = [
            {
                "platform": "instagram",
                "duration_seconds": 30,
                "start_time": 0,
                "end_time": 30,
                "hook": "Great hook",
                "suggested_caption": "Caption",
                "reason": "Good clip",
                "content_theme": "education",
                "clip_bytes": b"\x00" * 100,
                "filename": "clip_01.mp4",
            }
        ]

        mock_fc = MagicMock()
        mock_fc.update_repurpose_job = AsyncMock()

        with (
            patch.object(media_module, "firestore_client", mock_fc),
            patch(
                "backend.agents.video_repurpose_agent.analyze_and_repurpose",
                new=AsyncMock(return_value=clip_result),
            ),
            patch(
                "backend.services.storage_client.download_gcs_uri",
                new=AsyncMock(return_value=b"\x00" * 1000),
            ),
            patch.object(
                media_module,
                "upload_repurposed_clip",
                AsyncMock(return_value="gs://bucket/clip_01.mp4"),
            ),
        ):
            await _run_video_repurposing(
                "job-repurpose-1", TEST_BRAND_ID, "gs://bucket/source.mp4", sample_brand
            )

        calls = [str(c) for c in mock_fc.update_repurpose_job.call_args_list]
        assert any("complete" in c for c in calls)

    async def test_repurposing_failure_marks_job_failed(self, sample_brand):
        import backend.routers.media as media_module
        from backend.routers.media import _run_video_repurposing
        from backend.tests.conftest import TEST_BRAND_ID

        mock_fc = MagicMock()
        mock_fc.update_repurpose_job = AsyncMock()

        with (
            patch.object(media_module, "firestore_client", mock_fc),
            patch(
                "backend.services.storage_client.download_gcs_uri",
                new=AsyncMock(side_effect=RuntimeError("Download failed")),
            ),
        ):
            await _run_video_repurposing(
                "job-repurpose-1", TEST_BRAND_ID, "gs://bucket/source.mp4", sample_brand
            )

        calls = [str(c) for c in mock_fc.update_repurpose_job.call_args_list]
        assert any("failed" in c for c in calls)

    def test_upload_video_accepts_mov_extension(self, client, auth_headers, sample_brand):
        mp4_bytes = _make_mp4_header()
        mock_task = MagicMock()
        mock_task.add_done_callback = MagicMock()

        with (
            patch(_MEDIA_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch(
                "backend.routers.media.upload_raw_video_source",
                new=AsyncMock(return_value="gs://bucket/raw/job/video.mov"),
            ),
            patch("backend.routers.media.asyncio.create_task", return_value=mock_task),
        ):
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.create_repurpose_job = AsyncMock(return_value="repurpose-job-id")
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/video-repurpose",
                headers=auth_headers,
                files={"file": ("test.mov", io.BytesIO(mp4_bytes), "video/quicktime")},
            )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data


class TestIsValidVideoHeader:
    """Unit tests for _is_valid_video_header helper."""

    def test_valid_ftyp_box_returns_true(self):
        import struct

        from backend.routers.media import _is_valid_video_header

        header = struct.pack(">I", 20) + b"ftyp" + b"isom" + struct.pack(">I", 0) + b"isom"
        assert _is_valid_video_header(header + b"\x00" * 20) is True

    def test_moov_box_returns_true(self):
        from backend.routers.media import _is_valid_video_header

        data = b"\x00\x00\x00\x08" + b"moov" + b"\x00" * 20
        assert _is_valid_video_header(data) is True

    def test_random_bytes_returns_false(self):
        from backend.routers.media import _is_valid_video_header

        assert _is_valid_video_header(b"This is not a video" + b"\x00" * 20) is False

    def test_too_short_returns_false(self):
        from backend.routers.media import _is_valid_video_header

        assert _is_valid_video_header(b"\x00\x01") is False


class TestSanitizeRepurposeError:
    """Unit tests for _sanitize_repurpose_error helper."""

    def test_timeout_error_returns_user_friendly_message(self):
        from backend.routers.media import _sanitize_repurpose_error

        result = _sanitize_repurpose_error(TimeoutError("timed out"))
        assert "Processing timed out" in result

    def test_ffmpeg_runtime_error_returns_friendly_message(self):
        from backend.routers.media import _sanitize_repurpose_error

        result = _sanitize_repurpose_error(RuntimeError("FFmpeg failed to process"))
        assert "Video processing failed" in result

    def test_value_error_returns_message_directly(self):
        from backend.routers.media import _sanitize_repurpose_error

        result = _sanitize_repurpose_error(ValueError("Invalid format"))
        assert result == "Invalid format"

    def test_generic_exception_returns_generic_message(self):
        from backend.routers.media import _sanitize_repurpose_error

        result = _sanitize_repurpose_error(Exception("unexpected"))
        assert "Video processing failed" in result
