import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        parchment: "#efe7d9",
        ink: "#181715",
        clay: "#c05331",
        clayDark: "#8e341b",
        field: "#173f38",
        brass: "#d49f37",
        panel: "rgba(255,248,239,0.74)",
      },
      boxShadow: {
        haze: "0 28px 90px rgba(51, 36, 21, 0.13)",
      },
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
        mono: ["var(--font-mono)"],
        serif: ["var(--font-serif)"],
      },
      borderRadius: {
        shell: "2rem",
      },
      backgroundImage: {
        "signal-grid":
          "linear-gradient(rgba(24, 23, 21, 0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(24, 23, 21, 0.06) 1px, transparent 1px)",
      },
      animation: {
        rail: "rail 1.8s linear infinite",
        breathe: "breathe 2.2s ease-in-out infinite",
      },
      keyframes: {
        rail: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
        breathe: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: ".52" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
