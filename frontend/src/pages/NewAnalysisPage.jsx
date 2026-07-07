import { useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { api } from "../api/client.js";
import Button from "../components/common/Button.jsx";

const STEPS = ["Fetching from USPTO…", "Parsing office action…", "Verifying references…", "Analysis complete"];

const inputCls =
  "w-full rounded-sm border border-borderc bg-bgWhite px-3 py-2 font-mono text-[13px] " +
  "outline-none transition-colors duration-200 ease-elegant " +
  "focus:border-accent focus:ring-1 focus:ring-accent/30";

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
    <div className="mx-auto max-w-2xl px-8 py-16">
      <h1 className="font-serif text-2xl mb-2">Analyze an Office Action</h1>
      <p className="text-textSecondary text-sm mb-10 doc">
        Enter a published application number, or paste the office action text.
      </p>

      {busy && (
        <div className="mb-8 rounded-sm border border-borderc bg-accentSubtle/60 px-4 py-3 text-sm flex items-center">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent animate-pulse mr-3" />
          <span className="text-textPrimary">{STEPS[step]}</span>
        </div>
      )}

      <form onSubmit={submitNumber} className="rounded-sm border border-borderc bg-bgWhite p-6 mb-6">
        <label className="block text-xs uppercase tracking-wide text-textSecondary mb-2">
          Application number
        </label>
        <div className="flex gap-3">
          <input
            value={appNo}
            onChange={(e) => setAppNo(e.target.value)}
            placeholder="19531961"
            className={`flex-1 ${inputCls}`}
          />
          <Button disabled={busy} type="submit">Analyze</Button>
        </div>
      </form>

      <div className="text-center text-[11px] uppercase tracking-[0.2em] text-textSecondary my-6">
        — or —
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); if (text.trim()) run({ office_action_text: text }); }}
        className="rounded-sm border border-borderc bg-bgWhite p-6"
      >
        <label className="block text-xs uppercase tracking-wide text-textSecondary mb-2">
          Paste office action text
        </label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          placeholder="Paste the full office action text here…"
          className={inputCls}
        />
        <div className="mt-4">
          <Button disabled={busy} type="submit">Analyze</Button>
        </div>
      </form>
    </div>
  );
}
