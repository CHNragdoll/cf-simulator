import type { FastifyInstance } from "fastify";

import { buildReadyReport } from "../services/readiness.js";
import { PythonBridge } from "../services/python-bridge.js";

export async function registerHealthRoutes(app: FastifyInstance, bridge: PythonBridge): Promise<void> {
  app.get("/healthz", async () => ({ ok: true }));

  app.get("/readyz", async (request, reply) => {
    const report = await buildReadyReport(bridge);
    if (!report.ok) {
      return reply.code(503).send(report);
    }
    return report;
  });
}
