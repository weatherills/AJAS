# Sprint 17 operations

Sprint 17 lands the live CodeSpring Kanban generated from the product PRDs:
Greenhouse/Lever ingest, matching, review, Graph mail, Auto-Apply, and learning.

**Live fetch stays Greenhouse + Lever only.** Extra boards stay fixture-only
with flags **off**. Captcha paths never bypass. Robots/consent fail closed.
Graph tokens are sealed at rest.

Kanban: [sprint17-kanban.md](./sprint17-kanban.md).
Cookbook: [sprint17-api-cookbook.md](./sprint17-api-cookbook.md).

Health `version` is `sprint17`. HTTP: `GET /api/v1/s17/status`, `GET /api/v1/s17/health`,
`GET /api/v1/s17/kanban`, `GET /api/v1/s17/traces`.
