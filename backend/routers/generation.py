import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Query

# Strong references to background tasks to prevent GC before completion
_background_tasks: set[asyncio.Task] = set()
from sse_starlette.sse import EventSourceResponse

from backend.agents.content_creator import generate_post
from backend.services import firestore_client
from backend.services.storage_client import download_gcs_uri

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/generate/{plan_id}/{day_index}")
async def stream_generate(
    plan_id: str,
    day_index: int,
    brand_id: str = Query(...),
    instructions: str | None = Query(None),
    image_style: str | None = Query(None),
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
            except Exception as e:
                logger.warning("Best-effort cleanup failed for post %s: %s", ep.get("post_id"), e)

    # Extract prior hooks from already-generated posts for deduplication
    prior_hooks = [
        p.get("caption", "").split("\n")[0][:100]
        for p in existing_posts
        if p.get("status") in ("complete", "approved") and p.get("caption")
        and not (p.get("brief_index") == day_index and p.get("platform", "") == brief_platform)
    ]

    # Create a pending post record in Firestore.
    post_id = await firestore_client.save_post(brand_id, plan_id, {
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
                    image_style_key=image_style,
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
                            "content_theme": day_brief.get("content_theme", ""),
                            "pillar": day_brief.get("pillar", ""),
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
                # Gate Veo on review score -- skip if caption quality < 7
                _veo_gate_score = (gate_review or {}).get("score", 0) if gate_review else 0
                if _veo_gate_score < 7:
                    logger.warning("Skipping Veo -- review score %d < 7 for video_first post %s",
                                   _veo_gate_score, post_id)
                    await event_queue.put({
                        "event": "video_error",
                        "data": {"message": f"Video skipped -- caption scored {_veo_gate_score}/10. Regenerate for a higher-quality result."},
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
                            content_theme=day_brief.get("content_theme", ""),
                            pillar=day_brief.get("pillar", ""),
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
                                "audio_note": "Add trending audio before publishing -- silent video underperforms on this platform.",
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
            except Exception as e:
                logger.warning("Failed to mark post %s as failed: %s", post_id, e)
            await event_queue.put({"event": "error", "data": {"message": str(exc)}})
        finally:
            await event_queue.put(None)  # sentinel: end of stream

    gen_task = asyncio.create_task(_run_generation())
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
