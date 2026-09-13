# Observability how-to v2

Propagate a single `traceId` through ingest → match → apply via
`app.sprint14.ops.traces`. Inspect with `GET /api/v1/s14/traces`.
Alerts use adaptive error-rate thresholds. Health v3 returns the dependency matrix.
