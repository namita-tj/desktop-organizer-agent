"""
classifier.py — LLM-powered file classifier using local Ollama (llama3.2).

Falls back to rule-based classification if Ollama is unavailable,
so the agent always produces a result.

Requirements:
    1. Install Ollama from https://ollama.com
    2. Run: ollama pull llama3.2
    3. Ollama must be running (it starts automatically on Windows after install)
"""

import json
import urllib.request
import urllib.error
import src.memory as _memory
from src.memory import MEMORY_FILE  # expose for test monkeypatching

# ── Rule-based fallback (kept from v1) ────────────────────────────────────────

CATEGORIES = {
    "Documents": {
        "extensions": [".pdf", ".docx", ".txt", ".pptx", ".xlsx"],
        "keywords": ["resume", "invoice", "notes", "report", "assignment"]
    },
    "Images": {
        "extensions": [".jpg", ".jpeg", ".png", ".svg", ".webp", ".gif"],
        "keywords": ["img", "image", "photo", "screenshot"]
    },
    "Code": {
        "extensions": [".py", ".js", ".java", ".cpp", ".ts", ".rs", ".go", ".html", ".json", ".yaml", ".yml", ".toml"],
        "keywords": ["src", "code", "script", "main", "app"]
    },
    "Archives": {
        "extensions": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "keywords": ["archive", "backup"]
    },
    "Installers": {
        "extensions": [".exe", ".msi", ".dmg", ".pkg"],
        "keywords": ["setup", "installer"]
    },
    "Videos": {
        "extensions": [".mp4", ".mov", ".avi", ".mkv"],
        "keywords": ["video", "clip", "recording"]
    },
    "Audio": {
        "extensions": [".mp3", ".wav", ".flac", ".aac"],
        "keywords": ["audio", "music", "sound", "podcast"]
    }
}

VALID_CATEGORIES = list(CATEGORIES.keys()) + ["Unknown"]


def _rule_based_classify(file_obs: dict) -> dict:
    """Original rule-based classifier — used as fallback."""
    name = file_obs["name"].lower()
    extension = file_obs["extension"].lower()

    best_match = {"category": "Unknown", "confidence": 0.0, "signals": []}

    for category, rules in CATEGORIES.items():
        score = 0.0
        signals = []

        if extension in rules["extensions"]:
            score += 0.6
            signals.append(f"extension:{extension}")

        for keyword in rules["keywords"]:
            if keyword in name:
                score += 0.2
                signals.append(f"keyword:{keyword}")

        if score > best_match["confidence"]:
            best_match = {
                "category": category,
                "confidence": min(score, 1.0),
                "signals": signals
            }

    return {
        "name": file_obs["name"],
        "category": best_match["category"],
        "confidence": round(best_match["confidence"], 2),
        "signals": best_match["signals"],
        "method": "rule-based"
    }


# ── Ollama LLM classifier ──────────────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

PROMPT_TEMPLATE = """You are a file classification assistant.
Given a filename and its metadata, classify it into exactly one of these categories:
Documents, Images, Code, Archives, Installers, Videos, Audio, Unknown.

Rules:
- .lnk files are Shortcuts — classify as Unknown
- .html .json .yaml .toml files → Code
- .pdf .docx .pptx .xlsx .txt → Documents
- When unsure, use your best judgment and set a low confidence

You must respond with ONLY valid JSON, no other text, no markdown, no explanation:
{{
  "category": "<category>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one short sentence>"
}}

File to classify:
Filename: {name}
Extension: {extension}
Size: {size_kb} KB"""


def _build_prompt(file_obs: dict) -> str:
    size_kb = round(file_obs.get("size_bytes", 0) / 1024, 1)
    return PROMPT_TEMPLATE.format(
        name=file_obs["name"],
        extension=file_obs["extension"],
        size_kb=size_kb
    )


def _call_llm(file_obs: dict) -> dict | None:
    """
    Call local Ollama (llama3.2) and return parsed JSON, or None on failure.
    No API key needed — runs entirely on your machine.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": _build_prompt(file_obs),
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1
        }
    }

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            raw_text = data["response"].strip()
            parsed = json.loads(raw_text)

            if parsed.get("category") not in VALID_CATEGORIES:
                parsed["category"] = "Unknown"

            return parsed

    except urllib.error.URLError:
        print(f"  [LLM] Ollama not reachable — is it running? Try: ollama serve")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  [LLM] Bad response from Ollama: {e}")
        return None
    except TimeoutError:
        print(f"  [LLM] Ollama timed out")
        return None


# ── Public interface ───────────────────────────────────────────────────────────

def classify_file(file_obs: dict) -> dict:
    """
    Classify a file observation dict.

    Decision pipeline (in order):
        1. Memory    — check learned patterns first (fastest, most personal)
        2. Ollama    — call local LLM if no memory match
        3. Rule-based — fallback if Ollama is unavailable

    Returns:
        {
            name:       str,
            category:   str,
            confidence: float,
            reasoning:  str,
            method:     "memory" | "llm" | "rule-based"
        }
    """
    print(f"  Classifying: {file_obs['name']}")

    # ── Layer 1: Memory ───────────────────────────────────────────────────────
    memory_result = _memory.lookup(file_obs, MEMORY_FILE)
    if memory_result:
        print(f"  [MEMORY] Hit: {memory_result['reasoning']}")
        return memory_result

    # ── Layer 2: Ollama LLM ───────────────────────────────────────────────────
    llm_result = _call_llm(file_obs)
    if llm_result:
        category = llm_result.get("category", "Unknown")
        if category not in VALID_CATEGORIES:
            category = "Unknown"
        return {
            "name": file_obs["name"],
            "category": category,
            "confidence": round(float(llm_result.get("confidence", 0.8)), 2),
            "reasoning": llm_result.get("reasoning", ""),
            "method": "llm"
        }

    # ── Layer 3: Rule-based fallback ──────────────────────────────────────────
    print(f"  [LLM] Falling back to rule-based for {file_obs['name']}")
    return _rule_based_classify(file_obs)


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    samples = [
        {"name": "resume_final_v3.pdf",     "extension": ".pdf",  "size_bytes": 204800},
        {"name": "screenshot_2024.png",      "extension": ".png",  "size_bytes": 512000},
        {"name": "data_pipeline.py",         "extension": ".py",   "size_bytes": 8192},
        {"name": "project_backup.zip",       "extension": ".zip",  "size_bytes": 1048576},
        {"name": "random_thing_xyz123.blob", "extension": ".blob", "size_bytes": 1024},
    ]

    for sample in samples:
        result = classify_file(sample)
        print(f"  → {result['category']} ({result['confidence']}) [{result['method']}]")
        if result.get("reasoning"):
            print(f"     Reason: {result['reasoning']}")
        print()