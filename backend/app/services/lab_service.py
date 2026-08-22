"""Lab panels: ordering, results, and the recorded abnormal-result rule (§4.2).

RECORDED
--------
* A blood panel costs **₹499** (`core/pricing.ADD_ONS`).
* An abnormal result raises an **alert** and a **24-hour follow-up task**.

`ASSUMED` (all in `core/clinical.py`): what a panel contains, every reference
range, and which flags count as abnormal.

Two rules this module exists to hold
------------------------------------
**One alert per order, not per analyte.** A panel with four values outside range
is one clinical event. Four alerts would push three real findings off the top of
a family's screen with copies of the same news.

**Every result stores the range it was compared against.** `core/clinical.py` is
meant to be edited — that is the whole design — and a range that moves must not
silently re-flag a result somebody has already read and acted on.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core import clinical, pricing
from ..core.exceptions import BadRequestError, ConflictError, NotFoundError
from ..database import now
from ..models import (
    AlertSeverity,
    LabBilling,
    LabFlag,
    LabOrder,
    LabOrderStatus,
    LabResult,
    Patient,
    TaskKind,
    User,
    UserRole,
)
from . import alert_service, billing_service, subscription_service, task_service

logger = logging.getLogger("doordoctor.labs")

SOURCE_TYPE = "lab_order"

# Resolved from the entitlement key rather than typed or indexed: "lab_panels"
# is `pricing.QUOTAS`' business, and an index would break the day a meter is
# added ahead of it.
LAB_QUOTA = next(
    q.name for q in pricing.QUOTAS if q.entitlement_key == pricing.LAB_PANELS_PER_YEAR
)


# --------------------------------------------------------------------------
# The catalogue
# --------------------------------------------------------------------------


def list_panels() -> list[dict[str, Any]]:
    """The published panels, straight from `core/clinical.py`.

    Priced by pointing at `core/pricing.ADD_ONS`, never by restating a rupee
    figure — the same rule Phase 8's public pricing page follows.
    """
    panels = []
    for panel in clinical.LAB_PANELS:
        addon = pricing.ADD_ONS_BY_CODE[panel.addon_code]
        panels.append(
            {
                "code": panel.code,
                "name": panel.name,
                "description": panel.description,
                "turnaround_hours": panel.turnaround_hours,
                "price_paise": addon.price_paise,
                "addon_code": panel.addon_code,
                "analytes": [
                    {
                        "code": a.code,
                        "label": a.label,
                        "unit": a.unit,
                        "ref_low": a.ref_low,
                        "ref_high": a.ref_high,
                    }
                    for a in panel.analytes
                ],
            }
        )
    return panels


def get_panel(panel_code: str) -> clinical.PanelSpec:
    panel = clinical.LAB_PANELS_BY_CODE.get(panel_code)
    if panel is None:
        raise NotFoundError("Lab panel not found.")
    return panel


# --------------------------------------------------------------------------
# Flagging — pure, so a test can re-run the arithmetic
# --------------------------------------------------------------------------


def flag_for(
    value: float,
    *,
    ref_low: float | None,
    ref_high: float | None,
    critical_low: float | None = None,
    critical_high: float | None = None,
) -> LabFlag:
    """Compare one value against one range. No database, no clock.

    Critical is checked before ordinary abnormal, so a value that is both reports
    the more serious of the two.
    """
    if critical_low is not None and value < critical_low:
        return LabFlag.CRITICAL_LOW
    if critical_high is not None and value > critical_high:
        return LabFlag.CRITICAL_HIGH
    if ref_low is None and ref_high is None:
        return LabFlag.UNKNOWN
    if ref_low is not None and value < ref_low:
        return LabFlag.LOW
    if ref_high is not None and value > ref_high:
        return LabFlag.HIGH
    return LabFlag.NORMAL


# --------------------------------------------------------------------------
# Ordering
# --------------------------------------------------------------------------


def order(
    db: Session,
    *,
    patient: Patient,
    user: User,
    panel_code: str,
    notes: str | None = None,
    as_of: datetime | None = None,
) -> LabOrder:
    """Order a panel, paying for it out of the plan's allowance or as an add-on.

    **Payment is resolved in exactly one place.** The plan's `lab_panels` quota
    is tried first; if it is spent, the panel is billed as the recorded ₹499
    add-on rather than refused. That is the reading the prices support — an
    allowance is included care, and the add-on price exists precisely so more is
    purchasable. Refusing instead would make the add-on price unreachable.

    This is the first caller of Phase 4's `charge_addon`, exactly as Phase 4's
    deferral predicted.
    """
    panel = get_panel(panel_code)
    moment = as_of or now()

    subscription = _subscription_for(db, patient)
    billing = LabBilling.ADDON
    price = pricing.ADD_ONS_BY_CODE[panel.addon_code].price_paise
    invoice_line_id: int | None = None

    if subscription is not None:
        try:
            subscription_service.consume_quota(db, subscription, LAB_QUOTA, as_of=moment)
            billing = LabBilling.ENTITLEMENT
            price = 0
        except ConflictError:
            # The allowance is spent, not the family's right to a test.
            line = billing_service.charge_addon(
                db,
                subscription,
                addon_code=panel.addon_code,
                description=f"{panel.name} — {patient.name}",
                as_of=moment,
            )
            invoice_line_id = line.id
    else:
        # No subscription at all (an admin ordering for an unsubscribed patient).
        # The order still happens and the price is recorded; there is nothing to
        # bill it against, and losing the clinical record to a billing gap would
        # be the wrong trade.
        price = pricing.ADD_ONS_BY_CODE[panel.addon_code].price_paise

    lab_order = LabOrder(
        patient_id=patient.id,
        panel_code=panel.code,
        panel_name=panel.name,
        status=LabOrderStatus.ORDERED,
        billing=billing,
        price_paise=price,
        invoice_line_id=invoice_line_id,
        ordered_by=user.id,
        ordered_at=moment,
        notes=(notes or "").strip() or None,
    )
    db.add(lab_order)
    db.flush()
    logger.info(
        "Lab order %s: patient=%s panel=%s billing=%s",
        lab_order.id,
        patient.id,
        panel.code,
        billing.value,
    )
    return lab_order


def _subscription_for(db: Session, patient: Patient):
    from ..models import Subscription

    return db.scalar(
        select(Subscription)
        .options(selectinload(Subscription.plan))
        .where(Subscription.family_user_id == patient.family_user_id)
        .order_by(Subscription.id.desc())
        .limit(1)
    )


def mark_collected(db: Session, lab_order: LabOrder, as_of: datetime | None = None) -> LabOrder:
    if lab_order.status not in (LabOrderStatus.ORDERED, LabOrderStatus.COLLECTED):
        raise BadRequestError("This order is not awaiting collection.")
    lab_order.status = LabOrderStatus.COLLECTED
    lab_order.collected_at = as_of or now()
    db.flush()
    return lab_order


def cancel(db: Session, lab_order: LabOrder, user: User) -> LabOrder:
    """Cancel before results. The allowance is **not** handed back.

    Deliberate, and different from a cancelled consult: a lab panel's cost is
    the sample and the laboratory, both of which are spent the moment the order
    is placed. A consult that never happened cost nothing.
    """
    if lab_order.status == LabOrderStatus.RESULTED:
        raise BadRequestError("This order already has results and cannot be cancelled.")
    if lab_order.status == LabOrderStatus.CANCELLED:
        raise BadRequestError("This order is already cancelled.")
    lab_order.status = LabOrderStatus.CANCELLED
    lab_order.cancelled_at = now()
    db.flush()
    return lab_order


# --------------------------------------------------------------------------
# Results — and the recorded abnormal rule
# --------------------------------------------------------------------------


def record_results(
    db: Session,
    lab_order: LabOrder,
    values: dict[str, float],
    *,
    as_of: datetime | None = None,
    notify: bool = True,
) -> LabOrder:
    """Attach results, flag each against its range, and apply the recorded rule.

    Re-recording replaces the previous results rather than appending — a
    corrected report is a correction, not a second opinion — and reuses the open
    task rather than opening a second one.
    """
    if lab_order.status == LabOrderStatus.CANCELLED:
        raise BadRequestError("This order was cancelled.")

    panel = get_panel(lab_order.panel_code)
    known = {a.code: a for a in panel.analytes}
    unknown = sorted(set(values) - set(known))
    if unknown:
        raise BadRequestError(f"Not part of the {panel.name}: {', '.join(unknown)}.")
    if not values:
        raise BadRequestError("At least one result is required.")

    moment = as_of or now()
    lab_order.results.clear()
    db.flush()

    for code, spec in known.items():
        if code not in values:
            continue
        value = float(values[code])
        flag = flag_for(
            value,
            ref_low=spec.ref_low,
            ref_high=spec.ref_high,
            critical_low=spec.critical_low,
            critical_high=spec.critical_high,
        )
        db.add(
            LabResult(
                order_id=lab_order.id,
                analyte_code=spec.code,
                label=spec.label,
                value=value,
                unit=spec.unit,
                # Copied, not referenced. See the module docstring.
                ref_low=spec.ref_low,
                ref_high=spec.ref_high,
                flag=flag,
                created_at=moment,
            )
        )

    lab_order.status = LabOrderStatus.RESULTED
    lab_order.reported_at = moment
    db.flush()
    db.refresh(lab_order)

    abnormal = lab_order.abnormal_results
    if abnormal:
        _raise_abnormal_alert(db, lab_order, abnormal, notify=notify)
        _open_follow_up(db, lab_order, abnormal, as_of=moment)

    return lab_order


def describe_result(result: LabResult) -> str:
    """One result and the range it was judged against, in one readable phrase."""
    unit = f" {result.unit}" if result.unit else ""
    if result.ref_low is not None and result.ref_high is not None:
        band = f"expected {_number(result.ref_low)}–{_number(result.ref_high)}{unit}"
    elif result.ref_high is not None:
        band = f"expected up to {_number(result.ref_high)}{unit}"
    elif result.ref_low is not None:
        band = f"expected at least {_number(result.ref_low)}{unit}"
    else:
        band = "no expected range configured"
    return f"{result.label} {_number(result.value)}{unit} ({band})"


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _raise_abnormal_alert(
    db: Session, lab_order: LabOrder, abnormal: list[LabResult], notify: bool = True
):
    """RECORDED: an abnormal result raises an alert. One alert, per order.

    Severity is `ASSUMED`: a critically abnormal value is critical, anything else
    outside range is a warning.
    """
    critical = any(LabFlag(r.flag).is_critical for r in abnormal)
    severity = AlertSeverity.CRITICAL if critical else AlertSeverity.WARNING
    joined = "; ".join(describe_result(r) for r in abnormal)

    return alert_service.create_alert(
        db,
        patient=lab_order.patient,
        alert_type="lab_result_abnormal",
        severity=severity,
        title=f"{lab_order.panel_name}: results outside the expected range",
        message=(
            f"{len(abnormal)} result(s) from the {lab_order.panel_name} fell outside the "
            f"expected range: {joined}. A member of the care team will follow up within "
            f"{clinical.LAB_FOLLOW_UP_HOURS} hours. This is a monitoring alert, not a "
            "medical diagnosis."
        ),
        breaches=[
            {
                "metric": r.analyte_code,
                "label": r.label,
                "value": r.value,
                "unit": r.unit,
                "ref_low": r.ref_low,
                "ref_high": r.ref_high,
                "flag": LabFlag(r.flag).value,
            }
            for r in abnormal
        ],
        notify=notify,
    )


def _open_follow_up(
    db: Session, lab_order: LabOrder, abnormal: list[LabResult], as_of: datetime | None = None
):
    """RECORDED: an abnormal result creates a **24-hour** follow-up task."""
    existing = task_service.open_for_source(db, SOURCE_TYPE, lab_order.id)
    if existing is not None:
        return existing

    return task_service.create(
        db,
        patient=lab_order.patient,
        kind=TaskKind.LAB_FOLLOW_UP,
        title=f"Review {lab_order.panel_name} for {lab_order.patient.name}",
        detail="; ".join(describe_result(r) for r in abnormal),
        due_in_hours=clinical.LAB_FOLLOW_UP_HOURS,
        source_type=SOURCE_TYPE,
        source_id=lab_order.id,
        assigned_user_id=task_service.assign_to_patients_nurse(db, lab_order.patient),
        as_of=as_of,
    )


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


def _loaded(query):
    return query.options(selectinload(LabOrder.results), selectinload(LabOrder.patient))


def list_for_patient(db: Session, patient_id: int, limit: int = 50) -> list[LabOrder]:
    return list(
        db.scalars(
            _loaded(select(LabOrder))
            .where(LabOrder.patient_id == patient_id)
            .order_by(LabOrder.ordered_at.desc(), LabOrder.id.desc())
            .limit(limit)
        )
    )


def list_awaiting_results(db: Session, limit: int = 100) -> list[LabOrder]:
    return list(
        db.scalars(
            _loaded(select(LabOrder))
            .where(LabOrder.status.in_((LabOrderStatus.ORDERED, LabOrderStatus.COLLECTED)))
            .order_by(LabOrder.ordered_at, LabOrder.id)
            .limit(limit)
        )
    )


def get_for_user(db: Session, user: User, order_id: int) -> LabOrder:
    """Someone else's lab order is a 404, exactly as their patient is.

    Delegates to `authorize_patient` rather than repeating its rules, the same
    way `authorize_report` does — a lab order is visible to exactly the people
    the patient behind it is visible to.
    """
    from ..core.dependencies import authorize_patient

    lab_order = db.scalar(_loaded(select(LabOrder)).where(LabOrder.id == order_id))
    if lab_order is None:
        raise NotFoundError("Lab order not found.")
    try:
        authorize_patient(db, user, lab_order.patient_id)
    except NotFoundError:
        raise NotFoundError("Lab order not found.") from None
    return lab_order


def serialize(lab_order: LabOrder) -> dict[str, Any]:
    return {
        "id": lab_order.id,
        "patient_id": lab_order.patient_id,
        "patient_name": lab_order.patient.name if lab_order.patient else None,
        "panel_code": lab_order.panel_code,
        "panel_name": lab_order.panel_name,
        "status": lab_order.status.value,
        "billing": lab_order.billing.value,
        "price_paise": lab_order.price_paise,
        "invoice_line_id": lab_order.invoice_line_id,
        "ordered_at": lab_order.ordered_at,
        "collected_at": lab_order.collected_at,
        "reported_at": lab_order.reported_at,
        "cancelled_at": lab_order.cancelled_at,
        "notes": lab_order.notes,
        "abnormal_count": len(lab_order.abnormal_results),
        "results": [serialize_result(r) for r in lab_order.results],
    }


def serialize_result(result: LabResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "analyte_code": result.analyte_code,
        "label": result.label,
        "value": result.value,
        "unit": result.unit,
        "ref_low": result.ref_low,
        "ref_high": result.ref_high,
        "flag": result.flag.value,
        "is_abnormal": LabFlag(result.flag).is_abnormal,
        "description": describe_result(result),
    }
