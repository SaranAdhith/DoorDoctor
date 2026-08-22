"""Reset and seed the DoorDoctor demo database.

    python -m app.seed              # the full operating business
    python -m app.seed --small      # the demo core only, as the test suite uses
    python -m app.seed --demo-reset # rewind today's board, keep everything else
    python -m app.seed --keep       # do not drop existing tables

Two profiles are built by one code path. `SMALL` is the Phase-4 dataset exactly —
three accounts, one patient, one nurse, and fourteen months of billing history —
and is what `tests/conftest.py` seeds, because 183 tests assert against it by
hand. `FULL` is `SMALL` **plus** the wider population: three admins, fourteen
nurses, twenty-eight patients across six Bangalore zones, eighteen families,
ninety days of visits, readings and doses, and an alert queue with thirty
resolved and four open.

The billing history is produced by calling the real services, not by writing
rows. If the loyalty rule or the credit arithmetic breaks, the seed shows it.

All data is fictional. No real patient information is used. No payment gateway
is integrated and no money moves.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..database import Base, engine
from . import business, core, population
from .demo_data import DEMO_PASSWORD, FULL, SMALL, SeedProfile
from .reset import demo_reset

__all__ = [
    "DEMO_PASSWORD",
    "FULL",
    "SMALL",
    "SeedProfile",
    "demo_reset",
    "reset_database",
    "seed",
]


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed(db: Session, profile: SeedProfile = FULL) -> dict[str, object]:
    """Load the demo dataset and commit it.

    Order matters in one place: `business.seed_business` must run before the
    population, because the demo family's subscription has to be the *first*
    family subscription created — `test_seeded_history_earned_exactly_one_loyalty
    _reward` selects it by id order.
    """
    result = core.build_core(db)
    business_info = business.seed_business(db, result.family_user)

    extras: dict[str, object] = {}
    if profile.population:
        extras = population.build(db, result, profile)

    db.commit()

    return {
        "profile": profile.name,
        "patient_id": result.patient.id,
        "nurse_id": result.nurse.id,
        "today_visit_id": result.today_visit.id,
        **business_info,
        **extras,
    }
