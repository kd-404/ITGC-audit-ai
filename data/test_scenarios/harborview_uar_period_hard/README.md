# Harborview Behavioral Health - ClinCareEHR (hard scenario)

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

    python3 scripts/run_pipeline.py \
        --company data/test_scenarios/harborview_uar_period_hard/company \
        --evidence data/test_scenarios/harborview_uar_period_hard/evidence \
        --as-of 2026-09-14 --no-llm

Work the case from the raw evidence first - read both UAR extracts, the
ticket export, and all four emails - before checking your own conclusions
against ANSWER_KEY_PRIVATE.md or the pipeline's own output.
