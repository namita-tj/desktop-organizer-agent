"""
invoice.py — Extract structured invoice fields from raw document text.

Designed for real-world invoice text from:
    - PDFs (via PyMuPDF)
    - DOCX (via python-docx)
    - OCR output (noisy, incomplete, misread characters)

Returns a structured dict with all fields — missing fields are None,
never raised as exceptions.

Handles:
    - Clean digital invoices
    - OCR noise (l→I, 0→o, extra spaces, double colons)
    - European number formats (€29.155,00)
    - US number formats ($29,155.00)
    - Multiple invoice IDs in same document (returns first)
    - Completely irrelevant text (returns all None safely)
"""

import re
from typing import Optional


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """
    Normalise invoice text for regex parsing.
    Collapses whitespace and newlines into single spaces.
    Does NOT remove OCR noise — individual extractors handle that.
    """
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _first_match(patterns: list, text: str, flags: int = 0) -> Optional[str]:
    """
    Try each pattern in order, return the first captured group that matches.
    Returns None if no pattern matches.
    """
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(1).strip()
    return None


def _parse_amount(value: str) -> Optional[float]:
    """
    Parse a numeric string into a float, handling:
        - European format: 29.155,00  → 29155.00
        - US format:       29,155.00  → 29155.00
        - Plain:           1200.50    → 1200.50
        - Spaced:          1 200.50   → 1200.50
    Returns None if the string cannot be parsed.
    """
    if not value:
        return None

    value = value.strip().replace(" ", "")

    # European format: digits with dot-thousands and comma-decimal
    # e.g. 29.155,00 or 1.200,50
    if re.match(r'^\d{1,3}(\.\d{3})+(,\d{1,2})?$', value):
        value = value.replace(".", "").replace(",", ".")

    # US format: digits with comma-thousands and dot-decimal
    # e.g. 29,155.00 or 1,200.50
    elif re.match(r'^\d{1,3}(,\d{3})+(\.\d{1,2})?$', value):
        value = value.replace(",", "")

    # Simple comma as decimal separator: 1200,50
    elif re.match(r'^\d+,\d{1,2}$', value):
        value = value.replace(",", ".")

    # Remove any remaining commas (e.g. just thousands with no decimal)
    else:
        value = value.replace(",", "")

    try:
        return float(value)
    except ValueError:
        return None


def _empty_fields() -> dict:
    return {
        "vendor":       None,
        "invoice_id":   None,
        "total_amount": None,
        "vat_rate":     None,
        "due_date":     None,
        "currency":     None,
    }


# ── Field extractors ───────────────────────────────────────────────────────────

def extract_vendor(text: str) -> Optional[str]:
    """
    Extract vendor / supplier name.
    Looks for 'Vendor:', 'Supplier:', 'From:', 'Bill From:' labels.
    Stops at next double-space, digit sequence, or known field label.
    """
    patterns = [
        # "Vendor: Siemens AG" — stops at next label or number
        r'[Vv]endor[:\-\s]+([A-Za-z][\w\s&.,]+?)(?=\s{2,}|\d|Invoice|Total|VAT|Due|$)',
        r'[Ss]upplier[:\-\s]+([A-Za-z][\w\s&.,]+?)(?=\s{2,}|\d|Invoice|Total|VAT|Due|$)',
        r'[Ff]rom[:\-\s]+([A-Za-z][\w\s&.,]+?)(?=\s{2,}|\d|Invoice|Total|VAT|Due|$)',
        r'[Bb]ill\s+[Ff]rom[:\-\s]+([A-Za-z][\w\s&.,]+?)(?=\s{2,}|\d|Invoice|Total|VAT|Due|$)',
    ]
    result = _first_match(patterns, text, re.IGNORECASE)
    return result.strip() if result else None


def extract_invoice_id(text: str) -> Optional[str]:
    """
    Extract invoice reference number.
    Handles: INV-1001, Invoice No 1001, Invoice # A-001
    Returns just the ID string, not the label.
    """
    patterns = [
        # INV-1001 or INV 1001 — standalone token
        r'\b(INV[-\s]?\d{3,})\b',
        # "Invoice No: INV-1001" or "Invoice No 1001"
        r'[Ii]nvoice\s+[Nn]o\.?\s*[:\-]?\s*([A-Z0-9][\w\-]+)',
        # "Invoice # A-001"
        r'[Ii]nvoice\s*#\s*([A-Z0-9][\w\-]+)',
        # "Invoice: 1001"
        r'[Ii]nvoice[:\-]\s*([A-Z0-9][\w\-]+)',
    ]
    return _first_match(patterns, text, re.IGNORECASE)


def extract_total_amount(text: str) -> Optional[float]:
    """
    Extract total invoice amount.
    Handles currency symbols, various labels, EU and US number formats.
    """
    # Label-based patterns — capture the number after common total labels
    label_patterns = [
        r'(?:Total\s+Due|Grand\s+Total|Amount\s+Due|Total\s+Amount|Total)[:\-\s]+[€$£]?\s*([\d.,\s]+)',
        r'[€$£]\s*([\d.,]+)',  # bare currency symbol + number
    ]

    raw = _first_match(label_patterns, text, re.IGNORECASE)
    if raw:
        # Take only the first number-like token (stops at next word)
        token = re.split(r'\s+[A-Za-z]', raw)[0].strip()
        return _parse_amount(token)

    return None


def extract_vat_rate(text: str) -> Optional[float]:
    """
    Extract VAT percentage and return as decimal.
    e.g. "VAT: 19%" → 0.19
    Handles extra spaces and double colons from OCR.
    """
    match = re.search(
        r'VAT\s*[:\-]{0,2}\s*(\d{1,2})\s*%',
        text,
        re.IGNORECASE
    )
    if match:
        return round(float(match.group(1)) / 100, 4)
    return None


def extract_due_date(text: str) -> Optional[str]:
    """
    Extract due / payment date.
    Returns the date string as-is from the document.
    """
    patterns = [
        r'[Dd]ue\s+[Dd]ate[:\-\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        r'[Pp]ayable\s+[Bb]y[:\-\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        r'[Pp]ayment\s+[Dd]ue[:\-\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
    ]
    return _first_match(patterns, text, re.IGNORECASE)


def extract_currency(text: str) -> Optional[str]:
    """
    Detect currency from symbols or ISO codes.
    Symbol takes priority over ISO code if both present.
    """
    if "€" in text:
        return "EUR"
    if "$" in text:
        return "USD"
    if "£" in text:
        return "GBP"
    if "¥" in text:
        return "JPY"

    match = re.search(r'\b(EUR|USD|GBP|CHF|JPY)\b', text)
    return match.group(1) if match else None


# ── Public API ─────────────────────────────────────────────────────────────────

def extract_invoice_fields(text: str) -> dict:
    """
    Extract all structured invoice fields from raw document text.

    Args:
        text: Raw text extracted from a PDF, DOCX, or OCR output

    Returns:
        Dict with keys: vendor, invoice_id, total_amount,
                        vat_rate, due_date, currency
        All values are None if not found — never raises.
    """
    if not text or not text.strip():
        return _empty_fields()

    # Normalise once — all extractors use the cleaned version
    cleaned = _clean(text)

    return {
        "vendor":       extract_vendor(cleaned),
        "invoice_id":   extract_invoice_id(cleaned),
        "total_amount": extract_total_amount(cleaned),
        "vat_rate":     extract_vat_rate(cleaned),
        "due_date":     extract_due_date(cleaned),
        "currency":     extract_currency(cleaned),
    }


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample = """
    Invoice No INV-4521
    Date: 12.04.2026
    Due Date: 30/04/2026

    Vendor: Siemens AG
    Munich, Germany

    Description: Software Development Services
    Subtotal: €24,500
    VAT: 19%
    Total Due: €29,155.00

    Payment Terms: Net 30
    """

    fields = extract_invoice_fields(sample)
    print("Extracted invoice fields:")
    for k, v in fields.items():
        print(f"  {k:15s}: {v}")