"""Outbound delivery channels.

`notification_service.py` writes the in-app record. This module is the seam to
everything *outside* the app: email, SMS, WhatsApp, push.

No provider credentials exist in this build and none are bought. Each channel
formats the payload it would hand its provider and reports `simulated`, so the
demo runs offline while the call sites, the `delivery_log` table and the
per-channel formatting are the real ones. Phase 10 adds recipient preferences,
quiet hours and dual-channel critical alerts on top of this without changing
what a caller writes today.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from ..models import DeliveryChannelName, DeliveryLog, DeliveryStatus, User

logger = logging.getLogger("doordoctor.delivery")

REDACTED = "[redacted]"


@dataclass(frozen=True)
class DeliveryResult:
    status: DeliveryStatus
    recipient: str
    detail: str | None = None


class DeliveryChannel(Protocol):
    """What every channel must provide. Kept narrow on purpose."""

    name: DeliveryChannelName

    def address_for(self, user: User) -> str | None:
        """The user's address on this channel, or None when they cannot be reached."""

    def send(self, *, recipient: str, subject: str, body: str) -> DeliveryResult: ...


class _SimulatedChannel:
    """Shared behaviour: format, log, report `simulated`."""

    name: DeliveryChannelName

    def address_for(self, user: User) -> str | None:  # pragma: no cover - overridden
        raise NotImplementedError

    def send(self, *, recipient: str, subject: str, body: str) -> DeliveryResult:
        logger.info("[%s] to %s: %s", self.name.value, _mask(recipient), subject)
        return DeliveryResult(
            status=DeliveryStatus.SIMULATED,
            recipient=recipient,
            detail="No provider configured in this build; message was not transmitted.",
        )


class EmailChannel(_SimulatedChannel):
    name = DeliveryChannelName.EMAIL

    def address_for(self, user: User) -> str | None:
        return user.email


class SmsChannel(_SimulatedChannel):
    name = DeliveryChannelName.SMS

    def address_for(self, user: User) -> str | None:
        return user.phone


class WhatsAppChannel(_SimulatedChannel):
    name = DeliveryChannelName.WHATSAPP

    def address_for(self, user: User) -> str | None:
        return user.phone


class PushChannel(_SimulatedChannel):
    name = DeliveryChannelName.PUSH

    def address_for(self, user: User) -> str | None:
        # Device tokens arrive with the mobile client; until then push has no
        # address and callers fall through to another channel.
        return None


CHANNELS: dict[DeliveryChannelName, DeliveryChannel] = {
    channel.name: channel
    for channel in (EmailChannel(), SmsChannel(), WhatsAppChannel(), PushChannel())
}


def deliver(
    db: Session,
    *,
    channel: DeliveryChannelName,
    subject: str,
    body: str,
    user: User | None = None,
    recipient: str | None = None,
    sensitive: Sequence[str] = (),
) -> DeliveryLog | None:
    """Send through one channel and record it. Returns None if unreachable.

    `sensitive` values are replaced with `[redacted]` before the body is
    persisted. A password-reset link stored verbatim would make `delivery_log` a
    table of live account takeovers, readable by anyone with database access —
    the transmitted message carries the secret, the record does not.
    """
    handler = CHANNELS[channel]
    address = recipient or (handler.address_for(user) if user else None)
    if not address:
        logger.info("[%s] skipped: no address for user %s", channel.value, user.id if user else "-")
        return None

    result = handler.send(recipient=address, subject=subject, body=body)

    record = DeliveryLog(
        user_id=user.id if user else None,
        channel=channel,
        recipient=address,
        subject=subject,
        body=redact(body, sensitive),
        status=result.status,
        detail=result.detail,
    )
    db.add(record)
    return record


def redact(body: str, sensitive: Sequence[str]) -> str:
    for secret in sensitive:
        if secret:
            body = body.replace(secret, REDACTED)
    return body


def _mask(address: str) -> str:
    """Keep the log useful without printing a full address into it."""
    if "@" in address:
        local, _, domain = address.partition("@")
        return f"{local[:2]}***@{domain}"
    return f"***{address[-4:]}" if len(address) > 4 else "***"
