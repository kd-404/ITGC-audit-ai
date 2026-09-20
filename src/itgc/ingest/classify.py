"""Given a file of unknown provenance, work out what kind of evidence it is.

This is what lets the person "drop in any format" instead of telling us up
front which file is the employee master vs a UAR export vs a ticket dump.
"""
from __future__ import annotations

from pathlib import Path

from .base import load_table, match_quality
from .schemas import SCHEMAS

TABULAR_EXTS = {".xlsx", ".xlsm", ".csv", ".tsv"}
EMAIL_EXTS = {".txt", ".eml"}


def is_email_like(path: Path) -> bool:
    if path.suffix.lower() != ".eml" and path.suffix.lower() != ".txt":
        return False
    try:
        head = path.read_text(errors="ignore")[:1000]
    except Exception:
        return False
    head_lower = head.lower()
    return head_lower.startswith("from:") or ("\nfrom:" in head_lower and "\nsubject:" in head_lower)


def classify_file(path: Path) -> dict:
    """Returns {'evidence_type': str, 'confidence': float, 'loaded': LoadedTable|None}"""
    path = Path(path)
    if path.suffix.lower() in EMAIL_EXTS and is_email_like(path):
        return {"evidence_type": "email", "confidence": 1.0, "loaded": None}

    if path.suffix.lower() not in TABULAR_EXTS:
        return {"evidence_type": "unknown", "confidence": 0.0, "loaded": None}

    best_type, best_score, best_loaded = "unknown", 0.0, None
    for schema_name, schema in SCHEMAS.items():
        try:
            loaded = load_table(path, schema)
        except Exception:
            loaded = None
        score = match_quality(loaded, schema)
        # employee_master and uar_sheet can both partially match; require a
        # reasonably confident lead, not just "more columns happened to match".
        if score > best_score:
            best_type, best_score, best_loaded = schema_name, score, loaded

    if best_score < 0.4:
        return {"evidence_type": "unknown", "confidence": best_score, "loaded": best_loaded}
    return {"evidence_type": best_type, "confidence": best_score, "loaded": best_loaded}
