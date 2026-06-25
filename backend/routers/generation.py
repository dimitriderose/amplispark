import asyncio
import json
import logging
import time

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from backend.agents.content_creator import generate_post
from backend.agents.video_creator import generate_video_clip
from backend.constants import DERIVATIVE_TYPES
from backend.platforms import keys as platform_keys
from backend.services import firestore_client
from backend.services.rate_limiter import veo_limit
from backend.services.storage_client import download_gcs_uri

logger = logging.getLogger(__name__)

# Valid platform keys — sourced from the Platform Registry so both paths stay in sync.
# Used to validate the ?platform= query param on the adhoc endpoint before it reaches
# Firestore or the AI prompt.
_VALID_PLATFORMS: frozenset[str] = frozenset(platform_keys())

# Valid derivative/content types — sourced from constants (single source of truth shared
# with strategy_agent.py).  Used to validate ?content_type= on the adhoc endpoint.
_VALID_CONTENT_TYPES: frozenset[str] = frozenset(DERIVATIVE_TYPES)

# Strong references to background tasks to prevent GC before completion
_background_tasks: set[asyncio.Task] = set()

# In-memory cache for brand profiles during generation (30s TTL).
# Each Cloud Run worker maintains its own cache — this is fine for correctness since the
# cache is a performance optimisation only.  Stale brand data resolves within 30 seconds.
_brand_cache: dict[str, tuple[dict, float]] = {}

router = APIRouter()


async def _run_generation_task(
    brand_id: str,
    post_id: str,
    day_brief: dict,
    brand: dict,
    event_queue: asyncio.Queue,
    custom_photo_bytes: bytes | None,
    custom_photo_mime: str,
    instructions: str | None,
    prior_hooks: list,
    image_style: str | None,
    existing_images: dict | None,
) -> None:
    final_caption = ""
    final_hashtags: list = []
    final_image_url = None
    final_image_gcs_uri = None
    gate_review = None
    _gen_start = time.time()

    # Extract plan_id from day_brief if present (for generate_post call).
    # "_plan_id" is a private sentinel key injected by the two SSE endpoints before
    # passing day_brief into this shared helper.  It is never stored in Firestore — it
    # only tells generate_post() which plan the post belongs to ("adhoc" for quick posts).
    # The underscore prefix signals "not a real Firestore field"; do not add this key to
    # any Firestore document.
    plan_id = day_brief.get("_plan_id", "adhoc")

    try:
        # Heartbeat: sends "Still working..." every 15s if no events flowed
        _loop = asyncio.get_running_loop()
        _last_event_time = _loop.time()

        async def _gen_heartbeat():
            nonlocal _last_event_time
            while True:
                await asyncio.sleep(15)
                if asyncio.get_running_loop().time() - _last_event_time > 12:
                    try:
                        event_queue.put_nowait(
                            {
                                "event": "status",
                                "data": {"message": "Still working..."},
                            }
                        )
                    except asyncio.QueueFull:
                        logger.warning("SSE event queue full, dropping event")

        gen_hb = asyncio.create_task(_gen_heartbeat())
        try:
            async for event in generate_post(
                plan_id,
                day_brief,
                brand,
                post_id,
                custom_photo_bytes=custom_photo_bytes,
                custom_photo_mime=custom_photo_mime,
                instructions=instructions,
                prior_hooks=prior_hooks,
                image_style_key=image_style,
                existing_images=existing_images,
            ):
                _last_event_time = asyncio.get_running_loop().time()
                event_name = event["event"]
                event_data = event["data"]

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

                    update_data: dict = {
                        "status": "complete",
                        "caption": final_caption,
                        "hashtags": final_hashtags,
                        "image_url": final_image_url,
                        "content_theme": day_brief.get("content_theme", ""),
                        "pillar": day_brief.get("pillar", ""),
                    }
                    if final_image_gcs_uri:
                        update_data["image_gcs_uri"] = final_image_gcs_uri
                    carousel_urls = event_data.get("image_urls", [])
                    carousel_gcs = event_data.get("image_gcs_uris", [])
                    if carousel_urls:
                        update_data["image_urls"] = carousel_urls
                    if carousel_gcs:
                        update_data["image_gcs_uris"] = carousel_gcs
                    gate_review = event_data.get("review")
                    if gate_review:
                        update_data["review"] = gate_review
                    try:
                        await firestore_client.update_post(brand_id, post_id, update_data)
                    except Exception as fs_err:
                        logger.error("Firestore update failed for post %s: %s", post_id, fs_err)
                    logger.info(
                        "metric",
                        extra={
                            "metric_name": "generation_complete",
                            "duration_ms": round((time.time() - _gen_start) * 1000),
                            "platform": day_brief.get("platform", "unknown"),
                            "derivative_type": day_brief.get("derivative_type", "original"),
                            "post_id": post_id,
                            "brand_id": brand_id,
                        },
                    )
                elif event_name == "error":
                    try:
                        await firestore_client.update_post(brand_id, post_id, {"status": "failed"})
                    except Exception as fs_err:
                        logger.error(
                            "Firestore error-update failed for post %s: %s", post_id, fs_err
                        )

                try:
                    event_queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("SSE event queue full, dropping event")
        finally:
            gen_hb.cancel()

        if day_brief.get("derivative_type") == "video_first" and final_caption:
            # Gate Veo on review score -- skip if caption quality < 7
            _veo_gate_score = (gate_review or {}).get("score", 0) if gate_review else 0
            if _veo_gate_score < 7:
                logger.warning(
                    "Skipping Veo -- review score %d < 7 for video_first post %s",
                    _veo_gate_score,
                    post_id,
                )
                try:
                    event_queue.put_nowait(
                        {
                            "event": "video_error",
                            "data": {
                                "message": f"Video skipped -- caption scored {_veo_gate_score}/10. Regenerate for a higher-quality result."
                            },
                        }
                    )
                except asyncio.QueueFull:
                    logger.warning("SSE event queue full, dropping event")
            else:
                try:
                    event_queue.put_nowait(
                        {"event": "status", "data": {"message": "Generating video..."}}
                    )
                except asyncio.QueueFull:
                    logger.warning("SSE event queue full, dropping event")

                # Heartbeat keeps SSE alive during long Veo generation (avg 2-5 min)
                async def _heartbeat():
                    while True:
                        await asyncio.sleep(15)
                        try:
                            event_queue.put_nowait(
                                {"event": "status", "data": {"message": "Generating video..."}}
                            )
                        except asyncio.QueueFull:
                            logger.warning("SSE event queue full, dropping event")

                heartbeat_task = asyncio.create_task(_heartbeat())
                try:
                    async with veo_limit:
                        video_result = await generate_video_clip(
                            hero_image_bytes=None,  # text-to-video
                            caption=final_caption,
                            brand_profile=brand,
                            platform=day_brief.get("platform", "instagram"),
                            post_id=post_id,
                            tier="fast",
                            content_theme=day_brief.get("content_theme", ""),
                            pillar=day_brief.get("pillar", ""),
                        )
                    await firestore_client.update_post(
                        brand_id,
                        post_id,
                        {
                            "video_url": video_result["video_url"],
                            "video": {
                                "url": video_result["video_url"],
                                "video_gcs_uri": video_result.get("video_gcs_uri"),
                                "duration_seconds": 8,
                                "model": video_result.get("model", "veo-3.1"),
                            },
                        },
                    )
                    try:
                        event_queue.put_nowait(
                            {
                                "event": "video_complete",
                                "data": {
                                    "video_url": video_result["video_url"],
                                    "video_gcs_uri": video_result.get("video_gcs_uri"),
                                    "audio_note": "Add trending audio before publishing -- silent video underperforms on this platform.",
                                },
                            }
                        )
                    except asyncio.QueueFull:
                        logger.warning("SSE event queue full, dropping event")
                except Exception as video_err:
                    logger.error(
                        "Video generation failed for video_first post %s: %s",
                        post_id,
                        video_err,
                    )
                    try:
                        event_queue.put_nowait(
                            {
                                "event": "video_error",
                                "data": {"message": str(video_err)},
                            }
                        )
                    except asyncio.QueueFull:
                        logger.warning("SSE event queue full, dropping event")
                finally:
                    heartbeat_task.cancel()

    except Exception as exc:
        logger.error("Generation task error for post %s: %s", post_id, exc)
        logger.info(
            "metric",
            extra={
                "metric_name": "generation_failed",
                "post_id": post_id,
                "brand_id": brand_id,
                "error": str(exc)[:200],
            },
        )
        try:
            await firestore_client.update_post(brand_id, post_id, {"status": "failed"})
        except Exception as e:
            logger.warning("Failed to mark post %s as failed: %s", post_id, e)
        try:
            event_queue.put_nowait({"event": "error", "data": {"message": str(exc)}})
        except asyncio.QueueFull:
            logger.warning("SSE event queue full, dropping event")
    finally:
        # Drain the queue if full (e.g. client disconnected) so the sentinel
        # always lands and the task can complete without blocking forever.
        while True:
            try:
                event_queue.put_nowait(None)  # sentinel: end of stream
                break
            except asyncio.QueueFull:
                # Consumer is gone — clear one slot and retry
                try:
                    event_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass


@router.get("/generate/quickpost/{brand_id}")
async def stream_generate_adhoc(
    brand_id: str,
    platform: str = Query(...),
    content_type: str | None = Query(None),
    # brief: user-supplied topic text.  Capped at 2000 chars to prevent prompt injection
    # via excessively large payloads (e.g. a 10 MB brief would exhaust Gemini context).
    brief: str | None = Query(None, max_length=2000),
    image_style: str | None = Query(None),
    instructions: str | None = Query(None, max_length=1000),
):
    """SSE endpoint: generate a quick (ad-hoc) post without a content plan."""

    # --- Input validation ---
    # Validate platform against the Platform Registry.  An unknown platform value stored
    # in Firestore could cause frontend rendering bugs (missing icons, aspect ratios, etc.)
    # and could inject unexpected strings into AI prompts.
    if platform not in _VALID_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown platform '{platform}'. Valid platforms: {sorted(_VALID_PLATFORMS)}",
        )

    # Validate content_type against the canonical DERIVATIVE_TYPES list.  An unknown value
    # stored in Firestore as derivative_type could cause mismatches in scoring weights and
    # platform-specific formatting logic.
    resolved_content_type = content_type or "original"
    if resolved_content_type not in _VALID_CONTENT_TYPES:
        logger.warning(
            "adhoc: unknown content_type '%s', falling back to 'original'",
            content_type,
        )
        resolved_content_type = "original"

    brand: dict | None = None
    if brand_id in _brand_cache and time.time() - _brand_cache[brand_id][1] < 30:
        brand = _brand_cache[brand_id][0]
    else:
        brand = await firestore_client.get_brand(brand_id)
        if brand:
            _brand_cache[brand_id] = (brand, time.time())
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    day_brief = {
        "platform": platform,
        "derivative_type": resolved_content_type,
        "content_theme": brief or "",
        "pillar": "",
        "format": resolved_content_type,
        "cta_type": None,
        "day_index": None,
        "_plan_id": "adhoc",
    }

    post_id = await firestore_client.save_post(
        brand_id,
        "adhoc",
        {
            "day_index": None,
            "brief_index": None,
            "platform": platform,
            "pillar": "",
            "content_theme": brief or "",
            "format": resolved_content_type,
            "cta_type": None,
            "derivative_type": resolved_content_type,
            "status": "generating",
            "caption": "",
            "hashtags": [],
            "image_url": None,
            "byop": False,
            "is_quick_post": True,
        },
    )

    event_queue: asyncio.Queue = asyncio.Queue(maxsize=200)

    gen_task = asyncio.create_task(
        _run_generation_task(
            brand_id=brand_id,
            post_id=post_id,
            day_brief=day_brief,
            brand=brand,
            event_queue=event_queue,
            custom_photo_bytes=None,
            custom_photo_mime="image/jpeg",
            instructions=instructions,
            prior_hooks=[],
            image_style=image_style,
            existing_images=None,
        )
    )
    _background_tasks.add(gen_task)
    gen_task.add_done_callback(_background_tasks.discard)

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
            # SSE closed (user navigated away) -- generation task keeps running
            pass

    return EventSourceResponse(event_stream())


@router.get("/generate/{plan_id}/{day_index}")
async def stream_generate(
    plan_id: str,
    day_index: int,
    brand_id: str = Query(...),
    instructions: str | None = Query(None),
    image_style: str | None = Query(None),
    regen_mode: str | None = Query(None),
):
    """SSE endpoint: streams interleaved caption + image generation events."""

    plan = await firestore_client.get_plan(plan_id, brand_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    days = plan.get("days", [])
    if day_index < 0 or day_index >= len(days):
        raise HTTPException(status_code=400, detail="day_index out of range")

    day_brief = days[day_index]

    brand: dict | None = None
    if brand_id in _brand_cache and time.time() - _brand_cache[brand_id][1] < 30:
        brand = _brand_cache[brand_id][0]
    else:
        brand = await firestore_client.get_brand(brand_id)
        if brand:
            _brand_cache[brand_id] = (brand, time.time())
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

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
    existing_images: dict | None = None
    for ep in existing_posts:
        if ep.get("brief_index") == day_index and ep.get("platform", "") == brief_platform:
            if regen_mode == "text_only":
                # Capture existing image fields for reuse, skip deletion
                existing_images = {
                    "image_url": ep.get("image_url"),
                    "image_gcs_uri": ep.get("image_gcs_uri"),
                    "image_urls": ep.get("image_urls", []),
                    "image_gcs_uris": ep.get("image_gcs_uris", []),
                }
                try:
                    await firestore_client.delete_post(brand_id, ep["post_id"])
                except Exception as e:
                    logger.warning(
                        "Best-effort cleanup failed for post %s: %s", ep.get("post_id"), e
                    )
            else:
                try:
                    await firestore_client.delete_post(brand_id, ep["post_id"])
                except Exception as e:
                    logger.warning(
                        "Best-effort cleanup failed for post %s: %s", ep.get("post_id"), e
                    )

    # Extract prior hooks from already-generated posts for deduplication
    prior_hooks = [
        p.get("caption", "").split("\n")[0][:100]
        for p in existing_posts
        if p.get("status") in ("complete", "approved")
        and p.get("caption")
        and not (p.get("brief_index") == day_index and p.get("platform", "") == brief_platform)
    ]

    post_id = await firestore_client.save_post(
        brand_id,
        plan_id,
        {
            "day_index": day_brief.get("day_index", day_index),
            "brief_index": day_index,
            "platform": day_brief.get("platform", "instagram"),
            "pillar": day_brief.get("pillar", ""),
            "content_theme": day_brief.get("content_theme", ""),
            "format": day_brief.get("format"),
            "cta_type": day_brief.get("cta_type"),
            "derivative_type": day_brief.get("derivative_type", "original"),
            "status": "generating",
            "caption": "",
            "hashtags": [],
            "image_url": None,
            "byop": custom_photo_bytes is not None,
        },
    )

    # Run generation as a background task so it completes (and saves to
    # Firestore) even if the user navigates away and the SSE stream closes.
    event_queue: asyncio.Queue = asyncio.Queue(maxsize=200)

    day_brief_with_plan = {**day_brief, "_plan_id": plan_id}

    gen_task = asyncio.create_task(
        _run_generation_task(
            brand_id=brand_id,
            post_id=post_id,
            day_brief=day_brief_with_plan,
            brand=brand,
            event_queue=event_queue,
            custom_photo_bytes=custom_photo_bytes,
            custom_photo_mime=custom_photo_mime,
            instructions=instructions,
            prior_hooks=prior_hooks,
            image_style=image_style,
            existing_images=existing_images,
        )
    )
    _background_tasks.add(gen_task)
    gen_task.add_done_callback(_background_tasks.discard)

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
            # SSE closed (user navigated away) -- generation task keeps running
            pass

    return EventSourceResponse(event_stream())
