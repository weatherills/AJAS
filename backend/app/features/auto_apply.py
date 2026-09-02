"""Auto-Apply — Runbook Phase 5.

On approval, auto-fill/submit via source APIs and track application status.
Long-running submission work targets Azure Container Apps workers via queues.

Placeholder blueprint — no routes are defined yet.
"""
import azure.functions as func

bp = func.Blueprint()
