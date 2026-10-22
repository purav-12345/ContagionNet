/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        panel: "#1f2430",
        panelLight: "#2a3140",
        ink: "#e5e7eb",
      },
    },
  },
  plugins: [],
};
