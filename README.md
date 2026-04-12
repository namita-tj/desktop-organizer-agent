# 🗂 Desktop Organiser Agent

An LLM-powered agent that scans your Desktop, classifies each file using Claude, and moves them into organised folders — with a rule-based fallback for offline use.

---

## How it works

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

---

## Quickstart

```bash
# Install dependencies (none required beyond stdlib — Claude API uses urllib)
# Set your API key
export ANTHROPIC_API_KEY=your_key_here

# Preview what would happen (safe — nothing is moved)
python main.py

# Actually move files
python main.py --move

# Only move files the model is very confident about
python main.py --move --threshold 0.8
```

---

## Output structure

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

## Features

- **LLM classification** — Claude reasons about filenames and metadata to determine category
- **Rule-based fallback** — works offline if the API is unavailable
- **Confidence threshold** — skips files the model isn't sure about
- **Dry run by default** — safe to run; nothing moves unless you pass `--move`
- **Collision handling** — timestamps duplicate filenames instead of overwriting
- **Clean summary** — see exactly what was moved, skipped, or errored

---

## Architecture decisions

| Decision | Reason |
|---|---|
| LLM-first, rules as fallback | LLM handles edge cases rules can't; fallback ensures reliability |
| Dry run default | Destructive operations should always require explicit opt-in |
| Confidence threshold | Low-confidence classifications are worse than no classification |
| Timestamp collision handling | Safer than silent overwrites |

---

## Extending this

- Add a `--undo` flag using a move log saved to JSON
- Add email/Slack notification after organising
- Schedule with cron for automatic daily runs
- Fine-tune a small local model on your own file naming patterns