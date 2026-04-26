import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/scime/",
  plugins: [react(), tailwindcss()],
  server: {
    // Proxy /api requests to the FastAPI backend during development.
    // Run: uvicorn api:app --reload --port 10000
    proxy: {
      "/api": "http://localhost:10000",
    },
  },
});
