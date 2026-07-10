import { useCursorGlow } from "../../hooks/useCursorGlow.js";

// A calm, luxurious button. A faint highlight trails the cursor (via CSS custom props)
// and fades in on hover; the motion is minimal and eased, never a hard swap.
// `as="a"` renders an anchor (for download/nav links) with the same styling.
//
// NOTE: class names must appear as complete literals so Tailwind's content scan keeps
// the styles in the build. Never construct them as `btn-${variant}`.
const VARIANTS = {
  primary: "btn btn-primary",
  secondary: "btn btn-secondary",
};

export default function Button({
  variant = "primary",
  as: Tag = "button",
  className = "",
  children,
  ...props
}) {
  const onMouseMove = useCursorGlow();
  const cls = `${VARIANTS[variant] || VARIANTS.primary} px-4 py-2 text-sm ${className}`;
  return (
    <Tag className={cls} onMouseMove={onMouseMove} {...props}>
      {children}
    </Tag>
  );
}
