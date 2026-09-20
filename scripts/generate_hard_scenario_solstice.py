"""
Generates "Solstice Freight & Logistics Ltd" - a second, standalone hard/
adversarial ITGC test scenario, DELIBERATELY DIFFERENT IN SHAPE from the
Meridian Textiles UAR scenario (data/test_scenarios/meridian_uar_hard/).

Same ground rules as Meridian: this script and its output are not imported,
not run by any test, and not read by src/itgc. Pure evidence, for testing
ingestion/correlation intelligence by hand.

Where Meridian was an email-driven "retain/revoke" UAR campaign across 5
managers with zero ticket evidence, this scenario is ticket-driven (service
desk export is the primary evidence, not email) and targets a different mix
of control failures: a role change ("mover") whose old access was never
revoked, a contractor-to-permanent conversion across two completely
different email domains, a self-approved privileged grant, an approval
recorded after the access was already implemented, an unowned service
account masquerading as a normal UAR row, a terminated employee whose
access was never disabled, and two DIFFERENT REAL PEOPLE WHO SHARE THE SAME
FULL NAME (not just a first name, as in Meridian) in two different
departments - a harder identity-resolution trap than Meridian's, since a
naive fuzzy-name match would consider both an equally good "exact" hit and
has to fall back to department/manager context to tell them apart.

Planted, on purpose:
  - MOVER, ACCESS NOT REVOKED: David Ferreira is promoted from AP Clerk to
    AP Approver. The promotion ticket explicitly instructs "also remove the
    AP_Clerk profile", and a follow-up email from his director repeats that
    instruction independently - but the UAR export still shows him holding
    BOTH profiles, an active SoD conflict the existing role-based SoD check
    should catch automatically, with two independent pieces of evidence
    (ticket text + email) confirming it was known and should not exist.
  - CONTRACTOR TO PERMANENT CONVERSION ACROSS DOMAINS: Priya Chandran was a
    contractor (account C-0090, external email on a different domain),
    terminated and immediately converted to a permanent employee (new
    employee ID, new corporate email). Both her old and new access are
    properly ticketed and the old account is correctly disabled - a clean
    resolution, but only recognizable as clean if the two HR records are
    correctly linked as the same real person across two unrelated emails
    and IDs, rather than being treated as two unconnected identities or,
    worse, as a data inconsistency.
  - TWO "JAMES WALSH"s: an Operations Manager and, separately, a Warehouse
    Manager, in different departments with different email addresses. An
    informal email about a verbally-approved access grant just says "James
    Walsh approved it" with no department given - resolvable only by
    checking which James Walsh is actually the requester's manager on
    record, not by name-matching alone.
  - UNOWNED SERVICE ACCOUNT: an active, privileged UAR row
    (SVC-CargoLink-Batch) with no corresponding employee record at all -
    flagged as an orphan account, and a separate email shows IT itself does
    not know who owns it either - an open item, not a confirmed incident.
  - SELF-APPROVED PRIVILEGED GRANT: a warehouse supervisor requests and
    approves his own elevated access, corroborated independently by an
    unrelated HR email that separately noticed the same irregularity.
  - APPROVAL RECORDED AFTER IMPLEMENTATION: a stocktake-support grant was
    implemented, then "approved" two days later.
  - LEAVER ACCESS NEVER DISABLED: a warehouse stock controller who left the
    company months ago still shows an active account - the one item this
    scenario shares in spirit with Meridian's Anitha Verma case, included on
    purpose as a repeatable sanity check that the existing JML rule still
    works on a second, differently-shaped company.
  - VAGUE NEW-STARTER EMAIL: IT mentions granting access "for the new
    starter joining Ops this week" without a name, while TWO new starters
    joined Ops around the same time - one of whom already has an untracked
    access grant, the other has none at all yet. Genuinely underdetermined
    from the email alone.
  - Ordinary messy-evidence mechanics, deliberately different from
    Meridian's choices: a differently-worded CSV header set for the
    employee master, a banner block AND a stray commentary row in the UAR
    workbook, and a service-desk CSV with its own distinct (but still
    schema-alias-compatible) header wording.

Run: python3 scripts/generate_hard_scenario_solstice.py
"""
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "test_scenarios" / "solstice_jml_sod_hard"
COMPANY = BASE / "company"
SHEETS = BASE / "evidence" / "sheets"
SD = BASE / "evidence" / "servicedesk"
EMAIL = BASE / "evidence" / "email"

for d in (COMPANY, SHEETS, SD, EMAIL):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Employee master
# (emp_id, full_name, email, department, job_title, manager_email, status,
#  hire_date, term_date). Dates avoid ambiguous DD/MM day values (<=12) on
# purpose, same discipline as the Meridian dataset.
# ---------------------------------------------------------------------------
EMPLOYEES = [
    ("E-1001", "Grace Whitfield", "grace.whitfield@solsticefreight.co.uk", "Finance",    "Finance Director",                  None,                                       "Active",     "14-Feb-2014", None),
    ("E-1002", "David Ferreira",  "david.ferreira@solsticefreight.co.uk",  "Finance",    "AP Approver",                       "grace.whitfield@solsticefreight.co.uk",   "Active",     "21-Jun-2019", None),
    ("E-1003", "Helen Osei",      "helen.osei@solsticefreight.co.uk",      "Finance",    "AP Clerk",                          "grace.whitfield@solsticefreight.co.uk",   "Active",     "18-Sep-2020", None),
    ("E-1004", "Marcus Webb",     "marcus.webb@solsticefreight.co.uk",     "Finance",    "Financial Analyst",                 "grace.whitfield@solsticefreight.co.uk",   "Active",     "23-Jan-2021", None),
    ("E-1010", "James Walsh",     "james.walsh@solsticefreight.co.uk",     "Operations", "Operations Manager",                None,                                       "Active",     "19-Mar-2013", None),
    ("E-1011", "Chloe Bennett",   "chloe.bennett@solsticefreight.co.uk",   "Operations", "Dispatch Coordinator",              "james.walsh@solsticefreight.co.uk",       "Active",     "27-Aug-2021", None),
    ("E-1012", "Ola Adeyemi",     "ola.adeyemi@solsticefreight.co.uk",     "Operations", "Route Planner",                     "james.walsh@solsticefreight.co.uk",       "Active",     "30-Oct-2022", None),
    ("E-1050", "Anna Kowalczyk",  "anna.kowalczyk@solsticefreight.co.uk",  "Operations", "Customer Service Rep",              "james.walsh@solsticefreight.co.uk",       "Active",     "20-Aug-2026", None),
    ("E-1051", "Farid Rahman",    "farid.rahman@solsticefreight.co.uk",    "Operations", "Customer Service Rep",              "james.walsh@solsticefreight.co.uk",       "Active",     "22-Aug-2026", None),
    ("E-1020", "James Walsh",     "j.walsh@solsticefreight.co.uk",         "Warehouse",  "Warehouse Manager",                 None,                                       "Active",     "16-Nov-2015", None),
    ("E-1021", "Tariq Hussain",   "tariq.hussain@solsticefreight.co.uk",   "Warehouse",  "Warehouse Supervisor",              "j.walsh@solsticefreight.co.uk",           "Active",     "24-Apr-2018", None),
    ("E-1022", "Nadia Kowalski",  "nadia.kowalski@solsticefreight.co.uk",  "Warehouse",  "Stock Controller",                  "j.walsh@solsticefreight.co.uk",           "Active",     "19-Dec-2022", None),
    ("E-1023", "Ivy Chen",        "ivy.chen@solsticefreight.co.uk",        "Warehouse",  "Stock Controller",                  "j.walsh@solsticefreight.co.uk",           "Terminated", "18-May-2021", "20-Jun-2026"),
    ("E-1030", "Ben Sackey",      "ben.sackey@solsticefreight.co.uk",      "IT",         "IT Manager",                        None,                                       "Active",     "15-May-2012", None),
    ("E-1031", "Priya Chandran",  "priya.chandran@solsticefreight.co.uk",  "IT",         "IT Support Analyst",                "ben.sackey@solsticefreight.co.uk",        "Active",     "20-Aug-2026", None),
    ("E-1032", "Tom Fitzgerald",  "tom.fitzgerald@solsticefreight.co.uk",  "IT",         "IT Security Officer",               "ben.sackey@solsticefreight.co.uk",        "Active",     "28-Feb-2017", None),
    ("E-1040", "Lucy Adjei",      "lucy.adjei@solsticefreight.co.uk",      "HR",         "HR Manager",                        None,                                       "Active",     "17-Jun-2011", None),
    ("E-1041", "Samuel Owusu",    "samuel.owusu@solsticefreight.co.uk",    "HR",         "HR Advisor",                        "lucy.adjei@solsticefreight.co.uk",        "Active",     "25-Jul-2019", None),
    ("C-0090", "Priya Chandran",  "priya.freelance@extmail.co.uk",         "IT",         "IT Support Analyst (Contractor)",   "ben.sackey@solsticefreight.co.uk",        "Terminated", "14-Jan-2026", "15-Aug-2026"),
]

# ---------------------------------------------------------------------------
# 1. Employee master - messy CSV, header wording different from both ACME
#    and Meridian on purpose.
# ---------------------------------------------------------------------------
emp_csv_lines = [
    "Staff No.,Legal Name,Corp Email Address,Dept / Division,Job Title / Role,Line Manager Email,Employee Status,Start Date,Separation Date"
]
for row in EMPLOYEES:
    emp_id, name, email, dept, title, mgr, status, hire, term = row
    emp_csv_lines.append(f"{emp_id},{name},{email},{dept},{title},{mgr or ''},{status},{hire},{term or ''}")
(COMPANY / "employee_master.csv").write_text("\n".join(emp_csv_lines) + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# 2. role_access_matrix.yaml / company_context.yaml - conforms to the real
#    load_policy() schema from the start this time.
# ---------------------------------------------------------------------------
(COMPANY / "role_access_matrix.yaml").write_text(
    """applications:
  CargoLink TMS:
    sensitivity: high
    profiles:
    - Ops_User
    - Ops_Admin
    - Dispatch_User
    - Warehouse_User
    - Warehouse_Admin
    - AP_Clerk
    - AP_Approver
    - Finance_ReadOnly
    - IT_Admin
    - System_Admin
    - Security_Admin
    - HR_User
    sod_conflicts:
    - - AP_Clerk
      - AP_Approver
    role_to_profile:
      Finance Director:
      - Finance_ReadOnly
      AP Approver:
      - AP_Approver
      AP Clerk:
      - AP_Clerk
      Financial Analyst:
      - Finance_ReadOnly
      Operations Manager:
      - Ops_Admin
      Dispatch Coordinator:
      - Dispatch_User
      Route Planner:
      - Ops_User
      Customer Service Rep:
      - Ops_User
      Warehouse Manager:
      - Warehouse_Admin
      Warehouse Supervisor:
      - Warehouse_User
      Stock Controller:
      - Warehouse_User
      IT Manager:
      - IT_Admin
      - System_Admin
      IT Support Analyst:
      - IT_Admin
      IT Support Analyst (Contractor):
      - IT_Admin
      IT Security Officer:
      - Security_Admin
      - IT_Admin
      HR Manager:
      - HR_User
      HR Advisor:
      - HR_User
deprovisioning_sla_days: 5
dormant_threshold_days: 90
joiner_provisioning_sla_days: 10
uar_review_period: 2026-Q3
""",
    encoding="utf-8",
)

(COMPANY / "company_context.yaml").write_text(
    """company: Solstice Freight & Logistics Ltd
engagement: CargoLink TMS - ITGC review (JML, SoD, provisioning evidence)
in_scope_applications:
- CargoLink TMS
policy_reference: SFL-ITGC-POL-02 Access Management Policy v3.0
sod_policy_reference: SFL-ITGC-POL-05 Segregation of Duties Policy
industry: Road freight and logistics
notes: >
  Evidence for this engagement is a service-desk ticket export, a CargoLink
  TMS access (UAR) export, and ad hoc email correspondence between IT, HR
  and department heads - there was no formal review campaign run for this
  cycle, unlike a typical quarterly UAR; the tickets and emails are simply
  whatever normal operational trail exists.
""",
    encoding="utf-8",
)

# ---------------------------------------------------------------------------
# 3. CargoLink TMS access export (UAR sheet) - xlsx, its own messy mechanics:
#    a banner block, a stray free-text commentary row buried in the data
#    (not just before it, unlike Meridian's blank-row placement), and
#    header wording distinct from both prior datasets.
# ---------------------------------------------------------------------------
# (account_id, account_name, account_email, profiles, account_status, last_login)
UAR_ROWS = [
    ("E-1001", "Grace Whitfield", "grace.whitfield@solsticefreight.co.uk", "Finance_ReadOnly",              "Active",   "15-Sep-2026"),
    ("E-1002", "David Ferreira",  "david.ferreira@solsticefreight.co.uk",  "AP_Approver, AP_Clerk",         "Active",   "16-Sep-2026"),
    ("E-1003", "Helen Osei",      "helen.osei@solsticefreight.co.uk",      "AP_Clerk",                      "Active",   "16-Sep-2026"),
    ("E-1004", "Marcus Webb",     "marcus.webb@solsticefreight.co.uk",     "Finance_ReadOnly",              "Active",   "14-Sep-2026"),
    ("E-1010", "James Walsh",     "james.walsh@solsticefreight.co.uk",     "Ops_Admin",                     "Active",   "17-Sep-2026"),
    ("E-1011", "Chloe Bennett",   "chloe.bennett@solsticefreight.co.uk",   "Dispatch_User",                 "Active",   "17-Sep-2026"),
    ("E-1012", "Ola Adeyemi",     "ola.adeyemi@solsticefreight.co.uk",     "Ops_User, Ops_Admin",           "Active",   "16-Sep-2026"),
    ("E-1050", "Anna Kowalczyk",  "anna.kowalczyk@solsticefreight.co.uk",  "Ops_User",                      "Active",   "10-Sep-2026"),
    ("E-1020", "James Walsh",     "j.walsh@solsticefreight.co.uk",         "Warehouse_Admin",               "Active",   "17-Sep-2026"),
    ("E-1021", "Tariq Hussain",   "tariq.hussain@solsticefreight.co.uk",   "Warehouse_Admin",               "Active",   "16-Sep-2026"),
    ("E-1022", "Nadia Kowalski",  "nadia.kowalski@solsticefreight.co.uk",  "Warehouse_Admin",               "Active",   "15-Sep-2026"),
    ("E-1023", "Ivy Chen",        "ivy.chen@solsticefreight.co.uk",        "Warehouse_User",                "Active",   "18-Jun-2026"),
    ("E-1030", "Ben Sackey",      "ben.sackey@solsticefreight.co.uk",      "IT_Admin, System_Admin",        "Active",   "18-Sep-2026"),
    ("E-1031", "Priya Chandran",  "priya.chandran@solsticefreight.co.uk",  "IT_Admin",                      "Active",   "18-Sep-2026"),
    ("C-0090", "Priya Chandran",  "priya.freelance@extmail.co.uk",         "IT_Admin",                      "Disabled", "14-Aug-2026"),
    ("E-1032", "Tom Fitzgerald",  "tom.fitzgerald@solsticefreight.co.uk",  "Security_Admin, IT_Admin",      "Active",   "18-Sep-2026"),
    ("E-1040", "Lucy Adjei",      "lucy.adjei@solsticefreight.co.uk",      "HR_User",                       "Active",   "17-Sep-2026"),
    ("E-1041", "Samuel Owusu",    "samuel.owusu@solsticefreight.co.uk",    "HR_User",                       "Active",   "16-Sep-2026"),
    ("SVC-0001", "SVC-CargoLink-Batch", "svc-cargolink-batch@solsticefreight.co.uk", "System_Admin",        "Active",   "18-Sep-2026"),
]


def write_uar_sheet():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CargoLink TMS Access"
    ws["A1"] = "Solstice Freight & Logistics Ltd - CargoLink TMS - Active User Export"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = "Extracted from CargoLink TMS admin console on 18-Sep-2026"
    ws.append([])
    headers = ["Account Ref", "User Display Name", "Email", "Access Roles Held", "Status", "Last Sign-in"]
    ws.append(headers)  # row 4
    row_i = 5
    for i, r in enumerate(UAR_ROWS):
        ws.append(list(r))
        row_i += 1
        # A stray commentary row buried partway through the export, the way
        # someone pastes a note into a live workbook without thinking about
        # what a downstream parser will do with it - not at the top like a
        # banner, and not a clean blank row like Meridian's.
        if i == 9:
            ws.append(["NOTE:", "IT to re-run this export after the September change freeze ends", "", "", "", ""])
            row_i += 1
    wb.save(SHEETS / "cargolink_tms_active_users.xlsx")


write_uar_sheet()

# ---------------------------------------------------------------------------
# 4. Service desk ticket export - CSV, header wording distinct from both
#    ACME and Meridian but still alias-compatible with SERVICEDESK_SCHEMA.
# ---------------------------------------------------------------------------
SD_HEADERS = ["Request ID", "Raised By", "Approved By", "Application", "Description",
              "Ticket Status", "Raised Date", "Approved Date", "Implemented Date", "Implemented By"]

TICKETS = [
    # -- special / planted --
    ("T-3001", "david.ferreira@solsticefreight.co.uk", "grace.whitfield@solsticefreight.co.uk", "CargoLink TMS",
     "Grant AP_Approver profile (promotion to AP Approver); also remove existing AP_Clerk profile as this role change supersedes it.",
     "Closed", "10-Jul-2026", "12-Jul-2026", "15-Jul-2026", "ben.sackey@solsticefreight.co.uk"),
    ("T-3002", "priya.chandran@solsticefreight.co.uk", "ben.sackey@solsticefreight.co.uk", "CargoLink TMS",
     "New starter - grant IT_Admin profile (converted from IT contractor, previous account C-0090).",
     "Closed", "18-Aug-2026", "19-Aug-2026", "20-Aug-2026", "tom.fitzgerald@solsticefreight.co.uk"),
    ("T-3003", "lucy.adjei@solsticefreight.co.uk", "ben.sackey@solsticefreight.co.uk", "CargoLink TMS",
     "Disable contractor account C-0090 (Priya Chandran) - contract ended; she has converted to permanent employee under new ID E-1031.",
     "Closed", "14-Aug-2026", "15-Aug-2026", "15-Aug-2026", "tom.fitzgerald@solsticefreight.co.uk"),
    ("T-3004", "tariq.hussain@solsticefreight.co.uk", "tariq.hussain@solsticefreight.co.uk", "CargoLink TMS",
     "Grant Warehouse_Admin profile - covering warehouse manager duties while J. Walsh is on leave.",
     "Closed", "05-Sep-2026", "05-Sep-2026", "06-Sep-2026", "ben.sackey@solsticefreight.co.uk"),
    ("T-3005", "nadia.kowalski@solsticefreight.co.uk", "j.walsh@solsticefreight.co.uk", "CargoLink TMS",
     "Grant Warehouse_Admin profile - urgent stocktake support.",
     "Closed", "01-Sep-2026", "04-Sep-2026", "02-Sep-2026", "ben.sackey@solsticefreight.co.uk"),
    # -- baseline / clean, to keep signal-to-noise high rather than flooding
    #    every account with MISSING_APPROVAL_EVIDENCE the way an evidence
    #    set with zero tickets would --
    ("T-3010", "grace.whitfield@solsticefreight.co.uk", "ben.sackey@solsticefreight.co.uk", "CargoLink TMS",
     "Grant Finance_ReadOnly profile.", "Closed", "20-Feb-2014", "21-Feb-2014", "24-Feb-2014", "ben.sackey@solsticefreight.co.uk"),
    ("T-3011", "helen.osei@solsticefreight.co.uk", "grace.whitfield@solsticefreight.co.uk", "CargoLink TMS",
     "Grant AP_Clerk profile.", "Closed", "20-Sep-2020", "21-Sep-2020", "23-Sep-2020", "ben.sackey@solsticefreight.co.uk"),
    ("T-3012", "marcus.webb@solsticefreight.co.uk", "grace.whitfield@solsticefreight.co.uk", "CargoLink TMS",
     "Grant Finance_ReadOnly profile.", "Closed", "25-Jan-2021", "26-Jan-2021", "28-Jan-2021", "ben.sackey@solsticefreight.co.uk"),
    ("T-3013", "james.walsh@solsticefreight.co.uk", "ben.sackey@solsticefreight.co.uk", "CargoLink TMS",
     "Grant Ops_Admin profile.", "Closed", "22-Mar-2013", "23-Mar-2013", "25-Mar-2013", "ben.sackey@solsticefreight.co.uk"),
    ("T-3015", "j.walsh@solsticefreight.co.uk", "ben.sackey@solsticefreight.co.uk", "CargoLink TMS",
     "Grant Warehouse_Admin profile.", "Closed", "18-Nov-2015", "19-Nov-2015", "21-Nov-2015", "ben.sackey@solsticefreight.co.uk"),
    ("T-3016", "ben.sackey@solsticefreight.co.uk", "grace.whitfield@solsticefreight.co.uk", "CargoLink TMS",
     "Grant IT_Admin and System_Admin profiles.", "Closed", "18-May-2012", "19-May-2012", "21-May-2012", "tom.fitzgerald@solsticefreight.co.uk"),
    ("T-3017", "tom.fitzgerald@solsticefreight.co.uk", "ben.sackey@solsticefreight.co.uk", "CargoLink TMS",
     "Grant Security_Admin and IT_Admin profiles.", "Closed", "02-Mar-2017", "03-Mar-2017", "05-Mar-2017", "ben.sackey@solsticefreight.co.uk"),
    ("T-3018", "lucy.adjei@solsticefreight.co.uk", "ben.sackey@solsticefreight.co.uk", "CargoLink TMS",
     "Grant HR_User profile.", "Closed", "20-Jun-2011", "21-Jun-2011", "23-Jun-2011", "ben.sackey@solsticefreight.co.uk"),
    ("T-3019", "samuel.owusu@solsticefreight.co.uk", "lucy.adjei@solsticefreight.co.uk", "CargoLink TMS",
     "Grant HR_User profile.", "Closed", "28-Jul-2019", "29-Jul-2019", "31-Jul-2019", "ben.sackey@solsticefreight.co.uk"),
    ("T-3020", "ola.adeyemi@solsticefreight.co.uk", "james.walsh@solsticefreight.co.uk", "CargoLink TMS",
     "Grant Ops_User profile.", "Closed", "02-Nov-2022", "03-Nov-2022", "05-Nov-2022", "ben.sackey@solsticefreight.co.uk"),
    # Deliberately no ticket at all for: Chloe Bennett's Dispatch_User (verbal
    # approval only, see email evidence), Anna Kowalczyk's Ops_User (untracked
    # new-starter grant, see email evidence), or Ola Adeyemi's second profile
    # Ops_Admin (excess access with zero evidence of any kind).
]

sd_lines = [",".join(SD_HEADERS)]
for t in TICKETS:
    # quote the free-text description field since it may contain commas
    row = list(t)
    row[4] = '"' + row[4].replace('"', '""') + '"'
    sd_lines.append(",".join(row))
(SD / "cargolink_servicedesk_export.csv").write_text("\n".join(sd_lines) + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# 5. Emails
# ---------------------------------------------------------------------------
email_01 = """From: Tom Fitzgerald <tom.fitzgerald@solsticefreight.co.uk>
To: Ben Sackey <ben.sackey@solsticefreight.co.uk>
Date: 12-Sep-2026
Subject: Unrecognised account in CargoLink - SVC-CargoLink-Batch

Ben,

Doing a routine privileged-access sweep and I keep coming across
SVC-CargoLink-Batch - it's got System_Admin and it's clearly been active
recently, but I can't find it in our HR list or in any onboarding ticket.
Do you know what this is for, or who owns it? If it's a legitimate batch
job account it really needs a named owner on file.

Tom
"""

email_02 = """From: Grace Whitfield <grace.whitfield@solsticefreight.co.uk>
To: Ben Sackey <ben.sackey@solsticefreight.co.uk>
Cc: David Ferreira <david.ferreira@solsticefreight.co.uk>
Date: 09-Jul-2026
Subject: David's promotion - CargoLink access change

Hi Ben,

Ahead of the ticket David's about to raise - just confirming from my side
that as part of his promotion to AP Approver, his existing AP_Clerk profile
should come off entirely. He shouldn't be holding both once this goes
through, for obvious segregation-of-duties reasons.

Thanks,
Grace
"""

email_03 = """From: Ben Sackey <ben.sackey@solsticefreight.co.uk>
To: Ops Team <ops-team@solsticefreight.co.uk>
Date: 09-Sep-2026
Subject: Quick favour - CargoLink access for the new starter

Hi all,

Can someone confirm CargoLink Ops_User access is sorted for the new starter
joining Ops this week? I think I actioned it already but forgot to log a
proper ticket for it - will backfill the paperwork once I track down which
one I did.

Thanks,
Ben
"""

email_04 = """From: Lucy Adjei <lucy.adjei@solsticefreight.co.uk>
To: Ben Sackey <ben.sackey@solsticefreight.co.uk>
Date: 13-Aug-2026
Subject: Priya Chandran - contractor to permanent

Hi Ben,

Confirming from HR's side: Priya Chandran's contract (account C-0090) ends
15-Aug, and she starts as a permanent IT Support Analyst on 20-Aug under a
new employee ID (E-1031) and her new corporate email. Please make sure her
old contractor account is fully disabled and her new starter access is set
up separately - don't just re-point the old account, as the auditors flagged
that as an issue for a different contractor last year.

Thanks,
Lucy
"""

email_05 = """From: Ben Sackey <ben.sackey@solsticefreight.co.uk>
To: Lucy Adjei <lucy.adjei@solsticefreight.co.uk>
Date: 15-Aug-2026
Subject: RE: Priya Chandran - contractor to permanent

Hi Lucy,

Confirmed both sides - old contractor account C-0090 disabled today
(ticket T-3003), and her new IT_Admin access under E-1031 will go through
as a separate new-starter ticket once she's actually started (T-3002).

Ben
"""

email_06 = """From: Chloe Bennett <chloe.bennett@solsticefreight.co.uk>
To: Ben Sackey <ben.sackey@solsticefreight.co.uk>
Date: 10-Sep-2026
Subject: Dispatch access - forgot to raise a ticket

Hi Ben,

Just a heads up - James Walsh approved my CargoLink dispatch access over a
call last week since it was needed urgently for a client go-live, but I
don't think either of us actually logged a ticket for it. Could you log it
retrospectively when you get a chance? Sorry for the mess.

Thanks,
Chloe
"""

email_07 = """From: Lucy Adjei <lucy.adjei@solsticefreight.co.uk>
To: Ben Sackey <ben.sackey@solsticefreight.co.uk>
Date: 08-Sep-2026
Subject: Something odd in last month's access requests

Hi Ben,

Not sure if this is a data entry issue or not, but I was skimming last
month's CargoLink requests for an unrelated reason and noticed Tariq
Hussain's Warehouse_Admin request (T-3004) shows him as both the requester
and the approver. Can you check whether that's really what happened, or
just a mistake in how it was logged?

Thanks,
Lucy
"""

for fname, content in [
    ("email_01_tom_flags_service_account.txt", email_01),
    ("email_02_grace_confirms_removal_instruction.txt", email_02),
    ("email_03_ben_vague_new_starter_request.txt", email_03),
    ("email_04_lucy_priya_conversion.txt", email_04),
    ("email_05_ben_confirms_priya_conversion.txt", email_05),
    ("email_06_chloe_verbal_approval_no_ticket.txt", email_06),
    ("email_07_lucy_flags_tariq_self_approval.txt", email_07),
]:
    (EMAIL / fname).write_text(content, encoding="utf-8")

# ---------------------------------------------------------------------------
# 6. Private answer key
# ---------------------------------------------------------------------------
answer_key = """# Solstice Freight & Logistics Ltd - CargoLink TMS (hard scenario) - ANSWER KEY

Private, self-grading reference only. Not read by any code. See
data/test_scenarios/meridian_uar_hard/ANSWER_KEY_PRIVATE.md for the same
disclaimer in more detail - it all applies here too.

This scenario is ticket-driven (unlike Meridian, which was email-driven with
zero tickets), so more of it is automatable through the existing engine -
but several items still require reading the email evidence and correlating
it against the tickets and the UAR export by hand.

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
"""
(BASE / "ANSWER_KEY_PRIVATE.md").write_text(answer_key, encoding="utf-8")

readme = """# Solstice Freight & Logistics Ltd - CargoLink TMS (hard scenario)

Second standalone test scenario, deliberately different in shape from
data/test_scenarios/meridian_uar_hard/. Not used by any test, not imported
by any code.

## Folder layout

    company/
      employee_master.csv
      role_access_matrix.yaml
      company_context.yaml
    evidence/
      sheets/
        cargolink_tms_active_users.xlsx
      servicedesk/
        cargolink_servicedesk_export.csv
      email/
        email_01..07_*.txt

ANSWER_KEY_PRIVATE.md - not read by any code; for self-grading.

## How to use it

Point the tool at company/ + evidence/ the same way as the ACME sample or
the Meridian scenario, run it, then read the seven emails alongside the
ticket export and UAR sheet before checking your own conclusions against
ANSWER_KEY_PRIVATE.md. Roughly half of the planted issues are caught by the
existing automated rules on their own; the rest require reading the emails
and correlating them by hand - there is no shortcut through the ticket data
alone for those.
"""
(BASE / "README.md").write_text(readme, encoding="utf-8")

print("Solstice hard scenario written to:", BASE)
