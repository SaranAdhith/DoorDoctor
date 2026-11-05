"""One PDF page as an image, for the pages that have no text layer.

`pypdfium2` (Chrome's PDF engine) rather than shelling out to Poppler: it ships
as a wheel on Windows and Linux, so a laptop and a container behave the same.
Imported lazily for the same reason as `pypdf` in `pdf_text.py`.
"""

from __future__ import annotations

import io

from ...core.intelligence import RENDER_DPI, RENDER_MAX_EDGE_PX

#: PDF user space is 72 units per inch.
_PDF_POINTS_PER_INCH = 72


def render_page(data: bytes, index: int, *, dpi: int = RENDER_DPI) -> bytes:
    """PNG bytes of page `index` (0-based). Raises on a page that cannot render;
    the worker turns that into a `none` page rather than a failed document."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        page = pdf[index]
        try:
            bitmap = page.render(scale=dpi / _PDF_POINTS_PER_INCH)
            image = bitmap.to_pil()
        finally:
            page.close()
    finally:
        pdf.close()

    image.thumbnail((RENDER_MAX_EDGE_PX, RENDER_MAX_EDGE_PX))
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
