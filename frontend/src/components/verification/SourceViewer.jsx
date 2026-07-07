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
      <div className="absolute inset-0 bg-sidebar/25 animate-fade-in" />
      <aside
        className="animate-slide-in absolute right-0 top-0 h-full w-full max-w-xl bg-bgPrimary border-l border-borderc overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between px-7 py-5 border-b border-borderc bg-bgWhite">
          <div>
            <h3 className="font-serif text-lg">Source: <span className="font-mono text-base">{reference}</span></h3>
            <p className="text-[11px] uppercase tracking-wide text-textSecondary mt-1">Cited reference</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-textSecondary hover:text-accent text-2xl leading-none transition-colors duration-200 ease-elegant"
          >
            ×
          </button>
        </header>

        <div className="px-7 py-6 space-y-6">
          {error && <p className="text-unverified text-sm">{error}</p>}
          {!data && !error && <p className="text-textSecondary text-sm">Loading source…</p>}
          {data && (
            <>
              <div>
                <div className="text-[11px] uppercase tracking-[0.14em] text-textSecondary mb-2">
                  Cited passages
                </div>
                {(data.relevant_passages || []).length === 0 && (
                  <p className="text-sm text-textSecondary doc">
                    The examiner did not cite a specific passage for this reference.
                  </p>
                )}
                {(data.relevant_passages || []).map((p, i) => (
                  <blockquote
                    key={i}
                    className="doc whitespace-pre-wrap text-[15px] bg-bgWhite border-l-2 border-accent/40 px-4 py-3 mb-3 rounded-sm"
                  >
                    {p}
                  </blockquote>
                ))}
              </div>
              <div className="border-t border-borderc pt-5">
                <div className="text-[11px] uppercase tracking-[0.14em] text-textSecondary mb-2">
                  Verification
                </div>
                <VerificationBadge status={data.verified ? "verified" : "unsupported"} />
                {data.verification_details && (
                  <p className="text-sm mt-2 text-textSecondary doc">{data.verification_details}</p>
                )}
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
