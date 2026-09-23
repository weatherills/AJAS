"""Facade used by the HTTP API and the refresh timer."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.flags import feature_flags
from app.integrations.drive import LocalDriveClient, import_resume, list_library
from app.integrations.easy_apply import audit_log, receipts, reset as reset_easy_apply, submit as easy_apply_submit
from app.integrations.gmail import LocalGmailClient, send_mail, sync_inbox
from app.integrations.harvest import list_applications
from app.integrations.glassdoor_spec import spec_bundle as glassdoor_spec_bundle
from app.integrations.indeed_spec import spec_bundle as indeed_spec_bundle
from app.integrations.ingest import glassdoor_ingest, indeed_ingest, linkedin_ingest, reset_limiter
from app.integrations.linkedin_audit import events as linkedin_events
from app.integrations.linkedin_spec import spec_bundle
from app.integrations.linkedin_session import STORE as SESSION_STORE, reset as reset_sessions
from app.integrations.pipeline import run_linkedin_e2e
from app.integrations.scheduler import reset as reset_scheduler, snapshot as schedule_snapshot, tick
from app.integrations.search import SUPPORTED_INPUTS, parse_search
from app.integrations.slack import MemorySlackHttp, notify_event
from app.mail.graph import GraphClient, default_graph_client
from app.mail.outlook import outlook_status

INGESTERS = {
    "indeed": indeed_ingest,
    "linkedin": linkedin_ingest,
    "glassdoor": glassdoor_ingest,
}


class IntegrationService:
    def __init__(
        self,
        *,
        gmail: LocalGmailClient | None = None,
        drive: LocalDriveClient | None = None,
        slack_http: MemorySlackHttp | None = None,
        graph: GraphClient | None = None,
        jobs: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.gmail = gmail or LocalGmailClient()
        self.drive = drive or LocalDriveClient()
        self.slack_http = slack_http or MemorySlackHttp()
        self.graph = graph
        self.jobs: dict[str, dict[str, Any]] = jobs if jobs is not None else {}
        self.seen: dict[str, dict[str, Any]] = {}

    def status(self) -> dict[str, Any]:
        flags = feature_flags()
        settings = get_settings()
        return {
            "flags": {
                "indeed_adapter": flags.get("indeed_adapter"),
                "linkedin_adapter": flags.get("linkedin_adapter"),
                "linkedin_easy_apply": flags.get("linkedin_easy_apply"),
                "glassdoor_adapter": flags.get("glassdoor_adapter"),
                "greenhouse_harvest": flags.get("greenhouse_harvest"),
                "gmail_adapter": flags.get("gmail_adapter"),
                "google_drive": flags.get("google_drive"),
                "slack_notify": flags.get("slack_notify"),
            },
            "outlook": outlook_status(),
            "searchInputs": SUPPORTED_INPUTS,
            "schedule": schedule_snapshot(),
            "receipts": len(receipts()),
            "jobs": len(self.jobs),
            "slackConfigured": bool((settings.slack_webhook_url or "").strip()),
            "gmailConfigured": bool((settings.google_client_id or "").strip() and (settings.google_client_secret or "").strip()),
            "harvestConfigured": bool((settings.greenhouse_harvest_api_key or "").strip()),
        }

    def ingest(self, source: str, payload: Any, *, search: dict[str, Any] | None = None, listing_url: str | None = None) -> dict[str, Any]:
        fn = INGESTERS.get(source)
        if fn is None:
            return {"jobs": [], "metrics": {"source": source, "enabled": False}, "reason": "unknown_source"}
        return fn(payload, listing_url=listing_url, search=search, seen=self.seen, store=self.jobs)

    def board_spec(self, source: str) -> dict[str, Any]:
        if source == "indeed":
            return indeed_spec_bundle()
        if source == "glassdoor":
            return glassdoor_spec_bundle()
        return spec_bundle()

    def search_spec(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        return parse_search(payload).as_dict()

    def linkedin_spec(self) -> dict[str, Any]:
        bundle = spec_bundle()
        bundle["session"] = {"accounts": SESSION_STORE.list_accounts(), "policy": bundle.get("sessionPolicy")}
        return bundle

    def session_put(self, account_id: str, token: str, *, ttl_seconds: int | None = None) -> dict[str, Any]:
        return SESSION_STORE.put(account_id, token, ttl_seconds=ttl_seconds)

    def session_list(self) -> dict[str, Any]:
        return {"accounts": SESSION_STORE.list_accounts()}

    def session_refresh(self, account_id: str, token: str | None = None) -> dict[str, Any]:
        return SESSION_STORE.refresh(account_id, token)

    def session_revoke(self, account_id: str) -> dict[str, Any]:
        return SESSION_STORE.revoke(account_id)

    def easy_apply(self, body: dict[str, Any]) -> dict[str, Any]:
        job = body.get("job") if isinstance(body.get("job"), dict) else {}
        job_id = body.get("jobId")
        if job_id and not job:
            job = self.jobs.get(str(job_id)) or {"id": job_id}
        return easy_apply_submit(
            job=job,
            profile=dict(body.get("profile") or {}),
            questions=body.get("questions"),
            attachments=body.get("attachments"),
            page=body.get("page"),
            statuses=body.get("statuses"),
            approved_answers=body.get("approvedAnswers"),
            account_id=body.get("accountId") or body.get("account_id"),
        )

    def harvest(self, *, email: str | None = None, page: int = 1, pages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        settings = get_settings()
        return list_applications(
            api_key=settings.greenhouse_harvest_api_key,
            email=email,
            page=page,
            pages=pages,
        )

    def gmail_sync(self, account_id: str, *, labels: list[str] | None = None, fixtures: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return sync_inbox(account_id, labels=labels, client=self.gmail, fixtures=fixtures)

    def gmail_send(self, account_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return send_mail(
            account_id,
            to_addresses=list(body.get("to") or body.get("toAddresses") or []),
            subject=str(body.get("subject") or ""),
            body_text=str(body.get("body") or body.get("bodyText") or ""),
            thread_id=body.get("threadId"),
            client=self.gmail,
        )

    def outlook_delta(self, account_id: str, token: str | None = None) -> dict[str, Any]:
        client = self.graph or default_graph_client()
        messages, next_token = client.delta(account_id, token)
        return {
            "provider": "microsoft-graph",
            "count": len(messages),
            "deltaToken": next_token,
            "items": [
                {
                    "id": item.id,
                    "subject": item.subject,
                    "from": item.from_address,
                    "receivedAt": item.received_at,
                    "conversationId": item.conversation_id,
                }
                for item in messages
            ],
            "outlook": outlook_status(),
        }

    def drive_list(self, user_email: str) -> dict[str, Any]:
        from app.flags import feature_enabled
        from app.integrations.drive import DRIVE_FLAG

        if not feature_enabled(DRIVE_FLAG):
            return {"enabled": False, "items": [], "reason": "flag_off"}
        return {"enabled": True, "reason": "ok", "items": list_library(self.drive, user_email=user_email)}

    def drive_import(self, *, user_id: str, user_email: str, file_id: str, resume_service: Any) -> dict[str, Any]:
        return import_resume(
            user_id=user_id,
            user_email=user_email,
            file_id=file_id,
            client=self.drive,
            resume_service=resume_service,
        )

    def slack(self, *, kind: str, title: str, body: str) -> dict[str, Any]:
        settings = get_settings()
        return notify_event(
            kind=kind,
            title=title,
            body=body,
            webhook_url=settings.slack_webhook_url,
            http=self.slack_http,
        )

    def e2e(self, payload: Any, **kwargs: Any) -> dict[str, Any]:
        result = run_linkedin_e2e(payload, **kwargs)
        for job in result.get("jobs") or []:
            self.jobs[str(job.get("id"))] = job
        return result

    def refresh(self, payloads: dict[str, Any] | None = None) -> dict[str, Any]:
        return tick(payloads=payloads)

    def audit(self) -> dict[str, Any]:
        return {"receipts": receipts(), "events": audit_log(), "telemetry": linkedin_events()}


def get_service() -> IntegrationService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = IntegrationService()
    return _SERVICE


def reset_service() -> None:
    global _SERVICE
    _SERVICE = None
    reset_easy_apply()
    reset_scheduler()
    reset_limiter()
    reset_sessions()
    from app.integrations.linkedin_audit import reset as reset_audit

    reset_audit()
