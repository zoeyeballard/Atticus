/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Professional, quiet legal-tool palette (Westlaw + Linear).
        bgPrimary: "#FAFAF9", // warm white paper
        bgSecondary: "#F5F5F4", // subtle section backgrounds
        sidebar: "#1C1917", // dark sidebar (stone-900)
        textPrimary: "#1C1917",
        textSecondary: "#57534E", // stone-600
        accent: "#1E40AF", // blue-800
        accentHover: "#1E3A8A", // blue-900
        verified: "#166534", // green-800
        review: "#92400E", // amber-800
        unverified: "#991B1B", // red-800
        borderc: "#D6D3D1", // stone-300
      },
      fontFamily: {
        serif: ["Merriweather", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "'Courier New'", "monospace"],
      },
    },
  },
  plugins: [],
};
