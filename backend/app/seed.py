"""Reset and seed the DoorDoctor demo database.

    python -m app.seed

Drops every table, recreates the schema and loads the fictional demo dataset:
three accounts, one patient, one nurse, a medication schedule, four
completed historical visits and one visit left `scheduled` so the evaluator can
run the live workflow.

It also loads a running business (Phase 4): the published price list, the demo
family's fourteen-month subscription with its paid invoices, a loyalty reward
already earned at month twelve, a referral that converted, and two organization
accounts — so the billing screens open with history rather than with zeroes.

The billing history is produced by calling the real services, not by writing
rows. If the loyalty rule or the credit arithmetic breaks, the seed shows it.

All data is fictional. No real patient information is used. No payment gateway
is integrated and no money moves.
"""

from __future__ import annotations

import argparse
from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from .config import settings
from .core import pricing
from .database import Base, SessionLocal, engine, now
from .core.security import hash_password
from .models import (
    BillingCycle,
    InvoiceStatus,
    Nurse,
    NurseStatus,
    Organization,
    OrganizationType,
    Medication,
    MedicationLog,
    MedicationLogStatus,
    Patient,
    PatientStatus,
    PatientThreshold,
    User,
    UserRole,
    VerificationStatus,
    Visit,
    VisitStatus,
    Vital,
    VitalMetric,
)
from .services import billing_service, referral_service, subscription_service, vitals_service

DEMO_PASSWORD = "Demo@123"

DEMO_USERS = [
    {
        "name": "Darren D'Souza",
        "email": "family@doordoctor.in",
        "phone": "+91 90000 00001",
        "role": UserRole.FAMILY,
    },
    {
        "name": "Anitha Kumar",
        "email": "nurse@doordoctor.in",
        "phone": "+91 90000 00002",
        "role": UserRole.NURSE,
    },
    {
        "name": "Ravi Menon",
        "email": "admin@doordoctor.in",
        "phone": "+91 90000 00003",
        "role": UserRole.ADMIN,
    },
]

# Historical readings, all inside the configured thresholds. The live demo
# supplies the out-of-range reading (148/92) through the nurse UI.
HISTORY = [
    # days_ago, systolic, diastolic, hr, glucose, spo2, temp, weight
    (8, 126, 78, 76, 104, 98, 98.0, 64.0),
    (6, 130, 80, 78, 108, 98, 98.1, 64.2),
    (4, 128, 82, 74, 110, 97, 98.2, 64.1),
    (2, 132, 84, 80, 109, 98, 98.0, 64.3),
]

MEDICATIONS = [
    {"name": "Amlodipine", "dosage": "5 mg", "frequency": "Once daily", "scheduled_time": "08:00"},
    {"name": "Metformin", "dosage": "500 mg", "frequency": "Twice daily", "scheduled_time": "08:00"},
    {"name": "Atorvastatin", "dosage": "10 mg", "frequency": "Once daily", "scheduled_time": "20:00"},
]

THRESHOLDS = {
    VitalMetric.SYSTOLIC_BP: (90, 140),
    VitalMetric.DIASTOLIC_BP: (60, 90),
    VitalMetric.HEART_RATE: (50, 100),
    VitalMetric.BLOOD_GLUCOSE: (70, 180),
    VitalMetric.SPO2: (94, 100),
    VitalMetric.TEMPERATURE: (95, 100.4),
    VitalMetric.WEIGHT: (35, 120),
}

# Dose outcomes across the historical visits -> ~87% adherence.
# 13 administered / 15 logged doses = 87%.
ADHERENCE_PLAN = [
    ["administered", "administered", "administered"],
    ["administered", "skipped", "administered"],
    ["administered", "administered", "administered"],
    ["administered", "refused", "administered"],
]
EXTRA_ADHERENCE_DOSES = ["administered", "administered", "administered"]

SKIP_REASONS = {
    "skipped": "Dose held - patient had not eaten yet",
    "refused": "Patient declined the dose during the visit",
}


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _at(days_ago: int, hour: int = 10, minute: int = 30) -> datetime:
    day = (now() - timedelta(days=days_ago)).date()
    return datetime.combine(day, time(hour=hour, minute=minute))


# How much billing history the demo opens with. Fourteen months is the shortest
# span that shows a loyalty reward already earned at month twelve *and* the free
# month it bought at thirteen.
SUBSCRIPTION_HISTORY_MONTHS = 14
# Where the current billing period starts, relative to whenever the demo is run.
# Five days back means the period is genuinely in progress — some of the visit
# allowance spent, the invoice raised and inside its payment terms, the renewal
# date still ahead — on any day someone opens the demo.
PERIOD_START_DAYS_AGO = 5


def _billing_anchor() -> datetime:
    """The start of the period the demo subscriptions are currently in."""
    return datetime.combine(
        (now() - timedelta(days=PERIOD_START_DAYS_AGO)).date(), time(hour=9, minute=0)
    )


def _bill_history(db: Session, subscription, months: int, *, settle_current: bool = True) -> None:
    """Invoice and settle every past period, then issue the current one.

    This goes through `billing_service` rather than writing invoice rows, so the
    seed exercises the real numbering, credit application and loyalty rules. If
    the loyalty arithmetic breaks, the demo data is wrong in an obvious way
    instead of being quietly fabricated around the bug.
    """
    start = subscription.started_at
    for index in range(months):
        period_start = subscription_service.add_months(start, index)
        invoice = billing_service.generate_invoice(
            db,
            subscription,
            period_start=period_start,
            period_end=subscription_service.add_months(start, index + 1),
            issued_at=period_start,
        )
        billing_service.mark_paid(db, invoice)
        # Backdated to the day after it was raised. `mark_paid` stamps `paid_at`
        # with the real clock, which is right in production and wrong here — it
        # would report fourteen months of revenue as collected this morning.
        invoice.paid_at = period_start + timedelta(days=1)

    subscription_service.advance_period(db, subscription)

    current = billing_service.generate_invoice(db, subscription)
    if settle_current:
        billing_service.mark_paid(db, current)
        current.paid_at = current.issued_at + timedelta(days=1)
    db.flush()


def _seed_business(db: Session, family_user: User) -> dict[str, object]:
    """The commercial side: price list, subscriptions, invoices, referral, orgs."""
    subscription_service.sync_plans(db)

    anchor = _billing_anchor()
    started = subscription_service.add_months(anchor, -SUBSCRIPTION_HISTORY_MONTHS)

    subscription = subscription_service.create(
        db,
        plan=subscription_service.get_plan(db, pricing.CARE_PLUS.code),
        family_user_id=family_user.id,
        cycle=BillingCycle.MONTHLY,
        started_at=started,
    )
    _bill_history(db, subscription, SUBSCRIPTION_HISTORY_MONTHS, settle_current=False)

    # Part of this period's allowance is spent, so the meters read like a month
    # in progress rather than an untouched plan.
    subscription_service.consume_quota(db, subscription, "visits", 2)
    subscription_service.consume_quota(db, subscription, "lab_panels", 1)

    # ---- a referral that converted ---------------------------------------
    referred_user = User(
        name="Meera Raghavan",
        email="meera@doordoctor.in",
        phone="+91 90000 00004",
        password_hash=hash_password(DEMO_PASSWORD),
        role=UserRole.FAMILY,
        is_active=True,
    )
    db.add(referred_user)
    db.flush()

    referred_subscription = subscription_service.create(
        db,
        plan=subscription_service.get_plan(db, pricing.ESSENTIAL.code),
        family_user_id=referred_user.id,
        cycle=BillingCycle.MONTHLY,
        started_at=subscription_service.add_months(anchor, -3),
    )
    referral_service.record_signup(
        db,
        code=subscription_service.ensure_referral_code(db, subscription),
        user=referred_user,
    )
    # Their first settled invoice is what pays the referrer, so the reward lands
    # here rather than being written in by hand.
    _bill_history(db, referred_subscription, 3)

    # ---- organization accounts -------------------------------------------
    corporate = Organization(
        name="Ashwin Technologies Pvt Ltd",
        org_type=OrganizationType.CORPORATE,
        seats=40,
        contact_name="Priya Nair",
        contact_email="benefits@ashwintech.example",
        contact_phone="+91 90000 00005",
        city="Bengaluru",
    )
    institution = Organization(
        name="Sandhya Senior Living",
        org_type=OrganizationType.INSTITUTION,
        seats=25,
        contact_name="Colonel R. Iyer (Retd)",
        contact_email="care@sandhyaliving.example",
        contact_phone="+91 90000 00006",
        city="Mysuru",
    )
    db.add_all([corporate, institution])
    db.flush()

    corporate_subscription = subscription_service.create(
        db,
        plan=subscription_service.get_plan(db, pricing.CORPORATE.code),
        organization_id=corporate.id,
        cycle=BillingCycle.MONTHLY,
        seats=corporate.seats,
        started_at=subscription_service.add_months(anchor, -6),
    )
    _bill_history(db, corporate_subscription, 6)

    institution_subscription = subscription_service.create(
        db,
        plan=subscription_service.get_plan(db, pricing.INSTITUTION_25.code),
        organization_id=institution.id,
        cycle=BillingCycle.MONTHLY,
        seats=institution.seats,
        started_at=subscription_service.add_months(anchor, -9),
    )
    _bill_history(db, institution_subscription, 9)

    db.flush()
    return {
        "subscription_id": subscription.id,
        "referral_code": subscription.referral_code,
        "paid_months": subscription.paid_months,
    }


def seed(db: Session) -> dict[str, object]:
    users: dict[UserRole, User] = {}
    for spec in DEMO_USERS:
        user = User(
            name=spec["name"],
            email=spec["email"],
            phone=spec["phone"],
            password_hash=hash_password(DEMO_PASSWORD),
            role=spec["role"],
            is_active=True,
        )
        db.add(user)
        users[spec["role"]] = user
    db.flush()

    nurse = Nurse(
        user_id=users[UserRole.NURSE].id,
        credential="RN/ANM",
        verification_status=VerificationStatus.VERIFIED,
        status=NurseStatus.ACTIVE,
    )
    db.add(nurse)

    patient = Patient(
        name="Lakshmi D'Souza",
        age=68,
        gender="Female",
        address="4th Block, Koramangala, Bengaluru 560034",
        emergency_contact="Darren D'Souza (son) - +91 90000 00001",
        family_user_id=users[UserRole.FAMILY].id,
        status=PatientStatus.ACTIVE,
    )
    db.add(patient)
    db.flush()

    for metric, (low, high) in THRESHOLDS.items():
        db.add(
            PatientThreshold(
                patient_id=patient.id,
                metric=metric,
                low_threshold=low,
                high_threshold=high,
                enabled=True,
            )
        )

    medications = [
        Medication(
            patient_id=patient.id,
            name=spec["name"],
            dosage=spec["dosage"],
            frequency=spec["frequency"],
            scheduled_time=spec["scheduled_time"],
            active=True,
        )
        for spec in MEDICATIONS
    ]
    db.add_all(medications)
    db.flush()

    # ---- historical completed visits -------------------------------------
    for index, (days_ago, sys_bp, dia_bp, hr, glucose, spo2, temp, weight) in enumerate(HISTORY):
        scheduled_at = _at(days_ago)
        visit = Visit(
            patient_id=patient.id,
            nurse_id=nurse.id,
            scheduled_at=scheduled_at,
            status=VisitStatus.COMPLETED,
            checkin_at=scheduled_at,
            checkout_at=scheduled_at + timedelta(minutes=45),
            location_source="demo/unverified",
            notes="Routine home visit completed. Patient comfortable and responsive.",
        )
        db.add(visit)
        db.flush()

        vital = Vital(
            patient_id=patient.id,
            visit_id=visit.id,
            systolic_bp=sys_bp,
            diastolic_bp=dia_bp,
            heart_rate=hr,
            blood_glucose=glucose,
            spo2=spo2,
            temperature=temp,
            weight=weight,
            recorded_at=scheduled_at + timedelta(minutes=12),
        )
        thresholds = list(patient.thresholds)
        vital.threshold_breached = bool(vitals_service.evaluate_thresholds(vital, thresholds))
        db.add(vital)

        for medication, status_value in zip(medications, ADHERENCE_PLAN[index]):
            db.add(
                MedicationLog(
                    medication_id=medication.id,
                    visit_id=visit.id,
                    status=MedicationLogStatus(status_value),
                    reason=SKIP_REASONS.get(status_value),
                    recorded_at=scheduled_at + timedelta(minutes=20),
                    recorded_by=users[UserRole.NURSE].id,
                )
            )

    # Three extra administered doses so adherence lands on 87%.
    for offset, status_value in enumerate(EXTRA_ADHERENCE_DOSES):
        db.add(
            MedicationLog(
                medication_id=medications[offset % len(medications)].id,
                visit_id=None,
                status=MedicationLogStatus(status_value),
                reason=None,
                recorded_at=_at(7 - offset, hour=20, minute=0),
                recorded_by=users[UserRole.NURSE].id,
            )
        )

    # ---- today's visit, left scheduled for the live demo ------------------
    today_visit = Visit(
        patient_id=patient.id,
        nurse_id=nurse.id,
        scheduled_at=_at(0, hour=10, minute=30),
        status=VisitStatus.SCHEDULED,
        location_source="demo/unverified",
    )
    db.add(today_visit)

    # ---- a second scheduled visit for admin screens -----------------
    db.add(
        Visit(
            patient_id=patient.id,
            nurse_id=nurse.id,
            scheduled_at=_at(-2, hour=10, minute=30),
            status=VisitStatus.SCHEDULED,
            location_source="demo/unverified",
        )
    )

    # ---- the commercial side (Phase 4) -----------------------------------
    business = _seed_business(db, users[UserRole.FAMILY])

    db.commit()

    return {
        "patient_id": patient.id,
        "nurse_id": nurse.id,
        "today_visit_id": today_visit.id,
        **business,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset and seed the DoorDoctor demo database.")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Do not drop existing tables (only useful for an empty database).",
    )
    args = parser.parse_args()

    print(f"Database: {settings.database_url}")
    if args.keep:
        Base.metadata.create_all(bind=engine)
    else:
        print("Resetting schema ...")
        reset_database()

    with SessionLocal() as db:
        result = seed(db)

    print("Demo data seeded.")
    print(f"  Patient : Lakshmi D'Souza (id={result['patient_id']})")
    print(f"  Nurse   : Anitha Kumar (id={result['nurse_id']})")
    print(f"  Today's visit id={result['today_visit_id']} (status=scheduled)")
    print(
        f"  Plan    : Care Plus, {result['paid_months']} paid months, "
        f"referral code {result['referral_code']}"
    )
    print()
    print("Demo accounts (password for all three: Demo@123)")
    print("  family@doordoctor.in - family member")
    print("  nurse@doordoctor.in  - nurse")
    print("  admin@doordoctor.in  - admin")
    print()
    print("Demo alert scenario: record 148/92 during today's visit to trigger the threshold engine.")


if __name__ == "__main__":
    main()
