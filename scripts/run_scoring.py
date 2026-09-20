#!/usr/bin/env python3
"""Scores the pipeline's findings.json against the hidden ground truth
(data/ground_truth/planted_issues.yaml) - this file is NEVER read by the
pipeline itself, only by this script, so the score is an honest measure of
detection, not a lookup.

Matching a finding to a ground-truth issue: same finding_type (or, for
JML_TERMINATED_ACTIVE_ACCOUNT paired with MISSING_DEPROVISIONING_RECORD,
either counts for GT issues of that type), same system, and same person
(by email, or by name if email is absent, e.g. an orphan account).
"""
import sys
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_findings(path: Path):
    with open(path) as f:
        return json.load(f)


def load_ground_truth(path: Path):
    with open(path) as f:
        return yaml.safe_load(f)["issues"]


def matches(gt: dict, finding: dict) -> bool:
    if gt["type"] == "CLEAN_TIMELY_DEPROVISIONING":
        return False  # negative control - matched separately
    if finding["finding_type"] != gt["type"]:
        return False
    if finding["system"] != gt["system"]:
        return False
    subj = (finding.get("subject_email") or finding.get("subject_person") or "").lower()
    gt_subj = (gt.get("email") or gt.get("person") or "").lower()
    return gt_subj in subj or subj in gt_subj or gt.get("person", "").lower() in (finding.get("subject_person") or "").lower()


def main():
    findings_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "outputs" / "findings.json"
    gt_path = ROOT / "data" / "ground_truth" / "planted_issues.yaml"

    findings = load_findings(findings_path)
    issues = load_ground_truth(gt_path)

    real_issues = [i for i in issues if i["type"] != "CLEAN_TIMELY_DEPROVISIONING"]
    negative_controls = [i for i in issues if i["type"] == "CLEAN_TIMELY_DEPROVISIONING"]

    matched_findings_idx = set()
    hits, misses = [], []
    for gt in real_issues:
        found = False
        for idx, f in enumerate(findings):
            if idx in matched_findings_idx:
                continue
            if matches(gt, f):
                hits.append((gt, f))
                matched_findings_idx.add(idx)
                found = True
                break
        if not found:
            misses.append(gt)

    unexplained = [f for idx, f in enumerate(findings) if idx not in matched_findings_idx]

    # negative control check: did we wrongly raise a finding for the clean case?
    negative_hits = []
    for nc in negative_controls:
        for f in findings:
            subj = (f.get("subject_email") or f.get("subject_person") or "").lower()
            if nc.get("email", "").lower() in subj and f["system"] == nc["system"]:
                negative_hits.append((nc, f))

    recall = len(hits) / len(real_issues) if real_issues else 1.0
    precision = len(hits) / (len(hits) + len(unexplained)) if (hits or unexplained) else 1.0

    print(f"Planted issues (excluding negative controls): {len(real_issues)}")
    print(f"Findings raised by pipeline: {len(findings)}")
    print(f"True positives (matched a planted issue): {len(hits)}")
    print(f"Missed planted issues (false negatives): {len(misses)}")
    print(f"Unexplained findings (not matched to any planted issue - possible false positives): {len(unexplained)}")
    print(f"Negative control false alarms: {len(negative_hits)} (should be 0)")
    print(f"\nRECALL:    {recall:.0%}")
    print(f"PRECISION: {precision:.0%}")

    if misses:
        print("\n--- MISSED (false negatives) ---")
        for gt in misses:
            print(f"  {gt['id']} [{gt['type']}] {gt['system']} {gt['person']}: {gt['detail']}")

    if unexplained:
        print("\n--- UNEXPLAINED FINDINGS (check these) ---")
        for f in unexplained:
            print(f"  [{f['finding_type']}] {f['system']} {f.get('subject_person')}: {f['condition'][:120]}")

    if negative_hits:
        print("\n--- FALSE ALARMS ON NEGATIVE CONTROLS ---")
        for nc, f in negative_hits:
            print(f"  {nc['id']}: {f['condition'][:120]}")

    print("\n--- MATCHED (true positives) ---")
    for gt, f in hits:
        print(f"  {gt['id']} -> {f['finding_id']} [{f['severity']}] {f['finding_type']}")


if __name__ == "__main__":
    main()
