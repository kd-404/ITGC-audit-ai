# Solstice Freight & Logistics Ltd - CargoLink TMS (hard scenario) - ANSWER KEY

Private, self-grading reference only. Not read by any code. See
data/test_scenarios/meridian_uar_hard/ANSWER_KEY_PRIVATE.md for the same
disclaimer in more detail - it all applies here too.

This scenario is ticket-driven (unlike Meridian, which was email-driven with
zero tickets), so more of it is automatable through the existing engine -
but several items still require reading the email evidence and correlating
it against the tickets and the UAR export by hand.

**Note on decision_correlation.py:** the automated retain/revoke-vs-outcome
correlation added after this scenario was built (see Meridian's answer key)
does not add anything new here - none of this scenario's emails are
retain/revoke UAR decisions in that shape (they're about a verbal grant,
a vague new-starter grant, and a self-approval already caught by
provisioning.py). This is expected, not a gap in that control.

## Findings the existing automated engine should catch on its own

1. **SOD_VIOLATION_ACCESS - David Ferreira holds both AP_Clerk and
   AP_Approver.** Caught automatically via the role_access_matrix SoD
   conflict pair. What makes it "hard" is not the detection (the rule fires
   regardless) but recognizing the STRENGTH of the evidence trail behind
   it: the promotion ticket (T-3001) itself says to remove AP_Clerk, and
   Grace's email (independently, before the ticket was even raised) says
   the same thing. This isn't an ambiguous or arguable case - there are two
   independent, dated instructions that this exact conflict should not
   exist, and it exists anyway.

2. **JML_TERMINATED_ACTIVE_ACCOUNT / MISSING_DEPROVISIONING_RECORD - Ivy
   Chen.** Terminated 20-Jun-2026, but her CargoLink account is still
   Active as of the export date. Caught automatically, the same way
   Anitha Verma was in the Meridian scenario - included on purpose as a
   repeatable sanity check.

3. **ORPHAN_ACCOUNT - SVC-CargoLink-Batch.** Active, privileged
   (System_Admin), no employee-master match at all. Caught automatically.
   Tom's email confirms this isn't just a matching gap on the tool's side -
   IT itself doesn't know who owns it either. The correct read is "open
   item requiring ownership assignment," not "confirmed rogue account" -
   there's no evidence of misuse, just missing accountability.

   You will ALSO see a second ORPHAN_ACCOUNT / "unidentified account owner"
   enquiry for something called "NOTE:" with account name "IT to re-run
   this export after the September change freeze ends". That is not a
   planted person or account - it's the stray commentary row buried in the
   UAR workbook (see the mechanics section at the bottom) getting read as
   if it were a data row, because it has non-blank text in the first two
   columns. This is deliberate: the current ingestion layer has no concept
   of "this row is obviously a note, not an account," so it will raise a
   real enquiry asking who owns an "account" that is plainly just a
   sentence. Correctly recognizing and discarding this - rather than
   investigating it as a genuine unidentified account - is itself part of
   the test.

4. **PROVISIONING_SOD_SELF_APPROVED - Tariq Hussain (T-3004).** Requester
   and approver are the same person. Caught automatically. Lucy's email
   independently corroborates that this was noticed and is a real
   irregularity, not a data-entry glitch - two unrelated evidence sources
   agreeing is what should raise confidence here, not just the rule firing.

5. **APPROVAL_AFTER_IMPLEMENTATION - Nadia Kowalski (T-3005).** Implemented
   02-Sep, "approved" 04-Sep. Caught automatically.

6. **EXCESS_ACCESS_UNEXPECTED_ROLE - Tariq Hussain and Nadia Kowalski**
   both also hold Warehouse_Admin, outside what a Warehouse Supervisor /
   Stock Controller is mapped to. Caught automatically, and reinforces (4)
   and (5) independently through a completely different rule (role-based
   access matrix vs. ticket-approval logic) - useful as a cross-check that
   both angles land on the same two accounts.

7. **EXCESS_ACCESS_UNEXPECTED_ROLE + MISSING_APPROVAL_EVIDENCE - Ola
   Adeyemi's Ops_Admin profile** (her baseline Ops_User is fine and
   ticketed under T-3020). No ticket, no email, nothing justifies the
   second, more privileged profile. Caught automatically by two
   independent rules.

## Findings that require manual/email correlation - no automated rule exists for these

8. **Chloe Bennett's Dispatch_User grant** has no ticket - the only
   evidence is her own email admitting "James Walsh approved it over a
   call." There are TWO James Walshes in this company: Operations Manager
   (E-1010, her actual manager on record) and Warehouse Manager (E-1020,
   unrelated to her). The email alone does not disambiguate; only checking
   her manager_email field resolves it to E-1010. The automated
   MISSING_APPROVAL_EVIDENCE control will still fire here regardless (this
   is a high-sensitivity system and a verbal/email-only approval isn't
   sufficient evidence for it under the current control logic) - the
   manual work is correctly attributing WHO gave that verbal approval, not
   clearing the finding.

9. **The vague "new starter" email (email_03)** could refer to Anna
   Kowalczyk (who already has an untracked Ops_User grant with no ticket -
   plausibly what this email is backfilling) or Farid Rahman (who has no
   CargoLink access at all yet, and isn't necessarily overdue - he's only
   been in role a few weeks). The email under-determines which one it's
   about. The correct behaviour is to flag this explicitly as an open item
   needing clarification, not to confidently guess. Farid having zero
   access is not itself a finding at this point - there's no evidence he
   needs CargoLink for his role yet, and the joiner-provisioning SLA
   (10 days) has not been breached as of the review date.

10. **Priya Chandran's contractor-to-permanent conversion.** Two
    completely separate employee-master rows (C-0090 on an external
    @extmail.co.uk address, E-1031 on her new corporate address) refer to
    the same real person. Both her old and new access are correctly
    ticketed and the old account is correctly disabled (T-3002, T-3003,
    corroborated by the Lucy/Ben email exchange) - this is a NEGATIVE
    CONTROL. The point isn't to find a violation here; it's to correctly
    recognize these two records as one continuous person's history
    (useful context if either account is ever referenced elsewhere) without
    mistakenly treating the pair as a data inconsistency, a duplicate
    identity, or - worse - inferring a leaver-without-deprovisioning
    finding against C-0090 by failing to notice it actually was disabled.

## Spreadsheet/ticket mechanics planted (for ingestion robustness, not audit findings)

- Employee master CSV uses yet another set of header names ("Staff No.",
  "Legal Name", "Corp Email Address", "Dept / Division", "Job Title / Role",
  "Line Manager Email", "Employee Status", "Start Date", "Separation Date")
  - different wording again from both the ACME and Meridian datasets, chosen
    to still be within reach of a fuzzy character-similarity column matcher
    (this ingestion layer matches reworded/abbreviated headers, not
    unrelated synonyms like "Function" for "Department" - a genuinely
    synonym-based mapping would need a semantic/LLM matching step that
    doesn't exist yet in this deterministic ingestion layer).
- The UAR workbook has a banner block above the header row (like both prior
  datasets) AND a free-text commentary row pasted into the middle of the
  data rows (not at the top or as a clean blank row like Meridian) - a
  different kind of mess than either prior dataset used.
- The service-desk CSV uses its own header wording ("Request ID", "Raised
  By", "Approved By", "Application", "Description", "Ticket Status",
  "Raised Date", "Approved Date", "Implemented Date", "Implemented By").
- Two employees legitimately share an identical full name ("James Walsh")
  in different departments with different email addresses - a harder
  identity-resolution case than Meridian's shared-first-name pattern, since
  a naive exact full-name match would consider both an equally good hit.
