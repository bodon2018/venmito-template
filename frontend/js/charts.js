/* Chart primitives. No charting library: the design's charts are inline SVG
   polylines and percentage-width spans over datasets of 5-28 points, so the
   whole requirement is a handful of pure functions.

   Every function returns an HTML string and takes already-formatted data. */
import { C, F } from "./tokens.js";
import { esc } from "./format.js";

/** Map values onto pixel coordinates for an SVG of the given box. */
export function scale(values, { width, height, pad = 0, max = null }) {
  const top = max ?? (Math.max(...values, 0) || 1);
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  return values.map((v, i) => [
    +(i * step).toFixed(2),
    +(height - pad - (v / top) * (height - pad * 2)).toFixed(2),
  ]);
}

/** Line with an optional filled area beneath it. */
export function lineChart(values, {
  width = 1000, height = 130, colour = C.business, fill = true, bands = [], max = null,
} = {}) {
  if (!values.length) return "";
  const pts = scale(values, { width, height, pad: 0, max });
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
export function columnChart(values, { height = 90, colour = C.business, gap = 2,
                                      max = null } = {}) {
  const top = max ?? (Math.max(...values, 0) || 1);
  return `<div style="display:flex;align-items:flex-end;gap:${gap}px;height:${height === "100%" ? "100%" : height + "px"}">
    ${values.map((v) => `<span style="flex:1;height:${Math.max((v / top) * 100, v ? 1 : 0)}%;
        background:${colour};opacity:${v ? 0.85 : 0.15};border-radius:1px"></span>`).join("")}
  </div>`;
}

/** A labelled horizontal bar row. `muted` dims rows built on a small sample. */
export function barRow({ label, value, display, max, colour = C.business,
                         note = "", muted = false, wide = false }) {
  const w = max ? Math.max((value / max) * 100, 0.6) : 0;
  // Widths come from CSS so they can shrink with the viewport; only the
  // track flexes, so labels and figures stay aligned across rows.
  return `<div class="vm-bar">
    <span class="vm-bar-label${wide ? " vm-bar-label-wide" : ""}"
          style="font:400 12.5px/1.3 ${F.sans};color:${muted ? C.faint : C.ink}">${esc(label)}</span>
    <span class="vm-bar-track" style="height:9px;background:${C.hairSoft};
                 border-radius:1px;overflow:hidden">
      <span style="display:block;height:100%;width:${w.toFixed(1)}%;
                   background:${colour};opacity:${muted ? 0.3 : 1}"></span>
    </span>
    <span class="vm-bar-value" style="font:500 12px/1 ${F.mono};
                 color:${muted ? C.faint : C.ink}">${esc(display)}</span>
    <span class="vm-bar-note" style="font:400 11px/1 ${F.mono};color:${C.faint}">${note}</span>
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
  // Scrolls inside itself rather than forcing the page wide.
  return `<div class="vm-scroll"><table style="width:100%;border-collapse:collapse">
    ${head}${body}</table></div>`;
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

/* ---------------------------------------------------------------- axes ----
   A chart without a labelled y axis is decoration: the reader can see a shape
   but not read a value off it. `framed` wraps any plot in a value gutter,
   horizontal gridlines and an x-axis row, so every chart states its units.

   The plot itself stretches (`preserveAspectRatio: none`), so tick labels are
   HTML positioned beside the SVG rather than text inside it — that keeps the
   type at its true size and in the design's mono face. */

/** Round a maximum up to a readable tick value: 1, 2, 2.5 or 5 x 10^n. */
export function niceMax(value) {
  if (!(value > 0)) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const scaled = value / magnitude;
  const step = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 2.5 ? 2.5 : scaled <= 5 ? 5 : 10;
  return step * magnitude;
}

/** Pick a top value and tick count that give round steps.
 *  239 -> {max: 250, count: 5} rather than 4 steps of 62.5. */
export function niceScale(rawMax) {
  let best = null;
  for (const count of [4, 5]) {
    const step = niceMax(rawMax / count);
    const max = step * count;
    if (max >= rawMax && (best === null || max < best.max)) best = { max, count };
  }
  return best ?? { max: niceMax(rawMax), count: 4 };
}

export function ticks(max, count = 4) {
  return Array.from({ length: count + 1 }, (_, i) => (max / count) * i).reverse();
}

/**
 * @param plot      HTML for the plot area, sized to 100% x `height`
 * @param max       the value the top gridline represents
 * @param format    turns a tick value into its label
 * @param height    plot height in px
 * @param xLabels   [{label, at}] where `at` is 0..1 across the plot
 * @param axisLabel what the y axis counts, stated in words
 */
export function framed({ plot, max, format, height = 120, xLabels = [],
                         axisLabel = "", gutter = 62, tickCount = 4 }) {
  const rows = ticks(max, tickCount);
  const lines = rows.map((v, i) => {
    const top = (i / (rows.length - 1)) * 100;
    const baseline = i === rows.length - 1;
    return `<div style="position:absolute;left:0;right:0;top:${top}%;height:0;
      border-top:1px solid ${baseline ? C.hairHard : C.hairSoft}"></div>`;
  }).join("");

  const labels = rows.map((v, i) => {
    const top = (i / (rows.length - 1)) * 100;
    return `<div style="position:absolute;right:10px;top:${top}%;transform:translateY(-50%);
      font:400 10.5px/1 ${F.mono};color:${C.faint};white-space:nowrap">${esc(format(v))}</div>`;
  }).join("");

  const xRow = xLabels.length ? `
    <div style="position:relative;height:16px;margin-left:${gutter}px;margin-top:7px">
      ${xLabels.map((x) => `<span style="position:absolute;left:${(x.at * 100).toFixed(2)}%;
        transform:translateX(-50%);font:400 10.5px/1 ${F.mono};color:${C.faint};
        white-space:nowrap">${esc(x.label)}</span>`).join("")}
    </div>` : "";

  return `
    <div>
      ${axisLabel ? `<div style="margin-left:${gutter}px;margin-bottom:6px;
        font:400 10.5px/1 ${F.mono};letter-spacing:.05em;color:${C.faint}">${esc(axisLabel)}</div>` : ""}
      <div style="display:flex;align-items:stretch">
        <div style="position:relative;width:${gutter}px;flex:none;height:${height}px">${labels}</div>
        <div style="position:relative;flex:1;height:${height}px">
          ${lines}
          <div style="position:absolute;inset:0">${plot}</div>
        </div>
      </div>
      ${xRow}
    </div>`;
}

/** Evenly spaced x labels: first, last and a few between. */
export function spacedLabels(items, label, wanted = 5) {
  if (!items.length) return [];
  const step = Math.max(1, Math.round((items.length - 1) / (wanted - 1)));
  const out = [];
  for (let i = 0; i < items.length; i += step) {
    out.push({ label: label(items[i], i), at: i / Math.max(items.length - 1, 1) });
  }
  const lastAt = 1;
  if (out[out.length - 1].at !== lastAt) {
    out.push({ label: label(items[items.length - 1], items.length - 1), at: lastAt });
  }
  return out;
}
