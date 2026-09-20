"""Generic tabular ingestion: read any csv/xlsx into a grid, find the real
header row (client exports routinely have title/banner rows above it), map
its columns onto a canonical schema by fuzzy matching, and hand back clean
dict rows plus enough provenance to cite every fact back to its cell.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openpyxl
from dateutil import parser as dateparser

from .fuzzy import ratio

HEADER_MATCH_THRESHOLD = 0.72
COLUMN_MATCH_THRESHOLD = 0.72
MAX_HEADER_SEARCH_ROWS = 15


def read_grid(path: Path) -> tuple[list[list[str]], str]:
    """Returns (grid of stringified cells, sheet name or 'csv')."""
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        grid = []
        for row in ws.iter_rows(values_only=True):
            grid.append(["" if v is None else str(v) for v in row])
        return grid, ws.title
    elif path.suffix.lower() in (".csv", ".tsv"):
        delim = "\t" if path.suffix.lower() == ".tsv" else ","
        with open(path, newline="", encoding="utf-8-sig") as f:
            grid = [row for row in csv.reader(f, delimiter=delim)]
        return grid, "csv"
    else:
        raise ValueError(f"Unsupported tabular format: {path.suffix}")


def score_row_as_header(row: list[str], schema: dict[str, list[str]]) -> tuple[int, dict[int, str]]:
    """How many canonical fields does this row look like a header for?
    Returns (match_count, {col_index: canonical_field})."""
    matches: dict[int, str] = {}
    used_cols = set()
    for canonical, aliases in schema.items():
        best_col, best_score = None, 0.0
        for idx, cell in enumerate(row):
            if idx in used_cols or not str(cell).strip():
                continue
            for alias in aliases:
                s = ratio(cell, alias)
                if s > best_score:
                    best_score, best_col = s, idx
        if best_col is not None and best_score >= COLUMN_MATCH_THRESHOLD:
            matches[best_col] = canonical
            used_cols.add(best_col)
    return len(matches), matches


def detect_header_and_columns(grid: list[list[str]], schema: dict[str, list[str]]):
    """Scan the first rows for the one that best matches the schema's column
    aliases. Returns (header_row_index, column_map) or (None, {}) if nothing
    scores well enough to be usable."""
    best_idx, best_count, best_map = None, 0, {}
    for i, row in enumerate(grid[:MAX_HEADER_SEARCH_ROWS]):
        if not any(str(c).strip() for c in row):
            continue
        count, colmap = score_row_as_header(row, schema)
        if count > best_count:
            best_idx, best_count, best_map = i, count, colmap
    min_required = max(2, len(schema) // 3)
    if best_count < min_required:
        return None, {}
    return best_idx, best_map


def parse_date_cell(value: Any):
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("none", "nan", "n/a", "-"):
        return None
    try:
        return dateparser.parse(s, dayfirst=False, fuzzy=True).date()
    except (ValueError, OverflowError):
        return None


@dataclass
class LoadedTable:
    source_file: str
    sheet_name: str
    header_row_index: int
    column_map: dict[int, str]      # col_index -> canonical field
    rows: list[dict[str, Any]]      # canonical field -> raw string value
    row_locations: list[str]        # human-readable location per row, aligned with `rows`


def load_table(path: Path, schema: dict[str, list[str]]) -> LoadedTable | None:
    grid, sheet_name = read_grid(path)
    header_idx, colmap = detect_header_and_columns(grid, schema)
    if header_idx is None:
        return None
    rows, locations = [], []
    for r_offset, raw_row in enumerate(grid[header_idx + 1:], start=header_idx + 2):
        if not any(str(c).strip() for c in raw_row):
            continue
        record = {}
        for col_idx, field_name in colmap.items():
            record[field_name] = raw_row[col_idx] if col_idx < len(raw_row) else ""
        if not any(str(v).strip() for v in record.values()):
            continue
        rows.append(record)
        locations.append(f"{sheet_name}!row {r_offset}" if sheet_name != "csv" else f"row {r_offset}")
    return LoadedTable(
        source_file=Path(path).name,
        sheet_name=sheet_name,
        header_row_index=header_idx,
        column_map=colmap,
        rows=rows,
        row_locations=locations,
    )


def match_quality(loaded: LoadedTable, schema: dict[str, list[str]]) -> float:
    """0..1 - fraction of schema fields this table actually populated. Used by
    the classifier to decide which schema a file most likely represents."""
    if loaded is None:
        return 0.0
    return len(loaded.column_map) / max(1, len(schema))
