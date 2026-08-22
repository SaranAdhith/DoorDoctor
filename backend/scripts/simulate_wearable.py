#!/usr/bin/env python3
"""Push readings into DoorDoctor as if from a connected device (§4.8).

The hardware does not exist, so this stands in for it. It speaks the real
ingest endpoint with a real device key over HTTP — nothing here reaches into the
database, which is the point: if this works, a device works.

Usage
-----
Register a device first (as the family or an admin) and keep the key the
response prints once:

    curl -X POST http://localhost:8000/api/v1/patients/1/devices \
      -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
      -d '{"kind":"pulse_oximeter","label":"Bedside oximeter","serial":"OX-001"}'

Then:

    # A quiet hour of normal readings
    python scripts/simulate_wearable.py --key dd_dev_... --minutes 30

    # The demo: an oxygen level of 88, which fires the three recorded actions
    python scripts/simulate_wearable.py --key dd_dev_... --breach

`--breach` sends one SpO2 below the recorded 90% floor. Watch the family's
alerts, the admin escalation queue and the task list all move at once.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

DEFAULT_BASE = "http://localhost:8000/api/v1"

# Ordinary resting values for a calm older adult. Not clinical constants — the
# clinical rules live in `backend/app/core/clinical.py` and this script never
# restates them; it just sends numbers and lets the server decide.
NORMAL_SPO2 = (95, 99)
NORMAL_HR = (62, 88)


def build_readings(minutes: int, breach: bool) -> list[dict[str, object]]:
    now = datetime.now()
    readings: list[dict[str, object]] = []

    for index in range(minutes):
        stamp = (now - timedelta(minutes=minutes - index)).isoformat()
        readings.append(
            {"metric": "spo2", "value": random.randint(*NORMAL_SPO2), "recorded_at": stamp}
        )
        readings.append(
            {"metric": "heart_rate", "value": random.randint(*NORMAL_HR), "recorded_at": stamp}
        )

    if breach:
        readings.append(
            {"metric": "spo2", "value": 88, "recorded_at": now.isoformat()}
        )

    return readings


def post(base: str, key: str, readings: list[dict[str, object]]) -> dict[str, object]:
    request = urllib.request.Request(
        f"{base.rstrip('/')}/ingest/device-readings",
        data=json.dumps({"readings": readings}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Device-Key": key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", required=True, help="the device key printed at registration")
    parser.add_argument("--base", default=DEFAULT_BASE, help=f"API base (default {DEFAULT_BASE})")
    parser.add_argument("--minutes", type=int, default=10, help="minutes of normal readings")
    parser.add_argument(
        "--breach",
        action="store_true",
        help="append one low oxygen reading, firing the three recorded actions",
    )
    args = parser.parse_args()

    readings = build_readings(max(0, args.minutes), args.breach)
    if not readings:
        print("Nothing to send. Use --minutes or --breach.", file=sys.stderr)
        return 2

    try:
        result = post(args.base, args.key, readings)
    except urllib.error.HTTPError as error:
        # The server's message, not a guess at what went wrong.
        print(f"Refused ({error.code}): {error.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"Could not reach {args.base}: {error.reason}", file=sys.stderr)
        return 1

    print(
        f"Sent {len(readings)} reading(s): "
        f"{result['accepted']} accepted, {result['skipped']} skipped, "
        f"{result['triggered']} triggered."
    )
    for action in result.get("actions", []):
        print(f"  action: {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
