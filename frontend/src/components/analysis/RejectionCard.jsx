import { useState } from "react";
import VerificationBadge from "../verification/VerificationBadge.jsx";
import ClaimMappingTable from "./ClaimMappingTable.jsx";

const BASIS_LABEL = {
  "101": "Subject Matter Eligibility",
  "102": "Anticipation",
  "103": "Obviousness",
  "112(a)": "Written Description / Enablement",
  "112(b)": "Indefiniteness",
  dp: "Double Patenting",
};

// One rejection group (may be several claims sharing a basis). Collapsed by default.
export default function RejectionCard({ basis, claims, references, mappings, onViewSource }) {
  const [open, setOpen] = useState(false);
  return (
    <article className="rounded border border-borderc bg-white">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start justify-between px-4 py-3 text-left"
      >
        <div>
          <div className="font-medium">
            §{basis} — {BASIS_LABEL[basis] || "Rejection"}
          </div>
          <div className="text-sm text-textSecondary mt-0.5">
            Claims {claims.join(", ")}
            {references.length > 0 && <> · {references.join(", ")}</>}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <VerificationBadge status="verified" />
          <span className="text-textSecondary text-sm">{open ? "▲" : "▾"}</span>
        </div>
      </button>

      {open && (
        <div className="border-t border-borderc px-4 py-3">
          {mappings.length === 0 && (
            <p className="text-sm text-textSecondary">
              Deterministic parse identified this rejection; claim-by-claim mappings appear when
              AI-assisted analysis is enabled.
            </p>
          )}
          {mappings.length > 0 && (
            <ClaimMappingTable mappings={mappings} onViewSource={onViewSource} />
          )}
        </div>
      )}
    </article>
  );
}
