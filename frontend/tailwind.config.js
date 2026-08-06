/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // Documented in docs/UI-UX/ui_ux_blueprint.md §... "Ranglar":
        // primary blue ~#0C447C, success=green, warning=amber, error=red
        // (Tailwind defaults) — not a placeholder, the real spec.
        primary: {
          DEFAULT: "#0C447C",
          foreground: "#ffffff",
        },
        border: "hsl(214.3 31.8% 91.4%)",
        background: "hsl(0 0% 100%)",
        foreground: "hsl(222.2 84% 4.9%)",
      },
      borderRadius: {
        lg: "0.5rem",
        md: "0.375rem",
        sm: "0.25rem",
      },
    },
  },
  plugins: [],
};
