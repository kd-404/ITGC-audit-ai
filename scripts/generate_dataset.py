"""
Generates a realistic, deliberately messy ACME Industries evidence set for the
ITGC audit assistant to ingest, plus a hidden ground-truth answer key used only
by scripts/run_scoring.py (never by the pipeline itself).

Evidence formats mimic what an auditor actually receives from a client:
  - Employee master + role/access matrix + application register (company context)
  - UAR export sheets per application (xlsx, messy headers, title rows, blank cols)
  - Service desk export (csv, access request tickets with approvals)
  - Emails (plain-text .eml-style files, some approvals only exist here)

Run: python3 scripts/generate_dataset.py
"""
import random
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl
from openpyxl.styles import Font
import yaml

random.seed(42)

ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "data" / "company"
EVID_SHEETS = ROOT / "data" / "evidence" / "sheets"
EVID_SD = ROOT / "data" / "evidence" / "servicedesk"
EVID_EMAIL = ROOT / "data" / "evidence" / "email"
GT = ROOT / "data" / "ground_truth"

for d in (COMPANY, EVID_SHEETS, EVID_SD, EVID_EMAIL, GT):
    d.mkdir(parents=True, exist_ok=True)

TODAY = datetime(2026, 9, 15)

# --------------------------------------------------------------------------
# 1. EMPLOYEE MASTER
# --------------------------------------------------------------------------
# (emp_id, full_name, email, dept, job_title, manager_email, status, hire_date, term_date)
EMPLOYEES = [
    ("E001", "Sarah Connor",     "sarah.connor@acme.com",     "Finance", "Controller",        None,                        "Active",     "2018-03-01", None),
    ("E002", "Miguel Alvarez",   "miguel.alvarez@acme.com",   "Finance", "AP Manager",         "sarah.connor@acme.com",    "Active",     "2019-06-10", None),
    ("E003", "Priya Nathan",     "priya.nathan@acme.com",     "Finance", "AP Clerk",           "miguel.alvarez@acme.com",  "Active",     "2020-01-15", None),
    ("E004", "Derek Owusu",      "derek.owusu@acme.com",      "Finance", "AP Clerk",           "miguel.alvarez@acme.com",  "Active",     "2021-02-20", None),
    ("E005", "Lena Fischer",     "lena.fischer@acme.com",     "Finance", "Payroll Specialist", "sarah.connor@acme.com",    "Active",     "2017-11-05", None),
    ("E006", "Jonathan Ito",     "jonathan.ito@acme.com",     "Finance", "AP Clerk",           "miguel.alvarez@acme.com",  "Terminated", "2019-09-01", "2026-07-31"),
    ("E007", "Grace Kim",        "grace.kim@acme.com",        "HR",      "HR Manager",         None,                        "Active",     "2016-04-12", None),
    ("E008", "Oscar Bennett",    "oscar.bennett@acme.com",    "HR",      "HR Generalist",      "grace.kim@acme.com",       "Active",     "2020-08-19", None),
    ("E009", "Wanjiru Kamau",    "wanjiru.kamau@acme.com",    "HR",      "HR Generalist",      "grace.kim@acme.com",       "Active",     "2022-01-10", None),
    ("E010", "Ravi Desai",       "ravi.desai@acme.com",       "IT",      "IT Manager",         None,                        "Active",     "2015-05-01", None),
    ("E011", "Tomas Novak",      "tomas.novak@acme.com",      "IT",      "IT Admin",           "ravi.desai@acme.com",      "Active",     "2018-07-23", None),
    ("E012", "Fatima Zahra",     "fatima.zahra@acme.com",     "IT",      "Security Officer",   "ravi.desai@acme.com",      "Active",     "2019-03-14", None),
    ("E013", "Callum Reid",      "callum.reid@acme.com",      "IT",      "Helpdesk Analyst",   "ravi.desai@acme.com",      "Active",     "2023-02-06", None),
    ("E014", "Ana Beatriz Souza","ana.souza@acme.com",        "Sales",   "Sales Manager",       None,                        "Active",     "2017-09-18", None),
    ("E015", "Marcus Lindgren",  "marcus.lindgren@acme.com",  "Sales",   "Sales Rep",          "ana.souza@acme.com",       "Active",     "2021-06-01", None),
    ("E016", "Yuki Tanaka",      "yuki.tanaka@acme.com",      "Sales",   "Sales Rep",          "ana.souza@acme.com",       "Active",     "2022-10-11", None),
    ("E017", "Helena Cruz",      "helena.cruz@acme.com",      "Sales",   "Sales Rep",          "ana.souza@acme.com",       "Terminated", "2020-02-17", "2026-08-15"),
    ("E018", "Peter van Dijk",   "peter.vandijk@acme.com",    "Ops",     "Ops Manager",         None,                        "Active",     "2016-11-30", None),
    ("E019", "Amara Chukwu",     "amara.chukwu@acme.com",     "Ops",     "Ops Analyst",        "peter.vandijk@acme.com",   "Active",     "2021-04-05", None),
    ("E020", "Dmitri Volkov",    "dmitri.volkov@acme.com",    "Ops",     "Ops Analyst",        "peter.vandijk@acme.com",   "Active",     "2023-07-19", None),
    ("E021", "Isabelle Moreau",  "isabelle.moreau@acme.com",  "Finance", "AP Clerk",           "miguel.alvarez@acme.com",  "Active",     "2024-01-08", None),
    ("E022", "Kwame Asante",     "kwame.asante@acme.com",     "IT",      "IT Admin",           "ravi.desai@acme.com",      "Active",     "2020-09-22", None),
    ("E023", "Noor Hassan",      "noor.hassan@acme.com",      "HR",      "HR Generalist",      "grace.kim@acme.com",       "Terminated", "2019-01-14", "2026-06-20"),
    ("E024", "Ethan Brooks",     "ethan.brooks@acme.com",     "Sales",   "Sales Rep",          "ana.souza@acme.com",       "Active",     "2025-03-01", None),
]

def write_employee_master():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Employees"
    # realistic messiness: a title/banner row above the real header
    ws.append(["ACME Industries - HRIS Employee Extract - Confidential"])
    ws.append(["Generated 2026-09-15 by HRIS Export Tool v3.2"])
    ws.append([])
    header = ["Emp Code", "Employee Name", "Work Email", "Department", "Job Title",
              "Reporting Manager (Email)", "Employment Status", "Date of Hire", "Termination Date"]
    ws.append(header)
    for c in ws[4]:
        c.font = Font(bold=True)
    for row in EMPLOYEES:
        ws.append(list(row))
    wb.save(COMPANY / "employee_master.xlsx")

write_employee_master()

# --------------------------------------------------------------------------
# 2. ROLE / ACCESS MATRIX + APPLICATION REGISTER (clean YAML - "policy" input)
# --------------------------------------------------------------------------
ROLE_MATRIX = {
    "applications": {
        "FinERP": {
            "sensitivity": "high",
            "profiles": ["AP Invoice Entry", "AP Invoice Approval", "AP Admin", "Read Only"],
            "sod_conflicts": [["AP Invoice Entry", "AP Invoice Approval"]],
            "role_to_profile": {
                "AP Clerk": ["AP Invoice Entry"],
                "AP Manager": ["AP Invoice Approval"],
                "Controller": ["AP Invoice Approval", "Read Only"],
            },
        },
        "Payroll": {
            "sensitivity": "high",
            "profiles": ["Payroll Processor", "Payroll Approver", "Read Only"],
            "sod_conflicts": [["Payroll Processor", "Payroll Approver"]],
            "role_to_profile": {
                "Payroll Specialist": ["Payroll Processor"],
                "Controller": ["Payroll Approver"],
            },
        },
        "CRM": {
            "sensitivity": "low",
            "profiles": ["Sales User", "Sales Admin"],
            "sod_conflicts": [],
            "role_to_profile": {
                "Sales Rep": ["Sales User"],
                "Sales Manager": ["Sales Admin"],
            },
        },
    },
    "deprovisioning_sla_days": 3,
    "dormant_threshold_days": 90,
    "joiner_provisioning_sla_days": 10,
    "uar_review_period": "2026-Q3",
}
with open(COMPANY / "role_access_matrix.yaml", "w") as f:
    yaml.dump(ROLE_MATRIX, f, sort_keys=False)

with open(COMPANY / "company_context.yaml", "w") as f:
    yaml.dump({
        "company": "ACME Industries",
        "engagement": "FY2026 ITGC - User Access Review",
        "in_scope_applications": ["FinERP", "Payroll", "CRM"],
        "policy_reference": "ACME-ITGC-POL-04 Access Management Policy v2.1",
        "sod_policy_reference": "ACME-ITGC-POL-07 Segregation of Duties Policy",
    }, f, sort_keys=False)

# --------------------------------------------------------------------------
# 3. UAR EVIDENCE SHEETS (messy xlsx exports from each application)
# --------------------------------------------------------------------------
def emp_by_email(email):
    for e in EMPLOYEES:
        if e[2] == email:
            return e
    return None

def write_uar_sheet(app_name, filename, rows, header, title_rows=True):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = app_name[:31]
    if title_rows:
        ws.append([f"{app_name} - User Access Report - Export"])
        ws.append([f"Export Date: {TODAY.strftime('%d-%b-%Y')}  |  Source: {app_name} Admin Console"])
        ws.append([])
    ws.append(header)
    hdr_row = ws.max_row
    for c in ws[hdr_row]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append(r)
    wb.save(EVID_SHEETS / filename)

# ---- FinERP UAR (the primary test, deliberately dirty) ----
finerp_rows = [
    # user_id, user_name, email, profile, status, last_login
    ("FE-001", "Sarah Connor",   "sarah.connor@acme.com",   "AP Invoice Approval", "Active", "05-Sep-2026"),
    ("FE-002", "Miguel Alvarez", "miguel.alvarez@acme.com", "AP Invoice Approval", "Active", "12-Sep-2026"),
    ("FE-003", "Priya Nathan",   "priya.nathan@acme.com",   "AP Invoice Entry",    "Active", "14-Sep-2026"),
    ("FE-004", "Derek Owusu",    "derek.owusu@acme.com",    "AP Invoice Entry",    "Active", "13-Sep-2026"),
    # SoD violation: Isabelle has BOTH entry and approval (two separate rows as the export lists multi-profile users per row)
    ("FE-005", "Isabelle Moreau","isabelle.moreau@acme.com","AP Invoice Entry, AP Invoice Approval", "Active", "10-Sep-2026"),
    # JML violation: Jonathan Ito terminated 2026-07-31 but account still Active
    ("FE-006", "Jonathan Ito",   "jonathan.ito@acme.com",   "AP Invoice Entry",    "Active", "02-Sep-2026"),
    # Orphan account: no matching employee record at all (contractor never onboarded to HRIS, or typo'd departure)
    ("FE-007", "Contractor - B Hale", "bhale@acme-consulting.com", "AP Invoice Entry", "Active", "01-Aug-2026"),
    # Excess/unexpected access: Sales Rep with FinERP approval access - not in role matrix at all
    ("FE-008", "Marcus Lindgren","marcus.lindgren@acme.com","AP Invoice Approval", "Active", "20-Aug-2026"),
    # Dormant account: never logged in for >90 days, still active
    ("FE-009", "Derek Owusu",    "derek.owusu@acme.com",    "AP Admin",            "Active", "10-Jan-2026"),
    ("FE-010", "Kwame Asante",   "kwame.asante@acme.com",   "Read Only",           "Active", "11-Sep-2026"),
]
write_uar_sheet("FinERP", "FinERP_UserAccess_Export.xlsx", finerp_rows,
                ["User ID", "User Full Name", "Email Address", "Access Profile(s)", "Account Status", "Last Login"])

# ---- Payroll UAR (mostly clean, one SLA breach) ----
payroll_rows = [
    ("PR-001", "Lena Fischer",   "lena.fischer@acme.com",   "Payroll Processor", "Active", "15-Sep-2026"),
    ("PR-002", "Sarah Connor",   "sarah.connor@acme.com",   "Payroll Approver",  "Active", "15-Sep-2026"),
    # JML violation #2: Noor Hassan (HR, terminated 2026-06-20) still has Payroll read access - longer overdue, higher severity
    ("PR-003", "Noor Hassan",    "noor.hassan@acme.com",    "Read Only",         "Active", "18-Jun-2026"),
]
write_uar_sheet("Payroll", "Payroll_Access_Listing.xlsx", payroll_rows,
                ["User ID", "User Full Name", "Email Address", "Access Profile(s)", "Account Status", "Last Login"])

# ---- CRM UAR (clean, low sensitivity - control group) ----
crm_rows = [
    ("CR-001", "Ana Beatriz Souza", "ana.souza@acme.com",       "Sales Admin", "Active", "15-Sep-2026"),
    ("CR-002", "Marcus Lindgren",   "marcus.lindgren@acme.com", "Sales User",  "Active", "14-Sep-2026"),
    ("CR-003", "Yuki Tanaka",       "yuki.tanaka@acme.com",     "Sales User",  "Active", "15-Sep-2026"),
    ("CR-004", "Ethan Brooks",      "ethan.brooks@acme.com",    "Sales User",  "Active", "10-Sep-2026"),
    # Terminated Helena Cruz removed same-day - a CLEAN example so the pipeline shouldn't over-flag
    ("CR-005", "Helena Cruz",       "helena.cruz@acme.com",     "Sales User",  "Disabled", "15-Aug-2026"),
]
write_uar_sheet("CRM", "CRM_Access_Report.xlsx", crm_rows,
                ["User ID", "User Full Name", "Email Address", "Access Profile(s)", "Account Status", "Last Login"])

# --------------------------------------------------------------------------
# 4. SERVICE DESK EXPORT (csv, access request tickets)
# --------------------------------------------------------------------------
import csv

sd_rows = [
    # ticket_id, requester, approver, system, access_requested, status, created, approved, implemented, implementer
    # Baseline/legacy setup tickets, so senior/original accounts aren't flagged as "no approval evidence"
    # purely because they predate the messier evidence below.
    ("SD-1000A", "sarah.connor@acme.com", "ravi.desai@acme.com", "FinERP", "AP Invoice Approval", "Closed",
     "2018-03-05", "2018-03-06", "2018-03-08", "ravi.desai@acme.com"),
    ("SD-1000B", "miguel.alvarez@acme.com", "sarah.connor@acme.com", "FinERP", "AP Invoice Approval", "Closed",
     "2019-06-12", "2019-06-13", "2019-06-15", "tomas.novak@acme.com"),
    ("SD-1000C", "sarah.connor@acme.com", "ravi.desai@acme.com", "Payroll", "Payroll Approver", "Closed",
     "2018-03-05", "2018-03-06", "2018-03-09", "ravi.desai@acme.com"),
    ("SD-1000D", "ana.souza@acme.com", "ravi.desai@acme.com", "CRM", "Sales Admin", "Closed",
     "2017-09-20", "2017-09-21", "2017-09-22", "callum.reid@acme.com"),
    ("SD-1000E", "marcus.lindgren@acme.com", "ana.souza@acme.com", "CRM", "Sales User", "Closed",
     "2021-06-02", "2021-06-03", "2021-06-04", "callum.reid@acme.com"),
    ("SD-1001", "priya.nathan@acme.com", "miguel.alvarez@acme.com", "FinERP", "AP Invoice Entry", "Closed",
     "2020-01-10", "2020-01-12", "2020-01-14", "tomas.novak@acme.com"),
    ("SD-1002", "derek.owusu@acme.com", "miguel.alvarez@acme.com", "FinERP", "AP Invoice Entry", "Closed",
     "2021-02-15", "2021-02-16", "2021-02-18", "tomas.novak@acme.com"),
    ("SD-1003", "isabelle.moreau@acme.com", "miguel.alvarez@acme.com", "FinERP", "AP Invoice Entry", "Closed",
     "2024-01-05", "2024-01-06", "2024-01-08", "kwame.asante@acme.com"),
    # NOTE: no ticket exists anywhere for Isabelle's second profile "AP Invoice Approval" -> access granted without approval evidence
    # Provisioning SoD: approver == requester (self-approved access)
    ("SD-1004", "marcus.lindgren@acme.com", "marcus.lindgren@acme.com", "FinERP", "AP Invoice Approval", "Closed",
     "2026-08-15", "2026-08-15", "2026-08-20", "kwame.asante@acme.com"),
    # Approval-after-implementation: implemented before approval timestamp
    ("SD-1005", "kwame.asante@acme.com", "ravi.desai@acme.com", "FinERP", "Read Only", "Closed",
     "2026-09-01", "2026-09-05", "2026-09-02", "tomas.novak@acme.com"),
    # Termination -> deprovisioning tickets: one on-time, two breaching SLA (or missing)
    ("SD-1006", "grace.kim@acme.com", "grace.kim@acme.com", "CRM", "Disable Account - Helena Cruz", "Closed",
     "2026-08-15", "2026-08-15", "2026-08-15", "callum.reid@acme.com"),
    # Jonathan Ito termination: NO deprovisioning ticket exists in the service desk at all (control gap)
    # Noor Hassan termination: ticket exists but was never implemented (still Open) -> SLA breach, ongoing exposure
    ("SD-1007", "grace.kim@acme.com", "ravi.desai@acme.com", "Payroll", "Disable Account - Noor Hassan", "Open",
     "2026-06-21", "2026-06-22", "", ""),
    # normal clean payroll/CRM traffic
    ("SD-1008", "lena.fischer@acme.com", "sarah.connor@acme.com", "Payroll", "Payroll Processor", "Closed",
     "2017-11-06", "2017-11-07", "2017-11-09", "tomas.novak@acme.com"),
    ("SD-1009", "yuki.tanaka@acme.com", "ana.souza@acme.com", "CRM", "Sales User", "Closed",
     "2022-10-12", "2022-10-12", "2022-10-13", "callum.reid@acme.com"),
    ("SD-1010", "ethan.brooks@acme.com", "ana.souza@acme.com", "CRM", "Sales User", "Closed",
     "2025-03-02", "2025-03-03", "2025-03-04", "callum.reid@acme.com"),
]
with open(EVID_SD / "servicedesk_export.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Ticket #", "Requested By", "Approved By", "Application", "Access / Change Requested",
                "Ticket Status", "Date Created", "Date Approved", "Date Implemented", "Implemented By"])
    w.writerows(sd_rows)

# --------------------------------------------------------------------------
# 5. EMAILS (plain-text, .eml-style) - some approvals ONLY exist here
# --------------------------------------------------------------------------
def write_email(fname, frm, to, subject, date, body):
    content = f"From: {frm}\nTo: {to}\nSubject: {subject}\nDate: {date}\n\n{body}\n"
    (EVID_EMAIL / fname).write_text(content)

# Manager-only email approval for a sensitive FinERP profile - security approval never sought
# (this is how Isabelle's second, conflicting profile actually got approved - only by her own manager, over email,
#  bypassing the ticketing system's security-approval step entirely)
write_email(
    "email_001_isabelle_approval.txt",
    "miguel.alvarez@acme.com", "kwame.asante@acme.com",
    "Re: Isabelle - approve her for invoice approval too while Sarah is out",
    "Wed, 3 Jan 2024 09:14:00 +0000",
    "Kwame,\n\nGo ahead and give Isabelle approval rights in FinERP as well, we're short-staffed this week "
    "and I'll keep an eye on it. No need to loop in security for this one, it's temporary.\n\nThanks,\nMiguel",
)

# Clean, corroborating email for a legitimate change (matches ticket SD-1002)
write_email(
    "email_002_derek_confirmation.txt",
    "tomas.novak@acme.com", "derek.owusu@acme.com",
    "FinERP access provisioned - SD-1002",
    "Thu, 18 Feb 2021 15:02:00 +0000",
    "Hi Derek,\n\nYour AP Invoice Entry access in FinERP has been provisioned per SD-1002, approved by Miguel "
    "on 16-Feb-2021.\n\nRegards,\nTomas",
)

# Email revealing the dormant AP Admin grant to Derek was a one-off migration task, never revoked after
write_email(
    "email_003_ap_admin_temp.txt",
    "kwame.asante@acme.com", "miguel.alvarez@acme.com",
    "Temp AP Admin for year-end migration",
    "Fri, 8 Jan 2026 11:40:00 +0000",
    "Miguel,\n\nGranted Derek temporary AP Admin in FinERP so he can run the year-end vendor migration script. "
    "Please confirm once done so I can remove it again.\n\nKwame",
)

# --------------------------------------------------------------------------
# 6. GROUND TRUTH (hidden answer key - scoring only)
# --------------------------------------------------------------------------
ground_truth = {
    "issues": [
        {
            "id": "GT-01", "type": "JML_TERMINATED_ACTIVE_ACCOUNT",
            "system": "FinERP", "person": "Jonathan Ito", "email": "jonathan.ito@acme.com",
            "expected_severity": "Critical",
            "detail": "Terminated 2026-07-31; FinERP account FE-006 still Active, last login 02-Sep-2026 (post-termination use).",
        },
        {
            "id": "GT-02", "type": "JML_TERMINATED_ACTIVE_ACCOUNT",
            "system": "Payroll", "person": "Noor Hassan", "email": "noor.hassan@acme.com",
            "expected_severity": "Critical",
            "detail": "Terminated 2026-06-20; Payroll Read Only PR-003 still Active. Deprovisioning ticket SD-1007 raised but never implemented (still Open) - SLA breached by months.",
        },
        {
            "id": "GT-03", "type": "SOD_VIOLATION_ACCESS",
            "system": "FinERP", "person": "Isabelle Moreau", "email": "isabelle.moreau@acme.com",
            "expected_severity": "High",
            "detail": "Holds both AP Invoice Entry and AP Invoice Approval - conflicting profile pair per role matrix.",
        },
        {
            "id": "GT-04", "type": "MISSING_APPROVAL_EVIDENCE",
            "system": "FinERP", "person": "Isabelle Moreau", "email": "isabelle.moreau@acme.com",
            "expected_severity": "High",
            "detail": "AP Invoice Approval profile has no service-desk ticket; only a manager-only email (email_001) authorized it, and security approval required for this sensitive system was explicitly skipped.",
        },
        {
            "id": "GT-05", "type": "ORPHAN_ACCOUNT",
            "system": "FinERP", "person": "Contractor - B Hale", "email": "bhale@acme-consulting.com",
            "expected_severity": "Medium",
            "detail": "FE-007 has no matching record in employee master; external contractor address, no onboarding trace.",
        },
        {
            "id": "GT-06", "type": "EXCESS_ACCESS_UNEXPECTED_ROLE",
            "system": "FinERP", "person": "Marcus Lindgren", "email": "marcus.lindgren@acme.com",
            "expected_severity": "High",
            "detail": "Sales Rep holds AP Invoice Approval - not part of any role in the access matrix for Sales Rep.",
        },
        {
            "id": "GT-07", "type": "PROVISIONING_SOD_SELF_APPROVED",
            "system": "FinERP", "person": "Marcus Lindgren", "email": "marcus.lindgren@acme.com",
            "expected_severity": "Critical",
            "detail": "Ticket SD-1004: requester and approver are the same person (self-approved access request).",
        },
        {
            "id": "GT-08", "type": "APPROVAL_AFTER_IMPLEMENTATION",
            "system": "FinERP", "person": "Kwame Asante", "email": "kwame.asante@acme.com",
            "expected_severity": "Medium",
            "detail": "Ticket SD-1005: implemented 2026-09-02 before approval recorded 2026-09-05 - access granted ahead of approval.",
        },
        {
            "id": "GT-09", "type": "DORMANT_ACCOUNT_NOT_REVIEWED",
            "system": "FinERP", "person": "Derek Owusu", "email": "derek.owusu@acme.com",
            "expected_severity": "Medium",
            "detail": "FE-009 AP Admin last login 10-Jan-2026 (>90 days), still Active; email_003 shows it was meant to be temporary and revoked, but was not.",
        },
        {
            "id": "GT-10", "type": "MISSING_DEPROVISIONING_RECORD",
            "system": "FinERP", "person": "Jonathan Ito", "email": "jonathan.ito@acme.com",
            "expected_severity": "High",
            "detail": "No service-desk deprovisioning ticket exists at all for Jonathan Ito's termination - control/evidence gap, compounds GT-01.",
        },
        {
            "id": "GT-12", "type": "MISSING_APPROVAL_EVIDENCE",
            "system": "FinERP", "person": "Derek Owusu", "email": "derek.owusu@acme.com",
            "expected_severity": "High",
            "detail": "AP Admin (FE-009) has no service-desk ticket, and the only related email (email_003) is "
                      "from Kwame Asante (IT Admin, not an approver-eligible role) notifying rather than "
                      "authorizing - no valid approval evidence exists for this grant at all.",
        },
        {
            "id": "GT-11", "type": "CLEAN_TIMELY_DEPROVISIONING",
            "system": "CRM", "person": "Helena Cruz", "email": "helena.cruz@acme.com",
            "expected_severity": "N/A - should PASS, not be flagged",
            "detail": "Terminated 2026-08-15; CRM account disabled same day per SD-1006. Negative control: pipeline must NOT raise a finding here.",
        },
    ]
}
with open(GT / "planted_issues.yaml", "w") as f:
    yaml.dump(ground_truth, f, sort_keys=False)

print("Dataset generated:")
for d in (COMPANY, EVID_SHEETS, EVID_SD, EVID_EMAIL, GT):
    for p in sorted(d.iterdir()):
        print(" -", p.relative_to(ROOT))
