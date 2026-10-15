import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";

const python =
  process.env.PYTHON ||
  [resolve("../.venv/Scripts/python.exe"), resolve("../.venv/bin/python")].find(
    existsSync,
  ) ||
  "python";

export default defineConfig({
  testDir: "./e2e",
  testMatch: [
    "hydraulic-reach-rules.spec.ts",
    "hydraulic-connection-handles.spec.ts",
    "hydraulic-transit.spec.ts",
  ],
  workers: 1,
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:8137",
    browserName: "chromium",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `"${python}" ../scripts/run_reach_rules_smoke_app.py`,
    url: "http://127.0.0.1:8137/api/auth/me",
    timeout: 30_000,
    reuseExistingServer: false,
  },
});
