import VerificationBadge from "../verification/VerificationBadge.jsx";
import { ArrowUpRight } from "../common/Icons.jsx";

// Set as a claim chart, the artifact practitioners actually make: claim language on the
// left, the examiner's mapping beside it, verification in the margin.
export default function ClaimMappingTable({ mappings, onViewSource }) {
  if (!mappings || mappings.length === 0)
    return <p className="text-xs text-textSecondary mt-2 doc">No limitation mappings parsed.</p>;
  return (
    <table className="mt-2 w-full text-left text-sm border-collapse">
      <thead>
        <tr className="border-b border-textPrimary/60 text-[10px] uppercase tracking-[0.14em] text-textSecondary">
          <th className="py-2 pr-4 font-medium font-sans w-[42%]">Claim Language</th>
          <th className="py-2 pr-4 font-medium font-sans">Examiner's Mapping</th>
          <th className="py-2 font-medium font-sans w-[130px]">Verification</th>
        </tr>
      </thead>
      <tbody>
        {mappings.map((m, i) => (
          <tr key={i} className="row-hover border-b border-borderc/50 align-top">
            <td className="py-3 pr-4 doc text-[13.5px] leading-relaxed">
              &ldquo;{m.limitation_text}&rdquo;
            </td>
            <td className="py-3 pr-4 text-textSecondary doc text-[13.5px]">
              <span className="font-mono text-[12.5px] nums-tab">
                {m.mapped_to_reference || "–"}
              </span>
              {m.reference_passage ? <> at {m.reference_passage}</> : ""}
            </td>
            <td className="py-3 whitespace-nowrap">
              <VerificationBadge status={m.mapped_to_reference ? "verified" : "unverifiable"} />
              {m.mapped_to_reference && onViewSource && (
                <button
                  onClick={() => onViewSource(m.mapped_to_reference)}
                  className="link-quiet ml-3 inline-flex items-center gap-1 text-xs text-accent hover:text-accentHover"
                >
                  View source <ArrowUpRight />
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
