"""Tests for BudgetTracker with Firestore persistence."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.config import IMAGE_COST_PER_UNIT, VIDEO_COST_FAST, VIDEO_COST_STD, TOTAL_BUDGET


class TestBudgetTracker:
    """Tests for BudgetTracker cost calculations and budget limits."""

    def _make_tracker(self):
        from backend.services.budget_tracker import BudgetTracker
        tracker = BudgetTracker()
        tracker._loaded = True  # Skip Firestore load
        return tracker

    @pytest.fixture
    def mock_persist(self):
        with patch("backend.services.budget_tracker.BudgetTracker._persist", new_callable=AsyncMock):
            yield

    @pytest.mark.asyncio
    async def test_record_image_increments_cost(self, mock_persist):
        tracker = self._make_tracker()
        await tracker.record_image(1)
        assert tracker.images_generated == 1
        assert tracker.image_cost == pytest.approx(IMAGE_COST_PER_UNIT)

    @pytest.mark.asyncio
    async def test_record_multiple_images(self, mock_persist):
        tracker = self._make_tracker()
        await tracker.record_image(5)
        assert tracker.images_generated == 5
        assert tracker.image_cost == pytest.approx(IMAGE_COST_PER_UNIT * 5)

    @pytest.mark.asyncio
    async def test_record_video_fast_tier(self, mock_persist):
        tracker = self._make_tracker()
        await tracker.record_video("fast")
        assert tracker.videos_generated == 1
        assert tracker.video_cost == pytest.approx(VIDEO_COST_FAST)

    @pytest.mark.asyncio
    async def test_record_video_standard_tier(self, mock_persist):
        tracker = self._make_tracker()
        await tracker.record_video("standard")
        assert tracker.videos_generated == 1
        assert tracker.video_cost == pytest.approx(VIDEO_COST_STD)

    @pytest.mark.asyncio
    async def test_total_cost_combines_image_and_video(self, mock_persist):
        tracker = self._make_tracker()
        await tracker.record_image(10)
        await tracker.record_video("fast")
        expected = (IMAGE_COST_PER_UNIT * 10) + VIDEO_COST_FAST
        assert tracker.total_cost == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_can_generate_image_under_budget(self, mock_persist):
        tracker = self._make_tracker()
        result = await tracker.can_generate_image()
        assert result is True

    @pytest.mark.asyncio
    async def test_can_generate_image_over_budget(self, mock_persist):
        tracker = self._make_tracker()
        tracker.image_cost = TOTAL_BUDGET * 0.85  # Over 80% threshold
        tracker._loaded = True
        result = await tracker.can_generate_image()
        assert result is False

    @pytest.mark.asyncio
    async def test_can_generate_video_under_budget(self, mock_persist):
        tracker = self._make_tracker()
        result = await tracker.can_generate_video()
        assert result is True

    @pytest.mark.asyncio
    async def test_can_generate_video_over_budget(self, mock_persist):
        tracker = self._make_tracker()
        tracker.image_cost = TOTAL_BUDGET * 0.8  # At threshold
        tracker._loaded = True
        result = await tracker.can_generate_video()
        assert result is False

    def test_get_status_format(self):
        tracker = self._make_tracker()
        tracker.images_generated = 10
        tracker.image_cost = 0.39
        status = tracker.get_status()
        assert status["images_generated"] == 10
        assert status["image_cost"] == "$0.39"
        assert "$" in status["budget_remaining"]


class TestBudgetTrackerFirestorePersistence:
    """Tests for Firestore load/save integration."""

    @pytest.mark.asyncio
    async def test_ensure_loaded_reads_firestore(self):
        from backend.services.budget_tracker import BudgetTracker

        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "images_generated": 50,
            "videos_generated": 3,
            "image_cost": 1.95,
            "video_cost": 3.60,
        }

        mock_db = MagicMock()
        mock_db.document.return_value.get = AsyncMock(return_value=mock_doc)

        tracker = BudgetTracker()
        with patch.object(tracker, "_get_client", return_value=mock_db):
            await tracker._ensure_loaded()

        assert tracker.images_generated == 50
        assert tracker.videos_generated == 3
        assert tracker.image_cost == 1.95
        assert tracker.video_cost == 3.60
        assert tracker._loaded is True

    @pytest.mark.asyncio
    async def test_ensure_loaded_handles_missing_doc(self):
        from backend.services.budget_tracker import BudgetTracker

        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_db = MagicMock()
        mock_db.document.return_value.get = AsyncMock(return_value=mock_doc)

        tracker = BudgetTracker()
        with patch.object(tracker, "_get_client", return_value=mock_db):
            await tracker._ensure_loaded()

        assert tracker.images_generated == 0
        assert tracker._loaded is True
