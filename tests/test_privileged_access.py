"""Unit tests for the Privileged Access Management ITGC control module,
built with synthetic data the way the other tests_itgc unit tests are.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itgc.models import Employee, AccessRecord, PrivilegedAccessReview, Provenance
from itgc.policy import Policy, ApplicationPolicy
from itgc.context import AuditContext
from itgc.ingest import EvidenceBundle
from itgc.tests_itgc.privileged_access import run_privileged_access_tests
from itgc.tests_itgc.idgen import IdGen


def make_policy(privileged_profiles=("Admin",), review_cycle_days=90):
    return Policy(
        applications={"TestERP": ApplicationPolicy(
            name="TestERP", sensitivity="high", profiles=["User", "Admin"], sod_conflicts=[],
            role_to_profile={}, privileged_profiles=list(privileged_profiles),
        )},
        deprovisioning_sla_days=3, dormant_threshold_days=90, joiner_provisioning_sla_days=10,
        company_name="Test Co", policy_reference="TEST-POL-01", sod_policy_reference="TEST-SOD-01",
        privileged_review_cycle_days=review_cycle_days,
    )


def make_employee(emp_id, name, email, manager_email=None):
    return Employee(
        emp_id=emp_id, full_name=name, email=email, department="IT", job_title="Sysadmin",
        manager_email=manager_email, status="Active", hire_date=date(2020, 1, 1), term_date=None,
        provenance=Provenance(source_file="x", source_type="employee_master", location="row 1"),
    )


def make_access(system, emp, profiles, status="Active"):
    rec = AccessRecord(
        system=system, account_id=emp.emp_id, account_name=emp.full_name, account_email=emp.email,
        profiles=profiles, account_status=status, last_login=None,
        provenance=Provenance(source_file="uar.xlsx", source_type="uar_sheet", location="row 1"),
    )
    rec.matched_employee = emp
    return rec


def make_review(account_id, system, reviewer, review_date, decision="retain", justification="Reviewed and confirmed still required for role duties."):
    return PrivilegedAccessReview(
        review_id="REV-1", account_id=account_id, system=system, reviewer=reviewer,
        review_date=review_date, justification=justification, decision=decision,
        provenance=Provenance(source_file="reviews.csv", source_type="privileged_access_review", location="row 1"),
    )


def make_ctx(employees, access_records, reviews, as_of=date(2026, 9, 1), review_cycle_days=90):
    bundle = EvidenceBundle(employees=employees, access_records=access_records, privileged_access_reviews=reviews)
    ctx = AuditContext(as_of=as_of, policy=make_policy(review_cycle_days=review_cycle_days), bundle=bundle)
    ctx.employees_by_email = {e.email.lower(): e for e in employees}
    return ctx


class TestPrivilegedAccess(unittest.TestCase):
    def test_never_reviewed_flagged(self):
        emp = make_employee("E1", "Pat Admin", "pat@x.com")
        access = make_access("TestERP", emp, ["Admin"])
        ctx = make_ctx([emp], [access], [])
        findings, enquiries = run_privileged_access_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("PRIVILEGED_ACCESS_NEVER_REVIEWED", types)

    def test_review_outside_cycle_flagged(self):
        emp = make_employee("E1", "Pat Admin", "pat@x.com")
        access = make_access("TestERP", emp, ["Admin"])
        review = make_review("E1", "TestERP", "mgr@x.com", date(2026, 1, 1))  # >90 days before as_of
        ctx = make_ctx([emp], [access], [review], as_of=date(2026, 9, 1))
        findings, _ = run_privileged_access_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("PRIVILEGED_ACCESS_NEVER_REVIEWED", types)

    def test_recent_review_with_real_justification_clears_it(self):
        emp = make_employee("E1", "Pat Admin", "pat@x.com")
        access = make_access("TestERP", emp, ["Admin"])
        review = make_review("E1", "TestERP", "mgr@x.com", date(2026, 8, 15))
        ctx = make_ctx([emp], [access], [review], as_of=date(2026, 9, 1))
        findings, _ = run_privileged_access_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertNotIn("PRIVILEGED_ACCESS_NEVER_REVIEWED", types)
        self.assertNotIn("PRIVILEGED_ACCESS_RETAINED_WITHOUT_JUSTIFICATION", types)

    def test_retained_with_blank_justification_flagged(self):
        emp = make_employee("E1", "Pat Admin", "pat@x.com")
        access = make_access("TestERP", emp, ["Admin"])
        review = make_review("E1", "TestERP", "mgr@x.com", date(2026, 8, 15), decision="retain", justification="")
        ctx = make_ctx([emp], [access], [review], as_of=date(2026, 9, 1))
        findings, _ = run_privileged_access_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("PRIVILEGED_ACCESS_RETAINED_WITHOUT_JUSTIFICATION", types)

    def test_retained_with_circular_justification_flagged(self):
        emp = make_employee("E1", "Pat Admin", "pat@x.com")
        access = make_access("TestERP", emp, ["Admin"])
        review = make_review("E1", "TestERP", "mgr@x.com", date(2026, 8, 15), decision="retain",
                              justification="needs admin access")
        ctx = make_ctx([emp], [access], [review], as_of=date(2026, 9, 1))
        findings, _ = run_privileged_access_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("PRIVILEGED_ACCESS_RETAINED_WITHOUT_JUSTIFICATION", types)

    def test_self_reviewed_flagged(self):
        emp = make_employee("E1", "Pat Admin", "pat@x.com")
        access = make_access("TestERP", emp, ["Admin"])
        review = make_review("E1", "TestERP", "pat@x.com", date(2026, 8, 15))
        ctx = make_ctx([emp], [access], [review], as_of=date(2026, 9, 1))
        findings, _ = run_privileged_access_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("PRIVILEGED_ACCESS_SELF_REVIEWED", types)

    def test_non_privileged_profile_not_evaluated(self):
        emp = make_employee("E1", "Reg User", "reg@x.com")
        access = make_access("TestERP", emp, ["User"])
        ctx = make_ctx([emp], [access], [])
        findings, _ = run_privileged_access_tests(ctx, IdGen())
        self.assertEqual(findings, [])

    def test_reviewer_concentration_raises_enquiry(self):
        emps = [make_employee(f"E{i}", f"Person {i}", f"p{i}@x.com") for i in range(4)]
        accesses = [make_access("TestERP", e, ["Admin"]) for e in emps]
        reviews = [make_review(e.emp_id, "TestERP", "solo@x.com", date(2026, 8, 15)) for e in emps]
        ctx = make_ctx(emps, accesses, reviews, as_of=date(2026, 9, 1))
        findings, enquiries = run_privileged_access_tests(ctx, IdGen())
        topics = [e.topic for e in enquiries]
        self.assertIn("Privileged access review concentration", topics)


if __name__ == "__main__":
    unittest.main()
