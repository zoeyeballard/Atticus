import VerificationBadge from "../verification/VerificationBadge.jsx";

// Three columns: limitation | mapped reference + passage | verification (with [View ↗]).
export default function ClaimMappingTable({ mappings, onViewSource }) {
  if (!mappings || mappings.length === 0)
    return <p className="text-xs text-textSecondary mt-2">No limitation mappings parsed.</p>;
  return (
    <table className="mt-3 w-full text-left text-sm border-collapse">
      <thead>
        <tr className="border-b border-borderc text-[11px] uppercase text-textSecondary">
          <th className="py-1 pr-3 font-medium">Limitation</th>
          <th className="py-1 pr-3 font-medium">Mapped to</th>
          <th className="py-1 font-medium">Status</th>
        </tr>
      </thead>
      <tbody>
        {mappings.map((m, i) => (
          <tr key={i} className="border-b border-borderc/60 align-top">
            <td className="py-2 pr-3 font-mono text-[13px]">{m.limitation_text}</td>
            <td className="py-2 pr-3 text-textSecondary">
              {m.mapped_to_reference || "—"}
              {m.reference_passage ? `, ${m.reference_passage}` : ""}
            </td>
            <td className="py-2 whitespace-nowrap">
              <VerificationBadge status={m.mapped_to_reference ? "verified" : "unverifiable"} />
              {m.mapped_to_reference && onViewSource && (
                <button
                  onClick={() => onViewSource(m.mapped_to_reference)}
                  className="ml-2 text-xs text-accent hover:text-accentHover"
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
