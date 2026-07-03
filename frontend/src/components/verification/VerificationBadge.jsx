// Trust signal, not tech signal. Maps verification status -> practitioner-friendly label.
const STATES = {
  verified: { label: "Verified", dot: "bg-verified", text: "text-verified",
    tip: "This assertion has been confirmed against the original source document." },
  partial: { label: "Review Suggested", dot: "bg-review", text: "text-review",
    tip: "The source exists but may not fully support this assertion. Manual review recommended." },
  unsupported: { label: "Unverified", dot: "bg-unverified", text: "text-unverified",
    tip: "Could not verify. The source may not exist or may not say what is claimed." },
  fabricated: { label: "Unverified", dot: "bg-unverified", text: "text-unverified",
    tip: "The cited source could not be found. Do not rely on this without checking." },
  unverifiable: { label: "N/A", dot: "bg-stone-400", text: "text-textSecondary",
    tip: "Subjective judgment — no factual check is possible." },
};

// Accepts either a verification status string or a numeric confidence (0-1).
export default function VerificationBadge({ status, confidence }) {
  let key = status;
  if (!key && typeof confidence === "number") {
    key = confidence >= 0.8 ? "verified" : confidence >= 0.5 ? "partial" : "unsupported";
  }
  const s = STATES[key] || STATES.unverifiable;
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${s.text}`} title={s.tip}>
      <span className={`inline-block h-2 w-2 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}
