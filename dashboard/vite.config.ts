import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

// Vite config. `base: "./"` makes the built asset paths relative so Electron can
// load index.html from the filesystem (file://) in production.
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    strictPort: true,
    open: true,
  },
  build: {
    outDir: "dist",
    chunkSizeWarningLimit: 2500,
    sourcemap: false,
  },
});
