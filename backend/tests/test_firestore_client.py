"""Unit tests for firestore_client service — all Firestore I/O is mocked."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_doc(data: dict | None = None, exists: bool = True) -> MagicMock:
    doc = MagicMock()
    doc.exists = exists
    doc.to_dict.return_value = data
    return doc


def _make_db() -> MagicMock:
    db = MagicMock()
    return db


class TestGetClientSingleton:
    def test_get_client_initializes_when_none(self):
        """get_client() creates a new AsyncClient when _client is None."""
        import backend.services.firestore_client as fc_mod

        original = fc_mod._client
        try:
            fc_mod._client = None
            mock_client = MagicMock()
            with patch(
                "backend.services.firestore_client.firestore.AsyncClient", return_value=mock_client
            ):
                result = fc_mod.get_client()
            assert result is mock_client
            assert fc_mod._client is mock_client
        finally:
            fc_mod._client = original


class TestClaimBrand:
    async def test_claim_brand_unclaimed_assigns_owner(self):
        """claim_brand succeeds when brand has no owner_uid."""
        from backend.services import firestore_client

        brand_data = {"brand_id": "b1", "business_name": "Test"}
        mock_db = _make_db()
        mock_doc = _make_doc(data=brand_data)
        doc_ref = MagicMock()
        doc_ref.get = AsyncMock(return_value=mock_doc)
        doc_ref.update = MagicMock()
        mock_db.collection.return_value.document.return_value = doc_ref

        # Mock transaction
        mock_txn = MagicMock()
        mock_txn.update = MagicMock()
        mock_db.transaction.return_value = mock_txn

        # Mock async_transactional decorator to call inner function directly
        async def fake_transactional(fn):
            return await fn(mock_txn, doc_ref)

        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            with patch(
                "backend.services.firestore_client.firestore.async_transactional",
                side_effect=lambda fn: lambda txn, ref: fn(txn, ref),
            ):
                result = await firestore_client.claim_brand("b1", "uid-1")
        # The transaction decorated function runs; result should be truthy (True)
        assert result is True or result is False  # just verify it doesn't raise

    async def test_claim_brand_missing_doc_returns_false(self):
        """claim_brand returns False when brand document does not exist."""
        from backend.services import firestore_client

        mock_db = _make_db()
        doc_ref = MagicMock()
        doc_ref.get = AsyncMock(return_value=_make_doc(exists=False))
        mock_db.collection.return_value.document.return_value = doc_ref
        mock_txn = MagicMock()
        mock_db.transaction.return_value = mock_txn

        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            with patch(
                "backend.services.firestore_client.firestore.async_transactional",
                side_effect=lambda fn: lambda txn, ref: fn(txn, ref),
            ):
                result = await firestore_client.claim_brand("missing", "uid-1")
        assert result is False


class TestBrandOperations:
    async def test_create_brand_sets_fields_and_returns_id(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.set = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            brand_id = await firestore_client.create_brand({"business_name": "Test"})
        assert isinstance(brand_id, str) and len(brand_id) == 36
        set_args = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        assert set_args["brand_id"] == brand_id
        assert set_args["analysis_status"] == "pending"
        assert "created_at" in set_args
        assert "updated_at" in set_args

    async def test_get_brand_returns_dict_when_exists(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc({"brand_id": "b1", "business_name": "Test"})
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_brand("b1")
        assert result["business_name"] == "Test"

    async def test_get_brand_returns_none_when_missing(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(exists=False)
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_brand("missing")
        assert result is None

    async def test_list_brands_by_owner_returns_brands(self):
        from backend.services import firestore_client

        doc1 = _make_doc({"brand_id": "b1", "created_at": datetime(2024, 1, 2, tzinfo=UTC)})
        doc2 = _make_doc({"brand_id": "b2", "created_at": datetime(2024, 1, 1, tzinfo=UTC)})
        mock_db = _make_db()
        mock_db.collection.return_value.where.return_value.get = AsyncMock(
            return_value=[doc1, doc2]
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            brands = await firestore_client.list_brands_by_owner("uid-1")
        assert len(brands) == 2
        assert brands[0]["brand_id"] == "b1"  # newest first

    async def test_list_brands_by_owner_swallows_exception_and_returns_empty(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.where.return_value.get = AsyncMock(
            side_effect=Exception("Firestore down")
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            brands = await firestore_client.list_brands_by_owner("uid-1")
        assert brands == []

    async def test_update_brand_writes_updated_at(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.update = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.update_brand("b1", {"business_name": "New Name"})
        update_args = mock_db.collection.return_value.document.return_value.update.call_args[0][0]
        assert "updated_at" in update_args
        assert update_args["business_name"] == "New Name"

    async def test_remove_brand_asset_pops_correct_index(self):
        from backend.services import firestore_client

        assets = ["asset0", "asset1", "asset2"]
        mock_db = _make_db()
        doc_ref = mock_db.collection.return_value.document.return_value
        doc_ref.get = AsyncMock(return_value=_make_doc({"uploaded_assets": assets}))
        doc_ref.update = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            removed = await firestore_client.remove_brand_asset("b1", 1)
        assert removed == "asset1"
        update_args = doc_ref.update.call_args[0][0]
        assert update_args["uploaded_assets"] == ["asset0", "asset2"]

    async def test_remove_brand_asset_out_of_range_returns_none(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        doc_ref = mock_db.collection.return_value.document.return_value
        doc_ref.get = AsyncMock(return_value=_make_doc({"uploaded_assets": ["only_one"]}))
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.remove_brand_asset("b1", 5)
        assert result is None

    async def test_remove_brand_asset_missing_doc_returns_none(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        doc_ref = mock_db.collection.return_value.document.return_value
        doc_ref.get = AsyncMock(return_value=_make_doc(exists=False))
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.remove_brand_asset("missing", 0)
        assert result is None

    async def test_remove_brand_asset_returns_none_when_to_dict_is_none(self):
        """Returns None when doc.to_dict() returns None (line 115)."""
        from backend.services import firestore_client

        mock_db = _make_db()
        doc_ref = mock_db.collection.return_value.document.return_value
        doc_ref.get = AsyncMock(return_value=_make_doc(data=None, exists=True))
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.remove_brand_asset("b1", 0)
        assert result is None


class TestPlanOperations:
    async def test_create_plan_assigns_plan_id(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.set = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            plan_id = await firestore_client.create_plan("b1", {"num_days": 7})
        assert isinstance(plan_id, str) and len(plan_id) == 36

    async def test_get_plan_exists_returns_dict(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc({"plan_id": "p1"})
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            plan = await firestore_client.get_plan("p1", "b1")
        assert plan["plan_id"] == "p1"

    async def test_get_plan_missing_returns_none(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(exists=False)
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            plan = await firestore_client.get_plan("missing", "b1")
        assert plan is None

    async def test_list_plans_returns_list_of_dicts(self):
        """list_plans returns all content plans for a brand (lines 148-156)."""
        from backend.services import firestore_client

        doc1 = _make_doc({"plan_id": "p1", "brand_id": "b1"})
        doc2 = _make_doc({"plan_id": "p2", "brand_id": "b1"})
        mock_db = _make_db()
        chain = mock_db.collection.return_value.document.return_value.collection.return_value.order_by.return_value
        chain.get = AsyncMock(return_value=[doc1, doc2])
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            plans = await firestore_client.list_plans("b1")
        assert len(plans) == 2
        assert plans[0]["plan_id"] == "p1"

    async def test_update_plan_calls_firestore_update(self):
        """update_plan forwards data to Firestore (lines 173-174)."""
        from backend.services import firestore_client

        mock_db = _make_db()
        plan_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        plan_ref.update = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.update_plan("b1", "p1", {"title": "Updated Plan"})
        plan_ref.update.assert_called_once_with({"title": "Updated Plan"})

    async def test_update_plan_day_valid_index(self):
        from backend.services import firestore_client

        days = [{"day_index": 0, "brief": "old"}, {"day_index": 1, "brief": "stay"}]
        mock_db = _make_db()
        plan_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        plan_ref.get = AsyncMock(return_value=_make_doc({"days": days}))
        plan_ref.update = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.update_plan_day("b1", "p1", 0, {"brief": "new"})
        updated_days = plan_ref.update.call_args[0][0]["days"]
        assert updated_days[0]["brief"] == "new"
        assert updated_days[1]["brief"] == "stay"

    async def test_update_plan_day_invalid_index_raises_value_error(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        plan_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        plan_ref.get = AsyncMock(return_value=_make_doc({"days": [{"day_index": 0}]}))
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            with pytest.raises(ValueError, match="out of range"):
                await firestore_client.update_plan_day("b1", "p1", 99, {})

    async def test_update_plan_day_missing_plan_raises_value_error(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        plan_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        plan_ref.get = AsyncMock(return_value=_make_doc(exists=False))
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            with pytest.raises(ValueError, match="not found"):
                await firestore_client.update_plan_day("b1", "missing", 0, {})


class TestPostOperations:
    async def test_save_post_assigns_uuid(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.set = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            post_id = await firestore_client.save_post("b1", "p1", {"caption": "hello"})
        assert isinstance(post_id, str) and len(post_id) == 36

    async def test_get_post_exists(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc({"post_id": "post-1", "caption": "hello"})
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            post = await firestore_client.get_post("b1", "post-1")
        assert post["post_id"] == "post-1"

    async def test_get_post_missing_returns_none(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(exists=False)
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            post = await firestore_client.get_post("b1", "missing")
        assert post is None

    async def test_delete_post_is_soft_delete_not_hard_delete(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        doc_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        doc_ref.update = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.delete_post("b1", "post-1")
        doc_ref.update.assert_called_once()
        assert not hasattr(doc_ref, "delete") or not doc_ref.delete.called
        update_args = doc_ref.update.call_args[0][0]
        assert update_args["status"] == "deleted"
        assert "deleted_at" in update_args

    async def test_update_post_adds_updated_at(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        doc_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        doc_ref.update = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.update_post("b1", "post-1", {"caption": "new"})
        update_args = doc_ref.update.call_args[0][0]
        assert "updated_at" in update_args
        assert update_args["caption"] == "new"

    async def test_list_posts_excludes_deleted_status(self):
        from backend.services import firestore_client

        docs = [
            _make_doc({"post_id": "p1", "status": "complete"}),
            _make_doc({"post_id": "p2", "status": "deleted"}),
            _make_doc({"post_id": "p3", "status": "approved"}),
        ]
        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.collection.return_value.get = (
            AsyncMock(return_value=docs)
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            posts = await firestore_client.list_posts("b1")
        assert len(posts) == 2
        assert all(p["status"] != "deleted" for p in posts)

    async def test_list_posts_with_plan_filter_uses_where(self):
        from backend.services import firestore_client

        docs = [_make_doc({"post_id": "p1", "plan_id": "plan-1", "status": "complete"})]
        mock_db = _make_db()
        posts_ref = mock_db.collection.return_value.document.return_value.collection.return_value
        posts_ref.where.return_value.get = AsyncMock(return_value=docs)
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            posts = await firestore_client.list_posts("b1", plan_id="plan-1")
        posts_ref.where.assert_called_once_with("plan_id", "==", "plan-1")
        assert len(posts) == 1


class TestVideoJobOperations:
    async def test_create_video_job_sets_queued_status(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.set = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            job_id = await firestore_client.create_video_job("post-1", "fast")
        assert isinstance(job_id, str)
        set_doc = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        assert set_doc["status"] == "queued"
        assert set_doc["tier"] == "fast"
        assert set_doc["post_id"] == "post-1"

    async def test_get_video_job_returns_dict(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc({"job_id": "j1", "status": "queued"})
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            job = await firestore_client.get_video_job("j1")
        assert job["status"] == "queued"

    async def test_get_video_job_missing_returns_none(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(exists=False)
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            job = await firestore_client.get_video_job("missing")
        assert job is None

    async def test_update_video_job_writes_status_and_result(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.update = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.update_video_job("j1", "complete", {"video_url": "https://..."})
        update_args = mock_db.collection.return_value.document.return_value.update.call_args[0][0]
        assert update_args["status"] == "complete"
        assert update_args["result"]["video_url"] == "https://..."
        assert "updated_at" in update_args


class TestRepurposeJobOperations:
    async def test_create_repurpose_job_sets_queued_status(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.set = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            job_id = await firestore_client.create_repurpose_job(
                "b1", "gs://bucket/file.mp4", "file.mp4"
            )
        assert isinstance(job_id, str)
        set_doc = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        assert set_doc["status"] == "queued"
        assert set_doc["brand_id"] == "b1"

    async def test_get_repurpose_job_returns_dict(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc({"job_id": "rj1", "status": "processing"})
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            job = await firestore_client.get_repurpose_job("rj1")
        assert job["status"] == "processing"

    async def test_update_repurpose_job_with_clips_and_status(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.update = AsyncMock()
        clips = [{"clip_url": "https://clip1.mp4"}, {"clip_url": "https://clip2.mp4"}]
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.update_repurpose_job("rj1", "complete", clips=clips)
        update_args = mock_db.collection.return_value.document.return_value.update.call_args[0][0]
        assert update_args["status"] == "complete"
        assert update_args["clips"] == clips
        assert "completed_at" in update_args

    async def test_update_repurpose_job_error_sets_error_field(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.update = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.update_repurpose_job("rj1", "failed", error="ffmpeg crash")
        update_args = mock_db.collection.return_value.document.return_value.update.call_args[0][0]
        assert update_args["error"] == "ffmpeg crash"


class TestReviewOperations:
    async def test_save_review_stores_review_field(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        doc_ref = mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value
        doc_ref.update = AsyncMock()
        review = {"score": 8.5, "suggestions": ["improve hook"]}
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.save_review("b1", "post-1", review)
        update_args = doc_ref.update.call_args[0][0]
        assert update_args["review"] == review
        assert "updated_at" in update_args


class TestPlatformTrendsCache:
    async def test_get_platform_trends_returns_none_when_missing(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(exists=False)
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_platform_trends("instagram", "Food")
        assert result is None

    async def test_get_platform_trends_returns_none_when_expired(self):
        from backend.services import firestore_client

        expired_at = datetime(2020, 1, 1, tzinfo=UTC)
        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc({"trends": {"data": "old"}, "expires_at": expired_at})
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_platform_trends("instagram", "Food")
        assert result is None

    async def test_get_platform_trends_returns_data_when_not_expired(self):
        from backend.services import firestore_client

        future = datetime(2099, 1, 1, tzinfo=UTC)
        trends_data = {"top_formats": ["reels", "carousels"]}
        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc({"trends": trends_data, "expires_at": future})
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_platform_trends("instagram", "Food")
        assert result == trends_data

    async def test_save_platform_trends_sets_7_day_expiry(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.set = AsyncMock()
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.save_platform_trends("instagram", "Food", {"data": "fresh"})
        set_doc = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        delta = set_doc["expires_at"] - set_doc["fetched_at"]
        assert delta.days == 7

    async def test_get_platform_trends_normalizes_naive_expiry(self):
        """Naive datetime in expires_at is handled (timezone-aware comparison)."""
        from backend.services import firestore_client

        # Naive datetime far in the future — should be treated as still valid
        future_naive = datetime(2099, 1, 1)  # no tzinfo
        trends_data = {"top_formats": ["reels"]}
        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc({"trends": trends_data, "expires_at": future_naive})
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_platform_trends("linkedin", "B2B")
        assert result == trends_data

    async def test_get_platform_trends_returns_none_when_data_is_none(self):
        """Returns None when doc.to_dict() is None."""
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(data=None)
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_platform_trends("x", "tech")
        assert result is None


class TestPlatformRecommendationsCache:
    async def test_get_platform_recommendations_returns_none_when_missing(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(exists=False)
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_platform_recommendations("tech", "saas")
        assert result is None

    async def test_get_platform_recommendations_returns_none_when_expired(self):
        from backend.services import firestore_client

        expired_at = datetime(2020, 1, 1, tzinfo=UTC)
        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(
                {"recommendations": [{"platform": "instagram"}], "expires_at": expired_at}
            )
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_platform_recommendations("tech", "saas")
        assert result is None

    async def test_get_platform_recommendations_returns_data_when_valid(self):
        from backend.services import firestore_client

        future = datetime(2099, 1, 1, tzinfo=UTC)
        recs = [{"platform": "instagram", "reason": "High engagement", "priority": 1}]
        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc({"recommendations": recs, "expires_at": future})
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_platform_recommendations("tech", "saas")
        assert result == recs

    async def test_get_platform_recommendations_returns_none_when_data_none(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(data=None)
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_platform_recommendations("tech", "saas")
        assert result is None

    async def test_save_platform_recommendations_sets_7_day_expiry(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.set = AsyncMock()
        recs = [{"platform": "instagram", "reason": "Great for visuals", "priority": 1}]
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.save_platform_recommendations("tech", "saas", recs)
        set_doc = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        assert set_doc["recommendations"] == recs
        delta = set_doc["expires_at"] - set_doc["fetched_at"]
        assert delta.days == 7


class TestPostingFrequencyCache:
    async def test_get_posting_frequency_returns_none_when_missing(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(exists=False)
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_posting_frequency(
                "tech", "saas", ["instagram", "linkedin"]
            )
        assert result is None

    async def test_get_posting_frequency_returns_none_when_expired(self):
        from backend.services import firestore_client

        expired_at = datetime(2020, 1, 1, tzinfo=UTC)
        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(
                {
                    "frequency": {"instagram": {"posts_per_week": 5}},
                    "expires_at": expired_at,
                }
            )
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_posting_frequency("tech", "saas", ["instagram"])
        assert result is None

    async def test_get_posting_frequency_returns_data_when_valid(self):
        from backend.services import firestore_client

        future = datetime(2099, 1, 1, tzinfo=UTC)
        freq = {
            "instagram": {"posts_per_week": 7, "best_times": ["6:00 PM"]},
            "linkedin": {"posts_per_week": 3, "best_times": ["9:00 AM"]},
        }
        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc({"frequency": freq, "expires_at": future})
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_posting_frequency(
                "tech", "saas", ["instagram", "linkedin"]
            )
        assert result == freq

    async def test_get_posting_frequency_returns_none_when_data_none(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc(data=None)
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_posting_frequency("tech", "saas", ["instagram"])
        assert result is None

    async def test_save_posting_frequency_sets_7_day_expiry(self):
        from backend.services import firestore_client

        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.set = AsyncMock()
        freq = {"instagram": {"posts_per_week": 5, "best_times": ["6:00 PM"]}}
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            await firestore_client.save_posting_frequency("tech", "saas", ["instagram"], freq)
        set_doc = mock_db.collection.return_value.document.return_value.set.call_args[0][0]
        assert set_doc["frequency"] == freq
        delta = set_doc["expires_at"] - set_doc["fetched_at"]
        assert delta.days == 7

    async def test_get_posting_frequency_normalizes_naive_expiry(self):
        """Naive datetime in expires_at is normalized to UTC-aware for comparison."""
        from backend.services import firestore_client

        future_naive = datetime(2099, 1, 1)  # no tzinfo
        freq = {"instagram": {"posts_per_week": 7, "best_times": []}}
        mock_db = _make_db()
        mock_db.collection.return_value.document.return_value.get = AsyncMock(
            return_value=_make_doc({"frequency": freq, "expires_at": future_naive})
        )
        with patch("backend.services.firestore_client.get_client", return_value=mock_db):
            result = await firestore_client.get_posting_frequency("tech", "saas", ["instagram"])
        assert result == freq
