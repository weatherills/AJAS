"""Resume Management — Runbook Phase 1 (and revisited in Phase 9).

PRDs:
  .codespring/PRDs/resume-management/backend-prd-resume-management.md
  .codespring/PRDs/resume-management/database-prd-resume-management.md
  .codespring/PRDs/resume-management/frontend-prd-resume-management.md

Endpoints/workers to implement (see backend PRD): POST/GET /resumes,
GET /resumes/{id}, preview-url, PATCH/DELETE /resumes/{id}, per-run active
resume selection, and the async parse queue worker.

Placeholder blueprint — no routes are defined yet.
"""
import azure.functions as func

bp = func.Blueprint()
