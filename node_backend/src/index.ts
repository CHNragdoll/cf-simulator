import process from "node:process";

import { buildApp } from "./app.js";
import { config } from "./config.js";

async function main(): Promise<void> {
  const { app } = await buildApp();

  const close = async () => {
    try {
      await app.close();
    } finally {
      process.exit(0);
    }
  };

  process.on("SIGINT", close);
  process.on("SIGTERM", close);

  await app.listen({ host: config.host, port: config.port });
  app.log.info(`Node simulator running: http://${config.host}:${config.port}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
