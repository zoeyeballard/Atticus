import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../../api/client.js";
import { useCursorGlow } from "../../hooks/useCursorGlow.js";
import Mockingbird from "../common/Mockingbird.jsx";

export default function Sidebar() {
  const [recent, setRecent] = useState([]);
  const { pathname } = useLocation();
  const onMouseMove = useCursorGlow();

  useEffect(() => {
    api.listAnalyses(20).then((r) => setRecent(r.analyses || [])).catch(() => {});
  }, [pathname]); // refresh when navigation changes

  const navClass = (to) =>
    `glow nav-item ${pathname === to ? "is-active" : ""} block pl-4 pr-3 py-2 text-sm rounded-sm ` +
    `transition-colors duration-300 ease-elegant ${
      pathname === to
        ? "text-bgPrimary"
        : "text-white/60 hover:text-bgPrimary"
    }`;

  return (
    <aside className="sidebar-surface sidebar-grain flex w-64 flex-col text-white/80 border-r border-black/20">
      <div className="px-6 pt-7 pb-5">
        <span className="font-serif text-bgPrimary text-[15px] tracking-[0.32em] uppercase">
          Atticus
        </span>
        <p className="mt-2 mb-4 pr-12 text-[11px] tracking-wide text-white/40">
          Office Action Assistant
        </p>
        {/* Masthead rule, inverted for the dark surface. The mockingbird mark
            perches on the rule itself — its own perch is the layout's rule. */}
        <div className="border-t-2 border-white/25 relative">
          <Mockingbird
            perch={false}
            aria-hidden="true"
            className="absolute right-0 bottom-full h-7 w-auto text-bgPrimary/90"
          />
          <div className="absolute inset-x-0 top-[3px] border-t border-white/10" />
        </div>
      </div>

      <nav className="px-3 pb-5 space-y-1">
        <Link to="/" className={navClass("/")} onMouseMove={onMouseMove}>
          New Analysis
        </Link>
        <Link to="/search" className={navClass("/search")} onMouseMove={onMouseMove}>
          <span className="flex items-center justify-between">
            Prior Art Search
            <span className="text-[9px] uppercase tracking-[0.14em] text-gold/80">soon</span>
          </span>
        </Link>
        <Link to="/audit" className={navClass("/audit")} onMouseMove={onMouseMove}>
          <span className="flex items-center justify-between">
            Audit Trail
            <span className="text-[9px] uppercase tracking-[0.14em] text-gold/80">soon</span>
          </span>
        </Link>
        <Link to="/settings" className={navClass("/settings")} onMouseMove={onMouseMove}>
          Settings
        </Link>
      </nav>

      <div className="px-3 flex-1 overflow-y-auto">
        <p className="px-4 mb-3 text-[10px] uppercase tracking-[0.18em] text-white/35">
          Docket
        </p>
        {recent.length === 0 && (
          <p className="px-4 text-xs text-white/35">Nothing on the docket yet.</p>
        )}
        {recent.map((a) => (
          <Link
            key={a.analysis_id}
            to={`/analysis/${a.analysis_id}`}
            onMouseMove={onMouseMove}
            className="glow block px-4 py-2.5 rounded-sm transition-colors duration-300 ease-elegant hover:text-white"
          >
            <div className="text-[13px] text-white/85 truncate font-mono">
              {a.application_number}
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {(a.rejection_bases || []).map((b) => (
                <span
                  key={b}
                  className="text-[10px] px-1.5 py-0.5 rounded-sm bg-white/[0.06] text-white/50 font-mono"
                >
                  §{b}
                </span>
              ))}
            </div>
          </Link>
        ))}
      </div>

      <div className="px-6 py-4 border-t border-white/10 text-[10px] tracking-wide text-white/30">
        Verification first · every claim to a source
      </div>
    </aside>
  );
}
