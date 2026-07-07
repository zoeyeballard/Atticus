/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // "Patent Library" palette — institutional, green-forward, warm paper.
        bgPrimary: "#FAF8F4", // warm ivory; aged paper, not screen-white
        bgSecondary: "#F0ECE4", // parchment; subtle section backgrounds
        bgWhite: "#FFFFFF",
        sidebar: "#1C2420", // near-black with a green undertone
        textPrimary: "#1C2420",
        textSecondary: "#5A5F57", // warm gray-green
        accent: "#2B5940", // deep muted forest green (brand)
        accentHover: "#1E3F2D",
        accentSubtle: "#E8F0EB",
        verified: "#2B5940",
        review: "#8C6B2E", // antiqued gold/amber
        unverified: "#7D3040", // muted burgundy (not Harvard crimson)
        borderc: "#D4CFC6", // warm stone hairlines
        gold: "#8B7355", // antique brass, used sparingly
      },
      fontFamily: {
        // Serif display for authority; a serif "document" face for long-form legal text;
        // Inter for functional UI chrome; mono for patent/claim identifiers.
        serif: ['"Libre Baskerville"', "Georgia", '"Times New Roman"', "serif"],
        document: ['"Source Serif 4"', "Georgia", '"Palatino Linotype"', "serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', '"Courier New"', "monospace"],
      },
      borderRadius: {
        // Reads as a typeset document, not a consumer app.
        DEFAULT: "3px",
        sm: "2px",
      },
      transitionTimingFunction: {
        // Slow-in/slow-out; feels considered rather than snappy.
        elegant: "cubic-bezier(0.22, 0.61, 0.36, 1)",
      },
    },
  },
  plugins: [],
};
