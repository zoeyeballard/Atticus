/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        verified: "#16a34a",
        partial: "#ca8a04",
        flagged: "#dc2626",
      },
    },
  },
  plugins: [],
};
