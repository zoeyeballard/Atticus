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
    <article className="rounded-sm border border-borderc bg-bgWhite overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="row-hover flex w-full items-start justify-between px-5 py-4 text-left"
      >
        <div>
          <div className="font-serif text-[15px] text-textPrimary">
            §{basis} — {BASIS_LABEL[basis] || "Rejection"}
          </div>
          <div className="text-sm text-textSecondary mt-1 doc">
            Claims {claims.join(", ")}
            {references.length > 0 && (
              <> · <span className="font-mono text-[13px]">{references.join(", ")}</span></>
            )}
          </div>
        </div>
        <div className="flex items-center gap-4 pl-4 shrink-0">
          <VerificationBadge status="verified" />
          <span
            className="text-textSecondary text-xs transition-transform duration-300 ease-elegant"
            style={{ transform: open ? "rotate(180deg)" : "none" }}
          >
            ▾
          </span>
        </div>
      </button>

      {open && (
        <div className="animate-reveal border-t border-borderc px-5 py-4">
          {mappings.length === 0 && (
            <p className="text-sm text-textSecondary doc">
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
