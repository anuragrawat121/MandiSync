/** @type {import('tailwindcss').Config} */
const config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "Noto Sans", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Noto Serif", "Georgia", "serif"],
      },
      colors: {
        ink: "#1c1917",
        navy: {
          DEFAULT: "#123a63",
          dark: "#0c2744",
        },
        paper: "#f4efe6",
        panel: "#fffcf7",
        line: "#d7d0c4",
        saffron: "#c45c0a",
        harvest: "#1b6b3a",
      },
    },
  },
  plugins: [],
};

export default config;
