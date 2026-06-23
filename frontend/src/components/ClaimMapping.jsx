// Table: claim limitation → cited reference → passage.
export default function ClaimMapping({ mappings }) {
  if (!mappings || mappings.length === 0)
    return <p className="mt-2 text-xs text-gray-400">No limitation mappings parsed.</p>;
  return (
    <table className="mt-3 w-full text-left text-sm">
      <thead>
        <tr className="border-b text-xs uppercase text-gray-500">
          <th className="py-1 pr-2">Limitation</th>
          <th className="py-1 pr-2">Reference</th>
          <th className="py-1">Passage</th>
        </tr>
      </thead>
      <tbody>
        {mappings.map((m, i) => (
          <tr key={i} className="border-b align-top">
            <td className="py-2 pr-2">{m.limitation_text}</td>
            <td className="py-2 pr-2 font-mono text-xs">{m.mapped_to_reference || "—"}</td>
            <td className="py-2 text-gray-600">{m.reference_passage || "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
