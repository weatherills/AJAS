# API p95 SLOs

Budgets are enforced in-process (`app.slo`) and exported at `GET /api/v1/ops/slo`.

| Route | p95 budget |
| --- | --- |
| `POST /v1/matches/compute` | 800 ms |
| `POST /v1/matches/rank` | 2500 ms |
| `GET /v1/matches` | 400 ms |
| `GET /v1/jobs` | 600 ms |
| `POST /v1/matches/warmup` | 400 ms |

Alert when `alerts` is non-empty or semantic fallback rate exceeds 5% of scores
(`MatchingService.semantic_fallback_events`).

Wire the JSON into Azure Monitor / App Insights as a custom metric later; locally,
poll `/api/v1/ops/slo` after a Rank or Job Feed load.
