"""The only way an uploaded file leaves this server.

RECORDED: uploads are **never served statically**. There is no `StaticFiles`
mount anywhere in this application — `tests/test_ops_foundations.py` asserts
that — and this route is the alternative: the bytes are streamed only after the
caller passes exactly the same `authorize_patient` check that guards the
patient's readings, and with `Content-Disposition: inline` and a nosniff header
so a stored file cannot be talked into executing in a browser.
"""

from fastapi import APIRouter, Response

from ..core.dependencies import CurrentUser, DbSession, authorize_patient
from ..core.exceptions import NotFoundError
from ..models import Attachment
from ..services import attachment_service

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("/{attachment_id}", summary="Fetch an uploaded file", response_class=Response)
def fetch(attachment_id: int, db: DbSession, current_user: CurrentUser) -> Response:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise NotFoundError("File not found.")

    # Raises 404 for a patient this user may not see, so probing ids tells an
    # attacker nothing about what exists.
    authorize_patient(db, current_user, attachment.patient_id)

    return Response(
        content=attachment_service.read(attachment),
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
            # A dose photograph is a health record. It may sit in the browser's
            # memory cache for the tab's lifetime and nowhere else.
            "Cache-Control": "private, no-store",
        },
    )
