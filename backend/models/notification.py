from datetime import datetime
from typing import Literal

from pydantic import BaseModel

NotificationType = Literal["processing", "complete", "failed"]


class Notification(BaseModel):
    notification_id: str = ""
    uid: str = ""
    type: NotificationType = "processing"
    title: str = ""
    body: str = ""
    brand_id: str = ""
    post_id: str = ""
    plan_id: str = "adhoc"
    day_index: int | None = None
    read: bool = False
    created_at: datetime | None = None


class NotificationListResponse(BaseModel):
    notifications: list[Notification]
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int
