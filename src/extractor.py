"""
extractor.py — Reads document content for classification.

Extracts text from PDFs, DOCX, XLSX so the classifier
has actual content to reason about, not just filenames.
"""

import re
from pathlib import Path


def extract_text(file_obs: dict, max_chars: int = 2000) -> str:
    """
    Extract text preview from a document.
    Returns first max_chars characters — enough for classification,
    not so much that it blows up the LLM context window.
    """
    path = Path(file_obs["path"])
    ext = file_obs["extension"].lower()

    try:
        if ext == ".pdf":
            return _extract_pdf(path, max_chars)
        elif ext == ".docx":
            return _extract_docx(path, max_chars)
        elif ext in (".xlsx", ".csv"):
            return _extract_spreadsheet(path, max_chars)
        else:
            return ""
    except Exception as e:
        return ""  # never crash — content is optional


def _extract_pdf(path: Path, max_chars: int) -> str:
    import fitz  # PyMuPDF
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text()
        if len(text) >= max_chars:
            break
    return text[:max_chars]


def _extract_docx(path: Path, max_chars: int) -> str:
    from docx import Document
    doc = Document(path)
    text = "\n".join(p.text for p in doc.paragraphs)
    return text[:max_chars]


def _extract_spreadsheet(path: Path, max_chars: int) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(max_row=10, values_only=True):
        rows.append(" | ".join(str(c) for c in row if c is not None))
    return "\n".join(rows)[:max_chars]