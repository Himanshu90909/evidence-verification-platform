import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        verdict: {
          supported: "#059669",
          refuted: "#dc2626",
          nei: "#d97706",
        },
      },
    },
  },
  plugins: [],
};
export default config;
