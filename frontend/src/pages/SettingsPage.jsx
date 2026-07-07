import { useEffect, useState } from "react";
import { api } from "../api/client.js";

export default function SettingsPage() {
  const [health, setHealth] = useState(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  const yn = (v) => (health ? (v ? "Configured" : "Not configured") : "…");

  return (
    <div className="mx-auto max-w-2xl px-8 py-12">
      <h1 className="font-serif text-2xl mb-8">Settings</h1>

      <Section title="Provider">
        <Row label="Active provider">{health?.llm_provider || "…"}</Row>
        <Row label="Generation model">{health?.generation_model || "…"}</Row>
        <Row label="Verification model">{health?.verification_model || "…"}</Row>
      </Section>

      <Section title="API Configuration">
        <Row label="USPTO API">{yn(health?.uspto_configured)}</Row>
        <Row label="Gemini API">{yn(health?.gemini_configured)}</Row>
        <Row label="Anthropic API">{yn(health?.anthropic_configured)}</Row>
        <p className="text-xs text-textSecondary mt-3 doc">
          Keys are configured server-side in <code className="font-mono">.env</code>, never entered
          or stored in the browser.
        </p>
      </Section>

      <Section title="Data &amp; Privacy">
        <p className="text-sm text-textSecondary doc">
          Client work product is tenant-isolated and never used to train any model. A routing guard
          blocks client data from provider tiers that may train on inputs. Analyses can be
          permanently deleted from the analysis view. See the data-handling policy for details.
        </p>
      </Section>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="mb-6 rounded-sm border border-borderc bg-bgWhite p-6">
      <h2 className="text-[11px] uppercase tracking-[0.18em] text-textSecondary mb-4">{title}</h2>
      {children}
    </section>
  );
}

function Row({ label, children }) {
  return (
    <div className="flex justify-between py-1.5 text-sm border-b border-borderc/40 last:border-0">
      <span className="text-textSecondary">{label}</span>
      <span className="font-medium font-mono text-[13px]">{children}</span>
    </div>
  );
}
