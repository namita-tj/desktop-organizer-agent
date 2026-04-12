# 🗂️ Desktop Organiser Agent

An LLM-powered agent that scans your Desktop, classifies each file using Claude, and moves them into tidy, organised folders — with a rule-based fallback for offline use.

---

## ✨ Features

- **LLM classification** — Claude reasons about filenames and metadata to determine the best category for each file
- **Rule-based fallback** — works offline if the Anthropic API is unavailable
- **Confidence threshold** — skips files the model isn't confident about, so uncertain files are never misplaced
- **Dry run by default** — nothing moves unless you explicitly pass `--move`
- **Collision handling** — timestamps duplicate filenames instead of silently overwriting them
- **Clean summary** — see exactly what was moved, skipped, or errored after each run

---

## 🏗️ Architecture

```
Desktop files
     │
     ▼
 observer.py        → scans files, collects metadata
     │
     ▼
 classifier.py      → asks Claude to classify each file
 (+ rule-based      → falls back if API unavailable)
  fallback)
     │
     ▼
  actor.py          → moves files into Organised/<Category>/
```

The project is split into three focused modules under `src/`, plus a top-level `main.py` entry point and a `tests/` directory.

---

## 🚀 Quickstart

**1. Set your Anthropic API key**

```bash
export ANTHROPIC_API_KEY=your_key_here
```

**2. Preview (safe — nothing is moved)**

```bash
python main.py
```

**3. Move files**

```bash
python main.py --move
```

**4. Only move files the model is highly confident about**

```bash
python main.py --move --threshold 0.8
```

---

## 📁 Output Structure

After running with `--move`, your Desktop will look like:

```
Desktop/
└── Organised/
    ├── Documents/
    ├── Images/
    ├── Code/
    ├── Archives/
    ├── Installers/
    ├── Videos/
    └── Audio/
```

---

## ⚙️ Configuration

| Flag | Default | Description |
|---|---|---|
| `--move` | off | Actually move files (dry run otherwise) |
| `--threshold` | `0.0` | Minimum confidence score (0–1) required to move a file |

---

## 🧠 Architecture Decisions

| Decision | Reason |
|---|---|
| LLM-first, rules as fallback | LLM handles edge cases rules can't; fallback ensures reliability without an API key |
| Dry run by default | Destructive operations should always require explicit opt-in |
| Confidence threshold | Low-confidence classifications are worse than no classification |
| Timestamp collision handling | Safer than silent overwrites |

---

## 🛠️ Requirements

- Python 3.8+
- No third-party libraries required — Claude API calls use Python's built-in `urllib`
- An [Anthropic API key](https://console.anthropic.com/) (optional — rule-based fallback works without one)

---

## 🧪 Running Tests

```bash
pytest tests/
```

Test fixtures and shared configuration live in `conftest.py` at the project root.

---

## 🔭 Extending This

- Add a `--undo` flag using a move log saved to JSON
- Add email or Slack notifications after organising
- Schedule with `cron` for automatic daily runs
- Fine-tune a small local model on your own file naming patterns
- Support custom category mappings via a config file

---

## 📄 License

MIT