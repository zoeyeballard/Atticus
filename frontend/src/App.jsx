import { useState } from "react";
import { api } from "./api/client.js";
import OfficeActionUpload from "./components/OfficeActionUpload.jsx";
import RejectionAnalysis from "./components/RejectionAnalysis.jsx";
import VerificationPanel from "./components/VerificationPanel.jsx";
import ResponseDraft from "./components/ResponseDraft.jsx";

export default function App() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [draft, setDraft] = useState(null);

  async function analyze(payload) {
    setLoading(true);
    setError(null);
    setDraft(null);
    try {
      setResult(await api.analyze(payload));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function draftResponse(strategy) {
    if (!result) return;
    setLoading(true);
    try {
      setDraft(await api.draftResponse({ analysis_id: result.analysis_id, strategy }));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <header className="mb-6 border-b pb-4">
        <h1 className="text-2xl font-bold">Atticus</h1>
        <p className="text-sm text-gray-500">
          Verification-first office action assistant — every claim traces to a source.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="space-y-6">
          <OfficeActionUpload onAnalyze={analyze} loading={loading} />
          {error && <p className="text-sm text-flagged">{error}</p>}
          {result && <RejectionAnalysis analysis={result.analysis} />}
          {result && (
            <div className="flex gap-2">
              {["argue", "amend", "both"].map((s) => (
                <button
                  key={s}
                  onClick={() => draftResponse(s)}
                  disabled={loading}
                  className="rounded border border-gray-300 px-3 py-1 text-sm disabled:opacity-50"
                >
                  Draft ({s})
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-6">
          {result && <VerificationPanel report={result.verification} />}
          {draft && <ResponseDraft draft={draft} />}
        </div>
      </div>
    </div>
  );
}
