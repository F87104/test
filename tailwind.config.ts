import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f6f7f9",
          100: "#eceef2",
          200: "#d5dae1",
          300: "#b0b8c4",
          400: "#8590a1",
          500: "#677083",
          600: "#525a6b",
          700: "#434956",
          800: "#3a3f49",
          900: "#33373f",
          950: "#16181d",
        },
        brand: {
          50: "#eef6ff",
          100: "#d9eaff",
          200: "#bcdaff",
          300: "#8dc1ff",
          400: "#579dff",
          500: "#3079ff",
          600: "#1a5af5",
          700: "#1647e1",
          800: "#193cb6",
          900: "#1a388f",
          950: "#152357",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Hiragino Kaku Gothic ProN",
          "Hiragino Sans",
          "Meiryo",
          "sans-serif",
        ],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(16,24,40,0.05), 0 1px 3px rgba(16,24,40,0.06)",
        card: "0 4px 16px rgba(16,24,40,0.06), 0 1px 2px rgba(16,24,40,0.04)",
      },
    },
  },
  plugins: [],
};

export default config;
