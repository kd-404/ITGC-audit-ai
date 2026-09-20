# ITGC Audit AI — User Access Review, proven end-to-end

A working proof of the evidence-driven ITGC audit assistant: drop in an
employee master, UAR exports, a service-desk extract and emails in whatever
format they arrive, and it identifies people/roles, classifies the evidence,
correlates it, runs deterministic ITGC tests, and produces an audit workpaper
with condition/criteria/cause/effect/recommendation for every finding — plus
a list of enquiries for anything it couldn't resolve on its own.

Runs entirely locally. The only optional network call is to a local Ollama
server (`http://localhost:11434`) for turning a finding into a narrative
paragraph — nothing else leaves the machine, and if Ollama isn't running the
pipeline still produces every finding, just with a template narrative
instead of an LLM one.

## Why UAR first

This proves the hard part — messy-input ingestion, identity resolution,
evidence correlation, and the deterministic-verdict/LLM-narrative split —
against one real ITGC test end to end, rather than a shallow pass over many.
The architecture (`src/itgc/tests_itgc/`) is built so the next test (JML
beyond deprovisioning, change management, privileged access, SoD across
systems) is a new file in that folder, not a redesign.

## GUI (recommended way to use it)

```bash
pip install -r requirements.txt
python3 scripts/generate_dataset.py     # builds the sample ACME evidence set, only needed once
python3 webapp/server.py                # then open http://127.0.0.1:8420
```

Four tabs:
1. **Evidence** — drag-and-drop company policy files and evidence separately, or click "Load sample ACME dataset" to try it immediately. "Preview classification" shows how each file will be read *before* you commit to a run. "Run Audit" executes the full pipeline.
2. **Findings** — every finding as an expandable card (condition/criteria/cause/effect/recommendation/evidence/narrative), filterable by severity and system. Download the Excel workpaper from here.
3. **Enquiries** — anything the engine couldn't resolve alone, with an inline answer box. Answers are saved immediately; re-run the audit to see them reflected.
4. **Summary** — severity counts and the full evidence-ingestion audit trail (what every file was classified as, and with what confidence).

This is a **local, single-engagement tool** — no login, no multi-user support, state lives on disk under `webapp_data/current/`. "Reset engagement" on the Evidence tab clears it to start a new one. See "what needs upgrading for production" below for what a shared/hosted version would need.

## CLI (scriptable / CI use)

```bash
python3 scripts/run_pipeline.py         # runs the audit, writes outputs/
python3 scripts/run_scoring.py          # scores outputs/findings.json against the hidden ground truth
python3 -m unittest discover -s tests -v
```

Point it at your own evidence:

```bash
python3 scripts/run_pipeline.py --company /path/to/company_docs --evidence /path/to/client_evidence --out outputs
```

`--company` expects an employee master (any spreadsheet layout) plus
`role_access_matrix.yaml` and `company_context.yaml` (see `data/company/` for
the format — this is your policy, not evidence, so it isn't auto-detected).
`--evidence` accepts any mix of `.xlsx`/`.csv` UAR exports, service-desk
exports, and `.txt`/`.eml` emails, in any subfolder structure.

To use a real local LLM for narratives: `ollama serve` and
`ollama pull llama3.1` (or set `OLLAMA_MODEL`), then just run the pipeline
normally — it detects Ollama automatically. `--no-llm` skips narrative
generation entirely.

## What it actually does (pipeline stages)

```
data/company/  (policy: employee master, role-access matrix, SoD rules)
data/evidence/ (arbitrary UAR sheets, service-desk export, emails)
        │
        ▼
1. INGEST      classify each file by content (not filename), detect the real
                header row under banner/title rows, fuzzy-map columns to a
                canonical schema      → src/itgc/ingest/
        ▼
2. RESOLVE     tie every account/requester/approver/email sender back to the
                employee master (exact email → email local-part → fuzzy name);
                anything below confidence becomes an enquiry, not a guess
                                        → src/itgc/identity/
        ▼
3. TEST        deterministic ITGC rules: JML/deprovisioning, SoD, excess
                access, dormant accounts, orphan accounts, provisioning
                self-approval, approval-after-implementation, missing
                approval evidence (incl. required security approval for
                sensitive systems)     → src/itgc/tests_itgc/
        ▼
4. NARRATE     (optional) local LLM turns each already-decided finding into
                a workpaper paragraph — it cannot change type/severity/
                evidence, only explain it  → src/itgc/llm/
        ▼
5. REPORT      Excel workpaper (Summary / Findings / Enquiries / Evidence
                Index tabs) + text summary + JSON  → src/itgc/report/
```

The LLM is never on the critical path for a verdict — every finding_type,
severity, and evidence citation is produced by rules in `tests_itgc/` before
the AI gateway is even called. If Ollama is down, findings are identical;
only the prose narrative reverts to a template.

## The enquiry loop

Not everything is resolvable from the evidence alone. The pipeline raises an
**enquiry** instead of guessing when:
- a file doesn't match any known evidence schema,
- an account's identity match is ambiguous (mid-confidence fuzzy match),
- an account matches no employee at all (also raised as an `ORPHAN_ACCOUNT`
  finding, since that's an audit conclusion by itself, not just a data gap).

Enquiries land in `outputs/enquiries.json` and the workpaper's Enquiries tab.
Answer them in `data/answers.yaml` and re-run — matched answers show up
against the enquiry on the next run.

## Proving it against ground truth

`scripts/generate_dataset.py` builds a synthetic ACME Industries evidence set
with **11 deliberately planted ITGC issues** across FinERP/Payroll/CRM
(terminated-but-active accounts, SoD conflicts, self-approved access,
approval-after-implementation, orphan/contractor accounts, excess access
outside role, dormant unreviewed access, missing/incomplete deprovisioning
records, and missing approval evidence for a sensitive-system grant) **plus
one negative control** (a termination deprovisioned correctly and on time,
which must NOT be flagged). The answer key lives in
`data/ground_truth/planted_issues.yaml` and is read only by
`scripts/run_scoring.py` — never by the pipeline.

Current result: **100% recall, 100% precision, 0 false alarms on the
negative control** (`python3 scripts/run_scoring.py`).

## Project layout

```
itgc-audit-ai/
├── data/
│   ├── company/         policy: employee master, role-access matrix, context (edit for your engagement)
│   ├── evidence/         drop client evidence here (sheets/, servicedesk/, email/ are just suggested subfolders)
│   ├── ground_truth/     scoring-only answer key for the sample dataset - never read by the pipeline
│   └── answers.yaml      your answers to raised enquiries
├── src/itgc/
│   ├── models.py         Employee/AccessRecord/Ticket/EmailEvidence/Finding/Enquiry
│   ├── policy.py         loads role-access matrix, SoD conflicts, SLA/dormancy thresholds
│   ├── ingest/           format-agnostic tabular loader, header/column fuzzy matching, email parser, classifier
│   ├── identity/         email/name resolution across all evidence sources
│   ├── tests_itgc/       the actual ITGC test rules (one file per concern)
│   ├── enquiry.py         builds/answers the enquiry list
│   ├── llm/               Ollama client + AI Gateway (narrative-only, deterministic fallback)
│   ├── report/            Excel workpaper + text summary
│   ├── context.py         wires it all together into one AuditContext
│   └── pipeline.py        the end-to-end entry point
├── scripts/
│   ├── generate_dataset.py  builds the ACME sample evidence + hidden ground truth
│   ├── run_pipeline.py      CLI entry point
│   └── run_scoring.py       scores outputs/findings.json against ground truth
├── webapp/
│   ├── server.py            Starlette app - all API routes, wraps src/itgc directly
│   └── static/              index.html + app.js + style.css (vanilla JS, no build step)
├── webapp_data/current/     the GUI's working engagement: uploaded company/evidence files + outputs + answers.yaml
├── tests/                 unittest suite (stdlib only - no pytest in this sandbox; use pytest locally if you prefer)
└── outputs/                workpaper.xlsx, summary.txt, findings.json, enquiries.json (CLI output; the GUI writes to webapp_data/current/outputs/ instead)
```

## Extending to the rest of ITGC (next phases)

The UAR test proves the pattern; the same `AuditContext` + evidence model
supports the rest without re-architecting:

1. **Joiner/Mover**: role-change events (not just leavers) against the
   access matrix — mostly reuses `access.py`'s excess-access logic.
2. **Change management**: needs a change-ticket schema (similar shape to
   the service-desk schema) plus a test for change approval before
   deployment, and segregation between developer/deployer.
3. **Privileged access**: a stricter profile-sensitivity tier and periodic
   review-evidence check (who reviewed privileged accounts, and when).
4. **Backup/job scheduling/incident management**: each needs its own small
   evidence schema in `ingest/schemas.py` and test file in `tests_itgc/`;
   nothing else changes.

## Known limitations (be upfront about these with a client)

- Identity resolution is exact-email / email-local-part / fuzzy-name. It
  will ask (enquiry) rather than guess on anything genuinely ambiguous, but
  it has not been tested against real messy client HR exports with multiple
  legal-name changes, shared surnames, etc. — validate against a real sample
  before relying on it.
- Email parsing here is a plain header/body parser (`From:`/`To:`/`Subject:`/
  `Date:` + body), not a full MIME parser — real `.eml`/`.msg` exports from
  Outlook/Gmail may need a small adapter in `ingest/email_reader.py`.
- The LLM narrative step sends the **already-redacted, structured finding**
  (type, dates, system names, role names) to Ollama, not raw evidence files —
  but confirm your local Ollama model and setup meet your client's data
  handling requirements before using this on real engagement evidence.
- The role-access matrix and SoD conflicts are defined once per engagement in
  YAML (`data/company/role_access_matrix.yaml`) — building this from a real
  client's policy is itself audit work; the tool doesn't infer it for you.
