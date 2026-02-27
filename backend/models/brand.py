from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class BrandProfileCreate(BaseModel):
    website_url: Optional[str] = None
    description: str = Field(..., min_length=20)
    uploaded_assets: Optional[List[str]] = []
    owner_uid: Optional[str] = None

class BrandProfileUpdate(BaseModel):
    """Whitelist of fields a user is allowed to update directly."""
    business_name: Optional[str] = None
    business_type: Optional[str] = None
    website_url: Optional[str] = None
    description: Optional[str] = None
    industry: Optional[str] = None
    tone: Optional[str] = None
    colors: Optional[List[str]] = None
    target_audience: Optional[str] = None
    visual_style: Optional[str] = None
    image_style_directive: Optional[str] = None
    caption_style_directive: Optional[str] = None
    content_themes: Optional[List[str]] = None
    competitors: Optional[List[str]] = None
    logo_url: Optional[str] = None
    image_generation_risk: Optional[str] = None
    byop_recommendation: Optional[str] = None
    ui_preferences: Optional[dict] = None


class BrandProfile(BaseModel):
    brand_id: str
    business_name: str = ""
    business_type: str = "general"  # local_business | service | personal_brand | ecommerce
    website_url: Optional[str] = None
    description: str
    industry: str = ""
    tone: str = ""
    colors: List[str] = []
    target_audience: str = ""
    visual_style: str = ""
    image_style_directive: str = ""
    caption_style_directive: str = ""
    content_themes: List[str] = []
    competitors: List[str] = []
    logo_url: Optional[str] = None
    product_photos: List[str] = []
    uploaded_assets: List[dict] = []
    analysis_status: str = "pending"  # pending | analyzing | complete | failed
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
