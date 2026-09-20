"""Registry of selectable ITGC control domains: what each one checks, and
what evidence it needs to run meaningfully.

This is the backbone of the "which control do you want to check, and what
do you need to give me for it" flow: the webapp's Controls tab lists
`list_controls()`, the person picks one or more control_ids, the UI shows
that domain's `required_evidence`/`optional_evidence` back to them, and the
selected control_ids are passed straight through to
`pipeline.run_pipeline(selected_controls=...)`, which only runs the test
functions for the domains actually chosen.

Domain boundaries here mirror the actual test modules under tests_itgc/,
not an idealized taxonomy - "access_review" bundles jml/joiner/access/orphan
because they all key off the same two evidence shapes (employee master +
UAR export) and were built and validated together; provisioning,
decision_correlation, change_management and privileged_access each depend
on a distinct evidence shape the others don't need, so they're separate.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ControlDomain:
    control_id: str
    name: str
    description: str
    required_evidence: list[str]
    optional_evidence: list[str] = field(default_factory=list)
    finding_types: list[str] = field(default_factory=list)


CONTROL_DOMAINS: list[ControlDomain] = [
    ControlDomain(
        control_id="access_review",
        name="User Access Review (JML, SoD, Orphan Accounts)",
        description=(
            "Joiner/mover/leaver deprovisioning, segregation-of-duties conflicts, excess or "
            "unexpected access, dormant accounts, and orphan (unmatched) accounts - the core "
            "user access review control set."
        ),
        required_evidence=[
            "Employee master list (active and terminated employees, hire/term dates, manager)",
            "User access review (UAR) export for each in-scope system (account status, profiles held)",
        ],
        optional_evidence=[
            "Service desk / ticketing export (helps corroborate provisioning/deprovisioning)",
            "A second, differently-dated UAR export for the same system (period-start vs period-end) - "
            "lets the review compare access changes made DURING the period, not just what's held on the "
            "day the extract was pulled. A dated filename or a snapshot-date column both work.",
        ],
        finding_types=[
            "JML_TERMINATED_ACTIVE_ACCOUNT", "MISSING_DEPROVISIONING_RECORD", "SOD_VIOLATION_ACCESS",
            "EXCESS_ACCESS_UNEXPECTED_ROLE", "DORMANT_ACCOUNT_NOT_REVIEWED", "ORPHAN_ACCOUNT",
            "JOINER_PROVISIONING_DELAY", "UAR_UNDOCUMENTED_INTERIM_ACCESS_CHANGE",
        ],
    ),
    ControlDomain(
        control_id="provisioning",
        name="Provisioning & Approval Evidence",
        description=(
            "Whether every access grant has independent, evidenced approval: self-approved "
            "requests, approval recorded after implementation, and grants with no approval "
            "evidence at all."
        ),
        required_evidence=[
            "Service desk / ticketing export (requester, approver, dates, status)",
        ],
        optional_evidence=[
            "Employee master list and UAR export (needed to evaluate profile-level approval coverage)",
            "Email correspondence discussing access approvals",
        ],
        finding_types=[
            "PROVISIONING_SOD_SELF_APPROVED", "APPROVAL_AFTER_IMPLEMENTATION", "MISSING_APPROVAL_EVIDENCE",
        ],
    ),
    ControlDomain(
        control_id="decision_correlation",
        name="Email Decision Correlation",
        description=(
            "Cross-checks manager retain/revoke instructions found in email against what the "
            "UAR export actually shows: decisions never actioned, contradicted by a later "
            "instruction, or given by someone without reporting authority over the person."
        ),
        required_evidence=[
            "Email correspondence discussing access decisions (retain/revoke instructions)",
            "Employee master list (to resolve names and reporting lines)",
            "User access review (UAR) export (to check what was actually done)",
        ],
        finding_types=[
            "ACCESS_DECISION_NOT_ACTIONED", "ACCESS_DECISION_CONTRADICTED", "OUT_OF_AUTHORITY_INSTRUCTION",
        ],
    ),
    ControlDomain(
        control_id="change_management",
        name="Change Management",
        description=(
            "Unapproved or out-of-sequence deployments, developer/deployer segregation, missing "
            "test evidence, unreviewed emergency changes, and missing CAB approval for sensitive "
            "systems."
        ),
        required_evidence=[
            "Change/release log export (change ID, developer, approver, deployer, dates, "
            "environment, test evidence reference, emergency flag)",
        ],
        optional_evidence=[
            "Employee master list (to resolve names and check approver job titles for CAB eligibility)",
        ],
        finding_types=[
            "CHANGE_UNAPPROVED_DEPLOYMENT", "CHANGE_SOD_DEVELOPER_IS_DEPLOYER",
            "CHANGE_MISSING_TEST_EVIDENCE", "CHANGE_EMERGENCY_NOT_RETROACTIVELY_REVIEWED",
            "CHANGE_MISSING_CAB_APPROVAL",
        ],
    ),
    ControlDomain(
        control_id="privileged_access",
        name="Privileged Access Management",
        description=(
            "Whether privileged access is periodically re-certified: accounts never reviewed, "
            "retained with no real justification, or reviewed by the account holder themselves."
        ),
        required_evidence=[
            "User access review (UAR) export (to identify who holds a privileged profile)",
            "Privileged access review / re-certification export (reviewer, review date, "
            "justification, decision)",
        ],
        optional_evidence=[
            "Role/access matrix marking which profiles are privileged per system "
            "(role_access_matrix.yaml's privileged_profiles list)",
        ],
        finding_types=[
            "PRIVILEGED_ACCESS_NEVER_REVIEWED", "PRIVILEGED_ACCESS_RETAINED_WITHOUT_JUSTIFICATION",
            "PRIVILEGED_ACCESS_SELF_REVIEWED",
        ],
    ),
    ControlDomain(
        control_id="backup_recovery",
        name="Backup & Recovery",
        description=(
            "Whether backups actually protect the business: unresolved backup failures, backups "
            "that report success but were never independently verified, and restore capability "
            "that has never been (or hasn't recently been) tested."
        ),
        required_evidence=[
            "Backup job log/export per system (job ID, scheduled time, status, verified by/date, "
            "and a job type distinguishing routine backups from restore tests)",
        ],
        finding_types=[
            "BACKUP_JOB_FAILURE_UNRESOLVED", "BACKUP_NEVER_VERIFIED", "BACKUP_RESTORE_NEVER_TESTED",
        ],
    ),
    ControlDomain(
        control_id="incident_management",
        name="Incident Management",
        description=(
            "Whether incidents are resolved within SLA, closed with a documented root cause, and "
            "not silently recurring with nothing on record that actually fixed the underlying issue."
        ),
        required_evidence=[
            "Incident log/export per system (incident ID, severity, description, reported/resolved "
            "dates, root cause, status)",
        ],
        optional_evidence=[
            "Change/release log export (to check whether a recurring incident was ever actually "
            "remediated by a documented change)",
        ],
        finding_types=[
            "INCIDENT_SLA_BREACH", "INCIDENT_MISSING_ROOT_CAUSE", "INCIDENT_RECURRING_UNADDRESSED",
        ],
    ),
]

CONTROL_DOMAINS_BY_ID: dict[str, ControlDomain] = {c.control_id: c for c in CONTROL_DOMAINS}
ALL_CONTROL_IDS: list[str] = [c.control_id for c in CONTROL_DOMAINS]


def list_controls() -> list[dict]:
    """JSON-serializable listing for the webapp's Controls tab."""
    return [
        {
            "control_id": c.control_id,
            "name": c.name,
            "description": c.description,
            "required_evidence": c.required_evidence,
            "optional_evidence": c.optional_evidence,
            "finding_types": c.finding_types,
        }
        for c in CONTROL_DOMAINS
    ]


def resolve_selected_controls(selected: list[str] | None) -> set[str]:
    """Normalizes a possibly-None/partial selection from the UI into a valid
    set of control_ids. Unknown ids are silently dropped rather than
    rejected outright, since a stale UI build shouldn't break a run; an
    empty/None selection means "run everything" (the pre-existing default
    behavior, kept for backward compatibility with callers that don't know
    about control selection at all)."""
    if not selected:
        return set(ALL_CONTROL_IDS)
    valid = {c for c in selected if c in CONTROL_DOMAINS_BY_ID}
    return valid or set(ALL_CONTROL_IDS)
