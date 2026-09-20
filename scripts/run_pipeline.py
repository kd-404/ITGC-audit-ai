#!/usr/bin/env python3
"""Run the ITGC audit pipeline against the ACME sample evidence (or any
company/evidence folder pair) and write the workpaper + summary + JSON to
outputs/.

Usage:
    python3 scripts/run_pipeline.py
    python3 scripts/run_pipeline.py --company data/company --evidence data/evidence --out outputs
    python3 scripts/run_pipeline.py --no-llm
"""
import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from itgc.pipeline import run_pipeline  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", default=str(ROOT / "data" / "company"))
    ap.add_argument("--evidence", default=str(ROOT / "data" / "evidence"))
    ap.add_argument("--out", default=str(ROOT / "outputs"))
    ap.add_argument("--as-of", default="2026-09-15")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--answers", default=str(ROOT / "data" / "answers.yaml"))
    args = ap.parse_args()

    as_of = date.fromisoformat(args.as_of)
    result = run_pipeline(
        company_dir=Path(args.company), evidence_dir=Path(args.evidence), output_dir=Path(args.out),
        as_of=as_of, use_llm=not args.no_llm,
        answers_path=Path(args.answers) if Path(args.answers).exists() else None,
    )

    print(f"LLM narrative source: {result['llm_status']}")
    print(f"Findings: {len(result['findings'])}  |  Enquiries: {len(result['enquiries'])}")
    print(f"Workpaper: {result['workpaper_path']}")
    print(f"Summary:   {result['summary_path']}")
    print(f"JSON:      {result['findings_json_path']}")


if __name__ == "__main__":
    main()
