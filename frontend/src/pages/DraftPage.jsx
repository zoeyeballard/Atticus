import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import toast from "react-hot-toast";
import { api } from "../api/client.js";
import Button from "../components/common/Button.jsx";
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
      toast.error(e.message); // e.g. provider not permitted / quota
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    api.getDraft(id).then(setDraft).catch(() => {});
  }, [id]);

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <header className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="font-serif text-2xl">Response Draft</h1>
          <Link
            to={`/analysis/${id}`}
            className="text-sm text-accent hover:text-accentHover transition-colors duration-200 ease-elegant"
          >
            ← Back to analysis
          </Link>
        </div>
        {draft && (
          <Button as="a" href={api.exportDraftUrl(id)}>Export to Word</Button>
        )}
      </header>
      <hr className="border-0 border-t border-borderc mb-8" />

      <div className="rounded-sm border border-borderc bg-bgWhite p-6 mb-8">
        <div className="text-xs uppercase tracking-wide text-textSecondary mb-3">Strategy</div>
        <div className="space-y-2">
          {STRATEGIES.map(([val, label]) => (
            <label key={val} className="flex items-center gap-2.5 text-sm cursor-pointer doc">
              <input
                type="radio"
                name="strategy"
                checked={strategy === val}
                onChange={() => setStrategy(val)}
                className="accent-accent"
              />
              {label}
            </label>
          ))}
        </div>
        <div className="mt-5">
          <Button onClick={() => generate(strategy)} disabled={busy}>
            {busy ? "Generating…" : "Generate Draft"}
          </Button>
        </div>
        <p className="text-xs text-textSecondary mt-3 doc">
          AI-assisted drafting requires an LLM key on a no-training tier for client data.
        </p>
      </div>

      {draft && (
        <div className="space-y-4">
          {draft.arguments.map((arg, i) => (
            <article key={i} className="rounded-sm border border-borderc bg-bgWhite p-6">
              <header className="flex items-center justify-between mb-3">
                <span className="text-xs uppercase tracking-wide text-textSecondary">
                  Claim {arg.claim_number} · §{arg.rejection_basis} · {arg.strategy}
                </span>
                <VerificationBadge confidence={arg.confidence} />
              </header>
              <textarea
                defaultValue={arg.suggested_amendment || arg.argument_text}
                rows={6}
                className="doc w-full rounded-sm border border-borderc bg-bgPrimary/40 px-4 py-3 text-[15px] leading-relaxed outline-none transition-colors duration-200 ease-elegant focus:border-accent focus:ring-1 focus:ring-accent/30"
              />
              {arg.supporting_sources?.length > 0 && (
                <p className="text-xs text-textSecondary mt-2 font-mono">
                  Sources: {arg.supporting_sources.join("; ")}
                </p>
              )}
            </article>
          ))}
          <Button
            variant="secondary"
            onClick={() =>
              api.saveDraft(id, draft).then(() => toast.success("Draft saved.")).catch((e) => toast.error(e.message))
            }
          >
            Save Draft
          </Button>
        </div>
      )}
    </div>
  );
}
