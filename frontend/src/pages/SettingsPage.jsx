import { useEffect, useState } from "react";
import { api } from "../api/client.js";

export default function SettingsPage() {
  const [health, setHealth] = useState(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  const yn = (v) => (health ? (v ? "Configured" : "Not configured") : "…");

  return (
    <div className="mx-auto max-w-2xl px-8 py-16">
      <p className="text-[10px] uppercase tracking-[0.24em] text-gold mb-3">Chambers</p>
      <h1 className="font-serif text-[27px] mb-2">Settings</h1>
      <p className="text-textSecondary text-sm mb-5 doc">
        How this installation is configured. Keys live server-side and are never entered here.
      </p>
      <hr className="rule-double mb-10" />

      {/* Typographic sections separated by hairlines and whitespace, not boxed cards. */}
      <Section title="Model Provider">
        <Row label="Active provider">{health?.llm_provider || "…"}</Row>
        <Row label="Generation model">{health?.generation_model || "…"}</Row>
        <Row label="Verification model">{health?.verification_model || "…"}</Row>
      </Section>

      <Section title="Connections">
        <Row label="USPTO Open Data Portal">{yn(health?.uspto_configured)}</Row>
        <Row label="Gemini API">{yn(health?.gemini_configured)}</Row>
        <Row label="Anthropic API">{yn(health?.anthropic_configured)}</Row>
      </Section>

      <Section title="Confidentiality">
        <p className="text-sm text-textSecondary doc max-w-[58ch]">
          Client work product is tenant-isolated and never used to train any model. A routing
          guard refuses to send client matter to a provider tier that may train on inputs.
          Analyses can be permanently deleted from the analysis view; deletion also purges the
          drafts and audit records beneath them.
        </p>
      </Section>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="mb-9">
      <h2 className="text-[11px] uppercase tracking-[0.18em] text-textSecondary mb-3">{title}</h2>
      {children}
    </section>
  );
}

function Row({ label, children }) {
  return (
    <div className="leader-row py-1.5 text-sm">
      <span className="text-textSecondary shrink-0">{label}</span>
      <span className="leader-fill" aria-hidden="true" />
      <span className="font-mono text-[12.5px] nums-tab">{children}</span>
    </div>
  );
}
