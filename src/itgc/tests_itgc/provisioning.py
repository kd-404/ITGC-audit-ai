"""ITGC tests on the provisioning/approval process itself, as evidenced by
service desk tickets and email correspondence:

  - PROVISIONING_SOD_SELF_APPROVED: requester and approver are the same person
  - APPROVAL_AFTER_IMPLEMENTATION: access was granted before it was approved
  - MISSING_APPROVAL_EVIDENCE: no ticket, and no email from someone in an
    approver-eligible role, exists for a given access grant - or, for a
    sensitive system, the only evidence is an email that explicitly skipped
    the required security approval.
"""
from __future__ import annotations

from ..models import Finding, FindingType, Severity
from .evidence_lookup import find_provisioning_ticket, find_related_emails, DEPROVISION_WORDS
from .idgen import IdGen
from ..ingest.fuzzy import normalize

ACTIVE_STATES_EXCLUDED = {"disabled", "inactive", "revoked", "closed", "terminated", "removed"}
GENERIC_LOW_RISK_PROFILES = {"read only"}
APPROVER_ROLE_HINTS = ["manager", "controller", "officer", "director", "head", "lead"]


def _display_person(ctx, email: str) -> str:
    """Resolve an email to the employee's full name for readability in a
    finding; falls back to the raw email if there's no employee match."""
    emp = ctx.employees_by_email.get((email or "").lower())
    return emp.full_name if emp else (email or "unknown")


def _is_approver_eligible(sender_email: str, ctx) -> bool:
    emp = ctx.employees_by_email.get((sender_email or "").lower())
    if not emp or not emp.job_title:
        return False
    title = emp.job_title.lower()
    return any(h in title for h in APPROVER_ROLE_HINTS)


def run_provisioning_tests(ctx, ids: IdGen) -> list[Finding]:
    findings: list[Finding] = []

    # --- ticket-level checks: self-approval, approval-after-implementation ---
    for t in ctx.bundle.tickets:
        is_deprovisioning = any(w in normalize(t.access_requested) for w in DEPROVISION_WORDS)
        if (t.requester_email and t.approver_email and t.requester_email == t.approver_email
                and not is_deprovisioning):
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.PROVISIONING_SOD_SELF_APPROVED,
                severity=Severity.CRITICAL,
                system=t.system,
                subject_person=_display_person(ctx, t.requester_email),
                subject_email=t.requester_email,
                condition=f"Ticket {t.ticket_id}: requester and approver are the same person "
                          f"({t.requester_email}) for '{t.access_requested}' in {t.system}.",
                criteria="Access provisioning requires an approval independent of the requester (four-eyes principle).",
                cause="The service desk workflow did not enforce requester/approver segregation for this ticket.",
                effect="Self-approved access requests bypass the entire approval control and can be used to "
                       "grant unauthorized or excessive access undetected.",
                recommendation="Reassign approval for this ticket to an independent approver, retroactively "
                               "review the access granted, and add a system control preventing requester/approver "
                               "self-match in the ticketing tool.",
                evidence=[t.provenance.cite()],
                confidence=1.0,
            ))

        if t.approved and t.implemented and t.implemented < t.approved:
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.APPROVAL_AFTER_IMPLEMENTATION,
                severity=Severity.MEDIUM,
                system=t.system,
                subject_person=_display_person(ctx, t.requester_email),
                subject_email=t.requester_email,
                condition=f"Ticket {t.ticket_id}: '{t.access_requested}' in {t.system} was implemented on "
                          f"{t.implemented.isoformat()}, before the approval recorded on {t.approved.isoformat()}.",
                criteria="Approval must be obtained and evidenced before access is implemented.",
                cause="IT/implementer actioned the request ahead of formal approval, possibly due to urgency "
                      "or informal verbal go-ahead.",
                effect="Access granted ahead of approval means the approval step is not a real control - it "
                       "becomes a rubber stamp on something already done.",
                recommendation="Reinforce with the implementation team that tickets must not be actioned before "
                               "the approval field is set; consider a system control blocking this sequence.",
                evidence=[t.provenance.cite()],
                confidence=0.95,
            ))

    # --- profile-level check: is there ANY valid approval evidence for this grant? ---
    for (emp_key, system), records in ctx.employee_grants().items():
        if emp_key.startswith("UNMATCHED:"):
            continue
        emp = records[0].matched_employee
        if emp.status.strip().lower() == "terminated":
            continue
        active_records = [r for r in records if r.account_status.strip().lower() not in ACTIVE_STATES_EXCLUDED]
        if not active_records:
            continue
        profiles = sorted({p for r in active_records for p in r.profiles})
        app_policy = ctx.policy.applications.get(system)
        sensitivity = app_policy.sensitivity if app_policy else "low"

        for profile in profiles:
            if profile.lower() in GENERIC_LOW_RISK_PROFILES:
                continue
            ticket = find_provisioning_ticket(ctx.bundle.tickets, emp.email, system, profile)
            if ticket:
                continue  # ticket evidence is sufficient regardless of sensitivity

            related_emails = [e for e in find_related_emails(ctx.bundle.emails, emp, system) if e.is_approval_like]
            valid_approval_email = next(
                (e for e in related_emails if _is_approver_eligible(e.sender, ctx) and not e.security_skipped),
                None,
            )
            if valid_approval_email and sensitivity != "high":
                continue  # documentary email evidence is adequate for a low-sensitivity system

            evidence = [r.provenance.cite() for r in active_records]
            if not related_emails:
                condition = (
                    f"{emp.full_name} holds '{profile}' in {system}, but no service-desk ticket or email "
                    f"exists anywhere in the evidence provided that authorizes this access."
                )
                cause = "No approval record was captured at all for this grant."
            elif sensitivity == "high" and not any(e.security_mentioned and not e.security_skipped for e in related_emails):
                skip_email = next((e for e in related_emails if e.security_skipped), related_emails[0])
                evidence.append(skip_email.provenance.cite())
                condition = (
                    f"{emp.full_name} holds '{profile}' in {system} (a high-sensitivity system), with no "
                    f"service-desk ticket. The only related evidence is an email ({skip_email.provenance.cite()}) "
                    f"from {skip_email.sender}" +
                    (" that explicitly states security review was not sought" if skip_email.security_skipped
                     else " with no indication that the required security approval was obtained") + "."
                )
                cause = ("Access to a sensitive system was authorized informally by email, bypassing both the "
                         "ticketing system and the required independent security approval.")
            else:
                approver_ok = valid_approval_email is not None
                evidence.append(related_emails[0].provenance.cite())
                condition = (
                    f"{emp.full_name} holds '{profile}' in {system}, with no service-desk ticket; the only "
                    f"evidence is an email from {related_emails[0].sender}"
                    + ("" if approver_ok else ", who does not hold an approver-eligible role") + "."
                )
                cause = "Access was authorized outside the standard ticketing/approval workflow."

            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.MISSING_APPROVAL_EVIDENCE,
                severity=Severity.HIGH,
                system=system,
                subject_person=emp.full_name,
                subject_email=emp.email,
                condition=condition,
                criteria=f"{ctx.policy.policy_reference}: access must be approved by an authorized approver"
                         + (", including independent security approval for high-sensitivity systems" if sensitivity == "high" else "")
                         + ", with the approval evidenced (ticket or equivalent documented record).",
                cause=cause,
                effect="Without evidenced, independent approval, access grants cannot be shown to be authorized, "
                       "and unauthorized or excessive access may go undetected.",
                recommendation="Obtain retroactive approval through the proper channel, and require all future "
                               "access changes to this system to go through the service desk with the required "
                               "approvals evidenced.",
                evidence=evidence,
                confidence=0.85,
            ))

    return findings
