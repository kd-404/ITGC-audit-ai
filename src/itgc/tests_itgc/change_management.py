"""ITGC test domain: Change Management.

Operates on ChangeRecord evidence (see CHANGE_RECORD_SCHEMA in
ingest/schemas.py) the same way provisioning.py operates on Ticket evidence -
deterministic checks against fields that are either present/absent or in the
wrong order, with no LLM involved in the verdict.

Checks implemented:

  CHANGE_UNAPPROVED_DEPLOYMENT
      A change was deployed with no approver on record, or deployed_date is
      before approved_date - mirrors provisioning.py's
      APPROVAL_AFTER_IMPLEMENTATION pattern for tickets.

  CHANGE_SOD_DEVELOPER_IS_DEPLOYER
      Same person recorded as both developer and deployer for the same
      change, with no independent release step.

  CHANGE_MISSING_TEST_EVIDENCE
      A change to a production environment has no test_evidence_ref, unless
      it's an emergency change (which is judged under
      CHANGE_EMERGENCY_NOT_RETROACTIVELY_REVIEWED instead - emergency
      changes are expected to skip pre-deployment testing evidence by
      nature, not silently double-flagged for it).

  CHANGE_EMERGENCY_NOT_RETROACTIVELY_REVIEWED
      An emergency change has no post_review_date/post_reviewed_by recorded
      within EMERGENCY_REVIEW_SLA_DAYS of deployment - emergency changes
      skip pre-approval by design, but a well-controlled process still
      requires a documented after-the-fact review within a defined window.

  CHANGE_MISSING_CAB_APPROVAL
      For a change to a high-sensitivity system, the approver on record
      does not hold a CAB/change-board-eligible role (job title hint) -
      mirrors provisioning.py's "sensitive system requires an
      approver-eligible role" pattern, applied to change approval instead
      of access approval.

As with every other ITGC test module, this is not run through the LLM - the
verdict is entirely rule-based; only the narrative explanation attached
later (AIGateway.narrate_all) is LLM-produced.
"""
from __future__ import annotations

from ..models import Finding, FindingType, Severity
from .idgen import IdGen

CAB_APPROVER_ROLE_HINTS = ["change", "cab", "board", "release manager", "it manager", "director", "head"]
EMERGENCY_REVIEW_SLA_DAYS = 5


def _display_person(ctx, email: str | None) -> str:
    emp = ctx.employees_by_email.get((email or "").lower())
    return emp.full_name if emp else (email or "unknown")


def _is_cab_approver_eligible(email: str | None, ctx) -> bool:
    emp = ctx.employees_by_email.get((email or "").lower())
    if not emp or not emp.job_title:
        return False
    title = emp.job_title.lower()
    return any(h in title for h in CAB_APPROVER_ROLE_HINTS)


def run_change_management_tests(ctx, ids: IdGen) -> list[Finding]:
    findings: list[Finding] = []

    for c in ctx.bundle.change_records:
        app_policy = ctx.policy.applications.get(c.system)
        sensitivity = app_policy.sensitivity if app_policy else "low"
        subject = _display_person(ctx, c.developer or c.requested_by)
        subject_email = c.developer or c.requested_by

        # --- CHANGE_UNAPPROVED_DEPLOYMENT ---
        # Emergency changes are, by design, expected to skip pre-approval - a
        # missing approver alone must not double-flag an emergency change here;
        # that gap is judged under CHANGE_EMERGENCY_NOT_RETROACTIVELY_REVIEWED
        # instead. But an emergency change deployed AFTER its own approval date
        # is still inconsistent (there was no reason to skip the queue if it
        # waited for approval anyway), so that specific out-of-order case still
        # fires regardless of emergency_flag.
        deployed_before_approved = bool(c.approved_date and c.deployed_date and c.deployed_date < c.approved_date)
        missing_approver_flaggable = bool(c.deployed_date and not c.approver and not c.emergency_flag)
        if c.deployed_date and (missing_approver_flaggable or deployed_before_approved):
            if not c.approver:
                condition = (
                    f"Change {c.change_id} ('{c.description}') in {c.system} was deployed on "
                    f"{c.deployed_date.isoformat()} with no approver recorded at all."
                )
                cause = "No approval was captured before this change was deployed."
            else:
                condition = (
                    f"Change {c.change_id} ('{c.description}') in {c.system} was deployed on "
                    f"{c.deployed_date.isoformat()}, before the approval recorded on "
                    f"{c.approved_date.isoformat()}."
                )
                cause = "The change was deployed ahead of its formal approval, possibly due to urgency or an " \
                        "informal go-ahead outside the change record."
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.CHANGE_UNAPPROVED_DEPLOYMENT,
                severity=Severity.HIGH,
                system=c.system,
                subject_person=subject,
                subject_email=subject_email,
                condition=condition,
                criteria=f"{ctx.policy.policy_reference}: a change must be approved before it is deployed, and "
                         f"the approval must be evidenced.",
                cause=cause,
                effect="Deployment ahead of (or without) approval means the approval step is not a real control - "
                       "unauthorized or untested changes can reach production undetected.",
                recommendation="Obtain retroactive approval through the proper channel, and reinforce that changes "
                               "must not be deployed before the approval field is set.",
                evidence=[c.provenance.cite()],
                confidence=0.95,
            ))

        # --- CHANGE_SOD_DEVELOPER_IS_DEPLOYER ---
        if c.developer and c.deployer and c.developer.lower() == c.deployer.lower():
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.CHANGE_SOD_DEVELOPER_IS_DEPLOYER,
                severity=Severity.HIGH,
                system=c.system,
                subject_person=_display_person(ctx, c.developer),
                subject_email=c.developer,
                condition=f"Change {c.change_id} ('{c.description}') in {c.system} was both developed and "
                          f"deployed by the same person ({c.developer}), with no independent release step.",
                criteria=f"{ctx.policy.sod_policy_reference}: the person who develops a change must not also be "
                         f"the person who deploys it to production.",
                cause="The change process did not enforce developer/deployer segregation for this change.",
                effect="A developer able to release their own code can introduce unreviewed or unauthorized "
                       "changes directly into production undetected.",
                recommendation="Route future deployments for this system through an independent release function, "
                               "and review this change's contents for anything beyond its stated description.",
                evidence=[c.provenance.cite()],
                confidence=0.95,
            ))

        # --- CHANGE_MISSING_TEST_EVIDENCE ---
        is_prod = not c.environment or "prod" in c.environment.lower()
        if is_prod and not c.emergency_flag and not c.test_evidence_ref:
            findings.append(Finding(
                finding_id=ids.next("FND"),
                finding_type=FindingType.CHANGE_MISSING_TEST_EVIDENCE,
                severity=Severity.MEDIUM,
                system=c.system,
                subject_person=subject,
                subject_email=subject_email,
                condition=f"Change {c.change_id} ('{c.description}') in {c.system} was deployed to "
                          f"{c.environment or 'production'} with no test evidence reference on record.",
                criteria=f"{ctx.policy.policy_reference}: a non-emergency change to a production environment "
                         f"must have documented test/UAT evidence before deployment.",
                cause="The change was deployed without a recorded test reference, or testing occurred without "
                      "being documented in the change record.",
                effect="Untested changes deployed to production risk introducing defects or unintended behavior "
                       "with no evidence that they were validated beforehand.",
                recommendation="Obtain and attach the test/UAT evidence for this change, and require a test "
                               "reference as a mandatory field before a change can be marked deployed.",
                evidence=[c.provenance.cite()],
                confidence=0.85,
            ))

        # --- CHANGE_EMERGENCY_NOT_RETROACTIVELY_REVIEWED ---
        if c.emergency_flag and c.deployed_date:
            reviewed = bool(c.post_review_date and c.post_reviewed_by)
            overdue = (ctx.as_of - c.deployed_date).days > EMERGENCY_REVIEW_SLA_DAYS
            if not reviewed and overdue:
                findings.append(Finding(
                    finding_id=ids.next("FND"),
                    finding_type=FindingType.CHANGE_EMERGENCY_NOT_RETROACTIVELY_REVIEWED,
                    severity=Severity.MEDIUM,
                    system=c.system,
                    subject_person=subject,
                    subject_email=subject_email,
                    condition=f"Emergency change {c.change_id} ('{c.description}') in {c.system} was deployed on "
                              f"{c.deployed_date.isoformat()} ({(ctx.as_of - c.deployed_date).days} days ago) with "
                              f"no post-implementation review recorded, exceeding the "
                              f"{EMERGENCY_REVIEW_SLA_DAYS}-day review window.",
                    criteria=f"{ctx.policy.policy_reference}: an emergency change that skips pre-approval must "
                             f"receive a documented post-implementation review within "
                             f"{EMERGENCY_REVIEW_SLA_DAYS} days of deployment.",
                    cause="The emergency-change process does not enforce a mandatory retrospective review step, "
                          "or the review was performed but not documented in the change record.",
                    effect="Without retroactive review, an emergency change bypasses both pre- and post-deployment "
                           "scrutiny, and unauthorized or defective changes can go permanently unreviewed.",
                    recommendation="Conduct and document the post-implementation review for this change, and "
                                   "track emergency changes separately to ensure the review SLA is met going "
                                   "forward.",
                    evidence=[c.provenance.cite()],
                    confidence=0.9,
                ))

        # --- CHANGE_MISSING_CAB_APPROVAL ---
        # Skipped for emergency changes with no approver, same reasoning as
        # CHANGE_UNAPPROVED_DEPLOYMENT above - an emergency change is expected
        # to bypass pre-approval entirely, so "no CAB approver" isn't a
        # meaningful finding on top of that; an emergency change that DOES
        # have an approver on record is still held to the CAB-eligibility bar.
        if sensitivity == "high" and is_prod and not (c.emergency_flag and not c.approver):
            if not c.approver or not _is_cab_approver_eligible(c.approver, ctx):
                findings.append(Finding(
                    finding_id=ids.next("FND"),
                    finding_type=FindingType.CHANGE_MISSING_CAB_APPROVAL,
                    severity=Severity.HIGH,
                    system=c.system,
                    subject_person=subject,
                    subject_email=subject_email,
                    condition=(
                        f"Change {c.change_id} ('{c.description}') in {c.system} (a high-sensitivity system) has "
                        + (f"an approver ({c.approver}) who does not hold a change-board-eligible role"
                           if c.approver else "no approver recorded")
                        + "."
                    ),
                    criteria=f"{ctx.policy.policy_reference}: changes to high-sensitivity systems require approval "
                             f"from a Change Advisory Board (CAB) or equivalent change-authority role, not just "
                             f"any approver.",
                    cause="The change was approved (or went unapproved) outside the required CAB process for "
                          "sensitive systems.",
                    effect="Changes to high-sensitivity systems approved without genuine change-authority oversight "
                           "may not receive the scrutiny the system's risk level requires.",
                    recommendation="Route this change (and future changes to this system) through the CAB or "
                                   "designated change-authority approver, and retroactively review this one.",
                    evidence=[c.provenance.cite()],
                    confidence=0.8,
                ))

    return findings
