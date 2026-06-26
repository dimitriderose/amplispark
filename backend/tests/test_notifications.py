from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_NOTIF_FC = "backend.routers.notifications.firestore_client"

TEST_UID = "test-user-uid-123"
TEST_BRAND_ID = "test-brand-id-456"
TEST_POST_ID = "test-post-id-789"
TEST_PLAN_ID = "test-plan-id"
TEST_NOTIF_ID = "notif-id-abc123"

SAMPLE_NOTIF = {
    "notification_id": TEST_NOTIF_ID,
    "uid": TEST_UID,
    "type": "complete",
    "title": "Post ready",
    "body": "Your Instagram post is ready to review.",
    "brand_id": TEST_BRAND_ID,
    "post_id": TEST_POST_ID,
    "plan_id": TEST_PLAN_ID,
    "day_index": 2,
    "read": False,
    "created_at": datetime.now(UTC).isoformat(),
}


class TestGetUnreadCount:
    def test_returns_unread_count_for_authenticated_user(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.get_unread_count = AsyncMock(return_value=3)
            response = client.get("/api/notifications/unread-count", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["unread_count"] == 3

    def test_returns_zero_when_no_unread(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.get_unread_count = AsyncMock(return_value=0)
            response = client.get("/api/notifications/unread-count", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["unread_count"] == 0

    def test_returns_401_with_no_token(self, client):
        response = client.get("/api/notifications/unread-count")
        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    def test_unread_count_route_not_matched_as_notification_id(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.get_unread_count = AsyncMock(return_value=0)
            response = client.get("/api/notifications/unread-count", headers=auth_headers)
        assert response.status_code == 200
        assert "unread_count" in response.json()


class TestListNotifications:
    def test_returns_notification_list(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.list_notifications = AsyncMock(return_value=[SAMPLE_NOTIF])
            response = client.get("/api/notifications", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["notification_id"] == TEST_NOTIF_ID

    def test_returns_empty_list_when_no_notifications(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.list_notifications = AsyncMock(return_value=[])
            response = client.get("/api/notifications", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["notifications"] == []
        assert data["unread_count"] == 0

    def test_default_limit_is_10(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.list_notifications = AsyncMock(return_value=[])
            client.get("/api/notifications", headers=auth_headers)
        fc.list_notifications.assert_called_once_with(TEST_UID, limit=10)

    def test_custom_limit_respected(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.list_notifications = AsyncMock(return_value=[])
            client.get("/api/notifications?limit=5", headers=auth_headers)
        fc.list_notifications.assert_called_once_with(TEST_UID, limit=5)

    def test_unread_count_counts_only_unread_items(self, client, auth_headers):
        notifs = [
            {**SAMPLE_NOTIF, "notification_id": "n1", "read": False},
            {**SAMPLE_NOTIF, "notification_id": "n2", "read": True},
            {**SAMPLE_NOTIF, "notification_id": "n3", "read": False},
        ]
        with patch(_NOTIF_FC) as fc:
            fc.list_notifications = AsyncMock(return_value=notifs)
            response = client.get("/api/notifications", headers=auth_headers)
        assert response.json()["unread_count"] == 2

    def test_returns_401_with_no_token(self, client):
        response = client.get("/api/notifications")
        assert response.status_code == 401

    def test_limit_clamped_to_max_50(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.list_notifications = AsyncMock(return_value=[])
            client.get("/api/notifications?limit=999", headers=auth_headers)
        fc.list_notifications.assert_called_once_with(TEST_UID, limit=50)

    def test_negative_limit_clamped_to_1(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.list_notifications = AsyncMock(return_value=[])
            client.get("/api/notifications?limit=-1", headers=auth_headers)
        fc.list_notifications.assert_called_once_with(TEST_UID, limit=1)

    def test_zero_limit_clamped_to_1(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.list_notifications = AsyncMock(return_value=[])
            client.get("/api/notifications?limit=0", headers=auth_headers)
        fc.list_notifications.assert_called_once_with(TEST_UID, limit=1)

    def test_notification_with_missing_optional_fields_parsed_safely(self, client, auth_headers):
        minimal = {
            "notification_id": TEST_NOTIF_ID,
            "uid": TEST_UID,
            "type": "complete",
            "title": "Post ready",
            "body": "Done.",
            "brand_id": TEST_BRAND_ID,
            "post_id": TEST_POST_ID,
            "plan_id": TEST_PLAN_ID,
            "read": False,
        }
        with patch(_NOTIF_FC) as fc:
            fc.list_notifications = AsyncMock(return_value=[minimal])
            response = client.get("/api/notifications", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["notifications"][0]["notification_id"] == TEST_NOTIF_ID

    @pytest.mark.parametrize("notif_type", ["processing", "complete", "failed"])
    def test_all_notification_types_returned(self, client, auth_headers, notif_type):
        notif = {**SAMPLE_NOTIF, "type": notif_type}
        with patch(_NOTIF_FC) as fc:
            fc.list_notifications = AsyncMock(return_value=[notif])
            response = client.get("/api/notifications", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["notifications"][0]["type"] == notif_type


class TestMarkRead:
    def test_marks_single_notification_read(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.mark_notification_read = AsyncMock()
            response = client.patch(
                f"/api/notifications/{TEST_NOTIF_ID}/read", headers=auth_headers
            )
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "notification_id": TEST_NOTIF_ID}

    def test_calls_firestore_with_correct_uid_and_id(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.mark_notification_read = AsyncMock()
            client.patch(f"/api/notifications/{TEST_NOTIF_ID}/read", headers=auth_headers)
        fc.mark_notification_read.assert_called_once_with(TEST_UID, TEST_NOTIF_ID)

    def test_returns_401_with_no_token(self, client):
        response = client.patch(f"/api/notifications/{TEST_NOTIF_ID}/read")
        assert response.status_code == 401

    def test_returns_404_when_notification_not_found(self, client, auth_headers):
        from google.api_core.exceptions import NotFound

        with patch(_NOTIF_FC) as fc:
            fc.mark_notification_read = AsyncMock(side_effect=NotFound("not found"))
            response = client.patch(
                f"/api/notifications/{TEST_NOTIF_ID}/read", headers=auth_headers
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Notification not found"

    def test_returns_500_on_unexpected_firestore_error(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.mark_notification_read = AsyncMock(side_effect=Exception("connection timeout"))
            response = client.patch(
                f"/api/notifications/{TEST_NOTIF_ID}/read", headers=auth_headers
            )
        assert response.status_code == 500


class TestMarkAllRead:
    def test_marks_all_unread_as_read(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.mark_all_notifications_read = AsyncMock(return_value=5)
            response = client.post("/api/notifications/read-all", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "updated": 5}

    def test_returns_zero_when_nothing_to_mark(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.mark_all_notifications_read = AsyncMock(return_value=0)
            response = client.post("/api/notifications/read-all", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["updated"] == 0

    def test_returns_401_with_no_token(self, client):
        response = client.post("/api/notifications/read-all")
        assert response.status_code == 401

    def test_read_all_route_not_matched_as_notification_id_read(self, client, auth_headers):
        with patch(_NOTIF_FC) as fc:
            fc.mark_all_notifications_read = AsyncMock(return_value=0)
            response = client.post("/api/notifications/read-all", headers=auth_headers)
        assert response.status_code == 200
        assert "updated" in response.json()


class TestCreateNotificationFirestore:
    async def test_returns_uuid_string(self):
        mock_doc_ref = AsyncMock()
        mock_coll = MagicMock()
        mock_coll.document.return_value = mock_doc_ref
        mock_user_doc = MagicMock()
        mock_user_doc.collection.return_value = mock_coll
        mock_users_coll = MagicMock()
        mock_users_coll.document.return_value = mock_user_doc
        mock_db = MagicMock()
        mock_db.collection.return_value = mock_users_coll

        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            from backend.services import firestore_client

            result = await firestore_client.create_notification(
                TEST_UID,
                {
                    "type": "complete",
                    "title": "Post ready",
                    "body": "Done.",
                    "brand_id": TEST_BRAND_ID,
                    "post_id": TEST_POST_ID,
                    "plan_id": TEST_PLAN_ID,
                    "day_index": 0,
                },
            )
        assert isinstance(result, str)
        assert len(result) == 36

    async def test_written_doc_includes_read_false_and_created_at(self):
        mock_doc_ref = AsyncMock()
        mock_coll = MagicMock()
        mock_coll.document.return_value = mock_doc_ref
        mock_user_doc = MagicMock()
        mock_user_doc.collection.return_value = mock_coll
        mock_users_coll = MagicMock()
        mock_users_coll.document.return_value = mock_user_doc
        mock_db = MagicMock()
        mock_db.collection.return_value = mock_users_coll

        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            from backend.services import firestore_client

            await firestore_client.create_notification(
                TEST_UID,
                {
                    "type": "complete",
                    "title": "Post ready",
                    "body": "Done.",
                    "brand_id": TEST_BRAND_ID,
                    "post_id": TEST_POST_ID,
                    "plan_id": TEST_PLAN_ID,
                    "day_index": 0,
                },
            )

        mock_doc_ref.set.assert_called_once()
        written = mock_doc_ref.set.call_args[0][0]
        assert written["read"] is False
        assert "created_at" in written
        assert written["uid"] == TEST_UID

    async def test_written_to_correct_collection_path(self):
        mock_doc_ref = AsyncMock()
        mock_notif_coll = MagicMock()
        mock_notif_coll.document.return_value = mock_doc_ref
        mock_user_doc = MagicMock()
        mock_user_doc.collection.return_value = mock_notif_coll
        mock_users_coll = MagicMock()
        mock_users_coll.document.return_value = mock_user_doc
        mock_db = MagicMock()
        mock_db.collection.return_value = mock_users_coll

        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            from backend.services import firestore_client

            await firestore_client.create_notification(
                TEST_UID,
                {
                    "type": "complete",
                    "title": "t",
                    "body": "b",
                    "brand_id": TEST_BRAND_ID,
                    "post_id": TEST_POST_ID,
                    "plan_id": TEST_PLAN_ID,
                    "day_index": 0,
                },
            )

        mock_db.collection.assert_called_with("users")
        mock_users_coll.document.assert_called_with(TEST_UID)
        mock_user_doc.collection.assert_called_with("notifications")


class TestGetUnreadCountFirestore:
    def _make_db(self, docs):
        mock_select_query = MagicMock()
        mock_select_query.get = AsyncMock(return_value=docs)
        mock_count_query = MagicMock()
        mock_count_query.get = AsyncMock(side_effect=Exception("count not supported"))
        mock_filter_query = MagicMock()
        mock_filter_query.count.return_value = mock_count_query
        mock_filter_query.select.return_value = mock_select_query
        mock_coll = MagicMock()
        mock_coll.where.return_value = mock_filter_query
        mock_user_doc = MagicMock()
        mock_user_doc.collection.return_value = mock_coll
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_user_doc
        return mock_db

    async def test_returns_zero_when_no_unread_docs(self):
        mock_db = self._make_db([])
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            from backend.services import firestore_client

            count = await firestore_client.get_unread_count(TEST_UID)
        assert count == 0

    async def test_returns_correct_count(self):
        mock_db = self._make_db([MagicMock(), MagicMock(), MagicMock()])
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            from backend.services import firestore_client

            count = await firestore_client.get_unread_count(TEST_UID)
        assert count == 3


class TestMarkAllNotificationsReadFirestore:
    def _make_db(self, docs):
        mock_select_query = MagicMock()
        mock_select_query.get = AsyncMock(return_value=docs)
        mock_filter_query = MagicMock()
        mock_filter_query.select.return_value = mock_select_query
        mock_coll = MagicMock()
        mock_coll.where.return_value = mock_filter_query
        mock_user_doc = MagicMock()
        mock_user_doc.collection.return_value = mock_coll
        mock_db = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_user_doc
        return mock_db

    async def test_returns_zero_and_skips_batch_when_no_unread(self):
        mock_db = self._make_db([])
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            from backend.services import firestore_client

            result = await firestore_client.mark_all_notifications_read(TEST_UID)
        assert result == 0
        mock_db.batch.assert_not_called()

    async def test_commits_batch_for_each_unread_doc(self):
        mock_docs = [MagicMock(), MagicMock(), MagicMock()]
        for doc in mock_docs:
            doc.reference = MagicMock()
        mock_db = self._make_db(mock_docs)
        mock_batch = AsyncMock()
        mock_db.batch.return_value = mock_batch

        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            from backend.services import firestore_client

            result = await firestore_client.mark_all_notifications_read(TEST_UID)

        assert result == 3
        assert mock_batch.update.call_count == 3
        mock_batch.commit.assert_called_once()


class TestNotificationHookOnComplete:
    async def test_notification_created_when_post_completes(self):
        import asyncio

        from backend.routers.generation import _run_generation_task

        brand = {"owner_uid": TEST_UID, "business_name": "Test"}
        day_brief = {
            "platform": "instagram",
            "_plan_id": TEST_PLAN_ID,
            "day_index": 2,
            "derivative_type": "original",
            "content_theme": "theme",
            "pillar": "education",
        }
        event_queue = asyncio.Queue(maxsize=200)

        complete_event = {
            "event": "complete",
            "data": {
                "caption": "Test caption",
                "hashtags": ["#test"],
                "image_url": "https://example.com/img.png",
                "image_gcs_uri": "gs://bucket/img.png",
            },
        }

        async def mock_generate(*args, **kwargs):
            yield complete_event

        with (
            patch("backend.routers.generation.generate_post", mock_generate),
            patch("backend.routers.generation.firestore_client") as fc,
        ):
            fc.update_post = AsyncMock()
            fc.create_notification = AsyncMock(return_value=TEST_NOTIF_ID)

            await _run_generation_task(
                brand_id=TEST_BRAND_ID,
                post_id=TEST_POST_ID,
                day_brief=day_brief,
                brand=brand,
                event_queue=event_queue,
                custom_photo_bytes=None,
                custom_photo_mime="",
                instructions=None,
                prior_hooks=[],
                image_style=None,
                existing_images=None,
            )

        fc.create_notification.assert_called_once()
        call_kwargs = fc.create_notification.call_args[0]
        assert call_kwargs[0] == TEST_UID
        notif_data = call_kwargs[1]
        assert notif_data["type"] == "complete"
        assert notif_data["brand_id"] == TEST_BRAND_ID
        assert notif_data["post_id"] == TEST_POST_ID
        assert notif_data["plan_id"] == TEST_PLAN_ID
        assert notif_data["day_index"] == 2

    async def test_no_notification_for_unclaimed_brand(self):
        import asyncio

        from backend.routers.generation import _run_generation_task

        brand = {"business_name": "Unclaimed"}
        day_brief = {
            "platform": "instagram",
            "_plan_id": "adhoc",
            "day_index": None,
            "derivative_type": "original",
            "content_theme": "theme",
            "pillar": "education",
        }
        event_queue = asyncio.Queue(maxsize=200)

        async def mock_generate(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {"caption": "cap", "hashtags": [], "image_url": None},
            }

        with (
            patch("backend.routers.generation.generate_post", mock_generate),
            patch("backend.routers.generation.firestore_client") as fc,
        ):
            fc.update_post = AsyncMock()
            fc.create_notification = AsyncMock()

            await _run_generation_task(
                brand_id=TEST_BRAND_ID,
                post_id=TEST_POST_ID,
                day_brief=day_brief,
                brand=brand,
                event_queue=event_queue,
                custom_photo_bytes=None,
                custom_photo_mime="",
                instructions=None,
                prior_hooks=[],
                image_style=None,
                existing_images=None,
            )

        fc.create_notification.assert_not_called()

    async def test_notification_failure_does_not_break_sse(self):
        import asyncio

        from backend.routers.generation import _run_generation_task

        brand = {"owner_uid": TEST_UID}
        day_brief = {
            "platform": "linkedin",
            "_plan_id": TEST_PLAN_ID,
            "day_index": 0,
            "derivative_type": "original",
            "content_theme": "theme",
            "pillar": "education",
        }
        event_queue = asyncio.Queue(maxsize=200)

        async def mock_generate(*args, **kwargs):
            yield {
                "event": "complete",
                "data": {"caption": "cap", "hashtags": [], "image_url": None},
            }

        with (
            patch("backend.routers.generation.generate_post", mock_generate),
            patch("backend.routers.generation.firestore_client") as fc,
        ):
            fc.update_post = AsyncMock()
            fc.create_notification = AsyncMock(side_effect=Exception("Firestore down"))

            await _run_generation_task(
                brand_id=TEST_BRAND_ID,
                post_id=TEST_POST_ID,
                day_brief=day_brief,
                brand=brand,
                event_queue=event_queue,
                custom_photo_bytes=None,
                custom_photo_mime="",
                instructions=None,
                prior_hooks=[],
                image_style=None,
                existing_images=None,
            )

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())
        assert any(e["event"] == "complete" for e in events)


class TestNotificationHookOnError:
    async def test_notification_created_when_post_fails(self):
        import asyncio

        from backend.routers.generation import _run_generation_task

        brand = {"owner_uid": TEST_UID}
        day_brief = {
            "platform": "x",
            "_plan_id": TEST_PLAN_ID,
            "day_index": 1,
            "derivative_type": "original",
            "content_theme": "theme",
            "pillar": "education",
        }
        event_queue = asyncio.Queue(maxsize=200)

        async def mock_generate(*args, **kwargs):
            yield {"event": "error", "data": {"message": "Generation failed"}}

        with (
            patch("backend.routers.generation.generate_post", mock_generate),
            patch("backend.routers.generation.firestore_client") as fc,
        ):
            fc.update_post = AsyncMock()
            fc.create_notification = AsyncMock(return_value=TEST_NOTIF_ID)

            await _run_generation_task(
                brand_id=TEST_BRAND_ID,
                post_id=TEST_POST_ID,
                day_brief=day_brief,
                brand=brand,
                event_queue=event_queue,
                custom_photo_bytes=None,
                custom_photo_mime="",
                instructions=None,
                prior_hooks=[],
                image_style=None,
                existing_images=None,
            )

        fc.create_notification.assert_called_once()
        notif_data = fc.create_notification.call_args[0][1]
        assert notif_data["type"] == "failed"
        assert notif_data["brand_id"] == TEST_BRAND_ID

    async def test_notification_failure_on_error_event_does_not_break_sse(self):
        import asyncio

        from backend.routers.generation import _run_generation_task

        brand = {"owner_uid": TEST_UID}
        day_brief = {
            "platform": "facebook",
            "_plan_id": TEST_PLAN_ID,
            "day_index": 3,
            "derivative_type": "original",
            "content_theme": "theme",
            "pillar": "education",
        }
        event_queue = asyncio.Queue(maxsize=200)

        async def mock_generate(*args, **kwargs):
            yield {"event": "error", "data": {"message": "fail"}}

        with (
            patch("backend.routers.generation.generate_post", mock_generate),
            patch("backend.routers.generation.firestore_client") as fc,
        ):
            fc.update_post = AsyncMock()
            fc.create_notification = AsyncMock(side_effect=Exception("timeout"))

            await _run_generation_task(
                brand_id=TEST_BRAND_ID,
                post_id=TEST_POST_ID,
                day_brief=day_brief,
                brand=brand,
                event_queue=event_queue,
                custom_photo_bytes=None,
                custom_photo_mime="",
                instructions=None,
                prior_hooks=[],
                image_style=None,
                existing_images=None,
            )

        events = []
        while not event_queue.empty():
            events.append(event_queue.get_nowait())
        assert any(e["event"] == "error" for e in events)
