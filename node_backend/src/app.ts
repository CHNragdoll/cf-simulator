import fastify, { type FastifyInstance } from "fastify";
import fastifyProxy from "@fastify/http-proxy";
import fastifyStatic from "@fastify/static";

import { config } from "./config.js";
import { registerHealthRoutes } from "./routes/health.js";
import { PythonBridge } from "./services/python-bridge.js";

export async function buildApp(): Promise<{ app: FastifyInstance; bridge: PythonBridge }> {
  const app = fastify({ logger: true });
  const bridge = new PythonBridge();

  await bridge.start();

  await registerHealthRoutes(app, bridge);

  await app.register(fastifyStatic, {
    root: config.staticDir,
    prefix: "/static/",
  });

  await app.register(fastifyStatic, {
    root: config.imagesDir,
    prefix: "/cf_images/",
    decorateReply: false,
  });

  await app.register(fastifyStatic, {
    root: config.imagesDir,
    prefix: "/cfimages/",
    decorateReply: false,
  });

  app.get("/", async (_request, reply) => {
    return reply.sendFile("index.html", config.staticDir);
  });

  app.get("/admin", async (_request, reply) => {
    return reply.sendFile("admin.html", config.staticDir);
  });

  await app.register(fastifyProxy, {
    upstream: bridge.getUpstream(),
    prefix: "/api",
    rewritePrefix: "/api",
    replyOptions: {
      rewriteRequestHeaders: (request, headers) => ({
        ...headers,
        host: `${config.pythonHost}:${config.pythonPort}`,
        "x-forwarded-host": request.headers.host ?? "",
      }),
    },
  });

  app.setNotFoundHandler(async (request, reply) => {
    if (request.raw.url?.startsWith("/api/")) {
      return reply.code(404).send({ error: "Not Found" });
    }

    return reply.type("text/html; charset=utf-8").sendFile("index.html", config.staticDir);
  });

  app.addHook("onClose", async () => {
    await bridge.stop();
  });

  return { app, bridge };
}
