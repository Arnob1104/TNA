import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#12141C",        // base background - near-black navy, not pure black
        panel: "#1A1E2A",      // raised surfaces
        line: "#2B3040",       // hairline borders/dividers
        muted: "#8991A8",      // secondary text
        paper: "#F4F5F7",      // primary text on dark
        signal: "#E8A33D",     // amber - "at risk" / attention
        steady: "#4C9A6A",     // muted green - "on track"
        alert: "#D6544A",      // used sparingly for destructive actions
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
