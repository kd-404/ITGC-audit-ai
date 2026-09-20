"""Cross-finding correlation: some cases (accounts/people, as already
segregated by evidence_map.py) get flagged by more than one independent
ITGC control test. A person appearing in several independently-derived
findings is a materially different risk signal than the same number of
findings scattered across different people - two or three control tests,
built independently and looking at completely different evidence shapes,
landing on the same account is corroboration, not noise.

Deterministic only: which cases qualify, which control domains are
represented, and the combined severity are all decided here, by rule, from
data already on the Finding objects - none of that is delegated to the LLM.
The LLM (via AIGateway.narrate_correlation) is used afterward only to write
the explanatory paragraph, exactly the same "verdict is law before any LLM
sees it" split as every other control in tests_itgc/.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import Severity

SEVERITY_RANK = {Severity.CRITICAL: 4, Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1}
MIN_FINDINGS_FOR_CORRELATION = 2

# Maps each FindingType value to the control_registry domain that raises it,
# so a correlated case can say how many INDEPENDENT controls agree, not just
# how many findings exist (which could all be the same rule re-firing).
FINDING_TYPE_DOMAIN = {
    "JML_TERMINATED_ACTIVE_ACCOUNT": "access_review",
    "MISSING_DEPROVISIONING_RECORD": "access_review",
    "SOD_VIOLATION_ACCESS": "access_review",
    "EXCESS_ACCESS_UNEXPECTED_ROLE": "access_review",
    "DORMANT_ACCOUNT_NOT_REVIEWED": "access_review",
    "ORPHAN_ACCOUNT": "access_review",
    "JOINER_PROVISIONING_DELAY": "access_review",
    "UAR_UNDOCUMENTED_INTERIM_ACCESS_CHANGE": "access_review",
    "PROVISIONING_SOD_SELF_APPROVED": "provisioning",
    "APPROVAL_AFTER_IMPLEMENTATION": "provisioning",
    "MISSING_APPROVAL_EVIDENCE": "provisioning",
    "ACCESS_DECISION_NOT_ACTIONED": "decision_correlation",
    "ACCESS_DECISION_CONTRADICTED": "decision_correlation",
    "OUT_OF_AUTHORITY_INSTRUCTION": "decision_correlation",
    "CHANGE_UNAPPROVED_DEPLOYMENT": "change_management",
    "CHANGE_SOD_DEVELOPER_IS_DEPLOYER": "change_management",
    "CHANGE_MISSING_TEST_EVIDENCE": "change_management",
    "CHANGE_EMERGENCY_NOT_RETROACTIVELY_REVIEWED": "change_management",
    "CHANGE_MISSING_CAB_APPROVAL": "change_management",
    "PRIVILEGED_ACCESS_NEVER_REVIEWED": "privileged_access",
    "PRIVILEGED_ACCESS_RETAINED_WITHOUT_JUSTIFICATION": "privileged_access",
    "PRIVILEGED_ACCESS_SELF_REVIEWED": "privileged_access",
    "BACKUP_JOB_FAILURE_UNRESOLVED": "backup_recovery",
    "BACKUP_NEVER_VERIFIED": "backup_recovery",
    "BACKUP_RESTORE_NEVER_TESTED": "backup_recovery",
    "INCIDENT_SLA_BREACH": "incident_management",
    "INCIDENT_MISSING_ROOT_CAUSE": "incident_management",
    "INCIDENT_RECURRING_UNADDRESSED": "incident_management",
}


@dataclass
class CorrelatedCase:
    case_id: str
    subject_label: str
    subject_email: str | None
    finding_ids: list[str]
    finding_types: list[str]
    control_domains: list[str]      # distinct domains represented, sorted
    combined_severity: Severity
    narrative: str | None = None


def build_correlated_cases(evidence_cases: list, findings: list) -> list[CorrelatedCase]:
    """`evidence_cases` are EvidenceCase objects from evidence_map.py (already
    grouped by person/account); this re-groups their related_finding_ids by
    actual Finding objects and keeps only cases with 2+ findings."""
    findings_by_id = {f.finding_id: f for f in findings}
    out: list[CorrelatedCase] = []

    for case in evidence_cases:
        case_findings = [findings_by_id[fid] for fid in case.related_finding_ids if fid in findings_by_id]
        if len(case_findings) < MIN_FINDINGS_FOR_CORRELATION:
            continue
        domains = sorted({FINDING_TYPE_DOMAIN.get(f.finding_type.value, "other") for f in case_findings})
        combined_severity = max(case_findings, key=lambda f: SEVERITY_RANK.get(f.severity, 0)).severity
        out.append(CorrelatedCase(
            case_id=case.case_id,
            subject_label=case.subject_label,
            subject_email=case.subject_email,
            finding_ids=[f.finding_id for f in case_findings],
            finding_types=[f.finding_type.value for f in case_findings],
            control_domains=domains,
            combined_severity=combined_severity,
        ))

    # strongest signal first: more independent domains agreeing, then higher
    # combined severity, then more findings overall
    out.sort(key=lambda c: (-len(c.control_domains), -SEVERITY_RANK.get(c.combined_severity, 0), -len(c.finding_ids)))
    return out


def correlated_cases_to_json(cases: list[CorrelatedCase]) -> list[dict]:
    return [
        {
            "case_id": c.case_id,
            "subject_label": c.subject_label,
            "subject_email": c.subject_email,
            "finding_ids": c.finding_ids,
            "finding_types": c.finding_types,
            "control_domains": c.control_domains,
            "combined_severity": c.combined_severity.value,
            "narrative": c.narrative,
        }
        for c in cases
    ]
