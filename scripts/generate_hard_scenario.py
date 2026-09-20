"""
Generates "Meridian Textiles Pvt Ltd" - a standalone, deliberately HARD and
CONFUSING User Access Review (UAR) test scenario for Horizon ERP.

THIS SCRIPT AND ITS OUTPUT HAVE NO CONNECTION TO THE MAIN PIPELINE, THE
ITGC TEST MODULES, OR ANY UNIT TEST. It is not imported anywhere, it is not
run by any test, and nothing in src/itgc reads from
data/test_scenarios/meridian_uar_hard/. It exists purely so a human (or a
future, separately-invoked instance of the tool) can be handed a folder of
raw evidence - an employee list, two access sheets, and a real-looking email
chain - and be tested on whether they can actually work the case, the way a
real audit engagement would land on someone's desk with no format guarantees
and no answer key attached.

The confusion is intentional and each piece is enumerated in
ANSWER_KEY_PRIVATE.md (which is not read by anything either - it's for a
human to grade themselves against). Specifically the dataset plants:

  - Two employees who share a first name ("Rahul Menon" in Production vs.
    "Rahul Nair" in Sales) so a manager's email that just says "revoke
    Rahul's access" is only disambiguated by cross-referencing which Rahul
    actually reports to that manager.
  - Two employees who share the name "Meena" (Meena Krishnan, and Meenakshi
    Iyer who goes by "Meena") who BOTH report to the same manager, so
    "revoke Meena's access" from that manager genuinely cannot be resolved
    from the email alone - the correct auditor behaviour is to flag it as
    an open item requiring enquiry, not to guess.
  - An employee referenced only by employee ID ("MT-0013") with no name.
  - A manager instructing revocation for MT-0013, who does not report to
    that manager at all - an out-of-authority instruction that a control-
    minded reviewer should question independently of whether it was correct.
  - A superseding correction email that reverses part of an earlier
    instruction - the final, later email is the one that governs.
  - A moot/redundant instruction about an employee who had already been
    terminated before the review even started.
  - A vague "that contractor we discussed" reference with no name, resolvable
    only because there happens to be exactly one contractor company-wide.
  - A legitimate new joiner who only appears in the AFTER sheet (added
    mid-cycle with a proper approval) - a distractor that looks like a rogue
    new account but isn't.
  - Deliberately messy spreadsheet mechanics: inconsistent column headers
    across sheets (including one light typo, "Acount Status"), a duplicate
    row, and a blank row.

Run: python3 scripts/generate_hard_scenario.py
"""
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "test_scenarios" / "meridian_uar_hard"
COMPANY = BASE / "company"
SHEETS = BASE / "evidence" / "sheets"
EMAIL = BASE / "evidence" / "email"

for d in (COMPANY, SHEETS, EMAIL):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Employee roster
# (emp_id, full_name, email, department, job_title, manager_email, status,
#  hire_date, term_date)
# Dates use unambiguous day-of-month values (>12) or month names, on purpose -
# a DD-MM-YYYY numeric date with day<=12 is genuinely ambiguous to parse
# without locale context, and this dataset is meant to be hard because of
# WHO/WHAT is being said, not because of a coin-flip date bug.
# ---------------------------------------------------------------------------
EMPLOYEES = [
    ("MT-0001", "Deepa Nair",       "deepa.nair@meridiantex.com",       "Finance",           "Finance Manager",       None,                                  "Active",     "14-Mar-2016", None),
    ("MT-0002", "Ramesh Pillai",    "ramesh.pillai@meridiantex.com",    "Finance",           "Finance Executive",     "deepa.nair@meridiantex.com",         "Active",     "22-Jun-2018", None),
    ("MT-0003", "Suman Ghosh",      "suman.ghosh@meridiantex.com",      "Finance",           "Accounts Payable Clerk","deepa.nair@meridiantex.com",         "Active",     "18-Aug-2019", None),
    ("MT-0004", "Priya Varma",      "priya.varma@meridiantex.com",      "Finance",           "Financial Analyst",     "deepa.nair@meridiantex.com",         "Active",     "30-Jan-2021", None),
    ("MT-0005", "Anitha Verma",     "anitha.verma@meridiantex.com",     "Finance",           "Junior Accountant",     "deepa.nair@meridiantex.com",         "Terminated", "25-Jul-2020", "28-Feb-2026"),
    ("MT-0006", "Ravindra Shetty",  "ravindra.shetty@meridiantex.com",  "Production",        "Production Manager",    None,                                  "Active",     "17-Sep-2015", None),
    ("MT-0007", "Rahul Menon",      "rahul.menon@meridiantex.com",      "Production",        "Production Supervisor", "ravindra.shetty@meridiantex.com",    "Active",     "19-Apr-2019", None),
    ("MT-0008", "Karthik Iyer",     "karthik.iyer@meridiantex.com",     "Production",        "Machine Operator",      "ravindra.shetty@meridiantex.com",    "Active",     "23-Nov-2020", None),
    ("MT-0009", "Feroz Sheikh",     "feroz.sheikh@meridiantex.com",     "Production",        "Quality Auditor (Contractor)", "ravindra.shetty@meridiantex.com", "Active", "15-May-2025", None),
    ("MT-0010", "Lakshmi Narayan",  "lakshmi.narayan@meridiantex.com",  "Production",        "Production Planner",    "ravindra.shetty@meridiantex.com",    "Active",     "28-Feb-2022", None),
    ("MT-0011", "Kavitha Reddy",    "kavitha.reddy@meridiantex.com",    "Sales & Marketing", "Sales Manager",         None,                                  "Active",     "20-Oct-2014", None),
    ("MT-0012", "Rahul Nair",       "rahul.nair@meridiantex.com",       "Sales & Marketing", "Sales Executive",       "kavitha.reddy@meridiantex.com",      "Active",     "16-Jun-2021", None),
    ("MT-0013", "Suresh Pillai",    "suresh.pillai@meridiantex.com",    "Sales & Marketing", "Regional Sales Manager","kavitha.reddy@meridiantex.com",      "Active",     "21-Mar-2017", None),
    ("MT-0014", "Meena Krishnan",   "meena.krishnan@meridiantex.com",   "Sales & Marketing", "Marketing Executive",   "kavitha.reddy@meridiantex.com",      "Active",     "13-Aug-2022", None),
    ("MT-0015", "Meenakshi Iyer",   "meenakshi.iyer@meridiantex.com",   "Sales & Marketing", "Sales Coordinator",     "kavitha.reddy@meridiantex.com",      "Active",     "29-Jan-2023", None),
    ("MT-0016", "Arjun Malhotra",   "arjun.malhotra@meridiantex.com",   "Warehouse & Logistics", "Warehouse Manager", None,                                  "Active",     "19-Dec-2013", None),
    ("MT-0017", "Vikram Singh",     "vikram.singh@meridiantex.com",     "Warehouse & Logistics", "Warehouse Supervisor","arjun.malhotra@meridiantex.com",   "Active",     "24-Jul-2018", None),
    ("MT-0018", "Divya Menon",      "divya.menon@meridiantex.com",      "Warehouse & Logistics", "Logistics Coordinator","arjun.malhotra@meridiantex.com", "Active",     "17-Feb-2020", None),
    ("MT-0019", "Nasser Ali",       "nasser.ali@meridiantex.com",       "Warehouse & Logistics", "Store Keeper",       "arjun.malhotra@meridiantex.com",     "Active",     "22-Sep-2021", None),
    ("MT-0020", "Sunil Bhatia",     "sunil.bhatia@meridiantex.com",     "HR & Admin",        "HR Manager",            None,                                  "Active",     "15-Jan-2015", None),
    ("MT-0021", "Farah Khan",       "farah.khan@meridiantex.com",       "HR & Admin",        "HR Executive",          "sunil.bhatia@meridiantex.com",       "Active",     "27-May-2019", None),
    ("MT-0022", "Tarun Kapoor",     "tarun.kapoor@meridiantex.com",     "HR & Admin",        "Admin Officer",         "sunil.bhatia@meridiantex.com",       "Active",     "30-Oct-2021", None),
    ("MT-0023", "Neha Kapoor",      "neha.kapoor@meridiantex.com",      "IT & Compliance",   "IT Compliance Officer", None,                                  "Active",     "16-Mar-2018", None),
    # Legitimate mid-cycle new joiner - only appears in the AFTER sheet, with
    # a proper approval trail. Distractor: looks like a fresh, unexplained
    # grant unless the reviewer notices she genuinely joined during the
    # review window.
    ("MT-0024", "Ananya Das",       "ananya.das@meridiantex.com",       "Finance",           "Junior Accountant",     "deepa.nair@meridiantex.com",         "Active",     "20-Aug-2026", None),
]

REVIEW_START = "18-Aug-2026"
REVIEW_DEADLINE = "27-Aug-2026"

# ---------------------------------------------------------------------------
# 1. Employee master (messy CSV - different header wording than the ACME
#    dataset on purpose, one column reordered)
# ---------------------------------------------------------------------------
emp_csv_lines = [
    "Personnel Number,Staff Name,Work Email Address,Division,Position,Reporting Manager (Email),Employment Status,Date Of Hire,Last Working Day"
]
for row in EMPLOYEES:
    emp_id, name, email, dept, title, mgr, status, hire, term = row
    emp_csv_lines.append(
        f"{emp_id},{name},{email},{dept},{title},{mgr or ''},{status},{hire},{term or ''}"
    )
(COMPANY / "employee_master.csv").write_text("\n".join(emp_csv_lines) + "\n", encoding="utf-8")

# role_access_matrix.yaml / company_context.yaml must conform to the same
# schema load_policy() (src/itgc/policy.py) requires for the ACME dataset -
# this scenario is meant to run through the real pipeline, not just be
# eyeballed, so these are NOT abbreviated versions of that schema.
(COMPANY / "role_access_matrix.yaml").write_text(
    """applications:
  Horizon ERP:
    sensitivity: high
    profiles:
    - Finance_Approver
    - Finance_User
    - AP_Clerk
    - Production_Admin
    - Production_User
    - Production_Planner
    - QA_ReadOnly
    - Sales_Admin
    - Sales_User
    - Sales_Approver
    - Marketing_User
    - Warehouse_Admin
    - Warehouse_User
    - Logistics_User
    - HR_Admin
    - HR_User
    - Admin_User
    - Compliance_Admin
    sod_conflicts:
    - - Finance_User
      - Finance_Approver
    - - AP_Clerk
      - Finance_Approver
    role_to_profile:
      Finance Manager:
      - Finance_Approver
      Finance Executive:
      - Finance_User
      Accounts Payable Clerk:
      - AP_Clerk
      Financial Analyst:
      - Finance_User
      Junior Accountant:
      - Finance_User
      Production Manager:
      - Production_Admin
      Production Supervisor:
      - Production_User
      Machine Operator:
      - Production_User
      Quality Auditor (Contractor):
      - QA_ReadOnly
      Production Planner:
      - Production_Planner
      Sales Manager:
      - Sales_Admin
      Sales Executive:
      - Sales_User
      Regional Sales Manager:
      - Sales_Approver
      Marketing Executive:
      - Marketing_User
      Sales Coordinator:
      - Sales_User
      Warehouse Manager:
      - Warehouse_Admin
      Warehouse Supervisor:
      - Warehouse_User
      Logistics Coordinator:
      - Logistics_User
      Store Keeper:
      - Warehouse_User
      HR Manager:
      - HR_Admin
      HR Executive:
      - HR_User
      Admin Officer:
      - Admin_User
      IT Compliance Officer:
      - Compliance_Admin
deprovisioning_sla_days: 5
dormant_threshold_days: 90
joiner_provisioning_sla_days: 10
uar_review_period: 2026-Q3
""",
    encoding="utf-8",
)

(COMPANY / "company_context.yaml").write_text(
    """company: Meridian Textiles Pvt Ltd
engagement: Horizon ERP - quarterly User Access Review (UAR)
in_scope_applications:
- Horizon ERP
policy_reference: MTX-ITGC-POL-04 Access Management Policy v1.0
sod_policy_reference: MTX-ITGC-POL-07 Segregation of Duties Policy
industry: Textiles manufacturing & distribution
review_period_start: "18-Aug-2026"
review_deadline: "27-Aug-2026"
requested_by: Neha Kapoor, IT Compliance Officer
notes: >
  Five department managers were each sent the current Horizon ERP access
  list for their own reports and asked to confirm retain/revoke decisions.
  Evidence for this engagement is the email thread plus the before/after
  access export - there is deliberately no service-desk ticket evidence in
  scope for this review (see ANSWER_KEY_PRIVATE.md for what that implies for
  the automated MISSING_APPROVAL_EVIDENCE control).
""",
    encoding="utf-8",
)

# ---------------------------------------------------------------------------
# 2. BEFORE / AFTER Horizon ERP access sheets
# ---------------------------------------------------------------------------
# (emp_id, name, email, profile, status, last_login)
BEFORE_ROWS = [
    ("MT-0001", "Deepa Nair",      "deepa.nair@meridiantex.com",      "Finance_Approver",   "Active", "05-Sep-2026"),
    ("MT-0002", "Ramesh Pillai",   "ramesh.pillai@meridiantex.com",   "Finance_User",       "Active", "04-Sep-2026"),
    ("MT-0003", "Suman Ghosh",     "suman.ghosh@meridiantex.com",     "AP_Clerk",           "Active", "03-Sep-2026"),
    ("MT-0004", "Priya Varma",     "priya.varma@meridiantex.com",     "Finance_User",       "Active", "05-Sep-2026"),
    ("MT-0005", "Anitha Verma",    "anitha.verma@meridiantex.com",    "Finance_User",       "Active", "20-Feb-2026"),
    ("MT-0006", "Ravindra Shetty", "ravindra.shetty@meridiantex.com", "Production_Admin",   "Active", "05-Sep-2026"),
    ("MT-0007", "Rahul Menon",     "rahul.menon@meridiantex.com",     "Production_User",    "Active", "05-Sep-2026"),
    ("MT-0008", "Karthik Iyer",    "karthik.iyer@meridiantex.com",    "Production_User",    "Active", "02-Sep-2026"),
    ("MT-0008", "Karthik Iyer",    "karthik.iyer@meridiantex.com",    "Production_User",    "Active", "02-Sep-2026"),  # duplicate row, on purpose
    ("MT-0009", "Feroz Sheikh",    "feroz.sheikh@meridiantex.com",    "QA_ReadOnly",        "Active", "30-Aug-2026"),
    ("MT-0010", "Lakshmi Narayan", "lakshmi.narayan@meridiantex.com", "Production_Planner", "Active", "04-Sep-2026"),
    ("MT-0011", "Kavitha Reddy",   "kavitha.reddy@meridiantex.com",   "Sales_Admin",        "Active", "05-Sep-2026"),
    ("MT-0012", "Rahul Nair",      "rahul.nair@meridiantex.com",      "Sales_User",         "Active", "01-Sep-2026"),
    ("MT-0013", "Suresh Pillai",   "suresh.pillai@meridiantex.com",   "Sales_Approver",     "Active", "05-Sep-2026"),
    ("MT-0014", "Meena Krishnan",  "meena.krishnan@meridiantex.com",  "Marketing_User",     "Active", "04-Sep-2026"),
    ("", "", "", "", "", ""),  # blank row, on purpose
    ("MT-0015", "Meenakshi Iyer",  "meenakshi.iyer@meridiantex.com",  "Sales_User",         "Active", "03-Sep-2026"),
    ("MT-0016", "Arjun Malhotra",  "arjun.malhotra@meridiantex.com",  "Warehouse_Admin",    "Active", "05-Sep-2026"),
    ("MT-0017", "Vikram Singh",    "vikram.singh@meridiantex.com",    "Warehouse_User",     "Active", "05-Sep-2026"),
    ("MT-0018", "Divya Menon",     "divya.menon@meridiantex.com",     "Logistics_User",     "Active", "04-Sep-2026"),
    ("MT-0019", "Nasser Ali",      "nasser.ali@meridiantex.com",      "Warehouse_User",     "Active", "02-Sep-2026"),
    ("MT-0020", "Sunil Bhatia",    "sunil.bhatia@meridiantex.com",    "HR_Admin",           "Active", "05-Sep-2026"),
    ("MT-0021", "Farah Khan",      "farah.khan@meridiantex.com",      "HR_User",            "Active", "05-Sep-2026"),
    ("MT-0022", "Tarun Kapoor",    "tarun.kapoor@meridiantex.com",    "Admin_User",         "Active", "04-Sep-2026"),
    ("MT-0023", "Neha Kapoor",     "neha.kapoor@meridiantex.com",     "Compliance_Admin",   "Active", "05-Sep-2026"),
]

AFTER_ROWS = [
    ("MT-0001", "Deepa Nair",      "deepa.nair@meridiantex.com",      "Finance_Approver",   "Active",   "12-Sep-2026"),
    ("MT-0002", "Ramesh Pillai",   "ramesh.pillai@meridiantex.com",   "Finance_User",       "Disabled", "04-Sep-2026"),  # WRONG: correction email said keep him
    ("MT-0003", "Suman Ghosh",     "suman.ghosh@meridiantex.com",     "AP_Clerk",           "Disabled", "03-Sep-2026"),  # correct
    ("MT-0004", "Priya Varma",     "priya.varma@meridiantex.com",     "Finance_User",       "Active",   "12-Sep-2026"),
    ("MT-0005", "Anitha Verma",    "anitha.verma@meridiantex.com",    "Finance_User",       "Active",   "20-Feb-2026"),  # WRONG: still active, terminated leaver
    ("MT-0006", "Ravindra Shetty", "ravindra.shetty@meridiantex.com", "Production_Admin",   "Active",   "12-Sep-2026"),
    ("MT-0007", "Rahul Menon",     "rahul.menon@meridiantex.com",     "Production_User",    "Active",   "11-Sep-2026"),  # WRONG: should have been revoked, wasn't
    ("MT-0008", "Karthik Iyer",    "karthik.iyer@meridiantex.com",    "Production_User",    "Active",   "10-Sep-2026"),
    ("MT-0009", "Feroz Sheikh",    "feroz.sheikh@meridiantex.com",    "QA_ReadOnly",        "Disabled", "30-Aug-2026"),  # correct - the vague contractor reference
    ("MT-0010", "Lakshmi Narayan", "lakshmi.narayan@meridiantex.com", "Production_Planner", "Active",   "12-Sep-2026"),
    ("MT-0011", "Kavitha Reddy",   "kavitha.reddy@meridiantex.com",   "Sales_Admin",        "Active",   "12-Sep-2026"),
    ("MT-0012", "Rahul Nair",      "rahul.nair@meridiantex.com",      "Sales_User",         "Disabled", "01-Sep-2026"),  # WRONG PERSON: the other Rahul was actioned
    ("MT-0013", "Suresh Pillai",   "suresh.pillai@meridiantex.com",   "Sales_Approver",     "Disabled", "05-Sep-2026"),  # revoked on an out-of-authority instruction
    ("MT-0014", "Meena Krishnan",  "meena.krishnan@meridiantex.com",  "Marketing_User",     "Active",   "12-Sep-2026"),  # ambiguous "Meena" - left open, correctly unactioned
    ("MT-0015", "Meenakshi Iyer",  "meenakshi.iyer@meridiantex.com",  "Sales_User",         "Active",   "12-Sep-2026"),  # same
    ("MT-0016", "Arjun Malhotra",  "arjun.malhotra@meridiantex.com",  "Warehouse_Admin",    "Active",   "12-Sep-2026"),
    ("MT-0017", "Vikram Singh",    "vikram.singh@meridiantex.com",    "Warehouse_User",     "Active",   "12-Sep-2026"),
    ("MT-0018", "Divya Menon",     "divya.menon@meridiantex.com",     "Logistics_User",     "Active",   "12-Sep-2026"),
    ("MT-0019", "Nasser Ali",      "nasser.ali@meridiantex.com",      "Warehouse_User",     "Active",   "12-Sep-2026"),
    ("MT-0020", "Sunil Bhatia",    "sunil.bhatia@meridiantex.com",    "HR_Admin",           "Active",   "12-Sep-2026"),
    ("MT-0021", "Farah Khan",      "farah.khan@meridiantex.com",      "HR_User",            "Active",   "12-Sep-2026"),
    ("MT-0022", "Tarun Kapoor",    "tarun.kapoor@meridiantex.com",    "Admin_User",         "Active",   "12-Sep-2026"),
    ("MT-0023", "Neha Kapoor",     "neha.kapoor@meridiantex.com",     "Compliance_Admin",   "Active",   "12-Sep-2026"),
    ("MT-0024", "Ananya Das",      "ananya.das@meridiantex.com",      "Finance_User",       "Active",   "10-Sep-2026"),  # legitimate new joiner - not a violation
]


def write_before_sheet():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Horizon ERP Access"
    # A banner/title block above the real header row, like a real client
    # export with a report title pasted at the top.
    ws["A1"] = "Meridian Textiles Pvt Ltd - Horizon ERP Access Export"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = f"Extracted: {REVIEW_START}  |  Scope: All active users"
    headers = ["User ID", "User Full Name", "Email", "Access Profile(s)", "Account Status", "Last Login Date"]
    ws.append([])  # row 3 blank
    ws.append(headers)  # row 4
    for r in BEFORE_ROWS:
        ws.append(list(r))
    wb.save(SHEETS / "horizon_erp_access_before_audit.xlsx")


def write_after_sheet():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Horizon ERP Access (After)"
    # Different header wording than the BEFORE sheet, one light typo
    # ("Acount Status") to test fuzzy column matching without breaking it
    # outright, and columns in a different order than the before sheet.
    ws["A1"] = "Horizon ERP - Post-Review Access State"
    ws["A1"].font = Font(bold=True, size=13)
    ws["A2"] = f"Prepared by: IT Compliance  |  Date: 12-Sep-2026"
    headers = ["Login ID", "Display Name", "Acount Status", "Role(s)", "Email Address", "Last Logon"]
    ws.append([])
    ws.append(headers)
    for emp_id, name, email, profile, status, last_login in AFTER_ROWS:
        # note the reordered columns relative to BEFORE_ROWS' tuple shape
        ws.append([emp_id, name, status, profile, email, last_login])
    wb.save(SHEETS / "horizon_erp_access_after_audit.xlsx")


write_before_sheet()
write_after_sheet()

# ---------------------------------------------------------------------------
# 3. Email evidence (plain-text, informal, realistic noise: quoted threads,
#    varied sign-offs, CC noise, one reply-all typo)
# ---------------------------------------------------------------------------

email_01_initiating = f"""From: Neha Kapoor <neha.kapoor@meridiantex.com>
To: Deepa Nair <deepa.nair@meridiantex.com>; Ravindra Shetty <ravindra.shetty@meridiantex.com>; Kavitha Reddy <kavitha.reddy@meridiantex.com>; Arjun Malhotra <arjun.malhotra@meridiantex.com>; Sunil Bhatia <sunil.bhatia@meridiantex.com>
Cc: audit@meridiantex.com
Date: {REVIEW_START}
Subject: Quarterly Horizon ERP User Access Review - action needed by {REVIEW_DEADLINE}

Hi all,

Time for our quarterly Horizon ERP access review. Attached is the current
list of active Horizon ERP users under each of you (see
horizon_erp_access_before_audit.xlsx).

Please reply to this email by {REVIEW_DEADLINE} confirming, for each person
on your team:
  - KEEP - they still need Horizon ERP for their role, or
  - REVOKE - access should be removed.

A couple of reminders since this always comes up:
  - Please only action people who actually report to you.
  - If someone has moved teams or left, please say so explicitly rather than
    just leaving them off the list.
  - If you're not sure who a name refers to, please ask rather than guess -
    I'd rather get one follow-up email than revoke the wrong person's
    access.

Thanks,
Neha
IT Compliance
"""

email_02_deepa_first = f"""From: Deepa Nair <deepa.nair@meridiantex.com>
To: Neha Kapoor <neha.kapoor@meridiantex.com>
Cc: audit@meridiantex.com
Date: 19-Aug-2026
Subject: RE: Quarterly Horizon ERP User Access Review - action needed by {REVIEW_DEADLINE}

Hi Neha,

For Finance:
- Ramesh Pillai - please revoke. He's moved over to the new invoicing
  system and doesn't touch Horizon ERP anymore.
- Suman Ghosh - please revoke as well, same reason, moved to the new
  system.
- Priya Varma and I still need our access, no change there.

Separately (not really a Horizon ERP thing but flagging while I'm at it) -
Anitha Verma should be off all our systems by now, she left the company
earlier this year. Not sure why she's still on your list at all, can you
check?

Thanks,
Deepa

> On {REVIEW_START}, Neha Kapoor wrote:
> Hi all, time for our quarterly Horizon ERP access review...
"""

email_03_deepa_correction = """From: Deepa Nair <deepa.nair@meridiantex.com>
To: Neha Kapoor <neha.kapoor@meridiantex.com>
Cc: audit@meridiantex.com
Date: 21-Aug-2026
Subject: RE: RE: Quarterly Horizon ERP User Access Review - correction

Hi Neha,

Sorry, one correction to my earlier note - please IGNORE what I said about
Ramesh Pillai. I checked with the team and he's actually still doing the
year-end close in Horizon ERP through this quarter, so he needs to keep his
access for now. We'll revisit next cycle.

To be clear, the only Finance revoke this round is Suman Ghosh. Ramesh and
Priya both keep their access.

Sorry for the back-and-forth.

Deepa

> On 19-Aug-2026, Deepa Nair wrote:
> For Finance:
> - Ramesh Pillai - please revoke...
> - Suman Ghosh - please revoke as well...
"""

email_04_ravindra = """From: Ravindra Shetty <ravindra.shetty@meridiantex.com>
To: Neha Kapoor <neha.kapoor@meridiantex.com>
Date: 20-Aug-2026
Subject: Re: Quarterly Horizon ERP User Access Review

Neha,

For my side - please go ahead and revoke Rahul's Horizon access, he's
moved into a planning role that doesn't touch the ERP system day to day
anymore.

Also please revoke access for that contractor we discussed last month -
his engagement wrapped up end of August so he shouldn't need anything
after that.

Everyone else on my team stays as-is.

- Ravindra
"""

email_05_kavitha = """From: Kavitha Reddy <kavitha.reddy@meridiantex.com>
To: Neha Kapoor <neha.kapoor@meridiantex.com>
Date: 22-Aug-2026
Subject: RE: Quarterly Horizon ERP User Access Review - action needed by 27-Aug-2026

Hi Neha,

Quick one from Sales & Marketing - please revoke Meena's access, she's
been reassigned and doesn't need Horizon ERP in her new role. Everyone
else on my team is fine as they are.

Let me know if you need anything else from me before the deadline.

Best,
Kavitha
"""

email_06_arjun = """From: Arjun Malhotra <arjun.malhotra@meridiantex.com>
To: Neha Kapoor <neha.kapoor@meridiantex.com>
Date: 23-Aug-2026
Subject: Re: Quarterly Horizon ERP User Access Review

Hi Neha,

For Warehouse - no changes needed on my own team this round, everyone's
current.

One more thing though - I was asked to pass along that MT-0013's Horizon
access should be revoked. I'll leave it at the ID since it's a bit of a
sensitive one and I'd rather not put a name in writing over email. Can you
action that on your end?

Thanks,
Arjun
"""

email_07_sunil = """From: Sunil Bhatia <sunil.bhatia@meridiantex.com>
To: Neha Kapoor <neha.kapoor@meridiantex.com>
Cc: farah.khan@meridiantex.com
Date: 24-Aug-2026
Subject: RE: Quarterly Horizon ERP User Access Review - action needed by 27-Aug-2026

Hi Neha,

HR & Admin: no changes needed for my team this quarter, everyone listed
is current and correct.

Separate item while I have you - I noticed Anitha Verma's name came up
again in one of these threads. Just to close the loop from HR's side: she
was terminated effective 28-Feb-2026 (Finance department, reported to
Deepa). Can you confirm her Horizon ERP account has actually been
deactivated? Given the termination was several months ago now this
shouldn't still be open.

Thanks,
Sunil
"""

email_08_neha_followup = """From: Neha Kapoor <neha.kapoor@meridiantex.com>
To: Ravindra Shetty <ravindra.shetty@meridiantex.com>
Date: 25-Aug-2026
Subject: Re: Quarterly Horizon ERP User Access Review - quick check

Hi Ravindra,

Before I action your note - just to confirm on my end, when you say
"Rahul" you mean Rahul Menon (Production Supervisor, reports to you),
not Rahul Nair in Sales? Just double-checking since we have two Rahuls
on the roster this year.

Thanks,
Neha
"""

email_09_ravindra_confirm = """From: Ravindra Shetty <ravindra.shetty@meridiantex.com>
To: Neha Kapoor <neha.kapoor@meridiantex.com>
Date: 25-Aug-2026
Subject: Re: Quarterly Horizon ERP User Access Review - quick check

Yes, Rahul Menon on my team. Didn't realise there were two, thanks for
catching that.

- Ravindra
"""

for fname, content in [
    ("email_01_neha_initiating_request.txt", email_01_initiating),
    ("email_02_deepa_first_reply.txt", email_02_deepa_first),
    ("email_03_deepa_correction.txt", email_03_deepa_correction),
    ("email_04_ravindra_reply.txt", email_04_ravindra),
    ("email_05_kavitha_reply.txt", email_05_kavitha),
    ("email_06_arjun_reply.txt", email_06_arjun),
    ("email_07_sunil_reply.txt", email_07_sunil),
    ("email_08_neha_followup_to_ravindra.txt", email_08_neha_followup),
    ("email_09_ravindra_confirms_rahul_menon.txt", email_09_ravindra_confirm),
]:
    (EMAIL / fname).write_text(content, encoding="utf-8")

# ---------------------------------------------------------------------------
# 4. Private answer key - NOT read by any code, for a human to self-grade.
# ---------------------------------------------------------------------------
answer_key = """# Meridian Textiles - Horizon ERP UAR (hard scenario) - ANSWER KEY

This file is private and is not referenced by any code in this repository.
It exists so you (or whoever works this case) can self-grade against the
intended findings after working the evidence cold. Nothing in
src/itgc reads this file, and nothing in the generator script depends on it
either - it's a description of what was planted, written after the fact.

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
- Company/role/context YAML files are intentionally minimal - the point of
  this scenario is manual evidence cross-referencing, not another pass
  through the automated SoD/dormancy/excess-access rules already exercised
  by the ACME sample dataset.

## Spreadsheet mechanics planted (for ingestion robustness, not audit findings)

- BEFORE sheet: a title/banner block above the real header row, a
  duplicate row (Karthik Iyer, MT-0008), and a blank row before Meenakshi
  Iyer's row.
- AFTER sheet: different header wording than BEFORE ("Login ID" vs
  "User ID", "Acount Status" - deliberate typo - vs "Account Status"), and
  the columns are in a different order than BEFORE.
"""
(BASE / "ANSWER_KEY_PRIVATE.md").write_text(answer_key, encoding="utf-8")

readme = """# Meridian Textiles Pvt Ltd - Horizon ERP UAR (hard scenario)

Standalone test evidence. Not used by any test, not imported by any code,
not referenced anywhere in src/itgc. This exists purely to be fed into the
tool (or a human) as a cold case: a folder of realistic, differently-
formatted evidence with no answer key attached (ANSWER_KEY_PRIVATE.md is
for self-grading after the fact, not an input).

## Folder layout

    company/
      employee_master.csv        - employee roster (messy header names)
      role_access_matrix.yaml    - minimal Horizon ERP reference data
      company_context.yaml       - engagement context
    evidence/
      sheets/
        horizon_erp_access_before_audit.xlsx
        horizon_erp_access_after_audit.xlsx
      email/
        email_01..09_*.txt       - the initiating request + manager replies,
                                    a correction, and a disambiguation
                                    exchange, in send order

ANSWER_KEY_PRIVATE.md - what a correct working of the case should find, and
why. Not read by any code.

## How to use it

Point the tool's ingestion at company/ + evidence/ the same way you would
for the ACME sample dataset, work the case, then compare your findings
against ANSWER_KEY_PRIVATE.md yourself. There is deliberately no
service-desk evidence in this scenario, and the emails require actually
reading them in order (including the correction and the disambiguation
exchange) - taking the first instruction at face value will get several
items wrong.
"""
(BASE / "README.md").write_text(readme, encoding="utf-8")

print("Meridian hard scenario written to:", BASE)
