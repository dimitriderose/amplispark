import logging

from backend.config import (
    IMAGE_COST_PER_UNIT, VIDEO_COST_FAST, VIDEO_COST_STD,
    TOTAL_BUDGET, IMAGE_BUDGET
)

logger = logging.getLogger(__name__)

_DOC_PATH = "_system/budget"


class BudgetTracker:
    """Track image and video generation costs against $100 credit.

    State is persisted to Firestore at ``_system/budget`` so it survives
    restarts and is shared across replicas.
    """

    def __init__(self):
        self._loaded = False
        self.images_generated = 0
        self.videos_generated = 0
        self.image_cost = 0.0
        self.video_cost = 0.0

    def _get_client(self):
        from backend.services.firestore_client import get_client
        return get_client()

    async def _ensure_loaded(self):
        if self._loaded:
            return
        db = self._get_client()
        doc = await db.document(_DOC_PATH).get()
        if doc.exists:
            data = doc.to_dict()
            self.images_generated = data.get("images_generated", 0)
            self.videos_generated = data.get("videos_generated", 0)
            self.image_cost = data.get("image_cost", 0.0)
            self.video_cost = data.get("video_cost", 0.0)
        self._loaded = True

    async def _persist(self):
        db = self._get_client()
        await db.document(_DOC_PATH).set({
            "images_generated": self.images_generated,
            "videos_generated": self.videos_generated,
            "image_cost": self.image_cost,
            "video_cost": self.video_cost,
        })

    @property
    def total_cost(self) -> float:
        return self.image_cost + self.video_cost

    async def can_generate_image(self) -> bool:
        await self._ensure_loaded()
        return self.total_cost < (TOTAL_BUDGET * 0.8)

    async def can_generate_video(self) -> bool:
        await self._ensure_loaded()
        return self.total_cost + VIDEO_COST_FAST < (TOTAL_BUDGET * 0.8)

    async def record_image(self, num_images: int = 1):
        await self._ensure_loaded()
        self.images_generated += num_images
        self.image_cost = self.images_generated * IMAGE_COST_PER_UNIT
        await self._persist()
        logger.info("metric", extra={
            "metric_name": "image_generated",
            "images_generated": self.images_generated,
            "image_cost": self.image_cost,
            "total_cost": self.total_cost,
            "budget_remaining": TOTAL_BUDGET - self.total_cost,
        })

    async def record_video(self, tier: str = "fast"):
        await self._ensure_loaded()
        self.videos_generated += 1
        cost = VIDEO_COST_FAST if tier == "fast" else VIDEO_COST_STD
        self.video_cost += cost
        await self._persist()
        logger.info("metric", extra={
            "metric_name": "video_generated",
            "videos_generated": self.videos_generated,
            "video_cost": self.video_cost,
            "total_cost": self.total_cost,
            "budget_remaining": TOTAL_BUDGET - self.total_cost,
        })

    def get_status(self) -> dict:
        return {
            "images_generated": self.images_generated,
            "videos_generated": self.videos_generated,
            "image_cost": f"${self.image_cost:.2f}",
            "video_cost": f"${self.video_cost:.2f}",
            "total_cost": f"${self.total_cost:.2f}",
            "budget_remaining": f"${TOTAL_BUDGET - self.total_cost:.2f}",
        }

# Singleton
budget_tracker = BudgetTracker()
