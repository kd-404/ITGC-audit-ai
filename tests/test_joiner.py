"""Unit tests for the joiner-provisioning-timeliness rule, using synthetic
data built directly rather than the ACME sample - the ACME sample is
deliberately clean on this check (its legacy tickets predate the feature),
so this is what actually proves the rule fires, and doesn't false-positive
on an unrelated much-later ticket.
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
from itgc.tests_itgc.joiner import run_joiner_provisioning
from itgc.tests_itgc.idgen import IdGen


def make_policy(sla_days=10):
    return Policy(
        applications={"TestERP": ApplicationPolicy(
            name="TestERP", sensitivity="low", profiles=["User"], sod_conflicts=[], role_to_profile={},
        )},
        deprovisioning_sla_days=3, dormant_threshold_days=90,
        joiner_provisioning_sla_days=sla_days,
        company_name="Test Co", policy_reference="TEST-POL-01", sod_policy_reference="TEST-SOD-01",
    )


def make_ctx(employees, tickets, access_records, as_of, sla_days=10):
    bundle = EvidenceBundle(employees=employees, access_records=access_records, tickets=tickets)
    ctx = AuditContext(as_of=as_of, policy=make_policy(sla_days), bundle=bundle)
    ctx.employees_by_email = {e.email.lower(): e for e in employees}
    return ctx


def make_employee(name, email, hire_date, status="Active"):
    return Employee(
        emp_id="E1", full_name=name, email=email, department="Ops", job_title="Analyst",
        manager_email=None, status=status, hire_date=hire_date, term_date=None,
        provenance=Provenance(source_file="x", source_type="employee_master", location="row 1"),
    )


def make_ticket(requester, system, created, implemented):
    return Ticket(
        ticket_id="T1", requester_email=requester, approver_email="mgr@x.com", system=system,
        access_requested="User", status="Closed", created=created, approved=created, implemented=implemented,
        implementer_email="it@x.com", provenance=Provenance(source_file="x", source_type="servicedesk", location="row 1"),
    )


def make_access(system, emp):
    rec = AccessRecord(
        system=system, account_id="A1", account_name=emp.full_name, account_email=emp.email,
        profiles=["User"], account_status="Active", last_login=None,
        provenance=Provenance(source_file="x", source_type="uar_sheet", location="row 1"),
    )
    rec.matched_employee = emp
    return rec


class TestJoinerProvisioning(unittest.TestCase):
    def test_flags_a_genuine_late_onboarding_grant(self):
        emp = make_employee("Late Hire", "late@x.com", date(2026, 1, 1))
        ticket = make_ticket("late@x.com", "TestERP", date(2026, 1, 20), date(2026, 1, 25))  # 24 days after hire
        ctx = make_ctx([emp], [ticket], [make_access("TestERP", emp)], as_of=date(2026, 2, 1), sla_days=10)
        findings = run_joiner_provisioning(ctx, IdGen())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].finding_type.value, "JOINER_PROVISIONING_DELAY")
        self.assertIn("24 days", findings[0].condition)

    def test_does_not_flag_on_time_provisioning(self):
        emp = make_employee("On Time Hire", "ontime@x.com", date(2026, 1, 1))
        ticket = make_ticket("ontime@x.com", "TestERP", date(2025, 12, 28), date(2026, 1, 3))  # 2 days after hire
        ctx = make_ctx([emp], [ticket], [make_access("TestERP", emp)], as_of=date(2026, 2, 1), sla_days=10)
        findings = run_joiner_provisioning(ctx, IdGen())
        self.assertEqual(findings, [])

    def test_does_not_flag_preboarding_provisioning(self):
        """Access set up BEFORE day one is the ideal case, not a violation."""
        emp = make_employee("Prepped Hire", "prepped@x.com", date(2026, 1, 15))
        ticket = make_ticket("prepped@x.com", "TestERP", date(2026, 1, 5), date(2026, 1, 10))  # before hire
        ctx = make_ctx([emp], [ticket], [make_access("TestERP", emp)], as_of=date(2026, 2, 1), sla_days=10)
        findings = run_joiner_provisioning(ctx, IdGen())
        self.assertEqual(findings, [])

    def test_does_not_misattribute_a_much_later_unrelated_ticket(self):
        """A ticket years after hire is a different event (role change, one-off
        need), not delayed onboarding - must not be flagged as a joiner delay."""
        emp = make_employee("Old Timer", "old@x.com", date(2018, 1, 1))
        ticket = make_ticket("old@x.com", "TestERP", date(2026, 1, 1), date(2026, 1, 5))  # ~8 years later
        ctx = make_ctx([emp], [ticket], [make_access("TestERP", emp)], as_of=date(2026, 2, 1), sla_days=10)
        findings = run_joiner_provisioning(ctx, IdGen())
        self.assertEqual(findings, [])

    def test_does_not_flag_terminated_employees(self):
        emp = make_employee("Gone Already", "gone@x.com", date(2026, 1, 1), status="Terminated")
        ticket = make_ticket("gone@x.com", "TestERP", date(2026, 1, 20), date(2026, 1, 25))
        ctx = make_ctx([emp], [ticket], [make_access("TestERP", emp)], as_of=date(2026, 2, 1), sla_days=10)
        findings = run_joiner_provisioning(ctx, IdGen())
        self.assertEqual(findings, [])

    def test_does_not_flag_when_no_ticket_exists(self):
        """No evidence either way is provisioning.py's MISSING_APPROVAL_EVIDENCE
        problem, not this test's - avoid double-flagging the same gap."""
        emp = make_employee("No Ticket", "noticket@x.com", date(2026, 1, 1))
        ctx = make_ctx([emp], [], [make_access("TestERP", emp)], as_of=date(2026, 2, 1), sla_days=10)
        findings = run_joiner_provisioning(ctx, IdGen())
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
