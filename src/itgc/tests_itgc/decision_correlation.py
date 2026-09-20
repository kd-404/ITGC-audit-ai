"""ITGC test: does the actual access state match documented human decisions?

This automates the reasoning the two "hard" test scenarios
(data/test_scenarios/meridian_uar_hard, .../solstice_jml_sod_hard) were
built to exercise by hand: read every email that expresses a retain/revoke
decision about a specific person's access, work out who it's actually
about, work out which instruction governs when the same person is
mentioned more than once (the latest dated one wins), and check whether the
real access state agrees with it.

Everything here is deterministic pattern-matching, date comparison and
org-chart lookup - no LLM call is involved in reaching a verdict, per the
project's own principle that the LLM explains findings, it does not decide
them. That is a real scope limit, not an oversight: a sentence has to
actually name the person (by full name, first name/common nickname prefix,
email, or employee ID) and use a recognizable retain/revoke phrase for this
to fire. A reference by ID-only or an unnamed "that contractor" IS handled
(ID lookups are tier 2 below); a reference with literally no name or ID
token at all (Solstice's "the new starter", Meridian's original "please
ask rather than guess" instruction) is not, and rightly stays a manual/
enquiry item - guessing there would be worse than staying silent.

Ambiguous references - a name that could equally mean more than one person,
and isn't resolved by the sender's own reporting line - are never guessed.
They become an Enquiry, the same standard the rest of the enquiry layer
already applies to low-confidence identity matches.

Three finding types come out of this:
  ACCESS_DECISION_NOT_ACTIONED   - a revoke instruction exists; still Active.
  ACCESS_DECISION_CONTRADICTED   - the LATEST instruction says retain; the
                                    account has been revoked/disabled anyway
                                    (usually because a superseded, earlier
                                    instruction was actioned instead).
  OUT_OF_AUTHORITY_INSTRUCTION   - whoever gave the governing instruction is
                                    not the subject's manager of record, and
                                    no corroborating instruction from the
                                    actual manager exists in evidence. This
                                    is a "needs corroboration" signal, not
                                    proof the instruction was wrong.

Known, deliberate simplification: when a sentence contains hits from more
than one matching tier at once (e.g. an ID and a first name in the same
sentence, referring to two different people), only the single
highest-priority tier that fired is used for that whole sentence. Every
sentence in both hard test scenarios stays within one tier, so this hasn't
been a problem in practice, but it's a real limit worth knowing about
before trusting this against a third company's evidence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from ..models import Finding, FindingType, Severity, Enquiry
from .idgen import IdGen
from ..ingest.fuzzy import name_key, normalize

ACTIVE_STATES_EXCLUDED = {"disabled", "inactive", "revoked", "closed", "terminated", "removed"}

REVOKE_PHRASES = [
    "revoke", "remove access", "remove her access", "remove his access",
    "remove their access", "disable her account", "disable his account",
    "disable this account", "disable that account", "no longer need",
    "doesn't need", "does not need", "should be removed", "removed too",
    "access should be removed", "please revoke",
]
RETAIN_PHRASES = [
    "still need", "still needs", "needs to keep", "need to keep",
    "should keep", "keep his access", "keep her access", "keep their access",
    "keeps his access", "keeps her access", "both keep", "keep our access",
    "no change there",
]

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_GREETING_RE = re.compile(r"^\s*(hi|hello|hey|dear)\b[^,]{0,40},?\s*$", re.IGNORECASE)
# A bare "Name," opener with no "Hi"/"Hello" (e.g. just "Neha,") - only
# treated as a greeting when it is the very first content line, so a
# legitimate one-word line later in the body isn't stripped by mistake.
_BARE_NAME_GREETING_RE = re.compile(r"^\s*[A-Z][A-Za-z'\-]{1,20},\s*$")
_SIGNOFF_RE = re.compile(r"^\s*(thanks|thank you|regards|best|best regards|cheers|sincerely|kind regards)\b.*$",
                          re.IGNORECASE)


def _extract_email(raw: str) -> str:
    if not raw:
        return ""
    m = _EMAIL_RE.search(raw)
    return m.group(0).lower() if m else raw.strip().lower()


def _clean_email_body(body: str) -> str:
    """Strips quoted history ("> ..." lines) and the greeting/sign-off
    lines that bracket the actual message. Left in, these reliably corrupt
    sentence-level attribution: a quoted "On <date>, X wrote: ..." line
    re-injects X's name next to whatever the quoted text says, and "Hi
    <name>," / "Thanks, <name>" lines put a real employee's name next to
    unrelated action words purely because a sentence boundary (a period)
    doesn't happen to fall between the greeting and the first real
    sentence. Confirmed necessary by testing against the Meridian dataset,
    which otherwise produced a false "revoke Deepa Nair" and a false
    "revoke Neha Kapoor" purely from greeting/quoting artifacts."""
    lines = []
    seen_content = False
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            continue
        if _GREETING_RE.match(stripped):
            continue
        if not seen_content and _BARE_NAME_GREETING_RE.match(stripped):
            continue
        seen_content = True
        lines.append(line)
    kept = []
    for line in lines:
        if _SIGNOFF_RE.match(line.strip()):
            break  # everything from the sign-off onward is a closing/signature block
        kept.append(line)
    return "\n".join(kept)


def _split_sentences(text: str) -> list[str]:
    text = text.replace("\n", " ")
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _classify_action(sentence_n: str) -> str | None:
    has_revoke = any(p in sentence_n for p in REVOKE_PHRASES)
    has_retain = any(p in sentence_n for p in RETAIN_PHRASES)
    if has_retain and not has_revoke:
        return "retain"
    if has_revoke and not has_retain:
        return "revoke"
    return None  # neither, or both at once - too ambiguous to guess


def _disambiguate_by_authority(candidates: list, sender_email: str):
    if not sender_email:
        return None
    matches = [c for c in candidates if (c.manager_email or "").lower() == sender_email.lower()]
    return matches[0] if len(matches) == 1 else None


def _resolve_sentence_subjects(ctx, sentence: str, sender_email: str) -> list[tuple]:
    """Returns [(employee, None)] for each resolved subject, or
    [(None, [candidate, candidate, ...])] for an unresolved ambiguous one.
    Only the single highest-priority tier that produced any hit is used."""
    results: list[tuple] = []

    # tier 1: exact email address mentions
    emails_found = {m.group(0).lower() for m in _EMAIL_RE.finditer(sentence)}
    tier1 = [ctx.employees_by_email[e] for e in emails_found if e in ctx.employees_by_email]
    if tier1:
        return [(emp, None) for emp in tier1]

    # tier 2: exact employee-ID token mentions (IDs are unique by construction)
    tier2 = [
        emp for emp in ctx.bundle.employees
        if emp.emp_id and re.search(r"\b" + re.escape(emp.emp_id) + r"\b", sentence, re.IGNORECASE)
    ]
    if tier2:
        return [(emp, None) for emp in tier2]

    # tier 3: exact full-name mentions - ctx.employees_by_namekey already
    # groups genuine same-name collisions (e.g. two "James Walsh"s) together.
    seen_keys: set[str] = set()
    tier3_hit = False
    for emp in ctx.bundle.employees:
        key = name_key(emp.full_name)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        if re.search(r"\b" + re.escape(emp.full_name) + r"\b", sentence, re.IGNORECASE):
            tier3_hit = True
            candidates = ctx.employees_by_namekey.get(key) or [emp]
            if len(candidates) == 1:
                results.append((candidates[0], None))
            else:
                resolved = _disambiguate_by_authority(candidates, sender_email)
                results.append((resolved, None) if resolved else (None, candidates))
    if tier3_hit:
        return results

    # tier 4: first-name, or a >=4-char nickname prefix of a first name
    # (e.g. "Meena" for "Meenakshi") - the common shape of an informal
    # reference that skips the surname entirely.
    first_name_groups: dict[str, list] = {}
    for emp in ctx.bundle.employees:
        if not emp.full_name:
            continue
        first_name_groups.setdefault(emp.full_name.split()[0].lower(), []).append(emp)

    sentence_l = sentence.lower()
    words = set(re.findall(r"[a-z]+", sentence_l))
    matched_groups: dict[str, list] = {}
    for word in words:
        if word in first_name_groups and re.search(r"\b" + re.escape(word) + r"\b", sentence_l):
            matched_groups.setdefault(word, [])
            matched_groups[word] = list({e.emp_id: e for e in matched_groups[word] + first_name_groups[word]}.values())
        if len(word) >= 4:
            for first, group in first_name_groups.items():
                if first != word and first.startswith(word):
                    matched_groups.setdefault(word, [])
                    matched_groups[word] = list({e.emp_id: e for e in matched_groups[word] + group}.values())

    for word, group in matched_groups.items():
        if not group:
            continue
        if len(group) == 1:
            results.append((group[0], None))
        else:
            resolved = _disambiguate_by_authority(group, sender_email)
            results.append((resolved, None) if resolved else (None, group))

    return results


_RECENT_HINTS = ("after", "post", "revised", "updated", "final", "current")
_STALE_HINTS = ("before", "pre", "initial", "original", "draft", "prior")


def _is_currently_active(records: list) -> bool:
    """Best-effort read of 'what does access look like right now' when more
    than one snapshot of the same system's access exists for this person -
    e.g. a client hands over a before-remediation AND an after-remediation
    export, exactly as the Meridian scenario does. Naively merging every
    record for (employee, system) and checking whether ANY of them is
    'active' would make a correctly-revoked account look untouched, because
    the older, since-superseded snapshot is still sitting in the same
    group. This prefers whichever snapshot's filename signals it is the
    more recent one, falls back to the latest last_login when the naming
    gives no signal, and - when genuinely tied - stays conservative and
    reports active rather than silently assuming a revocation happened."""
    if not records:
        return False
    statuses = {r.account_status.strip().lower() for r in records}
    if len(statuses) == 1:
        return next(iter(statuses)) not in ACTIVE_STATES_EXCLUDED

    def fname(r):
        return (r.provenance.source_file or "").lower()

    recent = [r for r in records if any(h in fname(r) for h in _RECENT_HINTS)]
    stale = [r for r in records if any(h in fname(r) for h in _STALE_HINTS)]
    if recent and len(recent) < len(records) and not (set(id(r) for r in recent) & set(id(r) for r in stale)):
        pool = recent
    else:
        max_login = max((r.last_login for r in records if r.last_login), default=None)
        pool = [r for r in records if r.last_login == max_login] if max_login else records
    return any(r.account_status.strip().lower() not in ACTIVE_STATES_EXCLUDED for r in pool)


@dataclass
class _Decision:
    subject: object
    action: str
    when: date
    sender_email: str
    system: str
    citation: str
    sentence: str


def run_decision_correlation_tests(ctx, ids: IdGen) -> tuple[list[Finding], list[Enquiry]]:
    findings: list[Finding] = []
    enquiries: list[Enquiry] = []
    applications = list(ctx.policy.applications.keys())

    decisions: list[_Decision] = []
    ambiguous_hits: list[tuple] = []

    for e in ctx.bundle.emails:
        if not e.sent_date:
            continue
        sender_email = _extract_email(e.sender)
        full_text_l = f"{e.subject}\n{e.body}".lower()
        if len(applications) == 1:
            system = applications[0]
        else:
            system = next((app for app in applications if app.lower() in full_text_l), None)
        if not system:
            continue

        for sentence in _split_sentences(_clean_email_body(e.body)):
            action = _classify_action(normalize(sentence))
            if not action:
                continue
            for emp, ambiguous_candidates in _resolve_sentence_subjects(ctx, sentence, sender_email):
                if emp is None:
                    if ambiguous_candidates:
                        ambiguous_hits.append((ambiguous_candidates, sentence.strip(), e, action))
                    continue
                decisions.append(_Decision(
                    subject=emp, action=action, when=e.sent_date, sender_email=sender_email,
                    system=system, citation=e.provenance.cite(), sentence=sentence.strip(),
                ))

    # temporal precedence: the latest-dated decision per (subject, system) governs
    governing: dict[tuple, _Decision] = {}
    history_by_key: dict[tuple, list[_Decision]] = {}
    for d in decisions:
        key = (d.subject.emp_id, d.system)
        history_by_key.setdefault(key, []).append(d)
        if key not in governing or d.when > governing[key].when:
            governing[key] = d

    for key, d in governing.items():
        emp_id, system = key
        emp = d.subject
        records = ctx.employee_grants().get((emp_id, system), [])
        if not records:
            continue  # no access on record for this system at all - nothing to check
        currently_active = _is_currently_active(records)
        history_citations = sorted({hd.citation for hd in history_by_key[key]})

        if d.action == "revoke" and currently_active:
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.ACCESS_DECISION_NOT_ACTIONED,
                severity=Severity.HIGH,
                system=system,
                subject_person=emp.full_name,
                subject_email=emp.email,
                condition=f'{emp.full_name}\'s access in {system} was instructed to be revoked '
                          f'("{d.sentence}", {d.when.isoformat()}), but the account is still Active.',
                criteria="A documented revoke decision must be reflected in the actual access state.",
                cause="The instruction was not carried through to the system, or the change was never implemented.",
                effect="Access that was supposed to be removed remains available, contrary to the documented "
                       "decision and the reason given for it.",
                recommendation=f"Revoke {emp.full_name}'s {system} access now and confirm with "
                               f"{d.sender_email or 'the instructing manager'} that this closes the item.",
                evidence=sorted({r.provenance.cite() for r in records} | set(history_citations)),
                confidence=0.85,
            ))
        elif d.action == "retain" and not currently_active:
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.ACCESS_DECISION_CONTRADICTED,
                severity=Severity.HIGH,
                system=system,
                subject_person=emp.full_name,
                subject_email=emp.email,
                condition=f'{emp.full_name}\'s access in {system} was instructed to be retained '
                          f'("{d.sentence}", {d.when.isoformat()}, the most recent instruction on file), but the '
                          f'account shows as revoked/disabled.',
                criteria="The most recent documented decision governs; access must not be removed on the basis "
                         "of a superseded instruction.",
                cause="An earlier, superseded instruction (or an unrelated action) appears to have been actioned "
                      "instead of the current one.",
                effect="Access was removed against the current documented decision - if it was needed for a "
                       "legitimate business reason, work may now be blocked; if the removal was itself a "
                       "mistake, it should be corrected and the cause understood.",
                recommendation=f"Confirm with {d.sender_email or 'the instructing manager'} whether access should "
                               f"be restored, and identify why the superseded instruction was actioned instead.",
                evidence=sorted({r.provenance.cite() for r in records} | set(history_citations)),
                confidence=0.85,
            ))

        sender_emp = ctx.employees_by_email.get((d.sender_email or "").lower())
        if sender_emp and (emp.manager_email or "").lower() != (d.sender_email or "").lower():
            corroborated = any(
                (hd.sender_email or "").lower() == (emp.manager_email or "").lower()
                for hd in history_by_key[key]
            )
            if not corroborated:
                findings.append(Finding(
                    finding_id=ids.next("FND"),
                    finding_type=FindingType.OUT_OF_AUTHORITY_INSTRUCTION,
                    severity=Severity.MEDIUM,
                    system=system,
                    subject_person=emp.full_name,
                    subject_email=emp.email,
                    condition=f"The instruction to {d.action} {emp.full_name}'s access in {system} came from "
                              f"{sender_emp.full_name} ({d.sender_email}), who does not appear to be "
                              f"{emp.full_name}'s manager of record ({emp.manager_email or 'none on file'}), and "
                              f"no corroborating instruction from the actual manager exists in the evidence "
                              f"provided.",
                    criteria="Access decisions should come from, or be corroborated by, the subject's own "
                             "manager of record.",
                    cause="This may reflect a delegation, a reporting-line change not yet updated in the HR "
                          "record, or a genuine authority gap in how the request was raised.",
                    effect="Acting on instructions from someone without clear, evidenced authority over the "
                           "account holder weakens the audit trail for why the access change happened.",
                    recommendation=f"Confirm this instruction with "
                                   f"{emp.manager_email or 'the employee’s actual manager'} before relying "
                                   f"on it further.",
                    evidence=[d.citation],
                    confidence=0.6,
                ))

    seen_enq_keys: set[tuple] = set()
    for candidates, sentence, e, action in ambiguous_hits:
        key = (tuple(sorted(c.emp_id for c in candidates)), sentence)
        if key in seen_enq_keys:
            continue
        seen_enq_keys.add(key)
        names = "; ".join(
            f"{c.full_name} ({c.department or 'unknown dept'}, reports to {c.manager_email or 'no one on file'})"
            for c in candidates
        )
        enquiries.append(Enquiry(
            enquiry_id=ids.next("ENQ"),
            topic="Ambiguous access decision",
            question=f'An email instruction ("{sentence}") appears to {action} someone\'s access, but the name '
                      f'given could refer to more than one person: {names}. Which one does this refer to?',
            context=e.provenance.cite(),
            blocking=True,
        ))

    return findings, enquiries
