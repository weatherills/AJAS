# Sprint 18 operations

Sprint 18 lands the live CodeSpring Kanban skeletons generated from the
product PRDs: Greenhouse/Lever ingest wiring, matching 0–100 scores,
Graph mail pipelines, and Auto-Apply executor/adapters.

**Live fetch stays Greenhouse + Lever only.** Extra boards stay fixture-only
with flags **off**. Captcha paths never bypass. Robots/consent fail closed.
Graph tokens are sealed at rest. Match scores persist only at or above the
default threshold of **70** (0–100). Auto-Apply idempotency is
`user + job + resume`.

Kanban: [sprint18-kanban.md](./sprint18-kanban.md).
Cookbook: [sprint18-api-cookbook.md](./sprint18-api-cookbook.md).

Health `version` is `sprint18`. HTTP: `GET /api/v1/s18/status`, `GET /api/v1/s18/health`,
`GET /api/v1/s18/kanban`, `GET /api/v1/s18/traces`.
