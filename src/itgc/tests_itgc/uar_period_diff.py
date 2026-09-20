"""ITGC test: period-start vs period-end UAR comparison.

Every other access_review check (access.py, jml.py, orphan.py) looks at a
single, "current" UAR extract - which is exactly what a real user access
review usually gets: one export, pulled once, at some point during the
review period. That single point-in-time view has a structural blind spot:
an access change that happened mid-period is only visible if it happened to
still be in effect on the day the extract was pulled, and even then a single
extract can't tell you WHEN it changed or whether it was ever approved -
only that it currently exists.

This test is the one place in the pipeline that actually exploits having
TWO dated extracts for the same system (see AuditContext.current_access_records
and snapshot_dates_by_system in context.py, and infer_snapshot_date_from_filename
in ingest/loaders.py for how a record gets a snapshot_date at all). For any
system with 2+ distinct snapshot dates, it diffs the earliest ("period
start") against the latest ("period end") extract and flags any account
that shows MORE access at period end than it had at period start, unless
that specific new profile is backed by a provisioning ticket - using the
exact same find_provisioning_ticket lookup provisioning.py uses for its
current-state MISSING_APPROVAL_EVIDENCE check, so "documented" means the
same thing in both places.

Systems with only one snapshot (the common case) are untouched - this
function returns nothing for them, so it's purely additive over the
existing single-snapshot checks.
"""
from __future__ import annotations

from ..models import Finding, FindingType, Severity
from .evidence_lookup import find_provisioning_ticket
from .idgen import IdGen

ACTIVE_STATES_EXCLUDED = {"disabled", "inactive", "revoked", "closed", "terminated", "removed"}


def _active_profile_map(records: list) -> dict:
    """{employee_key: {"profiles": set[str], "records": [AccessRecord]}} for
    the active (non-disabled) rows in one snapshot. Unmatched accounts are
    excluded - orphan.py already owns "who does this account even belong
    to," and re-flagging an orphan here under a different finding type
    would just be noise, not a distinct signal."""
    out: dict = {}
    for r in records:
        if r.account_status.strip().lower() in ACTIVE_STATES_EXCLUDED:
            continue
        if not r.matched_employee:
            continue
        key = r.matched_employee.emp_id
        bucket = out.setdefault(key, {"profiles": set(), "records": []})
        bucket["profiles"].update(r.profiles)
        bucket["records"].append(r)
    return out


def run_uar_period_diff_tests(ctx, ids: IdGen) -> list[Finding]:
    findings: list[Finding] = []
    snapshot_systems = ctx.snapshot_dates_by_system()
    if not snapshot_systems:
        return findings

    for system, dates in snapshot_systems.items():
        start_date, end_date = dates[0], dates[-1]
        start_records = [r for r in ctx.bundle.access_records if r.system == system and r.snapshot_date == start_date]
        end_records = [r for r in ctx.bundle.access_records if r.system == system and r.snapshot_date == end_date]

        start_map = _active_profile_map(start_records)
        end_map = _active_profile_map(end_records)

        for key, end_info in end_map.items():
            start_info = start_map.get(key)
            start_profiles = start_info["profiles"] if start_info else set()
            new_profiles = sorted(end_info["profiles"] - start_profiles)
            if not new_profiles:
                continue

            emp = end_info["records"][0].matched_employee
            undocumented = [
                p for p in new_profiles
                if find_provisioning_ticket(ctx.bundle.tickets, emp.email, system, p) is None
            ]
            if not undocumented:
                continue  # every new profile has a ticket - a documented, legitimate mid-period change

            appeared_desc = (
                f"a new account that did not exist at all in the {start_date.isoformat()} extract"
                if start_info is None else
                f"additional access beyond what {emp.full_name} held in the {start_date.isoformat()} extract"
            )
            evidence = [r.provenance.cite() for r in end_info["records"]]
            if start_info:
                evidence += [r.provenance.cite() for r in start_info["records"]]

            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.UAR_UNDOCUMENTED_INTERIM_ACCESS_CHANGE,
                severity=Severity.HIGH,
                system=system,
                subject_person=emp.full_name,
                subject_email=emp.email,
                condition=(
                    f"Comparing the {start_date.isoformat()} and {end_date.isoformat()} {system} UAR extracts, "
                    f"{emp.full_name} shows {appeared_desc}: {', '.join(undocumented)}. No service-desk ticket "
                    f"in the evidence provided authorizes this change; a single end-of-period extract alone "
                    f"would not have surfaced this at all."
                ),
                criteria=f"{ctx.policy.policy_reference}: every access change made during the review period must "
                         f"be evidenced by an approved provisioning record, not only whatever access happens to "
                         f"be held on the day the review sample is pulled.",
                cause="Access was granted mid-period through a channel that bypassed the ticketing system, or "
                      "the approving ticket was never filed or was not retained.",
                effect="An access change with no approval trail cannot be shown to have been authorized. Because "
                       "this was only detected by comparing two dated extracts, a review relying on a single "
                       "point-in-time UAR export would have missed it entirely.",
                recommendation=f"Obtain retroactive approval for {', '.join(undocumented)} in {system}, or revoke "
                               f"it if it cannot be justified; ensure future in-period access changes are routed "
                               f"through the service desk regardless of urgency.",
                evidence=evidence,
                confidence=0.85,
            ))

    return findings
