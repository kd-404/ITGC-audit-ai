"""Loads the company's own policy/config (role-access matrix, SoD conflicts,
SLA thresholds) - this is the "criteria" side of every finding: what SHOULD be
true, independent of what the evidence shows."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ApplicationPolicy:
    name: str
    sensitivity: str                       # low | high
    profiles: list[str]
    sod_conflicts: list[tuple[str, str]]
    role_to_profile: dict[str, list[str]]
    privileged_profiles: list[str] = field(default_factory=list)  # profiles requiring periodic re-certification


@dataclass
class Policy:
    applications: dict[str, ApplicationPolicy]
    deprovisioning_sla_days: int
    dormant_threshold_days: int
    joiner_provisioning_sla_days: int
    company_name: str
    policy_reference: str
    sod_policy_reference: str
    privileged_review_cycle_days: int = 90
    backup_restore_test_interval_days: int = 180
    incident_sla_days: dict = field(default_factory=lambda: {"critical": 1, "high": 3, "medium": 5, "low": 10})

    def is_sod_conflict(self, system: str, profiles: list[str]) -> tuple[str, str] | None:
        app = self.applications.get(system)
        if not app:
            return None
        profset = set(profiles)
        for a, b in app.sod_conflicts:
            if a in profset and b in profset:
                return (a, b)
        return None

    def allowed_profiles_for_role(self, system: str, job_title: str | None) -> list[str] | None:
        app = self.applications.get(system)
        if not app or not job_title:
            return None
        return app.role_to_profile.get(job_title)


def load_policy(company_dir: Path) -> Policy:
    company_dir = Path(company_dir)
    with open(company_dir / "role_access_matrix.yaml") as f:
        matrix = yaml.safe_load(f)
    with open(company_dir / "company_context.yaml") as f:
        ctx = yaml.safe_load(f)

    apps = {}
    for name, spec in matrix["applications"].items():
        apps[name] = ApplicationPolicy(
            name=name,
            sensitivity=spec.get("sensitivity", "low"),
            profiles=spec.get("profiles", []),
            sod_conflicts=[tuple(p) for p in spec.get("sod_conflicts", [])],
            role_to_profile=spec.get("role_to_profile", {}),
            privileged_profiles=spec.get("privileged_profiles", []),
        )
    return Policy(
        applications=apps,
        deprovisioning_sla_days=matrix.get("deprovisioning_sla_days", 3),
        dormant_threshold_days=matrix.get("dormant_threshold_days", 90),
        joiner_provisioning_sla_days=matrix.get("joiner_provisioning_sla_days", 10),
        company_name=ctx.get("company", "Unknown"),
        policy_reference=ctx.get("policy_reference", ""),
        sod_policy_reference=ctx.get("sod_policy_reference", ""),
        privileged_review_cycle_days=matrix.get("privileged_review_cycle_days", 90),
        backup_restore_test_interval_days=matrix.get("backup_restore_test_interval_days", 180),
        incident_sla_days={k.lower(): v for k, v in matrix.get(
            "incident_sla_days", {"critical": 1, "high": 3, "medium": 5, "low": 10},
        ).items()},
    )
