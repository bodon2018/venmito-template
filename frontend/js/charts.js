/* Chart primitives. No charting library: the design's charts are inline SVG
   polylines and percentage-width spans over datasets of 5-28 points, so the
   whole requirement is a handful of pure functions.

   Every function returns an HTML string and takes already-formatted data. */
import { C, F } from "./tokens.js";
import { esc } from "./format.js";

/** Map values onto pixel coordinates for an SVG of the given box. */
export function scale(values, { width, height, pad = 0 }) {
  const max = Math.max(...values, 0) || 1;
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  return values.map((v, i) => [
    +(i * step).toFixed(2),
    +(height - pad - (v / max) * (height - pad * 2)).toFixed(2),
  ]);
}

/** Line with an optional filled area beneath it. */
export function lineChart(values, {
  width = 1000, height = 130, colour = C.business, fill = true, bands = [],
} = {}) {
  if (!values.length) return "";
  const pts = scale(values, { width, height, pad: 8 });
  const line = pts.map((p) => p.join(",")).join(" ");
  const area = `0,${height} ${line} ${width},${height}`;
  const last = pts[pts.length - 1];

  // Bands mark dates the data itself flags -- e.g. the ingestion outage months.
  const bandRects = bands.map((i) => {
    const x = pts[i] ? pts[i][0] : 0;
    const w = Math.max(width / values.length, 3);
    return `<rect x="${(x - w / 2).toFixed(1)}" y="0" width="${w.toFixed(1)}"
            height="${height}" fill="${C.faint}" opacity=".16"></rect>`;
  }).join("");

  return `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none"
               style="width:100%;height:${height}px;display:block">
    ${bandRects}
    ${fill ? `<polygon points="${area}" fill="${colour}" opacity=".08"></polygon>` : ""}
    <polyline points="${line}" fill="none" stroke="${colour}"
              stroke-width="2" vector-effect="non-scaling-stroke"></polyline>
    <circle cx="${last[0]}" cy="${last[1]}" r="3.5" fill="${colour}"
            stroke="${C.surface}" stroke-width="2"></circle>
  </svg>`;
}

/** Vertical bars, used for the age histogram and monthly transaction counts. */
export function columnChart(values, { height = 90, colour = C.business, gap = 2 } = {}) {
  const max = Math.max(...values, 0) || 1;
  return `<div style="display:flex;align-items:flex-end;gap:${gap}px;height:${height}px">
    ${values.map((v) => `<span style="flex:1;height:${Math.max((v / max) * 100, 1)}%;
        background:${colour};opacity:${v ? 0.85 : 0.15};border-radius:1px"></span>`).join("")}
  </div>`;
}

/** A labelled horizontal bar row. `muted` dims rows built on a small sample. */
export function barRow({ label, value, display, max, colour = C.business,
                         note = "", muted = false, labelWidth = 132 }) {
  const w = max ? Math.max((value / max) * 100, 0.6) : 0;
  return `<div style="display:flex;align-items:center;gap:14px;padding:7px 0">
    <span style="width:${labelWidth}px;flex:none;font:400 12.5px/1.3 ${F.sans};
                 color:${muted ? C.faint : C.ink}">${esc(label)}</span>
    <span style="flex:1;height:9px;background:${C.hairSoft};border-radius:1px;overflow:hidden">
      <span style="display:block;height:100%;width:${w.toFixed(1)}%;
                   background:${colour};opacity:${muted ? 0.3 : 1}"></span>
    </span>
    <span style="width:96px;flex:none;text-align:right;font:500 12px/1 ${F.mono};
                 color:${muted ? C.faint : C.ink}">${esc(display)}</span>
    <span style="width:92px;flex:none;font:400 11px/1 ${F.mono};color:${C.faint}">${note}</span>
  </div>`;
}

/** Item x store revenue grid. Opacity carries magnitude; one hue only. */
export function heatGrid({ rows, cols, valueAt, format }) {
  const values = rows.flatMap((r) => cols.map((c) => valueAt(r, c)));
  const max = Math.max(...values, 0) || 1;
  const head = `<tr><th></th>${cols.map((c) =>
    `<th style="padding:0 0 10px;font:400 10.5px/1.3 ${F.mono};color:${C.faint};
                text-align:center;font-weight:400">${esc(c)}</th>`).join("")}</tr>`;
  const body = rows.map((r) => `<tr>
      <td style="padding:3px 12px 3px 0;font:400 12px/1 ${F.sans};white-space:nowrap">${esc(r)}</td>
      ${cols.map((c) => {
        const v = valueAt(r, c);
        const o = v ? 0.1 + (v / max) * 0.9 : 0;
        return `<td style="padding:2px">
          <span style="display:block;height:26px;line-height:26px;text-align:center;
                       background:${v ? C.business : "transparent"};opacity:${v ? 1 : 1};
                       border-radius:1px;font:500 10.5px ${F.mono};
                       color:${o > 0.55 ? C.surface : C.muted};
                       background-color:${v ? `color-mix(in oklch, ${C.business} ${Math.round(o * 100)}%, ${C.surface})` : C.hairSoft}"
          >${v ? esc(format(v)) : ""}</span></td>`;
      }).join("")}
    </tr>`).join("");
  return `<table style="width:100%;border-collapse:collapse">${head}${body}</table>`;
}

/** Proportional rail, used for channel coverage. */
export function stackedRail(segments, { height = 34 } = {}) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  return `<div style="display:flex;height:${height}px;border-radius:2px;overflow:hidden;gap:2px">
    ${segments.map((s) => `<span title="${esc(s.label)}"
        style="width:${((s.value / total) * 100).toFixed(2)}%;background:${s.colour};
               display:flex;align-items:center;justify-content:center;
               font:500 10.5px ${F.mono};color:${C.surface}">
        ${s.value / total > 0.06 ? esc(String(s.value)) : ""}</span>`).join("")}
  </div>`;
}
