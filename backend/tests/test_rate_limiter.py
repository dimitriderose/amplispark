"""Tests for backend.services.rate_limiter."""

import asyncio
from unittest.mock import patch

import pytest

from backend.services.rate_limiter import (
    _gemini_image_semaphore,
    _veo_semaphore,
    gemini_image_limit,
    veo_limit,
)

GEMINI_SEMAPHORE_CAPACITY = 4
VEO_SEMAPHORE_CAPACITY = 2


class TestGeminiImageLimit:
    async def test_acquires_and_releases_slot(self):
        before = _gemini_image_semaphore._value
        async with gemini_image_limit:
            assert _gemini_image_semaphore._value == before - 1
        assert _gemini_image_semaphore._value == before

    async def test_releases_slot_on_exception_inside_block(self):
        before = _gemini_image_semaphore._value
        with pytest.raises(RuntimeError):
            async with gemini_image_limit:
                raise RuntimeError("boom")
        assert _gemini_image_semaphore._value == before

    async def test_allows_up_to_capacity_concurrent_acquisitions(self):
        acquired = []
        release_events = [asyncio.Event() for _ in range(GEMINI_SEMAPHORE_CAPACITY)]

        async def _hold(event):
            async with gemini_image_limit:
                acquired.append(1)
                await event.wait()

        tasks = [asyncio.create_task(_hold(e)) for e in release_events]
        await asyncio.sleep(0.05)
        assert len(acquired) == GEMINI_SEMAPHORE_CAPACITY
        for e in release_events:
            e.set()
        await asyncio.gather(*tasks)

    async def test_fifth_concurrent_attempt_waits_for_slot(self):
        release_event = asyncio.Event()
        results = []

        async def _hold():
            async with gemini_image_limit:
                await release_event.wait()

        async def _acquire_fifth():
            async with gemini_image_limit:
                results.append("fifth_ran")

        holders = [asyncio.create_task(_hold()) for _ in range(GEMINI_SEMAPHORE_CAPACITY)]
        await asyncio.sleep(0.05)
        fifth = asyncio.create_task(_acquire_fifth())
        await asyncio.sleep(0.05)
        assert not results
        release_event.set()
        await asyncio.gather(*holders, fifth)
        assert results == ["fifth_ran"]


class TestVeoLimit:
    async def test_acquires_and_releases_slot(self):
        before = _veo_semaphore._value
        async with veo_limit:
            assert _veo_semaphore._value == before - 1
        assert _veo_semaphore._value == before

    async def test_releases_slot_on_exception_inside_block(self):
        before = _veo_semaphore._value
        with pytest.raises(ValueError):
            async with veo_limit:
                raise ValueError("veo error")
        assert _veo_semaphore._value == before

    async def test_allows_up_to_capacity_concurrent_acquisitions(self):
        acquired = []
        release_events = [asyncio.Event() for _ in range(VEO_SEMAPHORE_CAPACITY)]

        async def _hold(event):
            async with veo_limit:
                acquired.append(1)
                await event.wait()

        tasks = [asyncio.create_task(_hold(e)) for e in release_events]
        await asyncio.sleep(0.05)
        assert len(acquired) == VEO_SEMAPHORE_CAPACITY
        for e in release_events:
            e.set()
        await asyncio.gather(*tasks)


class TestTimedSemaphoreLogging:
    async def test_logs_when_wait_exceeds_threshold(self):
        return_values = iter([0.0, 0.201])

        def _monotonic():
            return next(return_values)

        with (
            patch("backend.services.rate_limiter.time") as mock_time,
            patch("backend.services.rate_limiter.logger") as mock_logger,
        ):
            mock_time.monotonic.side_effect = _monotonic
            async with gemini_image_limit:
                pass

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args.args
        assert any("gemini_image" in str(a) for a in call_args)

    async def test_does_not_log_when_wait_is_under_threshold(self):
        return_values = iter([0.0, 0.05])

        def _monotonic():
            return next(return_values)

        with (
            patch("backend.services.rate_limiter.time") as mock_time,
            patch("backend.services.rate_limiter.logger") as mock_logger,
        ):
            mock_time.monotonic.side_effect = _monotonic
            async with gemini_image_limit:
                pass

        mock_logger.info.assert_not_called()
