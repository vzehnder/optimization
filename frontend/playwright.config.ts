import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // Mesa owns its authenticated fixture/server in playwright.mesa.config.ts.
  testIgnore: ["optimization-mesa.spec.ts", "mesa-*.spec.ts"],
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  workers: 1,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:8123",
    browserName: "chromium",
    trace: "retain-on-failure",
  },
});
