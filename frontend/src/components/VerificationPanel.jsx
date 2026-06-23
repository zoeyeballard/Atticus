import ConfidenceBadge from "./ConfidenceBadge.jsx";

const STATUS_STYLES = {
  verified: "text-verified",
  partial: "text-partial",
  unsupported: "text-flagged",
  fabricated: "text-flagged font-semibold",
  unverifiable: "text-gray-400",
};

// Per-claim verification status with overall confidence and review flags.
export default function VerificationPanel({ report }) {
  if (!report) return null;
  return (
    <section className="rounded border border-gray-200 p-4">
      <header className="flex items-center justify-between">
        <h3 className="font-medium">Verification</h3>
        <ConfidenceBadge score={report.overall_confidence} />
      </header>

      {report.needs_human_review && (
        <div className="mt-2 rounded bg-red-50 p-2 text-sm text-flagged">
          ⚠ Needs human review — {report.review_flags.length} item(s) flagged.
        </div>
      )}

      <dl className="mt-3 grid grid-cols-5 gap-2 text-center text-xs">
        <Stat label="Verified" value={report.verified_count} />
        <Stat label="Partial" value={report.partial_count} />
        <Stat label="Unsupported" value={report.unsupported_count} />
        <Stat label="Fabricated" value={report.fabricated_count} />
        <Stat label="N/A" value={report.unverifiable_count} />
      </dl>

      <ul className="mt-3 space-y-1 text-sm">
        {report.claims.map((c, i) => (
          <li key={i} className={STATUS_STYLES[c.status] || ""}>
            [{c.status}] {c.claim_text}
          </li>
        ))}
      </ul>
    </section>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded bg-gray-50 p-2">
      <div className="text-lg font-semibold">{value}</div>
      <div className="text-gray-500">{label}</div>
    </div>
  );
}
