"""End-to-end regression test: runs the full pipeline against the ACME sample
evidence and checks it against the hidden ground truth, the same way
scripts/run_scoring.py does. This is the test that would catch a regression
in any test rule silently breaking detection.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml

from itgc.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]


def _matches(gt: dict, f) -> bool:
    """A ground-truth issue matches a finding on type + system, and then
    either: the GT issue is a system-level finding (person: "N/A..." with no
    email), in which case the finding must likewise carry no subject person,
    or the GT person's name must appear in the finding's subject_person."""
    if f.finding_type.value != gt["type"] or f.system != gt["system"]:
        return False
    if gt.get("person", "").startswith("N/A"):
        return not f.subject_person
    return gt["person"].lower() in (f.subject_person or "").lower()


class TestPipelineEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = run_pipeline(
            company_dir=ROOT / "data" / "company",
            evidence_dir=ROOT / "data" / "evidence",
            output_dir=Path("/tmp/_itgc_test_output"),
            as_of=date(2026, 9, 15),
            use_llm=False,
        )
        with open(ROOT / "data" / "ground_truth" / "planted_issues.yaml") as f:
            cls.ground_truth = yaml.safe_load(f)["issues"]

    def test_workpaper_and_summary_are_produced(self):
        self.assertTrue(self.result["workpaper_path"].exists())
        self.assertTrue(self.result["summary_path"].exists())

    def test_finds_every_planted_issue(self):
        findings = self.result["findings"]
        real_issues = [i for i in self.ground_truth if i["type"] != "CLEAN_TIMELY_DEPROVISIONING"]
        for gt in real_issues:
            match = [f for f in findings if _matches(gt, f)]
            self.assertTrue(match, f"Missed planted issue {gt['id']}: {gt['detail']}")

    def test_no_false_alarm_on_clean_negative_control(self):
        findings = self.result["findings"]
        clean = next(i for i in self.ground_truth if i["type"] == "CLEAN_TIMELY_DEPROVISIONING")
        false_alarms = [f for f in findings if clean["email"].lower() == (f.subject_email or "").lower()]
        self.assertEqual(false_alarms, [], "Pipeline raised a finding on the clean/negative control case")

    def test_no_unexplained_findings(self):
        """Every finding the pipeline raises should trace to a planted issue -
        i.e. precision should be 100% on this known dataset."""
        findings = self.result["findings"]
        real_issues = [i for i in self.ground_truth if i["type"] != "CLEAN_TIMELY_DEPROVISIONING"]

        def explained(f):
            return any(_matches(gt, f) for gt in real_issues)
        unexplained = [f for f in findings if not explained(f)]
        self.assertEqual(unexplained, [], f"Unexplained findings: {[f.finding_id for f in unexplained]}")

    def test_orphan_account_still_produces_enquiry(self):
        topics = [e.topic for e in self.result["enquiries"]]
        self.assertIn("Unidentified account owner", topics)


if __name__ == "__main__":
    unittest.main()
