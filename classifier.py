CATEGORIES = {
    "Documents": {
        "extensions": [".pdf", ".docx", ".txt", ".pptx", ".xlsx"],
        "keywords": ["resume", "invoice", "notes", "report", "assignment"]
    },
    "Images": {
        "extensions": [".jpg", ".jpeg", ".png", ".svg"],
        "keywords": ["img", "image", "photo", "screenshot"]
    },
    "Code": {
        "extensions": [".py", ".js", ".java", ".cpp"],
        "keywords": ["src", "code", "script"]
    },
    "Archives": {
        "extensions": [".zip", ".rar", ".7z"],
        "keywords": ["archive", "backup"]
    },
    "Installers": {
        "extensions": [".exe", ".msi"],
        "keywords": ["setup", "installer"]
    }
}

def classify_file(file_obs):
    name = file_obs["name"].lower()
    extension = file_obs["extension"].lower()

    best_match = {
        "category": "Unknown",
        "confidence": 0.0,
        "signals": []
    }

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
        "signals": best_match["signals"]
    }

if __name__ == "__main__":
    sample = {
        "name": "resume_final_v3.pdf",
        "extension": ".pdf"
    }

    result = classify_file(sample)
    print(result)
