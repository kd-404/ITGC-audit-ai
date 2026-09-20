"""Identity resolution: tie every account, ticket requester/approver and email
sender/recipient back to a row in the employee master.

Match order (most to least reliable), each carrying its own confidence:
  1. exact email match
  2. exact email match on local-part only (domain typo/alias, e.g. old domain)
  3. fuzzy name match (handles "Jon Ito" vs "Jonathan Ito", nicknames, typos)
Anything below MIN_CONFIDENCE is left unmatched - callers decide whether that
means "orphan account" (an ITGC finding) or "needs an enquiry" (can't audit
this record without more information), which are different things.
"""
from __future__ import annotations

from ..models import Employee, AccessRecord
from ..ingest.fuzzy import ratio, name_key

MIN_CONFIDENCE = 0.55
FUZZY_NAME_THRESHOLD = 0.82


def _by_email(employees: list[Employee]) -> dict[str, Employee]:
    return {e.email.lower(): e for e in employees if e.email}


def _by_namekey(employees: list[Employee]) -> dict[str, list[Employee]]:
    out: dict[str, list[Employee]] = {}
    for e in employees:
        out.setdefault(name_key(e.full_name), []).append(e)
    return out


def resolve_person(name: str | None, email: str | None, employees: list[Employee],
                    email_index: dict[str, Employee] | None = None,
                    name_index: dict[str, list[Employee]] | None = None) -> tuple[Employee | None, float, str]:
    """Resolve a single (name, email) pair to an Employee.
    Returns (employee_or_None, confidence 0..1, method)."""
    email_index = email_index if email_index is not None else _by_email(employees)
    name_index = name_index if name_index is not None else _by_namekey(employees)

    if email:
        e = email_index.get(email.lower())
        if e:
            return e, 1.0, "exact_email"
        local = email.split("@")[0].lower()
        for cand_email, cand in email_index.items():
            if cand_email.split("@")[0] == local:
                return cand, 0.85, "email_localpart"

    if name:
        key = name_key(name)
        candidates = name_index.get(key)
        if candidates and len(candidates) == 1:
            return candidates[0], 0.9, "exact_name"
        # broader fuzzy pass across all employees
        best_emp, best_score = None, 0.0
        for e in employees:
            s = ratio(name, e.full_name)
            if s > best_score:
                best_score, best_emp = s, e
        if best_emp and best_score >= FUZZY_NAME_THRESHOLD:
            return best_emp, round(best_score, 2), "fuzzy_name"

    return None, 0.0, "unmatched"


def resolve_access_records(records: list[AccessRecord], employees: list[Employee]) -> None:
    """Mutates each AccessRecord in place, setting matched_employee/confidence/method."""
    email_index = _by_email(employees)
    name_index = _by_namekey(employees)
    for r in records:
        emp, conf, method = resolve_person(r.account_name, r.account_email, employees, email_index, name_index)
        r.matched_employee = emp
        r.match_confidence = conf
        r.match_method = method
