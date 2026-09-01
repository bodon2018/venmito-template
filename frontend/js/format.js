/* The API returns rates as fractions and dates as ISO strings. All
   presentation lives here so no render function invents its own format. */
export const money = (v, dp = 0) =>
  v == null ? "—" : "$" + Number(v).toLocaleString("en-US",
    { minimumFractionDigits: dp, maximumFractionDigits: dp });

export const num = (v, dp = 0) =>
  v == null ? "—" : Number(v).toLocaleString("en-US",
    { minimumFractionDigits: dp, maximumFractionDigits: dp });

export const pct = (v, dp = 0) =>
  v == null ? "—" : (Number(v) * 100).toFixed(dp) + "%";

export const monthLabel = (iso) => {
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
};

export const dateLabel = (iso) => (iso ? iso.slice(0, 10) : "—");

export const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
                       "Jul","Aug","Sep","Oct","Nov","Dec"];

export const bytes = (n) =>
  n > 1024 * 1024 ? (n / 1048576).toFixed(1) + " MB" : Math.round(n / 1024) + " KB";

/** Escape anything that came from the database before it reaches innerHTML. */
export const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
