"""Unit tests for the period-start/period-end UAR comparison
(uar_period_diff.py), built with synthetic data the way the other
tests_itgc unit tests are - this is what actually proves the multi-snapshot
diff fires (and, just as importantly, stays quiet) since the ACME sample's
existing UAR sheets are all single-snapshot by design.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itgc.models import Employee, Ticket, AccessRecord, Provenance
from itgc.policy import Policy, ApplicationPolicy
from itgc.context import AuditContext
from itgc.ingest import EvidenceBundle
from itgc.tests_itgc.uar_period_diff import run_uar_period_diff_tests
from itgc.tests_itgc.idgen import IdGen


def make_policy():
    return Policy(
        applications={"TestERP": ApplicationPolicy(
            name="TestERP", sensitivity="low", profiles=["User", "Admin"], sod_conflicts=[], role_to_profile={},
        )},
        deprovisioning_sla_days=3, dormant_threshold_days=90, joiner_provisioning_sla_days=10,
        company_name="Test Co", policy_reference="TEST-POL-01", sod_policy_reference="TEST-SOD-01",
    )


def make_employee(emp_id, name, email):
    return Employee(
        emp_id=emp_id, full_name=name, email=email, department="Ops", job_title="Analyst",
        manager_email="mgr@x.com", status="Active", hire_date=date(2020, 1, 1), term_date=None,
        provenance=Provenance(source_file="x", source_type="employee_master", location="row 1"),
    )


def make_access(emp, profiles, snapshot_date, account_id=None, status="Active", system="TestERP", loc="row 1"):
    rec = AccessRecord(
        system=system, account_id=account_id or emp.emp_id, account_name=emp.full_name, account_email=emp.email,
        profiles=profiles, account_status=status, last_login=None,
        provenance=Provenance(source_file="uar.csv", source_type="uar_sheet", location=loc),
        snapshot_date=snapshot_date,
    )
    rec.matched_employee = emp
    return rec


def make_ticket(requester, system, access_requested, created, approved, implemented):
    return Ticket(
        ticket_id="T1", requester_email=requester, approver_email="mgr@x.com", system=system,
        access_requested=access_requested, status="Closed", created=created, approved=approved,
        implemented=implemented, implementer_email="it@x.com",
        provenance=Provenance(source_file="tix.csv", source_type="servicedesk", location="row 1"),
    )


def make_ctx(access_records, tickets=None, employees=None):
    bundle = EvidenceBundle(employees=employees or [], access_records=access_records, tickets=tickets or [])
    return AuditContext(as_of=date(2026, 9, 15), policy=make_policy(), bundle=bundle)


class TestUarPeriodDiff(unittest.TestCase):
    def test_single_snapshot_system_is_untouched(self):
        """No second dated extract at all - the legacy, overwhelmingly common
        case - must produce nothing, regardless of what the one snapshot
        looks like."""
        emp = make_employee("E1", "Pat", "pat@x.com")
        rec = make_access(emp, ["Admin"], snapshot_date=None)
        ctx = make_ctx([rec])
        self.assertEqual(run_uar_period_diff_tests(ctx, IdGen()), [])

    def test_new_account_appearing_mid_period_without_ticket_is_flagged(self):
        emp = make_employee("E1", "Pat", "pat@x.com")
        end = make_access(emp, ["User"], snapshot_date=date(2026, 9, 1))
        ctx = make_ctx([end])  # only ONE snapshot date so far -> not multi-snapshot yet
        self.assertEqual(run_uar_period_diff_tests(ctx, IdGen()), [])

        start_of_other_system = make_access(
            make_employee("E2", "Other", "other@x.com"), ["User"], snapshot_date=date(2026, 6, 1), account_id="A2",
        )
        ctx2 = make_ctx([end, start_of_other_system])
        findings = run_uar_period_diff_tests(ctx2, IdGen())
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.finding_type.value, "UAR_UNDOCUMENTED_INTERIM_ACCESS_CHANGE")
        self.assertEqual(f.subject_email, "pat@x.com")
        self.assertIn("did not exist at all", f.condition)

    def test_new_profile_added_between_two_snapshots_without_ticket_is_flagged(self):
        emp = make_employee("E1", "Pat", "pat@x.com")
        start = make_access(emp, ["User"], snapshot_date=date(2026, 6, 1), loc="row 1")
        end = make_access(emp, ["User", "Admin"], snapshot_date=date(2026, 9, 1), loc="row 2")
        ctx = make_ctx([start, end])
        findings = run_uar_period_diff_tests(ctx, IdGen())
        self.assertEqual(len(findings), 1)
        self.assertIn("Admin", findings[0].condition)
        self.assertIn("additional access beyond", findings[0].condition)

    def test_new_profile_backed_by_a_ticket_is_not_flagged(self):
        emp = make_employee("E1", "Pat", "pat@x.com")
        start = make_access(emp, ["User"], snapshot_date=date(2026, 6, 1), loc="row 1")
        end = make_access(emp, ["User", "Admin"], snapshot_date=date(2026, 9, 1), loc="row 2")
        ticket = make_ticket("pat@x.com", "TestERP", "Admin", date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3))
        ctx = make_ctx([start, end], tickets=[ticket])
        self.assertEqual(run_uar_period_diff_tests(ctx, IdGen()), [])

    def test_unchanged_access_across_snapshots_is_not_flagged(self):
        emp = make_employee("E1", "Pat", "pat@x.com")
        start = make_access(emp, ["User"], snapshot_date=date(2026, 6, 1), loc="row 1")
        end = make_access(emp, ["User"], snapshot_date=date(2026, 9, 1), loc="row 2")
        ctx = make_ctx([start, end])
        self.assertEqual(run_uar_period_diff_tests(ctx, IdGen()), [])

    def test_profile_removed_between_snapshots_is_not_flagged(self):
        """Losing access mid-period is not a violation of this check - only
        gaining undocumented access is."""
        emp = make_employee("E1", "Pat", "pat@x.com")
        start = make_access(emp, ["User", "Admin"], snapshot_date=date(2026, 6, 1), loc="row 1")
        end = make_access(emp, ["User"], snapshot_date=date(2026, 9, 1), loc="row 2")
        ctx = make_ctx([start, end])
        self.assertEqual(run_uar_period_diff_tests(ctx, IdGen()), [])

    def test_disabled_account_at_end_snapshot_is_ignored(self):
        emp = make_employee("E1", "Pat", "pat@x.com")
        start = make_access(emp, ["User"], snapshot_date=date(2026, 6, 1), loc="row 1")
        end = make_access(emp, ["User", "Admin"], snapshot_date=date(2026, 9, 1), loc="row 2", status="Disabled")
        ctx = make_ctx([start, end])
        self.assertEqual(run_uar_period_diff_tests(ctx, IdGen()), [])

    def test_unmatched_account_is_ignored(self):
        """Orphan accounts are orphan.py's job, not this check's - an
        unmatched account gaining a new profile between snapshots shouldn't
        also raise a second, differently-typed finding here."""
        emp = make_employee("E1", "Pat", "pat@x.com")
        end = make_access(emp, ["User", "Admin"], snapshot_date=date(2026, 9, 1), loc="row 2")
        end.matched_employee = None
        start_other = make_access(make_employee("E2", "Q", "q@x.com"), ["User"], snapshot_date=date(2026, 6, 1), account_id="A2")
        ctx = make_ctx([end, start_other])
        self.assertEqual(run_uar_period_diff_tests(ctx, IdGen()), [])


if __name__ == "__main__":
    unittest.main()
