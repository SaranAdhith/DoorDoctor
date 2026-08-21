"""Reset and seed the DoorDoctor demo database.

    python -m app.seed

Drops every table, recreates the schema and loads the fictional demo dataset:
three accounts, one patient, one caregiver, a medication schedule, four
completed historical visits and one visit left `scheduled` so the evaluator can
run the live workflow.

All data is fictional. No real patient information is used.
"""

from __future__ import annotations

import argparse
from datetime import datetime, time, timedelta

from sqlalchemy.orm import Session

from .config import settings
from .database import Base, SessionLocal, engine, now
from .core.security import hash_password
from .models import (
    Caregiver,
    CaregiverStatus,
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
from .services import vitals_service

DEMO_PASSWORD = "Demo@123"

DEMO_USERS = [
    {
        "name": "Darren D'Souza",
        "email": "family@doordoc.demo",
        "phone": "+91 90000 00001",
        "role": UserRole.FAMILY,
    },
    {
        "name": "Anitha Kumar",
        "email": "caregiver@doordoc.demo",
        "phone": "+91 90000 00002",
        "role": UserRole.CAREGIVER,
    },
    {
        "name": "Ravi Menon",
        "email": "coordinator@doordoc.demo",
        "phone": "+91 90000 00003",
        "role": UserRole.COORDINATOR,
    },
]

# Historical readings, all inside the configured thresholds. The live demo
# supplies the out-of-range reading (148/92) through the caregiver UI.
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

    caregiver = Caregiver(
        user_id=users[UserRole.CAREGIVER].id,
        credential="RN/ANM",
        verification_status=VerificationStatus.VERIFIED,
        status=CaregiverStatus.ACTIVE,
    )
    db.add(caregiver)

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
            caregiver_id=caregiver.id,
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
                    recorded_by=users[UserRole.CAREGIVER].id,
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
                recorded_by=users[UserRole.CAREGIVER].id,
            )
        )

    # ---- today's visit, left scheduled for the live demo ------------------
    today_visit = Visit(
        patient_id=patient.id,
        caregiver_id=caregiver.id,
        scheduled_at=_at(0, hour=10, minute=30),
        status=VisitStatus.SCHEDULED,
        location_source="demo/unverified",
    )
    db.add(today_visit)

    # ---- a second scheduled visit for coordinator screens -----------------
    db.add(
        Visit(
            patient_id=patient.id,
            caregiver_id=caregiver.id,
            scheduled_at=_at(-2, hour=10, minute=30),
            status=VisitStatus.SCHEDULED,
            location_source="demo/unverified",
        )
    )

    db.commit()

    return {
        "patient_id": patient.id,
        "caregiver_id": caregiver.id,
        "today_visit_id": today_visit.id,
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
    print(f"  Patient   : Lakshmi D'Souza (id={result['patient_id']})")
    print(f"  Caregiver : Anitha Kumar (id={result['caregiver_id']})")
    print(f"  Today's visit id={result['today_visit_id']} (status=scheduled)")
    print()
    print("Demo accounts (password for all three: Demo@123)")
    print("  family@doordoc.demo       - family member")
    print("  caregiver@doordoc.demo    - caregiver")
    print("  coordinator@doordoc.demo  - care coordinator")
    print()
    print("Demo alert scenario: record 148/92 during today's visit to trigger the threshold engine.")


if __name__ == "__main__":
    main()
