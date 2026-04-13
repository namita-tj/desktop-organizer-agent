from extractors.invoice import extract_invoice_fields


# ─────────────────────────────────────────────────────────────
# 1. Normal invoice (baseline case)
# ─────────────────────────────────────────────────────────────
def test_invoice_normal():
    text = """
    Invoice No INV-1001
    Vendor: Siemens AG
    Total Due: 1200.50
    VAT: 19%
    Due Date: 12/05/2026
    """

    result = extract_invoice_fields(text)

    assert result["vendor"] == "Siemens AG"
    assert result["invoice_id"] == "INV-1001"
    assert result["total_amount"] == 1200.50
    assert result["vat_rate"] == 0.19
    assert result["due_date"] == "12/05/2026"


# ─────────────────────────────────────────────────────────────
# 2. Missing fields (real-world invoices are messy)
# ─────────────────────────────────────────────────────────────
def test_invoice_missing_fields():
    text = """
    Invoice No INV-2002
    Vendor: Amazon EU
    """

    result = extract_invoice_fields(text)

    assert result["vendor"] == "Amazon EU"
    assert result["invoice_id"] == "INV-2002"
    assert result["total_amount"] is None
    assert result["vat_rate"] is None


# ─────────────────────────────────────────────────────────────
# 3. OCR noisy text (very common in PDFs)
# ─────────────────────────────────────────────────────────────
def test_invoice_ocr_noise():
    text = """
    INVOlCE n0 INV-9999
    V€ndor:: Siem3ns AG
    T0tal Due ::: € 1,500.75
    VAT:: 19 %
    """

    result = extract_invoice_fields(text)

    # relaxed expectations due to OCR noise
    assert result["invoice_id"] is not None
    assert result["total_amount"] is not None


# ─────────────────────────────────────────────────────────────
# 4. Currency detection
# ─────────────────────────────────────────────────────────────
def test_invoice_currency_detection():
    text = """
    Invoice No INV-3001
    Vendor: Apple Inc
    Total Due: $999.99
    """

    result = extract_invoice_fields(text)

    assert result["currency"] == "USD"


# ─────────────────────────────────────────────────────────────
# 5. Euro format parsing
# ─────────────────────────────────────────────────────────────
def test_invoice_euro_format():
    text = """
    Invoice No INV-3002
    Vendor: BMW AG
    Total Due: €1200.00
    """

    result = extract_invoice_fields(text)

    assert result["currency"] == "EUR"
    assert result["total_amount"] == 1200.00


# ─────────────────────────────────────────────────────────────
# 6. No invoice text at all
# ─────────────────────────────────────────────────────────────
def test_invoice_empty_text():
    result = extract_invoice_fields("")

    assert result["vendor"] is None
    assert result["invoice_id"] is None
    assert result["total_amount"] is None


# ─────────────────────────────────────────────────────────────
# 7. Completely irrelevant text (should not crash)
# ─────────────────────────────────────────────────────────────
def test_invoice_irrelevant_text():
    text = """
    Hello this is just a random email.
    No invoice data here.
    """

    result = extract_invoice_fields(text)

    assert all(v is None for v in result.values())


# ─────────────────────────────────────────────────────────────
# 8. Multiple invoice-like numbers (should pick first)
# ─────────────────────────────────────────────────────────────
def test_invoice_multiple_ids():
    text = """
    Invoice No INV-1111
    Another reference INV-2222
    Vendor: Tesla
    """

    result = extract_invoice_fields(text)

    assert result["invoice_id"] == "INV-1111"


# ─────────────────────────────────────────────────────────────
# 9. Broken numeric formats
# ─────────────────────────────────────────────────────────────
def test_invoice_malformed_numbers():
    text = """
    Invoice No INV-7777
    Vendor: OpenAI
    Total Due: twelve hundred euros
    VAT: nineteen percent
    """

    result = extract_invoice_fields(text)

    assert result["total_amount"] is None
    assert result["vat_rate"] is None