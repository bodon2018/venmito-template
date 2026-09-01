/* Design tokens lifted from the mockup's stylesheet comment.
   The mockup styles every element inline with no class system, so the render
   functions do the same and pull their values from here -- one place to change
   a colour rather than a find-and-replace across the markup. */
export const C = {
  canvas:   "#eeebe4",
  surface:  "#fffdfa",
  ink:      "#1b1917",
  muted:    "#57534c",
  muted2:   "#6b665e",
  faint:    "#8a8479",
  faint2:   "#b3ada1",
  hair:     "rgba(27,25,23,.12)",
  hairSoft: "rgba(27,25,23,.08)",
  hairHard: "rgba(27,25,23,.2)",
  business: "oklch(0.52 0.12 45)",    // insights view
  technical:"oklch(0.52 0.12 215)",   // pipeline view
  ok:       "oklch(0.62 0.14 145)",
  warn:     "oklch(0.62 0.13 75)",
  error:    "oklch(0.55 0.15 25)",
};

export const F = {
  mono:  "'IBM Plex Mono',monospace",
  sans:  "'Public Sans',sans-serif",
  serif: "Newsreader,Georgia,serif",
};

/* Distinct hue per transfer flag, so a row's tag combination is readable
   at a glance (the mockup calls for one chip colour per flag). */
export const FLAG_HUES = {
  self_transfer:   "oklch(0.55 0.11 300)",
  amt_outlier:     "oklch(0.55 0.15 25)",
  round_amount:    "oklch(0.62 0.13 75)",
  reciprocal_pair: "oklch(0.52 0.12 215)",
  fanout:          "oklch(0.52 0.12 45)",
  null_row:        "#8a8479",
  ambiguous_998:   "oklch(0.55 0.08 180)",
};

/* The three channels a client can appear in. The design carries two accents
   only -- rust for business, steel blue for pipeline -- so rather than
   inventing hues these are three steps of the business accent. One hue,
   ordered, each with its own swatch and label. */
export const CHANNEL_HUES = {
  promotions: "oklch(0.42 0.13 45)",
  purchases:  "oklch(0.52 0.12 45)",
  transfers:  "oklch(0.66 0.09 45)",
};

/* Campaigns below this many offers are drawn muted: a 58% on 13 offers must
   not read like a 52% on 31. */
export const SMALL_SAMPLE = 20;
