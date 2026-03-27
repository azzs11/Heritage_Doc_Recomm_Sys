import type { Config } from "tailwindcss";

const config: Config = {
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
        },
      },
      fontFamily: {
        serif: ["Georgia", "Cambria", "Times New Roman", "serif"],
        sans:  ["Inter", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "parchment-texture": "url('/parchment-bg.jpg')",
      },
    },
  },
  plugins: [],
};

export default config;
