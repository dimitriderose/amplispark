"""Global in-process rate limiters for Gemini image and Veo API calls.

Semaphore(4) for Gemini image, Semaphore(2) for Veo — keeps concurrent API
calls below quota limits when multiple users generate carousels simultaneously.

In-process only: keep max_instance_count=1 in terraform/main.tf until the
Cloud Tasks migration ships (issue #18).
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

_gemini_image_semaphore = asyncio.Semaphore(4)
_veo_semaphore = asyncio.Semaphore(2)


class _TimedSemaphore:
    def __init__(self, semaphore: asyncio.Semaphore, name: str, threshold_ms: float = 100) -> None:
        self._sem = semaphore
        self._name = name
        self._threshold_ms = threshold_ms

    async def __aenter__(self):
        start = time.monotonic()
        await self._sem.acquire()
        wait_ms = (time.monotonic() - start) * 1000
        if wait_ms > self._threshold_ms:
            logger.info("rate_limiter: %s waited %.0f ms for slot", self._name, wait_ms)
        return self

    async def __aexit__(self, *_):
        self._sem.release()


gemini_image_limit = _TimedSemaphore(_gemini_image_semaphore, "gemini_image")
veo_limit = _TimedSemaphore(_veo_semaphore, "veo")
