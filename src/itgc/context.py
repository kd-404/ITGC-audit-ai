"""Assembles everything a test needs: resolved evidence + policy + a couple
of shared indexes, built once per engagement run."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .ingest import ingest_directory, EvidenceBundle
from .identity import resolve_access_records, resolve_person
from .policy import Policy, load_policy
from .ingest.fuzzy import name_key


@dataclass
class AuditContext:
    as_of: date
    policy: Policy
    bundle: EvidenceBundle
    employees_by_email: dict = field(default_factory=dict)
    employees_by_namekey: dict = field(default_factory=dict)

    def current_access_records(self):
        """The access_records that represent "now" for each system.

        Most evidence is a single point-in-time UAR export with no snapshot
        date at all, in which case every record for that system is "current"
        - exactly the pre-existing behavior. A system evidenced by two or
        more DISTINCT snapshot dates is being compared period-start vs
        period-end (see tests_itgc/uar_period_diff.py); for every other test
        (SoD, dormant, excess, orphan, JML), "current" means the latest of
        those dated snapshots, not the union of all of them - otherwise a
        profile a person held only at period-start and gave up before
        period-end would wrongly still look "held" today.

        A system with a MIX of dated and undated rows is treated as legacy
        single-snapshot (all rows kept) rather than guessed at - that shape
        shouldn't occur from a single export process, and silently picking
        a side would be worse than just not attempting the split.
        """
        by_system: dict[str, list] = {}
        for rec in self.bundle.access_records:
            by_system.setdefault(rec.system, []).append(rec)

        out = []
        for system, records in by_system.items():
            dates = {r.snapshot_date for r in records}
            if None in dates or len(dates) < 2:
                out.extend(records)  # legacy: no usable multi-snapshot signal
            else:
                latest = max(dates)
                out.extend(r for r in records if r.snapshot_date == latest)
        return out

    def snapshot_dates_by_system(self) -> dict:
        """{system: sorted list of distinct snapshot dates} for systems that
        have 2+ distinct dated snapshots - i.e. the systems uar_period_diff.py
        has anything to compare. Systems not in this dict have no usable
        multi-snapshot evidence (single export, or a mix of dated/undated
        rows - see current_access_records)."""
        by_system: dict[str, set] = {}
        for rec in self.bundle.access_records:
            by_system.setdefault(rec.system, set()).add(rec.snapshot_date)
        return {s: sorted(d) for s, d in by_system.items() if None not in d and len(d) >= 2}

    def employee_grants(self):
        """Group CURRENT (see current_access_records) access records by
        (employee, system) so multi-row profile grants (an account listed
        twice for two profiles, or a comma-joined profile cell) are
        evaluated together."""
        groups: dict[tuple, list] = {}
        for rec in self.current_access_records():
            key = (rec.matched_employee.emp_id if rec.matched_employee else f"UNMATCHED:{rec.account_id}", rec.system)
            groups.setdefault(key, []).append(rec)
        return groups


def build_context(company_dir: Path, evidence_dir: Path, as_of: date) -> AuditContext:
    company_dir, evidence_dir = Path(company_dir), Path(evidence_dir)
    policy = load_policy(company_dir)
    known_systems = list(policy.applications.keys())

    company_bundle = ingest_directory(company_dir, known_systems)
    evidence_bundle = ingest_directory(evidence_dir, known_systems)

    bundle = EvidenceBundle(
        employees=company_bundle.employees,
        access_records=evidence_bundle.access_records,
        tickets=evidence_bundle.tickets,
        change_records=evidence_bundle.change_records,
        privileged_access_reviews=evidence_bundle.privileged_access_reviews,
        backup_jobs=evidence_bundle.backup_jobs,
        incidents=evidence_bundle.incidents,
        emails=evidence_bundle.emails,
        unclassified_files=company_bundle.unclassified_files + evidence_bundle.unclassified_files,
        file_classifications=company_bundle.file_classifications + evidence_bundle.file_classifications,
    )

    resolve_access_records(bundle.access_records, bundle.employees)

    ctx = AuditContext(
        as_of=as_of,
        policy=policy,
        bundle=bundle,
        employees_by_email={e.email.lower(): e for e in bundle.employees if e.email},
        employees_by_namekey={},
    )
    for e in bundle.employees:
        ctx.employees_by_namekey.setdefault(name_key(e.full_name), []).append(e)
    return ctx
