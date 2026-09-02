"""AI Matching / Matching & Ranking — Runbook Phase 3 (and Phase 11).

PRD:
  .codespring/PRDs/matching-ranking/backend-prd-matching-ranking.md

To implement (see PRD): POST /v1/matches/compute and /rank, GET /v1/matches,
operations endpoints, hybrid keyword+semantic scoring via Azure OpenAI
embeddings, threshold persistence, and async batch workers.

Placeholder blueprint — no routes are defined yet.
"""
import azure.functions as func

bp = func.Blueprint()
