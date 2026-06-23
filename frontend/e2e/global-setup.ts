import { execFile, spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const repoRoot = resolve("..");
const serverUrl = "http://127.0.0.1:8123/login";

function pythonExecutable(): string {
  return (
    process.env.PYTHON ||
    [
      resolve(repoRoot, ".venv/Scripts/python.exe"),
      resolve(repoRoot, ".venv/bin/python"),
    ].find(existsSync) ||
    "python"
  );
}

async function stopServer(server: ChildProcess): Promise<void> {
  if (server.exitCode !== null || server.pid === undefined) return;
  if (process.platform === "win32") {
    await new Promise<void>((resolveStop) => {
      execFile("taskkill", ["/pid", String(server.pid), "/T", "/F"], () =>
        resolveStop(),
      );
    });
    return;
  }
  server.kill("SIGTERM");
}

async function waitForServer(server: ChildProcess): Promise<void> {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (server.exitCode !== null)
      throw new Error(`Smoke server exited with ${server.exitCode}`);
    try {
      const response = await fetch(serverUrl);
      if (response.ok) return;
    } catch {
      // Server is still starting.
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 100));
  }
  throw new Error(`Smoke server did not become ready at ${serverUrl}`);
}

export default async function globalSetup() {
  const server = spawn(
    pythonExecutable(),
    [resolve(repoRoot, "scripts/run_react_smoke_app.py")],
    {
      cwd: repoRoot,
      env: { ...process.env, REACT_SMOKE_PORT: "8123" },
      stdio: "ignore",
      windowsHide: true,
    },
  );
  try {
    await waitForServer(server);
  } catch (error) {
    await stopServer(server);
    throw error;
  }
  return async () => stopServer(server);
}
