"""Phase 10, stage 0 — the constants module, the append-only log, the file seam.

These are the promises the rest of the phase is built on. If one of them stops
holding, the features above it stop meaning what they say.
"""

import io
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from app.core import clinical, ops
from app.core.exceptions import BadRequestError
from app.models import AppendOnlyError, AuditAction, AuditEvent, User
from app.services import audit_service, storage


# --- core/ops.py ----------------------------------------------------------


def test_ops_imports_nothing_from_the_application():
    """`ops.py` is a leaf, exactly like `pricing.py` and `clinical.py`.

    It may read `core.clinical` — that module is a leaf too and the dependency
    runs one way — but an import of a model, a service or a router would let the
    constants depend on the code that reads them.
    """
    source = Path(ops.__file__).read_text()
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped.startswith(("import ", "from ")):
            continue
        assert not any(
            token in stripped for token in ("..models", "..services", "..routers", "..database", "app.")
        ), f"core/ops.py must not import from the application: {stripped}"


def test_ops_does_not_restate_a_clinical_sla():
    """The alert queue points at the clinical budgets; it does not copy them."""
    assert ops.ALERT_SLA_MINUTES is clinical.SLA_DURATIONS_MINUTES


def test_recorded_values_are_what_was_recorded():
    assert ops.GEOFENCE_RADIUS_M == 150.0
    assert ops.CRITICAL_CHANNEL_COUNT == 2
    assert (ops.BREAK_EVEN_MIN_SUBSCRIBERS, ops.BREAK_EVEN_MAX_SUBSCRIBERS) == (30, 45)
    assert ops.UPLOAD_DIR_NAME == "uploads"


def test_quiet_hours_can_never_silence_a_critical_alert():
    assert ops.QUIET_HOURS_NEVER_SUPPRESS_CRITICAL is True


def test_every_consent_and_onboarding_key_is_unique():
    assert len(ops.CONSENT_KINDS_BY_KEY) == len(ops.CONSENT_KINDS)
    assert len(ops.ONBOARDING_STEPS_BY_KEY) == len(ops.ONBOARDING_STEPS)


def test_at_least_one_consent_is_genuinely_optional():
    """A consent screen where everything is required is not asking anything."""
    assert any(not spec.required for spec in ops.CONSENT_KINDS)


def test_the_erasure_promise_states_its_exceptions():
    """Every retained category carries the reason it is retained."""
    assert ops.ERASURE_DESTROYS
    assert ops.ERASURE_RETAINS
    for label, reason in ops.ERASURE_RETAINS:
        assert label and reason and len(reason) > 20


# --- the append-only audit log --------------------------------------------


def test_audit_entry_cannot_be_updated(db: Session):
    entry = audit_service.record(
        db, action=AuditAction.RECORD_VIEWED, subject_type="patient", subject_id=1, patient_id=1
    )
    db.commit()

    entry.detail = "something else"
    with pytest.raises(AppendOnlyError):
        db.commit()
    db.rollback()


def test_audit_entry_cannot_be_deleted(db: Session):
    entry = audit_service.record(
        db, action=AuditAction.RECORD_VIEWED, subject_type="patient", subject_id=1, patient_id=1
    )
    db.commit()

    db.delete(entry)
    with pytest.raises(AppendOnlyError):
        db.commit()
    db.rollback()


def test_audit_record_joins_the_callers_transaction(db: Session):
    """An audited action that rolls back must not leave an entry claiming it happened."""
    before = len(audit_service.list_events(db))
    audit_service.record(
        db, action=AuditAction.CONSENT_GRANTED, subject_type="patient", subject_id=1, patient_id=1
    )
    db.rollback()
    assert len(audit_service.list_events(db)) == before


def test_audit_entry_survives_its_actor(db: Session):
    """An erasure can remove the account that requested it. The entry stays readable."""
    user = db.query(User).filter(User.email == "family@doordoctor.in").one()
    audit_service.record(
        db,
        actor=user,
        action=AuditAction.ERASURE_REQUESTED,
        subject_type="patient",
        subject_id=1,
        patient_id=1,
        detail="Requested erasure.",
    )
    db.commit()

    entry = db.query(AuditEvent).order_by(AuditEvent.id.desc()).first()
    assert entry is not None
    assert entry.actor_label == user.name  # frozen at write time, not a join


def test_a_family_reading_their_own_relatives_record_is_not_logged(db: Session):
    """Logging every family read would bury the entries that matter."""
    family = db.query(User).filter(User.email == "family@doordoctor.in").one()
    nurse = db.query(User).filter(User.email == "nurse@doordoctor.in").one()

    assert audit_service.record_view(db, actor=family, patient_id=1, what="the dashboard") is None
    assert audit_service.record_view(db, actor=nurse, patient_id=1, what="the dashboard") is not None


# --- the file seam --------------------------------------------------------


def _png(size: tuple[int, int] = (40, 30), colour: str = "red") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def test_storage_writes_under_the_configured_root_and_nowhere_else():
    stored = storage.store_image(_png())
    absolute = storage.resolve(stored.path)
    assert absolute.is_relative_to(storage.root())
    assert absolute.is_file()


def test_storage_is_content_addressed():
    first = storage.store_image(_png())
    second = storage.store_image(_png())
    assert first.sha256 == second.sha256
    assert first.path == second.path


def test_storage_rejects_a_file_that_is_not_an_image():
    with pytest.raises(BadRequestError):
        storage.store_image(b"GIF89a-not-really-an-image")


def test_storage_rejects_an_empty_upload():
    with pytest.raises(BadRequestError):
        storage.store_image(b"")


def test_storage_rejects_a_file_over_the_cap():
    with pytest.raises(BadRequestError):
        storage.store_image(b"\x89PNG" + b"0" * ops.PHOTO_MAX_BYTES)


def test_storage_strips_exif():
    """A dose photo carries the patient's home GPS until this runs."""
    image = Image.new("RGB", (60, 40), "blue")
    exif = image.getexif()
    exif[0x9286] = "user comment that must not survive"  # UserComment
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    assert b"user comment that must not survive" in buffer.getvalue()

    stored = storage.store_image(buffer.getvalue())
    written = storage.read(stored.path)
    assert b"user comment that must not survive" not in written
    assert not Image.open(io.BytesIO(written)).getexif()


def test_storage_shrinks_an_oversized_image():
    stored = storage.store_image(_png(size=(3000, 2000)))
    assert max(stored.width, stored.height) <= ops.PHOTO_MAX_EDGE_PX


def test_storage_refuses_a_path_that_escapes_the_root():
    with pytest.raises(BadRequestError):
        storage.resolve("../../../etc/passwd")


def test_storage_delete_reports_whether_anything_was_there():
    stored = storage.store_image(_png(colour="green"))
    assert storage.delete(stored.path) is True
    assert storage.delete(stored.path) is False


def test_the_application_mounts_no_static_files():
    """RECORDED: uploads are never served statically. This is how that is kept."""
    from fastapi.staticfiles import StaticFiles

    from app.main import app

    assert not any(isinstance(getattr(route, "app", None), StaticFiles) for route in app.routes)
