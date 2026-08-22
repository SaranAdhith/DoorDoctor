"""What the marketing site is allowed to read without a login (§2.6).

There is exactly one endpoint here and it exists to keep a promise made in
Phase 4: **`core/pricing.py` is the only place a price is written down.**

The public pricing page could have had the prices typed into a `.tsx`. That is
the second source of truth and the first thing to go stale — a price changed in
`pricing.py`, the invoice PDF and the in-app plan picker following it, and the
page a customer actually buys from still quoting last quarter. So the page reads
them over the wire, from the same two functions the authenticated `/plans`
endpoint uses:

    subscription_service.list_plans  ->  subscription_service.serialize_plan

Not a second serializer, not a static blob — the same functions, minus the auth
dependency. `tests/test_public.py` asserts this payload's `plans` array is
byte-identical to authenticated `/plans`, so the two cannot drift, and separately
that the prices served equal `pricing.PLANS`.

Nothing else is served publicly. Plans and add-on prices are, by definition,
what DoorDoctor tells strangers; every other endpoint in the API concerns a
named person's health.
"""

from typing import Any

from fastapi import APIRouter, Query

from ..core import pricing
from ..core.dependencies import DbSession
from ..services import subscription_service

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/plans", summary="Published price list (public)")
def public_plans(
    db: DbSession,
    audience: str | None = Query(default=None, description="individual | corporate | institution"),
) -> dict[str, Any]:
    """Every sellable plan and every add-on, with no authentication.

    Add-ons come straight from `pricing.ADD_ONS` rather than the database
    because they are not `Plan` rows — nothing sells one yet (Phase 4 deferred
    the purchase flow to Phase 9). They are still published from the constants,
    so the page states no number of its own either way.
    """
    plans = [subscription_service.serialize_plan(plan) for plan in subscription_service.list_plans(db, audience)]
    return {
        "plans": plans,
        "add_ons": [
            {
                "code": add_on.code,
                "name": add_on.name,
                "price_paise": add_on.price_paise,
                "unit": add_on.unit,
            }
            for add_on in pricing.ADD_ONS
        ],
        # The annual price is "2 months free". The page says so in words; this is
        # where the words get their number, so the claim cannot outlive the offer.
        "annual_months_free": pricing.ANNUAL_MONTHS_FREE,
    }
