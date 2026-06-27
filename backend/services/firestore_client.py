import logging
import uuid
from datetime import UTC, datetime, timedelta

from google.cloud import firestore
from google.cloud.firestore_v1.async_client import AsyncClient
from google.cloud.firestore_v1.base_query import FieldFilter

from backend.config import GCP_PROJECT_ID

logger = logging.getLogger(__name__)

_client: AsyncClient | None = None


def get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = firestore.AsyncClient(project=GCP_PROJECT_ID)
    return _client


# ── Brand operations ──────────────────────────────────────────


async def create_brand(data: dict) -> str:
    db = get_client()
    brand_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    doc = {
        **data,
        "brand_id": brand_id,
        "analysis_status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    await db.collection("brands").document(brand_id).set(doc)
    return brand_id


async def get_brand(brand_id: str) -> dict | None:
    db = get_client()
    doc = await db.collection("brands").document(brand_id).get()
    return doc.to_dict() if doc.exists else None


async def list_brands_by_owner(owner_uid: str) -> list:
    """Return all brands owned by a given UID, newest first."""
    logger.info("list_brands_by_owner: fetching brands for owner_uid=%s", owner_uid)
    db = get_client()
    try:
        docs = await (
            db.collection("brands")
            .where(filter=FieldFilter("owner_uid", "==", owner_uid))
            .order_by("created_at", direction="DESCENDING")
            .get()
        )
        brands = [d for d in (doc.to_dict() for doc in docs) if d is not None]
        brands.sort(
            key=lambda b: b.get("created_at") or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return brands
    except Exception as exc:
        exc_type = type(exc).__name__
        is_missing_index = (
            "FailedPrecondition" in exc_type or "failed precondition" in str(exc).lower()
        )
        if is_missing_index:
            logger.warning(
                "list_brands_by_owner: composite index missing for owner_uid=%s — "
                "returning []. Create index: owner_uid ASC, created_at DESC. (%s)",
                owner_uid,
                exc,
            )
            return []
        logger.error(
            "list_brands_by_owner: unexpected error for owner_uid=%s (%s: %s)",
            owner_uid,
            exc_type,
            exc,
        )
        raise


async def claim_brand(brand_id: str, owner_uid: str) -> bool:
    """Assign an owner to an unclaimed brand. Returns True if claimed.

    Uses a Firestore transaction to prevent TOCTOU race conditions where
    two concurrent requests could both read the brand as unclaimed.
    """
    db = get_client()
    doc_ref = db.collection("brands").document(brand_id)

    @firestore.async_transactional
    async def _claim_in_txn(txn, ref):
        doc = await ref.get(transaction=txn)
        if not doc.exists:
            return False
        data = doc.to_dict()
        if data.get("owner_uid"):
            return data["owner_uid"] == owner_uid
        txn.update(
            ref,
            {
                "owner_uid": owner_uid,
                "updated_at": datetime.now(UTC),
            },
        )
        return True

    txn = db.transaction()
    return await _claim_in_txn(txn, doc_ref)


async def update_brand(brand_id: str, data: dict) -> None:
    db = get_client()
    await (
        db.collection("brands")
        .document(brand_id)
        .update(
            {
                **data,
                "updated_at": datetime.now(UTC),
            }
        )
    )


async def remove_brand_asset(brand_id: str, asset_index: int) -> dict | None:
    """Remove an asset from uploaded_assets by index. Returns the removed asset or None."""
    db = get_client()
    doc_ref = db.collection("brands").document(brand_id)
    doc = await doc_ref.get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    if data is None:
        return None
    assets = data.get("uploaded_assets", [])
    if asset_index < 0 or asset_index >= len(assets):
        return None
    removed = assets.pop(asset_index)
    await doc_ref.update(
        {
            "uploaded_assets": assets,
            "updated_at": datetime.now(UTC),
        }
    )
    return removed


# ── Content plan operations ───────────────────────────────────


async def create_plan(brand_id: str, data: dict) -> str:
    db = get_client()
    plan_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    doc = {**data, "plan_id": plan_id, "brand_id": brand_id, "created_at": now}
    await (
        db.collection("brands")
        .document(brand_id)
        .collection("content_plans")
        .document(plan_id)
        .set(doc)
    )
    return plan_id


async def list_plans(brand_id: str) -> list:
    db = get_client()
    docs = await (
        db.collection("brands")
        .document(brand_id)
        .collection("content_plans")
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .get()
    )
    return [d for d in (doc.to_dict() for doc in docs) if d is not None]


async def get_plan(plan_id: str, brand_id: str) -> dict | None:
    db = get_client()
    doc = await (
        db.collection("brands")
        .document(brand_id)
        .collection("content_plans")
        .document(plan_id)
        .get()
    )
    return doc.to_dict() if doc.exists else None


async def update_plan(brand_id: str, plan_id: str, data: dict) -> None:
    db = get_client()
    await (
        db.collection("brands")
        .document(brand_id)
        .collection("content_plans")
        .document(plan_id)
        .update(data)
    )


async def update_plan_day(brand_id: str, plan_id: str, day_index: int, data: dict) -> None:
    db = get_client()
    plan_ref = (
        db.collection("brands").document(brand_id).collection("content_plans").document(plan_id)
    )
    plan_doc = await plan_ref.get()
    if not plan_doc.exists:
        raise ValueError(f"Plan {plan_id} not found for brand {brand_id}")
    days = list(plan_doc.to_dict().get("days", []))
    if day_index < 0 or day_index >= len(days):
        raise ValueError(f"day_index {day_index} out of range (plan has {len(days)} days)")
    days[day_index] = {**days[day_index], **data}
    await plan_ref.update({"days": days})


# ── Post operations ───────────────────────────────────────────


async def save_post(brand_id: str, plan_id: str, data: dict) -> str:
    db = get_client()
    post_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    doc = {
        **data,
        "post_id": post_id,
        "brand_id": brand_id,
        "plan_id": plan_id,
        "created_at": now,
        "updated_at": now,
    }
    await db.collection("brands").document(brand_id).collection("posts").document(post_id).set(doc)
    return post_id


async def get_post(brand_id: str, post_id: str) -> dict | None:
    db = get_client()
    doc = await (
        db.collection("brands").document(brand_id).collection("posts").document(post_id).get()
    )
    return doc.to_dict() if doc.exists else None


async def delete_post(brand_id: str, post_id: str) -> None:
    from datetime import datetime

    db = get_client()
    await (
        db.collection("brands")
        .document(brand_id)
        .collection("posts")
        .document(post_id)
        .update(
            {
                "status": "deleted",
                "deleted_at": datetime.now(UTC).isoformat(),
            }
        )
    )


async def update_post(brand_id: str, post_id: str, data: dict) -> None:
    db = get_client()
    await (
        db.collection("brands")
        .document(brand_id)
        .collection("posts")
        .document(post_id)
        .update(
            {
                **data,
                "updated_at": datetime.now(UTC),
            }
        )
    )


async def list_posts(brand_id: str, plan_id: str | None = None) -> list:
    db = get_client()
    ref = db.collection("brands").document(brand_id).collection("posts")
    if plan_id:
        ref = ref.where("plan_id", "==", plan_id)
    docs = await ref.get()
    posts = [d.to_dict() for d in docs]
    posts = [p for p in posts if p.get("status") != "deleted"]
    return posts


# ── Video job operations ──────────────────────────────────────


async def create_video_job(post_id: str, tier: str) -> str:
    db = get_client()
    job_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    await (
        db.collection("video_jobs")
        .document(job_id)
        .set(
            {
                "job_id": job_id,
                "post_id": post_id,
                "tier": tier,
                "status": "queued",
                "result": None,
                "error": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    )
    return job_id


async def update_video_job(job_id: str, status: str, result: dict | None = None) -> None:
    db = get_client()
    await (
        db.collection("video_jobs")
        .document(job_id)
        .update(
            {
                "status": status,
                "result": result,
                "updated_at": datetime.now(UTC),
            }
        )
    )


async def get_video_job(job_id: str) -> dict | None:
    db = get_client()
    doc = await db.collection("video_jobs").document(job_id).get()
    return doc.to_dict() if doc.exists else None


# ── Video repurpose job operations ────────────────────────────


async def create_repurpose_job(
    brand_id: str, source_gcs_uri: str, filename: str, job_id: str | None = None
) -> str:
    db = get_client()
    if not job_id:
        job_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    await (
        db.collection("repurpose_jobs")
        .document(job_id)
        .set(
            {
                "job_id": job_id,
                "brand_id": brand_id,
                "source_gcs_uri": source_gcs_uri,
                "filename": filename,
                "status": "queued",
                "clips": [],
                "error": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    )
    return job_id


async def update_repurpose_job(
    job_id: str,
    status: str,
    clips: list | None = None,
    error: str | None = None,
) -> None:
    db = get_client()
    now = datetime.now(UTC)
    payload: dict = {"status": status, "updated_at": now}
    if clips is not None:
        payload["clips"] = clips
    if error is not None:
        payload["error"] = error
    if status == "complete":
        payload["completed_at"] = now
    await db.collection("repurpose_jobs").document(job_id).update(payload)


async def get_repurpose_job(job_id: str) -> dict | None:
    db = get_client()
    doc = await db.collection("repurpose_jobs").document(job_id).get()
    return doc.to_dict() if doc.exists else None


async def save_review(brand_id: str, post_id: str, review: dict) -> None:
    db = get_client()
    await (
        db.collection("brands")
        .document(brand_id)
        .collection("posts")
        .document(post_id)
        .update(
            {
                "review": review,
                "updated_at": datetime.now(UTC),
            }
        )
    )


# ── Platform trends cache ──────────────────────────────────────


async def get_platform_trends(platform: str, industry: str) -> dict | None:
    """Return cached trend data for platform+industry if not expired (7-day TTL)."""
    db = get_client()
    doc_id = f"{platform}_{industry}".lower().replace(" ", "_")
    snap = await db.collection("platform_trends").document(doc_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict()
    if data is None:
        return None
    expires_at = data.get("expires_at")
    if expires_at:
        if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if datetime.now(UTC) > expires_at:
            return None
    return data.get("trends")


async def save_platform_trends(platform: str, industry: str, trends: dict) -> None:
    """Cache trend data for platform+industry with a 7-day TTL."""
    db = get_client()
    doc_id = f"{platform}_{industry}".lower().replace(" ", "_")
    now = datetime.now(UTC)
    await (
        db.collection("platform_trends")
        .document(doc_id)
        .set(
            {
                "trends": trends,
                "fetched_at": now,
                "expires_at": now + timedelta(days=7),
            }
        )
    )


# ── Platform recommendation cache ─────────────────────────────


async def get_platform_recommendations(industry: str, business_type: str) -> list | None:
    """Return cached platform recommendations if not expired (7-day TTL)."""
    db = get_client()
    doc_id = f"{industry}_{business_type}".lower().replace(" ", "_")
    snap = await db.collection("platform_recommendations").document(doc_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict()
    if data is None:
        return None
    expires_at = data.get("expires_at")
    if expires_at:
        if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if datetime.now(UTC) > expires_at:
            return None
    return data.get("recommendations")


async def save_platform_recommendations(
    industry: str, business_type: str, recommendations: list
) -> None:
    """Cache platform recommendations with a 7-day TTL."""
    db = get_client()
    doc_id = f"{industry}_{business_type}".lower().replace(" ", "_")
    now = datetime.now(UTC)
    await (
        db.collection("platform_recommendations")
        .document(doc_id)
        .set(
            {
                "recommendations": recommendations,
                "fetched_at": now,
                "expires_at": now + timedelta(days=7),
            }
        )
    )


# ── Posting frequency cache ───────────────────────────────────


async def get_posting_frequency(
    industry: str, business_type: str, platforms: list[str]
) -> dict | None:
    """Return cached posting frequency data if not expired (7-day TTL)."""
    db = get_client()
    plat_key = "_".join(sorted(platforms))
    doc_id = f"{industry}_{business_type}_{plat_key}".lower().replace(" ", "_")
    snap = await db.collection("posting_frequency").document(doc_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict()
    if data is None:
        return None
    expires_at = data.get("expires_at")
    if expires_at:
        if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if datetime.now(UTC) > expires_at:
            return None
    return data.get("frequency")


async def save_posting_frequency(
    industry: str, business_type: str, platforms: list[str], frequency: dict
) -> None:
    """Cache posting frequency with a 7-day TTL."""
    db = get_client()
    plat_key = "_".join(sorted(platforms))
    doc_id = f"{industry}_{business_type}_{plat_key}".lower().replace(" ", "_")
    now = datetime.now(UTC)
    await (
        db.collection("posting_frequency")
        .document(doc_id)
        .set(
            {
                "frequency": frequency,
                "platforms": platforms,
                "fetched_at": now,
                "expires_at": now + timedelta(days=7),
            }
        )
    )


# ── Notification operations ───────────────────────────────────


async def create_notification(uid: str, data: dict) -> str:
    db = get_client()
    notification_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    doc = {
        **data,
        "notification_id": notification_id,
        "uid": uid,
        "read": False,
        "created_at": now,
    }
    await (
        db.collection("users")
        .document(uid)
        .collection("notifications")
        .document(notification_id)
        .set(doc)
    )
    return notification_id


async def list_notifications(uid: str, limit: int = 10) -> list[dict]:
    db = get_client()
    docs = await (
        db.collection("users")
        .document(uid)
        .collection("notifications")
        .order_by("created_at", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .get()
    )
    return [d for d in (doc.to_dict() for doc in docs) if d is not None]


async def get_unread_count(uid: str) -> int:
    db = get_client()
    query = (
        db.collection("users")
        .document(uid)
        .collection("notifications")
        .where(filter=FieldFilter("read", "==", False))
    )
    try:
        result = await query.count().get()
        return result[0][0].value
    except Exception:
        docs = await query.select([]).get()
        return len(docs)


async def mark_notification_read(uid: str, notification_id: str) -> None:
    db = get_client()
    await (
        db.collection("users")
        .document(uid)
        .collection("notifications")
        .document(notification_id)
        .update({"read": True})
    )


async def mark_all_notifications_read(uid: str) -> int:
    db = get_client()
    docs = await (
        db.collection("users")
        .document(uid)
        .collection("notifications")
        .where(filter=FieldFilter("read", "==", False))
        .select([])
        .get()
    )
    if not docs:
        return 0
    _BATCH_LIMIT = 500
    for i in range(0, len(docs), _BATCH_LIMIT):
        batch = db.batch()
        for doc in docs[i : i + _BATCH_LIMIT]:
            batch.update(doc.reference, {"read": True})
        await batch.commit()
    return len(docs)


async def join_waitlist(email: str, source: str = "waitlist_page") -> bool:
    """Idempotent upsert using email as doc ID. Returns True if newly added.

    Transaction prevents duplicate writes when two concurrent requests race for the same email.
    """
    db = get_client()
    email_normalized = email.strip().lower()
    doc_ref = db.collection("waitlist").document(email_normalized)

    @firestore.async_transactional
    async def _join_in_txn(txn, ref):
        snap = await ref.get(transaction=txn)
        if snap.exists:
            return False
        txn.set(
            ref,
            {
                "email": email_normalized,
                "signed_up_at": datetime.now(UTC),
                "source": source,
            },
        )
        return True

    txn = db.transaction()
    return await _join_in_txn(txn, doc_ref)


async def get_user(uid: str) -> dict | None:
    db = get_client()
    doc = await db.collection("users").document(uid).get()
    return doc.to_dict() if doc.exists else None


async def get_or_create_user(uid: str, email: str | None = None) -> dict:
    db = get_client()
    ref = db.collection("users").document(uid)
    doc = await ref.get()
    if doc.exists:
        return doc.to_dict() or {}
    now = datetime.now(UTC)
    data = {
        "role": "beta",
        "email": email,
        "created_at": now,
        "updated_at": now,
        "beta_expires_at": None,
        "quick_posts_this_month": 0,
        "calendars_this_month": 0,
        "counters_reset_at": now,
    }
    await ref.set(data, merge=True)
    return data


async def increment_quick_posts(uid: str) -> dict:
    return await _increment_usage_counter(uid, "quick_posts_this_month")


async def increment_calendars(uid: str) -> dict:
    return await _increment_usage_counter(uid, "calendars_this_month")


async def _increment_usage_counter(uid: str, field: str) -> dict:
    db = get_client()
    ref = db.collection("users").document(uid)
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @firestore.async_transactional
    async def _txn(txn, ref):
        snap = await ref.get(transaction=txn)
        data = snap.to_dict() if snap.exists else {}
        counters_reset_at = data.get("counters_reset_at")
        if isinstance(counters_reset_at, datetime) and counters_reset_at.tzinfo is None:
            counters_reset_at = counters_reset_at.replace(tzinfo=UTC)
        needs_reset = not counters_reset_at or counters_reset_at < month_start
        if needs_reset:
            txn.set(
                ref,
                {
                    "quick_posts_this_month": 1 if field == "quick_posts_this_month" else 0,
                    "calendars_this_month": 1 if field == "calendars_this_month" else 0,
                    "counters_reset_at": month_start,
                    "updated_at": now,
                },
                merge=True,
            )
        else:
            txn.update(ref, {field: firestore.Increment(1), "updated_at": now})

    txn = db.transaction()
    await _txn(txn, ref)
    updated_snap = await ref.get()
    return updated_snap.to_dict() or {}
