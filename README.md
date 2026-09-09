# AJAS — AI Job Application System

AJAS ingests job postings, matches them against a user's resume using hybrid
keyword + semantic scoring, and streamlines review, auto-apply, and email
follow-up. See `.codespring/project-overview.md` for the product overview and
`.codespring/CURSOR_RUNBOOK.md` for the phased implementation plan.

> Status: **Phase 4 — Resume Management.** Users can upload and parse resumes,
> review matches, auto-apply, and persist settings. Remaining features are still
> planned.

## Repository layout

```
.
├── backend/     # Azure Functions app (Python v2 model) — API, workers, timers
├── frontend/    # React + TypeScript + Vite web UI
├── docs/        # Architecture notes
└── .codespring/ # Product overview, runbook, and per-feature PRDs
```

Each runbook phase adds a feature module under `backend/app/features/` and its
corresponding UI under `frontend/`. See `docs/architecture.md` for how the PRD
features map onto the skeleton and Azure services. REST Client samples for
Review and Settings live in `docs/api/`.

## Tech stack

- **Azure Functions (Consumption)** — event-driven HTTP APIs, queue workers, timers
- **Azure Cosmos DB (Serverless)** — JobPosting / Match / Application / resume data
- **Azure Blob Storage** — resumes, raw postings, artifacts
- **Azure Storage Queues** — asynchronous pipelines (parse, crawl, match, apply)
- **Azure OpenAI** — embeddings (semantic matching) and summaries
- **Microsoft Graph API** — email ingestion and reply
- **Azure Container Apps** — on-demand workers (e.g. headless browser for auto-apply)

## Local development

The Cloud Agent environment provisions the toolchain (Python 3.12, Azure
Functions Core Tools v4, Azurite, Node.js 22). To set up manually, see
`.cursor/install.sh`.

### Backend

```bash
source .venv/bin/activate           # project virtualenv
pip install -r backend/requirements-dev.txt
cp backend/local.settings.json.example backend/local.settings.json
cd backend && func start            # http://localhost:7071/api/health
```

Run backend tests:

```bash
cd backend && pytest
```

### Frontend

```bash
cd frontend
npm install
npm run dev                         # http://localhost:3000
```

### Local Azure services

Azurite emulates Blob/Queue/Table storage locally (started automatically by the
Cloud Agent environment; otherwise run `azurite`). Cosmos DB and Azure OpenAI
are managed services — provide connection settings in
`backend/local.settings.json` when implementing features that use them.
