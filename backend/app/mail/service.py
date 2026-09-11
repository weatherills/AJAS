"""Email Ingestion & Reply application service."""

from __future__ import annotations

import base64
import logging
from datetime import timedelta

from app.config import get_settings as get_app_settings
from app.config import microsoft_oauth_configured
from app.mail.bounce import classify_delivery, thread_fingerprint
from app.mail.errors import (
    MailConflictError,
    MailForbiddenError,
    MailNotFoundError,
    MailRateLimitedError,
    MailUnauthorizedError,
    MailUnprocessableError,
    MailValidationError,
)
from app.mail.graph import GraphAttachment, GraphClient, GraphMessage, LocalGraphClient, pending_followup
from app.mail.pii import redact_pii
from app.mail.keys import (
    apply_template,
    body_hash,
    new_id,
    parse_ts,
    sha256_text,
    snippet_of,
    unfilled_template_vars,
    utc_now,
)
from app.mail.linking import JobHint, decide_link
from app.mail.models import (
    EmailAccount,
    EmailAttachment,
    EmailIngestionEvent,
    EmailMessage,
    EmailRecipient,
    EmailThread,
    GraphSubscription,
    GraphSyncCursor,
    LinkAudit,
    ReplyIdempotency,
    SuggestionUse,
)
from app.mail.queues import JobQueue
from app.mail.store import EmailStore
from app.mail.suggestions import generate_suggestions

log = logging.getLogger("ajas")


class EmailService:
    def __init__(
        self,
        store: EmailStore,
        queue: JobQueue,
        graph: GraphClient,
        *,
        local_mode: bool = True,
        clock=utc_now,
        settings_store=None,
    ) -> None:
        self.store = store
        self.queue = queue
        self.graph = graph
        self.local_mode = local_mode
        self.clock = clock
        self.settings_store = settings_store

    def status(self, user_id: str) -> dict:
        connection = self._graph_connection(user_id)
        graph_ok = connection is not None
        account = self._mailbox(user_id, create_demo=self.local_mode and not graph_ok)
        return self._status_json(account, connection)

    def list_threads(self, user_id: str, *, job_id: str | None = None, unlinked_only: bool = False, limit: int = 50, cursor: str | None = None) -> dict:
        account = self._require_mailbox(user_id)
        rows = self.store.list_threads(account.id, job_id=job_id, unlinked_only=unlinked_only)
        rows = self._merge_thread_views(rows)
        offset = int(cursor) if cursor else 0
        if offset < 0:
            raise MailValidationError("invalid cursor", path="cursor")
        limit = max(1, min(limit, 100))
        page = rows[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(rows) else None
        return {"items": [self._thread_json(item) for item in page], "nextCursor": next_cursor, "total": len(rows)}

    def list_messages(self, user_id: str, thread_id: str, *, limit: int = 50, cursor: str | None = None) -> dict:
        account = self._require_mailbox(user_id)
        thread = self._owned_thread(account, thread_id)
        self.store.mark_thread_read(thread.id)
        thread = self.store.get_thread(thread.id)
        rows = self.store.list_messages(thread.id)
        offset = int(cursor) if cursor else 0
        limit = max(1, min(limit, 200))
        page = rows[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(rows) else None
        return {
            "thread": self._thread_json(thread),
            "items": [self._message_json(item) for item in page],
            "nextCursor": next_cursor,
            "total": len(rows),
        }

    def download_attachment(self, user_id: str, attachment_id: str) -> tuple[bytes, str, str]:
        account = self._require_mailbox(user_id)
        attachment = self.store.get_attachment(attachment_id)
        if attachment.email_account_id != account.id or attachment.user_id != user_id:
            raise MailNotFoundError(attachment_id)
        if attachment.status != "stored" or not attachment.blob_path:
            raise MailUnprocessableError("attachment is not available for download", path="attachment")
        content = self.store.get_blob(attachment.blob_path)
        if content is None:
            raise MailNotFoundError(attachment_id)
        return content, attachment.content_type or "application/octet-stream", attachment.file_name

    def reply(self, user_id: str, thread_id: str, body: dict) -> tuple[int, dict]:
        account = self._require_mailbox(user_id)
        thread = self._owned_thread(account, thread_id)
        body_text = (body.get("bodyText") or body.get("body_text") or "").strip()
        template_id = body.get("templateId") or body.get("template_id")
        variables = body.get("variables") or {}
        if template_id:
            template = next((item for item in self.store.templates() if item["id"] == template_id), None)
            if template is None:
                raise MailNotFoundError(template_id)
            body_text = apply_template(template["body"], {str(k): str(v) for k, v in variables.items()})
        elif variables:
            body_text = apply_template(body_text, {str(k): str(v) for k, v in variables.items()})
        if not body_text:
            raise MailValidationError("bodyText is required", path="bodyText")
        leftover = unfilled_template_vars(body_text)
        if leftover:
            raise MailUnprocessableError(
                f"unfilled template variables: {', '.join(leftover)}",
                path="variables",
            )
        key = (body.get("idempotencyKey") or body.get("idempotency_key") or "").strip()
        if key:
            existing = self.store.get_idempotency(self._idempotency_id(user_id, thread_id, key))
            if existing and not self._expired(existing.created_at, hours=get_app_settings().mail_reply_idempotency_hours):
                raise MailConflictError("duplicate idempotencyKey")
        attachments_in = body.get("attachments") or []
        graph_attachments = self._validate_outgoing_attachments(attachments_in)
        messages = self.store.list_messages(thread.id)
        last_inbound = next((item for item in reversed(messages) if item.is_incoming), messages[-1] if messages else None)
        to_addresses = [last_inbound.from_address] if last_inbound else [p for p in thread.participants if p != account.address]
        sent = self.graph.send_reply(
            account.id,
            conversation_id=thread.graph_conversation_id,
            internet_message_id=last_inbound.internet_message_id if last_inbound else f"<root-{thread.id}@ajas.dev>",
            subject=thread.subject,
            body_text=body_text,
            to_addresses=to_addresses,
            attachments=graph_attachments,
        )
        now = self.clock()
        message = EmailMessage(
            email_account_id=account.id,
            email_thread_id=thread.id,
            user_id=user_id,
            graph_message_id=sent.id,
            internet_message_id=sent.internet_message_id,
            conversation_id=thread.graph_conversation_id,
            in_reply_to=sent.in_reply_to,
            references=sent.references,
            from_address=account.address,
            from_name="You",
            to_addresses=to_addresses,
            subject=sent.subject,
            body_text=body_text,
            body_html=body.get("bodyHtml") or body.get("body_html"),
            received_at=now,
            sent_at=now,
            is_incoming=False,
            is_read=True,
            delivery_status="sent",
            has_attachments=bool(graph_attachments),
            created_at=now,
            updated_at=now,
        )
        saved = self.store.upsert_message(message)
        self._store_attachments(saved, graph_attachments, incoming=False)
        if key:
            self.store.put_idempotency(
                ReplyIdempotency(
                    id=self._idempotency_id(user_id, thread_id, key),
                    user_id=user_id,
                    thread_id=thread_id,
                    message_id=saved.id,
                    created_at=now,
                )
            )
        log.info("ajas.mail.reply thread_id=%s message_id=%s", thread.id, saved.id)
        return 201, self._message_json(saved)

    def suggestions(self, user_id: str, thread_id: str, body: dict | None = None) -> dict:
        account = self._require_mailbox(user_id)
        thread = self._owned_thread(account, thread_id)
        now = self.clock()
        limit = get_app_settings().mail_suggestion_limit_per_day
        if self.store.suggestion_count_today(thread.id, now=now) >= limit:
            raise MailRateLimitedError(
                "Suggestion limit reached for today. Try again tomorrow.",
                retry_after=86400,
            )
        messages = self.store.list_messages(thread.id)
        payload = body or {}
        drafts = generate_suggestions(
            thread,
            messages,
            tone=payload.get("tone"),
            notes=payload.get("contextNotes") or payload.get("context_notes"),
        )
        self.store.record_suggestion(SuggestionUse(thread_id=thread.id, user_id=user_id, created_at=now))
        return {"items": drafts}

    def link(self, user_id: str, thread_id: str, body: dict) -> dict:
        account = self._require_mailbox(user_id)
        thread = self._owned_thread(account, thread_id)
        job_id = (body.get("jobId") or body.get("job_posting_id") or "").strip()
        if not job_id:
            raise MailValidationError("jobId is required", path="jobId")
        job = next((item for item in self._jobs() if item.id == job_id), None)
        if job is None:
            raise MailNotFoundError(job_id)
        updated = self.store.link_thread(
            thread.id,
            job_posting_id=job.id,
            job_title=job.title,
            job_company=job.company,
            source="manual",
            confidence=100,
        )
        self.store.record_audit(
            LinkAudit(
                email_account_id=account.id,
                thread_id=thread.id,
                method="manual",
                score=1.0,
                job_posting_id=job.id,
                actor=user_id,
                created_at=self.clock(),
            )
        )
        return self._thread_json(updated)

    def unlink(self, user_id: str, thread_id: str) -> dict:
        account = self._require_mailbox(user_id)
        thread = self._owned_thread(account, thread_id)
        updated = self.store.unlink_thread(thread.id)
        self.store.record_audit(
            LinkAudit(
                email_account_id=account.id,
                thread_id=thread.id,
                method="manual",
                score=None,
                job_posting_id=None,
                actor=user_id,
                created_at=self.clock(),
            )
        )
        return self._thread_json(updated)

    def templates(self) -> dict:
        return {"items": self.store.templates()}

    def refresh(self, user_id: str) -> dict:
        account = self._require_mailbox(user_id)
        if isinstance(self.graph, LocalGraphClient):
            pending_id = f"pending-{account.id[:8]}"
            if self.store.get_by_graph_id(account.id, pending_id) is None:
                self.graph.seed_pending(account.id, pending_followup(account.id, account.address))
        self.queue.enqueue(get_app_settings().mail_ingest_queue, {"kind": "poll", "accountId": account.id, "userId": user_id})
        self.drain()
        status = self.status(user_id)
        return {"status": "ok", **status}

    def ensure_graph_subscription(self, user_id: str) -> GraphSubscription | None:
        account = self._require_mailbox(user_id)
        create = getattr(self.graph, "create_subscription", None)
        if not callable(create):
            return None
        existing = self.store.get_subscription(account.id)
        cfg = get_app_settings()
        notification_url = (getattr(cfg, "mail_webhook_public_url", None) or "").strip() or "https://localhost/api/webhooks/graph/mail"
        result = create(
            notification_url=notification_url,
            client_state=cfg.mail_webhook_client_state,
            existing_id=existing.graph_subscription_id if existing else None,
        )
        if not result:
            return existing
        now = self.clock()
        row = GraphSubscription(
            email_account_id=account.id,
            graph_subscription_id=str(result.get("id") or new_id()),
            resource=str(result.get("resource") or "/me/messages"),
            expires_at=str(result.get("expirationDateTime") or result.get("expires_at") or now),
            client_state=cfg.mail_webhook_client_state,
            created_at=existing.created_at if existing else now,
        )
        saved = self.store.upsert_subscription(row)
        try:
            settings_store = self._settings_store()
            if settings_store is not None:
                connections = settings_store.list_connections(user_id)
                if connections:
                    connection = connections[0]
                    connection.webhook_subscription_id = saved.graph_subscription_id
                    connection.subscription_expires_at = saved.expires_at
                    connection.updated_at = now
                    settings_store.upsert_connection(user_id, connection, actor_id=user_id)
        except Exception:
            log.exception("ajas.mail.subscription settings link failed")
        return saved

    def handle_webhook(self, *, validation_token: str | None, payload: dict | None, client_state: str | None) -> tuple[int, str | dict]:
        if validation_token:
            return 200, validation_token
        expected = get_app_settings().mail_webhook_client_state
        notifications = (payload or {}).get("value") or []
        if not notifications:
            raise MailValidationError("notification payload required")
        for item in notifications:
            state = item.get("clientState") or client_state
            if state != expected:
                raise MailUnauthorizedError("invalid webhook clientState")
            resource = item.get("resourceData") or {}
            graph_id = resource.get("id")
            self.queue.enqueue(
                get_app_settings().mail_ingest_queue,
                {
                    "kind": "webhook",
                    "graphMessageId": graph_id,
                    "subscriptionId": item.get("subscriptionId"),
                    "changeType": item.get("changeType") or "created",
                },
            )
        self.drain()
        return 202, {"status": "accepted"}

    def drain(self) -> None:
        cfg = get_app_settings()
        if not hasattr(self.queue, "pop_all"):
            return
        while True:
            messages = self.queue.pop_all(cfg.mail_ingest_queue)
            if not messages:
                break
            for payload in messages:
                self.process_ingest(payload)

    def process_ingest(self, payload: dict, dequeue_count: int = 1) -> None:
        kind = payload.get("kind") or "webhook"
        account = None
        if payload.get("accountId"):
            try:
                account = self.store.get_account(payload["accountId"])
            except MailNotFoundError:
                account = None
        if account is None and payload.get("userId"):
            account = self.store.get_account_for_user(payload["userId"])
        if account is None and payload.get("subscriptionId"):
            for item in self.store.list_accounts():
                sub = self.store.get_subscription(item.id)
                if sub and sub.graph_subscription_id == payload["subscriptionId"]:
                    account = item
                    break
        if account is None and payload.get("graphMessageId"):
            for item in self.store.list_accounts():
                if self.graph.fetch_message(item.id, payload["graphMessageId"]):
                    account = item
                    break
        if account is None:
            account = self.store.get_account_for_user("local-user")
        if account is None:
            log.info("ajas.mail.ingest skipped no-account")
            return
        if kind == "poll" or not payload.get("graphMessageId"):
            cursor = self.store.get_cursor(account.id)
            messages, token = self.graph.delta(account.id, cursor.delta_token if cursor else None)
            self.store.upsert_cursor(
                GraphSyncCursor(email_account_id=account.id, mode="both", delta_token=token, updated_at=self.clock())
            )
            for item in messages:
                self._ingest_graph_message(account, item)
        else:
            fetched = self.graph.fetch_message(account.id, payload["graphMessageId"])
            if fetched is None and isinstance(self.graph, LocalGraphClient):
                return
            if fetched is None:
                log.info("ajas.mail.ingest skipped missing graph id=%s", payload.get("graphMessageId"))
                return
            self._ingest_graph_message(account, fetched)
        self.store.touch_sync(account.id)

    def poll_all(self) -> None:
        self.renew_expiring_subscriptions()
        for account in self.store.list_accounts():
            self.process_ingest({"kind": "poll", "accountId": account.id, "userId": account.user_id})

    def renew_expiring_subscriptions(self) -> None:
        now = parse_ts(self.clock())
        horizon = timedelta(hours=12)
        seen: set[str] = set()
        for account in self.store.list_accounts():
            if account.user_id in seen:
                continue
            seen.add(account.user_id)
            sub = self.store.get_subscription(account.id)
            if sub is None:
                if self._graph_connection(account.user_id) is None:
                    continue
                try:
                    self.ensure_graph_subscription(account.user_id)
                except Exception:
                    log.exception("ajas.mail.subscription create failed user_id=%s", account.user_id)
                continue
            try:
                expires = parse_ts(sub.expires_at)
            except Exception:
                expires = now
            if expires - now <= horizon:
                try:
                    self.ensure_graph_subscription(account.user_id)
                except Exception:
                    log.exception("ajas.mail.subscription renew failed user_id=%s", account.user_id)

    def _ingest_graph_message(self, account: EmailAccount, item: GraphMessage) -> None:
        if item.change_type == "deleted":
            existing = self.store.get_by_graph_id(account.id, item.id)
            if existing:
                existing.is_deleted = True
                existing.deleted_at = self.clock()
                self.store.upsert_message(existing)
            return
        if item.internet_message_id and self.store.get_by_internet_id(account.user_id, item.internet_message_id):
            log.info("ajas.mail.ingest deduped internetMessageId")
            return
        if self.store.get_by_graph_id(account.id, item.id):
            log.info("ajas.mail.ingest deduped graphMessageId")
            return
        if self.store.event_exists(account.id, graph_message_id=item.id, internet_message_id=item.internet_message_id):
            return
        existing_thread = self.store.get_thread_by_conversation(account.id, item.conversation_id)
        referenced = None
        for header in [item.in_reply_to, *item.references]:
            if not header:
                continue
            found = self.store.get_by_internet_id(account.user_id, header)
            if found:
                referenced = self.store.get_thread(found.email_thread_id)
                break
        inbound = EmailMessage(
            email_account_id=account.id,
            email_thread_id=existing_thread.id if existing_thread else new_id(),
            user_id=account.user_id,
            graph_message_id=item.id,
            internet_message_id=item.internet_message_id or f"<missing-{item.id}@graph>",
            conversation_id=item.conversation_id,
            in_reply_to=item.in_reply_to,
            references=item.references,
            from_address=item.from_address,
            from_name=item.from_name,
            to_addresses=item.to_addresses,
            cc_addresses=item.cc_addresses,
            subject=item.subject,
            body_text=item.body_text,
            body_html=item.body_html,
            received_at=item.received_at or self.clock(),
            is_incoming=item.from_address != account.address,
            is_read=item.is_read,
            delivery_status="received",
            has_attachments=bool(item.attachments),
            etag=item.etag,
            created_at=self.clock(),
            updated_at=self.clock(),
        )
        bounce = classify_delivery(item.from_address, item.subject, item.body_text)
        if bounce:
            inbound.delivery_status = bounce
        decision = decide_link(
            inbound,
            existing_thread=existing_thread,
            referenced_thread=referenced,
            jobs=self._jobs(),
            auto_threshold=get_app_settings().mail_link_auto_threshold,
        )
        now = self.clock()
        if existing_thread:
            thread = existing_thread
        else:
            thread = EmailThread(
                id=inbound.email_thread_id,
                email_account_id=account.id,
                user_id=account.user_id,
                graph_conversation_id=item.conversation_id,
                subject=item.subject,
                last_message_at=inbound.received_at,
                snippet=snippet_of(item.body_text),
                participants=[item.from_address, *item.to_addresses],
                created_at=now,
                updated_at=now,
            )
            duplicate = self._thread_by_fingerprint(account.id, thread.subject, thread.participants)
            if duplicate:
                thread = duplicate
                inbound.email_thread_id = duplicate.id
            else:
                thread = self.store.upsert_thread(thread)
        if decision.job:
            thread = self.store.link_thread(
                thread.id,
                job_posting_id=decision.job.id,
                job_title=decision.job.title,
                job_company=decision.job.company,
                source=decision.source or "auto",
                confidence=decision.confidence,
            )
            self.store.record_audit(
                LinkAudit(
                    email_account_id=account.id,
                    thread_id=thread.id,
                    message_id=inbound.id,
                    method=decision.source or "auto",  # type: ignore[arg-type]
                    score=decision.score,
                    job_posting_id=decision.job.id,
                    actor="system",
                    created_at=now,
                )
            )
        inbound.email_thread_id = thread.id
        inbound.body_hash = body_hash(inbound.body_text, inbound.body_html)
        saved = self.store.upsert_message(inbound)
        for kind, addr in [("from", item.from_address), *[("to", addr) for addr in item.to_addresses]]:
            self.store.add_recipient(
                EmailRecipient(email_account_id=account.id, email_message_id=saved.id, kind=kind, address=addr)
            )
        self._store_attachments(saved, item.attachments, incoming=True)
        self.store.record_event(
            EmailIngestionEvent(
                email_account_id=account.id,
                graph_message_id=item.id,
                internet_message_id=item.internet_message_id,
                status="persisted",
                detail={"linked": bool(decision.job), "ambiguous": decision.ambiguous},
                created_at=now,
            )
        )
        log.info(
            "ajas.mail.ingest persisted message_id=%s thread_id=%s snippet=%s",
            saved.id,
            thread.id,
            redact_pii(inbound.snippet or snippet_of(inbound.body_text)),
        )

    def _store_attachments(self, message: EmailMessage, attachments: list[GraphAttachment], *, incoming: bool) -> None:
        cfg = get_app_settings()
        total = 0
        for item in attachments:
            total += item.size
            status = "stored"
            reason = None
            blob_path = None
            digest = None
            if item.size > cfg.mail_attachment_max_file_bytes or total > cfg.mail_attachment_max_message_bytes:
                status = "skipped_oversize"
                reason = "oversize"
            elif item.content:
                from app.mail.scan import scan_attachment

                scan = scan_attachment(item.content, file_name=item.name)
                if not scan.clean:
                    status = "skipped_scan"
                    reason = scan.reason
                else:
                    digest = sha256_text(item.content.hex())
                    blob_path = f"/users/{message.user_id}/messages/{message.id}/{item.name}"
                    self.store.put_blob(blob_path, item.content)
            self.store.add_attachment(
                EmailAttachment(
                    email_account_id=message.email_account_id,
                    email_message_id=message.id,
                    user_id=message.user_id,
                    file_name=item.name,
                    size=item.size,
                    content_type=item.content_type,
                    sha256=digest,
                    blob_path=blob_path,
                    is_inline=item.is_inline,
                    content_id=item.content_id,
                    status=status,
                    skip_reason=reason,
                )
            )
        if attachments:
            message.has_attachments = True
            self.store.upsert_message(message)

    def _validate_outgoing_attachments(self, rows: list[dict]) -> list[GraphAttachment]:
        cfg = get_app_settings()
        if len(rows) > 20:
            raise MailUnprocessableError("at most 20 attachments", path="attachments")
        total = 0
        out: list[GraphAttachment] = []
        for idx, row in enumerate(rows):
            name = row.get("fileName") or row.get("name") or "file"
            size = int(row.get("size") or 0)
            content_b64 = row.get("contentBase64") or ""
            content = base64.b64decode(content_b64) if content_b64 else b""
            if content:
                size = len(content)
            total += size
            if size > cfg.mail_attachment_max_file_bytes:
                raise MailUnprocessableError(f"{name} exceeds 10 MB", path=f"attachments/{idx}")
            if total > cfg.mail_attachment_max_message_bytes:
                raise MailUnprocessableError("attachments exceed 25 MB", path="attachments")
            if content:
                from app.mail.scan import scan_attachment

                scan = scan_attachment(content, file_name=str(name))
                if not scan.clean:
                    raise MailUnprocessableError(
                        f"{name} failed malware scan ({scan.reason})",
                        path=f"attachments/{idx}",
                    )
            out.append(
                GraphAttachment(
                    name=name,
                    content_type=row.get("contentType") or "application/octet-stream",
                    size=size,
                    content=content,
                )
            )
        return out

    def _status_json(self, account: EmailAccount | None, connection) -> dict:
        graph_ok = connection is not None
        demo = bool(account and account.demo and not graph_ok)
        if account is None:
            return {
                "connected": False,
                "graphConnected": False,
                "address": None,
                "lastSyncedAt": None,
                "unreadCount": 0,
                "demo": False,
                "provider": None,
                "oauthConfigured": microsoft_oauth_configured(),
            }
        threads = self.store.list_threads(account.id) if graph_ok or demo else []
        if graph_ok:
            address = connection.account_email or account.address
            provider = "microsoft365"
        elif demo:
            address = account.address
            provider = "demo"
        else:
            address = None
            provider = None
        return {
            "connected": graph_ok,
            "graphConnected": graph_ok,
            "address": address,
            "lastSyncedAt": account.last_synced_at if graph_ok or demo else None,
            "unreadCount": sum(item.unread_count for item in threads) if graph_ok or demo else 0,
            "demo": demo,
            "provider": provider,
            "lastSyncError": account.last_sync_error if graph_ok or demo else None,
            "oauthConfigured": microsoft_oauth_configured(),
        }

    def _settings_store(self):
        if self.settings_store is not None:
            return self.settings_store
        try:
            from app.settings.runtime import try_get_service

            svc = try_get_service()
            if svc is not None:
                return svc.store
        except Exception:
            return None
        return None

    def _graph_connection(self, user_id: str):
        store = self._settings_store()
        if store is None:
            return None
        try:
            active = store.get_active_connection(user_id)
            if active is not None:
                return active
            expired = [
                row
                for row in store.list_connections(user_id)
                if row.provider == "microsoft_365" and row.status == "expired" and row.refresh_token_enc
            ]
            return expired[0] if expired else None
        except Exception:
            return None

    def _mailbox(self, user_id: str, *, create_demo: bool) -> EmailAccount | None:
        connection = self._graph_connection(user_id)
        account = self.store.get_account_for_user(user_id)
        if account:
            return account
        if connection is not None:
            return self.store.ensure_account(
                user_id, address=connection.account_email or user_id, demo=False
            )
        if not create_demo:
            return None
        jobs = [{"id": job.id, "title": job.title, "company": job.company} for job in self._jobs()]
        return self.store.seed_demo_mailbox(user_id, jobs=jobs)

    def _require_mailbox(self, user_id: str) -> EmailAccount:
        account = self._mailbox(user_id, create_demo=self.local_mode)
        if account is None:
            raise MailUnauthorizedError("mailbox is not connected")
        return account

    def _owned_thread(self, account: EmailAccount, thread_id: str) -> EmailThread:
        try:
            thread = self.store.get_thread(thread_id)
        except MailNotFoundError as exc:
            raise MailNotFoundError(thread_id) from exc
        if thread.email_account_id != account.id or thread.user_id != account.user_id:
            raise MailForbiddenError("thread is not in this mailbox")
        return thread

    def _jobs(self) -> list[JobHint]:
        try:
            from app.job_sources.feed import feed_cards, seed_demo_feed
            from app.job_sources.store import get_job_source_store

            store = get_job_source_store()
            seed_demo_feed(store)
            hints: list[JobHint] = []
            for card in feed_cards(store):
                title = card.get("title") or ""
                company = card.get("company") or ""
                tokens = [title, company]
                contacts: list[str] = []
                if "staff engineer" in title.lower():
                    tokens.append("JOB-SE-1")
                    contacts.append("maya@acme.test")
                if "data analyst" in title.lower():
                    contacts.append("priya@globex.test")
                hints.append(JobHint(id=card["id"], title=title, company=company, contacts=contacts, tokens=tokens))
            return hints
        except Exception:
            return []

    def purge_expired(self, *, user_id: str | None = None) -> dict:
        days = get_app_settings().mail_retention_days
        cutoff = parse_ts(self.clock()) - timedelta(days=days)
        purged = 0
        accounts = []
        if user_id:
            try:
                accounts = [self._require_mailbox(user_id)]
            except Exception:
                accounts = []
        else:
            try:
                accounts = list(getattr(self.store, "_accounts", {}).values())
            except Exception:
                accounts = []
        for account in accounts:
            for thread in self.store.list_threads(account.id):
                for message in self.store.list_messages(thread.id):
                    stamp = parse_ts(message.received_at or message.created_at)
                    if stamp >= cutoff:
                        continue
                    if message.body_text and message.body_text != "[redacted]":
                        message.body_text = "[redacted]"
                        message.body_html = None
                        message.snippet = redact_pii(message.snippet)
                        self.store.upsert_message(message)
                        purged += 1
        return {"purged": purged, "retentionDays": days}

    def _merge_thread_views(self, rows: list) -> list:
        groups: dict[tuple, list] = {}
        order: list[tuple] = []
        for row in rows:
            key = thread_fingerprint(row.subject, row.participants)
            if key not in groups:
                order.append(key)
            groups.setdefault(key, []).append(row)
        merged = []
        for key in order:
            items = groups[key]
            items.sort(key=lambda item: item.last_message_at, reverse=True)
            primary = items[0]
            if len(items) > 1:
                primary = primary.model_copy(
                    update={"unread_count": sum(item.unread_count for item in items)}
                )
            merged.append(primary)
        return merged

    def _thread_by_fingerprint(self, account_id: str, subject: str, participants: list[str]):
        wanted = thread_fingerprint(subject, participants)
        for row in self.store.list_threads(account_id):
            if thread_fingerprint(row.subject, row.participants) == wanted:
                return row
        return None

    def _delivery_alert(self, thread) -> str | None:
        try:
            messages = self.store.list_messages(thread.id)
        except Exception:
            return None
        for message in messages:
            if message.delivery_status in {"bounced", "failed"}:
                return "bounced"
            if message.delivery_status == "deferred":
                return "deferred"
        return None

    def _thread_json(self, thread: EmailThread) -> dict:
        alert = self._delivery_alert(thread)
        return {
            "id": thread.id,
            "subject": thread.subject,
            "jobId": thread.job_posting_id,
            "applicationId": thread.application_id,
            "jobTitle": thread.job_title,
            "jobCompany": thread.job_company,
            "linked": bool(thread.job_posting_id or thread.application_id),
            "linkSource": thread.link_source,
            "linkConfidence": thread.link_confidence,
            "lastMessageAt": thread.last_message_at,
            "unreadCount": thread.unread_count,
            "snippet": thread.snippet,
            "participants": thread.participants,
            "deliveryAlert": alert,
            "canonical": True,
        }

    def _message_json(self, message: EmailMessage) -> dict:
        attachments = [
            {
                "id": item.id,
                "fileName": item.file_name,
                "size": item.size,
                "contentType": item.content_type,
                "status": item.status,
                "skipReason": item.skip_reason,
                "blobPath": item.blob_path,
                "downloadUrl": f"/api/v1/email/attachments/{item.id}" if item.status == "stored" and item.blob_path else None,
            }
            for item in self.store.list_attachments(message.id)
        ]
        return {
            "id": message.id,
            "threadId": message.email_thread_id,
            "from": {"address": message.from_address, "name": message.from_name},
            "to": message.to_addresses,
            "cc": message.cc_addresses,
            "subject": message.subject,
            "bodyText": message.body_text,
            "bodyHtml": message.body_html,
            "receivedAt": message.received_at,
            "sentAt": message.sent_at,
            "isIncoming": message.is_incoming,
            "isRead": message.is_read,
            "deliveryStatus": message.delivery_status,
            "hasAttachments": message.has_attachments,
            "attachments": attachments,
        }

    def _idempotency_id(self, user_id: str, thread_id: str, key: str) -> str:
        return f"{user_id}:{thread_id}:{key}"

    def _expired(self, created_at: str, *, hours: int) -> bool:
        return self.clock() > (parse_ts(created_at) + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
