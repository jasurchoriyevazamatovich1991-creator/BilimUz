import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // The backend is CORS-configured (app/core/config.py ALLOWED_ORIGINS)
    // for http://localhost:5173 by default — no dev-server proxy needed,
    // the axios client (src/api/client.ts) targets the API base URL directly.
  },
});
