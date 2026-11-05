"""A PDF's structure, and the text its pages already carry.

A born-digital PDF — most lab portals' downloads — has an exact text layer.
Reading it costs nothing, is instant and cannot misread a digit, so it is
always tried first and OCR only sees the pages it leaves empty.

`pypdf` is imported inside the functions, not at module load, so a missing
package degrades an upload to a clear error instead of breaking app start-up.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from ...core.exceptions import BadRequestError
from ...core.intelligence import DOCUMENT_MAX_PAGES

logger = logging.getLogger("doordoctor.documents")


@dataclass(frozen=True)
class PdfInfo:
    page_count: int


def inspect(data: bytes) -> PdfInfo:
    """Check a PDF can be processed at all. Raises `BadRequestError` with a reason
    the uploader can act on; never one that leaks a parser's internals."""
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        raise BadRequestError("PDF uploads are not available on this server.") from exc

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise BadRequestError(
                "This PDF is password-protected. Please upload a copy without a password."
            )
        page_count = len(reader.pages)
    except BadRequestError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise BadRequestError("That PDF could not be opened. It may be damaged.") from exc
    except Exception as exc:  # noqa: BLE001 — a malformed file must never be a 500
        logger.info("pdf inspect failed: %s", type(exc).__name__)
        raise BadRequestError("That PDF could not be opened. It may be damaged.") from exc

    if page_count == 0:
        raise BadRequestError("That PDF has no pages.")
    if page_count > DOCUMENT_MAX_PAGES:
        raise BadRequestError(f"Documents can have at most {DOCUMENT_MAX_PAGES} pages.")
    return PdfInfo(page_count=page_count)


def page_texts(data: bytes) -> list[str]:
    """The text layer of every page, in order. A page that fails to extract is
    an empty string — it then goes to OCR like a scan would — never an error."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    texts: list[str] = []
    for page in reader.pages:
        try:
            texts.append((page.extract_text() or "").strip())
        except Exception as exc:  # noqa: BLE001 — one bad page must not sink the rest
            logger.info("pdf page text failed: %s", type(exc).__name__)
            texts.append("")
    return texts
