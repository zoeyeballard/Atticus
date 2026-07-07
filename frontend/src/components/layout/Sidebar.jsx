import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../../api/client.js";

export default function Sidebar() {
  const [recent, setRecent] = useState([]);
  const { pathname } = useLocation();

  useEffect(() => {
    api.listAnalyses(20).then((r) => setRecent(r.analyses || [])).catch(() => {});
  }, [pathname]); // refresh when navigation changes

  const navClass = (to) =>
    `block px-3 py-2 text-sm rounded-sm transition-colors duration-200 ease-elegant ${
      pathname === to
        ? "bg-white/[0.08] text-bgPrimary"
        : "text-white/60 hover:text-bgPrimary hover:bg-white/[0.04]"
    }`;

  return (
    <aside className="flex w-64 flex-col bg-sidebar text-white/80 border-r border-black/20">
      <div className="px-6 py-6 border-b border-white/10">
        <span className="font-serif text-bgPrimary text-[15px] tracking-[0.32em] uppercase">
          Atticus
        </span>
        <p className="mt-2 text-[11px] tracking-wide text-white/40">
          Office Action Assistant
        </p>
      </div>

      <nav className="px-3 py-5 space-y-1">
        <Link to="/" className={navClass("/")}>New Analysis</Link>
        <Link to="/settings" className={navClass("/settings")}>Settings</Link>
      </nav>

      <div className="px-3 flex-1 overflow-y-auto">
        <p className="px-3 mb-3 text-[10px] uppercase tracking-[0.18em] text-white/35">
          Recent Analyses
        </p>
        {recent.length === 0 && (
          <p className="px-3 text-xs text-white/35">No analyses yet.</p>
        )}
        {recent.map((a) => (
          <Link
            key={a.analysis_id}
            to={`/analysis/${a.analysis_id}`}
            className="block px-3 py-2.5 rounded-sm transition-colors duration-200 ease-elegant hover:bg-white/[0.05]"
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
        Verification-first · every claim to a source
      </div>
    </aside>
  );
}
