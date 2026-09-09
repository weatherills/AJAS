"""Cosmos DB implementation of AutoApplyStore."""

from __future__ import annotations

from typing import Any

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.auto_apply.constants import (
    ATTEMPTS_CONTAINER,
    AUTOFILL_CONTAINER,
    COVERS_CONTAINER,
    EVENTS_CONTAINER,
    MAPPINGS_CONTAINER,
    PACKAGES_CONTAINER,
    SUBMITS_CONTAINER,
    VARIANTS_CONTAINER,
    WEBHOOKS_CONTAINER,
)
from app.auto_apply.memory import InMemoryAutoApplyStore
from app.auto_apply.models import (
    ApplyPackage,
    AutoApplyAttempt,
    CoverLetter,
    FormAutofillValue,
    ResumeVariant,
    StatusEvent,
    SubmitRequest,
    VendorFieldMapping,
    WebhookCallback,
)


class CosmosAutoApplyStore:
    def __init__(self, database: Any) -> None:
        self._attempts = database.get_container_client(ATTEMPTS_CONTAINER)
        self._packages = database.get_container_client(PACKAGES_CONTAINER)
        self._variants = database.get_container_client(VARIANTS_CONTAINER)
        self._covers = database.get_container_client(COVERS_CONTAINER)
        self._autofill = database.get_container_client(AUTOFILL_CONTAINER)
        self._mappings = database.get_container_client(MAPPINGS_CONTAINER)
        self._submits = database.get_container_client(SUBMITS_CONTAINER)
        self._events = database.get_container_client(EVENTS_CONTAINER)
        self._webhooks = database.get_container_client(WEBHOOKS_CONTAINER)

    def seed_default_mappings(self):
        working = self._hydrate()
        saved = working.seed_default_mappings()
        self._persist_working(working)
        return saved

    def create_attempt(self, user_id: str, **kwargs: Any):
        working = self._hydrate()
        saved = working.create_attempt(user_id, **kwargs)
        self._persist_working(working)
        return saved

    def get_attempt(self, attempt_id: str, *, user_id: str):
        return self._hydrate().get_attempt(attempt_id, user_id=user_id)

    def list_attempts(self, user_id: str, **kwargs: Any):
        return self._hydrate().list_attempts(user_id, **kwargs)

    def approve(self, user_id: str, attempt_id: str):
        working = self._hydrate()
        saved = working.approve(user_id, attempt_id)
        self._persist_working(working)
        return saved

    def queue(self, user_id: str, attempt_id: str):
        working = self._hydrate()
        saved = working.queue(user_id, attempt_id)
        self._persist_working(working)
        return saved

    def transition(self, user_id: str, attempt_id: str, status: str, **kwargs: Any):
        working = self._hydrate()
        saved = working.transition(user_id, attempt_id, status, **kwargs)
        self._persist_working(working)
        return saved

    def create_resume_variant(self, user_id: str, **kwargs: Any):
        working = self._hydrate()
        saved = working.create_resume_variant(user_id, **kwargs)
        self._persist_working(working)
        return saved

    def list_resume_variants(self, user_id: str):
        return self._hydrate().list_resume_variants(user_id)

    def create_cover_letter(self, user_id: str, **kwargs: Any):
        working = self._hydrate()
        saved = working.create_cover_letter(user_id, **kwargs)
        self._persist_working(working)
        return saved

    def put_package(self, user_id: str, auto_apply_id: str, **kwargs: Any):
        working = self._hydrate()
        saved = working.put_package(user_id, auto_apply_id, **kwargs)
        self._persist_working(working)
        return saved

    def get_package(self, auto_apply_id: str, *, user_id: str):
        return self._hydrate().get_package(auto_apply_id, user_id=user_id)

    def lock_package(self, user_id: str, auto_apply_id: str):
        working = self._hydrate()
        saved = working.lock_package(user_id, auto_apply_id)
        self._persist_working(working)
        return saved

    def put_autofill(self, user_id: str, auto_apply_id: str, **kwargs: Any):
        working = self._hydrate()
        saved = working.put_autofill(user_id, auto_apply_id, **kwargs)
        self._persist_working(working)
        return saved

    def list_autofill(self, user_id: str, auto_apply_id: str):
        return self._hydrate().list_autofill(user_id, auto_apply_id)

    def missing_required_fields(self, user_id: str, auto_apply_id: str):
        return self._hydrate().missing_required_fields(user_id, auto_apply_id)

    def put_vendor_mapping(self, **kwargs: Any):
        working = self._hydrate()
        saved = working.put_vendor_mapping(**kwargs)
        self._persist_working(working)
        return saved

    def list_vendor_mappings(self, vendor: str | None = None):
        return self._hydrate().list_vendor_mappings(vendor)

    def create_submit_request(self, user_id: str, auto_apply_id: str, **kwargs: Any):
        working = self._hydrate()
        saved = working.create_submit_request(user_id, auto_apply_id, **kwargs)
        self._persist_working(working)
        return saved

    def complete_submit(self, user_id: str, submit_id: str, **kwargs: Any):
        working = self._hydrate()
        saved = working.complete_submit(user_id, submit_id, **kwargs)
        self._persist_working(working)
        return saved

    def list_submits(self, user_id: str, auto_apply_id: str):
        return self._hydrate().list_submits(user_id, auto_apply_id)

    def list_status_events(self, user_id: str, auto_apply_id: str, **kwargs: Any):
        return self._hydrate().list_status_events(user_id, auto_apply_id, **kwargs)

    def ingest_webhook(self, **kwargs: Any):
        working = self._hydrate()
        saved = working.ingest_webhook(**kwargs)
        self._persist_working(working)
        return saved

    def list_webhooks(self, **kwargs: Any):
        return self._hydrate().list_webhooks(**kwargs)

    def _all_items(self, client: Any) -> list[dict]:
        try:
            return list(client.query_items(query="SELECT * FROM c", enable_cross_partition_query=True))
        except TypeError:
            return list(client.query_items(query="SELECT * FROM c"))

    def _hydrate(self) -> InMemoryAutoApplyStore:
        working = InMemoryAutoApplyStore(seed=False)
        working._attempts = {
            row.id: row for row in (AutoApplyAttempt.model_validate(item) for item in self._all_items(self._attempts))
        }
        working._packages = {
            row.id: row for row in (ApplyPackage.model_validate(item) for item in self._all_items(self._packages))
        }
        working._variants = {
            row.id: row for row in (ResumeVariant.model_validate(item) for item in self._all_items(self._variants))
        }
        working._covers = {
            row.id: row for row in (CoverLetter.model_validate(item) for item in self._all_items(self._covers))
        }
        working._autofill = {
            row.id: row for row in (FormAutofillValue.model_validate(item) for item in self._all_items(self._autofill))
        }
        working._mappings = {
            row.id: row for row in (VendorFieldMapping.model_validate(item) for item in self._all_items(self._mappings))
        }
        working._submits = {
            row.id: row for row in (SubmitRequest.model_validate(item) for item in self._all_items(self._submits))
        }
        working._events = {
            row.id: row for row in (StatusEvent.model_validate(item) for item in self._all_items(self._events))
        }
        working._webhooks = {
            row.id: row for row in (WebhookCallback.model_validate(item) for item in self._all_items(self._webhooks))
        }
        return working

    def _upsert(self, client: Any, payload: dict) -> None:
        try:
            client.replace_item(item=payload["id"], body=payload)
        except CosmosResourceNotFoundError:
            client.create_item(body=payload)

    def _persist_working(self, working: InMemoryAutoApplyStore) -> None:
        for row in working._attempts.values():
            self._upsert(self._attempts, row.model_dump())
        for row in working._packages.values():
            self._upsert(self._packages, row.model_dump())
        for row in working._variants.values():
            self._upsert(self._variants, row.model_dump())
        for row in working._covers.values():
            self._upsert(self._covers, row.model_dump())
        for row in working._autofill.values():
            self._upsert(self._autofill, row.model_dump())
        for row in working._mappings.values():
            self._upsert(self._mappings, row.model_dump())
        for row in working._submits.values():
            self._upsert(self._submits, row.model_dump())
        for row in working._events.values():
            self._upsert(self._events, row.model_dump())
        for row in working._webhooks.values():
            self._upsert(self._webhooks, row.model_dump())
