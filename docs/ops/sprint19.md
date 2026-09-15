# Sprint 19 operations

Sprint 19 completes the follow-on PRD Kanban: live Greenhouse/Lever fetch
adapters, matching ensemble + threshold gate, Graph mail sync, and Auto-Apply
submit adapters.

**Live fetch stays Greenhouse + Lever only.** Extra boards stay fixture-only
with flags **off**. Captcha paths never bypass. Robots/consent fail closed.
Graph tokens are sealed at rest. Match scores persist only at or above **70**
(0–100). Auto-Apply idempotency is `user + job + resume`.

Kanban: [sprint19-kanban.md](./sprint19-kanban.md).
Cookbook: [sprint19-api-cookbook.md](./sprint19-api-cookbook.md).

Health `version` is `sprint19`. HTTP: `GET /api/v1/s19/status`, `GET /api/v1/s19/health`,
`GET /api/v1/s19/kanban`, `GET /api/v1/s19/traces`.
