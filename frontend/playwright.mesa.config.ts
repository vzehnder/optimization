import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: [
    "mesa-acceptance.spec.ts",
    "optimization-mesa.spec.ts",
    "mesa-hydraulic-execution.spec.ts",
    "mesa-comparison.spec.ts",
    "mesa-hydraulic-comparison.spec.ts",
    "mesa-hydraulic-assets.spec.ts",
    "mesa-history.spec.ts",
    "mesa-manual-series.spec.ts",
    "mesa-charts.spec.ts",
    "mesa-layout.spec.ts",
  ],
  globalSetup: "./e2e/mesa-global-setup.ts",
  outputDir: "../.tmp/mesa-playwright-results",
  workers: 1,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:8141",
    browserName: "chromium",
    trace: "retain-on-failure",
    locale: "en-US",
    timezoneId: "America/Santiago",
    colorScheme: "light",
    contextOptions: { reducedMotion: "reduce" },
    deviceScaleFactor: 1,
  },
});
