import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { once } from "node:events";
import process from "node:process";
import { setTimeout as sleep } from "node:timers/promises";

import { config, pythonBaseUrl } from "../config.js";

export class PythonBridge {
  private child: ChildProcessWithoutNullStreams | null = null;
  private stopping = false;

  async start(): Promise<void> {
    if (this.child) {
      return;
    }

    const env = {
      ...process.env,
      CF_SIM_PORT: String(config.pythonPort),
      CF_SIM_DB_PATH: config.dbPath,
      CF_SIM_STATE_PATH: config.statePath,
    };

    this.child = spawn(config.pythonBin, [config.pythonServerPath], {
      env,
      stdio: "pipe",
      cwd: process.cwd(),
    });

    this.child.stdout.on("data", (buf) => {
      process.stdout.write(`[python] ${String(buf)}`);
    });

    this.child.stderr.on("data", (buf) => {
      process.stderr.write(`[python] ${String(buf)}`);
    });

    this.child.on("exit", (code, signal) => {
      if (!this.stopping) {
        process.stderr.write(`python bridge exited unexpectedly (code=${code}, signal=${signal})\n`);
      }
      this.child = null;
    });

    await this.waitUntilReady();
  }

  getUpstream(): string {
    return pythonBaseUrl;
  }

  async checkUpstream(): Promise<boolean> {
    try {
      const res = await fetch(`${pythonBaseUrl}/api/config`, { method: "GET" });
      return res.ok;
    } catch {
      return false;
    }
  }

  async stop(): Promise<void> {
    if (!this.child) {
      return;
    }
    this.stopping = true;
    this.child.kill("SIGTERM");

    const child = this.child;
    const timeout = sleep(3000).then(() => {
      if (child && child.exitCode === null && child.signalCode === null) {
        child.kill("SIGKILL");
      }
    });

    try {
      await Promise.race([once(child, "exit"), timeout]);
    } finally {
      this.child = null;
      this.stopping = false;
    }
  }

  private async waitUntilReady(): Promise<void> {
    const deadline = Date.now() + 30000;
    while (Date.now() < deadline) {
      if (await this.checkUpstream()) {
        return;
      }
      await sleep(300);
    }
    throw new Error("Python upstream did not become ready within 30s");
  }
}
