"""Layer 1a — medical documents in, text out.

    intake.py      validate an upload, store it, create the Document row
    access.py      who may upload, see and delete a document
    pdf_text.py    a PDF's structure and its text layer (pypdf)
    render.py      a scanned PDF page as an image (pypdfium2)
    ocr_engine.py  the one place that knows an OCR engine exists
    worker.py      the queue that turns an upload into pages of text
    service.py     listing, serialising, deleting, export and erasure
"""
