import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itgc.models import Employee, Provenance
from itgc.identity.resolve import resolve_person


def make_employee(name, email):
    return Employee(
        emp_id="E1", full_name=name, email=email, department="Finance", job_title="AP Clerk",
        manager_email=None, status="Active", hire_date=None, term_date=None,
        provenance=Provenance(source_file="x", source_type="employee_master", location="row 1"),
    )


class TestIdentityResolution(unittest.TestCase):
    def setUp(self):
        self.employees = [
            make_employee("Jonathan Ito", "jonathan.ito@acme.com"),
            make_employee("Sarah Connor", "sarah.connor@acme.com"),
        ]

    def test_exact_email_match(self):
        emp, conf, method = resolve_person("Some Other Name", "jonathan.ito@acme.com", self.employees)
        self.assertEqual(emp.full_name, "Jonathan Ito")
        self.assertEqual(conf, 1.0)
        self.assertEqual(method, "exact_email")

    def test_fuzzy_name_match_typo_variant(self):
        # "Jonathon" (misspelled) with no email at all - must fall through to fuzzy name matching
        emp, conf, method = resolve_person("Jonathon Ito", None, self.employees)
        self.assertEqual(emp.full_name, "Jonathan Ito")
        self.assertGreater(conf, 0.8)
        self.assertEqual(method, "fuzzy_name")

    def test_name_too_different_does_not_match(self):
        # a genuine nickname/short-form is NOT confidently resolved by name alone -
        # this is a deliberate design choice: below-threshold matches become an
        # enquiry for a human to confirm, rather than a silent guess.
        emp, conf, method = resolve_person("Jon Ito", None, self.employees)
        self.assertIsNone(emp)

    def test_no_match_for_unrelated_person(self):
        emp, conf, method = resolve_person("Totally Different Person", "nobody@external.com", self.employees)
        self.assertIsNone(emp)
        self.assertEqual(conf, 0.0)
        self.assertEqual(method, "unmatched")

    def test_email_localpart_match_on_domain_change(self):
        emp, conf, method = resolve_person(None, "jonathan.ito@old-domain.com", self.employees)
        self.assertEqual(emp.full_name, "Jonathan Ito")
        self.assertEqual(method, "email_localpart")


if __name__ == "__main__":
    unittest.main()
