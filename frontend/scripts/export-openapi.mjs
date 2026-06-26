import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

const output = process.argv[2];
if (!output) throw new Error("usage: export-openapi.mjs OUTPUT_PATH");

const candidates = [
  process.env.PYTHON,
  resolve("../.venv/Scripts/python.exe"),
  resolve("../.venv/bin/python"),
  "python",
].filter(Boolean);
const python = candidates.find(
  (candidate) => candidate === "python" || existsSync(candidate),
);
const result = spawnSync(
  python,
  [resolve("../scripts/export_openapi.py"), output],
  {
    stdio: "inherit",
  },
);
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
