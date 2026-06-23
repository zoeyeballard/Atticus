// Thin API client for the Atticus backend.
const BASE = "/api/v1";

async function post(path, body) {
  const resp = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return resp.json();
}

async function get(path) {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) throw new Error(`${resp.status}: ${await resp.text()}`);
  return resp.json();
}

export const api = {
  health: () => get("/health"),
  analyze: (payload) => post("/analyze", payload),
  draftResponse: (payload) => post("/draft-response", payload),
  searchPriorArt: (payload) => post("/search-prior-art", payload),
  verifyClaim: (payload) => post("/verify-claim", payload),
  auditTrail: (analysisId) => get(`/audit-trail/${analysisId}`),
};
