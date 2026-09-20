"""
Generates "Harborview Behavioral Health" - a third, standalone hard/
adversarial ITGC test scenario for its ClinCareEHR system, deliberately
different in shape from both existing scenarios:

  - Meridian Textiles (data/test_scenarios/meridian_uar_hard/): email-driven,
    zero ticket evidence, single UAR snapshot.
  - Solstice Freight (data/test_scenarios/solstice_jml_sod_hard/): ticket-
    driven, 7 emails, single UAR snapshot.
  - Harborview (this one): TWO DATED UAR EXTRACTS for the same system
    (period-start and period-end), which is the centerpiece - it targets the
    exact gap the automated pipeline's uar_period_diff.py check exists for
    (comparing what changed DURING a review period, not just what a single
    point-in-time pull happens to show), plus a deliberately planted FALSE
    POSITIVE in that same check, to test whether a reviewer trusts an
    automated finding without reading the underlying evidence.

Same ground rules as Meridian and Solstice: this script and its output are
not imported, not run by any test, and not read by src/itgc. Pure evidence,
for testing a human (or another instance of this tool) by hand.

Planted, on purpose - three near-identical "PHI_Admin added mid-period"
grants with three different evidentiary outcomes, meant to be compared
side by side:

  1. Dana Whitfield (Clinical Coordinator) gains PHI_Admin (a
     privileged/sensitive profile) between the two UAR extracts. No ticket,
     no email - a genuine, undocumented interim grant. The automated tool
     SHOULD catch this (uar_period_diff.py), and provisioning.py's existing
     MISSING_APPROVAL_EVIDENCE check should independently agree - two
     controls corroborating the same gap, the intended correlation case.

  2. Grace Liu (Care Manager) also gains PHI_Admin mid-period, and there
     IS a real, approved ticket for it - but the ticket's requester is
     Alicia Munroe (IT Support), who filed it "on Grace's behalf" while
     Grace was travelling, not Grace herself. The automated tool's ticket
     lookup only matches on the GRANT HOLDER'S OWN email as requester, so
     it will (wrongly) flag this as undocumented too - a planted FALSE
     POSITIVE. Only reading email_04 (Alicia explaining the arrangement,
     with Renee's phone approval confirmed in writing) resolves it. This is
     an honest, documented limitation of the tool's matching logic, not a
     bug to "fix" by loosening the check (loosening it would just open the
     door to real self-service-approval abuse looking legitimate).

  3. Tobias Reyes (Clinical Coordinator) also gains PHI_Admin mid-period,
     via a completely ordinary, correctly-attributed ticket (Tobias is his
     own requester). Clean; must not be flagged by anything. The point of
     having all three side by side is that #1, #2 and #3 are indistinguishable
     from the UAR extracts alone - the difference is entirely in the ticket
     data, and for #2, entirely in an email the ticket text alone doesn't
     resolve.

  4. MOVER, ACCESS NOT REVOKED: Marcus Doyle is promoted from Billing Clerk
     to Billing Supervisor. The promotion ticket explicitly says to remove
     his Billing_Clerk profile; his manager separately emails asking IT to
     confirm the removal happened. The period-end UAR still shows him
     holding BOTH profiles - an active SoD conflict per the role-access
     matrix, already catchable by the existing (single-snapshot) SoD check,
     with two independent pieces of evidence confirming it was known.

  5. SAME-NAME IDENTITY TRAP: two "Sam Okafor"s - a permanent Care Manager
     in the Outpatient program (reports to Naomi Park) and a contractor
     Care Manager in the Residential program (reports to Warren Bell). Only
     the contractor's assignment ends mid-period. Warren's termination
     email just says "Sam's last day was Friday, please disable his
     ClinCare access" with no department or contractor qualifier - resolvable
     only by checking which Sam actually reports to Warren. The contractor
     Sam's account IS correctly disabled by period-end (a clean leaver, once
     correctly identified) - the permanent Sam must not be touched.

  6. DOCUMENTED EXCEPTION, NOT A CLEAR VIOLATION: SVC-ClinCare-ETL is an
     active, privileged (System_Admin) UAR row with no employee-master
     match at all - mechanically an orphan account, and the existing
     orphan.py check will flag it exactly like it would flag a genuine
     unowned account. But an email shows Renee Castillo (Compliance
     Officer) has, in fact, tracked this service account in the compliance
     register for years with an annual access recertification - a
     judgment call for the reviewer (is a registered, recertified service
     account exception still a "finding" for THIS engagement, or a
     documented exception the client's own framework already accepts?),
     not a clean automated true/false.

Run: python3 scripts/generate_hard_scenario_harborview.py
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "test_scenarios" / "harborview_uar_period_hard"
COMPANY = BASE / "company"
SHEETS = BASE / "evidence" / "sheets"
SERVICEDESK = BASE / "evidence" / "servicedesk"
EMAIL = BASE / "evidence" / "email"

for d in (COMPANY, SHEETS, SERVICEDESK, EMAIL):
    d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# company/
# --------------------------------------------------------------------------
(COMPANY / "company_context.yaml").write_text("""\
company: Harborview Behavioral Health
engagement: ClinCareEHR - ITGC review (period-start vs period-end UAR comparison)
in_scope_applications:
- ClinCareEHR
policy_reference: HBH-ITGC-POL-03 Access Management Policy v1.4
sod_policy_reference: HBH-ITGC-POL-06 Segregation of Duties Policy
industry: Behavioral health / outpatient and residential clinical services
notes: >
  This cycle's evidence includes TWO dated ClinCareEHR access extracts
  (period-start and period-end) rather than a single point-in-time pull,
  specifically so that access changes made DURING the review period - not
  just what happens to be held on the day a single extract is taken - can
  be evaluated. A service-desk export and four emails round out the
  evidence; roughly half the planted issues are caught by the automated
  rules on their own, the rest (including one deliberate false positive)
  require reading the emails.
""", encoding="utf-8")

(COMPANY / "role_access_matrix.yaml").write_text("""\
applications:
  ClinCareEHR:
    sensitivity: high
    profiles:
    - Clinician_User
    - Clinician_Admin
    - Billing_Clerk
    - Billing_Approver
    - PHI_Admin
    - IT_Admin
    - System_Admin
    - ReadOnly
    sod_conflicts:
    - - Billing_Clerk
      - Billing_Approver
    role_to_profile:
      Clinical Coordinator:
      - Clinician_User
      - PHI_Admin
      Care Manager:
      - Clinician_User
      - PHI_Admin
      Care Manager (Contractor):
      - Clinician_User
      Program Director:
      - Clinician_Admin
      Billing Clerk:
      - Billing_Clerk
      Billing Supervisor:
      - Billing_Approver
      Compliance Officer:
      - ReadOnly
      IT Manager:
      - IT_Admin
      - System_Admin
      IT Support Analyst:
      - IT_Admin
    privileged_profiles:
    - PHI_Admin
    - System_Admin
deprovisioning_sla_days: 5
dormant_threshold_days: 90
joiner_provisioning_sla_days: 10
uar_review_period: 2026-Q3
""", encoding="utf-8")

EMPLOYEES = [
    # emp_id, name, email, dept, title, manager_email, status, hire, term
    ("H-01", "Priya Ramanathan", "priya.ramanathan@harborviewbh.org", "Billing", "Billing Supervisor", "", "Active", "12-Mar-2016", ""),
    ("H-02", "Marcus Doyle", "marcus.doyle@harborviewbh.org", "Billing", "Billing Supervisor", "priya.ramanathan@harborviewbh.org", "Active", "04-Aug-2020", ""),
    ("H-03", "Dana Whitfield", "dana.whitfield@harborviewbh.org", "Outpatient", "Clinical Coordinator", "naomi.park@harborviewbh.org", "Active", "19-Feb-2019", ""),
    ("H-04", "Grace Liu", "grace.liu@harborviewbh.org", "Outpatient", "Care Manager", "naomi.park@harborviewbh.org", "Active", "23-Jul-2021", ""),
    ("H-05", "Tobias Reyes", "tobias.reyes@harborviewbh.org", "Outpatient", "Clinical Coordinator", "naomi.park@harborviewbh.org", "Active", "11-Jan-2022", ""),
    ("H-06", "Naomi Park", "naomi.park@harborviewbh.org", "Outpatient", "Program Director", "", "Active", "02-Sep-2013", ""),
    ("H-07", "Sam Okafor", "sam.okafor@harborviewbh.org", "Outpatient", "Care Manager", "naomi.park@harborviewbh.org", "Active", "15-May-2018", ""),
    ("H-08", "Sam Okafor", "s.okafor.contractor@harborviewbh.org", "Residential", "Care Manager (Contractor)", "warren.bell@harborviewbh.org", "Terminated", "01-Oct-2025", "12-Sep-2026"),
    ("H-09", "Warren Bell", "warren.bell@harborviewbh.org", "Residential", "Program Director", "", "Active", "07-Apr-2015", ""),
    ("H-10", "Ben Ferris", "ben.ferris@harborviewbh.org", "IT", "IT Manager", "", "Active", "20-Jun-2014", ""),
    ("H-11", "Alicia Munroe", "alicia.munroe@harborviewbh.org", "IT", "IT Support Analyst", "ben.ferris@harborviewbh.org", "Active", "09-Nov-2022", ""),
    ("H-12", "Renee Castillo", "renee.castillo@harborviewbh.org", "Compliance", "Compliance Officer", "", "Active", "03-Jan-2012", ""),
]

with open(COMPANY / "employee_master.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Staff No.", "Legal Name", "Corp Email Address", "Dept / Division", "Job Title / Role",
                "Line Manager Email", "Employee Status", "Start Date", "Separation Date"])
    for row in EMPLOYEES:
        w.writerow(row)


# --------------------------------------------------------------------------
# evidence/sheets/ - two dated ClinCareEHR UAR extracts
# --------------------------------------------------------------------------
def uar_row(account_id, name, email, profiles, status, last_login, snapshot_date):
    return [account_id, name, email, profiles, status, last_login, snapshot_date]

PERIOD_START = "2026-06-01"
PERIOD_END = "2026-09-14"

start_rows = [
    uar_row("CC-101", "Priya Ramanathan", "priya.ramanathan@harborviewbh.org", "Billing_Approver", "Active", "2026-05-30", PERIOD_START),
    uar_row("CC-102", "Marcus Doyle", "marcus.doyle@harborviewbh.org", "Billing_Clerk", "Active", "2026-05-29", PERIOD_START),
    uar_row("CC-103", "Dana Whitfield", "dana.whitfield@harborviewbh.org", "Clinician_User", "Active", "2026-05-28", PERIOD_START),
    uar_row("CC-104", "Grace Liu", "grace.liu@harborviewbh.org", "Clinician_User", "Active", "2026-05-27", PERIOD_START),
    uar_row("CC-105", "Tobias Reyes", "tobias.reyes@harborviewbh.org", "Clinician_User", "Active", "2026-05-31", PERIOD_START),
    uar_row("CC-106", "Naomi Park", "naomi.park@harborviewbh.org", "Clinician_Admin", "Active", "2026-05-30", PERIOD_START),
    uar_row("CC-107", "Sam Okafor", "sam.okafor@harborviewbh.org", "Clinician_User", "Active", "2026-05-26", PERIOD_START),
    uar_row("CC-108", "Sam Okafor", "s.okafor.contractor@harborviewbh.org", "Clinician_User", "Active", "2026-06-01", PERIOD_START),
    uar_row("CC-109", "Warren Bell", "warren.bell@harborviewbh.org", "Clinician_Admin", "Active", "2026-05-29", PERIOD_START),
    uar_row("CC-110", "Ben Ferris", "ben.ferris@harborviewbh.org", "IT_Admin, System_Admin", "Active", "2026-05-30", PERIOD_START),
    uar_row("CC-111", "Alicia Munroe", "alicia.munroe@harborviewbh.org", "IT_Admin", "Active", "2026-05-28", PERIOD_START),
    uar_row("CC-112", "Renee Castillo", "renee.castillo@harborviewbh.org", "ReadOnly", "Active", "2026-05-20", PERIOD_START),
    uar_row("SVC-201", "SVC-ClinCare-ETL", "", "System_Admin", "Active", "2026-05-30", PERIOD_START),
]

end_rows = [
    uar_row("CC-101", "Priya Ramanathan", "priya.ramanathan@harborviewbh.org", "Billing_Approver", "Active", "2026-09-10", PERIOD_END),
    uar_row("CC-102", "Marcus Doyle", "marcus.doyle@harborviewbh.org", "Billing_Clerk, Billing_Approver", "Active", "2026-09-12", PERIOD_END),
    uar_row("CC-103", "Dana Whitfield", "dana.whitfield@harborviewbh.org", "Clinician_User, PHI_Admin", "Active", "2026-09-11", PERIOD_END),
    uar_row("CC-104", "Grace Liu", "grace.liu@harborviewbh.org", "Clinician_User, PHI_Admin", "Active", "2026-09-09", PERIOD_END),
    uar_row("CC-105", "Tobias Reyes", "tobias.reyes@harborviewbh.org", "Clinician_User, PHI_Admin", "Active", "2026-09-13", PERIOD_END),
    uar_row("CC-106", "Naomi Park", "naomi.park@harborviewbh.org", "Clinician_Admin", "Active", "2026-09-10", PERIOD_END),
    uar_row("CC-107", "Sam Okafor", "sam.okafor@harborviewbh.org", "Clinician_User", "Active", "2026-09-08", PERIOD_END),
    uar_row("CC-108", "Sam Okafor", "s.okafor.contractor@harborviewbh.org", "Clinician_User", "Disabled", "2026-09-11", PERIOD_END),
    uar_row("CC-109", "Warren Bell", "warren.bell@harborviewbh.org", "Clinician_Admin", "Active", "2026-09-09", PERIOD_END),
    uar_row("CC-110", "Ben Ferris", "ben.ferris@harborviewbh.org", "IT_Admin, System_Admin", "Active", "2026-09-10", PERIOD_END),
    uar_row("CC-111", "Alicia Munroe", "alicia.munroe@harborviewbh.org", "IT_Admin", "Active", "2026-09-09", PERIOD_END),
    uar_row("CC-112", "Renee Castillo", "renee.castillo@harborviewbh.org", "ReadOnly", "Active", "2026-08-29", PERIOD_END),
    uar_row("SVC-201", "SVC-ClinCare-ETL", "", "System_Admin", "Active", "2026-09-12", PERIOD_END),
]

UAR_HEADER = ["Account ID", "User Full Name", "Email Address", "Access Profile(s)", "Account Status", "Last Login", "Snapshot Date"]

with open(SHEETS / f"ClinCareEHR_UAR_PeriodStart_{PERIOD_START}.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(UAR_HEADER); w.writerows(start_rows)

with open(SHEETS / f"ClinCareEHR_UAR_PeriodEnd_{PERIOD_END}.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(UAR_HEADER); w.writerows(end_rows)


# --------------------------------------------------------------------------
# evidence/servicedesk/
# --------------------------------------------------------------------------
TICKET_HEADER = ["Ticket #", "Requested By", "Approved By", "Application", "Access / Change Requested",
                  "Ticket Status", "Date Created", "Date Approved", "Date Implemented", "Implemented By"]

tickets = [
    # Marcus Doyle's promotion - explicitly says remove Billing_Clerk, but UAR shows it wasn't
    ["SD-3001", "priya.ramanathan@harborviewbh.org", "ben.ferris@harborviewbh.org",
     "ClinCareEHR", "Promote Marcus Doyle to Billing Supervisor: grant Billing_Approver, remove Billing_Clerk",
     "Closed", "2026-07-14", "2026-07-14", "2026-07-16", "ben.ferris@harborviewbh.org"],
    # Grace Liu's PHI_Admin - filed BY Alicia, "on behalf of" Grace - requester mismatch trap
    ["SD-3002", "alicia.munroe@harborviewbh.org", "renee.castillo@harborviewbh.org",
     "ClinCareEHR", "PHI_Admin for Grace Liu (filed on her behalf - she is travelling)",
     "Closed", "2026-08-01", "2026-08-02", "2026-08-04", "alicia.munroe@harborviewbh.org"],
    # Tobias Reyes's PHI_Admin - clean, correctly self-requested
    ["SD-3003", "tobias.reyes@harborviewbh.org", "renee.castillo@harborviewbh.org",
     "ClinCareEHR", "PHI_Admin - needed for new record-export duties",
     "Closed", "2026-08-20", "2026-08-21", "2026-08-22", "alicia.munroe@harborviewbh.org"],
    # Contractor Sam Okafor's deprovisioning
    ["SD-3004", "warren.bell@harborviewbh.org", "warren.bell@harborviewbh.org",
     "ClinCareEHR", "Disable Sam Okafor ClinCareEHR access - contract ended",
     "Closed", "2026-09-11", "2026-09-11", "2026-09-11", "ben.ferris@harborviewbh.org"],
]

with open(SERVICEDESK / "clincare_servicedesk_export.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(TICKET_HEADER); w.writerows(tickets)


# --------------------------------------------------------------------------
# evidence/email/
# --------------------------------------------------------------------------
def write_email(fname, frm, to, date, subject, body, cc=None):
    lines = [f"From: {frm}", f"To: {to}"]
    if cc:
        lines.append(f"Cc: {cc}")
    lines += [f"Date: {date}", f"Subject: {subject}", "", body]
    (EMAIL / fname).write_text("\n".join(lines) + "\n", encoding="utf-8")

write_email(
    "email_01_marcus_promotion_followup.txt",
    "Priya Ramanathan <priya.ramanathan@harborviewbh.org>",
    "Ben Ferris <ben.ferris@harborviewbh.org>",
    "20-Jul-2026",
    "Re: Marcus Doyle promotion - please confirm old profile removed",
    "Ben,\n\n"
    "Following up on SD-3001 - can you confirm Marcus's old Billing_Clerk\n"
    "profile was actually removed as part of the Billing_Approver grant?\n"
    "He shouldn't be holding both once he's the one approving his own team's\n"
    "entries.\n\nPriya",
)

write_email(
    "email_02_sam_okafor_termination.txt",
    "Warren Bell <warren.bell@harborviewbh.org>",
    "Ben Ferris <ben.ferris@harborviewbh.org>",
    "11-Sep-2026",
    "Access removal - Sam's last day was Friday",
    "Ben,\n\n"
    "Sam's contract wrapped up - his last day was Friday. Please disable his\n"
    "ClinCareEHR access today if it hasn't happened already.\n\nWarren",
)

write_email(
    "email_03_svc_account_ownership.txt",
    "Renee Castillo <renee.castillo@harborviewbh.org>",
    "Ben Ferris <ben.ferris@harborviewbh.org>",
    "05-Aug-2026",
    "SVC-ClinCare-ETL - compliance register entry",
    "Ben,\n\n"
    "For the record since this comes up on every UAR: SVC-ClinCare-ETL is the\n"
    "nightly claims-extract job. It's never been an HR-tracked identity - it's\n"
    "listed in the compliance register (entry CR-2019-014) with System_Admin\n"
    "as required for the ETL role, and I personally recertify it every January\n"
    "as part of the annual privileged-access review. It doesn't have an HR\n"
    "record because it was never meant to be a person.\n\nRenee",
)

write_email(
    "email_04_grace_liu_phi_admin_context.txt",
    "Alicia Munroe <alicia.munroe@harborviewbh.org>",
    "Renee Castillo <renee.castillo@harborviewbh.org>",
    "01-Aug-2026",
    "Filed SD-3002 for Grace Liu on her behalf",
    "Renee,\n\n"
    "Grace is on leave in the field this week with no laptop access, so I\n"
    "filed SD-3002 for her PHI_Admin grant on her behalf - you and I discussed\n"
    "and you verbally approved by phone on Friday, this is just confirming\n"
    "that in writing for the ticket record. Let me know if you want her to\n"
    "re-confirm in writing herself once she's back.\n\nAlicia",
)


# --------------------------------------------------------------------------
# ANSWER_KEY_PRIVATE.md and README.md
# --------------------------------------------------------------------------
answer_key = """# Harborview Behavioral Health - ClinCareEHR (hard scenario) - ANSWER KEY

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

    python3 scripts/run_pipeline.py \\
        --company data/test_scenarios/harborview_uar_period_hard/company \\
        --evidence data/test_scenarios/harborview_uar_period_hard/evidence \\
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
"""
(BASE / "ANSWER_KEY_PRIVATE.md").write_text(answer_key, encoding="utf-8")

readme = """# Harborview Behavioral Health - ClinCareEHR (hard scenario)

Third standalone test scenario, deliberately different in shape from
data/test_scenarios/meridian_uar_hard/ and
data/test_scenarios/solstice_jml_sod_hard/. Not used by any test, not
imported by any code.

Centerpiece: TWO DATED UAR EXTRACTS (period-start and period-end) for the
same system, exercising src/itgc/tests_itgc/uar_period_diff.py - and a
deliberate false positive in that same check, to test whether a reviewer
trusts an automated finding without reading the underlying evidence.

## Folder layout

    company/
      employee_master.csv
      role_access_matrix.yaml
      company_context.yaml
    evidence/
      sheets/
        ClinCareEHR_UAR_PeriodStart_2026-06-01.csv
        ClinCareEHR_UAR_PeriodEnd_2026-09-14.csv
      servicedesk/
        clincare_servicedesk_export.csv
      email/
        email_01..04_*.txt

ANSWER_KEY_PRIVATE.md - not read by any code; for self-grading.

## How to use it

    python3 scripts/run_pipeline.py \\
        --company data/test_scenarios/harborview_uar_period_hard/company \\
        --evidence data/test_scenarios/harborview_uar_period_hard/evidence \\
        --as-of 2026-09-14 --no-llm

Work the case from the raw evidence first - read both UAR extracts, the
ticket export, and all four emails - before checking your own conclusions
against ANSWER_KEY_PRIVATE.md or the pipeline's own output.
"""
(BASE / "README.md").write_text(readme, encoding="utf-8")

print("Harborview hard scenario written to:", BASE)
