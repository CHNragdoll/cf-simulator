import path from "node:path";

import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { buildApp } from "../src/app.js";

const runIntegration = process.env.RUN_INTEGRATION_TESTS === "1";
const maybeDescribe = runIntegration ? describe : describe.skip;

maybeDescribe("health routes", () => {
  let appInstance: Awaited<ReturnType<typeof buildApp>> | null = null;

  beforeAll(async () => {
    process.env.CF_SIM_PORT = "19180";
    process.env.CF_SIM_PY_PORT = "19181";
    process.env.CF_SIM_PY_SERVER_PATH = path.resolve(process.cwd(), "../lottery_simulator/server.py");
    process.env.CF_SIM_DB_PATH = path.resolve(process.cwd(), "../lottery_simulator/data/lottery.db");
    process.env.CF_SIM_STATE_PATH = path.resolve(process.cwd(), "../lottery_simulator/data/state.json");
    appInstance = await buildApp();
    await appInstance.app.listen({ host: "127.0.0.1", port: 19180 });
  });

  afterAll(async () => {
    if (appInstance) {
      await appInstance.app.close();
    }
  });

  it("returns liveness", async () => {
    const res = await fetch("http://127.0.0.1:19180/healthz");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body).toEqual({ ok: true });
  });

  it("returns readiness", async () => {
    const res = await fetch("http://127.0.0.1:19180/readyz");
    expect([200, 503]).toContain(res.status);
    const body = await res.json();
    expect(typeof body.ok).toBe("boolean");
    expect(body.checks).toBeDefined();
  });
});
