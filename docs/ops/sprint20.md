# Sprint 20 operations

Sprint 20 lands the live CodeSpring Kanban for Greenhouse/Lever ingest,
matching 0–100 scores, Graph mail, Auto-Apply submit, and review APIs.

**Live fetch stays Greenhouse + Lever only.** Extra boards stay fixture-only
with flags **off**. Captcha paths never bypass. Robots/consent fail closed.
Graph tokens are sealed at rest. Match scores persist only at or above **70**.
Auto-Apply idempotency is `user + job + resume`.

Kanban: [sprint20-kanban.md](./sprint20-kanban.md).
Cookbook: [sprint20-api-cookbook.md](./sprint20-api-cookbook.md).

Health `version` is `sprint20`. HTTP: `GET /api/v1/s20/status`, `GET /api/v1/s20/health`,
`GET /api/v1/s20/kanban`, `GET /api/v1/s20/traces`.
