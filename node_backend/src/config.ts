import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "../../");

function resolvePath(input: string | undefined, fallback: string): string {
  if (!input || input.trim() === "") {
    return path.resolve(repoRoot, fallback);
  }
  if (path.isAbsolute(input)) {
    return input;
  }
  return path.resolve(repoRoot, input);
}

export const config = {
  host: process.env.CF_SIM_HOST ?? "127.0.0.1",
  port: Number(process.env.CF_SIM_PORT ?? "18080"),
  pythonHost: process.env.CF_SIM_PY_HOST ?? "127.0.0.1",
  pythonPort: Number(process.env.CF_SIM_PY_PORT ?? "18081"),
  pythonBin: process.env.CF_SIM_PYTHON_BIN ?? "python3",
  dbPath: resolvePath(process.env.CF_SIM_DB_PATH, "lottery_simulator/data/lottery.db"),
  statePath: resolvePath(process.env.CF_SIM_STATE_PATH, "lottery_simulator/data/state.json"),
  pythonServerPath: resolvePath(process.env.CF_SIM_PY_SERVER_PATH, "lottery_simulator/server.py"),
  staticDir: resolvePath(process.env.CF_SIM_STATIC_DIR, "lottery_simulator/static"),
  imagesDir: resolvePath(process.env.CF_SIM_IMAGES_DIR, "cf_images"),
} as const;

export const pythonBaseUrl = `http://${config.pythonHost}:${config.pythonPort}`;
