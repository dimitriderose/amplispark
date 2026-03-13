import asyncio
import io
import json
import logging
import os
import re
import uuid
import zipfile
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form, Body, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response, StreamingResponse

from backend.config import CORS_ORIGINS, GCS_BUCKET_NAME
from backend.models.brand import BrandProfileCreate, BrandProfile, BrandProfileUpdate
from backend.services import firestore_client
from backend.services.storage_client import (
    upload_brand_asset,
    get_signed_url,
    download_from_gcs,
    download_gcs_uri,
    upload_byop_photo,
    upload_raw_video_source,
    upload_repurposed_clip,
    get_bucket,
)
from google import genai as _genai
from google.genai import types as _gtypes
from backend.config import GOOGLE_API_KEY, GEMINI_MODEL
from backend.agents.brand_analyst import run_brand_analysis
from backend.agents.strategy_agent import run_strategy, _research_platform_trends, _research_visual_trends, _research_video_trends
from backend.agents.voice_coach import build_coaching_prompt

_live_client = _genai.Client(api_key=GOOGLE_API_KEY)
_LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Amplifi API",
    description="AI-powered social media content generation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Health ────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "amplifi-backend", "version": "1.0.0"}

# ── Brand Management ──────────────────────────────────────────

@app.get("/api/brands")
async def list_brands(owner_uid: str = Query(...)):
    """List all brands owned by a given anonymous UID."""
    brands = await firestore_client.list_brands_by_owner(owner_uid)
    return {"brands": brands}


@app.post("/api/brands")
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


@app.patch("/api/brands/{brand_id}/claim")
async def claim_brand_endpoint(brand_id: str, owner_uid: str = Body(..., embed=True)):
    """Claim an ownerless brand for an anonymous UID (grandfathering)."""
    success = await firestore_client.claim_brand(brand_id, owner_uid)
    if not success:
        raise HTTPException(status_code=404, detail="Brand not found")
    return {"status": "claimed", "brand_id": brand_id}


@app.post("/api/brands/{brand_id}/analyze")
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
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/brands/{brand_id}")
async def get_brand(brand_id: str):
    """Get brand profile by ID."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return {"brand_profile": brand}


@app.put("/api/brands/{brand_id}")
async def update_brand(brand_id: str, data: BrandProfileUpdate):
    """Update brand profile fields (user corrections). Only whitelisted fields accepted."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    # exclude_unset=True so only explicitly provided fields are written
    await firestore_client.update_brand(brand_id, data.model_dump(exclude_unset=True))
    updated = await firestore_client.get_brand(brand_id)
    return {"brand_profile": updated, "status": "updated"}


@app.post("/api/brands/{brand_id}/upload")
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


@app.delete("/api/brands/{brand_id}/assets/{asset_index}")
async def delete_brand_asset(brand_id: str, asset_index: int):
    """Remove a single asset from uploaded_assets by its index."""
    removed = await firestore_client.remove_brand_asset(brand_id, asset_index)
    if removed is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "deleted", "removed": removed}


@app.patch("/api/brands/{brand_id}/logo")
async def set_brand_logo(brand_id: str, logo_url: Optional[str] = Body(None, embed=True)):
    """Set or clear the brand logo_url field."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    await firestore_client.update_brand(brand_id, {"logo_url": logo_url})
    return {"status": "updated", "logo_url": logo_url}


# ── Social Voice Analysis ──────────────────────────────────────

@app.post("/api/brands/{brand_id}/connect-social")
async def connect_social_account(
    brand_id: str,
    platform: str = Body(...),
    oauth_token: str = Body(...),
):
    """Connect a social account, analyze the user's writing voice, and persist it.

    Accepts a platform OAuth 2.0 user access token. Fetches recent posts via
    the platform's API, runs Gemini voice analysis, and stores the result on
    the brand profile.

    Request body (JSON):
      { "platform": "linkedin|instagram|x", "oauth_token": "..." }

    Stored fields:
      social_voice_analyses: dict[platform → analysis]  — all connected platforms
      social_voice_analysis:  dict                       — latest analysis (for injection)
      social_voice_platform:  str                        — platform of latest analysis
      connected_platforms:    list[str]                  — all connected platform keys
    """
    from backend.agents.social_voice_agent import connect_platform

    if not oauth_token or not oauth_token.strip():
        raise HTTPException(status_code=400, detail="oauth_token must not be empty")

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    try:
        voice_analysis = await connect_platform(platform, oauth_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Social voice analysis failed for brand %s platform %s: %s",
            brand_id, platform, e,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch posts from {platform}. Check your token and try again.",
        )

    # Merge into brand profile — store per-platform dict + latest shortcut
    connected = list(brand.get("connected_platforms", []))
    if platform not in connected:
        connected.append(platform)

    existing_analyses = dict(brand.get("social_voice_analyses", {}))
    existing_analyses[platform] = voice_analysis

    await firestore_client.update_brand(brand_id, {
        "social_voice_analyses": existing_analyses,   # all platforms
        "social_voice_analysis": voice_analysis,       # latest (used by content creator)
        "social_voice_platform": platform,
        "connected_platforms": connected,
    })

    return {"platform": platform, "voice_analysis": voice_analysis}


# ── GCS proxy (local dev) ──────────────────────────────────────
from fastapi.responses import Response


@app.get("/api/storage/serve/{blob_path:path}")
async def serve_storage_object(blob_path: str):
    """Proxy-serve a GCS object.  Used when signed URLs are unavailable
    (e.g. local dev with ADC credentials that lack a private key)."""
    try:
        bucket = get_bucket()
        blob = bucket.blob(blob_path)
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, blob.download_as_bytes)
        ct = blob.content_type or "application/octet-stream"
        return Response(content=data, media_type=ct)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Posts ─────────────────────────────────────────────────────

async def _refresh_signed_urls(post: dict) -> dict:
    """Re-sign expired GCS URLs so images always load."""
    gcs_uri = post.get("image_gcs_uri")
    if gcs_uri:
        try:
            post["image_url"] = await get_signed_url(gcs_uri)
        except Exception:
            pass
    for i, uri in enumerate(post.get("image_gcs_uris") or []):
        try:
            urls = post.setdefault("image_urls", [])
            if i < len(urls):
                urls[i] = await get_signed_url(uri)
        except Exception:
            pass
    if post.get("thumbnail_gcs_uri"):
        try:
            post["thumbnail_url"] = await get_signed_url(post["thumbnail_gcs_uri"])
        except Exception:
            pass
    return post


@app.get("/api/posts")
async def list_posts_endpoint(
    brand_id: str = Query(...),
    plan_id: str | None = Query(None),
):
    """List all posts for a brand, optionally filtered by plan."""
    posts = await firestore_client.list_posts(brand_id, plan_id)
    await asyncio.gather(*[_refresh_signed_urls(p) for p in posts])
    return {"posts": posts}


@app.get("/api/posts/{post_id}")
async def get_post_endpoint(
    post_id: str,
    brand_id: str = Query(...),
):
    """Return a single post by ID."""
    post = await firestore_client.get_post(brand_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await _refresh_signed_urls(post)
    return post


# ── Export / Download ─────────────────────────────────────────

@app.get("/api/posts/{post_id}/export")
async def export_post(
    post_id: str,
    brand_id: str = Query(..., description="Brand ID that owns the post"),
):
    """Download a single post as a ZIP (image + caption.txt)."""
    post = await firestore_client.get_post(brand_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    platform: str = post.get("platform", "post")
    caption: str = post.get("caption", "")
    hashtags: list[str] = post.get("hashtags", [])
    day_index = post.get("day_index", 0)
    base_name = f"{platform}_day{day_index + 1}"

    # Helper to download a blob from GCS by gs:// URI
    async def _dl(uri: str | None) -> bytes | None:
        if not uri:
            return None
        prefix = f"gs://{GCS_BUCKET_NAME}/"
        if not uri.startswith(prefix):
            return None
        try:
            blob = get_bucket().blob(uri[len(prefix):])
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, blob.download_as_bytes)
        except Exception as exc:
            logger.warning("Could not download %s for post %s: %s", uri, post_id, exc)
            return None

    # Download image + video in parallel
    img_bytes, vid_bytes = await asyncio.gather(
        _dl(post.get("image_gcs_uri")),
        _dl((post.get("video") or {}).get("video_gcs_uri")),
    )

    # Build ZIP
    zip_buffer = io.BytesIO()
    archive_root = f"amplifi_{base_name}"
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        if img_bytes:
            ext = "png" if img_bytes[:4] == b"\x89PNG" else "jpg"
            zf.writestr(f"{archive_root}/{base_name}.{ext}", img_bytes)
        if vid_bytes:
            zf.writestr(f"{archive_root}/{base_name}.mp4", vid_bytes)
        hashtag_block = "\n".join(f"#{tag.lstrip('#')}" for tag in hashtags)
        caption_text = caption
        if hashtag_block:
            caption_text = f"{caption}\n\n{hashtag_block}"
        zf.writestr(f"{archive_root}/{base_name}_caption.txt", caption_text.encode("utf-8"))

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={archive_root}.zip"},
    )


@app.post("/api/export/{plan_id}")
async def export_plan_zip(
    plan_id: str,
    brand_id: str = Query(..., description="Brand ID that owns the plan"),
):
    """Build and stream a ZIP archive containing all posts for a content plan.

    Archive layout::

        amplifi_export_<plan_id>/
            instagram_0.jpg
            instagram_0_caption.txt
            linkedin_1.jpg
            linkedin_1_caption.txt
            …
            content_plan.json

    Each ``*_caption.txt`` file contains the post caption followed by the
    hashtags (one per line, prefixed with ``#``).
    ``content_plan.json`` contains full metadata for every post.
    """
    # ── Fetch plan to confirm it exists ───────────────────────
    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # ── List all posts belonging to this plan ─────────────────
    posts: list[dict] = await firestore_client.list_posts(brand_id, plan_id)
    if not posts:
        raise HTTPException(status_code=404, detail="No posts found for this plan")

    # ── Download image bytes directly from GCS ──────────────────
    async def _download_post_image(post: dict) -> bytes | None:
        gcs_uri: str | None = post.get("image_gcs_uri")
        if not gcs_uri:
            return None
        prefix = f"gs://{GCS_BUCKET_NAME}/"
        if not gcs_uri.startswith(prefix):
            return None
        blob_path = gcs_uri[len(prefix):]
        try:
            bucket = get_bucket()
            blob = bucket.blob(blob_path)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, blob.download_as_bytes)
        except Exception as exc:
            logger.warning("Could not download image for post %s: %s", post.get("post_id"), exc)
            return None

    # ── Download video bytes directly from GCS ─────────────────
    async def _download_post_video(post: dict) -> bytes | None:
        video = post.get("video")
        if not video:
            return None
        gcs_uri: str | None = video.get("video_gcs_uri")
        if not gcs_uri:
            return None
        prefix = f"gs://{GCS_BUCKET_NAME}/"
        if not gcs_uri.startswith(prefix):
            return None
        blob_path = gcs_uri[len(prefix):]
        try:
            bucket = get_bucket()
            blob = bucket.blob(blob_path)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, blob.download_as_bytes)
        except Exception as exc:
            logger.warning("Could not download video for post %s: %s", post.get("post_id"), exc)
            return None

    image_bytes_list: list[bytes | None] = await asyncio.gather(
        *[_download_post_image(p) for p in posts]
    )
    video_bytes_list: list[bytes | None] = await asyncio.gather(
        *[_download_post_video(p) for p in posts]
    )

    # ── Build ZIP in memory ───────────────────────────────────
    zip_buffer = io.BytesIO()
    archive_root = f"amplifi_export_{plan_id}"

    # Collect clean metadata for content_plan.json (strip internal GCS URIs)
    plan_metadata: list[dict] = []

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for index, (post, img_bytes, vid_bytes) in enumerate(
            zip(posts, image_bytes_list, video_bytes_list)
        ):
            platform: str = post.get("platform", "post")
            caption: str = post.get("caption", "")
            hashtags: list[str] = post.get("hashtags", [])
            base_name = f"{platform}_{index}"

            # Image file — detect PNG vs JPEG by magic bytes
            if img_bytes:
                ext = "png" if img_bytes[:4] == b"\x89PNG" else "jpg"
                zf.writestr(f"{archive_root}/{base_name}.{ext}", img_bytes)

            # Video file
            if vid_bytes:
                zf.writestr(f"{archive_root}/{base_name}.mp4", vid_bytes)

            # Caption + hashtags text file
            hashtag_block = "\n".join(f"#{tag.lstrip('#')}" for tag in hashtags)
            caption_text = caption
            if hashtag_block:
                caption_text = f"{caption}\n\n{hashtag_block}"
            zf.writestr(
                f"{archive_root}/{base_name}_caption.txt",
                caption_text.encode("utf-8"),
            )

            # Collect metadata (safe copy — omit internal GCS URIs)
            post_meta = {
                k: v for k, v in post.items()
                if k not in ("image_gcs_uri", "image_gcs_uris")
            }
            plan_metadata.append(post_meta)

        # content_plan.json
        zf.writestr(
            f"{archive_root}/content_plan.json",
            json.dumps(plan_metadata, indent=2, default=str).encode("utf-8"),
        )

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=amplifi_export_{plan_id}.zip"
        },
    )


# ── Content Plans ─────────────────────────────────────────────

from pydantic import BaseModel as _PydanticBaseModel


class CreatePlanBody(_PydanticBaseModel):
    num_days: int = 7
    business_events: str | None = None
    platforms: list[str] | None = None


@app.get("/api/brands/{brand_id}/plans")
async def list_plans(brand_id: str):
    """List all content plans for a brand, newest first."""
    plans = await firestore_client.list_plans(brand_id)
    return {"plans": plans}


@app.post("/api/brands/{brand_id}/plans")
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
        # else: None → Strategy Agent uses AI recommendation (existing behavior)

    try:
        days, trend_summary = await run_strategy(brand_id, brand, num_days, business_events=body.business_events, platforms=platforms)
    except Exception as e:
        logger.error(f"Strategy agent error for brand {brand_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        raise HTTPException(status_code=500, detail=str(e))

    return {"plan_id": plan_id, "status": "complete", "days": days, "trend_summary": trend_summary}


@app.get("/api/brands/{brand_id}/plans/{plan_id}")
async def get_plan(brand_id: str, plan_id: str):
    """Get a content plan by ID."""
    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan_profile": plan}


@app.post("/api/brands/{brand_id}/plans/{plan_id}/refresh-research")
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

    # Re-run all three research tracks in parallel (bypasses cache by using fresh calls)
    # Clear cache for these keys first so research is truly fresh
    for p in platforms[:5]:
        try:
            await firestore_client.save_platform_trends(p, industry, {})
        except Exception:
            pass
    try:
        await firestore_client.save_platform_trends(f"visual_{primary_platform}", industry, {})
        await firestore_client.save_platform_trends(f"video_{primary_platform}", industry, {})
    except Exception:
        pass

    platform_trends_results, visual_result, video_result = await asyncio.gather(
        asyncio.gather(*[_research_platform_trends(p, industry) for p in platforms[:5]], return_exceptions=True),
        _research_visual_trends(primary_platform, industry),
        _research_video_trends(primary_platform, industry),
        return_exceptions=True,
    )

    platform_trends_map = {}
    if isinstance(platform_trends_results, (list, tuple)):
        for p, r in zip(platforms[:5], platform_trends_results):
            if isinstance(r, dict):
                platform_trends_map[p] = r

    trend_summary = {
        "researched_at": datetime.utcnow().isoformat(),
        "platform_trends": platform_trends_map,
        "visual_trends": visual_result if isinstance(visual_result, dict) else None,
        "video_trends": video_result if isinstance(video_result, dict) else None,
    }

    await firestore_client.update_plan(brand_id, plan_id, {"trend_summary": trend_summary})

    return {"trend_summary": trend_summary}


@app.put("/api/brands/{brand_id}/plans/{plan_id}/days/{day_index}")
async def update_plan_day(
    brand_id: str,
    plan_id: str,
    day_index: int,
    data: dict = Body(...),
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
    safe_data = {k: v for k, v in data.items() if k not in ("day_index", "brand_id", "plan_id")}

    try:
        await firestore_client.update_plan_day(brand_id, plan_id, day_index, safe_data)
    except Exception as e:
        logger.error(f"Failed to update day {day_index} for plan {plan_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    updated_plan = await firestore_client.get_plan(plan_id, brand_id)
    return {"plan_profile": updated_plan}


# ── BYOP — Bring Your Own Photos ─────────────────────────────

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@app.post("/api/brands/{brand_id}/plans/{plan_id}/days/{day_index}/photo")
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

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:  # 20 MB cap
        raise HTTPException(status_code=400, detail="Image must be smaller than 20 MB")

    try:
        signed_url, gcs_uri = await upload_byop_photo(
            brand_id, plan_id, day_index, file_bytes, mime
        )
    except Exception as e:
        logger.error("BYOP upload failed for brand %s plan %s day %s: %s", brand_id, plan_id, day_index, e)
        raise HTTPException(status_code=500, detail=str(e))

    await firestore_client.update_plan_day(brand_id, plan_id, day_index, {
        "custom_photo_url": signed_url,
        "custom_photo_gcs_uri": gcs_uri,
        "custom_photo_mime": mime,
    })

    return {"custom_photo_url": signed_url, "day_index": day_index}


@app.delete("/api/brands/{brand_id}/plans/{plan_id}/days/{day_index}/photo")
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


# ── Interleaved Generation (SSE) ──────────────────────────────
from sse_starlette.sse import EventSourceResponse

from backend.agents.content_creator import generate_post


@app.get("/api/generate/{plan_id}/{day_index}")
async def stream_generate(
    plan_id: str,
    day_index: int,
    brand_id: str = Query(...),
    instructions: str | None = Query(None),
):
    """SSE endpoint: streams interleaved caption + image generation events."""

    # Fetch plan and brand
    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    days = plan.get("days", [])
    if day_index < 0 or day_index >= len(days):
        raise HTTPException(status_code=400, detail="day_index out of range")

    day_brief = days[day_index]

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # BYOP: if the day has a custom photo, download it for vision-based generation.
    # We use the gs:// URI (not the stored signed URL) to generate a fresh short-lived
    # signed URL at request time. This avoids both SSRF (no user-controlled URL is
    # fetched) and staleness (the GCS URI never expires).
    custom_photo_bytes: bytes | None = None
    custom_photo_mime = "image/jpeg"
    custom_photo_gcs_uri = day_brief.get("custom_photo_gcs_uri")
    if custom_photo_gcs_uri:
        try:
            custom_photo_bytes = await download_gcs_uri(custom_photo_gcs_uri)
            custom_photo_mime = day_brief.get("custom_photo_mime", "image/jpeg")
        except Exception as e:
            logger.warning("Could not download custom photo for day %s: %s", day_index, e)
            custom_photo_bytes = None  # fall back to normal generation

    # Delete any existing post for this plan+day+platform (regeneration replaces, not duplicates)
    brief_platform = day_brief.get("platform", "instagram")
    existing_posts = await firestore_client.list_posts(brand_id, plan_id)
    for ep in existing_posts:
        if ep.get("brief_index") == day_index and ep.get("platform", "") == brief_platform:
            try:
                await firestore_client.delete_post(brand_id, ep["post_id"])
            except Exception:
                pass  # best-effort cleanup

    # Extract prior hooks from already-generated posts for deduplication
    prior_hooks = [
        p.get("caption", "").split("\n")[0][:100]
        for p in existing_posts
        if p.get("status") in ("complete", "approved") and p.get("caption")
        and not (p.get("brief_index") == day_index and p.get("platform", "") == brief_platform)  # exclude the post we just deleted
    ]

    # Create a pending post record in Firestore.
    # save_post(brand_id, plan_id, data) generates and returns its own post_id.
    post_id = await firestore_client.save_post(brand_id, plan_id, {
        "day_index": day_brief.get("day_index", day_index),
        "brief_index": day_index,
        "platform": day_brief.get("platform", "instagram"),
        "pillar": day_brief.get("pillar"),
        "format": day_brief.get("format"),
        "cta_type": day_brief.get("cta_type"),
        "derivative_type": day_brief.get("derivative_type", "original"),
        "status": "generating",
        "caption": "",
        "hashtags": [],
        "image_url": None,
        "byop": custom_photo_bytes is not None,
    })

    # Run generation as a background task so it completes (and saves to
    # Firestore) even if the user navigates away and the SSE stream closes.
    event_queue: asyncio.Queue = asyncio.Queue()

    async def _run_generation():
        final_caption = ""
        final_hashtags: list = []
        final_image_url = None
        final_image_gcs_uri = None
        gate_review = None

        try:
            # Heartbeat: sends "Still working..." every 15s if no events flowed
            # recently. Keeps SSE alive during review gate (25s+) and image gen.
            _last_event_time = asyncio.get_event_loop().time()

            async def _gen_heartbeat():
                nonlocal _last_event_time
                while True:
                    await asyncio.sleep(15)
                    if asyncio.get_event_loop().time() - _last_event_time > 12:
                        await event_queue.put({
                            "event": "status",
                            "data": {"message": "Still working..."},
                        })

            gen_hb = asyncio.create_task(_gen_heartbeat())
            try:
                async for event in generate_post(
                    plan_id, day_brief, brand, post_id,
                    custom_photo_bytes=custom_photo_bytes,
                    custom_photo_mime=custom_photo_mime,
                    instructions=instructions,
                    prior_hooks=prior_hooks,
                ):
                    _last_event_time = asyncio.get_event_loop().time()
                    event_name = event["event"]
                    event_data = event["data"]

                    # Track final values
                    if event_name == "caption" and not event_data.get("chunk"):
                        final_caption = event_data.get("text", "")
                        final_hashtags = event_data.get("hashtags", [])
                    elif event_name == "image":
                        final_image_url = event_data.get("url")
                        final_image_gcs_uri = event_data.get("gcs_uri")
                    elif event_name == "complete":
                        final_caption = event_data.get("caption", final_caption)
                        final_hashtags = event_data.get("hashtags", final_hashtags)
                        final_image_url = event_data.get("image_url", final_image_url)
                        final_image_gcs_uri = event_data.get("image_gcs_uri", final_image_gcs_uri)

                        # Persist complete post to Firestore
                        update_data: dict = {
                            "status": "complete",
                            "caption": final_caption,
                            "hashtags": final_hashtags,
                            "image_url": final_image_url,
                        }
                        if final_image_gcs_uri:
                            update_data["image_gcs_uri"] = final_image_gcs_uri
                        # Carousel: store all slide URLs
                        carousel_urls = event_data.get("image_urls", [])
                        carousel_gcs = event_data.get("image_gcs_uris", [])
                        if carousel_urls:
                            update_data["image_urls"] = carousel_urls
                        if carousel_gcs:
                            update_data["image_gcs_uris"] = carousel_gcs
                        # Save review from inline review gate (if present)
                        gate_review = event_data.get("review")
                        if gate_review:
                            update_data["review"] = gate_review
                        try:
                            await firestore_client.update_post(brand_id, post_id, update_data)
                        except Exception as fs_err:
                            logger.error("Firestore update failed for post %s: %s", post_id, fs_err)
                    elif event_name == "error":
                        try:
                            await firestore_client.update_post(brand_id, post_id, {"status": "failed"})
                        except Exception as fs_err:
                            logger.error("Firestore error-update failed for post %s: %s", post_id, fs_err)

                    await event_queue.put(event)
            finally:
                gen_hb.cancel()

            # ── Video-first: trigger Veo after text-only caption ──────────
            if day_brief.get("derivative_type") == "video_first" and final_caption:
                # Gate Veo on review score — skip if caption quality < 7
                _veo_gate_score = (gate_review or {}).get("score", 0) if gate_review else 0
                if _veo_gate_score < 7:
                    logger.warning("Skipping Veo — review score %d < 7 for video_first post %s",
                                   _veo_gate_score, post_id)
                    await event_queue.put({
                        "event": "video_error",
                        "data": {"message": f"Video skipped — caption scored {_veo_gate_score}/10. Regenerate for a higher-quality result."},
                    })
                else:
                    await event_queue.put({"event": "status", "data": {"message": "Generating video..."}})

                    # Heartbeat keeps SSE alive during long Veo generation (avg 2-5 min)
                    async def _heartbeat():
                        while True:
                            await asyncio.sleep(15)
                            await event_queue.put({"event": "status", "data": {"message": "Generating video..."}})

                    heartbeat_task = asyncio.create_task(_heartbeat())
                    try:
                        from backend.agents.video_creator import generate_video_clip
                        video_result = await generate_video_clip(
                            hero_image_bytes=None,  # text-to-video
                            caption=final_caption,
                            brand_profile=brand,
                            platform=day_brief.get("platform", "instagram"),
                            post_id=post_id,
                            tier="fast",
                        )
                        # Update Firestore with video metadata
                        await firestore_client.update_post(brand_id, post_id, {
                            "video_url": video_result["video_url"],
                            "video": {
                                "url": video_result["video_url"],
                                "video_gcs_uri": video_result.get("video_gcs_uri"),
                                "duration_seconds": 8,
                                "model": video_result.get("model", "veo-3.1"),
                            },
                        })
                        await event_queue.put({
                            "event": "video_complete",
                            "data": {
                                "video_url": video_result["video_url"],
                                "video_gcs_uri": video_result.get("video_gcs_uri"),
                                "audio_note": "Add trending audio before publishing — silent video underperforms on this platform.",
                            },
                        })
                    except Exception as video_err:
                        logger.error("Video generation failed for video_first post %s: %s", post_id, video_err)
                        await event_queue.put({
                            "event": "video_error",
                            "data": {"message": str(video_err)},
                        })
                    finally:
                        heartbeat_task.cancel()

        except Exception as exc:
            logger.error("Generation task error for post %s: %s", post_id, exc)
            try:
                await firestore_client.update_post(brand_id, post_id, {"status": "failed"})
            except Exception:
                pass
            await event_queue.put({"event": "error", "data": {"message": str(exc)}})
        finally:
            await event_queue.put(None)  # sentinel: end of stream

    gen_task = asyncio.create_task(_run_generation())

    async def event_stream():
        try:
            while True:
                event = await event_queue.get()
                if event is None:
                    break
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"], ensure_ascii=False),
                }
        except asyncio.CancelledError:
            # SSE closed (user navigated away) — generation task keeps running
            pass

    return EventSourceResponse(event_stream())


# ── Post Review ───────────────────────────────────────────────
from backend.agents.review_agent import review_post as _run_review

from datetime import datetime, timezone


class PatchPostBody(_PydanticBaseModel):
    caption: str | None = None
    hashtags: list[str] | None = None


class EditMediaBody(_PydanticBaseModel):
    edit_prompt: str
    slide_index: Optional[int] = None   # for carousel posts; None = main image
    target: Optional[str] = None        # "thumbnail" for video thumbnail editing


@app.patch("/api/brands/{brand_id}/posts/{post_id}")
async def patch_post_endpoint(brand_id: str, post_id: str, data: PatchPostBody):
    """Patch individual post fields (caption, hashtags) for inline editing."""
    post = await firestore_client.get_post(brand_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    allowed: dict = {}
    if data.caption is not None:
        allowed["caption"] = data.caption
    if data.hashtags is not None:
        allowed["hashtags"] = data.hashtags
    if not allowed:
        raise HTTPException(status_code=400, detail="No patchable fields provided")
    await firestore_client.update_post(brand_id, post_id, {
        **allowed,
        "user_edited": True,
        "edited_at": datetime.now(timezone.utc).isoformat(),
    })
    updated = await firestore_client.get_post(brand_id, post_id)
    return {"post": updated}


@app.post("/api/brands/{brand_id}/posts/{post_id}/review")
async def review_post_endpoint(brand_id: str, post_id: str, force: bool = Query(False)):
    """AI-review a generated post against brand guidelines."""
    post = await firestore_client.get_post(brand_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Return cached review if one exists (unless force=true for re-review)
    if not force and post.get("review"):
        return {"review": post["review"], "post_id": post_id}

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    result = await _run_review(post, brand)

    # Save review to Firestore
    await firestore_client.save_review(brand_id, post_id, result)

    # If approved, update post status
    if result.get("approved"):
        await firestore_client.update_post(brand_id, post_id, {"status": "approved"})

    # Store revision notes (specific edit instructions, not full rewrites)
    if result.get("revision_notes"):
        await firestore_client.update_post(brand_id, post_id, {
            "revision_notes": result["revision_notes"],
        })

    # If revised hashtags provided, sanitize before saving
    if result.get("revised_hashtags"):
        from backend.agents.content_creator import _sanitize_hashtags
        platform = post.get("platform", "instagram")
        cleaned = _sanitize_hashtags(result["revised_hashtags"], platform)
        await firestore_client.update_post(brand_id, post_id, {
            "hashtags": cleaned,
        })

    return {"review": result, "post_id": post_id}


@app.post("/api/brands/{brand_id}/posts/{post_id}/approve")
async def approve_post_endpoint(brand_id: str, post_id: str):
    """Manually approve a post (user override)."""
    post = await firestore_client.get_post(brand_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await firestore_client.update_post(brand_id, post_id, {"status": "approved"})
    return {"status": "approved", "post_id": post_id}


@app.post("/api/brands/{brand_id}/posts/{post_id}/edit-media")
async def edit_post_media(brand_id: str, post_id: str, body: EditMediaBody):
    """Apply a conversational edit to a post's image using AI."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    post = await firestore_client.get_post(brand_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Enforce 8-edit cap per image
    edit_count = post.get("edit_count", 0)
    if edit_count >= 8:
        raise HTTPException(status_code=422, detail="Edit limit reached (8 per image). Reset to start fresh.")

    # Determine which GCS URI to edit
    gcs_uri: str | None = None
    if body.target == "thumbnail":
        gcs_uri = post.get("thumbnail_gcs_uri")
        if not gcs_uri:
            raise HTTPException(status_code=422, detail="No editable thumbnail GCS URI found on this post")
    elif body.slide_index is not None:
        image_uris = post.get("image_gcs_uris", [])
        if body.slide_index < len(image_uris):
            gcs_uri = image_uris[body.slide_index]
    else:
        gcs_uri = post.get("image_gcs_uri") or (post.get("image_gcs_uris") or [None])[0]

    # If no image URI found, check for video post and re-generate via Veo
    if not gcs_uri:
        video_data = post.get("video") or {}
        video_gcs_uri = video_data.get("video_gcs_uri")
        if not video_gcs_uri:
            raise HTTPException(status_code=422, detail="No image or video found to edit on this post")

        from backend.agents.video_creator import generate_video_clip
        caption = post.get("caption", "")
        _platform = post.get("platform", "instagram")
        tier = video_data.get("tier", "fast")

        # Snapshot original video on first edit
        if edit_count == 0 and not post.get("original_video_url"):
            await firestore_client.update_post(brand_id, post_id, {"original_video_url": video_data.get("url")})

        try:
            result = await generate_video_clip(
                hero_image_bytes=None,
                caption=caption,
                brand_profile=brand,
                platform=_platform,
                post_id=post_id,
                tier=tier,
                edit_prompt=body.edit_prompt,
            )
        except Exception as e:
            import traceback
            logger.error("edit_post_media video regen failed for post %s: %s\n%s", post_id, e, traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Video re-generation failed: {e}")

        new_edit_count = edit_count + 1
        new_edit_history = post.get("edit_history", []) + [body.edit_prompt]
        await firestore_client.update_post(brand_id, post_id, {
            "video": {
                **video_data,
                "url": result["video_url"],
                "video_gcs_uri": result["video_gcs_uri"],
            },
            "video_url": result["video_url"],
            "edit_count": new_edit_count,
            "edit_history": new_edit_history[-10:],
        })
        return {"image_url": result["video_url"], "edit_count": new_edit_count}

    # Snapshot original on first edit
    if edit_count == 0:
        original_key = "original_thumbnail_gcs_uri" if body.target == "thumbnail" else "original_image_gcs_uri"
        if not post.get(original_key):
            await firestore_client.update_post(brand_id, post_id, {original_key: gcs_uri})

    # Get edit history for context
    edit_history = post.get("edit_history", [])

    # Call image editor
    from backend.agents.image_editor import edit_image
    from backend.platforms import get as get_platform
    gcs_bucket = os.environ.get("GCS_BUCKET_NAME", GCS_BUCKET_NAME)

    # Resolve platform aspect ratio for the edit hint
    _platform = post.get("platform", "instagram")
    _derivative = post.get("derivative_type", "")
    _DERIVATIVE_ASPECTS: dict[str, str] = {"story": "9:16", "pin": "2:3", "blog_snippet": "1.91:1"}
    _aspect = _DERIVATIVE_ASPECTS.get(_derivative, get_platform(_platform).image_aspect)

    try:
        new_gcs_uri = await edit_image(
            image_gcs_uri=gcs_uri,
            edit_prompt=body.edit_prompt,
            brand_profile=brand,
            edit_history=edit_history,
            gcs_bucket=gcs_bucket,
            gemini_client=_live_client,
            aspect_ratio=_aspect,
            platform=_platform,
        )
    except Exception as e:
        import traceback
        logger.error("edit_post_media failed for post %s: %s\n%s", post_id, e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Image editing failed: {e}")

    # Update Firestore
    new_edit_count = edit_count + 1
    new_edit_history = edit_history + [body.edit_prompt]
    update_data: dict = {
        "edit_count": new_edit_count,
        "edit_history": new_edit_history[-10:],  # keep last 10
    }
    if body.target == "thumbnail":
        update_data["thumbnail_gcs_uri"] = new_gcs_uri
    elif body.slide_index is not None:
        image_uris = list(post.get("image_gcs_uris", []))
        if body.slide_index < len(image_uris):
            image_uris[body.slide_index] = new_gcs_uri
        update_data["image_gcs_uris"] = image_uris
    else:
        update_data["image_gcs_uri"] = new_gcs_uri

    await firestore_client.update_post(brand_id, post_id, update_data)

    # Return signed URL for frontend
    signed_url = await get_signed_url(new_gcs_uri)
    return {"image_url": signed_url, "edit_count": new_edit_count}


@app.post("/api/brands/{brand_id}/posts/{post_id}/edit-media/reset")
async def reset_post_media(brand_id: str, post_id: str, target: str | None = None):
    """Reset a post's image to the original pre-edit version."""
    post = await firestore_client.get_post(brand_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if target == "thumbnail":
        original_uri = post.get("original_thumbnail_gcs_uri")
        if not original_uri:
            raise HTTPException(status_code=422, detail="No original thumbnail to restore")
        await firestore_client.update_post(brand_id, post_id, {
            "thumbnail_gcs_uri": original_uri,
            "edit_count": 0,
            "edit_history": [],
        })
        signed_url = await get_signed_url(original_uri)
    else:
        original_uri = post.get("original_image_gcs_uri")
        if not original_uri:
            raise HTTPException(status_code=422, detail="No original image to restore")
        await firestore_client.update_post(brand_id, post_id, {
            "image_gcs_uri": original_uri,
            "edit_count": 0,
            "edit_history": [],
        })
        signed_url = await get_signed_url(original_uri)

    return {"image_url": signed_url}


# ── Video Generation ──────────────────────────────────────────

from backend.agents.video_creator import generate_video_clip
import backend.services.budget_tracker as bt


async def _run_video_generation(
    job_id: str,
    post_id: str,
    brand_id: str,
    hero_image_bytes: bytes | None,
    post: dict,
    brand: dict,
    tier: str,
):
    """Background task that runs Veo generation and updates Firestore."""
    try:
        await firestore_client.update_video_job(job_id, "generating")
        result = await generate_video_clip(
            hero_image_bytes=hero_image_bytes,
            caption=post.get("caption", ""),
            brand_profile=brand,
            platform=post.get("platform", "instagram"),
            post_id=post_id,
            tier=tier,
        )
        bt.budget_tracker.record_video(tier)
        await firestore_client.update_video_job(job_id, "complete", result)
        # Also update the post with video metadata
        await firestore_client.update_post(brand_id, post_id, {
            "video": {
                "url": result["video_url"],
                "video_gcs_uri": result.get("video_gcs_uri"),
                "duration_seconds": 8,
                "model": result["model"],
                "job_id": job_id,
            }
        })
    except Exception as e:
        logger.error(f"Video generation failed for job {job_id}: {e}")
        await firestore_client.update_video_job(job_id, "failed", {"error": str(e)})


@app.post("/api/posts/{post_id}/generate-video")
async def start_video_generation(
    post_id: str,
    brand_id: str = Query(...),
    tier: str = Query("fast"),
):
    """Queue async Veo video generation for a post that has a hero image.

    Returns: {job_id, status: "processing", estimated_seconds: 150}
    """
    # Check budget
    if not bt.budget_tracker.can_generate_video():
        return JSONResponse(
            status_code=429,
            content={
                "error": "Video generation budget exhausted",
                "budget_status": bt.budget_tracker.get_status(),
            },
        )

    # Load post
    post = await firestore_client.get_post(brand_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Load brand
    brand = await firestore_client.get_brand(post.get("brand_id", brand_id))
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Download hero image from GCS (optional — video_first posts have no image)
    image_gcs_uri = post.get("image_gcs_uri")
    hero_image_bytes: bytes | None = None
    if image_gcs_uri:
        try:
            hero_image_bytes = await download_gcs_uri(image_gcs_uri)
        except Exception as e:
            logger.error("Failed to download hero image for post %s: %s", post_id, e)
            raise HTTPException(status_code=500, detail=f"Failed to fetch hero image: {e}")

    # Create job record in Firestore
    job_id = await firestore_client.create_video_job(post_id, tier)

    # Fire background task; store reference to prevent GC before completion
    _veo_task = asyncio.create_task(
        _run_video_generation(job_id, post_id, brand_id, hero_image_bytes, post, brand, tier)
    )
    _veo_task.add_done_callback(
        lambda t: t.exception() and logger.error(
            "Unhandled exception in video generation task for job %s: %s", job_id, t.exception()
        ) if not t.cancelled() else None
    )

    return {
        "job_id": job_id,
        "status": "processing",
        "estimated_seconds": 150,
    }


@app.get("/api/video-jobs/{job_id}")
async def get_video_job_status(job_id: str):
    """Poll video generation job status.

    Returns the job dict including result.video_url when complete.
    """
    job = await firestore_client.get_video_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    return job


# ── Video Repurposing ──────────────────────────────────────────

_MAX_VIDEO_BYTES = 500 * 1024 * 1024  # 500 MB


def _is_valid_video_header(data: bytes) -> bool:
    """Check first 20 bytes for MP4/MOV container magic (ftyp or moov box)."""
    return len(data) >= 12 and (b'ftyp' in data[4:12] or b'moov' in data[:20])


def _sanitize_repurpose_error(e: Exception) -> str:
    """Return a user-friendly error string without exposing internal paths/stderr."""
    if isinstance(e, TimeoutError):
        return "Processing timed out. Try uploading a shorter video (under 5 minutes)."
    if isinstance(e, RuntimeError) and "FFmpeg" in str(e):
        return "Video processing failed. Ensure your video file is valid and not corrupted."
    if isinstance(e, ValueError):
        return str(e)  # Already user-facing from the agent
    return "Video processing failed. Please try again."


async def _run_video_repurposing(
    job_id: str,
    brand_id: str,
    source_gcs_uri: str,
    brand: dict,
) -> None:
    """Background task: download source video, run Gemini analysis + FFmpeg, upload clips."""
    from backend.agents.video_repurpose_agent import analyze_and_repurpose
    from backend.services.storage_client import download_gcs_uri

    try:
        await firestore_client.update_repurpose_job(job_id, "processing")

        video_bytes = await download_gcs_uri(source_gcs_uri)

        # Infer MIME type from the stored GCS path extension
        mime_type = "video/quicktime" if source_gcs_uri.lower().endswith(".mov") else "video/mp4"
        raw_clips = await analyze_and_repurpose(video_bytes, brand, mime_type=mime_type)

        clips_out = []
        for clip in raw_clips:
            # Store only gcs_uri — signed URLs are generated fresh at query time
            gcs_uri = await upload_repurposed_clip(
                brand_id, job_id, clip["clip_bytes"], clip["filename"]
            )
            clips_out.append({
                "platform": clip["platform"],
                "duration_seconds": clip["duration_seconds"],
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "hook": clip["hook"],
                "suggested_caption": clip["suggested_caption"],
                "reason": clip["reason"],
                "content_theme": clip.get("content_theme", ""),
                "clip_gcs_uri": gcs_uri,
                "filename": clip["filename"],
            })

        await firestore_client.update_repurpose_job(job_id, "complete", clips=clips_out)
        logger.info("Video repurposing complete for job %s: %d clips", job_id, len(clips_out))

    except Exception as e:
        logger.exception("Video repurposing failed for job %s", job_id)
        await firestore_client.update_repurpose_job(
            job_id, "failed", error=_sanitize_repurpose_error(e)
        )


@app.post("/api/brands/{brand_id}/video-repurpose")
async def upload_video_for_repurpose(
    brand_id: str,
    file: UploadFile = File(...),
):
    """Upload a raw video (mp4/mov ≤ 500 MB) and start async clip extraction.

    Returns: {job_id, status: "queued"}
    """
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    filename = file.filename or "video.mp4"
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ("mp4", "mov"):
        raise HTTPException(status_code=400, detail="Only .mp4 and .mov files are accepted")

    video_bytes = await file.read()
    if len(video_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(video_bytes) > _MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="Video must be under 500 MB")
    if not _is_valid_video_header(video_bytes):
        raise HTTPException(status_code=400, detail="File does not appear to be a valid MP4/MOV video")

    # Generate job_id up front so it's consistent across GCS path + Firestore
    job_id = str(uuid.uuid4())
    source_gcs_uri = await upload_raw_video_source(brand_id, job_id, video_bytes, filename)
    await firestore_client.create_repurpose_job(brand_id, source_gcs_uri, filename, job_id)

    # Fire background processing task with done-callback for exception logging
    task = asyncio.create_task(
        _run_video_repurposing(job_id, brand_id, source_gcs_uri, brand)
    )
    task.add_done_callback(
        lambda t: t.exception() and logger.error(
            "Unhandled exception in repurpose task for job %s: %s", job_id, t.exception()
        ) if not t.cancelled() else None
    )

    return {"job_id": job_id, "status": "queued"}


@app.get("/api/video-repurpose-jobs/{job_id}")
async def get_video_repurpose_job(job_id: str, brand_id: str = Query(...)):
    """Poll video repurposing job status. Requires brand_id for ownership verification.

    Returns: {job_id, status, clips (with fresh clip_url), error}
    """
    job = await firestore_client.get_repurpose_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Repurpose job not found")
    if job.get("brand_id") != brand_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Strip internal-only fields before returning
    response = {k: v for k, v in job.items() if k not in ("source_gcs_uri",)}

    # Generate fresh signed URLs for completed clip GCS URIs (avoids 7-day expiry in Firestore)
    if job.get("status") == "complete":
        clips_with_urls = []
        for clip in job.get("clips", []):
            clip_out = dict(clip)
            gcs_uri = clip.get("clip_gcs_uri")
            if gcs_uri:
                try:
                    clip_out["clip_url"] = await get_signed_url(gcs_uri)
                except Exception:
                    clip_out["clip_url"] = None
            clips_with_urls.append(clip_out)
        response["clips"] = clips_with_urls

    return response


# ── Voice Coaching (Gemini Live API) ──────────────────────────

@app.websocket("/api/brands/{brand_id}/voice-coaching")
async def voice_coaching_ws(websocket: WebSocket, brand_id: str, context: str = ""):
    """Bidirectional voice coaching via Gemini Live API.

    Frontend sends PCM audio (16kHz, 16-bit, mono) as binary WebSocket frames.
    Backend proxies to Gemini Live and returns PCM audio responses (24kHz).

    Query params:
      context — optional conversation history from previous sessions for continuity

    Control messages sent to frontend:
      { "type": "connected" }            — session ready
      { "type": "transcript", "text" }  — AI text transcript (when available)
      { "type": "session_ended" }       — Gemini session ended naturally
      { "type": "error", "message" }    — fatal error
    """
    await websocket.accept()

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        await websocket.close(code=1008, reason="Brand not found")
        return

    system_prompt = build_coaching_prompt(brand)
    if context:
        system_prompt += (
            "\n\nCONVERSATION CONTINUITY:\n"
            "This is a continuation of a previous session. Here is what was discussed:\n"
            f"{context}\n"
            "Continue naturally from where the conversation left off. "
            "Do NOT re-introduce yourself — just pick up the thread."
        )
    config = _gtypes.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=_gtypes.Content(
            parts=[_gtypes.Part(text=system_prompt)]
        ),
        speech_config=_gtypes.SpeechConfig(
            voice_config=_gtypes.VoiceConfig(
                prebuilt_voice_config=_gtypes.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
    )

    try:
        async with _live_client.aio.live.connect(model=_LIVE_MODEL, config=config) as session:
            await websocket.send_json({"type": "connected"})

            async def recv_from_frontend():
                """Forward mic audio from browser → Gemini Live.

                Re-raises on non-disconnect errors so asyncio.wait propagates them.
                Normal return (WebSocketDisconnect) signals the session to end.
                """
                try:
                    while True:
                        msg = await websocket.receive()
                        raw = msg.get("bytes")
                        if raw:
                            await session.send(
                                input=_gtypes.LiveClientRealtimeInput(
                                    media_chunks=[
                                        _gtypes.Blob(
                                            data=raw,
                                            mime_type="audio/pcm;rate=16000",
                                        )
                                    ]
                                )
                            )
                except (WebSocketDisconnect, RuntimeError):
                    pass  # normal client close or stale socket — let the task return
                except Exception:
                    logger.exception("recv_from_frontend error for brand %s", brand_id)
                    raise

            async def recv_from_gemini():
                """Forward Gemini audio responses → browser."""
                try:
                    async for response in session.receive():
                        sc = getattr(response, "server_content", None)
                        if not sc:
                            continue

                        # Signal end-of-turn to frontend (so it knows AI finished speaking)
                        if getattr(sc, "turn_complete", False):
                            try:
                                await websocket.send_json({"type": "turn_complete"})
                            except Exception:
                                return

                        model_turn = getattr(sc, "model_turn", None)
                        if not model_turn:
                            continue
                        for part in model_turn.parts:
                            inline = getattr(part, "inline_data", None)
                            if inline and inline.data:
                                try:
                                    await websocket.send_bytes(inline.data)
                                except Exception:
                                    return
                            text = getattr(part, "text", None)
                            if text:
                                # Check if the AI signalled end of conversation
                                clean_text = text.replace("[END_SESSION]", "").strip()
                                try:
                                    if clean_text:
                                        await websocket.send_json(
                                            {"type": "transcript", "text": clean_text}
                                        )
                                    if "[END_SESSION]" in text:
                                        logger.info("AI ended voice session for brand %s", brand_id)
                                        await websocket.send_json({
                                            "type": "session_complete",
                                            "message": "Great chatting with you! Click Voice Coach anytime to pick up where we left off.",
                                        })
                                        return  # exit recv_from_gemini → triggers cleanup
                                except Exception:
                                    return
                except asyncio.CancelledError:
                    raise  # let the task framework handle cancellation
                except Exception:
                    logger.exception("recv_from_gemini error for brand %s", brand_id)
                    try:
                        await websocket.send_json(
                            {"type": "error", "message": "Voice session interrupted"}
                        )
                    except Exception:
                        pass

            # BUG-1 fix: use asyncio.wait(FIRST_COMPLETED) so that when either task
            # finishes (frontend disconnect or Gemini session end), the other is
            # explicitly cancelled — preventing zombie Gemini sessions.
            fe_task = asyncio.create_task(recv_from_frontend())
            gm_task = asyncio.create_task(recv_from_gemini())
            try:
                done, pending = await asyncio.wait(
                    [fe_task, gm_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                # If Gemini finished (not the frontend), notify client gracefully
                if gm_task in done and fe_task not in done:
                    logger.info("Gemini Live session ended for brand %s", brand_id)
                    try:
                        await websocket.send_json({
                            "type": "session_ended",
                            "message": "Voice coaching session complete. Click Voice Coach to start a new session.",
                        })
                    except Exception:
                        pass
            finally:
                for task in (fe_task, gm_task):
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except (asyncio.CancelledError, Exception):
                            pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Voice coaching error for brand %s: %s", brand_id, e)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ── Notion Integration ────────────────────────────────────────

@app.get("/api/brands/{brand_id}/integrations/notion/auth-url")
async def notion_auth_url(brand_id: str):
    """Return the Notion OAuth authorize URL for the user to visit."""
    from backend.config import NOTION_CLIENT_ID, NOTION_REDIRECT_URI

    if not NOTION_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Notion integration not configured")

    url = (
        f"https://api.notion.com/v1/oauth/authorize"
        f"?client_id={NOTION_CLIENT_ID}"
        f"&response_type=code"
        f"&owner=user"
        f"&redirect_uri={NOTION_REDIRECT_URI}"
        f"&state={brand_id}"
    )
    return {"auth_url": url}


@app.get("/api/integrations/notion/callback")
async def notion_callback(code: str = Query(...), state: str = Query(...)):
    """OAuth callback — exchange code for tokens, store on brand profile."""
    from backend.config import NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, NOTION_REDIRECT_URI
    from backend.services.notion_client import exchange_code

    brand_id = state
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    try:
        token_data = await exchange_code(code, NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, NOTION_REDIRECT_URI)
    except Exception as e:
        logger.error("Notion OAuth token exchange failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Notion authorization failed: {e}")

    # Store integration data on brand
    from datetime import datetime as _dt
    integrations = brand.get("integrations", {})
    integrations["notion"] = {
        "access_token": token_data.get("access_token"),
        "bot_id": token_data.get("bot_id"),
        "workspace_id": token_data.get("workspace_id"),
        "workspace_name": token_data.get("workspace_name", ""),
        "connected_at": _dt.utcnow().isoformat(),
    }
    await firestore_client.update_brand(brand_id, {"integrations": integrations})

    # Redirect to dashboard with success param
    return Response(
        status_code=302,
        headers={"Location": f"/dashboard/{brand_id}?notion=connected"},
    )


@app.post("/api/brands/{brand_id}/integrations/notion/disconnect")
async def notion_disconnect(brand_id: str):
    """Remove Notion integration from brand."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    integrations = brand.get("integrations", {})
    integrations.pop("notion", None)
    await firestore_client.update_brand(brand_id, {"integrations": integrations})
    return {"status": "disconnected"}


@app.get("/api/brands/{brand_id}/integrations/notion/databases")
async def notion_databases(brand_id: str):
    """List databases the Notion integration can access."""
    from backend.services.notion_client import search_databases

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    notion = brand.get("integrations", {}).get("notion")
    if not notion or not notion.get("access_token"):
        raise HTTPException(status_code=400, detail="Notion not connected")

    try:
        databases = await search_databases(notion["access_token"])
    except Exception as e:
        logger.error("Failed to list Notion databases: %s", e)
        raise HTTPException(status_code=502, detail=f"Could not fetch databases: {e}")

    return {"databases": databases}


@app.post("/api/brands/{brand_id}/integrations/notion/select-database")
async def notion_select_database(
    brand_id: str,
    database_id: str = Body(..., embed=True),
    database_name: str = Body("", embed=True),
):
    """Set the target Notion database for exports."""
    from backend.services.notion_client import ensure_database_schema

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    notion = brand.get("integrations", {}).get("notion")
    if not notion or not notion.get("access_token"):
        raise HTTPException(status_code=400, detail="Notion not connected")

    # Ensure database has the right columns
    try:
        await ensure_database_schema(notion["access_token"], database_id)
    except Exception as e:
        logger.warning("Could not update Notion database schema: %s", e)

    integrations = brand.get("integrations", {})
    integrations["notion"]["database_id"] = database_id
    integrations["notion"]["database_name"] = database_name
    await firestore_client.update_brand(brand_id, {"integrations": integrations})

    return {"status": "selected", "database_id": database_id}


@app.post("/api/brands/{brand_id}/plans/{plan_id}/export/notion")
async def export_plan_to_notion(brand_id: str, plan_id: str):
    """Export all posts from a plan to the connected Notion database."""
    from backend.services.notion_client import create_page

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    notion = brand.get("integrations", {}).get("notion")
    if not notion or not notion.get("access_token"):
        raise HTTPException(status_code=400, detail="Notion not connected")
    if not notion.get("database_id"):
        raise HTTPException(status_code=400, detail="No Notion database selected")

    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    posts = await firestore_client.list_posts(brand_id, plan_id)
    if not posts:
        raise HTTPException(status_code=404, detail="No posts found for this plan")

    # Get day briefs for theme info
    days = plan.get("days", [])
    day_lookup = {d.get("day_index", i): d for i, d in enumerate(days)}

    results = []
    access_token = notion["access_token"]
    database_id = notion["database_id"]

    for post in posts:
        post_id = post.get("post_id", "")
        day_index = post.get("day_index", 0)
        platform = post.get("platform", "instagram")

        # Merge theme from day brief into post for property building
        day_brief = day_lookup.get(day_index, {})
        post_with_theme = {**post, "theme": day_brief.get("theme", "")}
        if not post.get("content_type"):
            post_with_theme["content_type"] = day_brief.get("content_type", "photo")

        try:
            page = await create_page(access_token, database_id, post_with_theme, day_index, platform)
            notion_page_id = page.get("id", "")
            results.append({"post_id": post_id, "status": "exported", "notion_page_id": notion_page_id})

            # Update post's publish_status
            publish_status = post.get("publish_status", {}) or {}
            publish_status["notion"] = {
                "status": "exported",
                "notion_page_id": notion_page_id,
                "published_at": datetime.utcnow().isoformat(),
            }
            await firestore_client.update_post(brand_id, post_id, {"publish_status": publish_status})

        except Exception as e:
            logger.error("Failed to export post %s to Notion: %s", post_id, e)
            results.append({"post_id": post_id, "status": "failed", "error": str(e)})

    exported = sum(1 for r in results if r["status"] == "exported")
    return {
        "exported": exported,
        "total": len(posts),
        "results": results,
    }


# ── .ics Calendar — Download + Email ──────────────────────────

def _parse_posting_time(time_str: str) -> tuple[int, int]:
    """Parse posting_time like '9:00 AM', '2:30 PM' into (hour, minute) 24h."""
    m = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", time_str.strip(), re.IGNORECASE)
    if not m:
        return (9, 0)  # default 9 AM
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    return (hour, minute)


def _ics_escape(text: str) -> str:
    """Escape text for iCalendar DESCRIPTION field."""
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _build_ics(plan: dict, posts: list[dict], brand_name: str) -> str:
    """Build an .ics (iCalendar) string from a content plan and its posts."""
    days = plan.get("days", [])

    # Determine base date: plan created_at or today
    created = plan.get("created_at")
    if isinstance(created, datetime):
        base_date = created.date()
    elif isinstance(created, str):
        try:
            base_date = datetime.fromisoformat(created.replace("Z", "+00:00")).date()
        except Exception:
            base_date = datetime.utcnow().date()
    else:
        base_date = datetime.utcnow().date()

    # Build lookup: day_index -> day brief
    day_lookup = {d.get("day_index", i): d for i, d in enumerate(days)}

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Amplifi//Content Plan//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{brand_name} Content Plan",
    ]

    for post in posts:
        post_id = post.get("post_id", uuid.uuid4().hex[:8])
        day_index = post.get("day_index", 0)
        platform = post.get("platform", "post")
        caption = post.get("caption", "")
        hashtags = post.get("hashtags", [])
        posting_time = post.get("posting_time", "")

        # Get theme from day brief
        day_brief = day_lookup.get(day_index, {})
        theme = day_brief.get("theme", day_brief.get("content_theme", ""))

        # Parse posting time
        if not posting_time:
            posting_time = day_brief.get("posting_time", "9:00 AM")
        hour, minute = _parse_posting_time(posting_time)

        # Event date
        event_date = base_date + timedelta(days=day_index)
        dt_start = datetime(event_date.year, event_date.month, event_date.day, hour, minute)
        dt_end = dt_start + timedelta(minutes=30)

        # Summary
        platform_display = platform.capitalize()
        summary = f"{platform_display} - {theme}" if theme else platform_display

        # Description
        desc_parts = [caption]
        if hashtags:
            tags = " ".join(f"#{h.lstrip('#')}" for h in hashtags)
            desc_parts.append(tags)
        description = _ics_escape("\n\n".join(desc_parts))

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:post_{post_id}@amplifi",
            f"DTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{_ics_escape(summary)}",
            f"DESCRIPTION:{description}",
            f"CATEGORIES:{platform}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


@app.get("/api/brands/{brand_id}/plans/{plan_id}/calendar.ics")
async def download_calendar_ics(brand_id: str, plan_id: str):
    """Download the content plan as an .ics calendar file."""
    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    posts = await firestore_client.list_posts(brand_id, plan_id)
    if not posts:
        raise HTTPException(status_code=404, detail="No posts found for this plan")

    brand_name = brand.get("business_name", "My Brand")
    ics_content = _build_ics(plan, posts, brand_name)

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": "attachment; filename=amplifi_content_plan.ics",
        },
    )


@app.post("/api/brands/{brand_id}/plans/{plan_id}/calendar/email")
async def email_calendar(
    brand_id: str,
    plan_id: str,
    email: str = Body(..., embed=True),
):
    """Email the content plan .ics file to the specified address."""
    from backend.services.email_client import send_calendar_email

    brand = await firestore_client.get_brand(brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    posts = await firestore_client.list_posts(brand_id, plan_id)
    if not posts:
        raise HTTPException(status_code=404, detail="No posts found for this plan")

    brand_name = brand.get("business_name", "My Brand")
    ics_content = _build_ics(plan, posts, brand_name)

    try:
        await send_calendar_email(email, brand_name, ics_content)
    except Exception as e:
        logger.error("Failed to send calendar email to %s: %s", email, e)
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")

    return {"status": "sent", "to": email}


# ── Static frontend (production) ──────────────────────────────
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    from starlette.responses import FileResponse as _FileResponse

    _index_html = os.path.join(frontend_dist, "index.html")

    # SPA catch-all: serve index.html for any non-API, non-file route
    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        # If a real file exists, serve it (JS, CSS, images, etc.)
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return _FileResponse(file_path)
        # Otherwise serve index.html so the SPA router handles it
        return _FileResponse(_index_html)

    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
