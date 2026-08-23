"""In-app notifications, and the one path everything outbound goes through.

Two layers, and the split matters. `create_notification` writes what a family
sees when they open the app. `dispatch` writes that **and** decides which
outside-the-app channels carry it, honouring preferences and quiet hours.

Phase 10 (§4.18) made `dispatch` the single outbound path. Nothing else should
call `notification_delivery` directly for a person-facing message — the
preferences, the quiet-hours rule and the dual-channel critical rule live here,
and a second path around them is a second set of rules.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.ops import (
    CHANNEL_DEFAULT_ENABLED,
    CHANNEL_ORDER,
    CHANNEL_ORDER_DEFAULT,
    CRITICAL_CHANNEL_COUNT,
    QUIET_HOURS_NEVER_SUPPRESS_CRITICAL,
)
from ..models import (
    Alert,
    AlertSeverity,
    CareCircleMember,
    DeliveryChannelName,
    DeliveryStatus,
    Notification,
    NotificationPreference,
    NotificationType,
    Patient,
    User,
    UserRole,
)
from . import care_circle_service, notification_delivery


def create_notification(
    db: Session,
    *,
    user_id: int,
    title: str,
    message: str,
    patient_id: int | None = None,
    alert_id: int | None = None,
    type_: NotificationType = NotificationType.ALERT,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        patient_id=patient_id,
        alert_id=alert_id,
        type=type_,
        title=title,
        message=message,
    )
    db.add(notification)
    return notification


def notify_alert_recipients(db: Session, alert: Alert, patient: Patient) -> list[Notification]:
    """Tell the family, every admin, and the care circle about a new alert.

    Everyone with an account gets an in-app record; everyone — accounts and
    circle members alike — is routed through `dispatch`, so preferences, quiet
    hours and the dual-channel critical rule apply once, in one place.

    The circle members are the addition this phase makes, and it is the point of
    the feature: the neighbour who can be at the house in ten minutes has no
    login, and until now the platform had no way to tell her anything.
    """
    users: list[User] = []
    family = db.get(User, patient.family_user_id)
    if family is not None:
        users.append(family)
    users.extend(
        db.scalars(
            select(User).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        ).all()
    )

    created: list[Notification] = []
    seen: set[int] = set()
    for user in users:
        if user.id in seen:
            continue
        seen.add(user.id)
        result = dispatch(
            db,
            Recipient(label=user.name, user=user),
            title=alert.title,
            message=alert.message,
            severity=alert.severity,
            patient_id=patient.id,
            alert_id=alert.id,
        )
        if result["notification_id"] is not None:
            notification = db.get(Notification, result["notification_id"])
            if notification is not None:
                created.append(notification)

    for member in care_circle_service.alert_recipients(db, patient.id):
        if member.user_id in seen:
            continue
        dispatch(
            db,
            Recipient(label=member.name, member=member),
            title=alert.title,
            message=alert.message,
            severity=alert.severity,
            patient_id=patient.id,
            alert_id=alert.id,
        )

    return created


def list_for_user(db: Session, user_id: int, unread_only: bool = False) -> list[Notification]:
    query = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        query = query.where(Notification.read.is_(False))
    return list(db.scalars(query.order_by(Notification.created_at.desc()).limit(50)))


def mark_read(db: Session, notification: Notification) -> Notification:
    notification.read = True
    db.commit()
    db.refresh(notification)
    return notification


# --------------------------------------------------------------------------
# Channel routing, preferences and quiet hours (Phase 10, §4.18)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Recipient:
    """Somebody to reach. Either an account, or a care circle member with none.

    The second case is the whole reason this exists: the neighbour with the
    spare key has no login, and reaching her is frequently the most useful thing
    the platform can do at 2am.
    """

    label: str
    user: User | None = None
    member: "CareCircleMember | None" = None

    @property
    def user_id(self) -> int | None:
        return self.user.id if self.user else None


@dataclass(frozen=True)
class ChannelPlan:
    channel: DeliveryChannelName
    address: str | None
    #: Why this channel will not carry the message, if it will not.
    blocked: str | None = None
    status: DeliveryStatus | None = None


def preferences_for(db: Session, user: User) -> NotificationPreference:
    """This user's preferences, creating the default row on first read."""
    existing = db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    if existing is not None:
        return existing
    preference = NotificationPreference(user_id=user.id)
    preference.channels = dict(CHANNEL_DEFAULT_ENABLED)
    db.add(preference)
    db.flush()
    return preference


def _address_for(recipient: Recipient, channel: DeliveryChannelName) -> str | None:
    if recipient.user is not None:
        return notification_delivery.CHANNELS[channel].address_for(recipient.user)
    member = recipient.member
    if member is None:  # pragma: no cover - defensive
        return None
    if channel == DeliveryChannelName.EMAIL:
        return member.email
    if channel in (DeliveryChannelName.SMS, DeliveryChannelName.WHATSAPP):
        return member.phone
    return None


def plan_channels(
    db: Session,
    recipient: Recipient,
    *,
    type_: NotificationType,
    critical: bool,
    at: datetime | None = None,
) -> list[ChannelPlan]:
    """Decide which channels carry this message, and record why the rest do not.

    Three rules, in this order:

    1. **A critical alert goes out on two channels that can actually reach
       somebody.** RECORDED as dual-channel; the "that can actually reach
       somebody" half is the correction Phase 9 forced. Push has no address in
       this build, so a rule returning SMS + push returns one channel wearing
       two names.
    2. **Quiet hours never silence a critical alert.** For anything else, a
       message inside the window is *suppressed and recorded as suppressed* —
       a decision, not a gap.
    3. **A channel with no address is an attempt that could not be made**, and
       it is written down as one rather than omitted.
    """
    order = CHANNEL_ORDER.get(type_.value, CHANNEL_ORDER_DEFAULT)
    preference = preferences_for(db, recipient.user) if recipient.user else None
    quiet = bool(preference and preference.in_quiet_hours(at))

    wanted = CRITICAL_CHANNEL_COUNT if critical else 1
    plans: list[ChannelPlan] = []
    chosen = 0

    for name in order:
        channel = DeliveryChannelName(name)

        # Reachability is checked *before* the preference switch, deliberately.
        # Push is off by default precisely because it has no address in this
        # build, and recording that as "switched off in settings" would blame a
        # preference for a limitation of the platform. "Switched off" then only
        # ever appears against a channel that could otherwise have delivered.
        address = _address_for(recipient, channel)
        if not address:
            plans.append(
                ChannelPlan(
                    channel,
                    None,
                    blocked="No address on this channel",
                    status=DeliveryStatus.UNREACHABLE,
                )
            )
            continue

        if preference is not None and not preference.is_enabled(channel):
            plans.append(
                ChannelPlan(channel, None, blocked="Switched off in notification settings")
            )
            continue

        if quiet and not (critical and QUIET_HOURS_NEVER_SUPPRESS_CRITICAL):
            plans.append(
                ChannelPlan(
                    channel,
                    address,
                    blocked="Held back during quiet hours",
                    status=DeliveryStatus.SUPPRESSED,
                )
            )
            continue

        if chosen >= wanted:
            plans.append(ChannelPlan(channel, address, blocked="Not needed for this message"))
            continue

        plans.append(ChannelPlan(channel, address))
        chosen += 1

    return plans


def dispatch(
    db: Session,
    recipient: Recipient,
    *,
    title: str,
    message: str,
    type_: NotificationType = NotificationType.ALERT,
    severity: AlertSeverity | None = None,
    patient_id: int | None = None,
    alert_id: int | None = None,
    sensitive: Sequence[str] = (),
    at: datetime | None = None,
) -> dict[str, Any]:
    """The single outbound path. Writes the in-app record, then routes channels.

    **The in-app record is always written.** Quiet hours and channel preferences
    govern what leaves the building; they never govern whether a family can see
    the alert when they open the app. A preference that could hide a reading
    from its own family inside the product would be a setting nobody asked for.
    """
    critical = severity == AlertSeverity.CRITICAL
    notification: Notification | None = None
    if recipient.user is not None:
        notification = create_notification(
            db,
            user_id=recipient.user.id,
            title=title,
            message=message,
            patient_id=patient_id,
            alert_id=alert_id,
            type_=type_,
        )
        # Flushed so the caller gets a real id back. Still not committed —
        # `dispatch` joins the transaction of whatever raised the alert, so a
        # rolled-back alert takes its notifications with it.
        db.flush()

    sent: list[str] = []
    for plan in plan_channels(db, recipient, type_=type_, critical=critical, at=at):
        if plan.blocked is None and plan.address:
            notification_delivery.deliver(
                db,
                channel=plan.channel,
                subject=title,
                body=message,
                user=recipient.user,
                recipient=plan.address,
                sensitive=sensitive,
            )
            sent.append(plan.channel.value)
        elif plan.status is not None:
            notification_delivery.record_outcome(
                db,
                channel=plan.channel,
                subject=title,
                user=recipient.user,
                recipient=plan.address or recipient.label,
                status=plan.status,
                detail=plan.blocked,
            )

    return {
        "recipient": recipient.label,
        "notification_id": notification.id if notification else None,
        "channels": sent,
    }
