# Node Migration Implementation Report

## Date

2026-02-26

## Completed in this change

1. Added `node_backend/` Fastify + TypeScript project scaffold.
2. Implemented static file compatibility:
   - `/`
   - `/admin`
   - `/static/*`
   - `/cf_images/*`
   - `/cfimages/*`
3. Implemented internal observability endpoints:
   - `GET /healthz`
   - `GET /readyz` (DB/state/upstream checks)
4. Implemented full `/api/*` compatibility path via proxy bridge:
   - Node starts Python backend internally on separate port.
   - Requests to `/api/*` are proxied to Python to preserve response compatibility.
5. Added contract/integration test skeletons for:
   - health endpoints
   - readonly API response-shape parity (Python vs Node)

## Constraint encountered

- Network to npm registry is unavailable (`ENOTFOUND registry.npmjs.org`), so dependencies could not be installed in this environment.
- Source code is fully committed to workspace, but build/test execution requires running `npm install` in a network-enabled environment.

## Compatibility impact

- Frontend pages (`index.html/app.js/admin.html/admin.js`) remain unchanged and can run against Node entrypoint.
- API routes and payloads remain Python-compatible through proxy mode.
- Python service remains rollback-ready.

## Next implementation slice

1. Replace proxied read-only APIs with native TS implementations.
2. Replace write-path APIs with TS transactional domain logic.
3. Move simulation worker to Node worker threads.
4. Enable full contract + E2E pipeline in CI.
