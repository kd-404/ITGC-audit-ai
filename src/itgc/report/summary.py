"""Plain-text executive summary - what a human reads first, before opening
the workpaper."""
from __future__ import annotations

from ..models import Finding, Enquiry


def build_summary(findings: list[Finding], enquiries: list[Enquiry], engagement_name: str, as_of: str) -> str:
    counts = {}
    for f in findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1

    lines = [
        f"{engagement_name}",
        f"As of: {as_of}",
        "=" * 70,
        f"Findings: {len(findings)}  "
        f"(Critical: {counts.get('Critical', 0)}, High: {counts.get('High', 0)}, "
        f"Medium: {counts.get('Medium', 0)}, Low: {counts.get('Low', 0)})",
        f"Open enquiries: {len(enquiries)} ({sum(1 for e in enquiries if e.blocking)} blocking)",
        "",
    ]
    for f in findings:
        lines.append(f"[{f.finding_id}] {f.severity.value} - {f.finding_type.value} - {f.system} - {f.subject_person or 'unidentified'}")
        lines.append(f"    {f.condition}")
        lines.append(f"    Recommendation: {f.recommendation}")
        lines.append("")
    if enquiries:
        lines.append("-" * 70)
        lines.append("OPEN ENQUIRIES")
        for e in enquiries:
            lines.append(f"[{e.enquiry_id}] ({'BLOCKING' if e.blocking else 'info'}) {e.topic}")
            lines.append(f"    {e.question}")
            if e.answer:
                lines.append(f"    Answer: {e.answer}")
            lines.append("")
    return "\n".join(lines)
