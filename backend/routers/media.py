import asyncio
import logging
import os
import uuid
from typing import Optional

# Strong references to background tasks to prevent GC before completion
_background_tasks: set[asyncio.Task] = set()

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Body
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel as _PydanticBaseModel

from backend.config import GCS_BUCKET_NAME, GOOGLE_API_KEY
from backend.services import firestore_client
from backend.services.storage_client import (
    get_signed_url,
    download_gcs_uri,
    get_bucket,
    upload_raw_video_source,
    upload_repurposed_clip,
)
from backend.agents.video_creator import generate_video_clip
import backend.services.budget_tracker as bt

from google import genai as _genai

_live_client = _genai.Client(api_key=GOOGLE_API_KEY)

logger = logging.getLogger(__name__)

router = APIRouter()


class EditMediaBody(_PydanticBaseModel):
    edit_prompt: str
    slide_index: Optional[int] = None   # for carousel posts; None = main image
    target: Optional[str] = None        # "thumbnail" for video thumbnail editing


# ── GCS proxy (local dev) ────────────────────────────────────

@router.get("/storage/serve/{blob_path:path}")
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


# ── Image Editing ────────────────────────────────────────────

@router.post("/brands/{brand_id}/posts/{post_id}/edit-media")
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
                content_theme=post.get("content_theme", ""),
                pillar=post.get("pillar", ""),
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


@router.post("/brands/{brand_id}/posts/{post_id}/edit-media/reset")
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


# ── Video Generation ─────────────────────────────────────────

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
            content_theme=post.get("content_theme", ""),
            pillar=post.get("pillar", ""),
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


@router.post("/posts/{post_id}/generate-video")
async def start_video_generation(
    post_id: str,
    brand_id: str = Query(...),
    tier: str = Query("fast"),
):
    """Queue async Veo video generation for a post that has a hero image."""
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

    # Download hero image from GCS (optional -- video_first posts have no image)
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

    # Fire background task; store strong reference to prevent GC
    _veo_task = asyncio.create_task(
        _run_video_generation(job_id, post_id, brand_id, hero_image_bytes, post, brand, tier)
    )
    _background_tasks.add(_veo_task)
    _veo_task.add_done_callback(_background_tasks.discard)
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


@router.get("/video-jobs/{job_id}")
async def get_video_job_status(job_id: str):
    """Poll video generation job status."""
    job = await firestore_client.get_video_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    return job


# ── Video Repurposing ────────────────────────────────────────

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
    from backend.services.storage_client import download_gcs_uri as _download_gcs_uri

    try:
        await firestore_client.update_repurpose_job(job_id, "processing")

        video_bytes = await _download_gcs_uri(source_gcs_uri)

        # Infer MIME type from the stored GCS path extension
        mime_type = "video/quicktime" if source_gcs_uri.lower().endswith(".mov") else "video/mp4"
        raw_clips = await analyze_and_repurpose(video_bytes, brand, mime_type=mime_type)

        clips_out = []
        for clip in raw_clips:
            # Store only gcs_uri -- signed URLs are generated fresh at query time
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


@router.post("/brands/{brand_id}/video-repurpose")
async def upload_video_for_repurpose(
    brand_id: str,
    file: UploadFile = File(...),
):
    """Upload a raw video (mp4/mov <= 500 MB) and start async clip extraction."""
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

    # Fire background processing task; store strong reference to prevent GC
    task = asyncio.create_task(
        _run_video_repurposing(job_id, brand_id, source_gcs_uri, brand)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    task.add_done_callback(
        lambda t: t.exception() and logger.error(
            "Unhandled exception in repurpose task for job %s: %s", job_id, t.exception()
        ) if not t.cancelled() else None
    )

    return {"job_id": job_id, "status": "queued"}


@router.get("/video-repurpose-jobs/{job_id}")
async def get_video_repurpose_job(job_id: str, brand_id: str = Query(...)):
    """Poll video repurposing job status. Requires brand_id for ownership verification."""
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
                except Exception as e:
                    logger.warning("Failed to sign clip URL %s: %s", gcs_uri, e)
                    clip_out["clip_url"] = None
            clips_with_urls.append(clip_out)
        response["clips"] = clips_with_urls

    return response
