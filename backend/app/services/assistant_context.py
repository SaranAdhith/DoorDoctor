"""Role-scoped context packs — the assistant's security boundary (§2.3).

**The model never queries the database.** It is handed a pack assembled here and
nothing else: not a session, not a user row, not a tool. That single decision is
what makes a language model safe to put in front of a family member's mother's
blood pressure, because authorization happens while the pack is *built* rather
than while the answer is *written*. There is no prompt instruction to disobey —
another family's patient was never in the context to begin with.

Two packs exist, and they are deliberately not one parameterised pack:

* `build_family_pack` — one patient, already through `authorize_patient`. Written
  end to end in the **family's vocabulary**, so a model copying a phrase out of
  the pack cannot reintroduce the clinical words Phase 6 exists to keep out. That
  makes the banned-word gate nearly unfailable instead of a trap.
* `build_admin_pack` — the operating business. Written in **clinical and
  commercial vocabulary**, which is the correct register for staff.

A pack is also the answer to "what is this model allowed to claim?".
`ContextPack.numbers()` is the set of every number the pack knows, and
`assistant_service` rejects any answer containing a number outside it. A model
cannot invent a reading it was never given.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..core import pricing
from ..database import now
from ..models import (
    Alert,
    AlertSeverity,
    AlertStatus,
    Nurse,
    NurseStatus,
    Patient,
    PatientStatus,
    Subscription,
    SubscriptionStatus,
    User,
    UserRole,
    VerificationStatus,
    Visit,
    VisitStatus,
    Vital,
)
from . import (
    admin_service,
    alert_service,
    billing_service,
    medication_service,
    subscription_service,
    summary_service,
    visit_service,
    vitals_service,
)

FAMILY_WINDOW: Final = "7d"
"""The window a family pack summarises. "This week" is what people ask about."""

MEDICINE_WINDOW_DAYS: Final = 30
"""Adherence over a week is too few doses to be worth a sentence."""

MAX_ALERTS_IN_PACK: Final = 5
MAX_NURSES_IN_PACK: Final = 20
MAX_VISITS_IN_PACK: Final = 25
"""Packs are bounded. An unbounded pack is an unbounded prompt, and a demo
database with 1,453 visits would otherwise put the whole board in one request."""


# --------------------------------------------------------------------------
# The pack
# --------------------------------------------------------------------------


@dataclass
class ContextPack:
    """Everything the assistant is allowed to know for one question."""

    audience: str
    """`family` or `admin`. Drives vocabulary, gates and the answer register."""
    facts: dict[str, Any] = field(default_factory=dict)
    """Structured truth. `assistant_fallback` composes its answers from this."""
    lines: list[str] = field(default_factory=list)
    """The same truth rendered for a prompt, one statement per line."""
    patient_id: int | None = None
    patient_first_name: str | None = None

    def render(self) -> str:
        return "\n".join(self.lines)

    def numbers(self) -> set[str]:
        """Every number this pack knows, in both its renderings.

        A superset on purpose: the structured facts and the rendered lines can
        format the same value differently (`230250` and `₹2,30,250`), and a gate
        that rejected a legitimately reformatted number would fail every honest
        answer.
        """
        blob = json.dumps(self.facts, default=str) + " " + self.render()
        return summary_service.numbers_in(blob)

    def add(self, key: str, value: Any, *lines: str) -> None:
        """Record one fact and the sentences that state it."""
        self.facts[key] = value
        self.lines.extend(line for line in lines if line)


# --------------------------------------------------------------------------
# Shared formatting
# --------------------------------------------------------------------------


def _day(moment: datetime) -> str:
    return f"{moment.day} {moment:%B}"


def _weekday(moment: datetime) -> str:
    return f"{moment:%A} {moment.day} {moment:%B}"


def _clock(moment: datetime) -> str:
    hour = moment.hour % 12 or 12
    suffix = "am" if moment.hour < 12 else "pm"
    return f"{hour}:{moment.minute:02d} {suffix}"


def _number(value: float | None, decimals: int = 0) -> str:
    if value is None:
        return "unknown"
    if decimals == 0:
        return str(int(round(float(value))))
    return f"{float(value):.{decimals}f}"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")


# --------------------------------------------------------------------------
# Family pack
# --------------------------------------------------------------------------

# Every reading a family pack states, in the reader's words. The order is the
# order a person asks about them.
_FAMILY_READINGS: Final[tuple[tuple[str, str, int, str], ...]] = (
    ("heart_rate", "heart rate", 0, " beats a minute"),
    ("blood_glucose", "blood sugar", 0, ""),
    ("spo2", "oxygen level", 0, " percent"),
    ("temperature", "temperature", 1, " degrees"),
    ("weight", "weight", 1, " kg"),
)


def _reading_phrases(reading: Vital) -> list[str]:
    """One reading as bare `label value` phrases, in family vocabulary.

    Bare — no name, no verb — because the caller decides the sentence. Prefixing
    each with "Lakshmi's" here produced "Lakshmi's blood pressure was 132 over 84,
    Lakshmi's heart rate was 80, Lakshmi's blood sugar was 109..." once six
    measurements were listed in one breath.

    Blood pressure is handled apart from the loop because it is two stored columns
    and one spoken phrase — "132 over 84", never a bare 132 the reader cannot
    place.
    """
    parts: list[str] = []
    if reading.systolic_bp is not None and reading.diastolic_bp is not None:
        parts.append(
            f"blood pressure {_number(reading.systolic_bp)} over {_number(reading.diastolic_bp)}"
        )
    for key, label, decimals, unit in _FAMILY_READINGS:
        value = getattr(reading, key, None)
        if value is not None:
            parts.append(f"{label} {_number(value, decimals)}{unit}")
    return parts


def _plain_alert_causes(alert: Alert) -> list[str]:
    """What an alert was about, in family vocabulary.

    **`Alert.message` is never used here.** `alert_service.build_alert_message`
    writes "Systolic blood pressure 148 mmHg (above configured threshold 140
    mmHg)" — three banned words in one sentence, and exactly the register Phase 6
    exists to keep away from a family member. The breached parameters are
    translated instead, and de-duplicated because both halves of a blood pressure
    share one spoken name.
    """
    seen: list[str] = []
    for breach in alert.breached_parameters or []:
        label = summary_service.plain_metric_label(str(breach.get("metric", "")))
        if label not in seen:
            seen.append(label)
    return seen or ["a reading"]


def primary_patient(db: Session, user: User) -> Patient | None:
    """The patient a family member means when they do not say.

    Lowest id, which is the one they were onboarded with. Phase 11's multi-family
    work replaces `family_user_id` with a membership table; this is the one query
    that will need to follow it.
    """
    return db.scalar(
        select(Patient)
        .where(Patient.family_user_id == user.id)
        .order_by(Patient.id)
        .limit(1)
    )


def build_family_pack(db: Session, user: User, patient: Patient | None) -> ContextPack:
    """Everything a family member may be told about their own relative.

    `patient` must already have been through `authorize_patient`. This function
    deliberately does **not** accept a `patient_id` — resolving one here would
    put an authorization decision in a service that has no business making it,
    and the day someone calls it with a value straight off the request is the day
    the boundary fails.
    """
    pack = ContextPack(audience="family")

    if patient is None:
        pack.add(
            "patient",
            None,
            "This family member has no relative linked to their DoorDoctor account yet.",
        )
        _add_family_account(db, user, pack)
        return pack

    first = patient.name.split()[0]
    pack.patient_id = patient.id
    pack.patient_first_name = first
    pack.add(
        "patient",
        {"name": patient.name, "first_name": first, "age": patient.age, "gender": patient.gender},
        f"{patient.name} is {patient.age} years old and is cared for at home by DoorDoctor.",
        f"The family member asking is {user.name}.",
    )

    # -- how they have been: reuse Phase 6 rather than re-derive it -------
    summary = summary_service.build_deterministic(db, patient, FAMILY_WINDOW)
    pack.add(
        "summary",
        {
            "window": summary["window_label"],
            "headline": summary["headline"],
            "paragraphs": summary["paragraphs"],
            "reading_count": summary["reading_count"],
            "visit_count": summary["visit_count"],
        },
        summary["headline"],
        *summary["paragraphs"],
    )

    # -- the last set of readings ----------------------------------------
    latest = vitals_service.latest_for_patient(db, patient.id)
    if latest is not None:
        phrases = _reading_phrases(latest)
        pack.add(
            "latest_reading",
            {
                "recorded_on": _day(latest.recorded_at),
                "flagged": bool(latest.threshold_breached),
                "described": phrases,
            },
            f"At the check on {_day(latest.recorded_at)}, {first}'s readings were: "
            f"{'; '.join(phrases)}.",
        )
    else:
        pack.add("latest_reading", None, f"No readings have been recorded for {first} yet.")

    # -- medicines --------------------------------------------------------
    since = now() - timedelta(days=MEDICINE_WINDOW_DAYS)
    doses = medication_service.adherence_for_patient(db, patient.id, since=since)
    if doses["total"]:
        pack.add(
            "medicines",
            {
                "taken": doses["administered"],
                "total": doses["total"],
                "percentage": doses["percentage"],
                "window_days": MEDICINE_WINDOW_DAYS,
            },
            f"In the last {MEDICINE_WINDOW_DAYS} days {first} took {doses['administered']} of "
            f"the {doses['total']} medicine doses the nurse recorded.",
        )
    else:
        pack.add(
            "medicines",
            None,
            f"No medicine doses have been recorded for {first} in the last "
            f"{MEDICINE_WINDOW_DAYS} days.",
        )

    # -- the next visit and who is coming ---------------------------------
    next_visit = db.scalar(
        select(Visit)
        .options(selectinload(Visit.nurse).selectinload(Nurse.user))
        .where(
            Visit.patient_id == patient.id,
            Visit.scheduled_at >= now(),
            Visit.status.in_((VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS)),
        )
        .order_by(Visit.scheduled_at)
        .limit(1)
    )
    if next_visit is not None:
        nurse_name = (
            next_visit.nurse.user.name
            if next_visit.nurse is not None and next_visit.nurse.user is not None
            else None
        )
        pack.add(
            "next_visit",
            {
                "when": f"{_weekday(next_visit.scheduled_at)} at {_clock(next_visit.scheduled_at)}",
                "nurse_name": nurse_name,
            },
            f"The next nurse visit is on {_weekday(next_visit.scheduled_at)} at "
            f"{_clock(next_visit.scheduled_at)}."
            + (f" {nurse_name} is coming." if nurse_name else " A nurse has not been assigned yet."),
        )
    else:
        pack.add("next_visit", None, "No nurse visit is booked yet.")

    _add_family_nurse(db, patient, pack)
    _add_family_alerts(db, patient, first, pack)
    _add_family_account(db, user, pack)
    return pack


def _add_family_nurse(db: Session, patient: Patient, pack: ContextPack) -> None:
    """The nurse who most recently saw this patient, and their standing."""
    nurse = db.scalar(
        select(Nurse)
        .options(selectinload(Nurse.user))
        .join(Visit, Visit.nurse_id == Nurse.id)
        .where(Visit.patient_id == patient.id)
        .order_by(Visit.scheduled_at.desc())
        .limit(1)
    )
    if nurse is None or nurse.user is None:
        pack.add("nurse", None, "No nurse has been assigned to this patient yet.")
        return

    verified = nurse.verification_status == VerificationStatus.VERIFIED
    pack.add(
        "nurse",
        {
            "name": nurse.user.name,
            "credential": nurse.credential,
            "verified": verified,
            "status": nurse.status.value,
        },
        # "a qualified {credential}" rather than "a {credential}": the credential
        # strings include "RN/ANM", and "a RN/ANM" is wrong in a sentence a family
        # member reads. Prefixing a word sidesteps every article-agreement case.
        f"The nurse caring for {patient.name.split()[0]} is {nurse.user.name}, a qualified "
        f"{nurse.credential}.",
        f"{nurse.user.name}'s documents have been checked and verified by DoorDoctor."
        if verified
        else f"{nurse.user.name}'s document check is still being completed by DoorDoctor.",
    )


def _add_family_alerts(db: Session, patient: Patient, first: str, pack: ContextPack) -> None:
    alerts = list(
        db.scalars(
            select(Alert)
            .where(Alert.patient_id == patient.id)
            .order_by(Alert.created_at.desc())
            .limit(MAX_ALERTS_IN_PACK)
        )
    )
    open_alerts = [a for a in alerts if a.status != AlertStatus.RESOLVED]
    described = [
        {
            "when": _day(alert.created_at),
            "about": _plain_alert_causes(alert),
            "open": alert.status != AlertStatus.RESOLVED,
        }
        for alert in alerts
    ]

    lines: list[str] = []
    for entry in described:
        state = "is still being reviewed by the care team" if entry["open"] else "has been reviewed and closed"
        lines.append(
            f"On {entry['when']} {first}'s {_join(entry['about'])} was outside the range "
            f"DoorDoctor watches, and it {state}."
        )
    if not lines:
        lines.append(f"Nothing has been flagged for {first} recently.")

    pack.add(
        "alerts",
        {"open_count": len(open_alerts), "recent": described},
        *lines,
    )


def _add_family_account(db: Session, user: User, pack: ContextPack) -> None:
    """The family's own plan and their own payments. Never anyone else's."""
    subscription = subscription_service.for_user(db, user)
    if subscription is None:
        pack.add("plan", None, "This family does not have a DoorDoctor plan at the moment.")
        pack.add("payments", None, "There are no DoorDoctor invoices on this account.")
        return

    visits_allowed = subscription_service.entitlement(subscription, pricing.VISITS_PER_MONTH)
    price = billing_service.format_inr(
        subscription_service.price_paise(
            subscription.plan, subscription.billing_cycle, subscription.seats
        )
    )
    pack.add(
        "plan",
        {
            "name": subscription.plan.name,
            "status": subscription.status.value,
            "cycle": subscription.billing_cycle.value,
            "price": price,
            "visits_per_month": visits_allowed,
            "renews_on": _day(subscription.current_period_end),
        },
        f"The family is on the {subscription.plan.name} plan at {price} per "
        f"{subscription.billing_cycle.value.replace('ly', '')}, and it renews on "
        f"{_day(subscription.current_period_end)}.",
        f"That plan includes {visits_allowed} nurse visits a month."
        if visits_allowed is not None
        else "That plan includes unlimited nurse visits.",
    )

    invoices = billing_service.invoices_for_user(db, user)
    paid = [i for i in invoices if i.status.value == "paid"]
    outstanding = [i for i in invoices if i.status.value == "issued"]
    total_paid = billing_service.format_inr(sum(i.total_paise for i in paid))
    lines = [
        f"The family has paid {len(paid)} DoorDoctor {_plural(len(paid), 'invoice')}, "
        f"{total_paid} in total."
    ]
    if outstanding:
        due = billing_service.format_inr(sum(i.total_paise for i in outstanding))
        lines.append(
            f"{due} is currently outstanding across {len(outstanding)} unpaid "
            f"{_plural(len(outstanding), 'invoice')}."
        )
    else:
        lines.append("There is nothing outstanding on the account.")

    pack.add(
        "payments",
        {
            "paid_count": len(paid),
            "total_paid": total_paid,
            "outstanding_count": len(outstanding),
        },
        *lines,
    )


def _join(items: list[str]) -> str:
    if not items:
        return "reading"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" and {items[-1]}"


# --------------------------------------------------------------------------
# Admin pack
# --------------------------------------------------------------------------


def build_admin_pack(db: Session, user: User) -> ContextPack:
    """The operating business, for someone who runs it.

    Org-wide by design — an admin already reads every patient through
    `authorize_patient`, so scoping the pack more tightly than the API would be
    theatre. The register is clinical and commercial, which is correct for staff
    and is why the banned-word gate is not applied to admin answers.
    """
    pack = ContextPack(audience="admin")
    pack.add("admin", {"name": user.name}, f"The admin asking is {user.name}.")

    _add_admin_board(db, user, pack)
    _add_admin_alerts(db, pack)
    _add_admin_nurses(db, pack)
    _add_admin_revenue(db, pack)
    return pack


def _add_admin_board(db: Session, user: User, pack: ContextPack) -> None:
    visits = visit_service.list_today_visits(db, user)[:MAX_VISITS_IN_PACK]
    by_status: dict[str, int] = {}
    unassigned: list[str] = []
    for visit in visits:
        by_status[visit.status.value] = by_status.get(visit.status.value, 0) + 1
        if visit.nurse_id is None:
            unassigned.append(
                f"{visit.patient.name if visit.patient else 'a patient'} at "
                f"{_clock(visit.scheduled_at)}"
            )

    pack.add(
        "today",
        {
            "total": len(visits),
            "scheduled": by_status.get(VisitStatus.SCHEDULED.value, 0),
            "in_progress": by_status.get(VisitStatus.IN_PROGRESS.value, 0),
            "completed": by_status.get(VisitStatus.COMPLETED.value, 0),
            "unassigned": len(unassigned),
            "unassigned_detail": unassigned,
        },
        f"Today's board has {len(visits)} {_plural(len(visits), 'visit')}: "
        f"{by_status.get(VisitStatus.COMPLETED.value, 0)} completed, "
        f"{by_status.get(VisitStatus.IN_PROGRESS.value, 0)} in progress and "
        f"{by_status.get(VisitStatus.SCHEDULED.value, 0)} still scheduled.",
        (
            f"{len(unassigned)} of today's visits {_plural(len(unassigned), 'has', 'have')} "
            f"no nurse assigned: {_join(unassigned)}."
            if unassigned
            else "Every visit today has a nurse assigned."
        ),
    )

    patients_total = db.scalar(select(func.count(Patient.id))) or 0
    patients_active = (
        db.scalar(select(func.count(Patient.id)).where(Patient.status == PatientStatus.ACTIVE)) or 0
    )
    pack.add(
        "patients",
        {"total": int(patients_total), "active": int(patients_active)},
        f"DoorDoctor is caring for {patients_active} active "
        f"{_plural(int(patients_active), 'patient')} out of {patients_total} on the books.",
    )



def _add_admin_alerts(db: Session, pack: ContextPack) -> None:
    open_alerts = list(
        db.scalars(
            select(Alert)
            .options(selectinload(Alert.patient))
            .where(Alert.status != AlertStatus.RESOLVED)
            .order_by(Alert.severity.desc(), Alert.created_at.desc())
            .limit(MAX_ALERTS_IN_PACK)
        )
    )
    total_open = (
        db.scalar(select(func.count(Alert.id)).where(Alert.status != AlertStatus.RESOLVED)) or 0
    )
    critical = (
        db.scalar(
            select(func.count(Alert.id)).where(
                Alert.status != AlertStatus.RESOLVED,
                Alert.severity == AlertSeverity.CRITICAL,
            )
        )
        or 0
    )

    described = []
    lines = []
    for alert in open_alerts:
        # Clinical labels here, not the family's. An admin is staff.
        causes = [
            alert_service.METRIC_LABELS.get(str(b.get("metric")), str(b.get("metric")))
            for b in alert.breached_parameters or []
        ]
        name = alert.patient.name if alert.patient else "Unknown patient"
        described.append(
            {
                "patient": name,
                "severity": alert.severity.value,
                "parameters": causes,
                "raised_on": _day(alert.created_at),
                "status": alert.status.value,
            }
        )
        lines.append(
            f"{name} has a {alert.severity.value} alert raised on {_day(alert.created_at)} "
            f"for {_join(causes)}, currently {alert.status.value}."
        )

    pack.add(
        "alerts",
        {"open": int(total_open), "critical": int(critical), "items": described},
        f"There are {total_open} open {_plural(int(total_open), 'alert')}, "
        f"{critical} of them critical.",
        *lines,
    )


def _add_admin_nurses(db: Session, pack: ContextPack) -> None:
    # Borrowed, not re-queried: the assistant and the Nurses screen must never
    # report different open-visit counts for the same nurse.
    nurses = admin_service.list_nurses(db)[:MAX_NURSES_IN_PACK]
    active = sum(1 for n in nurses if n["status"] == NurseStatus.ACTIVE.value)
    unverified = sum(1 for n in nurses if n["verification_status"] != VerificationStatus.VERIFIED.value)
    busiest = sorted(nurses, key=lambda n: n["open_visits"], reverse=True)[:5]

    pack.add(
        "nurses",
        {
            "total": len(nurses),
            "active": active,
            "unverified": unverified,
            "busiest": [{"name": n["name"], "open_visits": n["open_visits"]} for n in busiest],
        },
        f"There are {len(nurses)} {_plural(len(nurses), 'nurse')} on the roster, "
        f"{active} active and {unverified} not yet verified.",
        *[
            f"{n['name']} ({n['credential']}) has {n['open_visits']} open "
            f"{_plural(n['open_visits'], 'visit')}."
            for n in busiest
        ],
    )


def _add_admin_revenue(db: Session, pack: ContextPack) -> None:
    revenue = billing_service.revenue_summary(db)
    past_due = list(
        db.scalars(
            select(Subscription)
            .options(selectinload(Subscription.family_user), selectinload(Subscription.organization))
            .where(Subscription.status == SubscriptionStatus.PAST_DUE)
            .limit(MAX_ALERTS_IN_PACK)
        )
    )
    past_due_names = [
        (s.family_user.name if s.family_user else (s.organization.name if s.organization else "an account"))
        for s in past_due
    ]

    mrr = billing_service.format_inr(revenue["mrr_paise"])
    overdue = billing_service.format_inr(revenue["overdue_paise"])
    collected = billing_service.format_inr(revenue["collected_this_month_paise"])

    pack.add(
        "revenue",
        {
            "mrr": mrr,
            "arr": billing_service.format_inr(revenue["arr_paise"]),
            "active_subscriptions": revenue["active_subscriptions"],
            "collected_this_month": collected,
            "overdue": overdue,
            "past_due_accounts": past_due_names,
            "by_plan": [
                {"plan": row["plan"], "subscribers": row["subscribers"]}
                for row in revenue["by_plan"]
            ],
        },
        f"Monthly recurring revenue is {mrr} across "
        f"{revenue['active_subscriptions']} active subscriptions.",
        f"{collected} has been collected this month and {overdue} is overdue.",
        (
            f"{len(past_due_names)} {_plural(len(past_due_names), 'account is', 'accounts are')} "
            f"past due: {_join(past_due_names)}."
            if past_due_names
            else "No account is past due."
        ),
        *[
            f"{row['subscribers']} {_plural(row['subscribers'], 'subscriber')} on {row['plan']}."
            for row in revenue["by_plan"]
        ],
    )
