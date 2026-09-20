from __future__ import annotations

from .idgen import IdGen
from .jml import run_jml
from .joiner import run_joiner_provisioning
from .access import run_access_tests
from .orphan import run_orphan_test
from .provisioning import run_provisioning_tests
from .uar_period_diff import run_uar_period_diff_tests
# change_management, privileged_access and backup_incident all have real,
# unit-tested logic now (see tests/test_change_management.py,
# tests/test_privileged_access.py, tests/test_backup_incident.py), but are
# opt-in via control_registry/run_pipeline's selected_controls rather than
# run unconditionally by run_all_tests() below, since they only fire against
# evidence a company_dir/evidence_dir actually contains (change_record /
# privileged_access_review / backup_job / incident files) - most engagements
# won't have all of that evidence, so running them unconditionally would
# just add "no findings" noise.
from .change_management import run_change_management_tests
from .privileged_access import run_privileged_access_tests
from .backup_incident import run_backup_incident_tests, run_backup_tests, run_incident_tests
from ..models import Finding, Severity

SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}

# Maps control_registry control_ids to the test functions that implement
# them. Only "access_review" and "provisioning" live here - decision_
# correlation, change_management and privileged_access each have their own
# richer return shape (findings + enquiries) and are called directly by
# pipeline.run_pipeline instead of through run_all_tests.
_DOMAIN_TEST_FUNCS = {
    "access_review": [run_jml, run_joiner_provisioning, run_access_tests, run_orphan_test, run_uar_period_diff_tests],
    "provisioning": [run_provisioning_tests],
}


def run_all_tests(ctx, ids: IdGen | None = None, selected_controls: set[str] | None = None) -> list[Finding]:
    """Runs the access_review/provisioning test functions. `selected_controls`
    restricts which of those two domains actually run; None (the default)
    runs both, preserving the pre-existing behavior for any caller that
    doesn't know about control selection."""
    ids = ids if ids is not None else IdGen()
    domains = selected_controls if selected_controls is not None else set(_DOMAIN_TEST_FUNCS)
    findings: list[Finding] = []
    for domain, funcs in _DOMAIN_TEST_FUNCS.items():
        if domain not in domains:
            continue
        for fn in funcs:
            findings += fn(ctx, ids)
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.system, f.subject_person or ""))
    return findings


__all__ = [
    "run_all_tests", "IdGen",
    "run_change_management_tests", "run_privileged_access_tests",
    "run_backup_incident_tests", "run_backup_tests", "run_incident_tests",
]
