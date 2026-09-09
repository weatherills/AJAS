# AJAS Architecture (Phase 0 skeleton)

This document maps the product features and PRDs onto the code skeleton and the
Azure services from `.codespring/project-overview.md`. It describes the seams
that exist today; feature behavior is implemented per
`.codespring/CURSOR_RUNBOOK.md`.

## High-level shape

```
                +-------------------+       +-----------------------+
  Web UI  --->  | Azure Functions   | --->  | Cosmos DB (serverless)|
 (frontend)     | HTTP APIs (v2)    |       +-----------------------+
                |                   | --->  | Blob Storage          |
                | Queue workers     |       +-----------------------+
                | Timer triggers    | --->  | Storage Queues        |
                +---------+---------+       +-----------------------+
                          |
                          +--> Azure OpenAI (embeddings + summaries)
                          +--> Microsoft Graph (email)
                          +--> Azure Container Apps (auto-apply workers)
```

## Backend structure

The backend is a single Azure Functions app (Python v2 programming model). Shared
infrastructure lives in `backend/app/`; each feature is a blueprint registered in
`backend/function_app.py` as its phase is implemented.

| Module | Responsibility |
| --- | --- |
| `app/config.py` | Typed settings from environment / app settings |
| `app/http.py` | JSON response + standard error envelope |
| `app/auth.py` | Auth seam (Azure AD / B2C JWT — implemented per phase) |
| `app/storage/cosmos.py` | Cosmos DB client + database accessor |
| `app/storage/blobs.py` | Blob service client |
| `app/storage/queues.py` | Storage Queue client factory |
| `app/ai/openai_client.py` | Azure OpenAI client (embeddings + chat) |
| `app/features/health.py` | `GET /api/health` (infrastructure) |

## Feature ↔ phase ↔ PRD map

| Feature module | Runbook phase(s) | PRD(s) | Azure services |
| --- | --- | --- | --- |
| `resume_management` | 1, 9 | `PRDs/resume-management/{backend,database,frontend}` | Blob, Cosmos, Queue, OpenAI |
| `source_ingestion` | 2, 10 | `PRDs/job-source-integration/backend` | Cosmos, Blob, Queue, Timer |
| `matching` | 3, 11 | `PRDs/matching-ranking/backend` | Cosmos, OpenAI, Queue |
| `review_decision` | 4 | (see overview) | Cosmos |
| `auto_apply` | 5 | (see overview) | Queue, Container Apps |
| `email` | 7, 12 | `PRDs/email-ingestion-reply` | Microsoft Graph, Cosmos, Queue, Blob |
| `learning_loop` | 8, 13 | `PRDs/learning-loop/{backend,database,frontend}` | Cosmos, Queue |
| `settings` | 6 | (see overview) | Cosmos |

Feature blueprints are registered in `function_app.py`. Live modules expose HTTP
routes, queue workers, and timers; local development without Cosmos uses
in-memory stores.

## Async pipelines

The PRDs describe queue-driven pipelines, e.g.:

- Resume parse: `POST /resumes` → enqueue → parse worker → Cosmos update.
- Source ingestion: timer → `crawl-runs` queue → `job-fetch` queue → dedupe/upsert.
- Matching (batch): `POST /v1/matches/rank` (N>10) → enqueue → per-pair workers.
- Learning: Review approve/reject → `learning-decisions` queue → optional `tuning-tasks`.

Queue names and message schemas are defined within each feature as it is built.

## Frontend

`frontend/` is a Vite + React + TypeScript app. Phase 0 ships a placeholder
landing page enumerating the planned phases. The Vite dev server listens on
port 3000 (per `.codespring/CURSOR_RUNBOOK.md`) and proxies `/api` to the
Azure Functions host at `http://127.0.0.1:7071`. Feature screens (resume
library/editor, review & decision, settings, email reply, learning metrics) are added per phase
and call the Functions HTTP API.
