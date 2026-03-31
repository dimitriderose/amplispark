import logging

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Body
from pydantic import BaseModel as _PydanticBaseModel

from backend.services import firestore_client
from backend.services.storage_client import upload_byop_photo
from backend.agents.strategy_agent import run_strategy, refresh_research

logger = logging.getLogger(__name__)

router = APIRouter()


class CreatePlanBody(_PydanticBaseModel):
    num_days: int = 7
    business_events: str | None = None
    platforms: list[str] | None = None


@router.get("/brands/{brand_id}/plans")
async def list_plans(brand_id: str):
    """List all content plans for a brand, newest first."""
    plans = await firestore_client.list_plans(brand_id)
    return {"plans": plans}


@router.post("/brands/{brand_id}/plans")
async def create_plan(brand_id: str, body: CreatePlanBody = Body(CreatePlanBody())):
    """Generate a content calendar plan using the Strategy Agent."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    num_days = max(1, min(body.num_days, 30))

    platforms = body.platforms
    if platforms is None:
        stored = brand.get("selected_platforms", [])
        mode = brand.get("platform_mode", "ai")
        if mode == "manual" and stored:
            platforms = stored
        # else: None -> Strategy Agent uses AI recommendation (existing behavior)

    try:
        days, trend_summary = await run_strategy(brand_id, brand, num_days, business_events=body.business_events, platforms=platforms)
    except Exception as e:
        logger.error(f"Strategy agent error for brand {brand_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    plan_data = {
        "brand_id": brand_id,
        "num_days": num_days,
        "status": "complete",
        "days": days,
        "business_events": body.business_events,
        "trend_summary": trend_summary,
    }

    try:
        plan_id = await firestore_client.create_plan(brand_id, plan_data)
    except Exception as e:
        logger.error(f"Failed to persist plan for brand {brand_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    return {"plan_id": plan_id, "status": "complete", "days": days, "trend_summary": trend_summary}


@router.get("/brands/{brand_id}/plans/{plan_id}")
async def get_plan(brand_id: str, plan_id: str):
    """Get a content plan by ID."""
    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan_profile": plan}


@router.post("/brands/{brand_id}/plans/{plan_id}/refresh-research")
async def refresh_plan_research(brand_id: str, plan_id: str):
    """Re-run trend research for a plan and update its trend_summary in Firestore."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    industry = brand.get("industry", "")
    stored_platforms = brand.get("selected_platforms", [])
    platforms = stored_platforms if stored_platforms else ["instagram", "linkedin"]
    primary_platform = platforms[0] if platforms else "instagram"

    # Re-run all research via the strategy agent's public API
    trend_summary = await refresh_research(platforms, industry, primary_platform)

    await firestore_client.update_plan(brand_id, plan_id, {"trend_summary": trend_summary})

    return {"trend_summary": trend_summary}


class UpdatePlanDayBody(_PydanticBaseModel):
    content_theme: str | None = None
    platform: str | None = None
    pillar: str | None = None
    format: str | None = None
    cta_type: str | None = None
    posting_time: str | None = None
    derivative_type: str | None = None
    custom_photo_url: str | None = None
    custom_photo_gcs_uri: str | None = None
    custom_photo_mime: str | None = None
    briefs: list[dict] | None = None


@router.put("/brands/{brand_id}/plans/{plan_id}/days/{day_index}")
async def update_plan_day(
    brand_id: str,
    plan_id: str,
    day_index: int,
    data: UpdatePlanDayBody = Body(...),
):
    """Update a specific day in a content plan."""
    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    days = plan.get("days", [])
    if day_index < 0 or day_index >= len(days):
        raise HTTPException(
            status_code=400,
            detail=f"day_index {day_index} out of range (plan has {len(days)} days)",
        )

    # Remove protected fields from user-supplied data
    safe_data = {k: v for k, v in data.model_dump(exclude_none=True).items() if k not in ("day_index", "brand_id", "plan_id")}

    try:
        await firestore_client.update_plan_day(brand_id, plan_id, day_index, safe_data)
    except Exception as e:
        logger.error(f"Failed to update day {day_index} for plan {plan_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    updated_plan = await firestore_client.get_plan(plan_id, brand_id)
    return {"plan_profile": updated_plan}


# ── BYOP — Bring Your Own Photos ─────────────────────────────

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/brands/{brand_id}/plans/{plan_id}/days/{day_index}/photo")
async def upload_day_photo(
    brand_id: str,
    plan_id: str,
    day_index: int,
    file: UploadFile = File(...),
):
    """Upload a custom photo for a specific calendar day (BYOP).

    Stores the image in GCS and records the signed URL + GCS URI on the
    day's plan document so that content generation later uses the photo
    instead of generating one via Imagen.
    """
    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    days = plan.get("days", [])
    if day_index < 0 or day_index >= len(days):
        raise HTTPException(status_code=400, detail=f"day_index {day_index} out of range")

    mime = file.content_type or "image/jpeg"
    if mime not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP images are accepted")

    # Check Content-Length / file.size before reading entire file into memory
    max_size = 20 * 1024 * 1024  # 20 MB cap
    if file.size is not None and file.size > max_size:
        raise HTTPException(status_code=400, detail="Image must be smaller than 20 MB")

    # Stream-read up to max_size + 1 byte to detect oversized uploads
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 64)  # 64 KB chunks
        if not chunk:
            break
        total += len(chunk)
        if total > max_size:
            raise HTTPException(status_code=400, detail="Image must be smaller than 20 MB")
        chunks.append(chunk)
    file_bytes = b"".join(chunks)

    try:
        signed_url, gcs_uri = await upload_byop_photo(
            brand_id, plan_id, day_index, file_bytes, mime
        )
    except Exception as e:
        logger.error("BYOP upload failed for brand %s plan %s day %s: %s", brand_id, plan_id, day_index, e)
        raise HTTPException(status_code=500, detail="Internal server error")

    await firestore_client.update_plan_day(brand_id, plan_id, day_index, {
        "custom_photo_url": signed_url,
        "custom_photo_gcs_uri": gcs_uri,
        "custom_photo_mime": mime,
    })

    return {"custom_photo_url": signed_url, "day_index": day_index}


@router.delete("/brands/{brand_id}/plans/{plan_id}/days/{day_index}/photo")
async def delete_day_photo(brand_id: str, plan_id: str, day_index: int):
    """Remove a custom photo from a calendar day, reverting to AI image generation."""
    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    days = plan.get("days", [])
    if day_index < 0 or day_index >= len(days):
        raise HTTPException(status_code=400, detail=f"day_index {day_index} out of range")

    await firestore_client.update_plan_day(brand_id, plan_id, day_index, {
        "custom_photo_url": None,
        "custom_photo_gcs_uri": None,
        "custom_photo_mime": None,
    })

    return {"status": "removed", "day_index": day_index}
