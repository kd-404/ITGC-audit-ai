"""Ingestion entry point: point this at a folder of arbitrary evidence files
and get back typed, classified objects plus a list of anything it couldn't
make sense of (which becomes an enquiry, not a silent drop)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .classify import classify_file
from .email_reader import parse_email_file
from .loaders import (
    employees_from_table, access_records_from_table, tickets_from_table,
    change_records_from_table, privileged_access_reviews_from_table,
    backup_jobs_from_table, incidents_from_table,
)
from ..models import (
    Employee, AccessRecord, Ticket, ChangeRecord, PrivilegedAccessReview, BackupJob, Incident, EmailEvidence,
)


@dataclass
class EvidenceBundle:
    employees: list[Employee] = field(default_factory=list)
    access_records: list[AccessRecord] = field(default_factory=list)
    tickets: list[Ticket] = field(default_factory=list)
    change_records: list[ChangeRecord] = field(default_factory=list)
    privileged_access_reviews: list[PrivilegedAccessReview] = field(default_factory=list)
    backup_jobs: list[BackupJob] = field(default_factory=list)
    incidents: list[Incident] = field(default_factory=list)
    emails: list[EmailEvidence] = field(default_factory=list)
    unclassified_files: list[str] = field(default_factory=list)
    file_classifications: list[dict] = field(default_factory=list)  # for the audit trail / workpaper


def ingest_directory(root: Path, known_systems: list[str]) -> EvidenceBundle:
    root = Path(root)
    bundle = EvidenceBundle()
    files = [p for p in sorted(root.rglob("*")) if p.is_file() and not p.name.startswith(".")]

    for path in files:
        result = classify_file(path)
        etype, confidence, loaded = result["evidence_type"], result["confidence"], result["loaded"]
        bundle.file_classifications.append({
            "file": str(path.relative_to(root)), "evidence_type": etype, "confidence": round(confidence, 2),
        })

        if etype == "employee_master" and loaded:
            bundle.employees.extend(employees_from_table(loaded))
        elif etype == "uar_sheet" and loaded:
            bundle.access_records.extend(access_records_from_table(loaded, known_systems))
        elif etype == "servicedesk" and loaded:
            bundle.tickets.extend(tickets_from_table(loaded))
        elif etype == "change_record" and loaded:
            bundle.change_records.extend(change_records_from_table(loaded))
        elif etype == "privileged_access_review" and loaded:
            bundle.privileged_access_reviews.extend(privileged_access_reviews_from_table(loaded))
        elif etype == "backup_job" and loaded:
            bundle.backup_jobs.extend(backup_jobs_from_table(loaded))
        elif etype == "incident" and loaded:
            bundle.incidents.extend(incidents_from_table(loaded))
        elif etype == "email":
            bundle.emails.append(parse_email_file(path))
        else:
            bundle.unclassified_files.append(str(path.relative_to(root)))

    return bundle
