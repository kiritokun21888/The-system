import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Electron loads the built files from disk, so we use a relative base.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
