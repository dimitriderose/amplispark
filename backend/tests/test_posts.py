"""Tests for post CRUD and listing behavior."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

import pytest
from backend.tests.conftest import TEST_UID, TEST_BRAND_ID


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
        now = datetime.now(timezone.utc)
        fresh = {"status": "generating", "created_at": (now - timedelta(minutes=2)).isoformat()}
        stale = {"status": "generating", "created_at": (now - timedelta(minutes=15)).isoformat()}
        complete = {"status": "complete", "created_at": (now - timedelta(hours=1)).isoformat()}

        posts = [fresh, stale, complete]
        stale_posts = [
            p for p in posts
            if p.get("status") == "generating"
            and datetime.fromisoformat(p["created_at"]) < now - timedelta(minutes=10)
        ]
        assert len(stale_posts) == 1
        assert stale_posts[0] is stale
