// API client for the Atticus backend. Base URL is injected at runtime so the same build works
// for the web app, single-image server, and (later) the desktop sidecar.
const API_BASE = import.meta.env.VITE_API_URL || "";
const PREFIX = `${API_BASE}/api/v1`;

async function req(path, options = {}) {
  const res = await fetch(`${PREFIX}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      message = body.error?.message || body.detail?.error?.message || body.detail || message;
    } catch {
      /* non-JSON error */
    }
    throw new Error(message);
  }
  return res.json();
}

export const api = {
  health: () => req("/health"),
  analyze: (payload) => req("/analyze", { method: "POST", body: JSON.stringify(payload) }),
  listAnalyses: (limit = 20) => req(`/analyses?limit=${limit}`),
  getAnalysis: (id) => req(`/analyses/${id}`),
  deleteAnalysis: (id) => req(`/analyses/${id}`, { method: "DELETE" }),
  createDraft: (id, strategy) =>
    req(`/analyses/${id}/draft`, { method: "POST", body: JSON.stringify({ strategy }) }),
  getDraft: (id) => req(`/analyses/${id}/draft`),
  saveDraft: (id, draft) =>
    req(`/analyses/${id}/draft`, { method: "PUT", body: JSON.stringify(draft) }),
  getSource: (id, ref) => req(`/analyses/${id}/sources/${encodeURIComponent(ref)}`),
  exportAnalysisUrl: (id) => `${PREFIX}/analyses/${id}/export`,
  exportDraftUrl: (id) => `${PREFIX}/analyses/${id}/draft/export`,
};
