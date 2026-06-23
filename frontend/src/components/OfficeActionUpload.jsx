import { useState } from "react";

// Paste office-action text or enter an application number, then analyze.
export default function OfficeActionUpload({ onAnalyze, loading }) {
  const [text, setText] = useState("");
  const [appNo, setAppNo] = useState("");

  function submit(e) {
    e.preventDefault();
    if (text.trim()) onAnalyze({ office_action_text: text });
    else if (appNo.trim()) onAnalyze({ application_number: appNo.trim() });
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">
        Application number
        <input
          value={appNo}
          onChange={(e) => setAppNo(e.target.value)}
          placeholder="16/123,456"
          className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
        />
      </label>
      <div className="text-center text-xs text-gray-400">— or paste the office action —</div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={10}
        placeholder="Paste the full office action text here..."
        className="w-full rounded border border-gray-300 px-3 py-2 font-mono text-sm"
      />
      <button
        type="submit"
        disabled={loading}
        className="rounded bg-gray-900 px-4 py-2 text-white disabled:opacity-50"
      >
        {loading ? "Analyzing…" : "Analyze office action"}
      </button>
    </form>
  );
}
