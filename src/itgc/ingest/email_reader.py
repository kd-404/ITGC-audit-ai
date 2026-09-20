"""Parses plain-text/.eml-style emails into EmailEvidence, and pulls out
lightweight signals (approval language, system names, whether security was
mentioned) that the correlation and enquiry layers use later.

This is intentionally a simple header parser, not a MIME parser - client
evidence handed over as "email screenshots turned into text" or exports from
a mail client rarely comes as clean MIME anyway, and the fields we need
(from/to/subject/date/body) are the same either way.
"""
from __future__ import annotations

import re
from pathlib import Path

from dateutil import parser as dateparser

from ..models import EmailEvidence, Provenance

APPROVAL_WORDS = ["approve", "approved", "go ahead", "authorized", "sign off", "ok to", "granted", "grant"]
SECURITY_WORDS = ["security", "infosec", "security officer", "security approval", "security review"]
SECURITY_SKIP_PATTERNS = [
    r"no need to (loop in|involve|include) security",
    r"skip(ping)? security",
    r"without security",
    r"security.{0,15}not (needed|required)",
]
SYSTEM_HINTS = ["FinERP", "Payroll", "CRM", "ITSM"]


def parse_email_file(path: Path) -> EmailEvidence:
    path = Path(path)
    text = path.read_text(errors="ignore")
    headers = {}
    body_lines = []
    in_body = False
    for line in text.splitlines():
        if not in_body:
            m = re.match(r"^([A-Za-z-]+):\s*(.*)$", line)
            if m and m.group(1).lower() in ("from", "to", "subject", "date", "cc"):
                headers[m.group(1).lower()] = m.group(2).strip()
                continue
            if line.strip() == "":
                in_body = True
                continue
        in_body = True
        body_lines.append(line)
    body = "\n".join(body_lines).strip()

    sent_date = None
    if headers.get("date"):
        try:
            sent_date = dateparser.parse(headers["date"], fuzzy=True).date()
        except (ValueError, OverflowError):
            sent_date = None

    full_text = f"{headers.get('subject', '')}\n{body}".lower()
    is_approval = any(w in full_text for w in APPROVAL_WORDS)
    security_mentioned = any(w in full_text for w in SECURITY_WORDS)
    security_skipped = any(re.search(p, full_text) for p in SECURITY_SKIP_PATTERNS)
    systems = [s for s in SYSTEM_HINTS if s.lower() in full_text]

    # crude person-mention extraction: capitalized two-word sequences in body/subject
    people = sorted(set(re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)\b", f"{headers.get('subject','')} {body}")))

    return EmailEvidence(
        sender=headers.get("from", "").strip(),
        recipient=headers.get("to", "").strip(),
        subject=headers.get("subject", "").strip(),
        sent_date=sent_date,
        body=body,
        provenance=Provenance(source_file=path.name, source_type="email", location="email body",
                               raw={"headers": headers}),
        mentions_systems=systems,
        mentions_people=list(people),
        is_approval_like=is_approval,
        security_mentioned=security_mentioned,
        security_skipped=security_skipped,
    )
