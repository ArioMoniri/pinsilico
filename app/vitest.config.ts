import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/tests/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      coverage: {
        provider: "v8",
        reporter: ["text", "lcov"],
        thresholds: {
          lines: 85,
          branches: 75,
          functions: 85,
          statements: 85,
        },
        exclude: ["src/tests/**", "src/main.tsx", "**/*.d.ts"],
      },
    },
  }),
);
