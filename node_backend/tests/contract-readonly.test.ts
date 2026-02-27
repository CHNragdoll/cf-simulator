import path from "node:path";
import process from "node:process";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { buildApp } from "../src/app.js";
import {
  makeTmpCopies,
  shapeOf,
  spawnPythonServer,
  stopProcess,
  waitForHttp,
} from "./helpers.js";

const runContract = process.env.RUN_CONTRACT_TESTS === "1";
const maybeDescribe = runContract ? describe : describe.skip;

maybeDescribe("readonly API contract", () => {
  const pythonBase = "http://127.0.0.1:19280";
  const nodeBase = "http://127.0.0.1:19281";
  let appInstance: Awaited<ReturnType<typeof buildApp>> | null = null;
  let baselinePython: ReturnType<typeof spawnPythonServer> | null = null;

  const repoRoot = path.resolve(process.cwd(), "..");
  const pythonServerPath = path.resolve(repoRoot, "lottery_simulator/server.py");
  const tmpA = makeTmpCopies(repoRoot);
  const tmpB = makeTmpCopies(repoRoot);

  beforeAll(async () => {
    baselinePython = spawnPythonServer("python3", pythonServerPath, 19280, tmpA.dbPath, tmpA.statePath);
    await waitForHttp(`${pythonBase}/api/config`);

    process.env.CF_SIM_PORT = "19281";
    process.env.CF_SIM_PY_PORT = "19282";
    process.env.CF_SIM_PY_SERVER_PATH = pythonServerPath;
    process.env.CF_SIM_DB_PATH = tmpB.dbPath;
    process.env.CF_SIM_STATE_PATH = tmpB.statePath;

    appInstance = await buildApp();
    await appInstance.app.listen({ host: "127.0.0.1", port: 19281 });
    await waitForHttp(`${nodeBase}/api/config`);
  });

  afterAll(async () => {
    if (appInstance) {
      await appInstance.app.close();
    }
    await stopProcess(baselinePython);
  });

  const paths = [
    "/api/config",
    "/api/state",
    "/api/analysis",
    "/api/db/items",
    "/api/db/meta",
    "/api/db/schema?table=prize_items",
    "/api/db/rows?table=purchase_options",
  ];

  for (const p of paths) {
    it(`matches shape for ${p}`, async () => {
      const [pythonRes, nodeRes] = await Promise.all([fetch(`${pythonBase}${p}`), fetch(`${nodeBase}${p}`)]);
      expect(nodeRes.status).toBe(pythonRes.status);

      const [pythonBody, nodeBody] = await Promise.all([pythonRes.json(), nodeRes.json()]);
      expect(shapeOf(nodeBody)).toEqual(shapeOf(pythonBody));
    });
  }
});
