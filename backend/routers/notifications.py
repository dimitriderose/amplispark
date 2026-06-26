import logging

from fastapi import APIRouter, Depends, HTTPException
from google.api_core.exceptions import NotFound

from backend.middleware import get_authenticated_uid
from backend.services import firestore_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/notifications/unread-count")
async def get_unread_count(uid: str | None = Depends(get_authenticated_uid)):
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    count = await firestore_client.get_unread_count(uid)
    return {"unread_count": count}


@router.get("/notifications")
async def list_notifications(
    uid: str | None = Depends(get_authenticated_uid),
    limit: int = 10,
):
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    safe_limit = max(1, min(limit, 50))
    notifications = await firestore_client.list_notifications(uid, limit=safe_limit)
    unread_count = sum(1 for n in notifications if not n.get("read", False))
    return {"notifications": notifications, "unread_count": unread_count}


@router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    uid: str | None = Depends(get_authenticated_uid),
):
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        await firestore_client.mark_notification_read(uid, notification_id)
    except NotFound as e:
        raise HTTPException(status_code=404, detail="Notification not found") from e
    except Exception as e:
        logger.error("mark_notification_read failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e
    return {"status": "ok", "notification_id": notification_id}


@router.post("/notifications/read-all")
async def mark_all_read(uid: str | None = Depends(get_authenticated_uid)):
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    updated = await firestore_client.mark_all_notifications_read(uid)
    return {"status": "ok", "updated": updated}
