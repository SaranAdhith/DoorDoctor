"""The payment boundary.

**No payment gateway is integrated in this build and none is bought.** This
module is the seam where one would go, shaped like Phase 3's
`notification_delivery.py`: a protocol, a simulated implementation, and one entry
point. A real gateway implements `PaymentGateway` and no call site moves.

What this boundary deliberately does *not* accept: card numbers, CVVs, UPI PINs,
bank credentials, or any gateway token that could be replayed. It takes an amount
and a description and returns a reference. A prototype that stored card data
because "it is only a demo" is how real card data ends up in a demo database.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Protocol

from ..models import PaymentStatus

logger = logging.getLogger("doordoctor.payments")


@dataclass(frozen=True)
class PaymentResult:
    status: PaymentStatus
    reference: str
    detail: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status in (PaymentStatus.SIMULATED, PaymentStatus.SUCCEEDED)


class PaymentGateway(Protocol):
    """Narrow on purpose — an amount, a currency, a human-readable description."""

    name: str

    def charge(self, *, amount_paise: int, description: str) -> PaymentResult: ...


class ManualGateway:
    """Records the intent to charge and reports `simulated`.

    Named for what actually happens today: DoorDoctor's early customers are
    invoiced and pay out of band, and an admin marks the invoice settled.
    """

    name = "manual"

    def charge(self, *, amount_paise: int, description: str) -> PaymentResult:
        reference = f"MAN-{secrets.token_hex(5).upper()}"
        logger.info(
            "[%s] charge intent %s for %s paise (%s)", self.name, reference, amount_paise, description
        )
        return PaymentResult(
            status=PaymentStatus.SIMULATED,
            reference=reference,
            detail="No payment gateway is configured in this build; no money moved.",
        )


gateway: PaymentGateway = ManualGateway()


def charge(*, amount_paise: int, description: str) -> PaymentResult:
    """Charge through the configured gateway."""
    if amount_paise <= 0:
        raise ValueError("A charge must be for a positive amount.")
    return gateway.charge(amount_paise=amount_paise, description=description)
