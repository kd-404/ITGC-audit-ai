"""Lightweight fuzzy matching (stdlib difflib only - no external dependency).

Used for two different jobs that must not be confused:
  - matching a messy COLUMN HEADER to a canonical field name ("Emp Code" -> emp_id)
  - matching a PERSON'S NAME/EMAIL across sources for identity resolution
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher


def normalize(s: str) -> str:
    s = s or ""
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def best_match(target: str, candidates: list[str]) -> tuple[str | None, float]:
    """Return (best candidate, score 0..1) or (None, 0.0) if candidates empty."""
    if not candidates:
        return None, 0.0
    scored = sorted(((c, ratio(target, c)) for c in candidates), key=lambda x: -x[1])
    return scored[0]


def name_key(full_name: str) -> str:
    """Normalized 'first last' key ignoring middle names/initials, for loose name matching."""
    n = normalize(full_name)
    parts = [p for p in n.split() if len(p) > 1]
    if len(parts) >= 2:
        return f"{parts[0]} {parts[-1]}"
    return n
