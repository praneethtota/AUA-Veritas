"""
core/field_classifier.py — Domain classifier for AUA-Veritas.

Keyword-based domain classification. Returns a probability distribution
over known domains. Used by the router to inject corrections and compute
VCG welfare scores. No external API calls — fully local.
"""
import math

KNOWN_DOMAINS = [
    "software_engineering", "mathematics", "legal", "medical",
    "finance", "science", "education", "general",
]

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "software_engineering": [
        "code", "function", "algorithm", "python", "javascript", "typescript",
        "java", "debug", "sort", "array", "class", "api", "bug", "complexity",
        "loop", "data structure", "database", "sql", "async", "git", "docker",
        "endpoint", "fastapi", "react", "backend", "frontend", "variable",
        "syntax", "compiler", "runtime", "deploy", "server", "postgres",
        "sqlite", "schema", "migration", "orm", "rest", "graphql",
    ],
    "mathematics": [
        "proof", "theorem", "equation", "integral", "derivative", "matrix",
        "vector", "probability", "calculus", "algebra", "geometry", "prime",
        "factorial", "statistics", "regression", "distribution", "formula",
        "solve", "compute", "calculate", "sum", "product", "series",
    ],
    "legal": [
        "legal", "contract", "statute", "court", "liability", "regulation",
        "attorney", "plaintiff", "defendant", "lawsuit", "precedent", "tort",
        "jurisdiction", "intellectual property", "patent", "copyright", "gdpr",
    ],
    "medical": [
        "patient", "diagnosis", "treatment", "drug", "dose", "symptom",
        "medical", "clinical", "disease", "therapy", "surgery", "prescription",
        "hospital", "doctor", "medication", "condition", "health", "anatomy",
    ],
    "finance": [
        "stock", "portfolio", "investment", "return", "risk", "dividend",
        "valuation", "market", "asset", "equity", "bond", "fund", "crypto",
        "budget", "revenue", "profit", "tax", "accounting", "balance sheet",
    ],
    "science": [
        "physics", "chemistry", "biology", "experiment", "hypothesis",
        "molecule", "atom", "energy", "force", "quantum", "evolution",
        "dna", "cell", "reaction", "element", "compound", "gravity",
    ],
    "education": [
        "explain", "teach", "learn", "understand", "concept", "study",
        "tutorial", "example", "definition", "what is", "how does",
        "why does", "difference between", "compare",
    ],
}


class FieldClassifier:
    """Keyword-based domain classifier — no external API calls."""

    def classify(self, task: str) -> dict[str, float]:
        text = task.lower()
        scores: dict[str, float] = {d: 0.0 for d in KNOWN_DOMAINS}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    scores[domain] += 1.0
        total = sum(scores.values())
        if total == 0:
            return {"general": 1.0}
        return {d: s / total for d, s in scores.items() if s > 0}

    def reset_history(self):
        pass


_default_classifier = FieldClassifier()

def classify_field(task: str) -> dict[str, float]:
    return _default_classifier.classify(task)
