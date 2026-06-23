import ClaimMapping from "./ClaimMapping.jsx";
import ConfidenceBadge from "./ConfidenceBadge.jsx";

// Structured display of each rejection: basis, references, claim mappings.
export default function RejectionAnalysis({ analysis }) {
  if (!analysis) return null;
  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">
            Application {analysis.application_number}
          </h2>
          <p className="text-sm text-gray-500">
            {analysis.rejection_type} · Art Unit {analysis.art_unit || "—"} · Examiner{" "}
            {analysis.examiner_name || "—"}
          </p>
        </div>
        <ConfidenceBadge score={analysis.confidence_score} />
      </header>

      {analysis.rejections.length === 0 && (
        <p className="text-sm text-gray-500">
          No structured rejections parsed. Detected flags:{" "}
          {analysis.unverified_claims.join(", ") || "none"}.
        </p>
      )}

      {analysis.rejections.map((rej, i) => (
        <article key={i} className="rounded border border-gray-200 p-4">
          <h3 className="font-medium">
            Claim {rej.claim_number} — §{rej.rejection_basis} rejection
            <a
              className="ml-2 text-xs text-blue-600 underline"
              href={`https://www.uspto.gov/web/offices/pac/mpep/`}
              target="_blank"
              rel="noreferrer"
            >
              MPEP
            </a>
          </h3>
          <p className="mt-1 text-sm text-gray-600">
            Cited:{" "}
            {rej.cited_references.map((r) => r.patent_number).join(", ") || "—"}
          </p>
          <ClaimMapping mappings={rej.limitation_mappings} />
        </article>
      ))}
    </section>
  );
}
