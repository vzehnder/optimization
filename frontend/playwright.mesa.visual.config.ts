import { defineConfig } from "@playwright/test";
import mesa from "./playwright.mesa.config";

// Fixed order and a fresh isolated database make review captures reproducible.
// These are candidates for human review; no approved screenshot baseline yet.
export default defineConfig({
  ...mesa,
  grep: /La ayuda acompaña|Cuatro paneles de comparación|La matriz hidráulica muestra|la matriz 2x2 cabe/,
  outputDir: "../.tmp/mesa-visual-review",
});
