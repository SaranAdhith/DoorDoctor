"""The queue that turns an uploaded document into pages of text.

The queue is the `documents.status` column, not an in-memory list, so it
survives a restart, can be retried from the admin screen, and is visible to
anyone looking at the table. Three entry points share one implementation:

- the scheduler job (`scheduler.py`, every `WORKER_INTERVAL_SECONDS`),
- `python -m app.intelligence.documents.worker --once` / `--loop`, for running
  next to a laptop's Chandra server,
- `process(db, document)` directly, which is what the tests call.

Per page, cheapest exact source first:

    text layer ≥ TEXT_LAYER_MIN_CHARS   → `text_layer`   (exact)
    else render → OCR engine → text     → `ocr`          (an engine's reading)
    else                                → `none`         (needs manual entry)

A document ends `extracted` when every page has text, `needs_manual` when any
page has none, and `failed` only when the file itself could not be processed —
after `EXTRACTION_MAX_ATTEMPTS`, with a reason a person can act on.

Claiming is a conditional UPDATE (`… WHERE status = 'uploaded'`), so the
scheduler and a CLI worker running at once never process the same document.
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ...core.intelligence import (
    EXTRACTION_MAX_ATTEMPTS,
    EXTRACTION_STALE_MINUTES,
    TEXT_LAYER_MIN_CHARS,
    WORKER_INTERVAL_SECONDS,
)
from ...database import SessionLocal, now
from ...models import Document, DocumentPage, DocumentStatus, PageMethod
from ...services import storage
from . import extraction, notify, ocr_engine, pdf_text, render

logger = logging.getLogger("doordoctor.documents")

_TEXT_LAYER_ENGINE = "pypdf"


def requeue_stale(db: Session) -> int:
    """Documents left in `extracting` by a process that died mid-way go back in
    the queue. Returns how many."""
    cutoff = now() - timedelta(minutes=EXTRACTION_STALE_MINUTES)
    result = db.execute(
        update(Document)
        .where(
            Document.status == DocumentStatus.EXTRACTING,
            Document.processing_started_at < cutoff,
        )
        .values(status=DocumentStatus.UPLOADED)
    )
    db.commit()
    return result.rowcount or 0


def claim(db: Session, document_id: int) -> bool:
    """Atomically move one document from `uploaded` to `extracting`."""
    result = db.execute(
        update(Document)
        .where(Document.id == document_id, Document.status == DocumentStatus.UPLOADED)
        .values(
            status=DocumentStatus.EXTRACTING,
            processing_started_at=now(),
            attempts=Document.attempts + 1,
        )
    )
    db.commit()
    return (result.rowcount or 0) == 1


def _page(document: Document, page_no: int, method: PageMethod, text: str, engine: str | None,
          elapsed_ms: int | None) -> DocumentPage:
    return DocumentPage(
        document_id=document.id,
        page_no=page_no,
        method=method,
        text=text,
        char_count=len(text),
        engine=engine,
        elapsed_ms=elapsed_ms,
    )


def _ocr(engine: ocr_engine.OcrEngine, image: bytes, content_type: str) -> ocr_engine.OcrResult | None:
    # The engine contract is "never raises"; this is the belt to that brace, so
    # a buggy engine costs one page and not the document.
    try:
        return engine.extract(image, content_type=content_type)
    except Exception as exc:  # noqa: BLE001
        logger.info("OCR engine raised %s; page left for manual entry", type(exc).__name__)
        return None


def _read_pages(document: Document, data: bytes) -> list[DocumentPage]:
    engine = ocr_engine.get_engine()

    if not storage.is_pdf(data):
        result = _ocr(engine, data, document.attachment.content_type)
        if result is None:
            return [_page(document, 1, PageMethod.NONE, "", engine.name, None)]
        return [_page(document, 1, PageMethod.OCR, result.text, result.engine, result.elapsed_ms)]

    pages: list[DocumentPage] = []
    for index, layer in enumerate(pdf_text.page_texts(data)):
        page_no = index + 1
        if len(layer) >= TEXT_LAYER_MIN_CHARS:
            pages.append(_page(document, page_no, PageMethod.TEXT_LAYER, layer, _TEXT_LAYER_ENGINE, None))
            continue

        result = None
        if not isinstance(engine, ocr_engine.NullEngine):
            try:
                image = render.render_page(data, index)
            except Exception as exc:  # noqa: BLE001 — one unrenderable page, not the file
                logger.info("page render failed: %s", type(exc).__name__)
                image = None
            if image is not None:
                result = _ocr(engine, image, "image/png")

        if result is not None:
            pages.append(_page(document, page_no, PageMethod.OCR, result.text, result.engine, result.elapsed_ms))
        else:
            # Keep whatever scrap the text layer had: a page number or a header
            # is still something for the person entering it by hand.
            pages.append(_page(document, page_no, PageMethod.NONE, layer, None, None))
    return pages


def process(db: Session, document: Document) -> Document:
    """Read every page of one claimed document. Never raises for a bad file."""
    try:
        data = storage.read(document.attachment.path)
        pages = _read_pages(document, data)
    except Exception as exc:  # noqa: BLE001 — a corrupt upload must not kill the worker
        db.rollback()
        logger.info("document %d failed: %s", document.id, type(exc).__name__)
        document = db.get(Document, document.id)
        if document.attempts >= EXTRACTION_MAX_ATTEMPTS:
            document.status = DocumentStatus.FAILED
            document.error = "The file could not be read. Please upload it again or enter it by hand."
            notify.document_event(db, document, notify.Event.FAILED)
        else:
            document.status = DocumentStatus.UPLOADED  # retried on the next tick
        db.commit()
        return document

    # A re-run replaces the pages rather than appending a second set.
    # `delete-orphan` removes the old rows; the flush between keeps the
    # (document_id, page_no) unique constraint from seeing both sets at once.
    document.pages.clear()
    db.flush()
    document.pages.extend(pages)

    db.flush()

    # Stage 2: propose facts from the text just read. A failure here costs the
    # facts, never the pages — the admin can still read the text and add facts
    # by hand, or press "Extract again" once the cause is fixed.
    # A savepoint, so a half-finished extraction rolls back alone and the pages
    # already flushed above are kept.
    try:
        with db.begin_nested():
            extraction.extract_document(db, document)
    except Exception as exc:  # noqa: BLE001
        logger.info("fact extraction failed for document %d: %s", document.id, type(exc).__name__)

    document.page_count = len(pages)
    document.status = (
        DocumentStatus.NEEDS_MANUAL
        if any(page.method == PageMethod.NONE for page in pages)
        else DocumentStatus.EXTRACTED
    )
    document.error = None
    document.extracted_at = now()
    notify.document_event(db, document, notify.Event.READ)
    db.commit()
    db.refresh(document)
    return document


def process_next(db: Session) -> Document | None:
    """Claim and process the oldest waiting document, if there is one."""
    candidates = db.scalars(
        select(Document.id)
        .where(Document.status == DocumentStatus.UPLOADED)
        .order_by(Document.created_at, Document.id)
        .limit(5)
    ).all()
    for document_id in candidates:
        if claim(db, document_id):
            document = db.get(Document, document_id)
            db.refresh(document)
            return process(db, document)
    return None


def run_once(max_documents: int = 10) -> int:
    """One worker tick in its own session. Returns how many documents it handled."""
    handled = 0
    with SessionLocal() as db:
        requeue_stale(db)
        while handled < max_documents and process_next(db) is not None:
            handled += 1
    return handled


def scheduled_tick() -> None:
    """The scheduler's entry point. A failing tick is logged, never propagated —
    APScheduler would otherwise log a stack trace every 30 seconds."""
    try:
        run_once()
    except Exception as exc:  # noqa: BLE001
        logger.warning("document worker tick failed: %s", type(exc).__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read the text of uploaded documents.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="process the waiting queue, then exit")
    mode.add_argument("--loop", action="store_true", help="keep polling (Ctrl+C to stop)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    engine = ocr_engine.get_engine()
    print(f"OCR engine: {engine.name}")

    if not args.loop:
        print(f"Processed {run_once(max_documents=1000)} document(s).")
        return 0
    try:
        while True:
            handled = run_once()
            if handled:
                print(f"Processed {handled} document(s).")
            time.sleep(WORKER_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
