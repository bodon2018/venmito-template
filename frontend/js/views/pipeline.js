/* Technical view: what the pipeline did, and direct access to the API.
   Flagged rows are framed as categorised and retained -- they stay in
   Postgres and are excluded by query, not deleted. */
import { C, F, FLAG_HUES } from "../tokens.js";
import { money, num, dateLabel, esc } from "../format.js";
import { barRow } from "../charts.js";
import { api } from "../api.js";

const A = C.technical;

const panel = (id, eyebrow, title, sub, body) => `
  <section id="${id}" class="vm-section-tight" style="border-bottom:1px solid ${C.hair}">
    <div style="margin-bottom:22px">
      <div style="font:500 10px/1 ${F.mono};letter-spacing:.2em;text-transform:uppercase;
                  color:${A}">${esc(eyebrow)}</div>
      <h2 style="margin:12px 0 0;font:300 30px/1.15 ${F.serif}">${esc(title)}</h2>
      ${sub ? `<p style="margin:8px 0 0;font:400 13px/1.55 ${F.sans};color:${C.muted};
                          max-width:76ch">${sub}</p>` : ""}
    </div>${body}</section>`;

const tag = (text, colour) => `
  <span style="display:inline-block;padding:2px 7px;border-radius:2px;
               background:color-mix(in oklch, ${colour} 14%, ${C.surface});
               color:${colour};font:500 9.5px/1.5 ${F.mono};letter-spacing:.08em;
               text-transform:uppercase">${esc(text)}</span>`;

const flagChips = (flags) => (flags || "").split("|").filter(Boolean)
  .map((f) => tag(f.replace(/_/g, " "), FLAG_HUES[f] ?? C.faint)).join(" ");

/* --------------------------------------------------------- flagged records */
function flagged(dq, risk) {
  const c = dq.counts;
  const cards = [
    ["Orphan transactions", c.orphan_transactions, "RETAINED", C.ok,
     "Purchase matched no client by phone."],
    ["Duplicate transactions", c.duplicate_transactions, "RETAINED", C.ok,
     "Identical basket, store and date as an earlier row."],
    ["Line items needing review", c.items_needing_review, "RETAINED", C.ok,
     "Reported price disagreed with quantity × unit price."],
    ["Empty transfer rows", c.null_transfers, "RETAINED", C.ok,
     "No sender, recipient or amount — an ingestion outage."],
    ["Transfers with risk tags", c.behavioural_flagged, "RETAINED", C.ok,
     "Behavioural patterns worth review, kept as signal."],
    ["Merged duplicate identities", c.synthetic_people, "RETAINED", C.ok,
     "One person holding two ids, collapsed to one."],
    ["Quarantined rows", c.quarantined_rows, "NOT LOADED", C.error,
     "Could not be resolved to a client; held for review."],
  ].map(([label, value, state, colour, note]) => `
    <div style="padding:18px 20px;background:${C.canvas};border-radius:2px">
      <div style="display:flex;align-items:baseline;justify-content:space-between;gap:10px">
        <span style="font:400 11px/1.3 ${F.mono};letter-spacing:.05em;text-transform:uppercase;
                     color:${C.faint}">${esc(label)}</span>
        ${tag(state, colour)}
      </div>
      <div style="margin-top:12px;font:300 30px/1 ${F.serif}">${num(value)}</div>
      <p style="margin:8px 0 0;font:400 11.5px/1.45 ${F.sans};color:${C.muted}">${esc(note)}</p>
    </div>`).join("");

  const maxTag = Math.max(...risk.tags.map((t) => t.transfers), 0);
  const bars = risk.tags.map((t) => barRow({
    label: t.tag.replace(/_/g, " "), value: t.transfers, display: num(t.transfers),
    max: maxTag, colour: FLAG_HUES[t.tag] ?? A, wide: true,
  })).join("");

  const rows = risk.flagged.map((r) => `
    <tr style="border-top:1px solid ${C.hairSoft}">
      <td style="padding:8px 12px 8px 0;font:400 11.5px ${F.mono};color:${C.faint}">${r.transfer_key}</td>
      <td style="padding:8px 12px;font:400 12px ${F.mono}">${r.sender_id ?? "—"}</td>
      <td style="padding:8px 12px;font:400 12px ${F.mono}">${r.recipient_id ?? "—"}</td>
      <td style="padding:8px 12px;font:500 12px ${F.mono};text-align:right">${money(r.amount, 2)}</td>
      <td style="padding:8px 12px;font:400 11.5px ${F.mono};color:${C.muted}">${dateLabel(r.transfer_date)}</td>
      <td style="padding:8px 0">${flagChips(r.flags)}</td>
    </tr>`).join("");

  return panel("flagged", "Flagged records", "Categorised and retained",
    `Nothing here was deleted. Flagged rows stay in Postgres and are excluded from
     business figures by query, not by removal — the transfer patterns in particular are
     kept because they are a fraud signal. One transfer can carry several tags, so the
     bars below sum to more than ${num(dq.counts.behavioural_flagged)}.`, `
    <div class="vm-quad" style="margin-bottom:32px">${cards}</div>
    <h3 style="margin:0 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
               text-transform:uppercase;color:${C.muted2}">Transfer risk tags</h3>
    ${bars}
    <h3 style="margin:30px 0 4px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
               text-transform:uppercase;color:${C.muted2}">Flagged transfers</h3>
    <p style="margin:0 0 10px;font:400 11.5px ${F.sans};color:${C.faint}">
      Showing ${risk.flagged.length} rows, largest amount first.</p>
    <div class="vm-scroll"><table style="width:100%;border-collapse:collapse">
      <tr>${["Key","Sender","Recipient","Amount","Date","Tags"].map((h, i) =>
        `<th style="text-align:${i === 3 ? "right" : "left"};padding:0 12px 8px ${i === 0 ? "0" : ""};
          font:500 10.5px ${F.mono};letter-spacing:.1em;text-transform:uppercase;
          color:${C.faint};font-weight:500">${h}</th>`).join("")}</tr>
      ${rows}</table></div>
    ${dq.outages.length ? `
      <h3 style="margin:30px 0 8px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
                 text-transform:uppercase;color:${C.muted2}">Ingestion notes</h3>
      ${dq.outages.map((o) => `
        <div style="display:flex;gap:16px;padding:8px 0;border-top:1px solid ${C.hairSoft}">
          <span style="font:500 12px ${F.mono};width:110px">${dateLabel(o.note_date)}</span>
          <span style="font:400 12.5px ${F.sans};color:${C.muted}">${esc(o.detail)}</span>
        </div>`).join("")}` : ""}`);
}

/* ------------------------------------------------------------ load history */
function loadHistory(loads, quarantine) {
  const rows = loads.map((l) => {
    const colour = l.status === "succeeded" ? C.ok
      : l.status === "failed" ? C.error : C.warn;
    return `<tr style="border-top:1px solid ${C.hairSoft}">
      <td style="padding:9px 12px 9px 0;font:400 12px ${F.mono}">${esc(l.filename)}</td>
      <td style="padding:9px 12px;font:400 11.5px ${F.mono};color:${C.muted}">${esc(l.file_format)}</td>
      <td style="padding:9px 12px;font:400 12px ${F.sans}">${esc(l.entity)}</td>
      <td style="padding:9px 12px">${tag(l.status, colour)}</td>
      <td style="padding:9px 12px;font:500 12px ${F.mono};text-align:right">${num(l.rows_loaded)}</td>
      <td style="padding:9px 12px;font:500 12px ${F.mono};text-align:right;
                 color:${l.rows_quarantined ? C.error : C.faint}">${num(l.rows_quarantined)}</td>
      <td style="padding:9px 0;font:400 11px ${F.mono};color:${C.faint}">
        ${l.started_at ? String(l.started_at).slice(0, 19).replace("T", " ") : "—"}</td>
    </tr>`;
  }).join("");

  const qRows = quarantine.map((q, i) => `
    <div data-quarantine="${i}" style="padding:12px 14px;border-top:1px solid ${C.hairSoft};cursor:pointer">
      <div style="display:flex;justify-content:space-between;gap:12px">
        <span style="font:400 12px ${F.sans}">${esc(q.reason)}</span>
        <span style="font:400 11px ${F.mono};color:${C.faint}">row ${q.source_row ?? "—"}</span>
      </div>
      <div style="margin-top:5px;font:400 11px ${F.mono};color:${C.faint}">
        ${esc(q.filename)} · ${esc(q.entity)}</div>
    </div>`).join("");

  return panel("loads", "Load history", "Every upload, and what it rejected",
    "Superseded loads keep their audit row and raw records; they are excluded from current counts, not erased.", `
    <div class="vm-scroll" style="margin-bottom:34px"><table style="width:100%;border-collapse:collapse">
      <tr>${["File","Format","Entity","Status","Loaded","Quarantined","Started"].map((h, i) =>
        `<th style="text-align:${i === 4 || i === 5 ? "right" : "left"};
          padding:0 12px 8px ${i === 0 ? "0" : ""};font:500 10.5px ${F.mono};letter-spacing:.1em;
          text-transform:uppercase;color:${C.faint};font-weight:500">${h}</th>`).join("")}</tr>
      ${rows}</table></div>
    <h3 style="margin:0 0 10px;font:500 12px/1 ${F.mono};letter-spacing:.1em;
               text-transform:uppercase;color:${C.muted2}">Quarantine — ${quarantine.length} rows</h3>
    <div class="vm-split-narrow" style="border:1px solid ${C.hair};border-radius:2px;overflow:hidden">
      <div style="max-height:330px;overflow:auto;border-right:1px solid ${C.hair}">
        ${qRows || `<p style="padding:16px;margin:0;font:400 12.5px ${F.sans};color:${C.muted}">
          Nothing quarantined.</p>`}</div>
      <div id="quarantine-detail" style="padding:16px 18px 18px 0;min-height:120px">
        <p style="margin:0;font:400 12.5px ${F.sans};color:${C.faint}">
          Select a row to see the payload the parser rejected.</p></div>
    </div>
    <p style="margin:12px 0 0;font:400 11.5px/1.5 ${F.sans};color:${C.faint}">
      Nothing retries automatically. Re-upload a corrected file to resolve these rows.</p>`);
}

/* ------------------------------------------------------------- API console */
const ENDPOINTS = [
  ["GET", "/health", "Liveness and database connectivity"],
  ["GET", "/analysis", "Full report — every section plus headlines"],
  ["GET", "/analysis/headlines", "Headline sentences only"],
  ["GET", "/analysis/sections", "Section names"],
  ["GET", "/analysis/clients", "One section"],
  ["GET", "/analysis/stores", "One section"],
  ["GET", "/analysis/promotions", "One section"],
  ["GET", "/analysis/turn_no_into_yes", "One section"],
  ["GET", "/analysis/transfers", "One section"],
  ["GET", "/analysis/transfer_risk", "One section"],
  ["GET", "/analysis/channel_coverage", "One section"],
  ["GET", "/analysis/data_quality", "One section"],
  ["GET", "/loads", "Upload history"],
  ["GET", "/loads/quarantine", "Rejected rows with reasons"],
  ["GET", "/loads/notes", "Data-quality notes"],
];

function console_() {
  return panel("console", "API console", "Work against the server directly",
    `Requests go to <code style="font:500 12px ${F.mono}">${esc(api.base)}</code>.
     Uploads are not listed here — use the upload panel, which posts multipart form data.`, `
    <div class="vm-split">
      <div style="border:1px solid ${C.hair};border-radius:2px;max-height:430px;overflow:auto">
        ${ENDPOINTS.map(([m, p, d]) => `
          <button data-endpoint="${esc(p)}" data-method="${m}"
            style="width:100%;text-align:left;display:block;padding:11px 14px;background:none;
                   border:none;border-top:1px solid ${C.hairSoft};cursor:pointer;font:inherit">
            <span style="display:flex;align-items:center;gap:9px">
              <span style="font:500 10px ${F.mono};color:${A};letter-spacing:.08em">${m}</span>
              <span style="font:500 12px ${F.mono}">${esc(p)}</span></span>
            <span style="display:block;margin-top:4px;font:400 11px ${F.sans};
                         color:${C.faint}">${esc(d)}</span>
          </button>`).join("")}
      </div>
      <div>
        <div id="console-status" style="display:flex;gap:18px;padding:0 0 12px;
             font:400 11.5px ${F.mono};color:${C.faint}">Pick an endpoint to send a request.</div>
        <pre id="console-body" style="margin:0;padding:16px;background:${C.canvas};
             border-radius:2px;max-height:390px;overflow:auto;font:400 11.5px/1.6 ${F.mono};
             white-space:pre-wrap;word-break:break-word;color:${C.ink}"></pre>
      </div>
    </div>`);
}

/* ------------------------------------------------------------------ shell */
export function renderPipeline({ report, loads, quarantine }) {
  return `
    <div class="vm-page" style="background:${C.surface};min-height:100vh">
      <div class="vm-pad" style="position:sticky;top:0;z-index:20;background:${C.surface};
                  border-bottom:1px solid ${C.hair};display:flex;
                  align-items:center;justify-content:space-between;height:64px">
        <div style="display:flex;align-items:baseline;gap:26px">
          <span style="font:500 12px/1 ${F.mono};letter-spacing:.18em;text-transform:uppercase">Venmito</span>
          <span style="font:400 12.5px/1 ${F.sans};color:${C.faint}">Pipeline</span>
        </div>
        <div style="display:flex;align-items:center;gap:20px">
          <span id="health-pill" style="font:400 11.5px/1 ${F.mono};color:${C.faint}">checking…</span>
          <button data-action="open-upload"
            style="padding:9px 15px;border:1px solid ${C.hairHard};border-radius:2px;
                   background:none;font:500 12px ${F.sans};cursor:pointer">Upload data</button>
          <button data-action="go-insights"
            style="padding:9px 15px;border:1px solid transparent;background:none;
                   font:400 12px ${F.sans};color:${C.business};cursor:pointer">
            ← Switch to insights view</button>
        </div>
      </div>
      <nav class="vm-pad" style="position:sticky;top:64px;z-index:19;border-bottom:1px solid ${C.hair};
                  background:${C.surface};display:flex;gap:26px;height:44px;
                  align-items:center;font:400 12px ${F.sans};color:${C.faint}">
        <a href="#flagged" style="color:inherit;text-decoration:none">Flagged records</a>
        <a href="#loads" style="color:inherit;text-decoration:none">Load history</a>
        <a href="#console" style="color:inherit;text-decoration:none">API console</a>
      </nav>
      ${flagged(report.data_quality, report.transfer_risk)}
      ${loadHistory(loads, quarantine)}
      ${console_()}
    </div>`;
}
