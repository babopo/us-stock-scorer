import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 650
  },
  resolve: {
    alias: {
      "@stock-scorer/api-client": fileURLToPath(new URL("../../packages/api-client/src/index.ts", import.meta.url))
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    testTimeout: 15000
  }
});
