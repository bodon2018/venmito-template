/* Entry, loading and empty screens. */
import { C, F } from "../tokens.js";
import { esc } from "../format.js";

export function entryScreen() {
  const card = (action, accent, eyebrow, title, blurb, list) => `
    <button data-action="${action}" style="flex:1;text-align:left;background:${C.surface};
        border:1px solid ${C.hair};border-radius:2px;padding:34px 34px 30px;cursor:pointer;
        font:inherit;transition:border-color .15s">
      <div style="font:500 10px/1 ${F.mono};letter-spacing:.2em;text-transform:uppercase;
                  color:${accent}">${eyebrow}</div>
      <h2 style="margin:14px 0 0;font:300 30px/1.15 ${F.serif}">${title}</h2>
      <p style="margin:10px 0 18px;font:400 13.5px/1.6 ${F.sans};color:${C.muted}">${blurb}</p>
      ${list.map((l) => `<div style="display:flex;gap:9px;padding:4px 0;
          font:400 12.5px/1.5 ${F.sans};color:${C.muted}">
          <span style="color:${accent}">—</span><span>${l}</span></div>`).join("")}
      <div style="margin-top:20px;font:400 12px ${F.sans};color:${accent}">Open →</div>
    </button>`;

  return `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:60px 24px">
      <div style="width:100%;max-width:1000px">
        <div style="font:500 12px/1 ${F.mono};letter-spacing:.18em;text-transform:uppercase;
                    margin-bottom:16px">Venmito</div>
        <h1 style="margin:0 0 10px;font:300 44px/1.1 ${F.serif};letter-spacing:-.015em">
          Which view do you need?</h1>
        <p style="margin:0 0 34px;font:400 14px/1.6 ${F.sans};color:${C.muted};max-width:60ch">
          Both views read the same numbers. You can switch at any time.</p>
        <div class="vm-entry" style="display:flex;gap:18px">
          ${card("go-insights", C.business, "Non-technical", "Insights",
            "What the data says about clients, stores, campaigns and transfers — in plain language.",
            ["Findings rewritten after every upload",
             "Who to call back, and why",
             "Upload new files and watch the figures update"])}
          ${card("go-pipeline", C.technical, "Technical", "Pipeline",
            "What the ingestion did: which rows were flagged, why, and direct access to the API.",
            ["Flagged records by category, retained not deleted",
             "Load history and the quarantine queue",
             "Send requests to any endpoint"])}
        </div>
      </div>
    </div>`;
}

export function loadingScreen(accent = C.business) {
  const shimmer = `background:linear-gradient(90deg,${C.hairSoft} 0px,rgba(27,25,23,.05) 300px,${C.hairSoft} 600px);
                   background-size:1200px 100%;animation:shimmer 1.4s linear infinite;border-radius:2px`;
  const bar = (w, h = 13, mt = 10) => `<div style="${shimmer};width:${w};height:${h}px;margin-top:${mt}px"></div>`;
  return `
    <div style="background:${C.surface};min-height:100vh">
      <div class="vm-pad" style="border-bottom:1px solid ${C.hair};display:flex;
                  align-items:center;justify-content:space-between;height:64px">
        <span style="font:500 12px/1 ${F.mono};letter-spacing:.18em;text-transform:uppercase">Venmito</span>
        <span style="display:flex;align-items:center;gap:10px;font:400 11.5px ${F.mono};color:${C.faint}">
          <span style="width:12px;height:12px;border:2px solid ${C.hair};border-top-color:${accent};
                       border-radius:50%;animation:spin .8s linear infinite"></span>
          loading ~29 KB</span>
      </div>
      <div class="vm-section">
        <div style="${shimmer};width:420px;height:34px"></div>
        <div class="vm-cards" style="margin-top:28px">
          ${Array.from({ length: 4 }, () => `
            <div style="padding:20px 22px;background:${C.canvas};border-radius:2px">
              ${bar("120px", 10, 0)}${bar("100%")}${bar("80%")}
            </div>`).join("")}
        </div>
        <div class="vm-stats" style="margin-top:40px;padding:22px 0;
                    border-top:1px solid ${C.hairHard};border-bottom:1px solid ${C.hair}">
          ${Array.from({ length: 4 }, () => `<div style="flex:1">
            ${bar("70px", 9, 0)}<div style="${shimmer};width:110px;height:28px;margin-top:12px"></div>
          </div>`).join("")}
        </div>
        <div style="margin-top:30px">
          ${Array.from({ length: 6 }, (_, i) => `
            <div style="display:flex;align-items:center;gap:14px;padding:7px 0">
              ${bar("120px", 11, 0)}
              <div style="${shimmer};flex:1;height:9px"></div>
            </div>`).join("")}
        </div>
      </div>
    </div>`;
}

export function errorScreen(message, retryAction = "retry") {
  return `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:60px 24px">
      <div style="max-width:60ch">
        <div style="font:500 10px/1 ${F.mono};letter-spacing:.2em;text-transform:uppercase;
                    color:${C.error}">Cannot reach the server</div>
        <h1 style="margin:14px 0 10px;font:300 34px/1.15 ${F.serif}">The API did not respond</h1>
        <p style="margin:0 0 6px;font:400 13.5px/1.6 ${F.sans};color:${C.muted}">
          The page is served separately from the backend, so this usually means the API is
          not running or is on a different address.</p>
        <pre style="margin:14px 0;padding:12px 14px;background:${C.canvas};border-radius:2px;
                    font:400 11.5px/1.5 ${F.mono};white-space:pre-wrap">${esc(message)}</pre>
        <button data-action="${retryAction}" style="margin-top:8px;padding:11px 20px;border:none;
                border-radius:2px;cursor:pointer;background:${C.ink};color:${C.surface};
                font:500 12.5px ${F.sans}">Try again</button>
      </div>
    </div>`;
}

export function emptyScreen() {
  const entity = (name, formats) => `
    <div style="display:flex;gap:12px;padding:10px 0;border-top:1px solid ${C.hairSoft}">
      <span style="width:140px;font:400 12.5px ${F.sans}">${name}</span>
      <span style="font:400 11.5px ${F.mono};color:${C.faint}">${formats}</span></div>`;
  return `
    <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;padding:60px 24px">
      <div style="max-width:64ch">
        <div style="font:500 10px/1 ${F.mono};letter-spacing:.2em;text-transform:uppercase;
                    color:${C.business}">No data yet</div>
        <h1 style="margin:14px 0 10px;font:300 36px/1.15 ${F.serif}">
          Nothing has been uploaded</h1>
        <p style="margin:0 0 24px;font:400 13.5px/1.6 ${F.sans};color:${C.muted}">
          Upload a client file first — purchases, offers and transfers are matched to
          clients, so they need somewhere to attach.</p>
        <button data-action="open-upload" style="padding:11px 20px;border:none;border-radius:2px;
                cursor:pointer;background:${C.ink};color:${C.surface};font:500 12.5px ${F.sans}">
          Upload data</button>
        <div style="margin-top:32px">
          <h3 style="margin:0 0 4px;font:500 11px ${F.mono};letter-spacing:.1em;
                     text-transform:uppercase;color:${C.muted2}">What can be uploaded</h3>
          ${entity("Clients", "JSON · YAML")}
          ${entity("Purchases", "XML")}
          ${entity("Offers", "CSV")}
          ${entity("Transfers", "CSV")}
        </div>
        <p style="margin:26px 0 0;font:400 11.5px/1.6 ${F.sans};color:${C.faint}">
          A section with too little data says so — it does not draw an empty chart.</p>
      </div>
    </div>`;
}
