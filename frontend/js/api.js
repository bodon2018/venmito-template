/* Every call to the backend. Nothing else in the app knows the base URL or
   the endpoint paths. Override with `window.VENMITO_API` before this loads. */
const BASE = window.VENMITO_API ?? "http://localhost:8000";
const TOKEN_KEY = "venmito_token";
const HEADER = "x-venmito-token";

/** Thrown when the gate rejects us, so callers can show the code screen
 *  rather than a generic failure. */
export class NeedsCodeError extends Error {}

export const token = {
  get: () => localStorage.getItem(TOKEN_KEY) || "",
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const t = token.get();
  if (t) headers[HEADER] = t;

  const res = await fetch(BASE + path, { ...options, headers });
  const body = await res.json().catch(() => null);

  if (res.status === 401) {
    // The token is missing, expired, or its code was revoked.
    token.clear();
    throw new NeedsCodeError(body?.detail || "An access code is required.");
  }
  if (!res.ok) throw new Error(`${res.status} ${body?.detail ?? res.statusText}`);
  return body;
}

export const api = {
  base: BASE,

  gateRequired: () => request("/auth/required"),

  /** Exchange a code for a token. Stored on success. */
  async authenticate(code) {
    const res = await fetch(BASE + "/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    const body = await res.json().catch(() => null);
    if (!res.ok) throw new Error(body?.detail || "That code is not valid.");
    token.set(body.token);
    return body;
  },

  health:     () => request("/health"),
  report:     () => request("/analysis"),
  section:    (name) => request("/analysis/" + encodeURIComponent(name)),
  loads:      (limit = 50) => request(`/loads?limit=${limit}`),
  quarantine: (limit = 200) => request(`/loads/quarantine?limit=${limit}`),
  notes:      () => request("/loads/notes"),
  exports:    () => request("/export"),

  /** Fetch with the token, then hand the browser a file. A plain <a href>
   *  cannot carry the access-code header, so the download goes through fetch
   *  and an object URL. */
  async downloadCsv(name) {
    const t = token.get();
    const res = await fetch(`${BASE}/export/${encodeURIComponent(name)}.csv`,
                            { headers: t ? { [HEADER]: t } : {} });
    if (res.status === 401) { token.clear(); throw new NeedsCodeError("An access code is required."); }
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = (res.headers.get("content-disposition") || "")
      .match(/filename="?([^"]+)"?/)?.[1] || `venmito_${name}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    return a.download;
  },

  /** files: FileList or array. mode: "append" | "replace". */
  upload(files, mode = "append") {
    const form = new FormData();
    for (const f of files) form.append("files", f, f.name);
    form.append("mode", mode);
    return request("/uploads", { method: "POST", body: form });
  },

  /** Used by the API console, which shows status, timing and the raw body. */
  async raw(method, path) {
    const started = performance.now();
    const t = token.get();
    const res = await fetch(BASE + path, {
      method, headers: t ? { [HEADER]: t } : {},
    });
    const text = await res.text();
    let parsed; try { parsed = JSON.parse(text); } catch { parsed = text; }
    return { status: res.status, ok: res.ok, ms: Math.round(performance.now() - started),
             bytes: new Blob([text]).size, body: parsed };
  },
};
