import { useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { api } from "../api/client.js";

const STEPS = ["Fetching from USPTO…", "Parsing office action…", "Verifying references…", "Analysis complete"];

export default function NewAnalysisPage() {
  const [appNo, setAppNo] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(0);
  const navigate = useNavigate();

  async function run(payload) {
    setBusy(true);
    setStep(payload.application_number ? 0 : 1);
    try {
      const result = await api.analyze(payload);
      setStep(STEPS.length - 1);
      navigate(`/analysis/${result.analysis_id}`);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  function submitNumber(e) {
    e.preventDefault();
    const n = appNo.replace(/[^0-9]/g, "");
    if (n.length < 7) return toast.error("Please enter a valid application number.");
    run({ application_number: appNo.trim() });
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-xl font-display mb-1">Analyze an Office Action</h1>
      <p className="text-textSecondary text-sm mb-8">
        Enter a published application number, or paste the office action text.
      </p>

      {busy && (
        <div className="mb-6 rounded border border-borderc bg-bgSecondary p-4 text-sm">
          <span className="inline-block h-2 w-2 rounded-full bg-accent animate-pulse mr-2" />
          {STEPS[step]}
        </div>
      )}

      <form onSubmit={submitNumber} className="rounded border border-borderc bg-white p-5 mb-6">
        <label className="block text-sm font-medium mb-2">Application number</label>
        <div className="flex gap-2">
          <input
            value={appNo}
            onChange={(e) => setAppNo(e.target.value)}
            placeholder="19531961"
            className="flex-1 rounded border border-borderc px-3 py-2 font-mono"
          />
          <button disabled={busy} className="rounded bg-accent px-4 py-2 text-white hover:bg-accentHover disabled:opacity-50">
            Analyze
          </button>
        </div>
      </form>

      <div className="text-center text-xs text-textSecondary my-4">— or —</div>

      <form
        onSubmit={(e) => { e.preventDefault(); if (text.trim()) run({ office_action_text: text }); }}
        className="rounded border border-borderc bg-white p-5"
      >
        <label className="block text-sm font-medium mb-2">Paste office action text</label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          placeholder="Paste the full office action text here…"
          className="w-full rounded border border-borderc px-3 py-2 font-mono text-sm"
        />
        <button disabled={busy} className="mt-3 rounded bg-accent px-4 py-2 text-white hover:bg-accentHover disabled:opacity-50">
          Analyze
        </button>
      </form>
    </div>
  );
}
