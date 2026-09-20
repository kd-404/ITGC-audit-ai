"""ITGC test: orphan accounts - active accounts in an application's UAR that
cannot be tied to anyone in the employee master at all. These aren't a
gap in our matching (identity resolution already tried exact/local-part
email and fuzzy name matching); they're a gap in the CLIENT's data - a
contractor never onboarded to HR, a leaver whose HRIS record was purged
too early, or a bogus/shared account.
"""
from __future__ import annotations

from ..models import Finding, FindingType, Severity
from .idgen import IdGen

ACTIVE_STATES_EXCLUDED = {"disabled", "inactive", "revoked", "closed", "terminated", "removed"}


def run_orphan_test(ctx, ids: IdGen) -> list[Finding]:
    findings: list[Finding] = []
    for rec in ctx.current_access_records():
        if rec.matched_employee is not None:
            continue
        if rec.account_status.strip().lower() in ACTIVE_STATES_EXCLUDED:
            continue
        severity = Severity.HIGH if any(p.lower() in ("ap admin", "admin") for p in rec.profiles) else Severity.MEDIUM
        findings.append(Finding(
            finding_id=ids.next("FND"),
            finding_type=FindingType.ORPHAN_ACCOUNT,
            severity=severity,
            system=rec.system,
            subject_person=rec.account_name,
            subject_email=rec.account_email,
            condition=f"Account {rec.account_id} ({rec.account_name}, {rec.account_email or 'no email on file'}) "
                      f"in {rec.system} has profile(s) {', '.join(rec.profiles) or 'unspecified'} and status "
                      f"{rec.account_status}, but does not match any record in the employee master by email or name.",
            criteria=f"{ctx.policy.policy_reference}: every application account must be traceable to an "
                     f"active, authorized employee or an approved third-party/contractor record.",
            cause="Likely a contractor or external party account never captured in the HR system, or an "
                  "employee record that was removed from HR before the account was addressed.",
            effect="An account with no owner of record cannot be included in access reviews, cannot be tied "
                   "to an accountable individual, and may represent unauthorized or forgotten access.",
            recommendation="Identify the account owner directly with the application/system owner, confirm "
                           "business justification, and either onboard them properly (contractor record) or "
                           "disable the account.",
            evidence=[rec.provenance.cite()],
            confidence=0.9,
        ))
    return findings
