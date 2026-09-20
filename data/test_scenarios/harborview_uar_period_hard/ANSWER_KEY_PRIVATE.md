# Harborview Behavioral Health - ClinCareEHR (hard scenario) - ANSWER KEY

Not read by any code. For self-grading only.

## Centerpiece: period-start vs period-end UAR comparison

Three ClinCareEHR users all gain PHI_Admin (a privileged profile) between
the 2026-06-01 and 2026-09-14 extracts, and look identical in the UAR data
alone. The difference is entirely in the ticket data (and, for one of them,
an email the ticket text alone can't resolve):

1. **Dana Whitfield (H-03) - TRUE POSITIVE, undocumented.** No ticket, no
   email, anywhere. The automated pipeline's uar_period_diff.py check
   should flag UAR_UNDOCUMENTED_INTERIM_ACCESS_CHANGE, and provisioning.py's
   MISSING_APPROVAL_EVIDENCE should independently agree on the same
   account - two controls corroborating the same real gap.

2. **Grace Liu (H-04) - PLANTED FALSE POSITIVE.** SD-3002 is a real,
   approved ticket for exactly this grant - but it was filed by Alicia
   Munroe (IT Support), not Grace herself, because Grace was travelling.
   The pipeline's ticket lookup (find_provisioning_ticket) only matches a
   ticket whose REQUESTER is the grant holder's own email, so it will
   flag this exactly like Dana's case. Only email_04 (Alicia explaining
   the arrangement, with Renee's verbal approval confirmed in writing)
   resolves it as legitimate. This is a genuine, documented limitation of
   the tool's requester-matching, not a bug - a reviewer should NOT accept
   an automated flag here at face value without reading the emails, and
   should also not conclude the tool is "broken": loosening the match to
   accept any requester would make genuine self-service abuse (someone
   filing their own unauthorized grant and claiming it was "on behalf of"
   someone else) indistinguishable from this legitimate case.

3. **Tobias Reyes (H-05) - clean.** SD-3003, correctly self-requested,
   approved by Renee Castillo (an approver-eligible role). Must not be
   flagged by anything.

## Other planted issues

4. **Marcus Doyle (H-02) - mover, access not revoked.** Promoted from
   Billing Clerk to Billing Supervisor; SD-3001 explicitly says to remove
   Billing_Clerk; the period-end UAR still shows both Billing_Clerk AND
   Billing_Approver - an active SoD conflict per the role-access matrix,
   catchable by the existing single-snapshot SoD check alone (no
   multi-snapshot needed), corroborated independently by email_01 (Priya
   asking IT to confirm the removal happened).

5. **Two Sam Okafors - identity trap.** H-07 (permanent, Outpatient,
   reports to Naomi Park) and H-08 (contractor, Residential, reports to
   Warren Bell, Terminated 2026-09-12). email_02 just says "Sam's last day
   was Friday" with no department/contractor qualifier - resolvable only
   by checking that Warren Bell manages H-08, not H-07. H-08's account is
   correctly disabled by period-end (SD-3004 exists and the UAR confirms
   Disabled) - a clean leaver, once correctly identified. H-07 must not be
   touched or flagged.

6. **SVC-ClinCare-ETL - documented exception, not a clear violation.**
   Mechanically an orphan account (System_Admin, no employee-master match)
   - the existing orphan.py check will flag it exactly like a genuine
   unowned account would be flagged. email_03 shows Renee Castillo has, in
   fact, tracked and recertified it for years (compliance register entry
   CR-2019-014). Whether that's sufficient to close a mechanically-correct
   finding is a judgment call for the reviewer and this engagement's own
   framework, not something the tool can resolve on its own - note it as
   an open item requiring a policy decision, not a false alarm to dismiss
   outright.

## What the tool actually produces if you run it

This has been run end-to-end (not just designed on paper) against:

    python3 scripts/run_pipeline.py \
        --company data/test_scenarios/harborview_uar_period_hard/company \
        --evidence data/test_scenarios/harborview_uar_period_hard/evidence \
        --as-of 2026-09-14 --no-llm

The six planted issues above all appear exactly as designed:
  - UAR_UNDOCUMENTED_INTERIM_ACCESS_CHANGE + MISSING_APPROVAL_EVIDENCE on Dana Whitfield (correct - #1)
  - UAR_UNDOCUMENTED_INTERIM_ACCESS_CHANGE + MISSING_APPROVAL_EVIDENCE on Grace Liu (the planted false positive - #2, only email_04 resolves it)
  - Nothing extra on Tobias Reyes beyond baseline noise (see below) - correctly clean (#3)
  - SOD_VIOLATION_ACCESS on Marcus Doyle (correct - #4)
  - Nothing at all on either Sam Okafor besides baseline noise on the permanent one - the identity trap
    resolves correctly and the contractor's deprovisioning raises no finding because it WAS done correctly (#5)
  - ORPHAN_ACCOUNT on SVC-ClinCare-ETL (mechanically correct; email_03 makes it a judgment call, not a
    dismissal - #6)

Two things also show up that are real but NOT part of the six planted issues, and are worth being able to
tell apart from them rather than mistake for something you missed:

  - **MISSING_APPROVAL_EVIDENCE fires broadly across almost everyone's BASELINE (pre-existing) access** -
    this scenario deliberately includes no onboarding/legacy provisioning tickets for anyone's original
    access, only tickets for the mid-period changes. A real client this thin on historical evidence really
    would generate this much noise; the six graded issues above are the ones that matter, this is "we don't
    retain old provisioning records" as its own, less interesting, honest finding.
  - **Marcus Doyle's promotion ticket (SD-3001) ALSO trips UAR_UNDOCUMENTED_INTERIM_ACCESS_CHANGE and
    MISSING_APPROVAL_EVIDENCE for his new Billing_Approver profile**, on top of the intended
    SOD_VIOLATION_ACCESS - because Priya (his manager) filed the promotion ticket, not Marcus himself, so
    the same requester-must-equal-grant-holder matching limitation behind Grace Liu's planted false
    positive (#2) trips here too, completely organically, from an extremely common real-world pattern
    (managers routinely file role-change tickets for their reports rather than the employee filing their
    own). This is a genuine second illustration of the same limitation, not a scenario bug - worth noting
    if you're using this to teach the "don't trust an automated finding without reading the ticket text"
    lesson twice, in two different flavors.
  - **PRIVILEGED_ACCESS_NEVER_REVIEWED fires on every PHI_Admin/System_Admin holder** (Ben Ferris, Dana
    Whitfield, Grace Liu, Tobias Reyes) - this scenario provides no privileged-access-review evidence at
    all, so this is accurate (the client has never recertified privileged ClinCareEHR access) but, again,
    not one of the six graded issues - it's a real gap affecting the whole privileged population evenly,
    not something specific to any one person's story.

If the tool raises anything ELSE beyond what's listed here, treat that as worth investigating rather than
assuming the scenario is wrong.
