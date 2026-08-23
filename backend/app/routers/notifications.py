"""In-app notifications, channel preferences and the delivery record (§4.18)."""

from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from ..core.dependencies import CurrentUser, DbSession
from ..core.exceptions import NotFoundError
from ..core.ops import CRITICAL_CHANNEL_COUNT, QUIET_HOURS_NEVER_SUPPRESS_CRITICAL
from ..models import DeliveryLog, Notification
from ..schemas.alert import NotificationOut
from ..schemas.notification import (
    DeliveryLogOut,
    NotificationPreferenceOut,
    NotificationPreferenceUpdate,
)
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


@router.get(
    "/preferences",
    response_model=NotificationPreferenceOut,
    summary="How this account wants to be reached",
)
def get_preferences(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    preference = notification_service.preferences_for(db, current_user)
    db.commit()
    return _serialize(preference)


@router.put(
    "/preferences",
    response_model=NotificationPreferenceOut,
    summary="Update notification channels and quiet hours",
)
def update_preferences(
    payload: NotificationPreferenceUpdate, current_user: CurrentUser, db: DbSession
) -> dict[str, Any]:
    """Channels and quiet hours. Neither can silence a critical alert.

    There is deliberately no switch here for "in-app": what a family sees when
    they open the app is not a delivery preference, and a setting that could
    hide a reading from its own family inside the product is not one anybody
    asked for.
    """
    preference = notification_service.preferences_for(db, current_user)
    fields = payload.model_dump(exclude_unset=True)

    if "channels" in fields and fields["channels"] is not None:
        merged = preference.channels
        merged.update({key: bool(value) for key, value in fields["channels"].items()})
        preference.channels = merged
    for key in ("quiet_hours_enabled", "quiet_start_hour", "quiet_end_hour"):
        if key in fields and fields[key] is not None:
            setattr(preference, key, fields[key])

    db.commit()
    db.refresh(preference)
    return _serialize(preference)


@router.get(
    "/delivery-log",
    response_model=list[DeliveryLogOut],
    summary="Every message this account was sent, and every one it was not",
)
def delivery_log(current_user: CurrentUser, db: DbSession, limit: int = Query(default=50, le=200)):
    """Including the ones held back or undeliverable.

    This is what an admin opens when a family says "I never got the alert", and
    what a family opens to check the same thing themselves.
    """
    return list(
        db.scalars(
            select(DeliveryLog)
            .where(DeliveryLog.user_id == current_user.id)
            .order_by(DeliveryLog.created_at.desc())
            .limit(limit)
        )
    )


def _serialize(preference) -> dict[str, Any]:
    return {
        "channels": preference.channels,
        "quiet_hours_enabled": preference.quiet_hours_enabled,
        "quiet_start_hour": preference.quiet_start_hour,
        "quiet_end_hour": preference.quiet_end_hour,
        "in_quiet_hours_now": preference.in_quiet_hours(),
        "critical_always_delivered": QUIET_HOURS_NEVER_SUPPRESS_CRITICAL,
        "critical_channel_count": CRITICAL_CHANNEL_COUNT,
    }
