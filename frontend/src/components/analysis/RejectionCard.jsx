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
// The body stays mounted while the close transition plays, then unmounts —
// so both opening and closing feel measured rather than abrupt.
export default function RejectionCard({ basis, claims, references, mappings, onViewSource }) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  function toggle() {
    if (open) {
      setOpen(false); // collapse-grid eases shut; unmount on transition end
    } else {
      setMounted(true);
      requestAnimationFrame(() => setOpen(true));
    }
  }

  return (
    <article className="rounded-sm border border-borderc bg-bgWhite overflow-hidden">
      <button
        onClick={toggle}
        aria-expanded={open}
        className="row-hover flex w-full items-start justify-between px-5 py-4 text-left"
      >
        <div>
          <div className="font-serif text-[15px] text-textPrimary">
            §{basis} <span className="text-textSecondary/70 px-0.5">·</span>{" "}
            {BASIS_LABEL[basis] || "Rejection"}
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

      {mounted && (
        <div
          className={`collapse-grid ${open ? "is-open" : ""}`}
          onTransitionEnd={(e) => {
            if (e.propertyName === "grid-template-rows" && !open) setMounted(false);
          }}
        >
          <div>
            <div className="collapse-inner border-t border-borderc px-5 py-4">
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
          </div>
        </div>
      )}
    </article>
  );
}
