"""Every number the intelligence layers apply (Phase 12).

The same rule as `core/clinical.py` and `core/ops.py`: the modules under
`app/intelligence/` contain arithmetic and plumbing, and **no policy literal**.
Changing how big an upload may be, or when a page counts as having a text layer,
is a one-line edit here.

This module imports nothing from the application, so it can be read (and
tested) without a database, a settings object or a model.

Grows stage by stage. Stage 1 (document ingestion) is below; the later layers
add their own sections.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------
# Layer 1a — document ingestion
# --------------------------------------------------------------------------

#: ASSUMED — a 30-page scanned discharge summary at phone-camera quality.
DOCUMENT_MAX_BYTES: Final = 15 * 1024 * 1024

#: ASSUMED — longer than any lab report or prescription; short enough that one
#: upload can't hold the OCR worker for an afternoon.
DOCUMENT_MAX_PAGES: Final = 30

#: What Pillow must decode an image upload as. Never the client's Content-Type.
DOCUMENT_IMAGE_FORMATS: Final[frozenset[str]] = frozenset({"JPEG", "PNG", "WEBP"})

#: Document photos are kept far larger than dose photos (1600 px): a
#: prescription has to stay legible to OCR, not just recognisable to a person.
DOCUMENT_IMAGE_MAX_EDGE_PX: Final = 3000
DOCUMENT_IMAGE_QUALITY: Final = 92

#: A PDF counts as one only if this marker appears in its first KiB, which is
#: where the spec allows it. Anything else is not a PDF, whatever it is called.
PDF_MAGIC: Final = b"%PDF-"
PDF_MAGIC_WINDOW: Final = 1024

#: ASSUMED — a page whose text layer yields fewer characters than this is a
#: scan with, at most, a stray page number on it, and goes to OCR instead.
TEXT_LAYER_MIN_CHARS: Final = 50

#: Rendering resolution for a scanned PDF page sent to OCR. 200 dpi keeps
#: handwriting legible; the edge cap stops an A0 drawing becoming 9000 px.
RENDER_DPI: Final = 200
RENDER_MAX_EDGE_PX: Final = 3000

#: Display title cap. The original filename is a string somebody else chose.
DOCUMENT_TITLE_MAX: Final = 120
DOCUMENT_DEFAULT_TITLE: Final = "Document"

#: The worker's cadence, and when a document stuck in `extracting` is presumed
#: abandoned by a crashed process and picked up again.
WORKER_INTERVAL_SECONDS: Final = 30
EXTRACTION_STALE_MINUTES: Final = 10
EXTRACTION_MAX_ATTEMPTS: Final = 3

#: A nurse may upload only from a visit that is in progress, and never from a
#: check-in the geofence placed away from the home. `unavailable` (no GPS fix)
#: is allowed on purpose: a weak signal must not block a prescription photo.
#: Stored as the enum's value so this module stays import-free.
NURSE_UPLOAD_BLOCKED_LOCATIONS: Final[frozenset[str]] = frozenset({"out_of_range"})

#: The instruction sent with every page image. Chandra is trained to transcribe;
#: the prompt only asks it to keep the layout that makes a lab table a table.
OCR_PROMPT: Final = (
    "Transcribe every piece of text on this page exactly as written, including "
    "handwriting. Preserve tables as markdown tables and keep the reading order. "
    "Do not summarise, correct, translate or add anything."
)
OCR_MAX_TOKENS: Final = 4096

# --------------------------------------------------------------------------
# Layer 1a — facts and verification (Stage 2)
# --------------------------------------------------------------------------

#: Column headers that identify a lab table's columns. Matched case-insensitively
#: as substrings, so "Test Name", "Observed Value" and "Biological Ref. Interval"
#: all land. Order inside each tuple does not matter.
TABLE_NAME_HEADERS: Final[tuple[str, ...]] = ("test", "investigation", "parameter", "analyte", "description", "name")
TABLE_RESULT_HEADERS: Final[tuple[str, ...]] = ("result", "value", "observed", "reading")
TABLE_UNIT_HEADERS: Final[tuple[str, ...]] = ("unit",)
TABLE_REFERENCE_HEADERS: Final[tuple[str, ...]] = ("reference", "ref", "range", "normal", "interval", "biological")

#: The LLM extraction call. A page of a lab report is a few hundred tokens of
#: JSON out; the timeout is generous because this runs in the worker, not in a
#: request anyone is waiting on.
EXTRACTION_TIMEOUT_S: Final = 30.0
EXTRACTION_MAX_TOKENS: Final = 2000
#: The page text sent to the model is capped: a 30-page discharge summary is
#: extracted page by page, never as one prompt.
EXTRACTION_MAX_PAGE_CHARS: Final = 12_000
#: A runaway answer is truncated rather than trusted.
EXTRACTION_MAX_FACTS_PER_PAGE: Final = 40

#: Field limits, shared by extraction, the admin edit form and the schema.
FACT_LABEL_MAX: Final = 120
FACT_VALUE_MAX: Final = 200
FACT_UNIT_MAX: Final = 30
FACT_QUOTE_MAX: Final = 300
REJECTION_REASON_MAX: Final = 255
