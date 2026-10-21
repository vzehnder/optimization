import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  testMatch: ["optimization-mesa.spec.ts", "mesa-hydraulic-execution.spec.ts"],
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
    reducedMotion: "reduce",
    deviceScaleFactor: 1,
  },
});
