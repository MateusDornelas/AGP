/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        agp: {
          // Accent oficial dos apps AGP
          blue: "#8FC5CF",
          blueDark: "#5EA6B3",
          black: "#111111",
          // Tons do tema escuro
          bg: "#0d0d0f",
          surface: "#17171b",
          card: "#1d1d22",
          border: "#2b2b32",
          muted: "#8b8b94",
        },
      },
    },
  },
  plugins: [],
};
