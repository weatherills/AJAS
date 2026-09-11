"""Settings application service (Backend PRD)."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from app.config import get_settings as get_app_settings
from app.config import microsoft_oauth_configured
from app.settings.crypto import open_token, seal_token
from app.settings.errors import SettingsConflictError, SettingsNotFoundError, SettingsValidationError
from app.settings.mapping import api_threshold, db_threshold, requested_at, settings_response
from app.settings.models import EmailConnection, new_id
from app.settings.oauth import (
    GraphError,
    TokenExchanger,
    authorize_url,
    new_state,
    pkce_pair,
)
from app.settings.queues import InMemoryJobQueue, JobQueue
from app.settings.store import SettingsStore, get_settings_store
from app.settings.validation import parse_ts, utc_now


class SettingsRateLimitedError(Exception):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message)


class SettingsOAuthNotConfiguredError(Exception):
    def __init__(self, message: str = "Microsoft OAuth is not configured"):
        super().__init__(message)


class SettingsSourceNotConfiguredError(Exception):
    def __init__(self, source_id: str):
        from app.job_sources.service import source_not_configured_message

        self.source_id = source_id
        super().__init__(source_not_configured_message(source_id))


class SettingsService:
    def __init__(
        self,
        store: SettingsStore | None = None,
        queue: JobQueue | None = None,
        exchanger: TokenExchanger | None = None,
    ) -> None:
        self.store = store or get_settings_store()
        self.queue = queue or InMemoryJobQueue()
        self.exchanger = exchanger
        self._oauth: dict[str, dict] = {}
        self._writes: dict[str, deque[datetime]] = defaultdict(deque)
        self._connects: dict[str, deque[datetime]] = defaultdict(deque)

    def get(self, user_id: str) -> dict:
        settings = self.store.get_or_create_settings(user_id, actor_id=user_id)
        connection = self._visible_connection(user_id)
        return settings_response(settings, connection, updated_by=self._last_actor(user_id, settings.id))

    def patch(self, user_id: str, body: dict) -> dict:
        self._hit_write(user_id)
        if not isinstance(body, dict):
            raise SettingsValidationError("JSON object required")
        sources = body.get("sources")
        if sources is None:
            sources = {}
        if "sources" in body and not isinstance(sources, dict):
            raise SettingsValidationError("sources must be an object", path="sources")
        extra = set(sources) - {"greenhouseEnabled", "leverEnabled"}
        if extra:
            raise SettingsValidationError(f"Unknown source key: {sorted(extra)[0]}", path="sources")

        settings = self.store.get_or_create_settings(user_id, actor_id=user_id)
        old_threshold = api_threshold(settings.match_threshold)
        old_gh = settings.greenhouse_enabled
        old_lv = settings.lever_enabled
        self._reject_unconfigured_enable(sources)

        kwargs: dict = {"actor_id": user_id, "expected_version": settings.version}
        if "autoApplyEnabled" in body:
            if not isinstance(body["autoApplyEnabled"], bool):
                raise SettingsValidationError("autoApplyEnabled must be a boolean", path="autoApplyEnabled")
            kwargs["auto_apply_enabled"] = body["autoApplyEnabled"]
        if "matchThreshold" in body:
            kwargs["match_threshold"] = db_threshold(body["matchThreshold"])
        if "greenhouseEnabled" in sources:
            if not isinstance(sources["greenhouseEnabled"], bool):
                raise SettingsValidationError("greenhouseEnabled must be a boolean", path="sources/greenhouseEnabled")
            kwargs["greenhouse_enabled"] = sources["greenhouseEnabled"]
        if "leverEnabled" in sources:
            if not isinstance(sources["leverEnabled"], bool):
                raise SettingsValidationError("leverEnabled must be a boolean", path="sources/leverEnabled")
            kwargs["lever_enabled"] = sources["leverEnabled"]

        updated = self._patch_with_retry(user_id, kwargs)
        cfg = get_app_settings()
        new_threshold = api_threshold(updated.match_threshold)
        if "matchThreshold" in body and new_threshold != old_threshold:
            self.queue.enqueue(
                cfg.match_recalc_queue,
                {
                    "userId": user_id,
                    "oldThreshold": old_threshold,
                    "newThreshold": new_threshold,
                    "requestedAt": requested_at(),
                },
            )
        if updated.greenhouse_enabled and not old_gh:
            self.queue.enqueue(cfg.source_discovery_queue, {"userId": user_id, "source": "greenhouse"})
        if updated.lever_enabled and not old_lv:
            self.queue.enqueue(cfg.source_discovery_queue, {"userId": user_id, "source": "lever"})
        if "matchThreshold" in body and new_threshold != old_threshold:
            self.apply_match_recalc({"userId": user_id, "newThreshold": new_threshold})
        if "greenhouseEnabled" in sources or "leverEnabled" in sources:
            self.apply_source_discovery(
                {
                    "userId": user_id,
                    "greenhouseEnabled": updated.greenhouse_enabled,
                    "leverEnabled": updated.lever_enabled,
                    "crawlGreenhouse": bool(updated.greenhouse_enabled and not old_gh),
                    "crawlLever": bool(updated.lever_enabled and not old_lv),
                }
            )
        connection = self._visible_connection(user_id)
        return settings_response(updated, connection, updated_by=user_id)

    def connect(self, user_id: str, body: dict) -> dict:
        redirect_uri = (body or {}).get("redirectUri") if isinstance(body, dict) else None
        if not redirect_uri:
            raise SettingsValidationError("redirectUri is required", path="redirectUri")
        _validate_redirect(redirect_uri)
        if self.store.get_active_connection(user_id) is not None:
            return {"authUrl": None, "state": None, "noOp": True}
        cfg = get_app_settings()
        if not microsoft_oauth_configured(cfg):
            raise SettingsOAuthNotConfiguredError()
        self._hit_write(user_id)
        self._hit_connect(user_id)
        verifier, challenge = pkce_pair()
        state = new_state()
        now = utc_now()
        for existing in self.store.list_connections(user_id):
            if existing.status == "pending":
                self.store.revoke_connection(user_id, existing.id, actor_id=user_id)
        pending = EmailConnection(
            user_id=user_id,
            provider="microsoft_365",
            status="pending",
            access_token_enc=seal_token("pending-access", cfg.settings_token_key),
            refresh_token_enc=seal_token("pending-refresh", cfg.settings_token_key),
            created_at=now,
            updated_at=now,
        )
        pending = self.store.upsert_connection(user_id, pending, actor_id=user_id)
        self._oauth[state] = {
            "user_id": user_id,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            "connection_id": pending.id,
            "created_at": now,
        }
        url = authorize_url(
            tenant=cfg.microsoft_tenant,
            client_id=cfg.microsoft_client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=challenge,
        )
        return {"authUrl": url, "state": state, "noOp": False}

    def callback(self, user_id: str, body: dict) -> dict:
        self._hit_write(user_id)
        if not isinstance(body, dict):
            raise SettingsValidationError("JSON object required")
        code = body.get("code")
        state = body.get("state")
        redirect_uri = body.get("redirectUri")
        if not code or not state or not redirect_uri:
            raise SettingsValidationError("code, state, and redirectUri are required")
        session = self._oauth.get(state)
        if session is None or session["user_id"] != user_id:
            raise SettingsValidationError("Invalid or expired OAuth state", path="state")
        created = session["created_at"]
        age = (parse_ts(utc_now()) - parse_ts(created)).total_seconds()
        if age > 600:
            self._oauth.pop(state, None)
            raise SettingsValidationError("Invalid or expired OAuth state", path="state")
        if session["redirect_uri"] != redirect_uri:
            raise SettingsValidationError("redirectUri does not match the connect request", path="redirectUri")
        cfg = get_app_settings()
        exchanger = self.exchanger
        if exchanger is None:
            from app.settings.oauth import MicrosoftTokenExchanger

            exchanger = MicrosoftTokenExchanger(
                tenant=cfg.microsoft_tenant,
                client_id=cfg.microsoft_client_id,
                client_secret=cfg.microsoft_client_secret,
            )
        pending = None
        try:
            pending = self.store.get_connection(user_id, session["connection_id"])
        except SettingsNotFoundError:
            pending = None
        try:
            tokens = exchanger.exchange(
                code=code,
                redirect_uri=redirect_uri,
                code_verifier=session["code_verifier"],
            )
        except GraphError as exc:
            if pending is not None:
                pending.status = "error"
                pending.error_code = exc.code
                pending.updated_at = utc_now()
                self.store.upsert_connection(user_id, pending, actor_id=user_id)
            raise
        now = utc_now()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=int(tokens.expires_in or 3600))
        ).isoformat().replace("+00:00", "Z")
        scopes = tokens.scope.split() if tokens.scope else ["offline_access", "Mail.Read", "Mail.Send"]
        connection = EmailConnection(
            id=pending.id if pending else new_id(),
            user_id=user_id,
            provider="microsoft_365",
            status="active",
            account_email=tokens.account_id,
            tenant_id=tokens.tenant_id,
            account_id=tokens.account_id,
            scopes=scopes,
            access_token_enc=seal_token(tokens.access_token, cfg.settings_token_key),
            refresh_token_enc=seal_token(tokens.refresh_token, cfg.settings_token_key),
            expires_at=expires_at,
            last_verified_at=now,
            error_code=None,
            created_at=pending.created_at if pending else now,
            updated_at=now,
        )
        saved = self.store.upsert_connection(user_id, connection, actor_id=user_id)
        self._oauth.pop(state, None)
        try:
            from app.mail.runtime import get_service as get_email_service

            get_email_service().ensure_graph_subscription(user_id)
            settings_row = self.store.get_or_create_settings(user_id, actor_id=user_id)
            connections = self.store.list_connections(user_id)
            saved = connections[0] if connections else saved
            return settings_response(settings_row, saved, updated_by=user_id)
        except Exception:
            settings = self.store.get_or_create_settings(user_id, actor_id=user_id)
            return settings_response(settings, saved, updated_by=user_id)

    def disconnect(self, user_id: str) -> dict:
        self._hit_write(user_id)
        for connection in self.store.list_connections(user_id):
            if connection.status != "revoked":
                self.store.revoke_connection(user_id, connection.id, actor_id=user_id)
        settings = self.store.get_or_create_settings(user_id, actor_id=user_id)
        return settings_response(settings, None, updated_by=user_id)

    def graph_access_token(self, user_id: str) -> str:
        """Return a live Graph access token, refreshing when expiry is near."""
        connection = self.store.get_active_connection(user_id)
        if connection is None:
            expired = [
                row
                for row in self.store.list_connections(user_id)
                if row.provider == "microsoft_365" and row.status == "expired" and row.refresh_token_enc
            ]
            connection = expired[0] if expired else None
        if connection is None or not connection.access_token_enc:
            raise RuntimeError("no active Microsoft Graph token")
        cfg = get_app_settings()
        now = datetime.now(timezone.utc)
        expires = parse_ts(connection.expires_at) if connection.expires_at else None
        still_valid = (
            connection.status == "active"
            and expires is not None
            and expires - now > timedelta(minutes=2)
        )
        if still_valid:
            token = open_token(connection.access_token_enc, cfg.settings_token_key)
            if token:
                return token
        refresh = open_token(connection.refresh_token_enc, cfg.settings_token_key)
        if not refresh:
            raise RuntimeError("no refresh token")
        exchanger = self.exchanger
        refresh_fn = getattr(exchanger, "refresh", None) if exchanger is not None else None
        if not callable(refresh_fn):
            from app.settings.oauth import MicrosoftTokenExchanger

            exchanger = MicrosoftTokenExchanger(
                tenant=cfg.microsoft_tenant,
                client_id=cfg.microsoft_client_id,
                client_secret=cfg.microsoft_client_secret,
            )
            refresh_fn = exchanger.refresh
        tokens = refresh_fn(refresh_token=refresh)
        stamped = utc_now()
        connection.status = "active"
        connection.access_token_enc = seal_token(tokens.access_token, cfg.settings_token_key)
        if tokens.refresh_token:
            connection.refresh_token_enc = seal_token(tokens.refresh_token, cfg.settings_token_key)
        connection.expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=int(tokens.expires_in or 3600))
        ).isoformat().replace("+00:00", "Z")
        connection.updated_at = stamped
        connection.last_verified_at = stamped
        connection.error_code = None
        self.store.upsert_connection(user_id, connection, actor_id=user_id)
        return tokens.access_token

    def _visible_connection(self, user_id: str) -> EmailConnection | None:
        rows = self.store.list_connections(user_id)
        for status in ("active", "pending", "error", "expired"):
            for row in rows:
                if row.status == status:
                    return row
        return None

    def _last_actor(self, user_id: str, entity_id: str) -> str | None:
        entries = self.store.list_audit(user_id, entity_id=entity_id)
        return entries[0].actor_id if entries else None

    def list_audit(self, user_id: str) -> dict:
        entries = self.store.list_audit(user_id)
        return {
            "items": [
                {
                    "id": entry.id,
                    "entityType": entry.entity_type,
                    "entityId": entry.entity_id,
                    "actorId": entry.actor_id,
                    "fieldMask": entry.field_mask,
                    "detail": entry.detail,
                    "createdAt": entry.created_at,
                }
                for entry in entries
            ]
        }

    def _patch_with_retry(self, user_id: str, kwargs: dict):
        last_error: Exception | None = None
        for _ in range(3):
            try:
                return self.store.update_settings(user_id, **kwargs)
            except SettingsConflictError as exc:
                last_error = exc
                current = self.store.get_or_create_settings(user_id, actor_id=user_id)
                kwargs["expected_version"] = current.version
        assert last_error is not None
        raise last_error

    def _hit_write(self, user_id: str) -> None:
        self._hit(self._writes[user_id], get_app_settings().settings_write_rate_per_minute)

    def _hit_connect(self, user_id: str) -> None:
        self._hit(self._connects[user_id], get_app_settings().settings_connect_rate_per_minute)

    def _hit(self, bucket: deque[datetime], limit: int) -> None:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=1)
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            raise SettingsRateLimitedError("Rate limit exceeded")
        bucket.append(now)

    def apply_match_recalc(self, payload: dict) -> None:
        user_id = payload.get("userId") or payload.get("user_id")
        raw = payload.get("newThreshold")
        if not user_id or raw is None:
            return
        try:
            pct = int(round(float(raw) * 100)) if float(raw) <= 1 else int(round(float(raw)))
        except (TypeError, ValueError):
            return
        try:
            from app.matching.runtime import try_get_service as try_matching
            from app.matching.store import get_matching_store

            service = try_matching()
            store = service.store if service is not None else get_matching_store()
            store.update_prefs(user_id, threshold_pct=max(0, min(100, pct)))
        except Exception:
            pass

    def _reject_unconfigured_enable(self, sources: dict) -> None:
        if sources.get("greenhouseEnabled") is not True and sources.get("leverEnabled") is not True:
            return
        try:
            from app.job_sources.runtime import tenant_counts_or_none

            counts = tenant_counts_or_none()
        except Exception:
            counts = None
        if counts is None:
            return
        if sources.get("greenhouseEnabled") is True and counts.get("greenhouse", 0) == 0:
            raise SettingsSourceNotConfiguredError("greenhouse")
        if sources.get("leverEnabled") is True and counts.get("lever", 0) == 0:
            raise SettingsSourceNotConfiguredError("lever")

    def apply_source_discovery(self, payload: dict) -> None:
        try:
            from app.job_sources.runtime import try_get_service

            service = try_get_service()
            if service is None:
                return
            greenhouse = payload.get("greenhouseEnabled")
            lever = payload.get("leverEnabled")
            if greenhouse is None and payload.get("source") == "greenhouse":
                greenhouse = True
            if lever is None and payload.get("source") == "lever":
                lever = True
            if greenhouse is not None:
                for tenant in service.store.list_tenants("greenhouse"):
                    service.store.upsert_tenant(
                        "greenhouse",
                        tenant.tenant_key,
                        config=tenant.config,
                        enabled=bool(greenhouse),
                    )
            if lever is not None:
                for tenant in service.store.list_tenants("lever"):
                    service.store.upsert_tenant(
                        "lever",
                        tenant.tenant_key,
                        config=tenant.config,
                        enabled=bool(lever),
                    )
            if payload.get("crawlGreenhouse"):
                try:
                    service.enqueue_crawl("greenhouse")
                    service.drain()
                except Exception:
                    pass
            if payload.get("crawlLever"):
                try:
                    service.enqueue_crawl("lever")
                    service.drain()
                except Exception:
                    pass
        except Exception:
            pass


def _validate_redirect(uri: str) -> None:
    parsed = urlparse(uri)
    if parsed.scheme not in {"https", "http"}:
        raise SettingsValidationError("redirectUri must be http(s)", path="redirectUri")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise SettingsValidationError("http redirectUri is only allowed for localhost", path="redirectUri")
