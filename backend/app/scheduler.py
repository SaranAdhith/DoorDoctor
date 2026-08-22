"""Scheduled report generation (§4.1).

APScheduler runs two cron jobs in a background thread inside the API process.
That is right for this build — one process, one machine, a demo that must work
from a single `uvicorn` command. A production deployment with more than one
replica would move these to a worker, because two replicas would otherwise both
wake up on Sunday evening.

The job *bodies* live in `report_service` and are plain functions that take a
session. This module is wiring, and wiring is not what needs proving: the tests
call `report_service.run_weekly(db)` directly.
"""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .database import SessionLocal
from .services import report_service

logger = logging.getLogger("doordoctor.scheduler")

IST = ZoneInfo("Asia/Kolkata")

_scheduler: BackgroundScheduler | None = None


def _weekly_job() -> None:
    """Sunday 18:00 IST — the week that ends today."""
    with SessionLocal() as db:
        report_service.run_weekly(db)


def _monthly_job() -> None:
    """The 1st at 06:00 IST — the calendar month that just ended."""
    with SessionLocal() as db:
        report_service.run_monthly(db)


def start() -> None:
    """Start the background scheduler, unless it is switched off.

    Switched off under tests: `TestClient` as a context manager runs the
    lifespan, and a suite must not start a background thread per client fixture.
    """
    global _scheduler

    if not settings.reports_scheduler_enabled:
        logger.info("Report scheduler disabled by configuration")
        return
    if _scheduler is not None:  # pragma: no cover - defensive against a double start
        return

    _scheduler = BackgroundScheduler(timezone=IST)
    _scheduler.add_job(
        _weekly_job,
        CronTrigger(day_of_week="sun", hour=18, minute=0, timezone=IST),
        id="weekly-reports",
        replace_existing=True,
        # A laptop asleep at 18:00 on Sunday should still produce the report when
        # it wakes, but only once, and only if it is still that evening.
        misfire_grace_time=6 * 60 * 60,
        coalesce=True,
    )
    _scheduler.add_job(
        _monthly_job,
        CronTrigger(day=1, hour=6, minute=0, timezone=IST),
        id="monthly-reports",
        replace_existing=True,
        misfire_grace_time=12 * 60 * 60,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Report scheduler started (weekly Sun 18:00 IST, monthly 1st 06:00 IST)")


def shutdown() -> None:
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Report scheduler stopped")
