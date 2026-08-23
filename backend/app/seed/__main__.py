"""`python -m app.seed` — the entry point the README, the demo and CI all use.

It stays a package `__main__` rather than moving to a script, because
`tests/conftest.py` imports `seed` from `app.seed` and the two must not drift.
"""

from __future__ import annotations

import argparse

from ..config import settings
from ..database import Base, SessionLocal, engine
from . import FULL, SMALL, demo_reset, reset_database, seed


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset and seed the DoorDoctor demo database.")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Do not drop existing tables (only useful for an empty database).",
    )
    parser.add_argument(
        "--small",
        action="store_true",
        help="Seed only the demo core — three accounts, one patient, one nurse, "
        "and the full billing history. This is the dataset the test suite uses.",
    )
    parser.add_argument(
        "--demo-reset",
        action="store_true",
        help="Rewind the live demo path (today's 10:30 visit, its readings and its "
        "alerts) without touching users, billing or clinical history.",
    )
    args = parser.parse_args()

    print(f"Database: {settings.database_url}")

    if args.demo_reset:
        with SessionLocal() as db:
            changed = demo_reset(db)
        print("Demo path rewound.")
        print(f"  Removed  : {changed['alerts_removed']} alert(s), {changed['readings_removed']} reading(s)")
        print(f"  Ready    : visit id={changed['demo_visit_id']} at 10:30 (status=scheduled)")
        print()
        print("Record 148/92 during that visit to run the threshold engine again.")
        return

    if args.keep:
        Base.metadata.create_all(bind=engine)
    else:
        print("Resetting schema ...")
        reset_database()

    profile = SMALL if args.small else FULL
    with SessionLocal() as db:
        result = seed(db, profile)

    print(f"Demo data seeded ({result['profile']}).")
    print(f"  Patient : Lakshmi D'Souza (id={result['patient_id']})")
    print(f"  Nurse   : Anitha Kumar (id={result['nurse_id']})")
    print(f"  Today's visit id={result['today_visit_id']} (status=scheduled)")
    print(
        f"  Plan    : Care Plus, {result['paid_months']} paid months, "
        f"referral code {result['referral_code']}"
    )
    if profile.population:
        print(
            f"  Roster  : {result['patients']} patients, {result['nurses']} nurses, "
            f"{result['families']} families"
        )
        print(
            f"  Care    : {result['visits']} visits, {result['readings']} readings, "
            f"{result['doses']} logged doses"
        )
        print(
            f"  Alerts  : {result['alerts_resolved']} resolved, "
            f"{result['alerts_active']} still open"
        )
        print(f"  Leads   : {result['leads']} public enquiries waiting on Admin -> Leads")
        print(
            f"  Clinical: {result['lab_orders']} lab orders ({result['lab_abnormal']} abnormal), "
            f"{result['consults']} consults, {result['screenings']} mood checks"
        )
        print(
            f"  Care    : {result['care_managers']} care managers carrying "
            f"{result['care_assignments']} patients, {result['care_interactions']} logged contacts"
        )
        print(
            f"  Devices : {result['devices']} connected, {result['device_readings']} readings, "
            f"{result['device_breaches']} breach(es) -> the three documented actions"
        )
        print(
            f"  Urgent  : {result['hospital_bookings']} hospital requests, "
            f"{result['safety_scores']} safety scores on Admin -> Escalations"
        )
    print()
    print("Demo accounts (password for all of them: Demo@123)")
    print("  family@doordoctor.in - family member")
    print("  nurse@doordoctor.in  - nurse")
    print("  admin@doordoctor.in  - admin")
    print()
    print("Demo alert scenario: record 148/92 during today's visit to trigger the threshold engine.")


if __name__ == "__main__":
    main()
