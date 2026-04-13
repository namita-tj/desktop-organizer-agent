"""
extractor.py — Enterprise-grade document content extraction.

Supports:
- PDF (text + structured blocks + OCR fallback)
- DOCX
- XLSX
- CSV

Returns lightweight text for LLM classification,
but designed to evolve into structured document intelligence.
"""

from pathlib import Path
import re


# ─────────────────────────────────────────────────────────────────────────────
# Public API (backward compatible)
# ─────────────────────────────────────────────────────────────────────────────

def extract_text(file_obs: dict, max_chars: int = 2000) -> str:
    """
    Backward-compatible extractor for classifier pipeline.
    Always safe: never raises exceptions.
    """

    if "path" not in file_obs:
        return ""

    path = Path(file_obs["path"])
    ext = file_obs.get("extension", "").lower()

    try:
        if ext == ".pdf":
            text = _extract_pdf(path, max_chars)
        elif ext == ".docx":
            text = _extract_docx(path, max_chars)
        elif ext in (".xlsx", ".csv"):
            text = _extract_spreadsheet(path, max_chars)
        else:
            text = ""

        return _clean_text(text)[:max_chars]

    except Exception:
        return ""  # never crash classifier pipeline


# ─────────────────────────────────────────────────────────────────────────────
# PDF Extraction (text + structure + OCR fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_pdf(path: Path, max_chars: int) -> str:
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    chunks = []

    for page in doc:
        text = page.get_text("blocks")  # structured layout

        if text:
            # sort reading order
            text = sorted(text, key=lambda b: (b[1], b[0]))
            page_text = "\n".join(t[4] for t in text)
        else:
            page_text = _ocr_page(page)

        chunks.append(page_text)

        if sum(len(c) for c in chunks) >= max_chars:
            break

    return "\n".join(chunks)


# OCR fallback for scanned PDFs
def _ocr_page(page) -> str:
    try:
        import pytesseract
        from PIL import Image
        import io

        pix = page.get_pixmap()
        img = Image.open(io.BytesIO(pix.tobytes()))
        return pytesseract.image_to_string(img)

    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# DOCX Extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_docx(path: Path, max_chars: int) -> str:
    from docx import Document

    doc = Document(path)
    text = "\n".join(p.text for p in doc.paragraphs)

    return text[:max_chars]


# ─────────────────────────────────────────────────────────────────────────────
# Spreadsheet Extraction (XLSX / CSV)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_spreadsheet(path: Path, max_chars: int) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    rows = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i > 20:  # sample limit
            break

        row_text = " | ".join(str(c) for c in row if c is not None)
        if row_text.strip():
            rows.append(row_text)

    return "\n".join(rows)[:max_chars]


# ─────────────────────────────────────────────────────────────────────────────
# Text cleaning (important for LLM quality)
# ─────────────────────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\x00-\x7F]+", " ", text)  # remove weird unicode noise
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Optional: document type hinting (useful for LLM prompt enrichment)
# ─────────────────────────────────────────────────────────────────────────────

def detect_document_type(text: str) -> str:
    """
    Lightweight heuristic pre-classifier.
    Helps LLM converge faster.
    """

    text = text.lower()

    if "invoice" in text:
        return "invoice"
    if "contract" in text:
        return "contract"
    if "curriculum vitae" in text or "resume" in text:
        return "resume"
    if "report" in text:
        return "report"

    return "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Future upgrade path (for enterprise system)
# ─────────────────────────────────────────────────────────────────────────────
"""
Next evolution:
- extract_document() → returns structured JSON:
  {
    text,
    tables,
    entities,
    layout,
    doc_type_hint
  }
"""