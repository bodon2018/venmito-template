/* Every call to the backend. Nothing else in the app knows the base URL or
   the endpoint paths. Override with `window.VENMITO_API` before this loads. */
const BASE = window.VENMITO_API ?? "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(BASE + path, options);
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(`${res.status} ${body?.detail ?? res.statusText}`);
  return body;
}

export const api = {
  base: BASE,
  health:     () => request("/health"),
  report:     () => request("/analysis"),
  section:    (name) => request("/analysis/" + encodeURIComponent(name)),
  loads:      (limit = 50) => request(`/loads?limit=${limit}`),
  quarantine: (limit = 200) => request(`/loads/quarantine?limit=${limit}`),
  notes:      () => request("/loads/notes"),

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
    const res = await fetch(BASE + path, { method });
    const text = await res.text();
    let parsed; try { parsed = JSON.parse(text); } catch { parsed = text; }
    return { status: res.status, ok: res.ok, ms: Math.round(performance.now() - started),
             bytes: new Blob([text]).size, body: parsed };
  },
};
