"""ITGC test domains: Backup & Recovery and Incident Management.

Two distinct control areas that share a module because they're usually
evidenced by similar log-style exports (BACKUP_JOB_SCHEMA and
INCIDENT_SCHEMA in ingest/schemas.py); the rules below are independent of
each other and exposed as two separate functions/control_registry domains
so a person can check one without the other.

Backup & Recovery (run_backup_tests):
  BACKUP_JOB_FAILURE_UNRESOLVED
      A backup job's status is failure/error with no later successful job
      for the same system on record.
  BACKUP_NEVER_VERIFIED
      A system's backup jobs all report success, but none of them was ever
      independently verified (verified_by/verification_date on file) -
      "the job ran" isn't the same control as "someone confirmed the
      backup is restorable."
  BACKUP_RESTORE_NEVER_TESTED
      No restore-test job (job_type "restore_test") with a verification on
      record exists for a system within Policy.backup_restore_test_interval_days
      of the as-of date.

Incident Management (run_incident_tests):
  INCIDENT_SLA_BREACH
      resolved_date - reported_date exceeds Policy.incident_sla_days for the
      incident's severity (same shape as jml.py's deprovisioning SLA check,
      applied to a different domain).
  INCIDENT_MISSING_ROOT_CAUSE
      A closed/resolved incident has no root_cause on file.
  INCIDENT_RECURRING_UNADDRESSED (portfolio-level, moderate confidence)
      Two incidents against the same system with similar descriptions
      (fuzzy match), with no change record deployed to that system between
      them - i.e. nothing on record actually fixed the underlying issue
      before it recurred. This is a correlation signal, not a proven
      violation, so it's raised at lower confidence than the other checks
      here.

As with every other ITGC test module, none of this goes through the LLM -
the verdict is entirely rule-based; only the narrative explanation attached
later (AIGateway.narrate_all) is LLM-produced.
"""
from __future__ import annotations

from ..models import Finding, FindingType, Severity
from .idgen import IdGen
from ..ingest.fuzzy import ratio

FAILURE_STATES = {"failure", "failed", "error"}
SUCCESS_STATES = {"success", "successful", "completed", "ok", "passed"}
CLOSED_INCIDENT_STATES = {"closed", "resolved"}
SEVERITY_MAP = {"critical": Severity.CRITICAL, "high": Severity.HIGH, "medium": Severity.MEDIUM, "low": Severity.LOW}
RECURRING_SIMILARITY_THRESHOLD = 0.6


def run_backup_tests(ctx, ids: IdGen) -> list[Finding]:
    findings: list[Finding] = []

    by_system: dict[str, list] = {}
    for j in ctx.bundle.backup_jobs:
        by_system.setdefault(j.system, []).append(j)

    for system, jobs in by_system.items():
        backup_jobs = [j for j in jobs if j.job_type != "restore_test"]
        restore_jobs = [j for j in jobs if j.job_type == "restore_test"]
        dated_backup_jobs = sorted((j for j in backup_jobs if j.scheduled_time), key=lambda j: j.scheduled_time)

        # --- BACKUP_JOB_FAILURE_UNRESOLVED ---
        for i, j in enumerate(dated_backup_jobs):
            if j.status.strip().lower() not in FAILURE_STATES:
                continue
            later_success = any(
                later.scheduled_time > j.scheduled_time and later.status.strip().lower() in SUCCESS_STATES
                for later in dated_backup_jobs[i + 1:]
            )
            if later_success:
                continue
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.BACKUP_JOB_FAILURE_UNRESOLVED,
                severity=Severity.HIGH,
                system=system,
                subject_person=None,
                subject_email=None,
                condition=f"Backup job {j.job_id} for {system} failed on {j.scheduled_time.isoformat()} "
                          f"(status: {j.status}), with no later successful backup job on record for this system.",
                criteria=f"{ctx.policy.policy_reference}: a failed backup job must be rerun and completed "
                         f"successfully; a failure must not be the last recorded state for a system's backups.",
                cause="The failed job was not rerun, or a rerun occurred without being logged/exported.",
                effect="Without a confirmed successful backup after this failure, the system may have no "
                       "recoverable backup for the period since the failure, risking permanent data loss on "
                       "top of whatever caused the outage.",
                recommendation=f"Confirm whether {system} has a successful backup since "
                               f"{j.scheduled_time.isoformat()}; if not, run one immediately and investigate "
                               f"why the failure was not rerun or escalated.",
                evidence=[j.provenance.cite()],
                confidence=0.9,
            ))

        # --- BACKUP_NEVER_VERIFIED ---
        success_jobs = [j for j in backup_jobs if j.status.strip().lower() in SUCCESS_STATES]
        if success_jobs and not any(j.verified_by and j.verification_date for j in success_jobs):
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.BACKUP_NEVER_VERIFIED,
                severity=Severity.MEDIUM,
                system=system,
                subject_person=None,
                subject_email=None,
                condition=f"{system} has {len(success_jobs)} backup job(s) reporting success, but none has a "
                          f"verification (verified_by/verification_date) on record.",
                criteria=f"{ctx.policy.policy_reference}: a successful backup job status is not sufficient "
                         f"evidence on its own - completed backups must be independently verified.",
                cause="The backup process reports job status automatically but has no separate verification "
                      "step, or verification occurs without being logged.",
                effect="\"The job ran\" is not the same control as \"the backup is restorable\" - an "
                       "unverified backup may be corrupt, incomplete, or unusable, and this would not be "
                       "discovered until an actual restore is needed.",
                recommendation=f"Introduce (or start logging) an independent verification step for {system}'s "
                               f"backups, distinct from the job's own reported status.",
                evidence=[j.provenance.cite() for j in success_jobs],
                confidence=0.8,
            ))

        # --- BACKUP_RESTORE_NEVER_TESTED ---
        latest_restore_verification = max(
            (j.verification_date for j in restore_jobs if j.verification_date), default=None,
        )
        interval = ctx.policy.backup_restore_test_interval_days
        if latest_restore_verification is None or (ctx.as_of - latest_restore_verification).days > interval:
            age_note = (
                "no restore test has ever been recorded" if latest_restore_verification is None
                else f"the most recent verified restore test was {(ctx.as_of - latest_restore_verification).days} "
                     f"days ago, beyond the {interval}-day required interval"
            )
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.BACKUP_RESTORE_NEVER_TESTED,
                severity=Severity.HIGH,
                system=system,
                subject_person=None,
                subject_email=None,
                condition=f"{system}: {age_note}.",
                criteria=f"{ctx.policy.policy_reference}: restore capability must be tested and verified at "
                         f"least every {interval} days, independent of routine backup job status.",
                cause="No restore-test evidence was captured for this system, or restore tests occur without "
                      "being logged as their own job type.",
                effect="An untested restore path is unproven - the organization may only discover it doesn't "
                       "work at the moment of an actual disaster, when it is too late to fix.",
                recommendation=f"Schedule and document a restore test for {system} within the required "
                               f"interval, and log it as its own evidenced job.",
                evidence=[j.provenance.cite() for j in restore_jobs] or [f"no restore-test evidence found for {system}"],
                confidence=0.75,
            ))

    return findings


def run_incident_tests(ctx, ids: IdGen) -> list[Finding]:
    findings: list[Finding] = []

    for inc in ctx.bundle.incidents:
        sla_days = ctx.policy.incident_sla_days.get(inc.severity.strip().lower())
        finding_severity = SEVERITY_MAP.get(inc.severity.strip().lower(), Severity.MEDIUM)

        # --- INCIDENT_SLA_BREACH ---
        if sla_days is not None and inc.reported_date and inc.resolved_date:
            elapsed = (inc.resolved_date - inc.reported_date).days
            if elapsed > sla_days:
                findings.append(Finding(
                    finding_id=ids.next("FND"),
                    finding_type=FindingType.INCIDENT_SLA_BREACH,
                    severity=finding_severity,
                    system=inc.system,
                    subject_person=None,
                    subject_email=None,
                    condition=f"Incident {inc.incident_id} ({inc.severity}) in {inc.system} took {elapsed} days "
                              f"to resolve ({inc.reported_date.isoformat()} to {inc.resolved_date.isoformat()}), "
                              f"exceeding the {sla_days}-day SLA for {inc.severity} incidents.",
                    criteria=f"{ctx.policy.policy_reference}: incidents must be resolved within the SLA defined "
                             f"for their severity ({sla_days} days for {inc.severity}).",
                    cause="The incident was not resolved within the required timeframe, or the SLA clock was "
                          "not actively managed.",
                    effect="A prolonged unresolved incident extends the window of exposure to whatever risk "
                           "the incident represents, and undermines confidence in the incident process.",
                    recommendation="Review why this incident exceeded its SLA and reinforce SLA tracking/"
                                   "escalation for incidents on this system.",
                    evidence=[inc.provenance.cite()],
                    confidence=0.9,
                ))

        # --- INCIDENT_MISSING_ROOT_CAUSE ---
        if inc.status.strip().lower() in CLOSED_INCIDENT_STATES and not (inc.root_cause and inc.root_cause.strip()):
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.INCIDENT_MISSING_ROOT_CAUSE,
                severity=Severity.MEDIUM,
                system=inc.system,
                subject_person=None,
                subject_email=None,
                condition=f"Incident {inc.incident_id} in {inc.system} is {inc.status} with no root cause "
                          f"recorded.",
                criteria=f"{ctx.policy.policy_reference}: a closed incident must document its root cause.",
                cause="The incident was closed without a documented root-cause analysis, or the analysis "
                      "occurred without being logged.",
                effect="Without a documented root cause, there is no evidence the underlying issue was "
                       "actually addressed, and no way to confirm it won't recur.",
                recommendation="Obtain and document the root cause for this incident before considering it "
                               "fully closed.",
                evidence=[inc.provenance.cite()],
                confidence=0.85,
            ))

    # --- INCIDENT_RECURRING_UNADDRESSED (portfolio-level, cross-referenced against change records) ---
    by_system: dict[str, list] = {}
    for inc in ctx.bundle.incidents:
        if inc.reported_date:
            by_system.setdefault(inc.system, []).append(inc)
    for system, incidents in by_system.items():
        incidents = sorted(incidents, key=lambda i: i.reported_date)
        system_changes = [c for c in ctx.bundle.change_records if c.system == system and c.deployed_date]
        for earlier, later in zip(incidents, incidents[1:]):
            if not earlier.description or not later.description:
                continue
            similarity = ratio(earlier.description, later.description)
            if similarity < RECURRING_SIMILARITY_THRESHOLD:
                continue
            fix_in_between = any(
                earlier.reported_date < c.deployed_date < later.reported_date for c in system_changes
            )
            if fix_in_between:
                continue
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.INCIDENT_RECURRING_UNADDRESSED,
                severity=Severity.MEDIUM,
                system=system,
                subject_person=None,
                subject_email=None,
                condition=f"Incident {later.incident_id} in {system} ({later.reported_date.isoformat()}) has a "
                          f"description similar to earlier incident {earlier.incident_id} "
                          f"({earlier.reported_date.isoformat()}), with no change record deployed to {system} "
                          f"in between - nothing on record fixed the underlying issue before it recurred.",
                criteria=f"{ctx.policy.policy_reference}: a recurring incident of the same nature should be "
                         f"linked to a remediating change; unaddressed recurrence indicates the root cause was "
                         f"not actually resolved.",
                cause="The earlier incident's fix (if any) was not implemented as a documented change, or the "
                      "root cause was misdiagnosed and the same issue recurred.",
                effect="A recurring, unaddressed issue represents an unmanaged risk that keeps re-manifesting "
                       "and consuming incident-response effort without resolution.",
                recommendation=f"Confirm whether {earlier.incident_id} and {later.incident_id} share a root "
                               f"cause; if so, raise a change to address it rather than continuing to treat "
                               f"each recurrence as a new incident.",
                evidence=[earlier.provenance.cite(), later.provenance.cite()],
                confidence=0.55,
            ))

    return findings


def run_backup_incident_tests(ctx, ids: IdGen) -> list[Finding]:
    """Combined convenience wrapper kept for callers that want both domains
    at once; control_registry/pipeline.py call run_backup_tests and
    run_incident_tests directly so they can be selected independently."""
    return run_backup_tests(ctx, ids) + run_incident_tests(ctx, ids)
