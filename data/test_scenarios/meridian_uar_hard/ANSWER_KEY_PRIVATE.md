# Meridian Textiles - Horizon ERP UAR (hard scenario) - ANSWER KEY

This file is private and is not referenced by any code in this repository.
It exists so you (or whoever works this case) can self-grade against the
intended findings after working the evidence cold. Nothing in
src/itgc reads this file, and nothing in the generator script depends on it
either - it's a description of what was planted, written after the fact.

**Update:** as of the addition of src/itgc/tests_itgc/decision_correlation.py,
items 2, 4, 7 and 8 below are now caught automatically by the real pipeline
(ACCESS_DECISION_CONTRADICTED, ACCESS_DECISION_NOT_ACTIONED,
OUT_OF_AUTHORITY_INSTRUCTION, and an "Ambiguous access decision" enquiry for
Meena, respectively) - this is the automated version of the manual
cross-referencing this scenario was originally built to exercise by hand.
It does NOT catch item 5 (the wrong Rahul being revoked - there is no email
naming Rahul Nair at all, so there is nothing for it to attribute that
revocation to) or item 3/6/9 (nothing to detect - they're clean/negative
controls). Re-run the pipeline against this scenario to see the automated
findings before deciding what's left to work out by hand.

## What a correct working of this case should surface

1. **Anitha Verma (MT-0005) - leaver access not removed.**
   Terminated 28-Feb-2026 per Sunil's email, but Horizon ERP shows her
   account ACTIVE in both the before and after sheets. This is a leaver/
   deprovisioning-SLA violation, and it is the one item that should be
   catchable purely from employee-master-vs-access-sheet cross-referencing,
   without needing the email at all - the email is a second, independent
   confirmation, and Deepa's first email also mentions this in passing.
   Sunil's email is a moot/redundant instruction (he's not actioning
   anything, just flagging) - the finding stands regardless of whether his
   email existed.

2. **Ramesh Pillai (MT-0002) - wrongly revoked against the final instruction.**
   Deepa's first email said revoke him; her correction email (later,
   21-Aug) explicitly reverses that and says keep him. The AFTER sheet
   shows him DISABLED - i.e. the wrong (superseded) instruction was
   actioned instead of the current one. Correct answer: this is an
   erroneous revocation, evidenced by which of Deepa's two emails is later.

3. **Suman Ghosh (MT-0003) - correctly revoked.** Negative control - both
   of Deepa's emails agree on this one, and the after-sheet reflects it.
   Nothing to flag here.

4. **Rahul Menon (MT-0007) - instructed revoke, but NOT revoked.**
   Ravindra's email (and his confirmation in the follow-up thread with
   Neha) makes clear he means Rahul Menon, his own report. The AFTER sheet
   still shows Rahul Menon ACTIVE - the instruction was not actioned.

5. **Rahul Nair (MT-0012) - wrong person revoked.**
   Rahul Nair reports to Kavitha in Sales, not to Ravindra, and no one
   asked for his access to be touched. The AFTER sheet shows him DISABLED.
   This is the marquee "wrong person actioned" finding - it requires
   noticing that the Rahul who was actually revoked is not the Rahul who
   was named, which in turn requires checking the org chart (manager
   field), not just string-matching the first name "Rahul".

6. **Feroz Sheikh (MT-0009) - correctly revoked.** He is the only
   contractor in the whole roster, so Ravindra's vague "that contractor we
   discussed" is resolvable, and the after-sheet correctly disables him.
   Negative control - not a finding, but worth noting that the resolution
   depended on there being exactly one contractor.

7. **Suresh Pillai (MT-0013) - revoked on an out-of-authority instruction.**
   Arjun refers to him only by ID; the ID resolves (via the employee
   master) to Suresh Pillai, who reports to Kavitha Reddy in Sales, NOT to
   Arjun in Warehouse. Arjun has no reporting authority over this person.
   Independent of whether the underlying instruction was legitimate (it
   may have come from Suresh's actual manager through some other channel
   not evidenced here), a control-minded reviewer should flag that Arjun
   requested and Neha apparently actioned a revocation for someone outside
   Arjun's own reporting line, with no corroborating instruction from
   Kavitha (who said nothing about Suresh Pillai in her own email). This
   is a process/authority gap, not a proven wrongful revocation - treat it
   as an open item requiring corroboration, not a confirmed error either
   way.

8. **Meena Krishnan (MT-0014) vs. Meenakshi Iyer (MT-0015) - genuinely
   ambiguous, correctly left unresolved.**
   Both report to Kavitha and both could plausibly be "Meena" (Meenakshi
   goes by Meena). Kavitha's email never disambiguates. The AFTER sheet
   leaves both of them ACTIVE - i.e., no action was taken pending
   clarification. The correct auditor behaviour here is to raise this as
   an open enquiry back to Kavitha, not to guess which one she meant. If a
   tool or reviewer confidently "resolves" this to one specific person
   without further evidence, that overconfidence is itself the failure
   mode this item is testing for.

9. **Ananya Das (MT-0024) - legitimate new joiner, not a violation.**
   She does not appear in the BEFORE sheet at all and only appears in
   AFTER, which on its own looks like an unexplained new grant. She is in
   fact a genuine new hire (20-Aug-2026, inside the review window),
   reporting to Deepa Nair, added with an active account appropriate to a
   Junior Accountant role. There's no ticket/approval evidence bundled for
   her in this scenario (this scenario has no service-desk evidence at
   all, by design - see below) - the intended lesson is that "new since
   the review started" is not automatically suspicious once cross-checked
   against the employee master's hire date, but the absence of a
   documented approval for her IS a legitimate secondary observation
   (missing evidence of proper onboarding approval), distinct from
   treating her as a rogue/unauthorized account.

## Deliberately not modeled in this scenario

- No service-desk ticket evidence is included here at all - this scenario
  is entirely email + spreadsheet, on purpose, to test that the tool
  doesn't assume ticket evidence will always exist.
- The company/role/context YAML files DO conform to the same schema as the
  ACME sample dataset (load_policy() requires it to run the engagement at
  all through the real pipeline), so the existing automated JML/orphan/
  access rules do run against this data too - see the note below on what
  that does and doesn't catch.

## What the existing automated pipeline does and doesn't catch here

Running this folder through the real pipeline (same as the ACME sample) is
a valid thing to do and does catch item 1 above automatically -
JML_TERMINATED_ACTIVE_ACCOUNT and MISSING_DEPROVISIONING_RECORD both fire
for Anitha Verma with zero manual work, which is a good sanity check that
the existing engine still works correctly on a second company's data.

It will ALSO fire MISSING_APPROVAL_EVIDENCE for nearly every account,
because this scenario has zero ticket evidence and that control's current
logic requires either a ticket or an approver-eligible approval email to
exist for every active grant. That's not a bug - it's a real, valid
finding (nobody can prove any of this access was ever formally approved) -
but it isn't the finding this scenario was built to test, and it will
drown it out in the results list.

The actual hard puzzle - items 2, 4, 5, 7, 8 above (the correction-email
reversal, the two Rahuls, the out-of-authority MT-0013 instruction, the
Meena ambiguity) - requires correlating each manager's retain/revoke
decision in the email thread against what the before/after sheets actually
show. There is no automated ITGC control for that yet; it does not exist
as a rule anywhere in src/itgc/tests_itgc/. This scenario is meant to be
read end-to-end (the emails, in order, including the correction and the
disambiguation exchange) and reasoned through by hand, or by whatever
LLM-driven correlation layer gets built for this specifically - not
graded by what the current deterministic engine outputs.

## Spreadsheet mechanics planted (for ingestion robustness, not audit findings)

- BEFORE sheet: a title/banner block above the real header row, a
  duplicate row (Karthik Iyer, MT-0008), and a blank row before Meenakshi
  Iyer's row.
- AFTER sheet: different header wording than BEFORE ("Login ID" vs
  "User ID", "Acount Status" - deliberate typo - vs "Account Status"), and
  the columns are in a different order than BEFORE.
