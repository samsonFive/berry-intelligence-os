import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/static/investigation/",
  build: {
    outDir: fileURLToPath(new URL("../app/static/investigation", import.meta.url)),
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:18000",
      "/static": "http://127.0.0.1:18000",
    },
  },
});
