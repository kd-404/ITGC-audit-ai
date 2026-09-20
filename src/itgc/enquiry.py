"""The enquiry loop: things the pipeline could not resolve on its own and
needs a human auditor to answer, rather than silently guessing or dropping
evidence. These are surfaced up front, before/alongside the findings, and are
answerable via data/answers.yaml (see enquiry.apply_answers) so a re-run can
pick them up without re-asking.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .models import Enquiry
from .identity.resolve import MIN_CONFIDENCE, FUZZY_NAME_THRESHOLD
from .tests_itgc.idgen import IdGen


def build_enquiries(ctx, ids: IdGen) -> list[Enquiry]:
    enquiries: list[Enquiry] = []

    for f in ctx.bundle.unclassified_files:
        if f.endswith((".yaml", ".yml")):
            continue  # company policy config, not evidence - expected to be unclassified
        enquiries.append(Enquiry(
            enquiry_id=ids.next("ENQ"),
            topic="Unrecognized evidence file",
            question=f"'{f}' doesn't match any known evidence format (employee master, UAR export, service desk "
                     f"export, or email). What is this file, and which system/process does it relate to?",
            context="Ingestion could not confidently map this file's columns to a known schema.",
            blocking=False,
        ))

    for rec in ctx.bundle.access_records:
        if rec.matched_employee is None:
            continue
        if MIN_CONFIDENCE <= rec.match_confidence < FUZZY_NAME_THRESHOLD:
            enquiries.append(Enquiry(
                enquiry_id=ids.next("ENQ"),
                topic="Ambiguous identity match",
                question=f"Account {rec.account_id} ('{rec.account_name}', {rec.account_email}) in {rec.system} "
                         f"was matched to employee {rec.matched_employee.full_name} "
                         f"({rec.matched_employee.email}) with only {rec.match_confidence:.0%} confidence "
                         f"(method: {rec.match_method}). Please confirm this is the correct person.",
                context=rec.provenance.cite(),
                blocking=True,
            ))

    for rec in ctx.bundle.access_records:
        if rec.matched_employee is not None:
            continue
        if rec.account_status.strip().lower() in {"disabled", "inactive", "revoked", "closed"}:
            continue
        enquiries.append(Enquiry(
            enquiry_id=ids.next("ENQ"),
            topic="Unidentified account owner",
            question=f"Account {rec.account_id} ('{rec.account_name}', {rec.account_email or 'no email'}) in "
                     f"{rec.system} does not match any employee record. Is this a contractor, a shared/service "
                     f"account, or an employee missing from the HR extract provided?",
            context=rec.provenance.cite(),
            blocking=False,  # a finding (ORPHAN_ACCOUNT) is raised regardless; this just seeks disposition
        ))

    return enquiries


def load_answers(path: Path) -> dict[str, str]:
    path = Path(path)
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return data.get("answers", {})


def apply_answers(enquiries: list[Enquiry], answers: dict[str, str]) -> None:
    for e in enquiries:
        if e.enquiry_id in answers:
            e.answer = answers[e.enquiry_id]
