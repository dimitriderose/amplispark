from datetime import datetime

from pydantic import BaseModel, Field


class BrandProfileCreate(BaseModel):
    website_url: str | None = None
    description: str = Field(..., min_length=20)
    uploaded_assets: list[str] | None = []
    owner_uid: str | None = None


class BrandProfileUpdate(BaseModel):
    """Whitelist of fields a user is allowed to update directly."""

    business_name: str | None = None
    business_type: str | None = None
    website_url: str | None = None
    description: str | None = None
    industry: str | None = None
    tone: str | None = None
    colors: list[str] | None = None
    target_audience: str | None = None
    visual_style: str | None = None
    image_style_directive: str | None = None
    caption_style_directive: str | None = None
    content_themes: list[str] | None = None
    competitors: list[str] | None = None
    logo_url: str | None = None
    image_generation_risk: str | None = None
    byop_recommendation: str | None = None
    ui_preferences: dict | None = None
    selected_platforms: list[str] | None = None
    platform_mode: str | None = None
    default_image_style: str | None = None


class BrandProfile(BaseModel):
    brand_id: str
    business_name: str = ""
    business_type: str = "general"  # local_business | service | personal_brand | ecommerce
    website_url: str | None = None
    description: str
    industry: str = ""
    tone: str = ""
    colors: list[str] = []
    target_audience: str = ""
    visual_style: str = ""
    image_style_directive: str = ""
    caption_style_directive: str = ""
    content_themes: list[str] = []
    competitors: list[str] = []
    selected_platforms: list[str] = []
    platform_mode: str = "ai"  # "ai" | "manual"
    logo_url: str | None = None
    product_photos: list[str] = []
    uploaded_assets: list[dict] = []
    integrations: dict = {}  # { "notion": { access_token, ... }, "buffer": { ... } }
    default_image_style: str | None = None  # key from _IMAGE_STYLE_MAP (e.g. "editorial", "anime")
    analysis_status: str = "pending"  # pending | analyzing | complete | failed
    created_at: datetime | None = None
    updated_at: datetime | None = None
