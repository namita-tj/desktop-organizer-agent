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
from src.memory import MEMORY_FILE, lookup
from src.logger import get_logger
from src.extractor import extract_text
from src.entities import extract_entities
log = get_logger(__name__)

# ── Rule-based fallback ────────────────────────────────────────────────────────

CATEGORIES = {
    "Documents": {
        "extensions": [".pdf", ".docx", ".txt", ".pptx", ".xlsx"],
        "keywords":   ["resume", "invoice", "notes", "report", "assignment"]
    },
    "Images": {
        "extensions": [".jpg", ".jpeg", ".png", ".svg", ".webp", ".gif"],
        "keywords":   ["img", "image", "photo", "screenshot"]
    },
    "Code": {
        "extensions": [".py", ".js", ".java", ".cpp", ".ts", ".rs", ".go",
                       ".html", ".json", ".yaml", ".yml", ".toml"],
        "keywords":   ["src", "code", "script", "main", "app"]
    },
    "Archives": {
        "extensions": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "keywords":   ["archive", "backup"]
    },
    "Installers": {
        "extensions": [".exe", ".msi", ".dmg", ".pkg"],
        "keywords":   ["setup", "installer"]
    },
    "Videos": {
        "extensions": [".mp4", ".mov", ".avi", ".mkv"],
        "keywords":   ["video", "clip", "recording"]
    },
    "Audio": {
        "extensions": [".mp3", ".wav", ".flac", ".aac"],
        "keywords":   ["audio", "music", "sound", "podcast"]
    }
}

VALID_CATEGORIES = list(CATEGORIES.keys()) + ["Unknown"]


def _rule_based_classify(file_obs: dict) -> dict:
    """Rule-based fallback classifier."""
    name      = file_obs["name"].lower()
    extension = file_obs["extension"].lower()

    best_match = {"category": "Unknown", "confidence": 0.0, "signals": []}

    for category, rules in CATEGORIES.items():
        score   = 0.0
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
                "category":   category,
                "confidence": min(score, 1.0),
                "signals":    signals
            }

    result = {
        "name":       file_obs["name"],
        "category":   best_match["category"],
        "confidence": round(best_match["confidence"], 2),
        "signals":    best_match["signals"],
        "method":     "rule-based"
    }
    log.debug("Rule-based: %s → %s (%.2f)", file_obs["name"],
              result["category"], result["confidence"])
    return result


# ── Ollama LLM classifier ──────────────────────────────────────────────────────

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

PROMPT_TEMPLATE = """You are an enterprise document classifier.
Classify this document based on its filename AND content.

Categories: {categories}

Document metadata:
Filename:   {name}
Extension:  {extension}
Size:       {size_kb} KB

Content preview (first 2000 chars):
{content}

Extracted entities:
{entities}

Respond ONLY with valid JSON:
{{
  "category": "<category>",
  "subcategory": "<specific type e.g. invoice, nda, lab_result>",
  "confidence": <0.0-1.0>,
  "reasoning": "<one sentence>",
  "suggested_filename": "<structured name e.g. 2026-04-12_Siemens_Invoice_4521.pdf>"
}}"""


def _build_prompt(file_obs: dict) -> str:
    size_kb   = round(file_obs.get("size_bytes", 0) / 1024, 1)
    categories = ", ".join(VALID_CATEGORIES)

    return PROMPT_TEMPLATE.format(
        name=file_obs["name"],
        extension=file_obs["extension"],
        size_kb=size_kb,
        content=file_obs.get("content", ""),
        entities=json.dumps(file_obs.get("entities", {}), indent=2),
        categories=categories
    )


def _call_llm(file_obs: dict) -> dict | None:
    """Call local Ollama and return parsed JSON, or None on failure."""
    payload = {
        "model":   OLLAMA_MODEL,
        "prompt":  _build_prompt(file_obs),
        "stream":  False,
        "format":  "json",
        "options": {"temperature": 0.1}
    }

    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data     = json.loads(resp.read())
            raw_text = data["response"].strip()
            parsed   = json.loads(raw_text)

            if parsed.get("category") not in VALID_CATEGORIES:
                log.warning("LLM returned invalid category '%s' for %s - correcting to Unknown",
                            parsed.get("category"), file_obs["name"])
                parsed["category"] = "Unknown"

            log.debug("LLM: %s -> %s (%.2f)", file_obs["name"],
                      parsed["category"], parsed.get("confidence", 0))
            return parsed

    except urllib.error.URLError:
        log.warning("Ollama not reachable for %s - is it running? Try: ollama serve",
                    file_obs["name"])
        return None
    except (json.JSONDecodeError, KeyError) as e:
        log.warning("Bad response from Ollama for %s: %s", file_obs["name"], e)
        return None
    except TimeoutError:
        log.warning("Ollama timed out for %s", file_obs["name"])
        return None


# ── Public interface ───────────────────────────────────────────────────────────

def classify_file(file_obs: dict) -> dict:
    print(f"  Classifying: {file_obs['name']}")

    # ── Layer 0: Content extraction ───────────────────────────────────────────
    content = ""
    entities = {}

    if "path" in file_obs:
        content = extract_text(file_obs)
        entities = extract_entities(content) if content else {}

    # Enrich file_obs so the LLM prompt gets content
    enriched_obs = dict(file_obs)
    enriched_obs["content"] = content
    enriched_obs["entities"] = entities

    # ── Layer 1: Memory ───────────────────────────────────────────────────────
    memory_result = lookup(enriched_obs)

    if memory_result:
        memory_result["entities"]    = entities
        memory_result["is_sensitive"] = entities.get("is_sensitive", False)
        return memory_result

    # ── Layer 2: Ollama LLM ───────────────────────────────────────────────────
    llm_result = _call_llm(enriched_obs)

    if llm_result:
        category = llm_result.get("category", "Unknown")

        if category not in VALID_CATEGORIES:
            log.warning("Correcting invalid LLM category '%s' → Unknown", category)
            category = "Unknown"

        return {
            "name": file_obs["name"],
            "category": category,
            "subcategory": llm_result.get("subcategory") or entities.get("document_type", ""),
            "confidence": round(float(llm_result.get("confidence", 0.8)), 2),
            "reasoning": llm_result.get("reasoning", ""),
            "suggested_filename": llm_result.get("suggested_filename", ""),
            "entities": entities,
            "is_sensitive": entities.get("is_sensitive", False),
            "method": "llm"
        }


    # ── Layer 3: Rule-based fallback ──────────────────────────────────────────
    result = _rule_based_classify(file_obs)
    result["entities"]    = entities
    result["is_sensitive"] = entities.get("is_sensitive", False)
    return result


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
        print(f"  -> {result['category']} ({result['confidence']}) [{result['method']}]")
        if result.get("reasoning"):
            print(f"     Reason: {result['reasoning']}")
        print()