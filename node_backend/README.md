# Node Backend (Fastify + TypeScript)

This directory contains the Node.js migration backend for the CF lottery simulator.

## What is implemented

- Fastify server with TypeScript.
- Static hosting for:
  - `/` and `/admin`
  - `/static/*`
  - `/cf_images/*`
  - `/cfimages/*`
- Compatibility API routing for all existing `/api/*` endpoints.
- Internal health endpoints:
  - `GET /healthz`
  - `GET /readyz`
- Python bridge process (temporary migration mode):
  - Node launches `lottery_simulator/server.py` on an internal port and proxies all `/api/*` traffic.

## Environment variables

- `CF_SIM_HOST` (default: `127.0.0.1`)
- `CF_SIM_PORT` (default: `18080`) - Node listen port
- `CF_SIM_PY_HOST` (default: `127.0.0.1`)
- `CF_SIM_PY_PORT` (default: `18081`) - Python internal port
- `CF_SIM_PYTHON_BIN` (default: `python3`)
- `CF_SIM_PY_SERVER_PATH` (default: `lottery_simulator/server.py`)
- `CF_SIM_DB_PATH` (default: `lottery_simulator/data/lottery.db`)
- `CF_SIM_STATE_PATH` (default: `lottery_simulator/data/state.json`)
- `CF_SIM_STATIC_DIR` (default: `lottery_simulator/static`)
- `CF_SIM_IMAGES_DIR` (default: `cf_images`)

## Start

```bash
cd node_backend
npm install
npm run dev
```

Or production build:

```bash
npm run build
npm run start
```

## Tests

Unit/contract tests are present but skipped by default.

```bash
npm test
RUN_INTEGRATION_TESTS=1 npm test
RUN_CONTRACT_TESTS=1 npm test
```

## Notes

- Current implementation is migration-safe: behavior remains compatible by proxying `/api/*` to Python.
- Next step is route-by-route TypeScript domain replacement under `src/routes` + `src/services` while keeping API contracts unchanged.
