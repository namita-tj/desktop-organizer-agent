![Tests](https://github.com/namita-tj/desktop-organizer-agent/actions/workflows/ci.yml/badge.svg)

# 🗂️ Desktop Organiser Agent

A local AI agent that scans a folder, works out what each file is, and sorts it into tidy category folders. It classifies files with a **local LLM (Llama 3.2 via Ollama)**, so file contents never leave your machine. It **learns from your corrections**, and it records every move in an audit log that you can undo.

```
python main.py --move --feedback
```

---

## ✨ Features

- **Three-stage classification:** learned memory first, then the local LLM, then a rule-based fallback, so the agent still works offline or without Ollama.
- **Reads file contents, not just names:** text is extracted from PDFs (with an OCR fallback for scanned pages), DOCX, XLSX and CSV files. Key entities such as amounts, dates and reference numbers are passed to the LLM along with the text.
- **Learns from feedback:** with `--feedback` you confirm or correct each decision. Corrections are stored in persistent memory and reused on similar files. You can also create new categories on the fly.
- **Safe by default:** nothing moves without `--move`, files below the confidence threshold are skipped, and duplicate filenames get a timestamp instead of being overwritten.
- **Audit trail and undo:** every move is written as a JSON Lines audit entry (source, destination, category, confidence, method, reasoning), and `--undo` reverses the last run.
- **Sensitive-document flag:** documents that look sensitive are marked in the output.
- **Invoice field extraction:** a standalone module pulls vendor, invoice ID, total, VAT rate, due date and currency from invoice text. It handles OCR noise and both EU (`€29.155,00`) and US (`$29,155.00`) number formats.

---

## 🏗️ Architecture

```
 folder
   │
   ▼
 observer.py     → scans files and collects metadata
   │
   ▼
 classifier.py   → 1. memory.py      learned patterns from your corrections
                   2. local LLM      Ollama (llama3.2), using extracted content
                                     from extractor.py + entities.py
                   3. rule-based     extension and keyword fallback
   │
   ▼
 actor.py        → moves the file to Organised/<Category>/
                   and writes an audit entry to logs/moves.log
```

| Module | Responsibility |
|---|---|
| `src/observer.py` | Scans the target folder and builds a metadata record per file |
| `src/classifier.py` | Orchestrates memory → LLM → rules and validates the LLM's JSON output |
| `src/extractor.py` | Extracts text from PDF (incl. OCR fallback), DOCX, XLSX and CSV |
| `src/entities.py` | Regex-based extraction of amounts, dates, references and document type |
| `src/memory.py` | Persistent learning layer: stores corrections and custom categories |
| `src/actor.py` | Moves files, handles collisions, writes the audit log, supports undo |
| `src/logger.py` | Central logging to console and a rotating log file |
| `extractors/invoice.py` | Structured invoice field extraction (standalone, not yet wired into the pipeline) |

---

## 🚀 Quickstart

**1. Install Ollama and pull the model** (optional; without it the agent uses memory and rules only)

```bash
# install from https://ollama.com, then:
ollama pull llama3.2
```

**2. Install the optional extraction dependencies**

```bash
pip install -r requirements.txt
```

The core agent uses only the Python standard library. The extras enable PDF, DOCX and spreadsheet reading, OCR, and the test suite. OCR also needs the Tesseract binary installed on your system.

**3. Preview what would happen (nothing is moved)**

```bash
python main.py
```

**4. Organise for real, and teach the agent as it goes**

```bash
python main.py --move --feedback
```

---

## ⚙️ Commands

| Command | What it does |
|---|---|
| `python main.py` | Dry run on `~/Desktop` |
| `--move` | Actually move files |
| `--feedback` | Ask for a correction after each classification and learn from it |
| `--threshold 0.7` | Only act on classifications at or above this confidence (default `0.6`) |
| `--path ~/Downloads` | Scan a different folder |
| `--stats` | Show what the agent has learned |
| `--clear-memory` | Wipe all learned patterns |
| `--audit` | Show the most recent audit log entries (`--audit-lines N` to change how many) |
| `--undo` | Move the files from the last run back to where they were |

---

## 🧠 Design Decisions

| Decision | Reason |
|---|---|
| Local LLM instead of a cloud API | File contents can be private; nothing should leave the machine |
| Memory before the LLM | A user's own corrections are the most reliable signal and the cheapest to apply |
| Rule-based fallback | The agent keeps working when Ollama isn't running |
| LLM output validated against known categories | A malformed or invented category is never acted on |
| Dry run by default | Destructive operations should always need explicit opt-in |
| Confidence threshold | A wrong move is worse than no move |
| JSON Lines audit log + undo | Every action is traceable and reversible |

---

## 🧪 Testing

```bash
pytest tests/ -v
```

71 unit tests across the observer, classifier, memory, actor and invoice extractor, run by GitHub Actions on every push. The tests don't need Ollama; the LLM call is mocked.

There is also a small classification evaluation on a labelled set of 42 example filenames:

```bash
python tests/eval.py
```

It reports overall accuracy plus per-category precision, recall, F1 and a confusion matrix. The set is small and hand-written, so treat it as a regression check rather than a benchmark.

---

## 🔭 Limitations and Next Steps

- Organised folders are always created under `~/Desktop/Organised`, even when `--path` points elsewhere.
- The invoice extractor is tested but not yet connected to the main pipeline. The next step is to run it on files classified as invoices and attach the fields to the audit entry.
- The evaluation set is small. A larger set of real, anonymised files would give a more honest accuracy figure.
