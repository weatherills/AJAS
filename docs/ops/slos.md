# API p95 SLOs

Budgets are enforced in-process (`app.slo`) and exported at `GET /api/v1/ops/slo`.

| Route | p95 budget |
| --- | --- |
| `POST /v1/matches/compute` | 800 ms |
| `POST /v1/matches/rank` | 2500 ms |
| `GET /v1/matches` | 400 ms |
| `GET /v1/jobs` | 600 ms |
| `POST /v1/matches/warmup` | 400 ms |
| `GET /v1/review` | 400 ms |
| `POST /v1/sources/crawl` | 8000 ms |

Alert when `alerts` is non-empty or semantic fallback rate exceeds 5% of scores
(`MatchingService.semantic_fallback_events`).

Live samples appear on the Ops page after Review, Job Feed, compute, rank, warmup, or crawl traffic. Wire the JSON into Azure Monitor / App Insights as a custom metric later (`APPLICATIONINSIGHTS_CONNECTION_STRING` emits `ajas.monitor`).
