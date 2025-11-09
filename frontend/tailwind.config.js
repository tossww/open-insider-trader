/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'signal-strong': '#10b981',  // green
        'signal-watch': '#f59e0b',   // yellow
        'signal-weak': '#6b7280',    // gray
      }
    },
  },
  plugins: [],
}
