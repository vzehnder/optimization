import { readFile, rm } from "node:fs/promises";

const generated = [
  ["openapi.json", "openapi.check.json"],
  ["src/api/schema.ts", "src/api/schema.check.ts"],
];

let drift = false;
for (const [committedPath, checkPath] of generated) {
  const [committed, current] = await Promise.all([
    readFile(committedPath, "utf8"),
    readFile(checkPath, "utf8"),
  ]);
  if (committed !== current.replaceAll("openapi.check.json", "openapi.json")) {
    console.error(`${committedPath} is stale; run npm run api:generate`);
    drift = true;
  }
  await rm(checkPath, { force: true });
}

if (drift) process.exitCode = 1;
