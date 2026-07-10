// A placeholder that reads as an intentional part of the instrument, not a stub:
// masthead kicker, serif title, a short serif description of what the page will do,
// and a quiet brass "in preparation" seal.
export default function ComingSoonPage({ kicker, title, description, points = [] }) {
  return (
    <div className="mx-auto max-w-2xl px-8 py-16">
      <p className="text-[10px] uppercase tracking-[0.24em] text-gold mb-3">{kicker}</p>
      <h1 className="font-serif text-2xl mb-2">{title}</h1>
      <p className="text-textSecondary text-sm mb-5 doc">{description}</p>
      <hr className="rule-double mb-10" />

      {points.length > 0 && (
        <ul className="space-y-3 mb-12">
          {points.map((p, i) => (
            <li key={i} className="flex gap-3 text-sm doc text-textSecondary">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-accent/40" />
              {p}
            </li>
          ))}
        </ul>
      )}

      <div className="inline-flex items-center gap-3 rounded-sm border border-borderc bg-bgWhite px-4 py-3">
        <span className="h-1.5 w-1.5 rounded-full bg-gold" />
        <span className="text-[11px] uppercase tracking-[0.18em] text-textSecondary">
          In preparation
        </span>
      </div>
    </div>
  );
}
