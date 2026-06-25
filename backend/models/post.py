from datetime import datetime

from pydantic import BaseModel


class ReviewCheck(BaseModel):
    score: float
    feedback: str


class ReviewResult(BaseModel):
    overall_score: float
    approved: bool
    checks: dict  # tone, audience, platform, visual, quality — each with score + feedback
    suggestions: list[str] = []
    reviewed_at: datetime | None = None


class Post(BaseModel):
    post_id: str
    plan_id: str | None = None
    brand_id: str
    day_index: int | None = None
    is_quick_post: bool = False
    platform: str
    caption: str = ""
    image_urls: list[str] = []
    hashtags: list[str] = []
    posting_time: str = ""
    status: str = "draft"  # draft | approved | posted
    image_source: str = "generated"  # generated | user_upload
    review: ReviewResult | None = None
    video_url: str | None = None
    publish_status: dict | None = None  # { "notion": { status, page_id, ... } }
    created_at: datetime | None = None
    updated_at: datetime | None = None
    original_image_url: str | None = None  # snapshot before first edit (for reset)
    edit_count: int = 0  # number of edits applied to current image
    thumbnail_url: str | None = None  # custom thumbnail for video posts


class VideoJob(BaseModel):
    job_id: str
    post_id: str
    status: str = "queued"  # queued | generating | complete | failed
    tier: str = "fast"  # fast | standard
    result: dict | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
