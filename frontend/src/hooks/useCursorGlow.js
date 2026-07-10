import { useCallback } from "react";

// Shared handler for the cursor-trailing highlight: writes the pointer position
// into --gx/--gy custom properties, which the CSS radial-gradient (and its
// registered-property transition) turns into a soft light that follows the
// cursor. Attach as `onMouseMove` to any element styled with .btn or .glow.
export function useCursorGlow() {
  return useCallback((e) => {
    const el = e.currentTarget;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--gx", `${((e.clientX - r.left) / r.width) * 100}%`);
    el.style.setProperty("--gy", `${((e.clientY - r.top) / r.height) * 100}%`);
  }, []);
}
