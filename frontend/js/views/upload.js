/* Upload panel and its result.

   The result is not a toast: rows that could not be matched to a client change
   how the whole page should be read, so they get a figure of their own and a
   sentence spelling out the consequence. */
import { C, F } from "../tokens.js";
import { num, bytes, esc } from "../format.js";

const FORMATS = { json: "JSON", yml: "YAML", yaml: "YAML", csv: "CSV", xml: "XML" };
export const formatOf = (name) =>
  FORMATS[name.split(".").pop().toLowerCase()] ?? "unknown";

export function uploadPanel(staged, mode) {
  const rows = staged.map((f, i) => `
    <div style="display:flex;align-items:center;gap:14px;padding:10px 0;
                border-top:1px solid ${C.hairSoft}">
      <span style="flex:1;font:400 12.5px ${F.sans}">${esc(f.name)}</span>
      <span style="font:500 10px ${F.mono};letter-spacing:.08em;color:${C.faint}">${formatOf(f.name)}</span>
      <span style="width:70px;text-align:right;font:400 11.5px ${F.mono};
                   color:${C.faint}">${bytes(f.size)}</span>
      <button data-remove="${i}" style="border:none;background:none;cursor:pointer;
              font:400 15px ${F.mono};color:${C.faint};padding:0 2px">×</button>
    </div>`).join("");

  const choice = (value, label, note) => `
    <label style="display:flex;gap:10px;align-items:flex-start;cursor:pointer;padding:9px 0">
      <input type="radio" name="mode" value="${value}" ${mode === value ? "checked" : ""}
             style="margin-top:2px;accent-color:${C.business}">
      <span>
        <span style="display:block;font:500 12.5px ${F.sans}">${label}</span>
        <span style="display:block;margin-top:3px;font:400 11.5px/1.45 ${F.sans};
                     color:${C.muted}">${note}</span>
      </span></label>`;

  return `
    <div style="padding:30px 34px 34px">
      <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:20px">
        <h2 style="margin:0;font:300 26px/1.15 ${F.serif}">Upload data</h2>
        <button data-action="close-upload" style="border:none;background:none;cursor:pointer;
                font:400 18px ${F.mono};color:${C.faint}">×</button>
      </div>
      <div id="dropzone" style="border:1px dashed ${C.hairHard};border-radius:2px;
           padding:30px;text-align:center;background:${C.canvas};cursor:pointer">
        <div style="font:400 13.5px ${F.sans}">Drop files here, or click to choose</div>
        <div style="margin-top:7px;font:400 11.5px ${F.mono};color:${C.faint}">
          JSON · YAML · CSV · XML</div>
        <input id="file-input" type="file" multiple accept=".json,.yml,.yaml,.csv,.xml"
               style="display:none">
      </div>
      ${staged.length ? `<div style="margin-top:20px">${rows}</div>` : ""}
      <div style="margin-top:22px;border-top:1px solid ${C.hair};padding-top:14px">
        ${choice("append", "Add to existing data",
          "Keeps everything already stored. Re-uploading an identical file does nothing.")}
        ${choice("replace", "Replace this data",
          "The uploaded file becomes the contents for its type. Earlier loads are superseded — their rows leave the figures, but the audit trail is kept.")}
        ${mode === "replace" ? `
          <p style="margin:6px 0 0;padding:10px 12px;border-radius:2px;
                    background:color-mix(in oklch, ${C.warn} 12%, ${C.surface});
                    font:400 12px/1.5 ${F.sans};color:${C.ink}">
            Replace removes the current rows for every type you upload here.</p>` : ""}
      </div>
      <div style="display:flex;align-items:center;gap:16px;margin-top:22px">
        <button data-action="submit-upload" ${staged.length ? "" : "disabled"}
          style="padding:11px 20px;border:none;border-radius:2px;cursor:${staged.length ? "pointer" : "default"};
                 background:${staged.length ? C.ink : C.faint2};color:${C.surface};
                 font:500 12.5px ${F.sans}">
          ${staged.length ? `Upload ${staged.length} file${staged.length > 1 ? "s" : ""}` : "Upload"}
        </button>
        <span style="font:400 11.5px/1.45 ${F.sans};color:${C.muted};max-width:34ch">
          Every figure on the page is recalculated once the upload finishes.</span>
      </div>
    </div>`;
}

export function uploadInProgress(staged) {
  return `
    <div style="padding:30px 34px 34px">
      <h2 style="margin:0 0 20px;font:300 26px/1.15 ${F.serif}">Uploading…</h2>
      ${staged.map((f) => `
        <div style="display:flex;align-items:center;gap:14px;padding:10px 0;
                    border-top:1px solid ${C.hairSoft}">
          <span style="flex:1;font:400 12.5px ${F.sans}">${esc(f.name)}</span>
          <span style="width:14px;height:14px;border:2px solid ${C.hair};
                       border-top-color:${C.business};border-radius:50%;
                       animation:spin .8s linear infinite"></span>
        </div>`).join("")}
      <p style="margin:20px 0 0;font:400 12px/1.5 ${F.sans};color:${C.muted}">
        The figures behind this panel are still the previous load — they are replaced
        only once this commits.</p>
    </div>`;
}

export function uploadResult(results) {
  const loaded = results.reduce((s, r) => s + r.rows_loaded, 0);
  const unmatched = results.reduce((s, r) => s + r.rows_quarantined, 0);
  const warnings = results.flatMap((r) => r.warnings.map((w) => ({ file: r.filename, w })));
  const skipped = results.filter((r) => r.status === "skipped_duplicate_file");

  const stat = (label, value, colour = C.ink, tint = null) => `
    <div style="flex:1;${tint ? `background:${tint};padding:14px 16px;border-radius:2px` : ""}">
      <div style="font:400 10.5px/1 ${F.mono};letter-spacing:.07em;text-transform:uppercase;
                  color:${C.faint};margin-bottom:9px">${esc(label)}</div>
      <div style="font:300 28px/1 ${F.serif};color:${colour}">${value}</div>
    </div>`;

  const rows = results.map((r) => `
    <tr style="border-top:1px solid ${C.hairSoft}">
      <td style="padding:9px 12px 9px 0;font:400 12.5px ${F.sans}">${esc(r.filename)}</td>
      <td style="padding:9px 12px;font:400 12px ${F.sans};color:${C.muted}">${esc(r.entity)}</td>
      <td style="padding:9px 12px;font:400 11px ${F.mono};color:${C.faint}">${esc(r.mode)}</td>
      <td style="padding:9px 12px;font:500 12px ${F.mono};text-align:right">${num(r.rows_read)}</td>
      <td style="padding:9px 12px;font:500 12px ${F.mono};text-align:right">${num(r.rows_loaded)}</td>
      <td style="padding:9px 0;font:500 12px ${F.mono};text-align:right;
                 color:${r.rows_quarantined ? C.error : C.faint}">${num(r.rows_quarantined)}</td>
    </tr>`).join("");

  return `
    <div style="padding:30px 34px 34px">
      <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:22px">
        <h2 style="margin:0;font:300 26px/1.15 ${F.serif}">Upload complete</h2>
        <button data-action="close-upload" style="border:none;background:none;cursor:pointer;
                font:400 18px ${F.mono};color:${C.faint}">×</button>
      </div>
      <div style="display:flex;gap:20px;align-items:flex-start;padding:0 0 20px;
                  border-bottom:1px solid ${C.hair}">
        ${stat("Rows loaded", num(loaded))}
        ${stat("Could not match to a client", num(unmatched),
               unmatched ? C.error : C.faint,
               unmatched ? `color-mix(in oklch, ${C.error} 9%, ${C.surface})` : null)}
        ${stat("Warnings", num(warnings.length), warnings.length ? C.warn : C.faint)}
      </div>
      ${unmatched ? `
        <p style="margin:16px 0 0;font:400 13px/1.6 ${F.sans};max-width:72ch">
          ${num(unmatched)} row${unmatched === 1 ? "" : "s"} could not be matched to a client
          and ${unmatched === 1 ? "was" : "were"} held back. Totals will look lower than the
          files suggest until those rows are matched — usually because the client is not in
          the system yet. Upload the matching people file and re-upload to resolve them.</p>` : ""}
      ${skipped.length ? `
        <p style="margin:16px 0 0;font:400 12.5px/1.55 ${F.sans};color:${C.muted}">
          ${skipped.length} file${skipped.length === 1 ? " was" : "s were"} identical to data
          already stored, so nothing was changed for
          ${skipped.map((s) => esc(s.filename)).join(", ")}.</p>` : ""}
      <table style="width:100%;border-collapse:collapse;margin-top:22px">
        <tr>${["File","Type","Mode","Read","Loaded","Unmatched"].map((h, i) =>
          `<th style="text-align:${i > 2 ? "right" : "left"};padding:0 12px 8px ${i === 0 ? "0" : ""};
            font:500 10.5px ${F.mono};letter-spacing:.1em;text-transform:uppercase;
            color:${C.faint};font-weight:500">${h}</th>`).join("")}</tr>
        ${rows}</table>
      ${warnings.length ? `
        <div style="margin-top:22px">
          <h3 style="margin:0 0 8px;font:500 11px ${F.mono};letter-spacing:.1em;
                     text-transform:uppercase;color:${C.muted2}">Warnings</h3>
          ${warnings.map((x) => `
            <p style="margin:0 0 7px;padding:9px 12px;border-radius:2px;
                      background:color-mix(in oklch, ${C.warn} 10%, ${C.surface});
                      font:400 12px/1.5 ${F.sans}">
              <span style="font:500 11px ${F.mono}">${esc(x.file)}</span> — ${esc(x.w)}</p>`).join("")}
        </div>` : ""}
      <button data-action="close-upload"
        style="margin-top:24px;padding:11px 20px;border:none;border-radius:2px;cursor:pointer;
               background:${C.ink};color:${C.surface};font:500 12.5px ${F.sans}">
        See the updated figures</button>
    </div>`;
}
