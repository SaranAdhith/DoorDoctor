"""Where a check-in actually happened, and how sure we are.

RECORDED: a check-in is classified `verified`, `out_of_range` or `unavailable`
against a default 150 m geofence. This module is the arithmetic; every number it
applies comes from `core.ops`.

It contains **no policy and no numeric literal beyond the maths itself** — the
same split as `services/safety_score.py` against `core/clinical.py`, and for the
same reason: reconciling the real §4.11 must stay a one-file edit.

The classification is stored with the distance and the accuracy that produced
it, so `verified` is arithmetic a reader can re-run rather than a badge the
platform awarded itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..core.ops import (
    EARTH_RADIUS_M,
    GEOFENCE_ACCURACY_CEILING_M,
    GEOFENCE_ASSUME_ACCURACY_WHEN_MISSING,
    GEOFENCE_RADIUS_M,
)
from ..models import LocationStatus


@dataclass(frozen=True)
class LocationVerdict:
    status: LocationStatus
    distance_m: float | None
    accuracy_m: float | None
    source: str
    #: One sentence, family-readable. Rendered as-is; the UI invents nothing.
    detail: str


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres (haversine)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def classify(
    *,
    fix_lat: float | None,
    fix_lng: float | None,
    home_lat: float | None,
    home_lng: float | None,
    accuracy_m: float | None = None,
    radius_m: float = GEOFENCE_RADIUS_M,
) -> LocationVerdict:
    """Classify one check-in position.

    Three ways to land on `unavailable`, and each of them is a true statement
    rather than a failure:

    1. **No fix.** The phone gave nothing — permission denied, indoors, airplane
       mode. We do not know where the nurse was.
    2. **No home coordinates.** The patient's home was never located, so there is
       no circle to be inside. The fix is real; the reference point is missing.
    3. **A fix too vague to test the fence.** A +/-500 m position sitting 40 m
       from the door is not evidence that the nurse was at the door — it is
       evidence that the phone does not know. Calling that `verified` would be
       the platform lying about the one thing this feature exists to prove.
    """
    if fix_lat is None or fix_lng is None:
        return LocationVerdict(
            status=LocationStatus.UNAVAILABLE,
            distance_m=None,
            accuracy_m=None,
            source="none",
            detail="The nurse's device did not report a location for this check-in.",
        )

    if accuracy_m is None and not GEOFENCE_ASSUME_ACCURACY_WHEN_MISSING:  # pragma: no cover - config
        accuracy_m = GEOFENCE_ACCURACY_CEILING_M + 1

    if home_lat is None or home_lng is None:
        return LocationVerdict(
            status=LocationStatus.UNAVAILABLE,
            distance_m=None,
            accuracy_m=accuracy_m,
            source="browser",
            detail="This patient's home has no recorded location, so the check-in cannot be checked against it.",
        )

    measured = distance_m(fix_lat, fix_lng, home_lat, home_lng)

    if accuracy_m is not None and accuracy_m > GEOFENCE_ACCURACY_CEILING_M:
        return LocationVerdict(
            status=LocationStatus.UNAVAILABLE,
            distance_m=measured,
            accuracy_m=accuracy_m,
            source="browser",
            detail=(
                f"The device's location was only accurate to about {accuracy_m:.0f} m, "
                f"which is too vague to confirm a {radius_m:.0f} m radius."
            ),
        )

    if measured <= radius_m:
        return LocationVerdict(
            status=LocationStatus.VERIFIED,
            distance_m=measured,
            accuracy_m=accuracy_m,
            source="browser",
            detail=f"Checked in about {measured:.0f} m from the recorded home address.",
        )

    return LocationVerdict(
        status=LocationStatus.OUT_OF_RANGE,
        distance_m=measured,
        accuracy_m=accuracy_m,
        source="browser",
        detail=(
            f"Checked in about {measured:.0f} m away, outside the {radius_m:.0f} m radius "
            "set for this patient's home."
        ),
    )
