"""Source Ingestion / Job Source Integration — Runbook Phase 2 (and Phase 10).

PRD:
  .codespring/PRDs/job-source-integration/backend-prd-job-source-integration.md

To implement (see PRD): timer-triggered scheduler, crawl-run and job-fetch queue
workers, Greenhouse/Lever fetchers with rate limiting/backoff, normalization,
deduplication, and the admin crawl API.

Placeholder blueprint — no routes are defined yet.
"""
import azure.functions as func

bp = func.Blueprint()
