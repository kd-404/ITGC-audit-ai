"""Local web GUI for the ITGC audit engine.

Run with:
    python3 webapp/server.py
then open http://127.0.0.1:8420 in a browser.

This is a single-workspace, single-user local tool (an auditor working one
engagement at a time on their own machine) - no auth, no multi-tenancy, all
state lives on disk under webapp_data/current/ so nothing is lost between
restarts. That's a deliberate scope choice for a local desktop tool, not an
oversight; see README.md "what needs upgrading for production" for what a
multi-user/hosted version would need instead.
"""
from __future__ import annotations

import json
import shutil
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse, HTMLResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.requests import Request
import yaml

from itgc.pipeline import run_pipeline, _finding_to_json, _enquiry_to_json
from itgc.ingest.classify import classify_file
from itgc.control_registry import list_controls, resolve_selected_controls, ALL_CONTROL_IDS

WORKSPACE = ROOT / "webapp_data" / "current"
COMPANY_DIR = WORKSPACE / "company"
EVIDENCE_DIR = WORKSPACE / "evidence"
OUTPUT_DIR = WORKSPACE / "outputs"
ANSWERS_PATH = WORKSPACE / "answers.yaml"

SAMPLE_COMPANY = ROOT / "data" / "company"
SAMPLE_EVIDENCE = ROOT / "data" / "evidence"

for d in (COMPANY_DIR, EVIDENCE_DIR, OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

# in-memory cache of the last run's rich objects (ctx etc.) so /api/results
# doesn't have to re-run the pipeline just to answer a page load
STATE = {"last_result": None, "last_run_at": None, "error": None, "selected_controls": list(ALL_CONTROL_IDS)}


def _known_systems():
    matrix_path = COMPANY_DIR / "role_access_matrix.yaml"
    if not matrix_path.exists():
        return []
    with open(matrix_path) as f:
        return list((yaml.safe_load(f) or {}).get("applications", {}).keys())


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
async def api_state(request: Request):
    company_files = sorted(p.name for p in COMPANY_DIR.iterdir() if p.is_file())
    evidence_files = sorted(str(p.relative_to(EVIDENCE_DIR)) for p in EVIDENCE_DIR.rglob("*") if p.is_file())
    return JSONResponse({
        "company_files": company_files,
        "evidence_files": evidence_files,
        "has_run": STATE["last_result"] is not None,
        "last_run_at": STATE["last_run_at"],
        "error": STATE["error"],
    })


async def api_controls(request: Request):
    """Lists the selectable ITGC control domains and what evidence each one
    needs, for the Controls tab's "what do I need to provide" flow."""
    return JSONResponse({"controls": list_controls(), "selected": STATE["selected_controls"]})


async def api_set_controls(request: Request):
    body = await request.json()
    selected = body.get("selected_controls") or []
    STATE["selected_controls"] = sorted(resolve_selected_controls(selected)) if selected else list(ALL_CONTROL_IDS)
    return JSONResponse({"ok": True, "selected": STATE["selected_controls"]})


async def api_upload(request: Request):
    form = await request.form()
    kind = form.get("kind", "evidence")
    target_dir = COMPANY_DIR if kind == "company" else EVIDENCE_DIR
    saved = []
    files = form.getlist("files")
    for uf in files:
        if not hasattr(uf, "filename") or not uf.filename:
            continue
        dest = target_dir / uf.filename
        content = await uf.read()
        dest.write_bytes(content)
        saved.append(uf.filename)
    return JSONResponse({"saved": saved, "kind": kind})


async def api_load_sample(request: Request):
    shutil.rmtree(COMPANY_DIR, ignore_errors=True)
    shutil.rmtree(EVIDENCE_DIR, ignore_errors=True)
    shutil.copytree(SAMPLE_COMPANY, COMPANY_DIR)
    shutil.copytree(SAMPLE_EVIDENCE, EVIDENCE_DIR)
    STATE["last_result"] = None
    STATE["error"] = None
    return JSONResponse({"ok": True})


async def api_reset(request: Request):
    shutil.rmtree(COMPANY_DIR, ignore_errors=True)
    shutil.rmtree(EVIDENCE_DIR, ignore_errors=True)
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    for d in (COMPANY_DIR, EVIDENCE_DIR, OUTPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)
    if ANSWERS_PATH.exists():
        ANSWERS_PATH.unlink()
    STATE["last_result"] = None
    STATE["last_run_at"] = None
    STATE["error"] = None
    return JSONResponse({"ok": True})


async def api_preview_files(request: Request):
    """How each uploaded file currently classifies, without running the full
    pipeline - lets the user sanity-check ingestion before running the audit."""
    known_systems = _known_systems()
    results = []
    for base, label in ((COMPANY_DIR, "company"), (EVIDENCE_DIR, "evidence")):
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            try:
                c = classify_file(p)
                results.append({
                    "file": str(p.relative_to(base)), "area": label,
                    "evidence_type": c["evidence_type"], "confidence": round(c["confidence"], 2),
                })
            except Exception as e:
                results.append({"file": str(p.relative_to(base)), "area": label,
                                 "evidence_type": "error", "confidence": 0.0, "error": str(e)})
    return JSONResponse({"files": results})


async def api_run(request: Request):
    body = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.json()
    as_of_str = body.get("as_of") or date.today().isoformat()
    use_llm = bool(body.get("use_llm", True))
    selected_controls = body.get("selected_controls")
    if selected_controls is not None:
        STATE["selected_controls"] = sorted(resolve_selected_controls(selected_controls))

    try:
        result = run_pipeline(
            company_dir=COMPANY_DIR, evidence_dir=EVIDENCE_DIR, output_dir=OUTPUT_DIR,
            as_of=date.fromisoformat(as_of_str), use_llm=use_llm,
            answers_path=ANSWERS_PATH if ANSWERS_PATH.exists() else None,
            selected_controls=STATE["selected_controls"],
        )
        STATE["last_result"] = result
        STATE["last_run_at"] = datetime.now().isoformat(timespec="seconds")
        STATE["error"] = None
        return JSONResponse({
            "ok": True,
            "llm_status": result["llm_status"],
            "n_findings": len(result["findings"]),
            "n_enquiries": len(result["enquiries"]),
            "controls_run": result["controls_run"],
        })
    except Exception as e:
        STATE["error"] = f"{type(e).__name__}: {e}"
        tb = traceback.format_exc()
        return JSONResponse({"ok": False, "error": STATE["error"], "traceback": tb}, status_code=500)


async def api_results(request: Request):
    result = STATE["last_result"]
    if result is None:
        return JSONResponse({"ok": False, "error": "No run yet. POST /api/run first."}, status_code=404)
    findings = [_finding_to_json(f) for f in result["findings"]]
    enquiries = [_enquiry_to_json(e) for e in result["enquiries"]]
    file_classifications = result["ctx"].bundle.file_classifications
    counts = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    return JSONResponse({
        "ok": True,
        "findings": findings,
        "enquiries": enquiries,
        "file_classifications": file_classifications,
        "severity_counts": counts,
        "llm_status": result["llm_status"],
        "last_run_at": STATE["last_run_at"],
        "controls_run": result.get("controls_run", []),
    })


async def api_evidence_map(request: Request):
    result = STATE["last_result"]
    if result is None:
        return JSONResponse({"ok": False, "error": "No run yet. POST /api/run first."}, status_code=404)
    from itgc.evidence_map import evidence_map_to_json
    cases = evidence_map_to_json(result["evidence_cases"])
    return JSONResponse({"ok": True, "cases": cases})


async def api_correlations(request: Request):
    result = STATE["last_result"]
    if result is None:
        return JSONResponse({"ok": False, "error": "No run yet. POST /api/run first."}, status_code=404)
    from itgc.correlation import correlated_cases_to_json
    cases = correlated_cases_to_json(result["correlated_cases"])
    return JSONResponse({"ok": True, "cases": cases})


async def api_answer(request: Request):
    body = await request.json()
    enquiry_id, answer = body.get("enquiry_id"), body.get("answer")
    data = {"answers": {}}
    if ANSWERS_PATH.exists():
        with open(ANSWERS_PATH) as f:
            data = yaml.safe_load(f) or {"answers": {}}
    data.setdefault("answers", {})[enquiry_id] = answer
    with open(ANSWERS_PATH, "w") as f:
        yaml.dump(data, f, sort_keys=False)
    return JSONResponse({"ok": True, "note": "Answer saved. Re-run the audit to see it reflected in the workpaper."})


async def api_download_workpaper(request: Request):
    path = OUTPUT_DIR / "ITGC_UAR_Workpaper.xlsx"
    if not path.exists():
        return JSONResponse({"error": "No workpaper yet - run the audit first."}, status_code=404)
    return FileResponse(path, filename="ITGC_UAR_Workpaper.xlsx")


async def api_download_report(request: Request):
    path = OUTPUT_DIR / "ITGC_Audit_Report.pdf"
    if not path.exists():
        return JSONResponse({"error": "No report yet - run the audit first."}, status_code=404)
    return FileResponse(path, filename="ITGC_Audit_Report.pdf", media_type="application/pdf")


async def index(request: Request):
    return FileResponse(Path(__file__).parent / "static" / "index.html")


routes = [
    Route("/", index),
    Route("/api/state", api_state),
    Route("/api/controls", api_controls),
    Route("/api/controls", api_set_controls, methods=["POST"]),
    Route("/api/upload", api_upload, methods=["POST"]),
    Route("/api/load-sample", api_load_sample, methods=["POST"]),
    Route("/api/reset", api_reset, methods=["POST"]),
    Route("/api/preview-files", api_preview_files),
    Route("/api/run", api_run, methods=["POST"]),
    Route("/api/results", api_results),
    Route("/api/evidence-map", api_evidence_map),
    Route("/api/correlations", api_correlations),
    Route("/api/answer", api_answer, methods=["POST"]),
    Route("/api/download/workpaper", api_download_workpaper),
    Route("/api/download/report", api_download_report),
    Mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"),
]

app = Starlette(routes=routes)

if __name__ == "__main__":
    import os
    import uvicorn
    # HF Spaces (and most container platforms) inject PORT and expect the
    # process to bind 0.0.0.0; locally this still defaults to the familiar
    # 127.0.0.1:8420 with no env vars set.
    port = int(os.environ.get("PORT", 8420))
    host = "0.0.0.0" if "PORT" in os.environ or "SPACE_ID" in os.environ else "127.0.0.1"
    print(f"ITGC Audit AI - open http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port} in your browser")
    uvicorn.run(app, host=host, port=port)
