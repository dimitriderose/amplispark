from datetime import datetime

from pydantic import BaseModel


class Pillar(BaseModel):
    id: str
    theme: str
    key_message: str
    source: str = "generated"  # "event" | "generated"
    derivative_count: int = 0


class DayBrief(BaseModel):
    day_index: int
    day_name: str
    platform: str  # instagram | linkedin | x | tiktok | facebook
    theme: str
    content_type: str  # photo | carousel | story | reel | thread
    caption_direction: str
    image_direction: str
    posting_time: str
    pillar_id: str | None = None
    derivative_type: str | None = (
        None  # original | condensed | visual | conversational | engagement | standalone
    )
    pillar_context: str | None = None
    user_photo_url: str | None = None
    image_source: str = "generated"  # generated | user_upload
    generated: bool = False
    post_id: str | None = None
    status: str = "planned"  # planned | generated | approved | posted


class ContentPlanCreate(BaseModel):
    brand_id: str
    goals: str | None = None
    platforms: list[str] | None = ["instagram"]
    business_events: str | None = None


class ContentPlan(BaseModel):
    plan_id: str
    brand_id: str
    week_of: str
    goals: str | None = None
    business_events: str | None = None
    platforms: list[str] = []
    pillars: list[Pillar] = []
    days: list[DayBrief] = []
    status: str = "draft"  # draft | generating | complete
    created_at: datetime | None = None
