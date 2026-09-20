"""Core data model for the ITGC audit assistant.

Everything downstream (identity resolution, ITGC tests, correlation, reporting)
works off these plain dataclasses rather than raw rows, so a test never has to
know whether a fact came from a spreadsheet, a CSV export or an email.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Optional


# --------------------------------------------------------------------------
# Provenance - every fact traces back to exactly where it came from
# --------------------------------------------------------------------------
@dataclass
class Provenance:
    source_file: str
    source_type: str          # employee_master | uar_sheet | servicedesk | email
    location: str              # e.g. "row 8" or sheet!cell, or "email body"
    raw: dict[str, Any] = field(default_factory=dict)

    def cite(self) -> str:
        return f"{self.source_file} ({self.location})"


# --------------------------------------------------------------------------
# Company context
# --------------------------------------------------------------------------
@dataclass
class Employee:
    emp_id: str
    full_name: str
    email: str
    department: Optional[str]
    job_title: Optional[str]
    manager_email: Optional[str]
    status: str                 # Active | Terminated
    hire_date: Optional[date]
    term_date: Optional[date]
    provenance: Provenance


# --------------------------------------------------------------------------
# Evidence: access records extracted from UAR sheets
# --------------------------------------------------------------------------
@dataclass
class AccessRecord:
    system: str
    account_id: str
    account_name: str
    account_email: Optional[str]
    profiles: list[str]         # split out of a possibly comma-joined cell
    account_status: str         # Active | Disabled | ...
    last_login: Optional[date]
    provenance: Provenance
    matched_employee: Optional[Employee] = None
    match_confidence: float = 0.0
    match_method: str = "unmatched"
    # When a UAR export carries its own "as of" date (either a column, or a
    # date embedded in the filename - see loaders.access_records_from_table),
    # this lets the same system be evidenced by more than one dated extract
    # (e.g. period-start vs period-end) instead of a single point-in-time
    # snapshot. None means "no date given" - legacy single-snapshot behavior.
    snapshot_date: Optional[date] = None


# --------------------------------------------------------------------------
# Evidence: service desk / ticketing
# --------------------------------------------------------------------------
@dataclass
class Ticket:
    ticket_id: str
    requester_email: str
    approver_email: Optional[str]
    system: str
    access_requested: str
    status: str
    created: Optional[date]
    approved: Optional[date]
    implemented: Optional[date]
    implementer_email: Optional[str]
    provenance: Provenance


# --------------------------------------------------------------------------
# Evidence: change management (change/release records)
# --------------------------------------------------------------------------
@dataclass
class ChangeRecord:
    change_id: str
    system: str
    description: str
    requested_by: Optional[str]
    developer: Optional[str]
    approver: Optional[str]
    deployer: Optional[str]
    environment: Optional[str]
    test_evidence_ref: Optional[str]
    requested_date: Optional[date]
    approved_date: Optional[date]
    deployed_date: Optional[date]
    status: str
    emergency_flag: bool
    post_review_date: Optional[date]
    post_reviewed_by: Optional[str]
    provenance: Provenance


# --------------------------------------------------------------------------
# Evidence: privileged access review (periodic re-certification records)
# --------------------------------------------------------------------------
@dataclass
class PrivilegedAccessReview:
    review_id: str
    account_id: str
    system: str
    reviewer: Optional[str]
    review_date: Optional[date]
    justification: Optional[str]
    decision: str
    provenance: Provenance


# --------------------------------------------------------------------------
# Evidence: backup & recovery jobs
# --------------------------------------------------------------------------
@dataclass
class BackupJob:
    job_id: str
    system: str
    scheduled_time: Optional[date]
    status: str
    job_type: str               # "backup" | "restore_test"
    verified_by: Optional[str]
    verification_date: Optional[date]
    provenance: Provenance


# --------------------------------------------------------------------------
# Evidence: incident management
# --------------------------------------------------------------------------
@dataclass
class Incident:
    incident_id: str
    system: str
    severity: str
    reported_date: Optional[date]
    resolved_date: Optional[date]
    root_cause: Optional[str]
    status: str
    description: Optional[str]
    provenance: Provenance


# --------------------------------------------------------------------------
# Evidence: email
# --------------------------------------------------------------------------
@dataclass
class EmailEvidence:
    sender: str
    recipient: str
    subject: str
    sent_date: Optional[date]
    body: str
    provenance: Provenance
    mentions_systems: list[str] = field(default_factory=list)
    mentions_people: list[str] = field(default_factory=list)
    is_approval_like: bool = False
    security_mentioned: bool = False
    security_skipped: bool = False


# --------------------------------------------------------------------------
# Findings & enquiries
# --------------------------------------------------------------------------
class FindingType(str, Enum):
    JML_TERMINATED_ACTIVE_ACCOUNT = "JML_TERMINATED_ACTIVE_ACCOUNT"
    MISSING_DEPROVISIONING_RECORD = "MISSING_DEPROVISIONING_RECORD"
    SOD_VIOLATION_ACCESS = "SOD_VIOLATION_ACCESS"
    PROVISIONING_SOD_SELF_APPROVED = "PROVISIONING_SOD_SELF_APPROVED"
    MISSING_APPROVAL_EVIDENCE = "MISSING_APPROVAL_EVIDENCE"
    APPROVAL_AFTER_IMPLEMENTATION = "APPROVAL_AFTER_IMPLEMENTATION"
    ORPHAN_ACCOUNT = "ORPHAN_ACCOUNT"
    EXCESS_ACCESS_UNEXPECTED_ROLE = "EXCESS_ACCESS_UNEXPECTED_ROLE"
    DORMANT_ACCOUNT_NOT_REVIEWED = "DORMANT_ACCOUNT_NOT_REVIEWED"
    JOINER_PROVISIONING_DELAY = "JOINER_PROVISIONING_DELAY"
    POLICY_GAP = "POLICY_GAP"
    ACCESS_DECISION_NOT_ACTIONED = "ACCESS_DECISION_NOT_ACTIONED"
    ACCESS_DECISION_CONTRADICTED = "ACCESS_DECISION_CONTRADICTED"
    OUT_OF_AUTHORITY_INSTRUCTION = "OUT_OF_AUTHORITY_INSTRUCTION"
    CHANGE_UNAPPROVED_DEPLOYMENT = "CHANGE_UNAPPROVED_DEPLOYMENT"
    CHANGE_SOD_DEVELOPER_IS_DEPLOYER = "CHANGE_SOD_DEVELOPER_IS_DEPLOYER"
    CHANGE_MISSING_TEST_EVIDENCE = "CHANGE_MISSING_TEST_EVIDENCE"
    CHANGE_EMERGENCY_NOT_RETROACTIVELY_REVIEWED = "CHANGE_EMERGENCY_NOT_RETROACTIVELY_REVIEWED"
    CHANGE_MISSING_CAB_APPROVAL = "CHANGE_MISSING_CAB_APPROVAL"
    PRIVILEGED_ACCESS_NEVER_REVIEWED = "PRIVILEGED_ACCESS_NEVER_REVIEWED"
    PRIVILEGED_ACCESS_RETAINED_WITHOUT_JUSTIFICATION = "PRIVILEGED_ACCESS_RETAINED_WITHOUT_JUSTIFICATION"
    PRIVILEGED_ACCESS_SELF_REVIEWED = "PRIVILEGED_ACCESS_SELF_REVIEWED"
    BACKUP_JOB_FAILURE_UNRESOLVED = "BACKUP_JOB_FAILURE_UNRESOLVED"
    BACKUP_NEVER_VERIFIED = "BACKUP_NEVER_VERIFIED"
    BACKUP_RESTORE_NEVER_TESTED = "BACKUP_RESTORE_NEVER_TESTED"
    INCIDENT_SLA_BREACH = "INCIDENT_SLA_BREACH"
    INCIDENT_MISSING_ROOT_CAUSE = "INCIDENT_MISSING_ROOT_CAUSE"
    INCIDENT_RECURRING_UNADDRESSED = "INCIDENT_RECURRING_UNADDRESSED"
    UAR_UNDOCUMENTED_INTERIM_ACCESS_CHANGE = "UAR_UNDOCUMENTED_INTERIM_ACCESS_CHANGE"


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


@dataclass
class Finding:
    finding_id: str
    finding_type: FindingType
    severity: Severity
    system: str
    subject_person: Optional[str]      # name for readability
    subject_email: Optional[str]
    condition: str                      # what we found
    criteria: str                       # what should have been true (policy/control)
    cause: str                          # why, if determinable
    effect: str                         # risk / consequence
    recommendation: str
    evidence: list[str]                 # citations, "file (location)"
    confidence: float
    narrative: Optional[str] = None     # LLM-produced explanation, optional


@dataclass
class Enquiry:
    enquiry_id: str
    topic: str
    question: str
    context: str
    blocking: bool = True
    answer: Optional[str] = None
