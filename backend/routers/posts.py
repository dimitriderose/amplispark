import asyncio
import io
import json
import logging
import re
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Body
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel as _PydanticBaseModel

from backend.gcs_utils import parse_gcs_uri
from backend.services import firestore_client
from backend.services.storage_client import get_signed_url, get_bucket

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────

async def _refresh_signed_urls(post: dict) -> dict:
    """Re-sign expired GCS URLs so images always load."""
    gcs_uri = post.get("image_gcs_uri")
    if gcs_uri:
        try:
            post["image_url"] = await get_signed_url(gcs_uri)
        except Exception as e:
            logger.warning("Failed to re-sign image URL for %s: %s", post.get("post_id"), e)
    for i, uri in enumerate(post.get("image_gcs_uris") or []):
        try:
            urls = post.setdefault("image_urls", [])
            signed = await get_signed_url(uri)
            if i < len(urls):
                urls[i] = signed
            else:
                urls.append(signed)
        except Exception as e:
            logger.warning("Failed to re-sign image URL index %d for %s: %s", i, post.get("post_id"), e)
    if post.get("thumbnail_gcs_uri"):
        try:
            post["thumbnail_url"] = await get_signed_url(post["thumbnail_gcs_uri"])
        except Exception as e:
            logger.warning("Failed to re-sign thumbnail URL for %s: %s", post.get("post_id"), e)
    return post


async def _auto_fail_stale_generating(post: dict, brand_id: str) -> None:
    """If a post has been stuck at 'generating' for >10 min, mark it as failed."""
    if post.get("status") != "generating":
        return
    created = post.get("created_at")
    if created:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
    if created and (datetime.now(timezone.utc) - created) > timedelta(minutes=10):
        post["status"] = "failed"
        post_id = post.get("post_id")
        if post_id:
            try:
                await firestore_client.update_post(brand_id, post_id, {"status": "failed"})
            except Exception as e:
                logger.warning("Failed to auto-fail stale post %s: %s", post_id, e)


# ── Pydantic models ──────────────────────────────────────────

class PatchPostBody(_PydanticBaseModel):
    caption: str | None = None
    hashtags: list[str] | None = None


# ── Endpoints ────────────────────────────────────────────────

@router.get("/posts")
async def list_posts_endpoint(
    brand_id: str = Query(...),
    plan_id: str | None = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    """List all posts for a brand, optionally filtered by plan."""
    posts = await firestore_client.list_posts(brand_id, plan_id)

    # Batch-update stale "generating" posts instead of N+1 individual writes
    stale_ids = []
    for post in posts:
        if post.get("status") != "generating":
            continue
        created = post.get("created_at")
        if created:
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        if created and (datetime.now(timezone.utc) - created) > timedelta(minutes=10):
            post_id = post.get("post_id")
            if post_id:
                stale_ids.append(post_id)
                post["status"] = "failed"  # update in-memory
    if stale_ids:
        await asyncio.gather(*[
            firestore_client.update_post(brand_id, pid, {"status": "failed"})
            for pid in stale_ids
        ])

    posts = posts[offset:offset + limit]
    await asyncio.gather(*[_refresh_signed_urls(p) for p in posts])
    return {"posts": posts}


@router.get("/posts/{post_id}")
async def get_post_endpoint(
    post_id: str,
    brand_id: str = Query(...),
):
    """Return a single post by ID."""
    post = await firestore_client.get_post(brand_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await _auto_fail_stale_generating(post, brand_id)
    await _refresh_signed_urls(post)
    return post


@router.get("/posts/{post_id}/export")
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
        try:
            blob_path = parse_gcs_uri(uri)
        except ValueError:
            return None
        try:
            blob = get_bucket().blob(blob_path)
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


@router.post("/export/{plan_id}")
async def export_plan_zip(
    plan_id: str,
    brand_id: str = Query(..., description="Brand ID that owns the plan"),
):
    """Build and stream a ZIP archive containing all posts for a content plan."""
    # Fetch plan to confirm it exists
    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # List all posts belonging to this plan
    posts: list[dict] = await firestore_client.list_posts(brand_id, plan_id)
    if not posts:
        raise HTTPException(status_code=404, detail="No posts found for this plan")

    _IMAGE_SIZE_WARN = 50 * 1024 * 1024   # 50 MB
    _VIDEO_SIZE_LIMIT = 100 * 1024 * 1024  # 100 MB

    # Download image bytes directly from GCS
    async def _download_post_image(post: dict) -> bytes | None:
        gcs_uri: str | None = post.get("image_gcs_uri")
        if not gcs_uri:
            return None
        try:
            blob_path = parse_gcs_uri(gcs_uri)
        except ValueError:
            return None
        try:
            bucket = get_bucket()
            blob = bucket.blob(blob_path)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, blob.reload)
            if blob.size and blob.size > _IMAGE_SIZE_WARN:
                logger.warning(
                    "Image blob for post %s is very large (%d bytes)",
                    post.get("post_id"), blob.size,
                )
            return await loop.run_in_executor(None, blob.download_as_bytes)
        except Exception as exc:
            logger.warning("Could not download image for post %s: %s", post.get("post_id"), exc)
            return None

    # Download video bytes directly from GCS
    async def _download_post_video(post: dict) -> bytes | None:
        video = post.get("video")
        if not video:
            return None
        gcs_uri: str | None = video.get("video_gcs_uri")
        if not gcs_uri:
            return None
        try:
            blob_path = parse_gcs_uri(gcs_uri)
        except ValueError:
            return None
        try:
            bucket = get_bucket()
            blob = bucket.blob(blob_path)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, blob.reload)
            if blob.size and blob.size > _VIDEO_SIZE_LIMIT:
                logger.warning(
                    "Video blob for post %s exceeds 100 MB (%d bytes), skipping download",
                    post.get("post_id"), blob.size,
                )
                return None
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

    # Build ZIP in memory
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

            # Image file -- detect PNG vs JPEG by magic bytes
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

            # Collect metadata (safe copy -- omit internal GCS URIs)
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


@router.patch("/brands/{brand_id}/posts/{post_id}")
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


@router.post("/brands/{brand_id}/posts/{post_id}/review")
async def review_post_endpoint(brand_id: str, post_id: str, force: bool = Query(False)):
    """AI-review a generated post against brand guidelines."""
    from backend.agents.review_agent import review_post as _run_review

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
        from backend.agents.hashtag_engine import _sanitize_hashtags
        platform = post.get("platform", "instagram")
        cleaned = _sanitize_hashtags(result["revised_hashtags"], platform)
        await firestore_client.update_post(brand_id, post_id, {
            "hashtags": cleaned,
        })

    return {"review": result, "post_id": post_id}


@router.post("/brands/{brand_id}/posts/{post_id}/approve")
async def approve_post_endpoint(brand_id: str, post_id: str):
    """Manually approve a post (user override)."""
    post = await firestore_client.get_post(brand_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await firestore_client.update_post(brand_id, post_id, {"status": "approved"})
    return {"status": "approved", "post_id": post_id}


@router.post("/brands/{brand_id}/posts/{post_id}/regenerate")
async def regenerate_post(brand_id: str, post_id: str):
    """Delete a failed/stuck post and return the generate URL so the frontend can retry."""
    post = await firestore_client.get_post(brand_id, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    status = post.get("status", "")
    if status not in ("failed", "generating"):
        raise HTTPException(status_code=409, detail="Only failed or stuck posts can be regenerated")
    plan_id = post.get("plan_id")
    day_index = post.get("day_index")
    if plan_id is None or day_index is None:
        raise HTTPException(status_code=422, detail="Post is missing plan_id or day_index")
    await firestore_client.delete_post(brand_id, post_id)
    return {
        "generate_url": f"/generate/{plan_id}/{day_index}?brand_id={brand_id}"
    }


# ── .ics Calendar helpers ────────────────────────────────────

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


def _ics_fold_line(line: str) -> str:
    """Fold a single iCalendar content line at 75 octets per RFC 5545 Section 3.1.

    Long lines are split with CRLF followed by a single space continuation character.
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    parts: list[str] = []
    while len(encoded) > 75:
        # First chunk is 75 bytes, continuations are 74 (the space counts as 1)
        cut = 75 if not parts else 74
        # Don't split in the middle of a multi-byte UTF-8 sequence
        chunk = encoded[:cut]
        while cut > 1 and (encoded[cut - 1] & 0xC0) == 0x80:
            cut -= 1
            chunk = encoded[:cut]
        if cut == 0:
            cut = 1
            chunk = encoded[:cut]
        parts.append(chunk.decode("utf-8", errors="replace"))
        encoded = encoded[cut:]
    if encoded:
        parts.append(encoded.decode("utf-8"))
    return "\r\n ".join(parts)


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
        except Exception as e:
            logger.warning("Failed to parse plan created_at date %r: %s", created, e)
            base_date = datetime.now(timezone.utc).date()
    else:
        base_date = datetime.now(timezone.utc).date()

    # Build lookup: day_index -> day brief
    day_lookup = {d.get("day_index", i): d for i, d in enumerate(days)}

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Amplispark//Content Plan//EN",
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
            _ics_fold_line(f"SUMMARY:{_ics_escape(summary)}"),
            _ics_fold_line(f"DESCRIPTION:{description}"),
            f"CATEGORIES:{platform}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


@router.get("/brands/{brand_id}/plans/{plan_id}/calendar.ics")
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


_EMAIL_RE = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$')


@router.post("/brands/{brand_id}/plans/{plan_id}/calendar/email")
async def email_calendar(
    brand_id: str,
    plan_id: str,
    email: str = Body(..., embed=True),
):
    """Email the content plan .ics file to the specified address."""
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email address format")

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
        raise HTTPException(status_code=500, detail="Internal server error")

    return {"status": "sent", "to": email}
