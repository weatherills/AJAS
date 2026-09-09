# AJAS Backend (Azure Functions, Python)

Azure Functions app (Python v2 programming model) for the AI Job Application
System. Feature blueprints cover Review, Auto-Apply, Settings, Resume,
Job Source, Matching, and Email Ingestion.

## Layout

```
backend/
├── function_app.py            # App entry; registers blueprints
├── host.json                  # Functions host config (extension bundle v4)
├── requirements.txt           # Runtime dependencies
├── requirements-dev.txt       # + test tooling
├── local.settings.json.example# Copy to local.settings.json (gitignored)
└── app/
    ├── config.py              # Settings from environment
    ├── http.py                # JSON response + error envelope helpers
    ├── auth.py                # Auth seam (AAD/B2C JWT — implemented per phase)
    ├── storage/               # Cosmos / Blob / Queue client factories
    ├── ai/                    # Azure OpenAI client factory
    └── features/              # One module per runbook phase
        ├── health.py          # GET /api/health (infrastructure)
        ├── resume_management.py
        ├── source_ingestion.py
        ├── matching.py
        ├── review_decision.py
        ├── auto_apply.py
        ├── email.py
        ├── learning_loop.py
        └── settings.py
```

## Run locally

Prerequisites (provided by the Cloud Agent environment): Python 3.12, Azure
Functions Core Tools v4, and Azurite. See the repository root `README.md`.

```bash
# from repo root, with the project virtualenv active
cp backend/local.settings.json.example backend/local.settings.json
cd backend
func start           # serves http://localhost:7071/api/health
```

## Test

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```
