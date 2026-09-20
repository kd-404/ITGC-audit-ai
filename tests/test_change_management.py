"""Unit tests for the Change Management ITGC control module, built with
synthetic data the way test_joiner.py and test_decision_correlation.py are -
this proves each rule fires (and doesn't false-alarm) independent of any one
sample dataset.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itgc.models import Employee, ChangeRecord, Provenance
from itgc.policy import Policy, ApplicationPolicy
from itgc.context import AuditContext
from itgc.ingest import EvidenceBundle
from itgc.tests_itgc.change_management import run_change_management_tests
from itgc.tests_itgc.idgen import IdGen


def make_policy(sensitivity="low"):
    return Policy(
        applications={"TestERP": ApplicationPolicy(
            name="TestERP", sensitivity=sensitivity, profiles=["User"], sod_conflicts=[], role_to_profile={},
        )},
        deprovisioning_sla_days=3, dormant_threshold_days=90, joiner_provisioning_sla_days=10,
        company_name="Test Co", policy_reference="TEST-POL-01", sod_policy_reference="TEST-SOD-01",
    )


def make_employee(emp_id, name, email, job_title="Developer"):
    return Employee(
        emp_id=emp_id, full_name=name, email=email, department="Eng", job_title=job_title,
        manager_email=None, status="Active", hire_date=date(2020, 1, 1), term_date=None,
        provenance=Provenance(source_file="x", source_type="employee_master", location="row 1"),
    )


def make_change(**kwargs):
    defaults = dict(
        change_id="CHG-1", system="TestERP", description="Fix bug", requested_by=None,
        developer=None, approver=None, deployer=None, environment="Production",
        test_evidence_ref=None, requested_date=None, approved_date=None, deployed_date=None,
        status="Deployed", emergency_flag=False, post_review_date=None, post_reviewed_by=None,
        provenance=Provenance(source_file="changes.csv", source_type="change_record", location="row 1"),
    )
    defaults.update(kwargs)
    return ChangeRecord(**defaults)


def make_ctx(employees, change_records, as_of=date(2026, 9, 1), sensitivity="low"):
    bundle = EvidenceBundle(employees=employees, change_records=change_records)
    ctx = AuditContext(as_of=as_of, policy=make_policy(sensitivity), bundle=bundle)
    ctx.employees_by_email = {e.email.lower(): e for e in employees}
    return ctx


class TestChangeManagement(unittest.TestCase):
    def test_deployed_with_no_approver(self):
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver=None,
                         deployed_date=date(2026, 8, 1))
        ctx = make_ctx([], [c])
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("CHANGE_UNAPPROVED_DEPLOYMENT", types)

    def test_deployed_before_approved(self):
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver="mgr@x.com",
                         approved_date=date(2026, 8, 5), deployed_date=date(2026, 8, 1))
        ctx = make_ctx([], [c])
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("CHANGE_UNAPPROVED_DEPLOYMENT", types)

    def test_clean_change_with_approval_order_produces_no_deployment_finding(self):
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver="mgr@x.com",
                         approved_date=date(2026, 8, 1), deployed_date=date(2026, 8, 5),
                         test_evidence_ref="UAT-001")
        ctx = make_ctx([], [c])
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("CHANGE_UNAPPROVED_DEPLOYMENT", types)

    def test_developer_is_deployer_flagged(self):
        c = make_change(developer="dev@x.com", deployer="dev@x.com", approver="mgr@x.com",
                         approved_date=date(2026, 8, 1), deployed_date=date(2026, 8, 5),
                         test_evidence_ref="UAT-001")
        ctx = make_ctx([], [c])
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("CHANGE_SOD_DEVELOPER_IS_DEPLOYER", types)

    def test_missing_test_evidence_for_production_change(self):
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver="mgr@x.com",
                         approved_date=date(2026, 8, 1), deployed_date=date(2026, 8, 5),
                         environment="Production", test_evidence_ref=None, emergency_flag=False)
        ctx = make_ctx([], [c])
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("CHANGE_MISSING_TEST_EVIDENCE", types)

    def test_emergency_change_skips_missing_test_evidence_check(self):
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver="mgr@x.com",
                         deployed_date=date(2026, 8, 5), environment="Production",
                         test_evidence_ref=None, emergency_flag=True,
                         post_review_date=date(2026, 8, 7), post_reviewed_by="mgr@x.com")
        ctx = make_ctx([], [c], as_of=date(2026, 8, 8))
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("CHANGE_MISSING_TEST_EVIDENCE", types)

    def test_emergency_change_not_retroactively_reviewed(self):
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver="mgr@x.com",
                         deployed_date=date(2026, 8, 1), emergency_flag=True,
                         post_review_date=None, post_reviewed_by=None)
        ctx = make_ctx([], [c], as_of=date(2026, 8, 20))  # well past the SLA window
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("CHANGE_EMERGENCY_NOT_RETROACTIVELY_REVIEWED", types)

    def test_emergency_change_reviewed_in_time_produces_no_finding(self):
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver="mgr@x.com",
                         deployed_date=date(2026, 8, 1), emergency_flag=True,
                         post_review_date=date(2026, 8, 3), post_reviewed_by="mgr@x.com")
        ctx = make_ctx([], [c], as_of=date(2026, 8, 20))
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("CHANGE_EMERGENCY_NOT_RETROACTIVELY_REVIEWED", types)

    def test_missing_cab_approval_on_high_sensitivity_system(self):
        approver = make_employee("E1", "Regular Approver", "mgr@x.com", job_title="Team Lead Manager")
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver="staff@x.com",
                         approved_date=date(2026, 8, 1), deployed_date=date(2026, 8, 5),
                         test_evidence_ref="UAT-001", environment="Production")
        ctx = make_ctx([approver], [c], sensitivity="high")
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("CHANGE_MISSING_CAB_APPROVAL", types)

    def test_emergency_change_with_no_approver_does_not_flag_unapproved_deployment(self):
        """Regression: emergency changes are expected to skip pre-approval,
        so a missing approver alone must not double-flag them under
        CHANGE_UNAPPROVED_DEPLOYMENT - that gap belongs to the emergency
        retroactive-review check instead."""
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver=None,
                         deployed_date=date(2026, 8, 1), emergency_flag=True,
                         post_review_date=date(2026, 8, 3), post_reviewed_by="mgr@x.com")
        ctx = make_ctx([], [c], as_of=date(2026, 8, 20))
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("CHANGE_UNAPPROVED_DEPLOYMENT", types)

    def test_emergency_change_deployed_before_its_own_approval_still_flagged(self):
        """An emergency change that nonetheless has an approval date it
        ignored (deployed before that approval) is still inconsistent, even
        though emergency changes are otherwise allowed to skip approval
        entirely."""
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver="mgr@x.com",
                         approved_date=date(2026, 8, 5), deployed_date=date(2026, 8, 1),
                         emergency_flag=True, post_review_date=date(2026, 8, 3), post_reviewed_by="mgr@x.com")
        ctx = make_ctx([], [c], as_of=date(2026, 8, 20))
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("CHANGE_UNAPPROVED_DEPLOYMENT", types)

    def test_emergency_change_with_no_approver_does_not_flag_missing_cab(self):
        """Regression: an emergency change with no approver on a high-
        sensitivity system must not ALSO be flagged for missing CAB
        approval - that's the same "emergency changes skip pre-approval by
        design" exception as CHANGE_UNAPPROVED_DEPLOYMENT."""
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver=None,
                         deployed_date=date(2026, 8, 1), emergency_flag=True,
                         post_review_date=date(2026, 8, 3), post_reviewed_by="mgr@x.com")
        ctx = make_ctx([], [c], as_of=date(2026, 8, 20), sensitivity="high")
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("CHANGE_MISSING_CAB_APPROVAL", types)

    def test_emergency_change_with_ineligible_approver_still_flags_missing_cab(self):
        """An emergency change that DOES have an approver on record (just not
        a CAB-eligible one) is still held to the CAB-eligibility bar."""
        approver = make_employee("E1", "Regular Staff", "staff@x.com", job_title="Analyst")
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver="staff@x.com",
                         deployed_date=date(2026, 8, 1), emergency_flag=True,
                         post_review_date=date(2026, 8, 3), post_reviewed_by="mgr@x.com")
        ctx = make_ctx([approver], [c], as_of=date(2026, 8, 20), sensitivity="high")
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("CHANGE_MISSING_CAB_APPROVAL", types)

    def test_cab_eligible_approver_on_high_sensitivity_system_clears_it(self):
        approver = make_employee("E1", "Change Board Lead", "cab@x.com", job_title="Change Manager")
        c = make_change(developer="dev@x.com", deployer="ops@x.com", approver="cab@x.com",
                         approved_date=date(2026, 8, 1), deployed_date=date(2026, 8, 5),
                         test_evidence_ref="UAT-001", environment="Production")
        ctx = make_ctx([approver], [c], sensitivity="high")
        findings = run_change_management_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("CHANGE_MISSING_CAB_APPROVAL", types)


if __name__ == "__main__":
    unittest.main()
