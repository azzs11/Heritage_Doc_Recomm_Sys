import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        parchment: {
          50:  "#fdf8f0",
          100: "#f5ebe0",
          200: "#ead5c0",
          300: "#d9b896",
        },
        heritage: {
          brown:  "#8b5e3c",
          dark:   "#4a2c17",
          medium: "#6b4226",
          light:  "#c49a6c",
          gold:   "#c8a84b",
          teal:   "#2a7c6f",
          rust:   "#b84c2a",
        },
      },
      fontFamily: {
        serif:   ["var(--font-cormorant)", "Georgia", "Cambria", "Times New Roman", "serif"],
        display: ["var(--font-cormorant)", "Georgia", "serif"],
        sans:    ["Inter", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "parchment-texture": "url('/parchment-bg.jpg')",
      },
      animation: {
        marquee: "marquee 32s linear infinite",
        "fade-up": "fadeUp 0.5s ease both",
        spotlight: "spotlight 2s ease forwards",
        "count-up": "countUp 0.8s ease-out forwards",
      },
      keyframes: {
        marquee: {
          "0%":   { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-50%)" },
        },
        fadeUp: {
          from: { opacity: "0", transform: "translateY(16px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        spotlight: {
          "0%":   { opacity: "0", transform: "scale(0.9)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
