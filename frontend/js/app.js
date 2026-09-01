/* Application shell: routing between the two views, data fetching, and the
   upload flow. All rendering lives in js/views/. */
import { C, F } from "./tokens.js";
import { api } from "./api.js";
import { esc } from "./format.js";
import { renderInsights } from "./views/insights.js";
import { renderPipeline } from "./views/pipeline.js";
import { uploadPanel, uploadInProgress, uploadResult } from "./views/upload.js";
import { entryScreen, loadingScreen, emptyScreen, errorScreen } from "./views/shell.js";

const root = document.getElementById("app");
const modal = document.getElementById("modal");

const state = {
  view: "entry",            // entry | insights | pipeline
  report: null,
  loads: [],
  quarantine: [],
  staged: [],
  mode: "append",
  upload: "idle",           // idle | busy | done
  results: null,
};

/* ------------------------------------------------------------------ render */
function render() {
  if (state.view === "entry") { root.innerHTML = entryScreen(); return; }
  if (state.view === "loading") { root.innerHTML = loadingScreen(); return; }
  if (state.view === "error") { root.innerHTML = errorScreen(state.error); return; }
  if (state.view === "empty") { root.innerHTML = emptyScreen(); return; }
  if (state.view === "insights") root.innerHTML = renderInsights(state.report);
  if (state.view === "pipeline") {
    root.innerHTML = renderPipeline({
      report: state.report, loads: state.loads, quarantine: state.quarantine });
    refreshHealthPill();
  }
}

function renderModal() {
  if (state.upload === "idle" && !modal.dataset.open) { modal.innerHTML = ""; return; }
  const inner = state.upload === "busy" ? uploadInProgress(state.staged)
    : state.upload === "done" ? uploadResult(state.results)
    : uploadPanel(state.staged, state.mode);
  modal.innerHTML = `
    <div style="position:fixed;inset:0;background:rgba(27,25,23,.34);z-index:60;
                display:flex;align-items:flex-start;justify-content:center;padding:70px 20px;
                overflow:auto" data-overlay="1">
      <div style="width:100%;max-width:${state.upload === "done" ? "760px" : "560px"};
                  background:${C.surface};border-radius:3px" data-panel="1">${inner}</div>
    </div>`;
}

function openUpload() { modal.dataset.open = "1"; state.upload = "idle"; renderModal(); }
function closeUpload() {
  delete modal.dataset.open;
  state.upload = "idle"; state.staged = []; state.results = null;
  modal.innerHTML = "";
}

/* -------------------------------------------------------------------- data */
async function loadAll(view) {
  state.view = "loading"; render();
  try {
    // The pipeline view needs load history too; fetch in parallel.
    const [report, loads, quarantine] = await Promise.all([
      api.report(),
      view === "pipeline" ? api.loads() : Promise.resolve([]),
      view === "pipeline" ? api.quarantine() : Promise.resolve([]),
    ]);
    state.report = report; state.loads = loads; state.quarantine = quarantine;

    // No clients means nothing has been ingested yet -- an empty state, not an
    // error, and not a page of zeroes.
    if (!report.clients.summary.clients) { state.view = "empty"; render(); return; }
    state.view = view; render();
  } catch (err) {
    state.error = err.message; state.view = "error"; render();
  }
}

async function refreshHealthPill() {
  const pill = document.getElementById("health-pill");
  if (!pill) return;
  try {
    const h = await api.health();
    pill.textContent = `${api.base} · ${h.database}`;
    pill.style.color = h.database === "reachable" ? C.ok : C.error;
  } catch {
    pill.textContent = `${api.base} · unreachable`;
    pill.style.color = C.error;
  }
}

/* ------------------------------------------------------------------ upload */
async function submitUpload() {
  if (!state.staged.length) return;
  state.upload = "busy"; renderModal();
  try {
    state.results = await api.upload(state.staged, state.mode);
    state.upload = "done"; renderModal();
    // Re-fetch so every figure reflects the new data. The panel stays open
    // over the refreshed page until the user dismisses it.
    const view = state.view === "pipeline" ? "pipeline" : "insights";
    const [report, loads, quarantine] = await Promise.all([
      api.report(),
      view === "pipeline" ? api.loads() : Promise.resolve([]),
      view === "pipeline" ? api.quarantine() : Promise.resolve([]),
    ]);
    state.report = report; state.loads = loads; state.quarantine = quarantine;
    state.view = report.clients.summary.clients ? view : "empty";
    render(); renderModal();
  } catch (err) {
    state.upload = "idle";
    modal.innerHTML = `
      <div style="position:fixed;inset:0;background:rgba(27,25,23,.34);z-index:60;
                  display:flex;align-items:flex-start;justify-content:center;padding:70px 20px"
           data-overlay="1">
        <div style="max-width:520px;background:${C.surface};border-radius:3px;padding:30px 34px"
             data-panel="1">
          <h2 style="margin:0 0 10px;font:300 24px ${F.serif}">Upload failed</h2>
          <pre style="margin:0 0 18px;padding:12px;background:${C.canvas};border-radius:2px;
                      font:400 11.5px/1.5 ${F.mono};white-space:pre-wrap">${esc(err.message)}</pre>
          <p style="margin:0 0 18px;font:400 12.5px/1.5 ${F.sans};color:${C.muted}">
            Nothing was written — the load runs in a single transaction, so a failure
            leaves the stored data untouched.</p>
          <button data-action="close-upload" style="padding:10px 18px;border:none;border-radius:2px;
                  cursor:pointer;background:${C.ink};color:${C.surface};
                  font:500 12.5px ${F.sans}">Close</button>
        </div></div>`;
  }
}

/* ----------------------------------------------------------- API console */
async function callEndpoint(method, path) {
  const status = document.getElementById("console-status");
  const body = document.getElementById("console-body");
  if (!status || !body) return;
  status.textContent = `${method} ${path} …`;
  body.textContent = "";
  try {
    const r = await api.raw(method, path);
    status.innerHTML = `
      <span style="color:${r.ok ? C.ok : C.error}">${r.status}</span>
      <span>${esc(method)} ${esc(path)}</span>
      <span>${r.ms} ms</span>
      <span>${(r.bytes / 1024).toFixed(1)} KB</span>`;
    body.textContent = typeof r.body === "string"
      ? r.body : JSON.stringify(r.body, null, 2);
  } catch (err) {
    status.innerHTML = `<span style="color:${C.error}">request failed</span>`;
    body.textContent = err.message;
  }
}

/* ------------------------------------------------------------------ events */
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-action],[data-endpoint],[data-remove],[data-quarantine]");

  if (el?.dataset.action) {
    const a = el.dataset.action;
    if (a === "go-insights") return loadAll("insights");
    if (a === "go-pipeline") return loadAll("pipeline");
    if (a === "open-upload") return openUpload();
    if (a === "close-upload") return closeUpload();
    if (a === "submit-upload") return submitUpload();
    if (a === "retry") return loadAll(state.view === "pipeline" ? "pipeline" : "insights");
  }

  if (el?.dataset.endpoint) return callEndpoint(el.dataset.method, el.dataset.endpoint);

  if (el?.dataset.remove !== undefined) {
    state.staged.splice(Number(el.dataset.remove), 1);
    return renderModal();
  }

  if (el?.dataset.quarantine !== undefined) {
    const q = state.quarantine[Number(el.dataset.quarantine)];
    const target = document.getElementById("quarantine-detail");
    if (q && target) {
      target.innerHTML = `
        <div style="font:500 11px ${F.mono};letter-spacing:.08em;text-transform:uppercase;
                    color:${C.faint};margin-bottom:8px">Rejected payload</div>
        <pre style="margin:0;padding:12px;background:${C.canvas};border-radius:2px;
                    font:400 11.5px/1.55 ${F.mono};white-space:pre-wrap;max-height:200px;
                    overflow:auto">${esc(JSON.stringify(q.payload, null, 2))}</pre>
        <p style="margin:10px 0 0;font:400 12px/1.5 ${F.sans};color:${C.muted}">
          ${esc(q.reason)}</p>`;
    }
    return;
  }

  // Clicking the dimmed area closes the panel; clicking the panel does not.
  if (e.target.dataset.overlay) return closeUpload();

  if (e.target.closest("#dropzone")) document.getElementById("file-input")?.click();
});

document.addEventListener("change", (e) => {
  if (e.target.id === "file-input") {
    state.staged = [...state.staged, ...e.target.files];
    renderModal();
  }
  if (e.target.name === "mode") { state.mode = e.target.value; renderModal(); }
});

// Drag and drop onto the panel.
document.addEventListener("dragover", (e) => {
  if (e.target.closest("#dropzone")) { e.preventDefault(); }
});
document.addEventListener("drop", (e) => {
  if (e.target.closest("#dropzone")) {
    e.preventDefault();
    state.staged = [...state.staged, ...e.dataTransfer.files];
    renderModal();
  }
});

render();
