/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#02040A",
        surface: "#060D1A",
        glass: "rgba(0,210,255,0.04)",
        primary: "#00D2FF",
        secondary: "#7B2FFF",
        danger: "#FF3366",
        success: "#00FF88",
        warm: "#FF9500",
        "text-primary": "#E8F4FF",
        "text-dim": "#4A7090",
        "border-glow": "rgba(0,210,255,0.15)",
      },
      fontFamily: {
        display: ['"Orbitron"', "sans-serif"],
        body: ['"Inter"', "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      transitionTimingFunction: {
        zero: "cubic-bezier(0.16, 1, 0.32, 1)",
      },
    },
  },
  plugins: [],
};
