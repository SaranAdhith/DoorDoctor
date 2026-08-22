"""Connected device registration and wearable ingest (§4.8).

`POST /ingest/device-readings` is the only endpoint in this codebase
authenticated by something other than a bearer token, and it is treated with the
same suspicion as `POST /leads`: capped payload, per-device rate limit, and a
response that carries counts and nothing about the patient.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Header, Request, status

from ..core import clinical
from ..core.dependencies import (
    AdminUser,
    CurrentUser,
    DbSession,
    FamilyOrAdminUser,
    authorize_patient,
)
from ..core.ratelimit import DEVICE_INGEST_PER_DEVICE, limiter
from ..schemas.device import (
    DeviceCreate,
    DeviceOut,
    DeviceReadingOut,
    DeviceRegistered,
    IngestAccepted,
    IngestIn,
)
from ..services import device_service

router = APIRouter(tags=["devices"])


@router.post(
    "/patients/{patient_id}/devices",
    response_model=DeviceRegistered,
    status_code=status.HTTP_201_CREATED,
    summary="Register a connected device (family or admin)",
)
def register_device(
    patient_id: int, payload: DeviceCreate, current_user: FamilyOrAdminUser, db: DbSession
) -> dict[str, Any]:
    """The response carries the plaintext key **once**. It cannot be read back."""
    patient = authorize_patient(db, current_user, patient_id)
    device, raw_key = device_service.register(
        db, patient=patient, kind=payload.kind, label=payload.label, serial=payload.serial
    )
    db.commit()
    db.refresh(device)
    return {**device_service.serialize(device), "api_key": raw_key}


@router.get(
    "/patients/{patient_id}/devices",
    response_model=list[DeviceOut],
    summary="Devices connected for a patient",
)
def list_devices(patient_id: int, current_user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    patient = authorize_patient(db, current_user, patient_id)
    return [device_service.serialize(d) for d in device_service.list_for_patient(db, patient.id)]


@router.get(
    "/patients/{patient_id}/device-readings",
    response_model=list[DeviceReadingOut],
    summary="Readings a patient's devices have sent",
)
def list_readings(patient_id: int, current_user: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    patient = authorize_patient(db, current_user, patient_id)
    return [
        device_service.serialize_reading(r)
        for r in device_service.readings_for_patient(db, patient.id)
    ]


@router.post(
    "/devices/{device_id}/rotate-key",
    response_model=DeviceRegistered,
    summary="Issue a new device key (family or admin)",
)
def rotate_device_key(
    device_id: int, current_user: FamilyOrAdminUser, db: DbSession
) -> dict[str, Any]:
    device = device_service.get_for_user(db, current_user, device_id)
    raw_key = device_service.rotate_key(db, device)
    db.commit()
    db.refresh(device)
    return {**device_service.serialize(device), "api_key": raw_key}


@router.post(
    "/devices/{device_id}/deactivate",
    response_model=DeviceOut,
    summary="Stop accepting readings from a device (family or admin)",
)
def deactivate_device(
    device_id: int, current_user: FamilyOrAdminUser, db: DbSession
) -> dict[str, Any]:
    device = device_service.get_for_user(db, current_user, device_id)
    device_service.deactivate(db, device)
    db.commit()
    db.refresh(device)
    return device_service.serialize(device)


@router.post(
    "/ingest/device-readings",
    response_model=IngestAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Push readings from a device (device key)",
)
def ingest_readings(
    payload: IngestIn,
    request: Request,
    db: DbSession,
    x_device_key: Annotated[str | None, Header(alias="X-Device-Key")] = None,
) -> dict[str, Any]:
    """Authenticated by `X-Device-Key`, not a bearer token.

    The device is resolved **before** the limiter runs, so the budget is spent
    per device rather than per source address — a fleet behind one household
    router must not exhaust each other's budgets, and an unknown key must not be
    able to consume a real device's.
    """
    device = device_service.authenticate(db, x_device_key)

    limit, window = DEVICE_INGEST_PER_DEVICE
    limiter.check("device:ingest", str(device.id), limit=limit, per_seconds=window)

    result = device_service.ingest(
        db,
        device,
        [
            {"metric": r.metric, "value": r.value, "recorded_at": r.recorded_at}
            for r in payload.readings
        ],
    )
    db.commit()
    return result
