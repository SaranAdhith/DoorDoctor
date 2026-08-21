"""In-app notification endpoints."""

from fastapi import APIRouter, Query

from ..core.dependencies import CurrentUser, DbSession
from ..core.exceptions import NotFoundError
from ..models import Notification
from ..schemas.alert import NotificationOut
from ..services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut], summary="Notifications for the current user")
def list_notifications(
    current_user: CurrentUser, db: DbSession, unread_only: bool = Query(default=False)
):
    return notification_service.list_for_user(db, current_user.id, unread_only)


@router.post("/{notification_id}/read", response_model=NotificationOut, summary="Mark as read")
def mark_read(notification_id: int, current_user: CurrentUser, db: DbSession):
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise NotFoundError("Notification not found.")
    return notification_service.mark_read(db, notification)
