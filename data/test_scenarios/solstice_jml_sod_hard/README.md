# Solstice Freight & Logistics Ltd - CargoLink TMS (hard scenario)

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
