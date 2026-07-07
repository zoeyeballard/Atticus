import VerificationBadge from "../verification/VerificationBadge.jsx";

// Three columns: limitation | mapped reference + passage | verification (with [View ↗]).
export default function ClaimMappingTable({ mappings, onViewSource }) {
  if (!mappings || mappings.length === 0)
    return <p className="text-xs text-textSecondary mt-2 doc">No limitation mappings parsed.</p>;
  return (
    <table className="mt-2 w-full text-left text-sm border-collapse">
      <thead>
        <tr className="border-b border-borderc text-[10px] uppercase tracking-[0.14em] text-textSecondary">
          <th className="py-2 pr-4 font-medium font-sans">Limitation</th>
          <th className="py-2 pr-4 font-medium font-sans">Mapped to</th>
          <th className="py-2 font-medium font-sans">Status</th>
        </tr>
      </thead>
      <tbody>
        {mappings.map((m, i) => (
          <tr key={i} className="row-hover border-b border-borderc/50 align-top">
            <td className="py-2.5 pr-4 font-mono text-[13px] leading-relaxed">{m.limitation_text}</td>
            <td className="py-2.5 pr-4 text-textSecondary">
              <span className="font-mono text-[13px]">{m.mapped_to_reference || "—"}</span>
              {m.reference_passage ? (
                <span className="text-textSecondary">, {m.reference_passage}</span>
              ) : ""}
            </td>
            <td className="py-2.5 whitespace-nowrap">
              <VerificationBadge status={m.mapped_to_reference ? "verified" : "unverifiable"} />
              {m.mapped_to_reference && onViewSource && (
                <button
                  onClick={() => onViewSource(m.mapped_to_reference)}
                  className="ml-3 text-xs text-accent hover:text-accentHover transition-colors duration-200 ease-elegant"
                >
                  View ↗
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
