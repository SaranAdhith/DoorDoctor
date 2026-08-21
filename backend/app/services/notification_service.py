"""In-app notification records.

Production DoorDoctor pushes these through FCM / SMS / email providers. The MVP
stores them in the database and renders them in the UI.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Alert, Notification, NotificationType, Patient, User, UserRole


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
    """Notify the patient's family member and every coordinator about a new alert."""
    recipients: list[int] = [patient.family_user_id]
    coordinator_ids = db.scalars(
        select(User.id).where(User.role == UserRole.COORDINATOR, User.is_active.is_(True))
    ).all()
    recipients.extend(int(cid) for cid in coordinator_ids)

    created: list[Notification] = []
    for user_id in dict.fromkeys(recipients):  # de-duplicate, keep order
        created.append(
            create_notification(
                db,
                user_id=user_id,
                title=alert.title,
                message=alert.message,
                patient_id=patient.id,
                alert_id=alert.id,
            )
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
