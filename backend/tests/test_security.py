"""The password hashing primitives themselves.

`test_auth.py` and `test_password_reset.py` exercise hashing through the API.
This file guards the one property neither of them can see: that the cost factor
the suite lowers for its own speed is *only* lowered for the suite.
"""

import bcrypt

from app.config import Settings, settings
from app.core.security import hash_password, verify_password

PRODUCTION_BCRYPT_ROUNDS = 12


def test_production_bcrypt_cost_is_twelve():
    """The default must stay 12 however low the suite sets its own.

    Read off the field default rather than off `settings`, because `settings` is
    what conftest has already overridden — asserting on it would only prove the
    suite configured itself.
    """
    assert Settings.model_fields["bcrypt_rounds"].default == PRODUCTION_BCRYPT_ROUNDS


def test_the_suite_runs_at_a_reduced_cost():
    """The speedup is deliberate, not an accident of an unset variable.

    If this fails, the suite has silently gone back to ~0.73s per password
    verify and roughly six minutes of the run is bcrypt.
    """
    assert settings.bcrypt_rounds < PRODUCTION_BCRYPT_ROUNDS


def test_the_configured_cost_reaches_the_hash():
    """A bcrypt hash encodes its own cost, so the setting is checkable."""
    digest = hash_password("Demo@123")
    assert digest.startswith(f"$2b${settings.bcrypt_rounds:02d}$")


def test_a_hash_verifies_regardless_of_the_cost_it_was_made_at():
    """Lowering the factor must not invalidate anything already stored.

    This is what makes the setting safe: a password hashed at 12 in a real
    deployment still verifies in a process configured for 4, and vice versa, so
    the two never have to agree.
    """
    payload = b"Demo@123"
    at_twelve = bcrypt.hashpw(payload, bcrypt.gensalt(rounds=PRODUCTION_BCRYPT_ROUNDS)).decode()

    assert verify_password("Demo@123", at_twelve)
    assert not verify_password("Demo@124", at_twelve)


def test_verify_rejects_a_malformed_hash_instead_of_raising():
    """A corrupt stored hash is a failed login, never a 500."""
    assert not verify_password("Demo@123", "not-a-bcrypt-hash")
    assert not verify_password("Demo@123", "")
