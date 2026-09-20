"""Canonical field definitions for each evidence shape we know how to ingest.

Each schema is a list of (canonical_field, [alias phrases the header cell might
say]). Header detection and column mapping both fuzzy-match against these, so
a client's own column names ("Emp Code" vs "Employee ID" vs "Personnel Number")
don't need to be hard-coded exactly.
"""

EMPLOYEE_MASTER_SCHEMA = {
    "emp_id":        ["emp id", "emp code", "employee id", "employee code", "personnel number", "staff id"],
    "full_name":     ["employee name", "full name", "name", "staff name"],
    "email":         ["work email", "email", "email address", "work email address"],
    "department":    ["department", "dept", "division"],
    "job_title":     ["job title", "title", "position", "role"],
    "manager_email": ["reporting manager", "manager email", "manager (email)", "reporting manager (email)", "supervisor email"],
    "status":        ["employment status", "status", "emp status"],
    "hire_date":     ["date of hire", "hire date", "start date", "joining date"],
    "term_date":     ["termination date", "term date", "last working day", "separation date"],
}

UAR_SCHEMA = {
    "account_id":      ["user id", "account id", "login id", "username"],
    "account_name":    ["user full name", "user name", "full name", "display name"],
    "account_email":   ["email address", "email", "user email"],
    "profiles":        ["access profile(s)", "access profile", "role(s)", "profile", "entitlement", "access role"],
    "account_status":  ["account status", "status", "user status"],
    "last_login":      ["last login", "last login date", "last logon", "last access date"],
    "snapshot_date":   ["snapshot date", "extract date", "as of date", "as-of date", "pull date",
                         "review period date", "export date"],
}

SERVICEDESK_SCHEMA = {
    "ticket_id":            ["ticket #", "ticket id", "ticket number", "request id"],
    "requester_email":      ["requested by", "requester", "raised by", "requestor"],
    "approver_email":       ["approved by", "approver"],
    "system":               ["application", "system", "system/application"],
    "access_requested":     ["access / change requested", "access requested", "change requested", "description"],
    "status":               ["ticket status", "status"],
    "created":              ["date created", "created date", "opened date", "raised date"],
    "approved":             ["date approved", "approved date", "approval date"],
    "implemented":          ["date implemented", "implemented date", "resolved date", "closed date"],
    "implementer_email":    ["implemented by", "implementer", "resolved by"],
}

CHANGE_RECORD_SCHEMA = {
    "change_id":        ["change id", "change #", "cr number", "change request id", "ticket #"],
    "system":           ["system", "application", "environment/system"],
    "description":      ["description", "change description", "summary"],
    "requested_by":     ["requested by", "requestor", "raised by"],
    "developer":        ["developer", "implemented by", "developed by", "author"],
    "approver":         ["approved by", "approver", "cab approver"],
    "deployer":         ["deployed by", "deployer", "released by"],
    "environment":      ["environment", "target environment"],
    "test_evidence_ref":["test evidence", "test reference", "uat sign-off", "qa reference"],
    "requested_date":   ["date requested", "request date", "raised date"],
    "approved_date":    ["date approved", "approval date"],
    "deployed_date":    ["date deployed", "deployment date", "release date", "go-live date"],
    "status":           ["status", "change status"],
    "emergency_flag":   ["emergency change", "is emergency", "change type"],
    "post_review_date": ["post implementation review date", "post-review date", "pir date", "retrospective review date"],
    "post_reviewed_by": ["post implementation reviewed by", "post-review by", "pir reviewer", "reviewed by"],
}

PRIVILEGED_ACCESS_REVIEW_SCHEMA = {
    "review_id":        ["review id", "review #"],
    "account_id":       ["account id", "user id", "login id"],
    "system":           ["system", "application"],
    "reviewer":         ["reviewed by", "reviewer"],
    "review_date":      ["review date", "date reviewed"],
    "justification":    ["justification", "business justification", "reason"],
    "decision":         ["decision", "outcome", "action"],
}

BACKUP_JOB_SCHEMA = {
    "job_id":           ["job id", "backup job id", "job name"],
    "system":           ["system", "application", "server"],
    "scheduled_time":   ["scheduled time", "run time", "start time"],
    "status":           ["status", "job status", "result"],
    "job_type":         ["job type", "type", "test type", "backup type"],
    "verified_by":      ["verified by", "checked by"],
    "verification_date":["verification date", "date verified"],
}

INCIDENT_SCHEMA = {
    "incident_id":      ["incident id", "incident #", "ticket #"],
    "system":           ["system", "application", "affected system"],
    "severity":         ["severity", "priority"],
    "description":      ["description", "summary", "incident summary"],
    "reported_date":    ["date reported", "reported date", "opened date"],
    "resolved_date":    ["date resolved", "resolved date", "closed date"],
    "root_cause":       ["root cause", "rca"],
    "status":           ["status", "incident status"],
}

SCHEMAS = {
    "employee_master": EMPLOYEE_MASTER_SCHEMA,
    "uar_sheet": UAR_SCHEMA,
    "servicedesk": SERVICEDESK_SCHEMA,
    "change_record": CHANGE_RECORD_SCHEMA,
    "privileged_access_review": PRIVILEGED_ACCESS_REVIEW_SCHEMA,
    "backup_job": BACKUP_JOB_SCHEMA,
    "incident": INCIDENT_SCHEMA,
}
