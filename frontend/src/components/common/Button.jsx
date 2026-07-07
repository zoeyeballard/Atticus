import { useCallback } from "react";

// A calm, luxurious button. A faint highlight tracks the cursor (via CSS custom props)
// and fades in on hover — the motion is minimal and eased, never a loud gradient swap.
// `as="a"` renders an anchor (for download/nav links) with the same styling.
export default function Button({
  variant = "primary",
  as: Tag = "button",
  className = "",
  children,
  ...props
}) {
  const onMouseMove = useCallback((e) => {
    const el = e.currentTarget;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--gx", `${((e.clientX - r.left) / r.width) * 100}%`);
    el.style.setProperty("--gy", `${((e.clientY - r.top) / r.height) * 100}%`);
  }, []);

  const cls = `btn btn-${variant} px-4 py-2 text-sm ${className}`;
  return (
    <Tag className={cls} onMouseMove={onMouseMove} {...props}>
      {children}
    </Tag>
  );
}
