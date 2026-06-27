import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import (
    BETA_MAX_CALENDARS_PER_MONTH,
    BETA_MAX_QUICK_POSTS_PER_MONTH,
)
from backend.middleware import get_authenticated_uid
from backend.models.waitlist import UserMeResponse, WaitlistJoinRequest, WaitlistJoinResponse
from backend.services import email_client, firestore_client

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@router.post("/waitlist", response_model=WaitlistJoinResponse)
@limiter.limit("3/hour")
async def join_waitlist(request: Request, body: WaitlistJoinRequest):
    newly_added = await firestore_client.join_waitlist(body.email)
    if newly_added:
        try:
            await email_client.send_waitlist_confirmation(body.email)
        except Exception:
            logger.warning("send_waitlist_confirmation failed for %s", body.email)
    return WaitlistJoinResponse(status="joined" if newly_added else "already_registered")


@router.get("/users/me", response_model=UserMeResponse)
async def get_user_me(uid: str | None = Depends(get_authenticated_uid)):
    if not uid:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await firestore_client.get_user(uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role = user.get("role", "beta")
    beta_expires_at = user.get("beta_expires_at")
    now = datetime.now(UTC)

    if isinstance(beta_expires_at, datetime) and beta_expires_at.tzinfo is None:
        beta_expires_at = beta_expires_at.replace(tzinfo=UTC)

    days_remaining: int | None = None
    if role == "beta" and beta_expires_at:
        delta_seconds = (beta_expires_at - now).total_seconds()
        days_remaining = max(0, int(delta_seconds // 86400))

    return UserMeResponse(
        role=role,
        beta_expires_at=beta_expires_at,
        quick_posts_this_month=user.get("quick_posts_this_month", 0),
        calendars_this_month=user.get("calendars_this_month", 0),
        days_remaining=days_remaining,
        quick_posts_limit=BETA_MAX_QUICK_POSTS_PER_MONTH if role == "beta" else None,
        calendars_limit=BETA_MAX_CALENDARS_PER_MONTH if role == "beta" else None,
    )
