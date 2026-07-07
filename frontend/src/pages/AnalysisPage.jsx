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

  return (
    <div className="mx-auto max-w-4xl px-8 py-10">
      <header className="mb-8">
        <h1 className="font-serif text-2xl leading-snug">
          Application {analysis.application_number}
        </h1>
        <p className="text-sm text-textSecondary mt-2 doc">
          {analysis.rejection_type} rejection · Art Unit {analysis.art_unit || "—"} · Examiner{" "}
          {analysis.examiner_name || "—"}
        </p>
        {/* Thin legal-document rule rather than a heavy border. */}
        <hr className="mt-5 border-0 border-t border-borderc" />
        <div className="flex gap-3 mt-5">
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
      </header>

      <h2 className="text-[11px] uppercase tracking-[0.18em] text-textSecondary mb-4">Rejections</h2>
      <div className="space-y-3">
        {Object.keys(groups).length === 0 && (
          <p className="text-sm text-textSecondary">No rejections were parsed from this office action.</p>
        )}
        {Object.entries(groups).map(([basis, g]) => (
          <RejectionCard
            key={basis}
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

function Centered({ children }) {
  return <div className="flex h-full items-center justify-center">{children}</div>;
}
