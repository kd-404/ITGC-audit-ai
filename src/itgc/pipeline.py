"""End-to-end pipeline: point it at a company folder + an evidence folder and
get back findings, enquiries, and workpaper/summary outputs.

    python3 scripts/run_pipeline.py

is the CLI entry point; this module is what it (and the scoring script, and
eventually a UI) calls into.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .context import build_context
from .tests_itgc import run_all_tests, IdGen, SEVERITY_ORDER
from .tests_itgc.decision_correlation import run_decision_correlation_tests
from .tests_itgc.change_management import run_change_management_tests
from .tests_itgc.privileged_access import run_privileged_access_tests
from .tests_itgc.backup_incident import run_backup_tests, run_incident_tests
from .control_registry import resolve_selected_controls
from .enquiry import build_enquiries, load_answers, apply_answers
from .report import build_workpaper, build_summary, build_pdf_report
from .llm import AIGateway, fallback_correlation_narrative
from .evidence_map import build_evidence_map, evidence_map_to_json
from .correlation import build_correlated_cases, correlated_cases_to_json


def _finding_to_json(f) -> dict:
    d = asdict(f)
    d["finding_type"] = f.finding_type.value
    d["severity"] = f.severity.value
    return d


def _enquiry_to_json(e) -> dict:
    return asdict(e)


def run_pipeline(company_dir: Path, evidence_dir: Path, output_dir: Path,
                  as_of: date, use_llm: bool = True, answers_path: Path | None = None,
                  selected_controls: list[str] | None = None) -> dict:
    """`selected_controls` is a list of control_registry control_ids (see
    control_registry.list_controls()); None or empty runs every control
    domain, which is the pre-existing default behavior."""
    company_dir, evidence_dir, output_dir = Path(company_dir), Path(evidence_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    domains = resolve_selected_controls(selected_controls)

    ctx = build_context(company_dir, evidence_dir, as_of=as_of)
    ids = IdGen()

    findings = run_all_tests(ctx, ids, domains)

    dc_enquiries: list = []
    if "decision_correlation" in domains:
        dc_findings, dc_enquiries = run_decision_correlation_tests(ctx, ids)
        findings += dc_findings

    if "change_management" in domains:
        findings += run_change_management_tests(ctx, ids)

    pam_enquiries: list = []
    if "privileged_access" in domains:
        pam_findings, pam_enquiries = run_privileged_access_tests(ctx, ids)
        findings += pam_findings

    if "backup_recovery" in domains:
        findings += run_backup_tests(ctx, ids)

    if "incident_management" in domains:
        findings += run_incident_tests(ctx, ids)

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.system, f.subject_person or ""))

    enquiries = build_enquiries(ctx, ids)
    enquiries += dc_enquiries + pam_enquiries
    if answers_path:
        apply_answers(enquiries, load_answers(answers_path))

    gateway = None
    if use_llm:
        gateway = AIGateway()
        gateway.narrate_all(findings)
        llm_status = "ollama" if gateway.available() else "fallback_template (ollama unreachable)"
    else:
        llm_status = "disabled"

    engagement_name = f"{ctx.policy.company_name} - ITGC User Access Review - {as_of.isoformat()}"

    workpaper_path = build_workpaper(
        output_dir / "ITGC_UAR_Workpaper.xlsx", findings, enquiries,
        ctx.bundle.file_classifications, engagement_name, as_of.isoformat(),
    )
    summary_text = build_summary(findings, enquiries, engagement_name, as_of.isoformat())
    (output_dir / "summary.txt").write_text(summary_text)

    findings_json = [_finding_to_json(f) for f in findings]
    enquiries_json = [_enquiry_to_json(e) for e in enquiries]
    (output_dir / "findings.json").write_text(json.dumps(findings_json, indent=2, default=str))
    (output_dir / "enquiries.json").write_text(json.dumps(enquiries_json, indent=2, default=str))

    evidence_cases = build_evidence_map(ctx, findings, enquiries)
    evidence_map_json = evidence_map_to_json(evidence_cases)
    (output_dir / "evidence_map.json").write_text(json.dumps(evidence_map_json, indent=2, default=str))

    correlated_cases = build_correlated_cases(evidence_cases, findings)
    findings_by_id = {f.finding_id: f for f in findings}
    if gateway is not None:
        gateway.narrate_correlations(correlated_cases, findings_by_id)
    else:
        for c in correlated_cases:
            case_findings = [findings_by_id[fid] for fid in c.finding_ids if fid in findings_by_id]
            c.narrative = fallback_correlation_narrative(c.subject_label, case_findings)
    correlated_cases_json = correlated_cases_to_json(correlated_cases)
    (output_dir / "correlated_cases.json").write_text(json.dumps(correlated_cases_json, indent=2, default=str))

    (output_dir / "controls_run.json").write_text(json.dumps(sorted(domains), indent=2))

    pdf_report_path = build_pdf_report(
        output_dir / "ITGC_Audit_Report.pdf", findings, enquiries, correlated_cases,
        ctx.bundle.file_classifications, engagement_name, as_of.isoformat(), llm_status,
    )

    return {
        "ctx": ctx,
        "findings": findings,
        "enquiries": enquiries,
        "evidence_cases": evidence_cases,
        "correlated_cases": correlated_cases,
        "workpaper_path": workpaper_path,
        "summary_path": output_dir / "summary.txt",
        "findings_json_path": output_dir / "findings.json",
        "evidence_map_json_path": output_dir / "evidence_map.json",
        "pdf_report_path": pdf_report_path,
        "llm_status": llm_status,
        "controls_run": sorted(domains),
    }
