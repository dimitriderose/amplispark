"""Tests for backend.routers.generation — SSE content-generation endpoint."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.tests.conftest import TEST_BRAND_ID

_GEN_FC = "backend.routers.generation.firestore_client"
_MIDDLEWARE_FC = "backend.middleware.firestore_client"


@pytest.fixture(autouse=True)
def reset_sse_app_status():
    """Reset sse_starlette AppStatus event so each test gets a fresh asyncio.Event
    bound to its own event loop, avoiding 'bound to a different event loop' errors."""
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = asyncio.Event()
    yield
    AppStatus.should_exit_event = asyncio.Event()


class TestStreamGenerate:
    def test_returns_404_when_plan_not_found(self, client, auth_headers, sample_brand):
        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_plan = AsyncMock(return_value=None)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                "/api/generate/nonexistent-plan/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert "Plan not found" in response.json()["detail"]

    def test_returns_404_when_brand_not_found(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=None)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 404
        assert "Brand not found" in response.json()["detail"]

    def test_returns_400_when_day_index_is_negative(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/-1",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 400
        assert "day_index out of range" in response.json()["detail"]

    def test_returns_400_when_day_index_exceeds_plan_length(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        out_of_range_index = len(sample_plan["days"])

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/{out_of_range_index}",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 400
        assert "day_index out of range" in response.json()["detail"]

    def test_returns_sse_content_type_when_generation_succeeds(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "caption",
                "data": {"text": "Test caption", "hashtags": ["#test"], "chunk": False},
            }
            yield {
                "event": "complete",
                "data": {
                    "caption": "Test caption",
                    "hashtags": ["#test"],
                    "image_url": "https://example.com/img.png",
                    "image_gcs_uri": "gs://bucket/img.png",
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_sse_stream_contains_caption_event(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "caption",
                "data": {"text": "Hello world", "hashtags": [], "chunk": False},
            }
            yield {
                "event": "complete",
                "data": {
                    "caption": "Hello world",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "event: caption" in response.text

    def test_sse_stream_contains_complete_event(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Done",
                    "hashtags": [],
                    "image_url": "https://example.com/img.png",
                    "image_gcs_uri": "gs://bucket/img.png",
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "event: complete" in response.text

    def test_optional_instructions_query_param_accepted(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Done",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={
                    "brand_id": TEST_BRAND_ID,
                    "instructions": "Use a playful tone",
                    "image_style": "vivid",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200

    def test_brand_from_cache_is_used_without_extra_firestore_call(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        import time

        import backend.routers.generation as gen_router

        gen_router._brand_cache[TEST_BRAND_ID] = (sample_brand, time.time())

        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Cached",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        fc.get_brand.assert_not_called()

        gen_router._brand_cache.pop(TEST_BRAND_ID, None)

    def test_day_index_zero_is_valid(self, client, auth_headers, sample_brand, sample_plan):
        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Day 0",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200

    def test_last_valid_day_index_is_accepted(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        last_index = len(sample_plan["days"]) - 1

        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Last day",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/{last_index}",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200


class TestStreamGenerateRegenMode:
    """Tests for regen_mode=text_only behavior."""

    def test_regen_mode_text_only_captures_existing_image(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        existing_post = {
            "post_id": "old-post-id",
            "brief_index": 0,
            "platform": "instagram",
            "status": "complete",
            "image_url": "https://example.com/old.png",
            "image_gcs_uri": "gs://bucket/old.png",
            "image_urls": [],
            "image_gcs_uris": [],
            "caption": "Old caption",
        }

        async def _fake_generate_post(*args, **kwargs):
            assert kwargs.get("existing_images") is not None
            yield {
                "event": "complete",
                "data": {
                    "caption": "New caption",
                    "hashtags": [],
                    "image_url": "https://example.com/old.png",
                    "image_gcs_uri": "gs://bucket/old.png",
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[existing_post])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            fc.delete_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID, "regen_mode": "text_only"},
                headers=auth_headers,
            )

        assert response.status_code == 200

    def test_regen_mode_without_text_only_deletes_existing_post(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        existing_post = {
            "post_id": "old-post-id",
            "brief_index": 0,
            "platform": "instagram",
            "status": "complete",
            "caption": "Old",
            "image_url": None,
            "image_gcs_uri": None,
        }

        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "New",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[existing_post])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            fc.delete_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        fc.delete_post.assert_called_once()


class TestStreamGenerateCustomPhoto:
    """Tests for BYOP (Bring Your Own Photo) generation."""

    def test_custom_photo_gcs_uri_is_downloaded(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        plan_with_custom = dict(sample_plan)
        plan_with_custom["days"] = [
            {
                **sample_plan["days"][0],
                "custom_photo_gcs_uri": "gs://bucket/custom.jpg",
                "custom_photo_mime": "image/jpeg",
            }
        ]

        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "BYOP caption",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
            patch(
                "backend.routers.generation.download_gcs_uri",
                new=AsyncMock(return_value=b"\xff\xd8\xff" + b"\x00" * 50),
            ),
        ):
            fc.get_plan = AsyncMock(return_value=plan_with_custom)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200

    def test_custom_photo_download_failure_falls_back_gracefully(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        plan_with_custom = dict(sample_plan)
        plan_with_custom["days"] = [
            {**sample_plan["days"][0], "custom_photo_gcs_uri": "gs://bucket/missing.jpg"}
        ]

        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Fallback caption",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                },
            }

        async def _fail_download(*args, **kwargs):
            raise RuntimeError("GCS download failed")

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
            patch("backend.routers.generation.download_gcs_uri", new=_fail_download),
        ):
            fc.get_plan = AsyncMock(return_value=plan_with_custom)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200


class TestStreamGenerateErrorHandling:
    """Tests for SSE error event propagation."""

    def test_error_event_marks_post_failed(self, client, auth_headers, sample_brand, sample_plan):
        async def _fake_generate_post(*args, **kwargs):
            yield {"event": "error", "data": {"message": "Agent crashed"}}

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "event: error" in response.text


class TestStreamGenerateImageEvent:
    """Tests for image event and carousel URL tracking."""

    def test_image_event_is_forwarded_in_stream(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "image",
                "data": {"url": "https://example.com/img.png", "gcs_uri": "gs://bucket/img.png"},
            }
            yield {
                "event": "complete",
                "data": {
                    "caption": "Done",
                    "hashtags": [],
                    "image_url": "https://example.com/img.png",
                    "image_gcs_uri": "gs://bucket/img.png",
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "event: image" in response.text

    def test_carousel_urls_saved_when_complete_event_has_them(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Carousel post",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                    "image_urls": ["https://ex.com/s1.png", "https://ex.com/s2.png"],
                    "image_gcs_uris": ["gs://b/s1.png", "gs://b/s2.png"],
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        update_call_args = fc.update_post.call_args[0][2]
        assert "image_urls" in update_call_args
        assert "image_gcs_uris" in update_call_args

    def test_review_in_complete_event_is_saved(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Reviewed post",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                    "review": {"approved": True, "score": 9},
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        update_call_args = fc.update_post.call_args[0][2]
        assert update_call_args.get("review") == {"approved": True, "score": 9}


class TestStreamGenerateVideoFirst:
    """Tests for video_first derivative_type path — Veo post-generation."""

    def _plan_with_video_first_day(self, sample_plan):
        plan = dict(sample_plan)
        plan["days"] = [
            {
                **sample_plan["days"][0],
                "derivative_type": "video_first",
                "platform": "instagram",
            }
        ]
        return plan

    def test_video_first_with_low_review_score_emits_video_error_event(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        plan = self._plan_with_video_first_day(sample_plan)

        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Low quality caption",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                    "review": {"approved": False, "score": 5},
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "video_error" in response.text

    def test_video_first_with_no_review_score_emits_video_error_event(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        plan = self._plan_with_video_first_day(sample_plan)

        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Caption without review",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "video_error" in response.text

    def test_video_first_with_high_review_score_emits_video_complete_event(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        plan = self._plan_with_video_first_day(sample_plan)

        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Excellent caption",
                    "hashtags": ["#test"],
                    "image_url": None,
                    "image_gcs_uri": None,
                    "review": {"approved": True, "score": 9},
                },
            }

        video_result = {
            "video_url": "https://example.com/video.mp4",
            "video_gcs_uri": "gs://bucket/video.mp4",
            "model": "veo-3.1",
        }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
            patch(
                "backend.routers.generation.generate_video_clip",
                new=AsyncMock(return_value=video_result),
            ),
        ):
            fc.get_plan = AsyncMock(return_value=plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "video_complete" in response.text

    def test_video_first_veo_failure_emits_video_error_event(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        plan = self._plan_with_video_first_day(sample_plan)

        async def _fake_generate_post(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {
                    "caption": "Good caption",
                    "hashtags": [],
                    "image_url": None,
                    "image_gcs_uri": None,
                    "review": {"approved": True, "score": 8},
                },
            }

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
            patch(
                "backend.routers.generation.generate_video_clip",
                new=AsyncMock(side_effect=RuntimeError("Veo unavailable")),
            ),
        ):
            fc.get_plan = AsyncMock(return_value=plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "video_error" in response.text

    def test_generation_exception_emits_error_event_and_marks_post_failed(
        self, client, auth_headers, sample_brand, sample_plan
    ):
        async def _fake_generate_post(*args, **kwargs):
            raise RuntimeError("Unexpected crash")
            yield  # make it an async generator

        with (
            patch(_GEN_FC) as fc,
            patch(_MIDDLEWARE_FC) as mw_fc,
            patch("backend.routers.generation.generate_post", side_effect=_fake_generate_post),
        ):
            fc.get_plan = AsyncMock(return_value=sample_plan)
            fc.get_brand = AsyncMock(return_value=sample_brand)
            fc.list_posts = AsyncMock(return_value=[])
            fc.save_post = AsyncMock(return_value="new-post-id")
            fc.update_post = AsyncMock()
            mw_fc.get_brand = AsyncMock(return_value=sample_brand)

            response = client.get(
                f"/api/generate/{sample_plan['plan_id']}/0",
                params={"brand_id": TEST_BRAND_ID},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "event: error" in response.text
