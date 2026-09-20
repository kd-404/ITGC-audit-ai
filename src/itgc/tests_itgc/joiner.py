"""ITGC test: joiner provisioning timeliness (the other half of the
Joiner/Mover/Leaver lifecycle - jml.py owns the leaver/deprovisioning side).

For each active employee, find the earliest ticket that provisioned their
FIRST access in each system they currently hold, and check it happened
within the policy's SLA of their hire date. Pre-boarding (access set up
before day one) is fine and common - only a grant confirmed AFTER hire date
plus the SLA window is flagged. An employee with active access but no
ticket at all is not this test's problem: provisioning.py's
MISSING_APPROVAL_EVIDENCE already owns "no evidence this was ever approved,"
and flagging it twice under two finding types would just be noise.
"""
from __future__ import annotations

from ..models import Finding, FindingType, Severity
from .idgen import IdGen

ACTIVE_STATES_EXCLUDED = {"disabled", "inactive", "revoked", "closed", "terminated", "removed"}

# A ticket completed years after hire is almost certainly a later, unrelated
# access change (a role change, a one-off need) rather than delayed
# onboarding - attributing it to "joiner delay" would be a false positive,
# not a stricter finding. Cap how far past hire we'll still call this the
# joiner event.
MAX_PLAUSIBLE_JOINER_GAP_DAYS = 180


def run_joiner_provisioning(ctx, ids: IdGen) -> list[Finding]:
    findings: list[Finding] = []

    for (emp_key, system), records in ctx.employee_grants().items():
        if emp_key.startswith("UNMATCHED:"):
            continue
        emp = records[0].matched_employee
        if emp.status.strip().lower() == "terminated" or not emp.hire_date:
            continue
        active_records = [r for r in records if r.account_status.strip().lower() not in ACTIVE_STATES_EXCLUDED]
        if not active_records:
            continue

        # the earliest ticket where this employee requested access in this system
        candidate_tickets = [
            t for t in ctx.bundle.tickets
            if t.requester_email.lower() == (emp.email or "").lower() and t.system.lower() == system.lower()
        ]
        if not candidate_tickets:
            continue  # no evidence either way - provisioning.py's missing-evidence check owns this gap
        first_ticket = min(candidate_tickets, key=lambda t: t.created or t.implemented or ctx.as_of)

        completed = first_ticket.implemented or first_ticket.approved
        if not completed:
            continue  # still open - not this test's concern either

        gap_days = (completed - emp.hire_date).days
        if gap_days <= ctx.policy.joiner_provisioning_sla_days:
            continue  # on time (including provisioned before day one, which is negative/zero gap)
        if gap_days > MAX_PLAUSIBLE_JOINER_GAP_DAYS:
            continue  # too far past hire to plausibly BE the onboarding grant - likely an unrelated later ticket

        findings.append(Finding(
            finding_id=ids.next("FND"),
            finding_type=FindingType.JOINER_PROVISIONING_DELAY,
            severity=Severity.LOW if gap_days <= ctx.policy.joiner_provisioning_sla_days * 2 else Severity.MEDIUM,
            system=system,
            subject_person=emp.full_name,
            subject_email=emp.email,
            condition=f"{emp.full_name} joined on {emp.hire_date.isoformat()}, but access in {system} "
                      f"(ticket {first_ticket.ticket_id}) wasn't completed until {completed.isoformat()} - "
                      f"{gap_days} days later, against a {ctx.policy.joiner_provisioning_sla_days}-day target.",
            criteria=f"{ctx.policy.policy_reference}: new-hire access should be provisioned within "
                     f"{ctx.policy.joiner_provisioning_sla_days} day(s) of the start date.",
            cause="Onboarding and access-provisioning workflows are not synchronized to the hire date.",
            effect="A new hire without timely access is a productivity/business risk, and a late-arriving "
                   "grant is harder to trace back to a specific onboarding decision during a later review.",
            recommendation="Trigger the access request automatically from the HR onboarding event rather than "
                           "waiting for a manual follow-up request.",
            evidence=[first_ticket.provenance.cite()] + [r.provenance.cite() for r in active_records],
            confidence=0.8,
        ))

    return findings
