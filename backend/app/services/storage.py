"""The only code in this repository that writes a file to disk.

RECORDED: uploads live under `backend/app/uploads/` and are **never served
statically**. Keeping every write behind one module is what makes that
enforceable — the authenticated fetch route, the size cap, the format check and
the erasure sweep are each written once, and a test asserts the application
mounts no `StaticFiles` at all.

Files are **content-addressed**: the stored name is the sha256 of the stored
bytes, so re-uploading the same photograph does not make a second copy, and a
row that references a file can be checked against the file itself.

Every image is re-encoded on the way in. That is not a size optimisation — a
dose photo taken in the patient's living room carries the patient's home GPS in
its EXIF, and re-encoding drops the metadata entirely. It also means the format
is decided by what Pillow could actually decode, never by what the client
claimed in a `Content-Type` header.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from ..config import settings
from ..core.exceptions import BadRequestError
from ..core.ops import (
    PHOTO_ALLOWED_FORMATS,
    PHOTO_MAX_BYTES,
    PHOTO_MAX_EDGE_PX,
    PHOTO_OUTPUT_FORMAT,
    PHOTO_OUTPUT_QUALITY,
)
from ..database import now


@dataclass(frozen=True)
class StoredFile:
    """What a caller needs to write an `Attachment` row."""

    path: str  # relative to the upload root, always forward-slashed
    sha256: str
    content_type: str
    size_bytes: int
    width: int
    height: int


def root() -> Path:
    """The upload root, resolved. Read through a function, not captured at import,
    so a test that repoints `UPLOAD_ROOT` is obeyed."""
    return Path(settings.upload_root).resolve()


def store_image(data: bytes, *, at: datetime | None = None) -> StoredFile:
    """Validate, strip metadata, re-encode and write. Raises `BadRequestError`."""
    if not data:
        raise BadRequestError("The uploaded file was empty.")
    if len(data) > PHOTO_MAX_BYTES:
        raise BadRequestError(f"Photos must be under {PHOTO_MAX_BYTES // (1024 * 1024)} MB.")

    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()  # structural check; consumes the file object
        source_format = (probe.format or "").upper()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise BadRequestError("That file is not an image we can read.") from exc

    if source_format not in PHOTO_ALLOWED_FORMATS:
        allowed = ", ".join(sorted(PHOTO_ALLOWED_FORMATS))
        raise BadRequestError(f"Photos must be one of: {allowed}.")

    # Reopened because `verify()` leaves the first handle unusable.
    image = Image.open(io.BytesIO(data))
    image = image.convert("RGB")
    image.thumbnail((PHOTO_MAX_EDGE_PX, PHOTO_MAX_EDGE_PX))

    buffer = io.BytesIO()
    # No `exif=` argument and no `icc_profile=`: everything the camera attached
    # is left behind here, which is the point.
    image.save(buffer, format=PHOTO_OUTPUT_FORMAT, quality=PHOTO_OUTPUT_QUALITY, optimize=True)
    encoded = buffer.getvalue()

    digest = hashlib.sha256(encoded).hexdigest()
    stamp = at or now()
    relative = f"{stamp:%Y/%m}/{digest}.jpg"

    destination = root() / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():  # content-addressed: identical bytes, one file
        destination.write_bytes(encoded)

    return StoredFile(
        path=relative,
        sha256=digest,
        content_type="image/jpeg",
        size_bytes=len(encoded),
        width=image.width,
        height=image.height,
    )


def resolve(relative: str) -> Path:
    """Absolute path for a stored file, refusing anything outside the root.

    The paths this module writes are generated, not user-supplied — but `read`
    and `delete` take whatever a database row holds, and a row is not a
    guarantee. The containment check is cheap and the failure it prevents is not.
    """
    candidate = (root() / relative).resolve()
    if not candidate.is_relative_to(root()):
        raise BadRequestError("That file is not available.")
    return candidate


def read(relative: str) -> bytes:
    path = resolve(relative)
    if not path.is_file():
        raise BadRequestError("That file is no longer stored.")
    return path.read_bytes()


def exists(relative: str) -> bool:
    try:
        return resolve(relative).is_file()
    except BadRequestError:  # pragma: no cover - defensive
        return False


def delete(relative: str) -> bool:
    """Remove a stored file. Returns whether anything was there.

    Used by erasure. Content addressing means two rows can point at one file, so
    callers delete only after the last row referencing the path is gone —
    `attachment_service.delete_for_patient` is the one place that decides.
    """
    try:
        path = resolve(relative)
    except BadRequestError:  # pragma: no cover - defensive
        return False
    if not path.is_file():
        return False
    path.unlink()
    return True
