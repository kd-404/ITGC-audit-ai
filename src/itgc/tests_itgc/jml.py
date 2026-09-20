"""ITGC test: Joiner-Mover-Leaver / user deprovisioning.

For every terminated employee, checks whether access in each system was
removed, and whether a deprovisioning record (service desk ticket) exists at
all. These are treated as two distinct questions:

  - is the access risk still live right now?           -> JML_TERMINATED_ACTIVE_ACCOUNT
  - is there evidence the control process even ran?     -> MISSING_DEPROVISIONING_RECORD

A ticket that exists but was never implemented answers "yes" to the second
question (there IS a record) while making the first finding more severe, not
a second, redundant finding.
"""
from __future__ import annotations

from datetime import date

from ..models import Finding, FindingType, Severity, Employee
from .evidence_lookup import find_deprovisioning_tickets
from .idgen import IdGen

DISABLED_STATES = {"disabled", "inactive", "revoked", "closed", "terminated", "removed"}


def run_jml(ctx, ids: IdGen) -> list[Finding]:
    findings: list[Finding] = []
    terminated = [e for e in ctx.bundle.employees if e.status.strip().lower() == "terminated" and e.term_date]

    for emp in terminated:
        by_system: dict[str, list] = {}
        for rec in ctx.current_access_records():
            if rec.matched_employee and rec.matched_employee.emp_id == emp.emp_id:
                by_system.setdefault(rec.system, []).append(rec)

        for system, records in by_system.items():
            active_records = [r for r in records if r.account_status.strip().lower() not in DISABLED_STATES]
            if not active_records:
                continue  # deprovisioned correctly - nothing to raise

            dep_tickets = find_deprovisioning_tickets(ctx.bundle.tickets, emp, system)
            implemented_ticket = next((t for t in dep_tickets if t.implemented), None)
            open_tickets = [t for t in dep_tickets if not t.implemented]

            days_since_term = (ctx.as_of - emp.term_date).days
            last_login = max((r.last_login for r in active_records if r.last_login), default=None)
            post_term_login = bool(last_login and last_login > emp.term_date)

            severity = Severity.HIGH
            if post_term_login or days_since_term > 60:
                severity = Severity.CRITICAL

            evidence = [r.provenance.cite() for r in active_records]
            if dep_tickets:
                evidence += [f"{t.provenance.cite()} (ticket {t.ticket_id})" for t in dep_tickets]

            if open_tickets and not implemented_ticket:
                t = open_tickets[0]
                condition = (
                    f"{emp.full_name} was terminated on {emp.term_date.isoformat()}, but {system} account "
                    f"({', '.join(r.account_id for r in active_records)}) remains Active "
                    f"{days_since_term} days later. Deprovisioning ticket {t.ticket_id} was raised on "
                    f"{t.created.isoformat() if t.created else 'an unknown date'} but has never been implemented "
                    f"(status: {t.status})."
                )
                cause = "Deprovisioning ticket raised but not actioned by IT within the required SLA."
            elif dep_tickets:
                condition = (
                    f"{emp.full_name} was terminated on {emp.term_date.isoformat()}, but {system} account "
                    f"remains Active {days_since_term} days later despite deprovisioning ticket(s) "
                    f"{', '.join(t.ticket_id for t in dep_tickets)} existing."
                )
                cause = "Deprovisioning was logged but access removal was not confirmed/completed."
            else:
                condition = (
                    f"{emp.full_name} was terminated on {emp.term_date.isoformat()}, but {system} account "
                    f"remains Active {days_since_term} days later, and no deprovisioning ticket exists in the "
                    f"service desk for this termination."
                )
                cause = "No deprovisioning request was ever raised - the termination did not trigger the access-removal process."

            if post_term_login:
                condition += f" Last login on record ({last_login.isoformat()}) is AFTER the termination date, indicating the account was used post-termination."

            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.JML_TERMINATED_ACTIVE_ACCOUNT,
                severity=severity,
                system=system,
                subject_person=emp.full_name,
                subject_email=emp.email,
                condition=condition,
                criteria=f"{ctx.policy.policy_reference}: access must be disabled within "
                         f"{ctx.policy.deprovisioning_sla_days} day(s) of termination.",
                cause=cause,
                effect="Unauthorized access to a terminated employee's account risks data exposure, "
                       "credential misuse, and unauthorized transactions attributable to a former employee.",
                recommendation=f"Disable the {system} account immediately, investigate all post-termination "
                               f"activity on it, and confirm no dependent processes are broken by removal.",
                evidence=evidence,
                confidence=0.95,
            ))

            if not dep_tickets:
                findings.append(Finding(
                    finding_id=ids.next("FND"),
                    finding_type=FindingType.MISSING_DEPROVISIONING_RECORD,
                    severity=Severity.HIGH,
                    system=system,
                    subject_person=emp.full_name,
                    subject_email=emp.email,
                    condition=f"No service-desk ticket or other evidence of a deprovisioning request exists for "
                              f"{emp.full_name}'s termination in {system}.",
                    criteria=f"{ctx.policy.policy_reference}: every termination must generate a documented "
                             f"deprovisioning request routed to IT.",
                    cause="The termination-to-deprovisioning handoff between HR and IT/Service Desk did not occur, "
                          "or was not logged.",
                    effect="Without a record, this control cannot be evidenced to an auditor even if access is "
                           "later removed, and there is no trigger to ensure it happens at all.",
                    recommendation="Implement an automated trigger from the HR termination event to a mandatory "
                                   "service desk deprovisioning ticket for every in-scope application.",
                    evidence=[e.provenance.cite() for e in [emp]],
                    confidence=0.9,
                ))

    return findings
