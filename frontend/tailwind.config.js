/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dce7fd",
          500: "#3b6cf0",
          600: "#2f57d6",
          700: "#2747b4",
          900: "#1c306e",
        },
      },
    },
  },
  plugins: [],
};
