import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  cacheDir: "../../tmp/vite-cache",
  plugins: [vue()],
  build: {
    outDir: "../../tmp/frontend-dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});