"""ITGC tests operating on the aggregated access profile a person holds in
each system: segregation-of-duties conflicts, access outside their role
(excess/unexpected), and dormant accounts that were never reviewed/revoked.

Terminated employees are skipped here - jml.py already owns "should this
account even be active" for them, and re-flagging the same account under a
different finding type would just be noise.
"""
from __future__ import annotations

from ..models import Finding, FindingType, Severity
from .idgen import IdGen

ACTIVE_STATES_EXCLUDED = {"disabled", "inactive", "revoked", "closed", "terminated", "removed"}
GENERIC_LOW_RISK_PROFILES = {"read only"}


def run_access_tests(ctx, ids: IdGen) -> list[Finding]:
    findings: list[Finding] = []

    for (emp_key, system), records in ctx.employee_grants().items():
        if emp_key.startswith("UNMATCHED:"):
            continue  # orphan.py owns unmatched accounts
        emp = records[0].matched_employee
        if emp.status.strip().lower() == "terminated":
            continue

        active_records = [r for r in records if r.account_status.strip().lower() not in ACTIVE_STATES_EXCLUDED]
        if not active_records:
            continue

        profiles = sorted({p for r in active_records for p in r.profiles})
        evidence = [r.provenance.cite() for r in active_records]
        last_login = max((r.last_login for r in active_records if r.last_login), default=None)
        dormant = bool(last_login and (ctx.as_of - last_login).days > ctx.policy.dormant_threshold_days)

        # --- Segregation of duties ---
        conflict = ctx.policy.is_sod_conflict(system, profiles)
        conflicted = set(conflict) if conflict else set()
        if conflict:
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.SOD_VIOLATION_ACCESS,
                severity=Severity.HIGH,
                system=system,
                subject_person=emp.full_name,
                subject_email=emp.email,
                condition=f"{emp.full_name} ({emp.job_title}) holds both '{conflict[0]}' and '{conflict[1]}' "
                          f"in {system}, a conflicting profile pair.",
                criteria=f"{ctx.policy.sod_policy_reference}: '{conflict[0]}' and '{conflict[1]}' must not be "
                         f"held by the same user in {system}.",
                cause="Access was granted incrementally (e.g. covering for a colleague, temporary need) without "
                      "re-checking the resulting combination against the SoD matrix.",
                effect="A single individual can both create/initiate and approve the same class of transaction, "
                       "enabling undetected fraudulent or erroneous transactions.",
                recommendation=f"Remove one of the two conflicting profiles from {emp.full_name}'s {system} access; "
                               f"if both are genuinely required, document a compensating control (e.g. independent "
                               f"transaction-level review).",
                evidence=evidence,
                confidence=0.95,
            ))

        # --- Excess access / dormant: evaluated per ACCOUNT ROW, not the group.
        # Two separate accounts for the same person in the same system (e.g. a
        # normal login and a separate admin login) can have very different
        # usage patterns, and averaging them together would mask a dormant
        # privileged account behind a recently-used ordinary one.
        allowed = ctx.policy.allowed_profiles_for_role(system, emp.job_title)
        for rec in active_records:
            unusual = [
                p for p in rec.profiles
                if p not in conflicted and p.lower() not in GENERIC_LOW_RISK_PROFILES
                and not (allowed is not None and p in allowed)
            ]
            if not unusual:
                continue
            rec_dormant = bool(rec.last_login and (ctx.as_of - rec.last_login).days > ctx.policy.dormant_threshold_days)
            rec_evidence = [rec.provenance.cite()]

            if rec_dormant:
                findings.append(Finding(
                    finding_id=ids.next("FND"),
                    finding_type=FindingType.DORMANT_ACCOUNT_NOT_REVIEWED,
                    severity=Severity.MEDIUM,
                    system=system,
                    subject_person=emp.full_name,
                    subject_email=emp.email,
                    condition=f"{emp.full_name} holds {', '.join(unusual)} in {system} (account {rec.account_id}), "
                              f"outside the profiles expected for their role ({emp.job_title}), and this account "
                              f"has not been used since {rec.last_login.isoformat()} "
                              f"({(ctx.as_of - rec.last_login).days} days) despite being Active.",
                    criteria=f"{ctx.policy.policy_reference}: access must match the role-based access matrix, and "
                             f"unused entitlements must be identified and removed at periodic access review "
                             f"({ctx.policy.dormant_threshold_days}-day dormancy threshold).",
                    cause="Access appears to have been granted for a one-off task and not revoked afterward; no "
                          "periodic access review caught the unused entitlement.",
                    effect="Unused, unexplained privileged access widens the attack surface and is difficult to "
                           "justify to an auditor or regulator on demand.",
                    recommendation=f"Confirm with {emp.manager_email or 'the employee manager'} whether this "
                                   f"access is still required; if not, revoke it and document the review.",
                    evidence=rec_evidence,
                    confidence=0.85,
                ))
            else:
                findings.append(Finding(
                    finding_id=ids.next("FND"),
                    finding_type=FindingType.EXCESS_ACCESS_UNEXPECTED_ROLE,
                    severity=Severity.HIGH,
                    system=system,
                    subject_person=emp.full_name,
                    subject_email=emp.email,
                    condition=f"{emp.full_name} ({emp.job_title}, {emp.department}) holds {', '.join(unusual)} in "
                              f"{system} (account {rec.account_id}), not part of any role mapped to {emp.job_title} "
                              f"in the access matrix.",
                    criteria=f"{ctx.policy.policy_reference}: access must be limited to profiles mapped to the "
                             f"employee's role in the access matrix.",
                    cause="Access request appears to have bypassed role-based provisioning, or the employee changed "
                          "role/department without a corresponding access review.",
                    effect="Access inconsistent with job function increases the risk of unauthorized or unintended "
                           "transactions outside the employee's area of responsibility.",
                    recommendation=f"Validate business justification for this access with {emp.department} and "
                                   f"{system} owners; remove if not justified.",
                    evidence=rec_evidence,
                    confidence=0.85,
                ))

    return findings
