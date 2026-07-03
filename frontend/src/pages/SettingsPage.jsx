import { useEffect, useState } from "react";
import { api } from "../api/client.js";

export default function SettingsPage() {
  const [health, setHealth] = useState(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="text-xl font-display mb-6">Settings</h1>

      <Section title="API Configuration">
        <Row label="Anthropic API">
          {health ? (health.anthropic_configured ? "Configured" : "Not configured") : "…"}
        </Row>
        <Row label="USPTO API">
          {health ? (health.uspto_configured ? "Configured" : "Not configured") : "…"}
        </Row>
        <Row label="Generation model">{health?.generation_model || "…"}</Row>
        <Row label="Verification model">{health?.verification_model || "…"}</Row>
        <p className="text-xs text-textSecondary mt-2">
          Keys are configured server-side in <code>.env</code>, never entered or stored in the browser.
        </p>
      </Section>

      <Section title="Data & Privacy">
        <p className="text-sm text-textSecondary">
          Client work product is tenant-isolated and never used to train any model. Analyses can be
          permanently deleted from the analysis view. See the data-handling policy for details.
        </p>
      </Section>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="mb-6 rounded border border-borderc bg-white p-5">
      <h2 className="text-sm uppercase tracking-wide text-textSecondary mb-3">{title}</h2>
      {children}
    </section>
  );
}

function Row({ label, children }) {
  return (
    <div className="flex justify-between py-1 text-sm">
      <span className="text-textSecondary">{label}</span>
      <span className="font-medium">{children}</span>
    </div>
  );
}
