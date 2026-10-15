import { defineConfig } from "@playwright/test";
import reaches from "./playwright.reaches.config";

export default defineConfig({
  ...reaches,
  testMatch: "hydraulic-seepage.spec.ts",
  use: { ...reaches.use, viewport: { width: 1440, height: 1000 } },
});
