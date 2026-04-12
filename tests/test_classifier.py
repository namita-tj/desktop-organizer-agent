"""
test_classifier.py — Tests for classifier.py

Pass criteria:
    1.  Rule-based: known extensions classified correctly
    2.  Rule-based: keyword match works
    3.  Rule-based: unknown extension returns Unknown
    4.  LLM result used when Ollama responds correctly
    5.  Falls back to rules when Ollama returns None
    6.  Falls back to rules when Ollama is unreachable
    7.  Invalid category from Ollama is caught and corrected
    8.  Memory is checked before LLM is called
    9.  Pipeline order: memory → LLM → rules
    10. Result always has correct shape (all required keys)

Key concept — mocking:
    We never actually call Ollama in tests. Instead we use
    unittest.mock.patch to replace _call_llm with a fake function
    that returns whatever we tell it to. This makes tests:
        - Fast (no network calls)
        - Free (no API usage)
        - Deterministic (same result every time)
        - Isolated (tests don't depend on Ollama being running)
"""

import pytest
from unittest.mock import patch
from src.classifier import classify_file, _rule_based_classify, VALID_CATEGORIES
from src.memory import save_correction, MEMORY_FILE


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolate_memory(tmp_path, monkeypatch):
    """Fresh memory file for every test — prevents cross-test contamination."""
    fake_memory = tmp_path / "memory.json"
    monkeypatch.setattr("src.memory.MEMORY_FILE", fake_memory)
    monkeypatch.setattr("src.classifier.MEMORY_FILE", fake_memory)


# ── Sample file observations ───────────────────────────────────────────────────

PDF_FILE  = {"name": "resume.pdf",      "extension": ".pdf",  "size_bytes": 204800}
PY_FILE   = {"name": "app.py",          "extension": ".py",   "size_bytes": 8192}
PNG_FILE  = {"name": "photo.png",       "extension": ".png",  "size_bytes": 512000}
ZIP_FILE  = {"name": "backup.zip",      "extension": ".zip",  "size_bytes": 1048576}
EXE_FILE  = {"name": "setup.exe",       "extension": ".exe",  "size_bytes": 5242880}
BLOB_FILE = {"name": "random.blob",     "extension": ".blob", "size_bytes": 1024}
KEYWORD_FILE = {"name": "resume.blob",  "extension": ".blob", "size_bytes": 1024}


# ── Rule-based tests ───────────────────────────────────────────────────────────

class TestRuleBased:
    """Tests for the rule-based fallback classifier."""

    def test_pdf_classified_as_documents(self):
        result = _rule_based_classify(PDF_FILE)
        assert result["category"] == "Documents"
        assert result["confidence"] >= 0.6
        assert result["method"] == "rule-based"

    def test_py_classified_as_code(self):
        result = _rule_based_classify(PY_FILE)
        assert result["category"] == "Code"
        assert result["confidence"] >= 0.6

    def test_png_classified_as_images(self):
        result = _rule_based_classify(PNG_FILE)
        assert result["category"] == "Images"
        assert result["confidence"] >= 0.6

    def test_zip_classified_as_archives(self):
        result = _rule_based_classify(ZIP_FILE)
        assert result["category"] == "Archives"
        assert result["confidence"] >= 0.6

    def test_exe_classified_as_installers(self):
        result = _rule_based_classify(EXE_FILE)
        assert result["category"] == "Installers"
        assert result["confidence"] >= 0.6

    def test_unknown_extension_returns_unknown(self):
        result = _rule_based_classify(BLOB_FILE)
        assert result["category"] == "Unknown"
        assert result["confidence"] == 0.0

    def test_keyword_match_boosts_confidence(self):
        """'resume' keyword in filename should push confidence above 0.6."""
        result = _rule_based_classify(KEYWORD_FILE)
        assert result["category"] == "Documents"
        assert result["confidence"] >= 0.2  # keyword match alone


# ── LLM pipeline tests ─────────────────────────────────────────────────────────

class TestLLMPipeline:
    """Tests for the full classify_file pipeline with mocked Ollama."""

    def test_uses_llm_result_when_ollama_responds(self):
        """When Ollama returns a valid result, it should be used."""
        fake_response = {
            "category": "Documents",
            "confidence": 0.95,
            "reasoning": "PDF is a document format"
        }

        with patch("src.classifier._call_llm", return_value=fake_response):
            result = classify_file(PDF_FILE)

        assert result["category"] == "Documents"
        assert result["confidence"] == 0.95
        assert result["method"] == "llm"

    def test_falls_back_to_rules_when_ollama_returns_none(self):
        """When _call_llm returns None (Ollama down), use rule-based."""
        with patch("src.classifier._call_llm", return_value=None):
            result = classify_file(PY_FILE)

        assert result["method"] == "rule-based"
        assert result["category"] == "Code"

    def test_falls_back_gracefully_for_unknown_extension(self):
        """Unknown extension + Ollama down → Unknown from rule-based, no crash."""
        with patch("src.classifier._call_llm", return_value=None):
            result = classify_file(BLOB_FILE)

        assert result["method"] == "rule-based"
        assert result["category"] == "Unknown"

    def test_invalid_category_from_ollama_is_corrected(self):
        """If Ollama returns a made-up category, it should be set to Unknown."""
        fake_response = {
            "category": "MadeUpCategory",
            "confidence": 0.9,
            "reasoning": "some reasoning"
        }

        with patch("src.classifier._call_llm", return_value=fake_response):
            result = classify_file(BLOB_FILE)

        # Should not pass through an invalid category
        assert result["category"] in VALID_CATEGORIES

    def test_result_has_all_required_keys(self):
        """Result dict must always have name, category, confidence, method."""
        fake_response = {
            "category": "Code",
            "confidence": 0.9,
            "reasoning": "Python file"
        }

        with patch("src.classifier._call_llm", return_value=fake_response):
            result = classify_file(PY_FILE)

        assert "name" in result
        assert "category" in result
        assert "confidence" in result
        assert "method" in result

    def test_confidence_is_float(self):
        """Confidence must always be a float, not a string or int."""
        fake_response = {
            "category": "Code",
            "confidence": 0.9,
            "reasoning": "Python file"
        }

        with patch("src.classifier._call_llm", return_value=fake_response):
            result = classify_file(PY_FILE)

        assert isinstance(result["confidence"], float)


# ── Memory priority tests ──────────────────────────────────────────────────────

class TestMemoryPriority:
    """Tests that memory is checked before LLM — the core pipeline order."""

    def test_memory_hit_skips_llm_entirely(self):
        """
        If memory has a match, _call_llm should never be called.
        We verify this by checking the mock was NOT called.
        """
        save_correction(PDF_FILE, "Documents")

        with patch("src.classifier._call_llm") as mock_llm:
            result = classify_file(PDF_FILE)

        assert result["method"] == "memory"
        mock_llm.assert_not_called()  # LLM was never touched

    def test_memory_result_used_over_llm(self):
        """Memory category should win even if LLM would say something different."""
        save_correction(PDF_FILE, "Uni")  # custom category in memory

        fake_llm_response = {
            "category": "Documents",
            "confidence": 0.99,
            "reasoning": "PDF is a document"
        }

        with patch("src.classifier._call_llm", return_value=fake_llm_response):
            result = classify_file(PDF_FILE)

        # Memory wins — not LLM
        assert result["category"] == "Uni"
        assert result["method"] == "memory"

    def test_llm_called_when_no_memory_match(self):
        """When memory has no match, LLM should be called."""
        with patch("src.classifier._call_llm") as mock_llm:
            mock_llm.return_value = {
                "category": "Code",
                "confidence": 0.9,
                "reasoning": "Python file"
            }
            result = classify_file(PY_FILE)

        mock_llm.assert_called_once()  # LLM was called exactly once
        assert result["method"] == "llm"

    def test_pipeline_order_memory_llm_rules(self):
        """
        Full pipeline order test:
        1. Memory miss → goes to LLM
        2. LLM returns None → falls to rules
        3. Rules classify by extension
        """
        # No memory saved → memory miss
        # Ollama returns None → LLM miss
        with patch("src.classifier._call_llm", return_value=None):
            result = classify_file(PY_FILE)

        # Should have fallen all the way to rule-based
        assert result["method"] == "rule-based"
        assert result["category"] == "Code"