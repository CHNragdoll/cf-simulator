import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, type ChildProcess } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";

export async function waitForHttp(url: string, timeoutMs = 30000): Promise<void> {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    try {
      const res = await fetch(url);
      if (res.ok) {
        return;
      }
    } catch {
      // retry
    }
    await sleep(300);
  }
  throw new Error(`Timed out waiting for ${url}`);
}

export function makeTmpCopies(repoRoot: string): { tmpDir: string; dbPath: string; statePath: string } {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "cf-node-migrate-"));
  const dbPath = path.join(tmpDir, "lottery.db");
  const statePath = path.join(tmpDir, "state.json");
  fs.copyFileSync(path.join(repoRoot, "lottery_simulator/data/lottery.db"), dbPath);
  fs.copyFileSync(path.join(repoRoot, "lottery_simulator/data/state.json"), statePath);
  return { tmpDir, dbPath, statePath };
}

export async function stopProcess(child: ChildProcess | null): Promise<void> {
  if (!child || child.killed) {
    return;
  }
  child.kill("SIGTERM");
  await sleep(500);
  if (child.exitCode === null && child.signalCode === null) {
    child.kill("SIGKILL");
  }
}

export function shapeOf(value: unknown): unknown {
  if (value === null) {
    return "null";
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return [];
    }
    return [shapeOf(value[0])];
  }
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj).sort();
    const out: Record<string, unknown> = {};
    for (const k of keys) {
      out[k] = shapeOf(obj[k]);
    }
    return out;
  }
  return typeof value;
}

export function spawnPythonServer(
  pythonBin: string,
  serverPath: string,
  port: number,
  dbPath: string,
  statePath: string,
): ChildProcess {
  return spawn(pythonBin, [serverPath], {
    env: {
      ...process.env,
      CF_SIM_PORT: String(port),
      CF_SIM_DB_PATH: dbPath,
      CF_SIM_STATE_PATH: statePath,
    },
    stdio: "pipe",
    cwd: process.cwd(),
  });
}
