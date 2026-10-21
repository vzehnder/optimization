import { startSmokeServer } from "./global-setup";

export default async function globalSetup() {
  return startSmokeServer("scripts/run_mesa_smoke_app.py", 8141);
}
