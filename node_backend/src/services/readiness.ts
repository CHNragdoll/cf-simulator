import fs from "node:fs";

import Database from "better-sqlite3";

import { config } from "../config.js";
import type { ReadyReport } from "../types/health.js";
import { PythonBridge } from "./python-bridge.js";

export async function buildReadyReport(bridge: PythonBridge): Promise<ReadyReport> {
  let dbReadable = false;
  let stateReadable = false;
  let stateWritable = false;
  let details = "";

  try {
    const db = new Database(config.dbPath, { readonly: true });
    db.prepare("SELECT 1").get();
    db.close();
    dbReadable = true;
  } catch (err) {
    details += `db: ${(err as Error).message}; `;
  }

  try {
    fs.accessSync(config.statePath, fs.constants.R_OK);
    stateReadable = true;
  } catch (err) {
    details += `state-read: ${(err as Error).message}; `;
  }

  try {
    fs.accessSync(config.statePath, fs.constants.W_OK);
    stateWritable = true;
  } catch (err) {
    details += `state-write: ${(err as Error).message}; `;
  }

  const upstream = await bridge.checkUpstream();

  const ok = dbReadable && stateReadable && stateWritable && upstream;
  return {
    ok,
    checks: {
      db_readable: dbReadable,
      state_readable: stateReadable,
      state_writable: stateWritable,
      python_upstream: upstream,
    },
    details: details.trim() || undefined,
  };
}
