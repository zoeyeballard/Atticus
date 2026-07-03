import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import toast from "react-hot-toast";
import { api } from "../api/client.js";
import VerificationBadge from "../components/verification/VerificationBadge.jsx";

const STRATEGIES = [
  ["argue", "Argue (distinguish over prior art)"],
  ["amend", "Amend (narrow claims)"],
  ["both", "Both (argue + propose amendments)"],
];

export default function DraftPage() {
  const { id } = useParams();
  const [strategy, setStrategy] = useState("argue");
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);

  async function generate(strat) {
    setBusy(true);
    try {
      setDraft(await api.createDraft(id, strat));
    } catch (e) {
      toast.error(e.message); // e.g. LLM credits required
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    api.getDraft(id).then(setDraft).catch(() => {});
  }, [id]);

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <header className="border-b border-borderc pb-4 mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-display">Response Draft</h1>
          <Link to={`/analysis/${id}`} className="text-sm text-accent hover:text-accentHover">← Back to analysis</Link>
        </div>
        {draft && (
          <a href={api.exportDraftUrl(id)} className="rounded bg-accent px-4 py-2 text-sm text-white hover:bg-accentHover">
            Export to Word
          </a>
        )}
      </header>

      <div className="rounded border border-borderc bg-white p-4 mb-6">
        <div className="text-sm font-medium mb-2">Strategy</div>
        <div className="space-y-1">
          {STRATEGIES.map(([val, label]) => (
            <label key={val} className="flex items-center gap-2 text-sm">
              <input type="radio" name="strategy" checked={strategy === val} onChange={() => setStrategy(val)} />
              {label}
            </label>
          ))}
        </div>
        <button
          onClick={() => generate(strategy)}
          disabled={busy}
          className="mt-3 rounded bg-accent px-4 py-2 text-sm text-white hover:bg-accentHover disabled:opacity-50"
        >
          {busy ? "Generating…" : "Generate Draft"}
        </button>
        <p className="text-xs text-textSecondary mt-2">
          AI-assisted drafting requires an Anthropic API key with available credits.
        </p>
      </div>

      {draft && (
        <div className="space-y-3">
          {draft.arguments.map((arg, i) => (
            <article key={i} className="rounded border border-borderc bg-white p-4">
              <header className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">Claim {arg.claim_number} · §{arg.rejection_basis} · {arg.strategy}</span>
                <VerificationBadge confidence={arg.confidence} />
              </header>
              <textarea
                defaultValue={arg.suggested_amendment || arg.argument_text}
                rows={5}
                className="w-full rounded border border-borderc px-3 py-2 text-sm"
              />
              {arg.supporting_sources?.length > 0 && (
                <p className="text-xs text-textSecondary mt-1">Sources: {arg.supporting_sources.join("; ")}</p>
              )}
            </article>
          ))}
          <button
            onClick={() => api.saveDraft(id, draft).then(() => toast.success("Draft saved.")).catch((e) => toast.error(e.message))}
            className="rounded border border-borderc px-4 py-2 text-sm hover:bg-bgSecondary"
          >
            Save Draft
          </button>
        </div>
      )}
    </div>
  );
}
