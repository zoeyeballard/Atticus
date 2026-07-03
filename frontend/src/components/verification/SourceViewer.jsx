import { useEffect, useState } from "react";
import { api } from "../../api/client.js";
import VerificationBadge from "./VerificationBadge.jsx";

// Slide-out panel: the trust-building view. One click from an assertion to its source.
export default function SourceViewer({ analysisId, reference, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!reference) return;
    setData(null);
    setError(null);
    api.getSource(analysisId, reference).then((r) => setData(r.reference)).catch((e) => setError(e.message));
  }, [analysisId, reference]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!reference) return null;

  return (
    <div className="fixed inset-0 z-40" onClick={onClose}>
      <div className="absolute inset-0 bg-black/20" />
      <aside
        className="absolute right-0 top-0 h-full w-full max-w-xl bg-white shadow-xl border-l border-borderc overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-5 py-4 border-b border-borderc">
          <div>
            <h3 className="font-display text-lg">Source: {reference}</h3>
            <p className="text-xs text-textSecondary">Cited reference</p>
          </div>
          <button onClick={onClose} className="text-textSecondary hover:text-textPrimary text-xl">×</button>
        </header>

        <div className="px-5 py-4 space-y-4">
          {error && <p className="text-unverified text-sm">{error}</p>}
          {!data && !error && <p className="text-textSecondary text-sm">Loading source…</p>}
          {data && (
            <>
              <div>
                <div className="text-xs uppercase text-textSecondary mb-1">Cited passages</div>
                {(data.relevant_passages || []).length === 0 && (
                  <p className="text-sm text-textSecondary">
                    The examiner did not cite a specific passage for this reference.
                  </p>
                )}
                {(data.relevant_passages || []).map((p, i) => (
                  <pre key={i} className="whitespace-pre-wrap font-mono text-sm bg-bgSecondary p-3 rounded mb-2">
                    {p}
                  </pre>
                ))}
              </div>
              <div>
                <div className="text-xs uppercase text-textSecondary mb-1">Verification</div>
                <VerificationBadge status={data.verified ? "verified" : "unsupported"} />
                {data.verification_details && (
                  <p className="text-sm mt-1 text-textSecondary">{data.verification_details}</p>
                )}
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
