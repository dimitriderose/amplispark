import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Body

from backend.models.brand import BrandProfileCreate, BrandProfile, BrandProfileUpdate
from backend.services import firestore_client
from backend.services.storage_client import upload_brand_asset
from backend.agents.brand_analyst import run_brand_analysis

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/brands")
async def list_brands(owner_uid: str = Query(...)):
    """List all brands owned by a given anonymous UID."""
    brands = await firestore_client.list_brands_by_owner(owner_uid)
    return {"brands": brands}


@router.post("/brands")
async def create_brand(data: BrandProfileCreate):
    """Create a new brand profile record (without analysis)."""
    brand_data: dict = {
        "website_url": data.website_url,
        "description": data.description,
        "uploaded_assets": data.uploaded_assets or [],
        "analysis_status": "pending",
    }
    if data.owner_uid:
        brand_data["owner_uid"] = data.owner_uid
    brand_id = await firestore_client.create_brand(brand_data)
    return {"brand_id": brand_id, "status": "created"}


@router.patch("/brands/{brand_id}/claim")
async def claim_brand_endpoint(brand_id: str, owner_uid: str = Body(..., embed=True)):
    """Claim an ownerless brand for an anonymous UID (grandfathering)."""
    success = await firestore_client.claim_brand(brand_id, owner_uid)
    if not success:
        raise HTTPException(status_code=404, detail="Brand not found")
    return {"status": "claimed", "brand_id": brand_id}


@router.post("/brands/{brand_id}/analyze")
async def analyze_brand(brand_id: str, data: BrandProfileCreate):
    """Trigger Brand Analyst agent to build the brand profile."""
    # Mark as analyzing
    await firestore_client.update_brand(brand_id, {"analysis_status": "analyzing"})

    try:
        # Pass any existing social voice so re-analysis preserves connected voice data
        existing_brand = await firestore_client.get_brand(brand_id)
        existing_voice = existing_brand.get("social_voice_analysis") if existing_brand else None

        profile = await run_brand_analysis(
            description=data.description,
            website_url=data.website_url,
            brand_id=brand_id,
            social_voice_analysis=existing_voice,
        )

        # Only copy known-safe fields from LLM output — never spread arbitrary keys into Firestore
        _ALLOWED_PROFILE_KEYS = {
            "business_name", "business_type", "industry", "tone", "colors",
            "target_audience", "visual_style", "content_themes", "competitors",
            "image_style_directive", "caption_style_directive",
            "image_generation_risk", "byop_recommendation", "style_reference_gcs_uri",
            "logo_url",
        }
        update_data = {k: v for k, v in profile.items() if k in _ALLOWED_PROFILE_KEYS}
        update_data.update({
            "description": data.description,
            "website_url": data.website_url,
            "analysis_status": "complete",
        })
        await firestore_client.update_brand(brand_id, update_data)

        brand = await firestore_client.get_brand(brand_id)
        return {"brand_profile": brand, "status": "analyzed"}

    except Exception as e:
        logger.error(f"Brand analysis error for {brand_id}: {e}")
        await firestore_client.update_brand(brand_id, {"analysis_status": "failed"})
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/brands/{brand_id}")
async def get_brand(brand_id: str):
    """Get brand profile by ID."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return {"brand_profile": brand}


@router.put("/brands/{brand_id}")
async def update_brand(brand_id: str, data: BrandProfileUpdate):
    """Update brand profile fields (user corrections). Only whitelisted fields accepted."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    # exclude_unset=True so only explicitly provided fields are written
    await firestore_client.update_brand(brand_id, data.model_dump(exclude_unset=True))
    updated = await firestore_client.get_brand(brand_id)
    return {"brand_profile": updated, "status": "updated"}


@router.post("/brands/{brand_id}/upload")
async def upload_brand_asset_endpoint(
    brand_id: str,
    files: list[UploadFile] = File(...),
):
    """Upload brand assets (logo, product photos, PDFs). Max 3 files."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    if len(files) > 3:
        raise HTTPException(status_code=400, detail="Maximum 3 files allowed")

    uploaded = []
    for file in files:
        content = await file.read()
        mime = file.content_type or "application/octet-stream"
        file_type = "document" if "pdf" in mime else "image"
        gcs_uri = await upload_brand_asset(brand_id, content, file.filename, mime)
        uploaded.append({
            "filename": file.filename,
            "url": gcs_uri,
            "type": file_type,
        })

    # Update brand assets list in Firestore
    existing = brand.get("uploaded_assets", [])
    await firestore_client.update_brand(brand_id, {"uploaded_assets": existing + uploaded})

    return {"uploaded": uploaded}


@router.delete("/brands/{brand_id}/assets/{asset_index}")
async def delete_brand_asset(brand_id: str, asset_index: int):
    """Remove a single asset from uploaded_assets by its index."""
    removed = await firestore_client.remove_brand_asset(brand_id, asset_index)
    if removed is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "deleted", "removed": removed}


@router.patch("/brands/{brand_id}/logo")
async def set_brand_logo(brand_id: str, logo_url: Optional[str] = Body(None, embed=True)):
    """Set or clear the brand logo_url field."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    await firestore_client.update_brand(brand_id, {"logo_url": logo_url})
    return {"status": "updated", "logo_url": logo_url}
