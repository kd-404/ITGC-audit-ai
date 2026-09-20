"""Turns generic LoadedTable rows into typed, provenance-carrying domain
objects (Employee, AccessRecord, Ticket).
"""
from __future__ import annotations

import re
from pathlib import Path

from .base import LoadedTable, parse_date_cell
from ..models import (
    Employee, AccessRecord, Ticket, ChangeRecord, PrivilegedAccessReview, BackupJob, Incident, Provenance,
)


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _bool(v) -> bool:
    s = _s(v).lower()
    return s in ("yes", "y", "true", "1", "emergency")


_FILENAME_DATE_RE = re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})")


def infer_snapshot_date_from_filename(source_file: str):
    """A UAR export named e.g. 'VPN_UAR_PeriodEnd_2026-09-15.csv' (or with no
    separators, '20260915') carries its own as-of date without needing a
    dedicated column - real exports are very often named this way. Returns
    None if no date-shaped substring is found (the common case for a single
    point-in-time export, where the caller should default to the engagement
    as_of date rather than trying to compare snapshots)."""
    from datetime import date as _date
    m = _FILENAME_DATE_RE.search(Path(source_file).stem)
    if not m:
        return None
    try:
        return _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def infer_system_name(loaded: LoadedTable, known_systems: list[str]) -> str:
    """UAR exports rarely have a 'system' column - the application name lives
    in the filename or the sheet title. Fuzzy-free substring match is enough
    since these are short, distinct proper nouns."""
    haystack = f"{loaded.source_file} {loaded.sheet_name}".lower()
    for sys_name in known_systems:
        if sys_name.lower() in haystack:
            return sys_name
    # fall back to sheet title stripped of generic words
    return loaded.sheet_name


def split_profiles(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[,;/]| and ", raw)
    return [p.strip() for p in parts if p.strip()]


def employees_from_table(loaded: LoadedTable) -> list[Employee]:
    out = []
    for row, loc in zip(loaded.rows, loaded.row_locations):
        prov = Provenance(source_file=loaded.source_file, source_type="employee_master", location=loc, raw=row)
        out.append(Employee(
            emp_id=_s(row.get("emp_id")),
            full_name=_s(row.get("full_name")),
            email=_s(row.get("email")).lower(),
            department=_s(row.get("department")) or None,
            job_title=_s(row.get("job_title")) or None,
            manager_email=_s(row.get("manager_email")).lower() or None,
            status=_s(row.get("status")) or "Unknown",
            hire_date=parse_date_cell(row.get("hire_date")),
            term_date=parse_date_cell(row.get("term_date")),
            provenance=prov,
        ))
    return out


def access_records_from_table(loaded: LoadedTable, known_systems: list[str]) -> list[AccessRecord]:
    system = infer_system_name(loaded, known_systems)
    out = []
    # A per-row "snapshot date" column wins if present; otherwise fall back to
    # a date embedded in the file name (period-start/period-end extracts are
    # very often distinguished only by filename, not a column). None means
    # "no date evidence at all" - the legacy single-snapshot case.
    filename_date = infer_snapshot_date_from_filename(loaded.source_file)
    for row, loc in zip(loaded.rows, loaded.row_locations):
        prov = Provenance(source_file=loaded.source_file, source_type="uar_sheet", location=loc, raw=row)
        out.append(AccessRecord(
            system=system,
            account_id=_s(row.get("account_id")),
            account_name=_s(row.get("account_name")),
            account_email=_s(row.get("account_email")).lower() or None,
            profiles=split_profiles(_s(row.get("profiles"))),
            account_status=_s(row.get("account_status")) or "Unknown",
            last_login=parse_date_cell(row.get("last_login")),
            provenance=prov,
            snapshot_date=parse_date_cell(row.get("snapshot_date")) or filename_date,
        ))
    return out


def tickets_from_table(loaded: LoadedTable) -> list[Ticket]:
    out = []
    for row, loc in zip(loaded.rows, loaded.row_locations):
        prov = Provenance(source_file=loaded.source_file, source_type="servicedesk", location=loc, raw=row)
        out.append(Ticket(
            ticket_id=_s(row.get("ticket_id")),
            requester_email=_s(row.get("requester_email")).lower(),
            approver_email=_s(row.get("approver_email")).lower() or None,
            system=_s(row.get("system")),
            access_requested=_s(row.get("access_requested")),
            status=_s(row.get("status")) or "Unknown",
            created=parse_date_cell(row.get("created")),
            approved=parse_date_cell(row.get("approved")),
            implemented=parse_date_cell(row.get("implemented")),
            implementer_email=_s(row.get("implementer_email")).lower() or None,
            provenance=prov,
        ))
    return out


def change_records_from_table(loaded: LoadedTable) -> list[ChangeRecord]:
    out = []
    for row, loc in zip(loaded.rows, loaded.row_locations):
        prov = Provenance(source_file=loaded.source_file, source_type="change_record", location=loc, raw=row)
        out.append(ChangeRecord(
            change_id=_s(row.get("change_id")),
            system=_s(row.get("system")),
            description=_s(row.get("description")),
            requested_by=_s(row.get("requested_by")).lower() or None,
            developer=_s(row.get("developer")).lower() or None,
            approver=_s(row.get("approver")).lower() or None,
            deployer=_s(row.get("deployer")).lower() or None,
            environment=_s(row.get("environment")) or None,
            test_evidence_ref=_s(row.get("test_evidence_ref")) or None,
            requested_date=parse_date_cell(row.get("requested_date")),
            approved_date=parse_date_cell(row.get("approved_date")),
            deployed_date=parse_date_cell(row.get("deployed_date")),
            status=_s(row.get("status")) or "Unknown",
            emergency_flag=_bool(row.get("emergency_flag")),
            post_review_date=parse_date_cell(row.get("post_review_date")),
            post_reviewed_by=_s(row.get("post_reviewed_by")).lower() or None,
            provenance=prov,
        ))
    return out


def backup_jobs_from_table(loaded: LoadedTable) -> list[BackupJob]:
    out = []
    for row, loc in zip(loaded.rows, loaded.row_locations):
        prov = Provenance(source_file=loaded.source_file, source_type="backup_job", location=loc, raw=row)
        job_type_raw = _s(row.get("job_type")).lower()
        job_type = "restore_test" if ("restore" in job_type_raw and "test" in job_type_raw) or job_type_raw == "restore" else "backup"
        out.append(BackupJob(
            job_id=_s(row.get("job_id")),
            system=_s(row.get("system")),
            scheduled_time=parse_date_cell(row.get("scheduled_time")),
            status=_s(row.get("status")) or "Unknown",
            job_type=job_type,
            verified_by=_s(row.get("verified_by")).lower() or None,
            verification_date=parse_date_cell(row.get("verification_date")),
            provenance=prov,
        ))
    return out


def incidents_from_table(loaded: LoadedTable) -> list[Incident]:
    out = []
    for row, loc in zip(loaded.rows, loaded.row_locations):
        prov = Provenance(source_file=loaded.source_file, source_type="incident", location=loc, raw=row)
        out.append(Incident(
            incident_id=_s(row.get("incident_id")),
            system=_s(row.get("system")),
            severity=_s(row.get("severity")) or "Unknown",
            reported_date=parse_date_cell(row.get("reported_date")),
            resolved_date=parse_date_cell(row.get("resolved_date")),
            root_cause=_s(row.get("root_cause")) or None,
            status=_s(row.get("status")) or "Unknown",
            description=_s(row.get("description")) or None,
            provenance=prov,
        ))
    return out


def privileged_access_reviews_from_table(loaded: LoadedTable) -> list[PrivilegedAccessReview]:
    out = []
    for row, loc in zip(loaded.rows, loaded.row_locations):
        prov = Provenance(source_file=loaded.source_file, source_type="privileged_access_review", location=loc, raw=row)
        out.append(PrivilegedAccessReview(
            review_id=_s(row.get("review_id")),
            account_id=_s(row.get("account_id")),
            system=_s(row.get("system")),
            reviewer=_s(row.get("reviewer")).lower() or None,
            review_date=parse_date_cell(row.get("review_date")),
            justification=_s(row.get("justification")) or None,
            decision=_s(row.get("decision")) or "Unknown",
            provenance=prov,
        ))
    return out
