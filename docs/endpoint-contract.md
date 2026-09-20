# Endpoint contract (Functions ↔ frontend live clients)

Canonical list lives in `backend/app/storage/contracts.py` and `contracts/endpoints.json`.
CI fails if a live client path is missing from backend sources or the JSON copy drifts.

| Id | Method | Path | Client |
|---|---|---|---|
| health | GET | `/api/health` | n/a |
| review.list | GET | `/api/v1/matches` | `reviewLive.list` |
| review.get | GET | `/api/v1/matches/{matchId}` | `reviewLive.get` |
| review.decide | POST | `/api/v1/matches/{matchId}/decision` | `reviewLive.decide` |
| matching.rank | POST | `/api/v1/matches/rank` | `matchingLive.scoreMany` |
| autoApply.list | GET | `/api/v1/auto-apply/requests` | `autoApplyLive.list` |
| email.status | GET | `/api/v1/email/status` | `emailLive.status` |
| jobs.list | GET | `/api/v1/jobs` | `jobsLive` |
| resumes.list | GET | `/api/resumes` | `resumeLive` |
| settings.get | GET | `/api/v1/settings` | `settingsLive` |
| ops.queues | GET | `/api/v1/ops/queues` | admin |
| ops.storage | GET | `/api/v1/ops/storage` | admin |
