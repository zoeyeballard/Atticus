import ConfidenceBadge from "./ConfidenceBadge.jsx";

// Editable AI-generated response draft, one block per argument, with inline sources.
export default function ResponseDraft({ draft }) {
  if (!draft) return null;
  return (
    <section className="space-y-3">
      <h3 className="font-medium">Response draft ({draft.strategy})</h3>
      {draft.arguments.map((arg, i) => (
        <article key={i} className="rounded border border-gray-200 p-4">
          <header className="flex items-center justify-between">
            <span className="text-sm font-medium">
              Claim {arg.claim_number} · §{arg.rejection_basis} · {arg.strategy}
            </span>
            <ConfidenceBadge score={arg.confidence} />
          </header>
          <textarea
            defaultValue={arg.suggested_amendment || arg.argument_text}
            rows={5}
            className="mt-2 w-full rounded border border-gray-200 px-3 py-2 text-sm"
          />
          {arg.supporting_sources.length > 0 && (
            <p className="mt-1 text-xs text-gray-500">
              Sources: {arg.supporting_sources.join("; ")}
            </p>
          )}
        </article>
      ))}
    </section>
  );
}
