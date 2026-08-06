/**
 * ESLint v9 flat config — the file the previous config was missing
 * entirely. Matches the standard Vite + React 19 + TypeScript template
 * shape (typescript-eslint + react-hooks + react-refresh), not a custom
 * invention, so it stays predictable for anyone who's used a Vite React
 * project before.
 */
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "node_modules"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // shadcn/ui-style primitives (components/ui/*.tsx) legitimately
      // export both a component AND its variant/prop types from the
      // same file — react-refresh's rule already allows constant
      // exports via allowConstantExport above; no further override
      // needed here.
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
);
