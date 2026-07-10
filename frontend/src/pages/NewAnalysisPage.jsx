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
    <div className="mx-auto max-w-4xl px-8 py-16">
      <p className="text-[10px] uppercase tracking-[0.24em] text-gold mb-3">New Matter</p>
      <h1 className="font-serif text-[30px] leading-snug mb-2 [text-wrap:balance]">
        Analyze an Office Action
      </h1>
      <p className="text-textSecondary text-sm mb-5 doc">
        Enter a published application number, or paste the office action text.
      </p>
      <hr className="rule-double mb-10" />

      {/* Asymmetric working layout: the form carries the weight on the left; a quiet
          reference column on the right, like the margin notes of a working file. */}
      <div className="grid grid-cols-1 md:grid-cols-[1fr_240px] gap-12 items-start">
        <div>
          {busy && (
            <div className="mb-8 rounded-sm border border-borderc bg-accentSubtle/60 px-4 py-3 text-sm flex items-center">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent animate-pulse mr-3" />
              <span className="text-textPrimary">{STEPS[step]}</span>
            </div>
          )}

          <form onSubmit={submitNumber} className="mb-6">
            <label className="block text-xs uppercase tracking-wide text-textSecondary mb-2">
              Application number
            </label>
            <div className="flex gap-3">
              <input
                value={appNo}
                onChange={(e) => setAppNo(e.target.value)}
                placeholder="19531961"
                className={`flex-1 nums-tab ${inputCls}`}
              />
              <Button disabled={busy} type="submit">Analyze</Button>
            </div>
          </form>

          <div className="flex items-center gap-4 my-8" aria-hidden="true">
            <span className="flex-1 border-t border-borderc" />
            <span className="text-[11px] uppercase tracking-[0.2em] text-textSecondary">or</span>
            <span className="flex-1 border-t border-borderc" />
          </div>

          <form
            onSubmit={(e) => { e.preventDefault(); if (text.trim()) run({ office_action_text: text }); }}
          >
            <label className="block text-xs uppercase tracking-wide text-textSecondary mb-2">
              Paste office action text
            </label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={11}
              placeholder="Paste the full office action text here…"
              className={inputCls}
            />
            <div className="mt-4">
              <Button disabled={busy} type="submit">Analyze</Button>
            </div>
          </form>
        </div>

        <aside className="pt-1 text-[13px]">
          <p className="text-[10px] uppercase tracking-[0.18em] text-textSecondary mb-4">
            What happens
          </p>
          <ol className="space-y-4 doc text-textSecondary">
            <li className="flex gap-3">
              <span className="font-serif text-gold shrink-0">1.</span>
              The office action is fetched from the USPTO and parsed into its grounds of
              rejection, claim by claim.
            </li>
            <li className="flex gap-3">
              <span className="font-serif text-gold shrink-0">2.</span>
              Every cited reference is checked against USPTO records; nothing is taken on
              the model&rsquo;s word.
            </li>
            <li className="flex gap-3">
              <span className="font-serif text-gold shrink-0">3.</span>
              You review the claim chart, open any source, and draft a response you can
              edit and export to Word.
            </li>
          </ol>
          <hr className="my-6 border-0 border-t border-borderc" />
          <p className="colophon">
            Analyses are working drafts for attorney review, not legal advice.
          </p>
        </aside>
      </div>
    </div>
  );
}
