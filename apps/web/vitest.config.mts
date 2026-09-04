import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: { environment: "jsdom", include: ["**/*.test.{ts,tsx}"], exclude: ["node_modules", ".next"] },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./", import.meta.url)),
      "@schema": fileURLToPath(new URL("../../packages/schema/ts/index.ts", import.meta.url)),
    },
  },
});
