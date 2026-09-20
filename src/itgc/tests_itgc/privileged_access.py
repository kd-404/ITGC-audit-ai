"""ITGC test domain: Privileged Access Management.

Operates on PrivilegedAccessReview evidence (see
PRIVILEGED_ACCESS_REVIEW_SCHEMA in ingest/schemas.py) cross-referenced
against access records held via a profile the policy marks privileged
(`ApplicationPolicy.privileged_profiles`, alongside the existing
`sod_conflicts`). This is distinct from access.py's DORMANT_ACCOUNT_NOT_
REVIEWED, which is about usage; this is about periodic attestation,
whether or not the account is actively used.

Checks implemented:

  PRIVILEGED_ACCESS_NEVER_REVIEWED
      An account holding a privileged profile has no review record within
      the policy's review-cycle window (Policy.privileged_review_cycle_days).

  PRIVILEGED_ACCESS_RETAINED_WITHOUT_JUSTIFICATION
      A review record exists but its justification is blank, or is just a
      restatement of the access itself ("needs admin access" - circular,
      not a reason).

  PRIVILEGED_ACCESS_SELF_REVIEWED
      The reviewer on a privileged-access review is the same person as the
      account holder - a SoD violation in the review process itself, same
      shape as provisioning.py's PROVISIONING_SOD_SELF_APPROVED.

  PRIVILEGED_COUNT_CONCENTRATION (portfolio-level, not per-account)
      A single approver/reviewer accounts for a disproportionate share of
      all privileged-access reviews across the engagement - not a
      violation by itself, output as an Enquiry rather than a Finding
      (signal, not a confirmed control failure).

run_privileged_access_tests returns (findings, enquiries), the same shape
as decision_correlation.run_decision_correlation_tests, since it's the
first ITGC test module (besides decision_correlation) to legitimately
produce both.
"""
from __future__ import annotations

from datetime import date

from ..models import Finding, FindingType, Severity, Enquiry
from .idgen import IdGen

ACTIVE_STATES_EXCLUDED = {"disabled", "inactive", "revoked", "closed", "terminated", "removed"}
RETAIN_DECISIONS = {"retain", "retained", "keep", "approved", "confirmed"}
GENERIC_JUSTIFICATION_PHRASES = {
    "needs access", "needs admin access", "needs it", "required for role", "required", "n/a", "-",
}
CONCENTRATION_MIN_REVIEWS = 4
CONCENTRATION_SHARE_THRESHOLD = 0.6


def _display_person(ctx, email: str | None) -> str:
    emp = ctx.employees_by_email.get((email or "").lower())
    return emp.full_name if emp else (email or "unknown")


def _is_circular_justification(justification: str | None) -> bool:
    if not justification or not justification.strip():
        return True
    return justification.strip().lower() in GENERIC_JUSTIFICATION_PHRASES


def run_privileged_access_tests(ctx, ids: IdGen) -> tuple[list[Finding], list[Enquiry]]:
    findings: list[Finding] = []
    enquiries: list[Enquiry] = []

    # Index reviews by (account_id, system), case-insensitive, most recent first.
    reviews_by_account: dict[tuple[str, str], list] = {}
    for r in ctx.bundle.privileged_access_reviews:
        key = (r.account_id.strip().lower(), r.system.strip().lower())
        reviews_by_account.setdefault(key, []).append(r)
    for key, revs in reviews_by_account.items():
        revs.sort(key=lambda r: r.review_date or date.min, reverse=True)

    # --- account-level checks: never-reviewed, retained-without-justification, self-reviewed ---
    for (emp_key, system), records in ctx.employee_grants().items():
        if emp_key.startswith("UNMATCHED:"):
            continue
        emp = records[0].matched_employee
        if emp.status.strip().lower() == "terminated":
            continue
        active_records = [r for r in records if r.account_status.strip().lower() not in ACTIVE_STATES_EXCLUDED]
        if not active_records:
            continue

        app_policy = ctx.policy.applications.get(system)
        privileged_profiles = set(app_policy.privileged_profiles) if app_policy else set()
        if not privileged_profiles:
            continue

        for rec in active_records:
            held_privileged = sorted(set(rec.profiles) & privileged_profiles)
            if not held_privileged:
                continue

            key = (rec.account_id.strip().lower(), system.strip().lower())
            revs = reviews_by_account.get(key, [])
            latest = revs[0] if revs else None
            cycle_days = ctx.policy.privileged_review_cycle_days

            if latest is None or not latest.review_date or (ctx.as_of - latest.review_date).days > cycle_days:
                age_note = (
                    "no review record exists at all" if latest is None or not latest.review_date
                    else f"the most recent review was {(ctx.as_of - latest.review_date).days} days ago, "
                         f"beyond the {cycle_days}-day review cycle"
                )
                findings.append(Finding(
                    finding_id=ids.next("FND"),
                    finding_type=FindingType.PRIVILEGED_ACCESS_NEVER_REVIEWED,
                    severity=Severity.HIGH,
                    system=system,
                    subject_person=emp.full_name,
                    subject_email=emp.email,
                    condition=f"{emp.full_name} holds privileged profile(s) {', '.join(held_privileged)} in "
                              f"{system} (account {rec.account_id}), and {age_note}.",
                    criteria=f"{ctx.policy.policy_reference}: privileged access must be periodically "
                             f"re-certified at least every {cycle_days} days.",
                    cause="No periodic access-certification process captured this account, or the review was "
                          "performed without being documented.",
                    effect="Unreviewed privileged access can persist long after it is still needed, and "
                           "provides no evidence to an auditor that the access remains justified.",
                    recommendation=f"Perform and document a privileged-access review for this account with "
                                   f"{emp.manager_email or 'the account holders manager'}, and ensure future "
                                   f"reviews occur within the {cycle_days}-day cycle.",
                    evidence=[rec.provenance.cite()] + ([latest.provenance.cite()] if latest else []),
                    confidence=0.85,
                ))
                continue  # a never-reviewed account has nothing further to evaluate below

            if latest.decision.strip().lower() in RETAIN_DECISIONS and _is_circular_justification(latest.justification):
                findings.append(Finding(
                    finding_id=ids.next("FND"),
                    finding_type=FindingType.PRIVILEGED_ACCESS_RETAINED_WITHOUT_JUSTIFICATION,
                    severity=Severity.MEDIUM,
                    system=system,
                    subject_person=emp.full_name,
                    subject_email=emp.email,
                    condition=f"{emp.full_name}'s privileged access ({', '.join(held_privileged)}) in {system} "
                              f"(account {rec.account_id}) was retained at the {latest.review_date.isoformat() if latest.review_date else 'last'} "
                              f"review with " + (
                                  "no justification recorded" if not latest.justification or not latest.justification.strip()
                                  else f"only a circular justification ('{latest.justification}')"
                              ) + ".",
                    criteria=f"{ctx.policy.policy_reference}: a decision to retain privileged access must be "
                             f"supported by a substantive business justification, not a restatement of the "
                             f"access itself.",
                    cause="The reviewer completed the review record without providing (or being required to "
                          "provide) a real justification for retaining the access.",
                    effect="A retain decision with no real justification provides no defensible basis for the "
                           "access if challenged, and may mask access that should have been revoked.",
                    recommendation="Obtain a substantive justification for this access from the account holder's "
                                   "manager or system owner, or revoke the access if none can be provided.",
                    evidence=[latest.provenance.cite()],
                    confidence=0.75,
                ))

            if latest.reviewer and latest.reviewer.strip().lower() == (emp.email or "").strip().lower():
                findings.append(Finding(
                    finding_id=ids.next("FND"),
                    finding_type=FindingType.PRIVILEGED_ACCESS_SELF_REVIEWED,
                    severity=Severity.CRITICAL,
                    system=system,
                    subject_person=emp.full_name,
                    subject_email=emp.email,
                    condition=f"{emp.full_name}'s privileged access review for {system} (account {rec.account_id}) "
                              f"was performed by the account holder themselves ({latest.reviewer}).",
                    criteria=f"{ctx.policy.sod_policy_reference}: privileged-access reviews must be performed by "
                             f"someone independent of the account holder.",
                    cause="The review process did not enforce reviewer/account-holder segregation for this "
                          "review.",
                    effect="A self-reviewed privileged account has effectively never been independently "
                           "attested, regardless of what the review record shows.",
                    recommendation="Reassign this review to an independent reviewer (e.g. the account holder's "
                                   "manager or the system owner) and re-perform it.",
                    evidence=[latest.provenance.cite()],
                    confidence=0.95,
                ))

    # --- portfolio-level: reviewer concentration (signal, not a violation) ---
    all_reviews = ctx.bundle.privileged_access_reviews
    if len(all_reviews) >= CONCENTRATION_MIN_REVIEWS:
        counts: dict[str, int] = {}
        for r in all_reviews:
            if r.reviewer:
                counts[r.reviewer] = counts.get(r.reviewer, 0) + 1
        if counts:
            top_reviewer, top_count = max(counts.items(), key=lambda kv: kv[1])
            share = top_count / len(all_reviews)
            if share >= CONCENTRATION_SHARE_THRESHOLD:
                enquiries.append(Enquiry(
                    enquiry_id=ids.next("ENQ"),
                    topic="Privileged access review concentration",
                    question=(
                        f"{_display_person(ctx, top_reviewer)} ({top_reviewer}) performed {top_count} of "
                        f"{len(all_reviews)} privileged-access reviews in this engagement "
                        f"({share:.0%}). Is this level of concentration in a single reviewer expected "
                        f"(e.g. a dedicated access-certification role), or should review responsibility be "
                        f"more distributed?"
                    ),
                    context="Not a control violation by itself - a single reviewer accounting for most "
                            "privileged-access certifications is a portfolio-level signal worth asking about, "
                            "since it reduces the independence of the overall review process even when each "
                            "individual review is otherwise valid.",
                    blocking=False,
                ))

    return findings, enquiries
