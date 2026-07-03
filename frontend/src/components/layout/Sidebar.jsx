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
    `block px-3 py-2 rounded text-sm ${
      pathname === to ? "bg-white/10 text-white" : "text-stone-300 hover:text-white hover:bg-white/5"
    }`;

  return (
    <aside className="flex w-64 flex-col bg-sidebar text-stone-200">
      <div className="px-5 py-5 border-b border-white/10">
        <span className="font-display tracking-[0.2em] text-white text-lg">ATTICUS</span>
        <p className="text-xs text-stone-400 mt-1">Office Action Assistant</p>
      </div>

      <nav className="px-3 py-4 space-y-1">
        <Link to="/" className={navClass("/")}>＋ New Analysis</Link>
        <Link to="/settings" className={navClass("/settings")}>Settings</Link>
      </nav>

      <div className="px-3 flex-1 overflow-y-auto">
        <p className="px-3 text-xs uppercase tracking-wide text-stone-500 mb-2">Recent Analyses</p>
        {recent.length === 0 && <p className="px-3 text-xs text-stone-500">No analyses yet.</p>}
        {recent.map((a) => (
          <Link
            key={a.analysis_id}
            to={`/analysis/${a.analysis_id}`}
            className="block px-3 py-2 rounded hover:bg-white/5"
          >
            <div className="text-sm text-stone-200 truncate">App {a.application_number}</div>
            <div className="mt-1 flex flex-wrap gap-1">
              {(a.rejection_bases || []).map((b) => (
                <span key={b} className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 text-stone-300">
                  §{b}
                </span>
              ))}
            </div>
          </Link>
        ))}
      </div>
    </aside>
  );
}
