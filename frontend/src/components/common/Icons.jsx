// Hand-drawn micro-icons, 1.5px stroke, currentColor. Unicode glyphs (▾ ↗ ×) read as
// unfinished; a consistent drawn set is one of the quiet signals of a designed interface.
const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};

export function ChevronDown({ className = "" }) {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" className={className} {...base}>
      <path d="M3.5 6l4.5 4.5L12.5 6" />
    </svg>
  );
}

export function ArrowUpRight({ className = "" }) {
  return (
    <svg viewBox="0 0 16 16" width="11" height="11" className={className} {...base}>
      <path d="M4.5 11.5l7-7M6 4.5h5.5V10" />
    </svg>
  );
}

export function ArrowLeft({ className = "" }) {
  return (
    <svg viewBox="0 0 16 16" width="12" height="12" className={className} {...base}>
      <path d="M12.5 8h-9M7 3.5L2.5 8 7 12.5" />
    </svg>
  );
}

export function Close({ className = "" }) {
  return (
    <svg viewBox="0 0 16 16" width="14" height="14" className={className} {...base}>
      <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" />
    </svg>
  );
}
