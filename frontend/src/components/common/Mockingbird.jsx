// The Atticus mark: a mockingbird (for Atticus Finch) perched with its tail
// cocked — the species' posture — and its white wing-bar cut out as negative
// space. Drawn in currentColor so it takes whatever text color surrounds it.
//
// `perch` draws the double masthead rule under its feet (same motif as
// .rule-double); pass perch={false} when the bird stands on a rule the layout
// already draws, as in the sidebar masthead.
export default function Mockingbird({ perch = true, className = "", ...props }) {
  return (
    <svg
      viewBox={perch ? "42 40 168 120" : "42 40 168 110"}
      className={className}
      role="img"
      aria-label="Atticus mockingbird mark"
      {...props}
    >
      <path
        fillRule="evenodd"
        fill="currentColor"
        d="M 46 71
           C 56 68, 66 64, 74 60
           C 80 50, 94 50, 100 58
           C 104 63, 105 68, 105 72
           C 119 76, 132 81, 143 88
           C 161 73, 183 58, 198 47
           C 204 43, 208 47, 204 52
           C 190 66, 173 84, 159 97
           C 155 107, 147 116, 137 122
           C 128 128, 116 130.5, 106 129.5
           C 90 127.5, 76 113, 69 97
           C 67 90, 70 82, 72 76
           C 62 74, 54 72.5, 46 71
           Z
           M 88 62 a 2.8 2.8 0 1 0 0.1 0 Z
           M 113 91
           C 123 87.5, 135 90, 142 97
           C 135 102.5, 122 102, 114 97
           C 111 95, 110 92, 113 91
           Z"
      />
      <path
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinecap="round"
        fill="none"
        d="M 100 128 L 97 148 M 111 129 L 111 148"
      />
      {perch && (
        <>
          <path stroke="currentColor" strokeWidth="2.6" d="M 38 151 H 202" />
          <path stroke="currentColor" strokeWidth="1" opacity="0.55" d="M 38 157 H 202" />
        </>
      )}
    </svg>
  );
}
