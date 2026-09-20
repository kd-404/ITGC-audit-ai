"""Unit tests for cross-finding correlation (correlation.py): grouping
findings that share a subject into a single "this account was flagged by
N independent controls" case, built with synthetic data.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from itgc.models import Finding, FindingType, Severity, Provenance
from itgc.evidence_map import EvidenceCase
from itgc.correlation import build_correlated_cases
from itgc.llm.gateway import fallback_correlation_narrative


def make_finding(finding_id, finding_type, severity, system="TestERP", subject_email="pat@x.com"):
    return Finding(
        finding_id=finding_id, finding_type=finding_type, severity=severity, system=system,
        subject_person="Pat Admin", subject_email=subject_email,
        condition="c", criteria="k", cause="ca", effect="e", recommendation="r",
        evidence=["x.csv (row 1)"], confidence=0.9,
    )


def make_case(case_id, related_finding_ids, subject_label="Pat Admin", subject_email="pat@x.com"):
    return EvidenceCase(
        case_id=case_id, subject_label=subject_label, subject_email=subject_email, resolved=True,
        related_finding_ids=related_finding_ids,
    )


class TestCorrelation(unittest.TestCase):
    def test_single_finding_case_not_correlated(self):
        f1 = make_finding("FND-001", FindingType.DORMANT_ACCOUNT_NOT_REVIEWED, Severity.MEDIUM)
        case = make_case("EMP:E1", ["FND-001"])
        correlated = build_correlated_cases([case], [f1])
        self.assertEqual(correlated, [])

    def test_two_findings_same_subject_correlated(self):
        f1 = make_finding("FND-001", FindingType.DORMANT_ACCOUNT_NOT_REVIEWED, Severity.MEDIUM)
        f2 = make_finding("FND-002", FindingType.MISSING_APPROVAL_EVIDENCE, Severity.HIGH)
        case = make_case("EMP:E1", ["FND-001", "FND-002"])
        correlated = build_correlated_cases([case], [f1, f2])
        self.assertEqual(len(correlated), 1)
        c = correlated[0]
        self.assertEqual(set(c.finding_ids), {"FND-001", "FND-002"})
        self.assertEqual(c.combined_severity, Severity.HIGH)

    def test_findings_from_different_domains_both_listed(self):
        f1 = make_finding("FND-001", FindingType.DORMANT_ACCOUNT_NOT_REVIEWED, Severity.MEDIUM)
        f2 = make_finding("FND-002", FindingType.PRIVILEGED_ACCESS_NEVER_REVIEWED, Severity.HIGH)
        case = make_case("EMP:E1", ["FND-001", "FND-002"])
        correlated = build_correlated_cases([case], [f1, f2])
        c = correlated[0]
        self.assertIn("access_review", c.control_domains)
        self.assertIn("privileged_access", c.control_domains)

    def test_combined_severity_is_the_max_not_the_first(self):
        f1 = make_finding("FND-001", FindingType.DORMANT_ACCOUNT_NOT_REVIEWED, Severity.LOW)
        f2 = make_finding("FND-002", FindingType.PRIVILEGED_ACCESS_SELF_REVIEWED, Severity.CRITICAL)
        case = make_case("EMP:E1", ["FND-001", "FND-002"])
        correlated = build_correlated_cases([case], [f1, f2])
        self.assertEqual(correlated[0].combined_severity, Severity.CRITICAL)

    def test_more_domains_sort_first(self):
        # case A: 2 findings, 2 domains. case B: 3 findings, 1 domain.
        fa1 = make_finding("FND-A1", FindingType.DORMANT_ACCOUNT_NOT_REVIEWED, Severity.MEDIUM, subject_email="a@x.com")
        fa2 = make_finding("FND-A2", FindingType.PRIVILEGED_ACCESS_SELF_REVIEWED, Severity.MEDIUM, subject_email="a@x.com")
        case_a = make_case("EMP:A", ["FND-A1", "FND-A2"], subject_label="A", subject_email="a@x.com")

        fb1 = make_finding("FND-B1", FindingType.EXCESS_ACCESS_UNEXPECTED_ROLE, Severity.CRITICAL, subject_email="b@x.com")
        fb2 = make_finding("FND-B2", FindingType.SOD_VIOLATION_ACCESS, Severity.CRITICAL, subject_email="b@x.com")
        fb3 = make_finding("FND-B3", FindingType.DORMANT_ACCOUNT_NOT_REVIEWED, Severity.CRITICAL, subject_email="b@x.com")
        case_b = make_case("EMP:B", ["FND-B1", "FND-B2", "FND-B3"], subject_label="B", subject_email="b@x.com")

        correlated = build_correlated_cases([case_a, case_b], [fa1, fa2, fb1, fb2, fb3])
        self.assertEqual(correlated[0].case_id, "EMP:A")  # 2 domains beats 3 findings in 1 domain

    def test_findings_not_in_the_findings_list_are_ignored(self):
        """If a related_finding_id doesn't resolve (stale reference), it
        shouldn't count toward the 2+ threshold or crash."""
        f1 = make_finding("FND-001", FindingType.DORMANT_ACCOUNT_NOT_REVIEWED, Severity.MEDIUM)
        case = make_case("EMP:E1", ["FND-001", "FND-999-DOES-NOT-EXIST"])
        correlated = build_correlated_cases([case], [f1])
        self.assertEqual(correlated, [])


class TestFallbackCorrelationNarrative(unittest.TestCase):
    def test_mentions_subject_and_finding_count(self):
        f1 = make_finding("FND-001", FindingType.DORMANT_ACCOUNT_NOT_REVIEWED, Severity.MEDIUM)
        f2 = make_finding("FND-002", FindingType.MISSING_APPROVAL_EVIDENCE, Severity.HIGH)
        narrative = fallback_correlation_narrative("Pat Admin", [f1, f2])
        self.assertIn("Pat Admin", narrative)
        self.assertIn("2 independent finding", narrative)


if __name__ == "__main__":
    unittest.main()
