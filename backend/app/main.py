"""DoorDoctor MVP API.

Academic prototype: alerts are configured monitoring thresholds, not medical
diagnoses. See the disclaimer in the README and DESIGN.md.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import scheduler
from .config import settings
from .database import create_all
from .routers import (
    admin,
    alerts,
    assistant,
    attachments,
    auth,
    billing,
    care,
    care_circle,
    consults,
    devices,
    escalations,
    labs,
    leads,
    medications,
    notifications,
    nurses,
    ops,
    patients,
    privacy,
    public,
    referrals,
    reports,
    safety,
    screenings,
    subscriptions,
    tasks,
    visits,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("doordoctor")

DESCRIPTION = """
DoorDoctor connects a scheduled nurse visit to the family that cannot be present.

**Workflow:** visit -> vitals -> threshold evaluation -> alert -> family visibility -> admin action.

Care is sold as a subscription: a plan carries entitlements and metered
allowances, periods roll over and invoice themselves, and referral and loyalty
rewards both settle as credits against the next invoice.

Families also get a plain-language summary of how their relative has been, and a
weekly and monthly report as a PDF. Both families and admins can ask an assistant
questions in their own words; it answers from a role-scoped context pack, never
from the database directly, and works with no API key configured.

Two endpoints need no authentication: the published price list under `/public`,
and lead capture from the marketing site. Everything else concerns a named
person's health and is behind a role-checked login.

Alerts describe readings that fall outside the patient's configured monitoring
thresholds. They are not medical diagnoses. No payment gateway is integrated in
this build and no money moves.
"""

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create tables on boot so a fresh checkout runs without a migration step."""
    create_all()
    scheduler.start()
    logger.info("DoorDoctor API ready (environment=%s)", settings.environment)
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(
    title="DoorDoctor API",
    description=DESCRIPTION,
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Turn Pydantic validation errors into a single human-readable `detail` string.

    Field values are not echoed back, so vitals never reach the logs or the error body.
    """
    messages: list[str] = []
    for error in exc.errors():
        location = [str(part) for part in error.get("loc", []) if part not in ("body", "query", "path")]
        field = ".".join(location) or "request"
        message = error.get("msg", "Invalid value.")
        message = message.removeprefix("Value error, ")
        messages.append(f"{field}: {message}")

    logger.info("Validation rejected request to %s (%d issue(s))", request.url.path, len(messages))
    return JSONResponse(status_code=422, content={"detail": " ".join(messages)})


@app.get("/health", tags=["system"], summary="Liveness probe")
def health() -> dict[str, str]:
    return {"status": "ok"}


api_prefix = settings.api_prefix
app.include_router(auth.router, prefix=api_prefix)
app.include_router(patients.router, prefix=api_prefix)
app.include_router(attachments.router, prefix=api_prefix)
app.include_router(visits.router, prefix=api_prefix)
app.include_router(medications.router, prefix=api_prefix)
app.include_router(alerts.router, prefix=api_prefix)
app.include_router(notifications.router, prefix=api_prefix)
app.include_router(admin.router, prefix=api_prefix)
app.include_router(nurses.router, prefix=api_prefix)
app.include_router(ops.router, prefix=api_prefix)
app.include_router(subscriptions.router, prefix=api_prefix)
app.include_router(billing.router, prefix=api_prefix)
app.include_router(referrals.router, prefix=api_prefix)
app.include_router(reports.router, prefix=api_prefix)
app.include_router(safety.router, prefix=api_prefix)
app.include_router(labs.router, prefix=api_prefix)
app.include_router(consults.router, prefix=api_prefix)
app.include_router(care.router, prefix=api_prefix)
app.include_router(care_circle.router, prefix=api_prefix)
app.include_router(privacy.router, prefix=api_prefix)
app.include_router(screenings.router, prefix=api_prefix)
app.include_router(devices.router, prefix=api_prefix)
app.include_router(escalations.router, prefix=api_prefix)
app.include_router(tasks.router, prefix=api_prefix)
app.include_router(assistant.router, prefix=api_prefix)
app.include_router(leads.router, prefix=api_prefix)
app.include_router(public.router, prefix=api_prefix)


@app.get("/", tags=["system"], summary="Service banner")
def root() -> dict[str, str]:
    return {
        "service": "DoorDoctor API",
        "docs": "/docs",
        "health": "/health",
        "disclaimer": "Monitoring prototype. Alerts are threshold events, not medical diagnoses.",
    }
