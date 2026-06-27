from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator


class WaitlistJoinRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class WaitlistJoinResponse(BaseModel):
    status: Literal["joined", "already_registered"]


class UserRecord(BaseModel):
    uid: str
    role: Literal["beta", "user", "admin"]
    email: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    beta_expires_at: datetime | None = None
    quick_posts_this_month: int = 0
    calendars_this_month: int = 0
    counters_reset_at: datetime | None = None


class UserMeResponse(BaseModel):
    role: Literal["beta", "user", "admin"]
    beta_expires_at: datetime | None = None
    quick_posts_this_month: int = 0
    calendars_this_month: int = 0
    days_remaining: int | None = None
    quick_posts_limit: int | None = None
    calendars_limit: int | None = None
