import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          50:  "#eff6ff",
          100: "#dbeafe",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
        },
      },
      boxShadow: {
        card:  "0 1px 3px 0 rgba(15,23,42,.06), 0 1px 2px -1px rgba(15,23,42,.06)",
        "card-hover": "0 4px 16px 0 rgba(15,23,42,.10), 0 1px 3px 0 rgba(15,23,42,.06)",
        "card-lg": "0 10px 40px 0 rgba(15,23,42,.12)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #1e3a8a 0%, #1d4ed8 60%, #2563eb 100%)",
        "green-gradient": "linear-gradient(135deg, #065f46 0%, #059669 100%)",
      },
    },
  },
  plugins: [],
};

export default config;
