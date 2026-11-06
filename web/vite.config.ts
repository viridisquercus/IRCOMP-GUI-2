/**
 * @file vite.config.ts
 * @brief Build of the web client, in development /api goes to Python
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 */
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
