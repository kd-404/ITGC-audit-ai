"""Evidence mapping: the auditor's actual first task before any control test
runs — segregate the evidence pile by who/what it's about, put it in time
order, and see how each piece relates to the others.

This module builds one "case" per person (or per unmatched account, when
identity resolution couldn't tie it to anyone) containing every fact we have
about them, in chronological order, regardless of which file or medium it
came from. Findings and enquiries that mention that person are attached so
the case reads as a complete story: what happened, when, from where, and
what's still unresolved.

Deliberately independent of the ITGC test rules in tests_itgc/ - this builds
the same view a human auditor would sketch on paper before applying any
control, and is useful even for evidence that trips no rule at all.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import re


@dataclass
class TimelineEvent:
    event_date: date | None
    date_label: str          # always human-readable, "date unknown" when event_date is None
    kind: str                # employee | access | ticket | email
    title: str
    detail: str
    citation: str
    sort_key: tuple          # used for stable ordering, including undated events


@dataclass
class EvidenceCase:
    case_id: str
    subject_label: str
    subject_email: str | None
    resolved: bool            # False = an account/person evidence never tied to the employee master
    events: list[TimelineEvent] = field(default_factory=list)
    related_finding_ids: list[str] = field(default_factory=list)
    related_enquiry_ids: list[str] = field(default_factory=list)

    def sorted_events(self) -> list[TimelineEvent]:
        return sorted(self.events, key=lambda e: e.sort_key)


UNDATED_EPOCH = date(1900, 1, 1)  # undated events sort first, grouped, rather than scattered


def _case_key_for_email(email: str | None) -> str:
    return f"EMAIL_ADDR:{(email or '').lower()}"


def _mentioned_employees(text: str, employees: list) -> list[tuple[object, bool]]:
    """Find employees named in free text, against the ACTUAL employee list -
    not a blind capitalized-word regex. Returns (employee, ambiguous) pairs:
    a full-name match is unambiguous; a bare first-name match is flagged
    ambiguous whenever more than one employee shares that first name, so the
    evidence map never silently picks the wrong person out of two "Rahul"s.
    """
    if not text:
        return []
    found: dict[str, tuple[object, bool]] = {}

    # unambiguous: full name appears verbatim (case-insensitive, word-boundary)
    for emp in employees:
        if not emp.full_name:
            continue
        pattern = r"\b" + re.escape(emp.full_name) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            found[emp.emp_id] = (emp, False)

    # first-name-only mentions, for anyone not already matched by full name
    first_name_groups: dict[str, list] = {}
    for emp in employees:
        if not emp.full_name:
            continue
        first = emp.full_name.split()[0]
        first_name_groups.setdefault(first.lower(), []).append(emp)

    for first_lower, group in first_name_groups.items():
        pattern = r"\b" + re.escape(first_lower) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            ambiguous = len(group) > 1
            for emp in group:
                if emp.emp_id not in found:
                    found[emp.emp_id] = (emp, ambiguous)

    return list(found.values())


def build_evidence_map(ctx, findings: list, enquiries: list) -> list[EvidenceCase]:
    cases: dict[str, EvidenceCase] = {}

    def get_or_create(key: str, label: str, email: str | None, resolved: bool) -> EvidenceCase:
        if key not in cases:
            cases[key] = EvidenceCase(case_id=key, subject_label=label, subject_email=email, resolved=resolved)
        return cases[key]

    # --- every employee with any hire/term date becomes a case anchor ---
    for emp in ctx.bundle.employees:
        key = f"EMP:{emp.emp_id}"
        case = get_or_create(key, emp.full_name, emp.email, True)
        if emp.hire_date:
            case.events.append(TimelineEvent(
                event_date=emp.hire_date, date_label=emp.hire_date.isoformat(), kind="employee",
                title=f"Joined as {emp.job_title or 'unknown role'} ({emp.department or 'unknown dept'})",
                detail=f"Status on file: {emp.status}", citation=emp.provenance.cite(),
                sort_key=(emp.hire_date, 0),
            ))
        if emp.term_date:
            case.events.append(TimelineEvent(
                event_date=emp.term_date, date_label=emp.term_date.isoformat(), kind="employee",
                title="Terminated", detail="Employment ended per HR record.",
                citation=emp.provenance.cite(), sort_key=(emp.term_date, 0),
            ))
        if not emp.hire_date and not emp.term_date:
            case.events.append(TimelineEvent(
                event_date=None, date_label="date unknown", kind="employee",
                title=f"Employee record ({emp.job_title or 'unknown role'}, {emp.department or 'unknown dept'})",
                detail=f"Status on file: {emp.status}", citation=emp.provenance.cite(),
                sort_key=(UNDATED_EPOCH, 0),
            ))

    # --- access records ---
    for rec in ctx.bundle.access_records:
        if rec.matched_employee:
            key = f"EMP:{rec.matched_employee.emp_id}"
            case = get_or_create(key, rec.matched_employee.full_name, rec.matched_employee.email, True)
        else:
            key = f"ACCOUNT:{rec.account_id}"
            case = get_or_create(key, f"{rec.account_name} (unresolved account)", rec.account_email, False)
        d = rec.last_login
        case.events.append(TimelineEvent(
            event_date=d, date_label=(d.isoformat() + " (last login)") if d else "date unknown (never logged in / not recorded)",
            kind="access",
            title=f"{rec.system}: holds {', '.join(rec.profiles) or 'no profile listed'} ({rec.account_status})",
            detail=f"Account {rec.account_id}" + (f", matched via {rec.match_method} ({rec.match_confidence:.0%})" if rec.matched_employee else ", NOT matched to any employee record"),
            citation=rec.provenance.cite(),
            sort_key=(d or UNDATED_EPOCH, 1),
        ))

    # --- tickets: resolve requester to a case, add one event per meaningful date ---
    for t in ctx.bundle.tickets:
        emp = ctx.employees_by_email.get((t.requester_email or "").lower())
        if emp:
            key, label, email, resolved = f"EMP:{emp.emp_id}", emp.full_name, emp.email, True
        else:
            key, label, email, resolved = _case_key_for_email(t.requester_email), t.requester_email or "unknown requester", t.requester_email, False
        case = get_or_create(key, label, email, resolved)

        stages = [
            (t.created, "raised", f"Ticket {t.ticket_id} raised: '{t.access_requested}' in {t.system}"),
            (t.approved, "approved", f"Ticket {t.ticket_id} approved by {t.approver_email or 'unknown'}"),
            (t.implemented, "implemented", f"Ticket {t.ticket_id} implemented by {t.implementer_email or 'unknown'}"),
        ]
        for d, stage, title in stages:
            if d is None and stage != "raised":
                continue  # don't fabricate an "implemented" event for a ticket never implemented
            case.events.append(TimelineEvent(
                event_date=d, date_label=d.isoformat() if d else "date unknown",
                kind="ticket", title=title, detail=f"Status: {t.status}",
                citation=t.provenance.cite(), sort_key=(d or UNDATED_EPOCH, 2),
            ))

    # --- emails: resolve sender AND every mentioned person; unresolved go under sender's email address ---
    for e in ctx.bundle.emails:
        targets: list[tuple] = []
        sender_emp = ctx.employees_by_email.get((e.sender or "").split("<")[-1].strip(">").lower())
        if sender_emp:
            targets.append((f"EMP:{sender_emp.emp_id}", sender_emp.full_name, sender_emp.email, True, False))
        else:
            targets.append((_case_key_for_email(e.sender), e.sender or "unknown sender", e.sender, False, False))

        mention_text = f"{e.subject}\n{e.body}"
        mentioned = _mentioned_employees(mention_text, ctx.bundle.employees)
        for emp, ambiguous in mentioned:
            t = (f"EMP:{emp.emp_id}", emp.full_name, emp.email, True, ambiguous)
            if not any(t[:4] == existing[:4] for existing in targets):
                targets.append(t)

        title = f"Email: \"{e.subject}\""
        flags = []
        if e.is_approval_like:
            flags.append("approval-like")
        if e.security_mentioned:
            flags.append("mentions security")
        if e.security_skipped:
            flags.append("EXPLICITLY SKIPS security review")
        base_detail = f"From {e.sender} to {e.recipient}." + (f" [{', '.join(flags)}]" if flags else "")

        for target in targets:
            key, label, email, resolved = target[:4]
            ambiguous = target[4] if len(target) > 4 else False
            case = get_or_create(key, label, email, resolved)
            detail = base_detail
            if ambiguous:
                detail += (" ⚠ Name mentioned is a first name shared by more than one employee - "
                           "this attribution is a guess, not a confirmed match. Needs an enquiry to confirm who is meant.")
            case.events.append(TimelineEvent(
                event_date=e.sent_date, date_label=e.sent_date.isoformat() if e.sent_date else "date unknown",
                kind="email", title=title, detail=detail, citation=e.provenance.cite(),
                sort_key=(e.sent_date or UNDATED_EPOCH, 3),
            ))

    # --- attach findings and enquiries to whichever case(s) they mention ---
    for f in findings:
        subj = (f.subject_email or "").lower()
        for case in cases.values():
            if subj and case.subject_email and case.subject_email.lower() == subj:
                case.related_finding_ids.append(f.finding_id)
            elif f.subject_person and case.subject_label and f.subject_person.lower() in case.subject_label.lower():
                if f.finding_id not in case.related_finding_ids:
                    case.related_finding_ids.append(f.finding_id)

    for enq in enquiries:
        haystack = f"{enq.question} {enq.context}".lower()
        for case in cases.values():
            if case.subject_email and case.subject_email.lower() in haystack:
                enq_ids = case.related_enquiry_ids
                if enq.enquiry_id not in enq_ids:
                    enq_ids.append(enq.enquiry_id)
            elif case.subject_label.split(" (")[0].lower() in haystack:
                if enq.enquiry_id not in case.related_enquiry_ids:
                    case.related_enquiry_ids.append(enq.enquiry_id)

    # cases with the most going on (findings, then enquiries, then event count) lead the list
    ordered = sorted(
        cases.values(),
        key=lambda c: (-len(c.related_finding_ids), -len(c.related_enquiry_ids), -len(c.events), c.subject_label),
    )
    return ordered


def evidence_map_to_json(cases: list[EvidenceCase]) -> list[dict]:
    out = []
    for c in cases:
        out.append({
            "case_id": c.case_id,
            "subject_label": c.subject_label,
            "subject_email": c.subject_email,
            "resolved": c.resolved,
            "related_finding_ids": c.related_finding_ids,
            "related_enquiry_ids": c.related_enquiry_ids,
            "events": [
                {
                    "date_label": ev.date_label, "kind": ev.kind, "title": ev.title,
                    "detail": ev.detail, "citation": ev.citation,
                }
                for ev in c.sorted_events()
            ],
        })
    return out
