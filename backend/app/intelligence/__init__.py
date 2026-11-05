"""The intelligence layers (Phase 12).

The rule this package is built around: **it sits beside the platform, never
inside it.** Everything here reads the existing models and services and writes
only to its own tables until a person approves something.

The existing application imports this package from exactly the places listed in
`tests/test_intelligence_boundary.py::ALLOWED_IMPORTERS`, and nowhere else —
so removing a layer, or switching one off, cannot reach into code that predates
it. Every number used here lives in `app/core/intelligence.py`.

Layers, each its own subpackage:

- `documents` — uploads → text (pypdf text layer, then OCR) → facts → admin verification
- `summaries` — nurse brief, admin summary, family summary in their language   (Stage 3+)
- `routing`   — caseload and daily-route proposals                            (Stage 5)
- `risk`      — 7-day deterioration risk with its reasons                      (Stage 4)
"""
