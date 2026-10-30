/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Poppins", "ui-sans-serif", "system-ui", "sans-serif"] },
      colors: {
        brand: { 50: "#eef6ff", 100: "#d9eaff", 500: "#2f80ed", 600: "#1f6fd9", 700: "#1a5bb3" },
        tile: { yellow: "#fbeec1", blue: "#d8f0fb", mint: "#cdeee6", teal: "#c9e7e2", peach: "#fde2d3", lilac: "#e6e1fb" },
      },
      boxShadow: { card: "0 2px 14px rgba(30, 41, 59, 0.06)" },
    },
  },
  plugins: [],
};
