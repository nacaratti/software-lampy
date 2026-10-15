import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Backend the dev proxy forwards to. Override with LAMPY_API_URL when port
// 8000 is taken (e.g. LAMPY_API_URL=http://127.0.0.1:8001 npm run dev).
const apiTarget = process.env.LAMPY_API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": apiTarget,
      "/ws": {
        target: apiTarget.replace(/^http/, "ws"),
        ws: true,
      },
    },
  },
});
