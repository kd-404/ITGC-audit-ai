const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ---------------------------------------------------------------- tabs ----
$$(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    $$(".tab-btn").forEach(b => b.classList.remove("active"));
    $$(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// -------------------------------------------------------------- controls --
let ALL_CONTROLS = [];
let SELECTED_CONTROLS = [];

async function loadControls() {
  const res = await fetch("/api/controls");
  const data = await res.json();
  ALL_CONTROLS = data.controls;
  SELECTED_CONTROLS = data.selected;
  renderControls();
  renderControlsInScope();
}

function renderControls() {
  $("#controls-list").innerHTML = ALL_CONTROLS.map(controlCardHtml).join("");
  $$(".control-checkbox").forEach(cb => {
    cb.addEventListener("change", () => {
      const id = cb.dataset.id;
      if (cb.checked) {
        if (!SELECTED_CONTROLS.includes(id)) SELECTED_CONTROLS.push(id);
      } else {
        SELECTED_CONTROLS = SELECTED_CONTROLS.filter(c => c !== id);
      }
      cb.closest(".control-card").classList.toggle("selected", cb.checked);
      $("#controls-save-status").textContent = "Unsaved selection changes.";
    });
  });
}

function controlCardHtml(c) {
  const checked = SELECTED_CONTROLS.includes(c.control_id) ? "checked" : "";
  const optional = c.optional_evidence && c.optional_evidence.length
    ? `<h5>Optional / helps corroborate</h5><ul>${c.optional_evidence.map(e => `<li>${escapeHtml(e)}</li>`).join("")}</ul>`
    : "";
  return `
  <div class="control-card ${checked ? "selected" : ""}">
    <label class="control-head">
      <input type="checkbox" class="control-checkbox" data-id="${c.control_id}" ${checked}>
      <div>
        <div class="control-name">${escapeHtml(c.name)}</div>
        <div class="control-desc">${escapeHtml(c.description)}</div>
      </div>
    </label>
    <div class="control-evidence">
      <h5>You'll need to provide</h5>
      <ul>${c.required_evidence.map(e => `<li>${escapeHtml(e)}</li>`).join("")}</ul>
      ${optional}
      <div class="findings-hint">Detects: ${c.finding_types.join(", ")}</div>
    </div>
  </div>`;
}

function renderControlsInScope() {
  const el = $("#controls-in-scope");
  if (!el) return;
  el.textContent = SELECTED_CONTROLS.length === ALL_CONTROLS.length
    ? "All controls in scope for this run"
    : `${SELECTED_CONTROLS.length} of ${ALL_CONTROLS.length} control(s) in scope for this run`;
}

$("#btn-save-controls").addEventListener("click", async () => {
  await fetch("/api/controls", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_controls: SELECTED_CONTROLS }),
  });
  $("#controls-save-status").textContent = "Selection saved.";
  renderControlsInScope();
});

// ------------------------------------------------------------- uploads ----
function wireDropzone(zoneId, inputId, kind) {
  const zone = $(zoneId), input = $(inputId);
  zone.addEventListener("click", () => input.click());
  input.addEventListener("change", () => uploadFiles(input.files, kind));
  ["dragover", "dragenter"].forEach(evt =>
    zone.addEventListener(evt, e => { e.preventDefault(); zone.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach(evt =>
    zone.addEventListener(evt, e => { e.preventDefault(); zone.classList.remove("dragover"); }));
  zone.addEventListener("drop", e => uploadFiles(e.dataTransfer.files, kind));
}
wireDropzone("#drop-company", "#file-company", "company");
wireDropzone("#drop-evidence", "#file-evidence", "evidence");

async function uploadFiles(fileList, kind) {
  if (!fileList || fileList.length === 0) return;
  const form = new FormData();
  form.append("kind", kind);
  for (const f of fileList) form.append("files", f);
  await fetch("/api/upload", { method: "POST", body: form });
  refreshState();
}

$("#btn-sample").addEventListener("click", async () => {
  setRunLog("Loading sample ACME dataset...", "");
  await fetch("/api/load-sample", { method: "POST" });
  setRunLog("Sample ACME dataset loaded (24 employees; UAR, service desk, change log, privileged access review, backup log and incident log evidence; 25 planted issues across all 7 control domains).", "ok");
  refreshState();
});

$("#btn-reset").addEventListener("click", async () => {
  if (!confirm("Clear all uploaded files and results for this engagement?")) return;
  await fetch("/api/reset", { method: "POST" });
  setRunLog("Engagement reset.", "ok");
  refreshState();
  renderFindings({ findings: [] });
  renderEnquiries({ enquiries: [] });
});

$("#btn-preview").addEventListener("click", async () => {
  const res = await fetch("/api/preview-files");
  const data = await res.json();
  const tbody = $("#preview-table tbody");
  tbody.innerHTML = "";
  data.files.forEach(f => {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${f.file}</td><td>${f.area}</td><td>${f.evidence_type}</td><td>${(f.confidence * 100).toFixed(0)}%</td>`;
    tbody.appendChild(tr);
  });
  $("#preview-panel").classList.remove("hidden");
});

$("#btn-run").addEventListener("click", async () => {
  setRunLog("Running audit...", "");
  const asOf = $("#as-of-date").value || new Date().toISOString().slice(0, 10);
  const useLlm = $("#use-llm").checked;
  const res = await fetch("/api/run", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ as_of: asOf, use_llm: useLlm, selected_controls: SELECTED_CONTROLS }),
  });
  const data = await res.json();
  if (!data.ok) {
    setRunLog("Run failed:\n" + data.error + "\n\n" + (data.traceback || ""), "error");
    return;
  }
  setRunLog(`Run complete (controls: ${data.controls_run.join(", ")}). ${data.n_findings} findings, ${data.n_enquiries} enquiries. Narratives: ${data.llm_status}.`, "ok");
  refreshState();
  loadResults();
  loadEvidenceMap();
});

function setRunLog(text, cls) {
  const el = $("#run-log");
  el.classList.remove("hidden", "ok", "error");
  if (cls) el.classList.add(cls);
  el.textContent = text;
}

async function refreshState() {
  const res = await fetch("/api/state");
  const data = await res.json();
  $("#list-company").innerHTML = data.company_files.map(f => `<li>${f}</li>`).join("");
  $("#list-evidence").innerHTML = data.evidence_files.map(f => `<li>${f}</li>`).join("");
  $("#topbar-status").textContent = data.has_run
    ? `Last run: ${data.last_run_at}`
    : `${data.company_files.length} policy file(s), ${data.evidence_files.length} evidence file(s) loaded`;
  if (!$("#as-of-date").value) {
    $("#as-of-date").value = new Date().toISOString().slice(0, 10);
  }
}

// ------------------------------------------------------------- findings ---
let ALL_FINDINGS = [];

async function loadResults() {
  const res = await fetch("/api/results");
  if (res.status === 404) return;
  const data = await res.json();
  ALL_FINDINGS = data.findings;
  renderFindings(data);
  renderEnquiries(data);
  renderSummary(data);
}

function renderFindings(data) {
  const findings = data.findings || [];
  $("#findings-empty").classList.toggle("hidden", findings.length > 0);
  const systems = [...new Set(findings.map(f => f.system))].sort();
  const sysSelect = $("#filter-system");
  sysSelect.innerHTML = `<option value="">All systems</option>` + systems.map(s => `<option>${s}</option>`).join("");

  function draw() {
    const sevFilter = $("#filter-severity").value;
    const sysFilter = $("#filter-system").value;
    const filtered = findings.filter(f =>
      (!sevFilter || f.severity === sevFilter) && (!sysFilter || f.system === sysFilter));
    $("#findings-list").innerHTML = filtered.map(findingCardHtml).join("");
    $$(".finding-head").forEach(h => h.addEventListener("click", () => h.parentElement.classList.toggle("open")));
  }
  $("#filter-severity").onchange = draw;
  $("#filter-system").onchange = draw;
  draw();
}

function findingCardHtml(f) {
  const sevClass = "sev-" + f.severity.toLowerCase();
  return `
  <div class="finding-card ${sevClass}">
    <div class="finding-head">
      <span class="sev-pill ${sevClass}">${f.severity}</span>
      <span class="finding-type">${f.finding_type}</span>
      <span class="finding-title">${f.system} — ${f.subject_person || "unidentified"}</span>
      <span>${f.finding_id}</span>
    </div>
    <div class="finding-body">
      <dt>Condition</dt><dd>${escapeHtml(f.condition)}</dd>
      <dt>Criteria</dt><dd>${escapeHtml(f.criteria)}</dd>
      <dt>Cause</dt><dd>${escapeHtml(f.cause)}</dd>
      <dt>Effect</dt><dd>${escapeHtml(f.effect)}</dd>
      <dt>Recommendation</dt><dd>${escapeHtml(f.recommendation)}</dd>
      <dt>Evidence</dt><dd class="evidence-list">${f.evidence.map(escapeHtml).join("<br>")}</dd>
      ${f.narrative ? `<dt>Narrative</dt><dd>${escapeHtml(f.narrative)}</dd>` : ""}
    </div>
  </div>`;
}

// ------------------------------------------------------------ enquiries ---
function renderEnquiries(data) {
  const enquiries = data.enquiries || [];
  $("#enquiries-empty").classList.toggle("hidden", enquiries.length > 0);
  const badge = $("#enq-badge");
  const unanswered = enquiries.filter(e => !e.answer).length;
  badge.textContent = unanswered;
  badge.classList.toggle("hidden", unanswered === 0);

  $("#enquiries-list").innerHTML = enquiries.map(e => `
    <div class="enquiry-card" data-id="${e.enquiry_id}">
      <div class="enquiry-head">
        <span class="${e.blocking ? "blocking-pill" : "info-pill"}">${e.blocking ? "BLOCKING" : "INFO"}</span>
        <strong>${escapeHtml(e.topic)}</strong>
        <span style="color:var(--text-dim); font-size:12px;">${e.enquiry_id}</span>
      </div>
      <div class="enquiry-question">${escapeHtml(e.question)}</div>
      <div class="enquiry-context">${escapeHtml(e.context)}</div>
      ${e.answer
        ? `<div class="answered-tag">✓ Answered: ${escapeHtml(e.answer)}</div>`
        : `<div class="enquiry-answer-row">
             <input type="text" placeholder="Type the answer..." class="answer-input">
             <button class="btn-secondary answer-submit">Save answer</button>
           </div>`}
    </div>
  `).join("");

  $$(".answer-submit").forEach(btn => {
    btn.addEventListener("click", async () => {
      const card = btn.closest(".enquiry-card");
      const input = card.querySelector(".answer-input");
      const enquiry_id = card.dataset.id;
      await fetch("/api/answer", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enquiry_id, answer: input.value }),
      });
      card.querySelector(".enquiry-answer-row").outerHTML =
        `<div class="answered-tag">✓ Answered: ${escapeHtml(input.value)} (re-run audit to reflect in workpaper)</div>`;
    });
  });
}

// -------------------------------------------------------------- summary ---
function renderSummary(data) {
  $("#summary-empty").classList.add("hidden");
  $("#summary-content").classList.remove("hidden");
  $("#summary-title").textContent = `Last run: ${data.last_run_at} — narratives: ${data.llm_status}`;
  $("#summary-controls-run").textContent = `Controls checked this run: ${(data.controls_run || []).join(", ") || "none"}`;
  const order = ["Critical", "High", "Medium", "Low"];
  $("#stat-row").innerHTML = order.map(sev => `
    <div class="stat-tile sev-${sev.toLowerCase()}">
      <div class="n">${data.severity_counts[sev] || 0}</div>
      <div class="label">${sev}</div>
    </div>`).join("") + `
    <div class="stat-tile">
      <div class="n">${data.findings.length}</div>
      <div class="label">Total findings</div>
    </div>`;
  const tbody = $("#summary-evidence-table tbody");
  tbody.innerHTML = data.file_classifications.map(c => `
    <tr><td>${c.file}</td><td>${c.evidence_type}</td><td>${(c.confidence * 100).toFixed(0)}%</td></tr>
  `).join("");
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, m => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[m]));
}

// --------------------------------------------------------- evidence map ---
let ALL_CASES = [];
let CORRELATIONS_BY_CASE = {};

async function loadEvidenceMap() {
  const [mapRes, corrRes] = await Promise.all([
    fetch("/api/evidence-map"),
    fetch("/api/correlations"),
  ]);
  if (mapRes.status === 404) return;
  const data = await mapRes.json();
  ALL_CASES = data.cases;
  CORRELATIONS_BY_CASE = {};
  if (corrRes.status !== 404) {
    const corrData = await corrRes.json();
    (corrData.cases || []).forEach(c => { CORRELATIONS_BY_CASE[c.case_id] = c; });
  }
  renderEvidenceMap();
}

function renderEvidenceMap() {
  $("#map-empty").classList.toggle("hidden", ALL_CASES.length > 0);
  if (ALL_CASES.length === 0) return;

  function draw() {
    const q = $("#map-search").value.trim().toLowerCase();
    const filter = $("#map-filter").value;
    const filtered = ALL_CASES.filter(c => {
      if (q && !(c.subject_label.toLowerCase().includes(q) || (c.subject_email || "").toLowerCase().includes(q))) return false;
      if (filter === "findings" && c.related_finding_ids.length === 0) return false;
      if (filter === "enquiries" && c.related_enquiry_ids.length === 0) return false;
      if (filter === "unresolved" && c.resolved) return false;
      if (filter === "correlated" && !CORRELATIONS_BY_CASE[c.case_id]) return false;
      return true;
    });
    $("#map-list").innerHTML = filtered.map(caseCardHtml).join("") || `<div class="empty-state">No cases match.</div>`;
    $$(".case-head").forEach(h => h.addEventListener("click", () => h.parentElement.classList.toggle("open")));
  }
  $("#map-search").oninput = draw;
  $("#map-filter").onchange = draw;
  draw();
}

function auditorBoxHtml(corr) {
  if (!corr) return "";
  const sev = (corr.combined_severity || "").toLowerCase();
  return `
    <div class="auditor-box">
      <div class="auditor-head">
        <span>🔎 Auditor correlation</span>
        <span class="auditor-sev ${sev}">${escapeHtml(corr.combined_severity)}</span>
      </div>
      <div class="auditor-domains">${corr.finding_ids.length} findings across ${corr.control_domains.length} independent control domain(s): ${escapeHtml(corr.control_domains.join(", "))}</div>
      <div class="auditor-narrative">${escapeHtml(corr.narrative || "")}</div>
    </div>`;
}

function caseCardHtml(c) {
  const corr = CORRELATIONS_BY_CASE[c.case_id];
  const legend = `
    <div class="tl-legend">
      <span><i style="background:var(--text-dim)"></i> HR record</span>
      <span><i style="background:var(--medium)"></i> Access/UAR row</span>
      <span><i style="background:var(--accent)"></i> Service desk ticket</span>
      <span><i style="background:var(--low)"></i> Email</span>
    </div>`;
  const events = c.events.map(ev => `
    <div class="tl-event kind-${ev.kind}">
      <div class="tl-date">${ev.date_label}</div>
      <div class="tl-title">${escapeHtml(ev.title)}</div>
      <div class="tl-detail ${ev.detail.includes("⚠") ? "warn" : ""}">${escapeHtml(ev.detail)}</div>
      <div class="tl-citation">${escapeHtml(ev.citation)}</div>
    </div>`).join("");

  return `
  <div class="case-card">
    <div class="case-head">
      <span class="case-name">${escapeHtml(c.subject_label)}</span>
      <span class="case-email">${escapeHtml(c.subject_email || "")}</span>
      ${!c.resolved ? `<span class="case-pill unresolved">UNRESOLVED IDENTITY</span>` : ""}
      ${c.related_finding_ids.length ? `<span class="case-pill findings">${c.related_finding_ids.length} finding(s)</span>` : ""}
      ${c.related_enquiry_ids.length ? `<span class="case-pill enquiries">${c.related_enquiry_ids.length} enquiry(ies)</span>` : ""}
      ${corr ? `<span class="case-pill correlated">🔎 ${corr.control_domains.length} domains agree</span>` : ""}
      <span style="color:var(--text-dim); font-size:12px;">${c.events.length} event(s)</span>
    </div>
    <div class="case-timeline">
      ${legend}
      ${events}
      ${auditorBoxHtml(corr)}
    </div>
  </div>`;
}

// ------------------------------------------------------------------ boot --
refreshState();
loadControls();
loadResults();
loadEvidenceMap();
