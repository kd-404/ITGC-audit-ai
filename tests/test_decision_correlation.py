"""Unit tests for the email-decision-vs-access-state correlation rule.

Built with synthetic data, the way test_joiner.py is, because this is
specifically what proves the rule fires correctly (and doesn't false-alarm
on greeting/sign-off/quoted-thread text) independent of any one sample
dataset. It was also validated end-to-end against the ACME sample (zero
false positives) and the Meridian/Solstice hard scenarios (see
data/test_scenarios/*/ANSWER_KEY_PRIVATE.md for what it's expected to catch
there) - those aren't re-asserted here since they aren't meant to be
graded by automated tests, but this file locks in the specific bugs found
along the way.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itgc.models import Employee, AccessRecord, EmailEvidence, Provenance
from itgc.policy import Policy, ApplicationPolicy
from itgc.context import AuditContext
from itgc.ingest import EvidenceBundle
from itgc.ingest.fuzzy import name_key
from itgc.tests_itgc.decision_correlation import run_decision_correlation_tests
from itgc.tests_itgc.idgen import IdGen


def make_policy():
    return Policy(
        applications={"TestERP": ApplicationPolicy(
            name="TestERP", sensitivity="high", profiles=["User"], sod_conflicts=[], role_to_profile={},
        )},
        deprovisioning_sla_days=3, dormant_threshold_days=90, joiner_provisioning_sla_days=10,
        company_name="Test Co", policy_reference="TEST-POL-01", sod_policy_reference="TEST-SOD-01",
    )


def make_employee(emp_id, name, email, manager_email=None):
    return Employee(
        emp_id=emp_id, full_name=name, email=email, department="Ops", job_title="Analyst",
        manager_email=manager_email, status="Active", hire_date=date(2020, 1, 1), term_date=None,
        provenance=Provenance(source_file="x", source_type="employee_master", location="row 1"),
    )


def make_access(system, emp, status, source_file="uar.xlsx", last_login=None):
    rec = AccessRecord(
        system=system, account_id=emp.emp_id, account_name=emp.full_name, account_email=emp.email,
        profiles=["User"], account_status=status, last_login=last_login,
        provenance=Provenance(source_file=source_file, source_type="uar_sheet", location="row 1"),
    )
    rec.matched_employee = emp
    return rec


def make_email(sender, body, sent_date, subject="Access review"):
    return EmailEvidence(
        sender=sender, recipient="auditor@x.com", subject=subject, sent_date=sent_date, body=body,
        provenance=Provenance(source_file="email.txt", source_type="email", location="email body"),
    )


def make_ctx(employees, access_records, emails):
    bundle = EvidenceBundle(employees=employees, access_records=access_records, emails=emails)
    ctx = AuditContext(as_of=date(2026, 9, 1), policy=make_policy(), bundle=bundle)
    ctx.employees_by_email = {e.email.lower(): e for e in employees}
    ctx.employees_by_namekey = {}
    for e in employees:
        ctx.employees_by_namekey.setdefault(name_key(e.full_name), []).append(e)
    return ctx


class TestDecisionCorrelation(unittest.TestCase):
    def test_revoke_instruction_not_actioned(self):
        mgr = make_employee("E1", "Mo Manager", "mo@x.com")
        emp = make_employee("E2", "Priya Rao", "priya@x.com", manager_email="mo@x.com")
        access = make_access("TestERP", emp, "Active")
        email = make_email("mo@x.com", "Please revoke Priya Rao's access, she's moved teams.", date(2026, 8, 1))
        ctx = make_ctx([mgr, emp], [access], [email])
        findings, enquiries = run_decision_correlation_tests(ctx, IdGen())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].finding_type.value, "ACCESS_DECISION_NOT_ACTIONED")
        self.assertEqual(findings[0].subject_person, "Priya Rao")
        self.assertEqual(enquiries, [])

    def test_retain_instruction_contradicted_by_later_revoke_wins_on_date(self):
        mgr = make_employee("E1", "Mo Manager", "mo@x.com")
        emp = make_employee("E2", "Priya Rao", "priya@x.com", manager_email="mo@x.com")
        access = make_access("TestERP", emp, "Disabled")
        e1 = make_email("mo@x.com", "Please revoke Priya Rao's access.", date(2026, 8, 1))
        e2 = make_email("mo@x.com", "Correction - Priya Rao should still keep her access, ignore my earlier note.",
                         date(2026, 8, 3))
        ctx = make_ctx([mgr, emp], [access], [e1, e2])
        findings, _ = run_decision_correlation_tests(ctx, IdGen())
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].finding_type.value, "ACCESS_DECISION_CONTRADICTED")
        self.assertIn("most recent instruction", findings[0].condition)

    def test_clean_revoke_produces_no_finding(self):
        mgr = make_employee("E1", "Mo Manager", "mo@x.com")
        emp = make_employee("E2", "Priya Rao", "priya@x.com", manager_email="mo@x.com")
        access = make_access("TestERP", emp, "Disabled")
        email = make_email("mo@x.com", "Please revoke Priya Rao's access, she's moved teams.", date(2026, 8, 1))
        ctx = make_ctx([mgr, emp], [access], [email])
        findings, enquiries = run_decision_correlation_tests(ctx, IdGen())
        self.assertEqual(findings, [])
        self.assertEqual(enquiries, [])

    def test_ambiguous_first_name_raises_enquiry_not_a_guess(self):
        mgr = make_employee("E1", "Mo Manager", "mo@x.com")
        alice1 = make_employee("E2", "Alice Smith", "alice.smith@x.com", manager_email="mo@x.com")
        alice2 = make_employee("E3", "Alice Jones", "alice.jones@x.com", manager_email="mo@x.com")
        access1 = make_access("TestERP", alice1, "Active")
        access2 = make_access("TestERP", alice2, "Active")
        email = make_email("mo@x.com", "Please revoke Alice's access, she's moved teams.", date(2026, 8, 1))
        ctx = make_ctx([mgr, alice1, alice2], [access1, access2], [email])
        findings, enquiries = run_decision_correlation_tests(ctx, IdGen())
        self.assertEqual(findings, [])
        self.assertEqual(len(enquiries), 1)
        self.assertEqual(enquiries[0].topic, "Ambiguous access decision")
        self.assertIn("Alice Smith", enquiries[0].question)
        self.assertIn("Alice Jones", enquiries[0].question)

    def test_ambiguous_name_resolved_by_sender_authority(self):
        mgr1 = make_employee("E1", "Mo Manager", "mo@x.com")
        mgr2 = make_employee("E4", "Jo Manager", "jo@x.com")
        alice1 = make_employee("E2", "Alice Smith", "alice.smith@x.com", manager_email="mo@x.com")
        alice2 = make_employee("E3", "Alice Jones", "alice.jones@x.com", manager_email="jo@x.com")
        access1 = make_access("TestERP", alice1, "Active")
        access2 = make_access("TestERP", alice2, "Active")
        email = make_email("mo@x.com", "Please revoke Alice's access, she's moved teams.", date(2026, 8, 1))
        ctx = make_ctx([mgr1, mgr2, alice1, alice2], [access1, access2], [email])
        findings, enquiries = run_decision_correlation_tests(ctx, IdGen())
        self.assertEqual(enquiries, [])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].subject_person, "Alice Smith")  # mo@x.com's own report

    def test_out_of_authority_instruction_flagged(self):
        real_mgr = make_employee("E1", "Real Manager", "real@x.com")
        other_mgr = make_employee("E4", "Other Manager", "other@x.com")
        emp = make_employee("E2", "Priya Rao", "priya@x.com", manager_email="real@x.com")
        access = make_access("TestERP", emp, "Disabled")
        email = make_email("other@x.com", "Please revoke Priya Rao's access.", date(2026, 8, 1))
        ctx = make_ctx([real_mgr, other_mgr, emp], [access], [email])
        findings, _ = run_decision_correlation_tests(ctx, IdGen())
        types = [f.finding_type.value for f in findings]
        self.assertIn("OUT_OF_AUTHORITY_INSTRUCTION", types)

    def test_greeting_and_signoff_do_not_leak_into_the_instruction(self):
        """Regression test for a real bug: 'Neha,' as a bare salutation (no
        'Hi'/'Hello') and a quoted-thread 'X wrote:' line were both getting
        swept up as if the greeted/quoted person were the subject of an
        unrelated revoke instruction elsewhere in the same email."""
        mgr = make_employee("E1", "Neha Kapoor", "neha@x.com")
        subject_emp = make_employee("E2", "Priya Rao", "priya@x.com", manager_email="mo@x.com")
        other_mgr = make_employee("E3", "Mo Manager", "mo@x.com")
        access = make_access("TestERP", subject_emp, "Active")
        body = (
            "Neha,\n\n"
            "For my side - please go ahead and revoke Priya Rao's access, she's moved teams.\n\n"
            "> On 01-Aug-2026, Neha Kapoor wrote:\n"
            "> please review everyone's access\n\n"
            "Thanks,\nMo"
        )
        email = make_email("mo@x.com", body, date(2026, 8, 1))
        ctx = make_ctx([mgr, subject_emp, other_mgr], [access], [email])
        findings, _ = run_decision_correlation_tests(ctx, IdGen())
        subjects = {f.subject_person for f in findings}
        self.assertNotIn("Neha Kapoor", subjects)
        self.assertIn("Priya Rao", subjects)

    def test_before_after_snapshot_pair_does_not_mask_a_correct_revoke(self):
        """Regression test for a real bug: merging a stale 'before' snapshot
        and a current 'after' snapshot of the same system made a correctly
        revoked account look untouched, because the older Active record was
        still sitting in the same (employee, system) group."""
        mgr = make_employee("E1", "Mo Manager", "mo@x.com")
        emp = make_employee("E2", "Priya Rao", "priya@x.com", manager_email="mo@x.com")
        before = make_access("TestERP", emp, "Active", source_file="access_before_audit.xlsx",
                              last_login=date(2026, 7, 1))
        after = make_access("TestERP", emp, "Disabled", source_file="access_after_audit.xlsx",
                             last_login=date(2026, 7, 1))  # same last_login on purpose
        email = make_email("mo@x.com", "Please revoke Priya Rao's access, she's moved teams.", date(2026, 8, 1))
        ctx = make_ctx([mgr, emp], [before, after], [email])
        findings, _ = run_decision_correlation_tests(ctx, IdGen())
        self.assertEqual(findings, [])  # correctly revoked - no finding


if __name__ == "__main__":
    unittest.main()
