"""
entities.py — Extracts structured entities from document text.

No external NLP library needed — regex handles 90% of enterprise
document patterns. LLM handles the rest.
"""

import re


def extract_entities(text: str) -> dict:
    """
    Pull structured data out of raw document text.
    Returns a dict of found entities.
    """
    return {
        "amounts":      _find_amounts(text),
        "dates":        _find_dates(text),
        "references":   _find_references(text),
        "document_type": _infer_document_type(text),
        "is_sensitive": _check_sensitive(text),
    }


def _find_amounts(text: str) -> list:
    # Matches: €24,500 | $1,234.56 | 24.500 EUR
    pattern = r'[€$£¥]\s?[\d,]+\.?\d*|[\d,]+\.?\d*\s?(?:EUR|USD|GBP|CHF)'
    return re.findall(pattern, text)[:5]  # max 5


def _find_dates(text: str) -> list:
    # Matches: 12.04.2026 | 12/04/2026 | April 12 2026
    pattern = r'\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b'
    return re.findall(pattern, text)[:5]


def _find_references(text: str) -> list:
    # Matches: INV-2024-001 | PO-892 | REF#4521
    pattern = r'\b(?:INV|PO|REF|NDA|CONTRACT|CASE|FILE|DOC)[-#]?\d+\b'
    return re.findall(pattern, text, re.IGNORECASE)[:5]


def _infer_document_type(text: str) -> str:
    """Rule-based document type inference from content signals."""
    text_lower = text.lower()

    signals = {
        "invoice":    ["invoice", "bill to", "due date", "payment terms", "total due"],
        "contract":   ["agreement", "hereby agrees", "terms and conditions", "signed by"],
        "nda":        ["non-disclosure", "confidential", "shall not disclose"],
        "report":     ["executive summary", "findings", "methodology", "conclusion"],
        "receipt":    ["receipt", "paid", "transaction", "thank you for your purchase"],
        "lab_result": ["specimen", "result", "reference range", "normal", "abnormal"],
    }

    for doc_type, keywords in signals.items():
        if sum(1 for kw in keywords if kw in text_lower) >= 2:
            return doc_type

    return "unknown"


def _check_sensitive(text: str) -> bool:
    """Flag documents that likely contain sensitive information."""
    sensitive_patterns = [
        r'\b\d{3}-\d{2}-\d{4}\b',          # SSN (US)
        r'\b[A-Z]{2}\d{6}[A-Z]\b',          # Passport number
        r'\bIBAN\b',                          # Bank account
        r'\bpatient\b',                       # Healthcare
        r'\bconfidential\b',
        r'\bprivileged\b',                    # Legal
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in sensitive_patterns)