"""Unit tests for the Backup & Recovery / Incident Management ITGC control
module, built with synthetic data the way the other tests_itgc unit tests
are.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itgc.models import BackupJob, Incident, ChangeRecord, Provenance
from itgc.policy import Policy, ApplicationPolicy
from itgc.context import AuditContext
from itgc.ingest import EvidenceBundle
from itgc.tests_itgc.backup_incident import run_backup_tests, run_incident_tests
from itgc.tests_itgc.idgen import IdGen


def make_policy(restore_interval=180, incident_sla=None):
    return Policy(
        applications={"TestERP": ApplicationPolicy(
            name="TestERP", sensitivity="low", profiles=["User"], sod_conflicts=[], role_to_profile={},
        )},
        deprovisioning_sla_days=3, dormant_threshold_days=90, joiner_provisioning_sla_days=10,
        company_name="Test Co", policy_reference="TEST-POL-01", sod_policy_reference="TEST-SOD-01",
        backup_restore_test_interval_days=restore_interval,
        incident_sla_days=incident_sla or {"critical": 1, "high": 3, "medium": 5, "low": 10},
    )


def make_job(**kwargs):
    defaults = dict(
        job_id="JOB-1", system="TestERP", scheduled_time=date(2026, 8, 1), status="Success",
        job_type="backup", verified_by=None, verification_date=None,
        provenance=Provenance(source_file="backups.csv", source_type="backup_job", location="row 1"),
    )
    defaults.update(kwargs)
    return BackupJob(**defaults)


def make_incident(**kwargs):
    defaults = dict(
        incident_id="INC-1", system="TestERP", severity="High", reported_date=date(2026, 8, 1),
        resolved_date=None, root_cause=None, status="Open", description="Database connection timeout",
        provenance=Provenance(source_file="incidents.csv", source_type="incident", location="row 1"),
    )
    defaults.update(kwargs)
    return Incident(**defaults)


def make_change(**kwargs):
    defaults = dict(
        change_id="CHG-1", system="TestERP", description="Fix", requested_by=None, developer=None,
        approver=None, deployer=None, environment="Production", test_evidence_ref=None,
        requested_date=None, approved_date=None, deployed_date=None, status="Deployed",
        emergency_flag=False, post_review_date=None, post_reviewed_by=None,
        provenance=Provenance(source_file="changes.csv", source_type="change_record", location="row 1"),
    )
    defaults.update(kwargs)
    return ChangeRecord(**defaults)


def make_ctx(backup_jobs=None, incidents=None, change_records=None, as_of=date(2026, 9, 1), **policy_kwargs):
    bundle = EvidenceBundle(
        backup_jobs=backup_jobs or [], incidents=incidents or [], change_records=change_records or [],
    )
    return AuditContext(as_of=as_of, policy=make_policy(**policy_kwargs), bundle=bundle)


class TestBackupTests(unittest.TestCase):
    def test_unresolved_failure_flagged(self):
        j = make_job(status="Failure", scheduled_time=date(2026, 8, 1))
        ctx = make_ctx(backup_jobs=[j])
        findings = run_backup_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("BACKUP_JOB_FAILURE_UNRESOLVED", types)

    def test_failure_followed_by_success_clears_it(self):
        j1 = make_job(job_id="JOB-1", status="Failure", scheduled_time=date(2026, 8, 1))
        j2 = make_job(job_id="JOB-2", status="Success", scheduled_time=date(2026, 8, 2))
        ctx = make_ctx(backup_jobs=[j1, j2])
        findings = run_backup_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("BACKUP_JOB_FAILURE_UNRESOLVED", types)

    def test_never_verified_flagged(self):
        j = make_job(status="Success", verified_by=None, verification_date=None)
        ctx = make_ctx(backup_jobs=[j])
        findings = run_backup_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("BACKUP_NEVER_VERIFIED", types)

    def test_verified_backup_clears_never_verified(self):
        j = make_job(status="Success", verified_by="ops@x.com", verification_date=date(2026, 8, 5))
        ctx = make_ctx(backup_jobs=[j])
        findings = run_backup_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("BACKUP_NEVER_VERIFIED", types)

    def test_restore_never_tested_when_no_restore_job(self):
        j = make_job(status="Success", verified_by="ops@x.com", verification_date=date(2026, 8, 5))
        ctx = make_ctx(backup_jobs=[j], as_of=date(2026, 9, 1))
        findings = run_backup_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("BACKUP_RESTORE_NEVER_TESTED", types)

    def test_recent_restore_test_clears_it(self):
        j = make_job(status="Success", verified_by="ops@x.com", verification_date=date(2026, 8, 5))
        r = make_job(job_id="JOB-R1", job_type="restore_test", status="Success",
                     verified_by="ops@x.com", verification_date=date(2026, 8, 20))
        ctx = make_ctx(backup_jobs=[j, r], as_of=date(2026, 9, 1))
        findings = run_backup_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("BACKUP_RESTORE_NEVER_TESTED", types)

    def test_stale_restore_test_still_flagged(self):
        j = make_job(status="Success", verified_by="ops@x.com", verification_date=date(2026, 8, 5))
        r = make_job(job_id="JOB-R1", job_type="restore_test", status="Success",
                     verified_by="ops@x.com", verification_date=date(2026, 1, 1))
        ctx = make_ctx(backup_jobs=[j, r], as_of=date(2026, 9, 1), restore_interval=180)
        findings = run_backup_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("BACKUP_RESTORE_NEVER_TESTED", types)


class TestIncidentTests(unittest.TestCase):
    def test_sla_breach_flagged(self):
        inc = make_incident(severity="High", reported_date=date(2026, 8, 1), resolved_date=date(2026, 8, 10),
                             status="Resolved", root_cause="Root cause documented")
        ctx = make_ctx(incidents=[inc])
        findings = run_incident_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("INCIDENT_SLA_BREACH", types)

    def test_resolved_within_sla_clears_it(self):
        inc = make_incident(severity="High", reported_date=date(2026, 8, 1), resolved_date=date(2026, 8, 3),
                             status="Resolved", root_cause="Root cause documented")
        ctx = make_ctx(incidents=[inc])
        findings = run_incident_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("INCIDENT_SLA_BREACH", types)

    def test_missing_root_cause_on_closed_incident(self):
        inc = make_incident(status="Closed", root_cause=None, reported_date=date(2026, 8, 1),
                             resolved_date=date(2026, 8, 2))
        ctx = make_ctx(incidents=[inc])
        findings = run_incident_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("INCIDENT_MISSING_ROOT_CAUSE", types)

    def test_open_incident_with_no_root_cause_not_flagged(self):
        inc = make_incident(status="Open", root_cause=None)
        ctx = make_ctx(incidents=[inc])
        findings = run_incident_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("INCIDENT_MISSING_ROOT_CAUSE", types)

    def test_recurring_similar_incident_with_no_fix_in_between_flagged(self):
        inc1 = make_incident(incident_id="INC-1", reported_date=date(2026, 7, 1),
                              description="Database connection timeout on checkout service",
                              status="Resolved", resolved_date=date(2026, 7, 2), root_cause="Restarted service")
        inc2 = make_incident(incident_id="INC-2", reported_date=date(2026, 8, 1),
                              description="Database connection timeout on checkout service",
                              status="Resolved", resolved_date=date(2026, 8, 2), root_cause="Restarted service")
        ctx = make_ctx(incidents=[inc1, inc2])
        findings = run_incident_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("INCIDENT_RECURRING_UNADDRESSED", types)

    def test_recurring_similar_incident_with_fix_in_between_clears_it(self):
        inc1 = make_incident(incident_id="INC-1", reported_date=date(2026, 7, 1),
                              description="Database connection timeout on checkout service",
                              status="Resolved", resolved_date=date(2026, 7, 2), root_cause="Restarted service")
        inc2 = make_incident(incident_id="INC-2", reported_date=date(2026, 8, 1),
                              description="Database connection timeout on checkout service",
                              status="Resolved", resolved_date=date(2026, 8, 2), root_cause="Restarted service")
        fix = make_change(deployed_date=date(2026, 7, 15))
        ctx = make_ctx(incidents=[inc1, inc2], change_records=[fix])
        findings = run_incident_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("INCIDENT_RECURRING_UNADDRESSED", types)

    def test_dissimilar_incidents_not_flagged_as_recurring(self):
        inc1 = make_incident(incident_id="INC-1", reported_date=date(2026, 7, 1),
                              description="Database connection timeout on checkout service",
                              status="Resolved", resolved_date=date(2026, 7, 2), root_cause="Restarted service")
        inc2 = make_incident(incident_id="INC-2", reported_date=date(2026, 8, 1),
                              description="Disk space warning on file server",
                              status="Resolved", resolved_date=date(2026, 8, 2), root_cause="Cleared logs")
        ctx = make_ctx(incidents=[inc1, inc2])
        findings = run_incident_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("INCIDENT_RECURRING_UNADDRESSED", types)


if __name__ == "__main__":
    unittest.main()
