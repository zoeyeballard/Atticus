import { useState } from "react";
import VerificationBadge from "../verification/VerificationBadge.jsx";
import ClaimMappingTable from "./ClaimMappingTable.jsx";
import { ChevronDown } from "../common/Icons.jsx";

const BASIS_LABEL = {
  "101": "Subject Matter Eligibility",
  "102": "Anticipation",
  "103": "Obviousness",
  "112(a)": "Written Description / Enablement",
  "112(b)": "Indefiniteness",
  dp: "Double Patenting",
};

// One ground of rejection, set like a numbered section of a response brief: a hanging
// roman numeral in the margin, hairline separation instead of a boxed card. The body
// stays mounted while the close transition plays, then unmounts, so both opening and
// closing feel measured rather than abrupt.
export default function RejectionCard({
  numeral,
  basis,
  claims,
  references,
  mappings,
  onViewSource,
}) {
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
    <section className="brief-section border-t border-borderc first:border-t-0">
      <div className="brief-numeral select-none" aria-hidden="true">
        {numeral ? `${numeral}.` : ""}
      </div>
      <div>
        <button
          onClick={toggle}
          aria-expanded={open}
          className="row-hover flex w-full items-start justify-between py-4 pr-2 text-left"
        >
          <div>
            <div className="font-serif text-[15.5px] text-textPrimary">
              §{basis} <span className="text-textSecondary/60 px-0.5">·</span>{" "}
              {BASIS_LABEL[basis] || "Rejection"}
            </div>
            <div className="text-sm text-textSecondary mt-1 doc">
              Claims {claims.join(", ")}
              {references.length > 0 && (
                <>
                  {" "}over{" "}
                  <span className="font-mono text-[12.5px] nums-tab">
                    {references.join(", ")}
                  </span>
                </>
              )}
            </div>
          </div>
          <div className="flex items-center gap-4 pl-4 pt-1 shrink-0">
            <VerificationBadge status="verified" />
            <span
              className="text-textSecondary transition-transform duration-300 ease-elegant"
              style={{ transform: open ? "rotate(180deg)" : "none" }}
            >
              <ChevronDown />
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
              <div className="collapse-inner pb-5 pr-2">
                {mappings.length === 0 && (
                  <p className="text-sm text-textSecondary doc">
                    Deterministic parse identified this ground; the claim chart appears when
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
      </div>
    </section>
  );
}
