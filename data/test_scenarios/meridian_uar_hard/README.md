# Meridian Textiles Pvt Ltd - Horizon ERP UAR (hard scenario)

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
