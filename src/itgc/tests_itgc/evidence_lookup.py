"""Shared helpers for finding the ticket/email that corroborates (or fails to
corroborate) a given access grant or termination. Used by every ITGC test so
"how do we look for evidence" stays in one place.
"""
from __future__ import annotations

from ..models import Employee, Ticket, EmailEvidence
from ..ingest.fuzzy import name_key, normalize

DEPROVISION_WORDS = ["disable", "deprovision", "revoke", "terminate account", "remove access"]


def find_deprovisioning_tickets(tickets: list[Ticket], employee: Employee, system: str) -> list[Ticket]:
    emp_key = name_key(employee.full_name)
    out = []
    for t in tickets:
        text = normalize(t.access_requested)
        if not any(w in text for w in DEPROVISION_WORDS):
            continue
        if emp_key not in normalize(t.access_requested):
            continue
        if system and t.system and t.system.lower() != system.lower():
            continue
        out.append(t)
    return out


def find_provisioning_ticket(tickets: list[Ticket], employee_email: str, system: str, profile: str) -> Ticket | None:
    profile_n = normalize(profile)
    for t in tickets:
        if t.requester_email.lower() != (employee_email or "").lower():
            continue
        if t.system.lower() != system.lower():
            continue
        req_n = normalize(t.access_requested)
        # accept exact/substring match either way (short profile names, no need for fuzzy ratio)
        if profile_n in req_n or req_n in profile_n:
            return t
    return None


def find_related_emails(emails: list[EmailEvidence], employee: Employee, system: str | None = None) -> list[EmailEvidence]:
    emp_key = name_key(employee.full_name)
    emp_email = (employee.email or "").lower()
    out = []
    for e in emails:
        haystack = normalize(f"{e.subject} {e.body}")
        mentioned = emp_key in haystack or emp_email in f"{e.sender} {e.recipient} {e.body}".lower()
        if not mentioned:
            continue
        if system and e.mentions_systems and system not in e.mentions_systems:
            continue
        out.append(e)
    return out
