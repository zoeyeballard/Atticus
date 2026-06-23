// Visual confidence indicator: green (verified) / yellow (partial) / red (flagged).
export default function ConfidenceBadge({ score }) {
  const pct = Math.round((score ?? 0) * 100);
  let cls = "bg-flagged";
  let label = "Low";
  if (pct >= 80) {
    cls = "bg-verified";
    label = "High";
  } else if (pct >= 50) {
    cls = "bg-partial";
    label = "Medium";
  }
  return (
    <span className={`${cls} text-white text-xs font-medium px-2 py-0.5 rounded`}>
      {label} · {pct}%
    </span>
  );
}
