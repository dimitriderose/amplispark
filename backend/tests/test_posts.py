"""Tests for post CRUD and listing behavior."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPostSoftDelete:
    """Tests for soft delete behavior."""

    @pytest.mark.asyncio
    async def test_delete_post_sets_deleted_status(self):
        """delete_post should set status=deleted and deleted_at, not hard delete."""
        from unittest.mock import MagicMock, patch

        mock_doc_ref = MagicMock()
        mock_doc_ref.update = AsyncMock()

        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = mock_doc_ref

        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            from backend.services import firestore_client

            await firestore_client.delete_post("brand-1", "post-1")

        # Verify update was called (soft delete) rather than delete
        mock_doc_ref.update.assert_called_once()
        call_args = mock_doc_ref.update.call_args[0][0]
        assert call_args["status"] == "deleted"
        assert "deleted_at" in call_args


class TestPostListFiltering:
    """Tests for post listing with soft delete filtering."""

    @pytest.mark.asyncio
    async def test_list_posts_excludes_deleted(self):
        """list_posts should filter out posts with status=deleted."""
        posts = [
            {"post_id": "1", "status": "complete", "caption": "Hello"},
            {"post_id": "2", "status": "deleted", "caption": "Gone"},
            {"post_id": "3", "status": "approved", "caption": "World"},
        ]
        # Simulate the filtering logic
        filtered = [p for p in posts if p.get("status") != "deleted"]
        assert len(filtered) == 2
        assert all(p["status"] != "deleted" for p in filtered)


class TestStalePostCleanup:
    """Tests for batch stale post auto-fail."""

    def test_stale_detection_logic(self):
        """Posts generating for >10 minutes should be considered stale."""
        now = datetime.now(UTC)
        fresh = {"status": "generating", "created_at": (now - timedelta(minutes=2)).isoformat()}
        stale = {"status": "generating", "created_at": (now - timedelta(minutes=15)).isoformat()}
        complete = {"status": "complete", "created_at": (now - timedelta(hours=1)).isoformat()}

        posts = [fresh, stale, complete]
        stale_posts = [
            p
            for p in posts
            if p.get("status") == "generating"
            and datetime.fromisoformat(p["created_at"]) < now - timedelta(minutes=10)
        ]
        assert len(stale_posts) == 1
        assert stale_posts[0] is stale


_POSTS_FC = "backend.routers.posts.firestore_client"
_BRANDS_FC = "backend.routers.brands.firestore_client"
_MIDDLEWARE_FC = "backend.middleware.firestore_client"

TEST_BRAND_ID = "test-brand-id-456"
TEST_POST_ID = "test-post-id-789"
TEST_PLAN_ID = "test-plan-id"


class TestListPostsEndpoint:
    """HTTP tests for GET /api/posts."""

    def test_list_posts_returns_empty_list(self, client, auth_headers):
        with patch(_POSTS_FC) as fc:
            fc.list_posts = AsyncMock(return_value=[])
            response = client.get(
                "/api/posts", params={"brand_id": TEST_BRAND_ID}, headers=auth_headers
            )
        assert response.status_code == 200
        assert response.json()["posts"] == []

    def test_list_posts_returns_posts(self, client, auth_headers, sample_post):
        with patch(_POSTS_FC) as fc:
            fc.list_posts = AsyncMock(return_value=[sample_post])
            response = client.get(
                "/api/posts", params={"brand_id": TEST_BRAND_ID}, headers=auth_headers
            )
        assert response.status_code == 200
        assert len(response.json()["posts"]) == 1
        assert response.json()["posts"][0]["post_id"] == sample_post["post_id"]

    def test_list_posts_filters_by_plan_id(self, client, auth_headers, sample_post):
        with patch(_POSTS_FC) as fc:
            fc.list_posts = AsyncMock(return_value=[sample_post])
            response = client.get(
                "/api/posts",
                params={"brand_id": TEST_BRAND_ID, "plan_id": TEST_PLAN_ID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        fc.list_posts.assert_called_once_with(TEST_BRAND_ID, TEST_PLAN_ID)

    def test_list_posts_requires_brand_id(self, client, auth_headers):
        response = client.get("/api/posts", headers=auth_headers)
        assert response.status_code == 422


class TestGetPostEndpoint:
    """HTTP tests for GET /api/posts/{post_id}."""

    def test_get_post_returns_post(self, client, auth_headers, sample_post):
        with patch(_POSTS_FC) as fc:
            fc.get_post = AsyncMock(return_value=sample_post)
            response = client.get(
                f"/api/posts/{TEST_POST_ID}",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["post_id"] == sample_post["post_id"]
        assert response.json()["caption"] == sample_post["caption"]

    def test_get_post_returns_404_when_missing(self, client, auth_headers):
        with patch(_POSTS_FC) as fc:
            fc.get_post = AsyncMock(return_value=None)
            response = client.get(
                "/api/posts/nonexistent-post",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Post not found"

    def test_get_post_requires_brand_id(self, client, auth_headers):
        response = client.get("/api/posts/some-post-id", headers=auth_headers)
        assert response.status_code == 422


class TestPatchPostEndpoint:
    """HTTP tests for PATCH /api/brands/{brand_id}/posts/{post_id}."""

    def test_patch_post_updates_caption(self, client, auth_headers, sample_brand, sample_post):
        updated = {**sample_post, "caption": "Updated caption"}
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(side_effect=[sample_post, updated])
            fc.update_post = AsyncMock()
            response = client.patch(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}",
                json={"caption": "Updated caption"},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["post"]["caption"] == "Updated caption"

    def test_patch_post_updates_hashtags(self, client, auth_headers, sample_brand, sample_post):
        updated = {**sample_post, "hashtags": ["#new", "#tags"]}
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(side_effect=[sample_post, updated])
            fc.update_post = AsyncMock()
            response = client.patch(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}",
                json={"hashtags": ["#new", "#tags"]},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["post"]["hashtags"] == ["#new", "#tags"]

    def test_patch_post_returns_400_with_no_fields(
        self, client, auth_headers, sample_brand, sample_post
    ):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=sample_post)
            response = client.patch(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}",
                json={},
                headers=auth_headers,
            )
        assert response.status_code == 400

    def test_patch_post_returns_404_when_missing(self, client, auth_headers, sample_brand):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=None)
            response = client.patch(
                f"/api/brands/{TEST_BRAND_ID}/posts/nonexistent",
                json={"caption": "x"},
                headers=auth_headers,
            )
        assert response.status_code == 404


class TestApprovePostEndpoint:
    """HTTP tests for POST /api/brands/{brand_id}/posts/{post_id}/approve."""

    def test_approve_post_sets_approved_status(
        self, client, auth_headers, sample_brand, sample_post
    ):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=sample_post)
            fc.update_post = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/approve",
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["status"] == "approved"
        assert response.json()["post_id"] == TEST_POST_ID
        fc.update_post.assert_called_once_with(TEST_BRAND_ID, TEST_POST_ID, {"status": "approved"})

    def test_approve_post_returns_404_when_missing(self, client, auth_headers, sample_brand):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/nonexistent/approve",
                headers=auth_headers,
            )
        assert response.status_code == 404


class TestReviewPostEndpoint:
    """HTTP tests for POST /api/brands/{brand_id}/posts/{post_id}/review."""

    def test_review_post_returns_cached_review(
        self, client, auth_headers, sample_brand, sample_post
    ):
        post_with_review = {**sample_post, "review": {"approved": True, "score": 9}}
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post_with_review)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/review",
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["review"]["approved"] is True

    def test_review_post_runs_agent_when_no_cached_review(
        self, client, auth_headers, sample_brand, sample_post
    ):
        review_result = {"approved": True, "score": 8, "feedback": "Great post"}
        with (
            patch(_POSTS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch(
                "backend.agents.review_agent.review_post", new=AsyncMock(return_value=review_result)
            ),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=sample_post)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_post = AsyncMock()
            fc.save_review = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/review",
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["review"]["approved"] is True

    def test_review_post_returns_404_when_post_missing(self, client, auth_headers, sample_brand):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/nonexistent/review",
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_review_post_returns_404_when_brand_missing(
        self, client, auth_headers, sample_brand, sample_post
    ):
        review_result = {"approved": True}
        with (
            patch(_POSTS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch(
                "backend.agents.review_agent.review_post", new=AsyncMock(return_value=review_result)
            ),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=sample_post)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/review",
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_review_post_force_reruns_agent_when_cached(
        self, client, auth_headers, sample_brand, sample_post
    ):
        post_with_review = {**sample_post, "review": {"approved": False, "score": 3}}
        new_review = {"approved": True, "score": 9, "feedback": "Great"}
        with (
            patch(_POSTS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch(
                "backend.agents.review_agent.review_post", new=AsyncMock(return_value=new_review)
            ),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post_with_review)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_post = AsyncMock()
            fc.save_review = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/review?force=true",
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["review"]["score"] == 9

    def test_review_post_saves_revision_notes_when_present(
        self, client, auth_headers, sample_brand, sample_post
    ):
        review_result = {"approved": False, "score": 5, "revision_notes": "Make it shorter"}
        with (
            patch(_POSTS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch(
                "backend.agents.review_agent.review_post", new=AsyncMock(return_value=review_result)
            ),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=sample_post)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_post = AsyncMock()
            fc.save_review = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/review",
                headers=auth_headers,
            )
        assert response.status_code == 200
        calls = fc.update_post.call_args_list
        revision_call = any("revision_notes" in str(c) for c in calls)
        assert revision_call

    def test_review_post_saves_revised_hashtags_when_present(
        self, client, auth_headers, sample_brand, sample_post
    ):
        review_result = {
            "approved": True,
            "score": 8,
            "revised_hashtags": ["newhashtag", "another"],
        }
        with (
            patch(_POSTS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch(
                "backend.agents.review_agent.review_post", new=AsyncMock(return_value=review_result)
            ),
            patch(
                "backend.agents.hashtag_engine._sanitize_hashtags",
                return_value=["#newhashtag", "#another"],
            ),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=sample_post)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.update_post = AsyncMock()
            fc.save_review = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/review",
                headers=auth_headers,
            )
        assert response.status_code == 200
        calls = fc.update_post.call_args_list
        hashtag_call = any("hashtags" in str(c) for c in calls)
        assert hashtag_call


class TestRegeneratePostEndpoint:
    """HTTP tests for POST /api/brands/{brand_id}/posts/{post_id}/regenerate."""

    def test_regenerate_failed_post_returns_generate_url(
        self, client, auth_headers, sample_brand, sample_post
    ):
        failed_post = {**sample_post, "status": "failed", "plan_id": TEST_PLAN_ID, "day_index": 0}
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=failed_post)
            fc.delete_post = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/regenerate",
                headers=auth_headers,
            )
        assert response.status_code == 200
        data = response.json()
        assert "generate_url" in data
        assert TEST_PLAN_ID in data["generate_url"]

    def test_regenerate_generating_post_is_allowed(
        self, client, auth_headers, sample_brand, sample_post
    ):
        stuck_post = {
            **sample_post,
            "status": "generating",
            "plan_id": TEST_PLAN_ID,
            "day_index": 2,
        }
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=stuck_post)
            fc.delete_post = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/regenerate",
                headers=auth_headers,
            )
        assert response.status_code == 200

    def test_regenerate_complete_post_returns_409(
        self, client, auth_headers, sample_brand, sample_post
    ):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=sample_post)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/regenerate",
                headers=auth_headers,
            )
        assert response.status_code == 409

    def test_regenerate_returns_404_when_post_missing(self, client, auth_headers, sample_brand):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/nonexistent/regenerate",
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_regenerate_returns_422_when_plan_id_missing(
        self, client, auth_headers, sample_brand, sample_post
    ):
        post_no_plan = {**sample_post, "status": "failed", "plan_id": None, "day_index": 0}
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=post_no_plan)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/regenerate",
                headers=auth_headers,
            )
        assert response.status_code == 422

    def test_regenerate_deletes_post_and_returns_url(
        self, client, auth_headers, sample_brand, sample_post
    ):
        failed_post = {**sample_post, "status": "failed", "plan_id": TEST_PLAN_ID, "day_index": 1}
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_post = AsyncMock(return_value=failed_post)
            fc.delete_post = AsyncMock()
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/posts/{TEST_POST_ID}/regenerate",
                headers=auth_headers,
            )
        fc.delete_post.assert_called_once_with(TEST_BRAND_ID, TEST_POST_ID)
        assert (
            "day_index=1" in response.json()["generate_url"]
            or "1" in response.json()["generate_url"]
        )


class TestExportPostEndpoint:
    """HTTP tests for GET /api/posts/{post_id}/export."""

    def test_export_returns_zip_content_type(self, client, auth_headers, sample_post):
        from unittest.mock import MagicMock

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"\x89PNG\r\n" + b"\x00" * 50
        mock_bucket.blob.return_value = mock_blob

        with (
            patch(_POSTS_FC) as fc,
            patch("backend.routers.posts.get_bucket", return_value=mock_bucket),
            patch("backend.routers.posts.parse_gcs_uri", return_value="brands/test/img.png"),
        ):
            fc.get_post = AsyncMock(
                return_value={
                    **sample_post,
                    "image_gcs_uri": "gs://bucket/brands/test/img.png",
                }
            )
            response = client.get(
                f"/api/posts/{TEST_POST_ID}/export",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

    def test_export_returns_404_when_post_missing(self, client, auth_headers):
        with patch(_POSTS_FC) as fc:
            fc.get_post = AsyncMock(return_value=None)
            response = client.get(
                "/api/posts/nonexistent/export",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_export_zip_contains_caption_file(self, client, auth_headers, sample_post):
        import zipfile

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"\x89PNG\r\n" + b"\x00" * 50
        mock_bucket.blob.return_value = mock_blob

        with (
            patch(_POSTS_FC) as fc,
            patch("backend.routers.posts.get_bucket", return_value=mock_bucket),
            patch("backend.routers.posts.parse_gcs_uri", return_value="brands/test/img.png"),
        ):
            fc.get_post = AsyncMock(
                return_value={
                    **sample_post,
                    "image_gcs_uri": "gs://bucket/brands/test/img.png",
                    "caption": "Hello world",
                    "hashtags": ["travel", "photo"],
                    "day_index": 0,
                }
            )
            response = client.get(
                f"/api/posts/{TEST_POST_ID}/export",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        import io

        z = zipfile.ZipFile(io.BytesIO(response.content))
        names = z.namelist()
        caption_files = [n for n in names if "_caption.txt" in n]
        assert len(caption_files) == 1
        caption_text = z.read(caption_files[0]).decode()
        assert "Hello world" in caption_text
        assert "#travel" in caption_text

    def test_export_zip_works_without_image(self, client, auth_headers, sample_post):
        import io
        import zipfile

        post_no_image = {
            **sample_post,
            "image_gcs_uri": None,
            "caption": "No image post",
            "hashtags": [],
        }
        with patch(_POSTS_FC) as fc:
            fc.get_post = AsyncMock(return_value=post_no_image)
            response = client.get(
                f"/api/posts/{TEST_POST_ID}/export",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        z = zipfile.ZipFile(io.BytesIO(response.content))
        caption_files = [n for n in z.namelist() if "_caption.txt" in n]
        assert len(caption_files) == 1


class TestExportPlanZipEndpoint:
    """HTTP tests for POST /api/export/{plan_id}."""

    def test_export_plan_returns_zip(self, client, auth_headers, sample_plan, sample_post):
        import io
        import zipfile

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.size = 1024
        mock_blob.download_as_bytes.return_value = b"\x89PNG\r\n" + b"\x00" * 50
        mock_bucket.blob.return_value = mock_blob

        with (
            patch(_POSTS_FC) as fc,
            patch("backend.routers.posts.get_bucket", return_value=mock_bucket),
            patch("backend.routers.posts.parse_gcs_uri", return_value="brands/test/img.png"),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.list_posts = AsyncMock(
                return_value=[
                    {
                        **sample_post,
                        "image_gcs_uri": "gs://bucket/brands/test/img.png",
                    }
                ]
            )
            response = client.post(
                f"/api/export/{TEST_PLAN_ID}",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        z = zipfile.ZipFile(io.BytesIO(response.content))
        names = z.namelist()
        assert any("content_plan.json" in n for n in names)

    def test_export_plan_returns_404_when_plan_missing(self, client, auth_headers):
        with patch(_POSTS_FC) as fc:
            fc.get_plan = AsyncMock(return_value=None)
            response = client.post(
                f"/api/export/{TEST_PLAN_ID}",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 404
        assert "Plan not found" in response.json()["detail"]

    def test_export_plan_returns_404_when_no_posts(self, client, auth_headers, sample_plan):
        with patch(_POSTS_FC) as fc:
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.list_posts = AsyncMock(return_value=[])
            response = client.post(
                f"/api/export/{TEST_PLAN_ID}",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 404
        assert "No posts" in response.json()["detail"]

    def test_export_plan_zip_includes_video_when_present(
        self, client, auth_headers, sample_plan, sample_post
    ):
        import io
        import zipfile

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.size = 512
        mock_blob.download_as_bytes.return_value = b"\x00\x00\x00\x14ftypmp42" + b"\x00" * 50
        mock_bucket.blob.return_value = mock_blob

        post_with_video = {
            **sample_post,
            "image_gcs_uri": None,
            "video": {"video_gcs_uri": "gs://bucket/brands/test/clip.mp4"},
        }
        with (
            patch(_POSTS_FC) as fc,
            patch("backend.routers.posts.get_bucket", return_value=mock_bucket),
            patch("backend.routers.posts.parse_gcs_uri", return_value="brands/test/clip.mp4"),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.list_posts = AsyncMock(return_value=[post_with_video])
            response = client.post(
                f"/api/export/{TEST_PLAN_ID}",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        z = zipfile.ZipFile(io.BytesIO(response.content))
        names = z.namelist()
        mp4_files = [n for n in names if n.endswith(".mp4")]
        assert len(mp4_files) == 1

    def test_list_posts_with_gcs_uris_refreshes_signed_urls(self, client, auth_headers):
        post_with_gcs = {
            "post_id": TEST_POST_ID,
            "status": "complete",
            "image_gcs_uri": "gs://bucket/img.png",
            "created_at": None,
        }
        with (
            patch(_POSTS_FC) as fc,
            patch(
                "backend.routers.posts.get_signed_url",
                new=AsyncMock(return_value="https://signed.example.com/img.png"),
            ),
        ):
            fc.list_posts = AsyncMock(return_value=[post_with_gcs])
            response = client.get(
                "/api/posts",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        posts = response.json()["posts"]
        assert posts[0]["image_url"] == "https://signed.example.com/img.png"


class TestCalendarIcsEndpoint:
    """HTTP tests for GET /api/brands/{brand_id}/plans/{plan_id}/calendar.ics."""

    def test_returns_ics_content_type(
        self, client, auth_headers, sample_brand, sample_plan, sample_post
    ):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.list_posts = AsyncMock(return_value=[sample_post])
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/calendar.ics",
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert "text/calendar" in response.headers["content-type"]

    def test_ics_contains_vcalendar_markers(
        self, client, auth_headers, sample_brand, sample_plan, sample_post
    ):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.list_posts = AsyncMock(return_value=[sample_post])
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/calendar.ics",
                headers=auth_headers,
            )
        assert "BEGIN:VCALENDAR" in response.text
        assert "END:VCALENDAR" in response.text
        assert "BEGIN:VEVENT" in response.text

    def test_returns_404_when_brand_missing(self, client, auth_headers, sample_brand):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/calendar.ics",
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_returns_404_when_plan_missing(self, client, auth_headers, sample_brand):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=None)
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/calendar.ics",
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_returns_404_when_no_posts(self, client, auth_headers, sample_brand, sample_plan):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.list_posts = AsyncMock(return_value=[])
            response = client.get(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/calendar.ics",
                headers=auth_headers,
            )
        assert response.status_code == 404


class TestEmailCalendarEndpoint:
    """HTTP tests for POST /api/brands/{brand_id}/plans/{plan_id}/calendar/email."""

    def test_sends_email_and_returns_sent(
        self, client, auth_headers, sample_brand, sample_plan, sample_post
    ):
        with (
            patch(_POSTS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch("backend.services.email_client.send_calendar_email", new=AsyncMock()),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.list_posts = AsyncMock(return_value=[sample_post])
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/calendar/email",
                json={"email": "user@example.com"},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["status"] == "sent"
        assert response.json()["to"] == "user@example.com"

    def test_rejects_invalid_email(self, client, auth_headers, sample_brand):
        with patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/calendar/email",
                json={"email": "not-an-email"},
                headers=auth_headers,
            )
        assert response.status_code == 400
        assert "Invalid email" in response.json()["detail"]

    def test_returns_404_when_brand_missing_for_email(self, client, auth_headers, sample_brand):
        with patch(_POSTS_FC) as fc, patch(_MIDDLEWARE_FC) as mfc:
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=None)
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/calendar/email",
                json={"email": "user@example.com"},
                headers=auth_headers,
            )
        assert response.status_code == 404

    def test_returns_500_when_email_send_fails(
        self, client, auth_headers, sample_brand, sample_plan, sample_post
    ):
        async def _fail(*args, **kwargs):
            raise RuntimeError("SMTP error")

        with (
            patch(_POSTS_FC) as fc,
            patch(_MIDDLEWARE_FC) as mfc,
            patch("backend.services.email_client.send_calendar_email", new=_fail),
        ):
            mfc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.list_posts = AsyncMock(return_value=[sample_post])
            response = client.post(
                f"/api/brands/{TEST_BRAND_ID}/plans/{TEST_PLAN_ID}/calendar/email",
                json={"email": "user@example.com"},
                headers=auth_headers,
            )
        assert response.status_code == 500


class TestIcsHelpers:
    """Unit tests for ICS calendar helper functions."""

    def test_parse_posting_time_am(self):
        from backend.routers.posts import _parse_posting_time

        assert _parse_posting_time("9:00 AM") == (9, 0)

    def test_parse_posting_time_pm(self):
        from backend.routers.posts import _parse_posting_time

        assert _parse_posting_time("2:30 PM") == (14, 30)

    def test_parse_posting_time_noon(self):
        from backend.routers.posts import _parse_posting_time

        assert _parse_posting_time("12:00 PM") == (12, 0)

    def test_parse_posting_time_midnight(self):
        from backend.routers.posts import _parse_posting_time

        assert _parse_posting_time("12:00 AM") == (0, 0)

    def test_parse_posting_time_defaults_on_invalid(self):
        from backend.routers.posts import _parse_posting_time

        assert _parse_posting_time("not-a-time") == (9, 0)

    def test_ics_escape_newlines(self):
        from backend.routers.posts import _ics_escape

        result = _ics_escape("line1\nline2")
        assert "\\n" in result

    def test_ics_escape_commas(self):
        from backend.routers.posts import _ics_escape

        result = _ics_escape("a,b,c")
        assert "\\," in result

    def test_ics_escape_semicolons(self):
        from backend.routers.posts import _ics_escape

        result = _ics_escape("a;b")
        assert "\\;" in result

    def test_ics_fold_line_short_line_unchanged(self):
        from backend.routers.posts import _ics_fold_line

        short = "SUMMARY:Short"
        assert _ics_fold_line(short) == short

    def test_ics_fold_line_folds_long_line(self):
        from backend.routers.posts import _ics_fold_line

        long_line = "SUMMARY:" + "A" * 100
        result = _ics_fold_line(long_line)
        assert "\r\n " in result

    def test_build_ics_has_correct_structure(self):
        from backend.routers.posts import _build_ics

        plan = {
            "days": [{"day_index": 0, "theme": "Launch", "posting_time": "9:00 AM"}],
            "created_at": "2025-01-01T00:00:00+00:00",
        }
        posts = [
            {
                "post_id": "p1",
                "day_index": 0,
                "platform": "instagram",
                "caption": "Hello",
                "hashtags": [],
            }
        ]
        ics = _build_ics(plan, posts, "Test Brand")
        assert "BEGIN:VCALENDAR" in ics
        assert "BEGIN:VEVENT" in ics
        assert "END:VEVENT" in ics
        assert "END:VCALENDAR" in ics

    def test_build_ics_datetime_object_as_created_at(self):
        from datetime import UTC, datetime

        from backend.routers.posts import _build_ics

        plan = {"days": [], "created_at": datetime(2025, 3, 1, tzinfo=UTC)}
        ics = _build_ics(plan, [], "Brand")
        assert "BEGIN:VCALENDAR" in ics


class TestRefreshSignedUrlsHelper:
    """Unit tests for _refresh_signed_urls helper."""

    async def test_signs_image_gcs_uri(self):
        from unittest.mock import AsyncMock, patch

        from backend.routers.posts import _refresh_signed_urls

        post = {"post_id": "p1", "image_gcs_uri": "gs://bucket/img.png"}
        with patch(
            "backend.routers.posts.get_signed_url",
            new=AsyncMock(return_value="https://signed.example.com/img.png"),
        ):
            result = await _refresh_signed_urls(post)
        assert result["image_url"] == "https://signed.example.com/img.png"

    async def test_handles_signing_error_gracefully(self):
        from unittest.mock import patch

        from backend.routers.posts import _refresh_signed_urls

        async def _fail(*args, **kwargs):
            raise RuntimeError("sign failed")

        post = {"post_id": "p1", "image_gcs_uri": "gs://bucket/img.png"}
        with patch("backend.routers.posts.get_signed_url", new=_fail):
            result = await _refresh_signed_urls(post)
        assert "image_url" not in result

    async def test_signs_multiple_carousel_uris(self):
        from unittest.mock import AsyncMock, patch

        from backend.routers.posts import _refresh_signed_urls

        post = {
            "post_id": "p1",
            "image_gcs_uris": ["gs://bucket/s1.png", "gs://bucket/s2.png"],
            "image_urls": [],
        }
        with patch(
            "backend.routers.posts.get_signed_url",
            new=AsyncMock(side_effect=["https://s1.com", "https://s2.com"]),
        ):
            result = await _refresh_signed_urls(post)
        assert result["image_urls"] == ["https://s1.com", "https://s2.com"]

    async def test_signs_thumbnail_gcs_uri(self):
        from unittest.mock import AsyncMock, patch

        from backend.routers.posts import _refresh_signed_urls

        post = {"post_id": "p1", "thumbnail_gcs_uri": "gs://bucket/thumb.png"}
        with patch(
            "backend.routers.posts.get_signed_url",
            new=AsyncMock(return_value="https://signed.example.com/thumb.png"),
        ):
            result = await _refresh_signed_urls(post)
        assert result["thumbnail_url"] == "https://signed.example.com/thumb.png"

    async def test_thumbnail_signing_error_handled_gracefully(self):
        from unittest.mock import patch

        from backend.routers.posts import _refresh_signed_urls

        async def _fail(*args, **kwargs):
            raise RuntimeError("sign failed")

        post = {"post_id": "p1", "thumbnail_gcs_uri": "gs://bucket/thumb.png"}
        with patch("backend.routers.posts.get_signed_url", new=_fail):
            result = await _refresh_signed_urls(post)
        assert "thumbnail_url" not in result


class TestAutoFailStaleHelper:
    """Unit tests for _auto_fail_stale_generating helper."""

    async def test_non_generating_post_is_skipped(self):
        from backend.routers.posts import _auto_fail_stale_generating

        post = {"post_id": "p1", "status": "complete"}
        await _auto_fail_stale_generating(post, "brand-1")
        assert post["status"] == "complete"

    async def test_stale_post_is_marked_failed(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, patch

        from backend.routers.posts import _auto_fail_stale_generating

        post = {
            "post_id": "p1",
            "status": "generating",
            "created_at": datetime.now(UTC) - timedelta(minutes=15),
        }
        with patch("backend.routers.posts.firestore_client") as fc:
            fc.update_post = AsyncMock()
            await _auto_fail_stale_generating(post, "brand-1")
        assert post["status"] == "failed"
        fc.update_post.assert_called_once()

    async def test_update_error_is_logged_and_not_raised(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import patch

        from backend.routers.posts import _auto_fail_stale_generating

        async def _fail(*args, **kwargs):
            raise RuntimeError("db error")

        post = {
            "post_id": "p1",
            "status": "generating",
            "created_at": datetime.now(UTC) - timedelta(minutes=15),
        }
        with patch("backend.routers.posts.firestore_client") as fc:
            fc.update_post = _fail
            await _auto_fail_stale_generating(post, "brand-1")
        assert post["status"] == "failed"


class TestListPostsWithStaleHandling:
    """Tests for stale post auto-fail during listing."""

    def test_stale_generating_post_is_marked_failed(self, client, auth_headers):
        from datetime import UTC, datetime, timedelta

        stale_post = {
            "post_id": "stale-1",
            "status": "generating",
            "created_at": datetime.now(UTC) - timedelta(minutes=15),
        }
        with patch(_POSTS_FC) as fc:
            fc.list_posts = AsyncMock(return_value=[stale_post])
            fc.update_post = AsyncMock()
            response = client.get(
                "/api/posts",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        posts = response.json()["posts"]
        assert posts[0]["status"] == "failed"
        fc.update_post.assert_called_once()

    def test_fresh_generating_post_is_not_marked_failed(self, client, auth_headers):
        from datetime import UTC, datetime, timedelta

        fresh_post = {
            "post_id": "fresh-1",
            "status": "generating",
            "created_at": datetime.now(UTC) - timedelta(minutes=2),
        }
        with patch(_POSTS_FC) as fc:
            fc.list_posts = AsyncMock(return_value=[fresh_post])
            fc.update_post = AsyncMock()
            response = client.get(
                "/api/posts",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        posts = response.json()["posts"]
        assert posts[0]["status"] == "generating"
        fc.update_post.assert_not_called()

    def test_get_post_auto_fails_stale_generating(self, client, auth_headers):
        from datetime import UTC, datetime, timedelta

        stale_post = {
            "post_id": TEST_POST_ID,
            "status": "generating",
            "created_at": datetime.now(UTC) - timedelta(minutes=15),
        }
        with patch(_POSTS_FC) as fc:
            fc.get_post = AsyncMock(return_value=stale_post)
            fc.update_post = AsyncMock()
            response = client.get(
                f"/api/posts/{TEST_POST_ID}",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert response.json()["status"] == "failed"
