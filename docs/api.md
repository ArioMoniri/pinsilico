# Sidecar HTTP API

> This document is auto-regenerated from the FastAPI OpenAPI schema once the
> Phase 5 generator script lands. The Phase 0 surface is hand-written below
> as a reference.

The sidecar exposes a local-only HTTP API on `127.0.0.1:<ephemeral-port>`.
The Tauri shell reads the port from the sidecar's stdout at launch (Phase 6).

Every route except `/health` will require the `X-Pinsilico-Token` header
(landing in Phase 1).

## Endpoints (Phase 0)

### `GET /health`

Liveness probe used by the Tauri shell's startup health-check loop.

**Authentication:** None (deliberately — the shell needs to probe before it
has finished reading the auth token from stdout).

**Response 200**

```json
{ "status": "ok", "version": "0.0.1" }
```

| Field     | Type   | Notes                                       |
|-----------|--------|---------------------------------------------|
| `status`  | string | Always `"ok"` when the response is 200.     |
| `version` | string | Sidecar package version (`pinsilico.__version__`). |

The contract is locked by `sidecar/tests/unit/test_health.py`. Phase 1 may
add additive fields (`uptime_seconds`, `build_sha`) but must never remove
`status` or `version`.

## Coming next

- Phase 1: `POST /shutdown` (graceful exit), token auth, structured-log
  middleware.
- Phase 2: `GET /db/{provider}/...`.
- Phase 3: `POST /pocket/detect`, `POST /docking/dock`,
  `GET /docking/jobs/{id}`.
- Phase 4: `POST /sim/run` (SSE stream), `POST /sim/fast_forward`.
- Phase 10: `POST /session/save`, `POST /session/load`,
  `POST /io/import`, `GET /io/export/{format}`.
