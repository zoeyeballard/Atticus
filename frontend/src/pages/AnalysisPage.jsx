import { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import toast from "react-hot-toast";
import { api } from "../api/client.js";
import Button from "../components/common/Button.jsx";
import RejectionCard from "../components/analysis/RejectionCard.jsx";
import SourceViewer from "../components/verification/SourceViewer.jsx";

export default function AnalysisPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState(null);
  const [sourceRef, setSourceRef] = useState(null);

  useEffect(() => {
    setAnalysis(null);
    setError(null);
    api.getAnalysis(id).then((r) => setAnalysis(r.analysis)).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <Centered><p className="text-unverified">{error}</p></Centered>;
  if (!analysis) return <Centered><p className="text-textSecondary">Loading analysis…</p></Centered>;

  // Group rejections by statutory basis.
  const groups = {};
  for (const r of analysis.rejections) {
    const g = (groups[r.rejection_basis] ||= { claims: new Set(), refs: new Set(), mappings: [] });
    g.claims.add(r.claim_number);
    r.cited_references.forEach((c) => g.refs.add(c.patent_number));
    g.mappings.push(...r.limitation_mappings);
  }

  async function deleteAnalysis() {
    if (!confirm("Permanently delete this analysis and its drafts?")) return;
    try {
      await api.deleteAnalysis(id);
      toast.success("Deleted.");
      navigate("/");
    } catch (e) {
      toast.error(e.message);
    }
  }

  const numerals = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"];

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      {/* Header laid out like a filing: title left, caption block right with dotted
          leaders carrying the eye from label to value. */}
      <header className="mb-10 grid grid-cols-1 md:grid-cols-[1fr_260px] gap-8 items-start">
        <div>
          <p className="text-[10px] uppercase tracking-[0.24em] text-gold mb-3">
            Office Action Analysis
          </p>
          <h1 className="font-serif text-[27px] leading-snug [text-wrap:balance]">
            In re Application No.{" "}
            <span className="nums-tab">{analysis.application_number}</span>
          </h1>
          <div className="flex gap-3 mt-6">
            <Button as={Link} to={`/analysis/${id}/draft`}>Draft Response</Button>
            <Button variant="secondary" as="a" href={api.exportAnalysisUrl(id)}>
              Export Analysis
            </Button>
            <Button
              variant="secondary"
              onClick={deleteAnalysis}
              className="!text-unverified hover:!border-unverified hover:!text-unverified"
            >
              Delete
            </Button>
          </div>
        </div>

        <aside className="border border-borderc bg-bgWhite px-4 py-4 text-[12.5px] nums-tab">
          <CaptionRow label="Action">{analysis.rejection_type}</CaptionRow>
          <CaptionRow label="Art Unit">{analysis.art_unit || "–"}</CaptionRow>
          <CaptionRow label="Examiner">{analysis.examiner_name || "–"}</CaptionRow>
          {analysis.mailing_date && (
            <CaptionRow label="Mailed">{analysis.mailing_date}</CaptionRow>
          )}
        </aside>
      </header>

      <hr className="rule-double mb-8" />

      <h2 className="text-[11px] uppercase tracking-[0.18em] text-textSecondary mb-2">
        Grounds of Rejection
      </h2>
      <div>
        {Object.keys(groups).length === 0 && (
          <p className="text-sm text-textSecondary doc mt-3">
            No rejections were parsed from this office action.
          </p>
        )}
        {Object.entries(groups).map(([basis, g], i) => (
          <RejectionCard
            key={basis}
            numeral={numerals[i] || String(i + 1)}
            basis={basis}
            claims={[...g.claims].sort((a, b) => a - b)}
            references={[...g.refs]}
            mappings={g.mappings}
            onViewSource={setSourceRef}
          />
        ))}
      </div>

      <SourceViewer analysisId={id} reference={sourceRef} onClose={() => setSourceRef(null)} />
    </div>
  );
}

function CaptionRow({ label, children }) {
  return (
    <div className="leader-row py-1">
      <span className="text-[10px] uppercase tracking-[0.14em] text-textSecondary shrink-0">
        {label}
      </span>
      <span className="leader-fill" aria-hidden="true" />
      <span className="text-textPrimary text-right">{children}</span>
    </div>
  );
}

function Centered({ children }) {
  return <div className="flex h-full items-center justify-center">{children}</div>;
}
