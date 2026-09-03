"""Resume Management Database PRD — schema, constraints, and store behaviors."""

from __future__ import annotations

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.resumes import (
    InMemoryResumeStore,
    ResumeContact,
    ResumeEducation,
    ResumeExperience,
    ResumeNotFoundError,
    ResumeSelectionRejectedError,
    ResumeSkill,
    ResumeValidationError,
    StructuredResume,
    container_specs,
    library_preview,
)
from app.resumes.constants import (
    EVENTS_CONTAINER,
    EVENTS_PARTITION_KEY,
    RESUMES_CONTAINER,
    RESUMES_INDEXING_POLICY,
    RESUMES_PARTITION_KEY,
    SELECTIONS_CONTAINER,
    SELECTIONS_PARTITION_KEY,
)
from app.resumes.cosmos_store import CosmosResumeStore
from app.resumes.models import new_id
from app.resumes.validation import utc_now


PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
USER = "user-1"
OTHER = "user-2"


def _not_found() -> CosmosResourceNotFoundError:
    return CosmosResourceNotFoundError(status_code=404, message="not found")


class FakeContainer:
    def __init__(self, pk_field: str) -> None:
        self.pk_field = pk_field
        self.items: dict[tuple[str, str], dict] = {}

    def create_item(self, body: dict) -> dict:
        key = (body[self.pk_field], body["id"])
        if key in self.items:
            raise ValueError(f"conflict {key}")
        stored = dict(body)
        self.items[key] = stored
        return dict(stored)

    def read_item(self, item: str, partition_key: str) -> dict:
        key = (partition_key, item)
        if key not in self.items:
            raise _not_found()
        return dict(self.items[key])

    def replace_item(self, item: str, body: dict) -> dict:
        key = (body[self.pk_field], item if isinstance(item, str) else item["id"])
        if key not in self.items:
            raise _not_found()
        self.items[key] = dict(body)
        return dict(body)

    def upsert_item(self, body: dict) -> dict:
        key = (body[self.pk_field], body["id"])
        self.items[key] = dict(body)
        return dict(body)

    def query_items(self, query: str, parameters=None, partition_key=None, **_kwargs):
        params = {p["name"]: p["value"] for p in (parameters or [])}
        rows = [dict(v) for v in self.items.values()]
        if partition_key is not None:
            rows = [r for r in rows if r.get(self.pk_field) == partition_key]
        if params.get("@include_deleted") is False:
            rows = [r for r in rows if not r.get("is_deleted")]
        if "ORDER BY c.updated_at DESC" in query:
            rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        if "ORDER BY c.created_at DESC" in query:
            rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return rows


class FakeDatabase:
    def __init__(self) -> None:
        self._containers = {
            RESUMES_CONTAINER: FakeContainer("user_id"),
            SELECTIONS_CONTAINER: FakeContainer("run_id"),
            EVENTS_CONTAINER: FakeContainer("resume_id"),
        }
        self.created: list[dict] = []

    def get_container_client(self, name: str) -> FakeContainer:
        return self._containers[name]

    def create_container_if_not_exists(self, **kwargs) -> None:
        self.created.append(kwargs)


@pytest.fixture(params=["memory", "cosmos"])
def store(request):
    if request.param == "memory":
        return InMemoryResumeStore()
    return CosmosResumeStore(FakeDatabase())


def _upload(store, *, user_id=USER, filename="cv.pdf", checksum="aaa", **kwargs):
    defaults = dict(
        user_id=user_id,
        original_filename=filename,
        mime_type=PDF,
        file_size=1024,
        blob_uri=f"https://blobs.example/{user_id}/{filename}",
        checksum_sha256=checksum,
        preview_blob_uri=f"https://blobs.example/{user_id}/{filename}.preview",
        text_preview="Jane Doe — engineer",
    )
    defaults.update(kwargs)
    return store.create_resume(**defaults)


def _skill(name: str, resume_id: str = "pending") -> ResumeSkill:
    return ResumeSkill(resume_id=resume_id, name=name, updated_at=utc_now())


def _experience(**kwargs) -> ResumeExperience:
    payload = dict(
        resume_id="pending",
        title="Engineer",
        company="Acme",
        start_date="2020-01",
        end_date="2021-06",
        updated_at=utc_now(),
    )
    payload.update(kwargs)
    return ResumeExperience(**payload)


def _snapshot(*, skills=None, experiences=None, educations=None, contact=None) -> StructuredResume:
    return StructuredResume(
        contact=contact,
        skills=skills or [],
        experiences=experiences or [],
        educations=educations or [],
    )


def test_container_specs_match_prd():
    specs = {spec["id"]: spec for spec in container_specs()}
    assert set(specs) == {RESUMES_CONTAINER, SELECTIONS_CONTAINER, EVENTS_CONTAINER}
    assert specs[RESUMES_CONTAINER]["partition_key"] == RESUMES_PARTITION_KEY
    assert specs[SELECTIONS_CONTAINER]["partition_key"] == SELECTIONS_PARTITION_KEY
    assert specs[EVENTS_CONTAINER]["partition_key"] == EVENTS_PARTITION_KEY
    assert specs[RESUMES_CONTAINER]["indexing_policy"] == RESUMES_INDEXING_POLICY
    composite = specs[RESUMES_CONTAINER]["indexing_policy"]["compositeIndexes"][0]
    paths = [part["path"] for part in composite]
    assert paths == ["/user_id", "/is_deleted", "/updated_at"]


def test_ensure_resume_containers_creates_three():
    from app.resumes.containers import ensure_resume_containers

    db = FakeDatabase()
    ensure_resume_containers(db)
    assert {item["id"] for item in db.created} == {
        RESUMES_CONTAINER,
        SELECTIONS_CONTAINER,
        EVENTS_CONTAINER,
    }
    resumes = next(item for item in db.created if item["id"] == RESUMES_CONTAINER)
    assert resumes["partition_key"].path == "/user_id"


def test_upload_creates_uploaded_row_and_event(store):
    resume = _upload(store)
    assert resume.user_id == USER
    assert resume.processing_status == "uploaded"
    assert resume.is_deleted is False
    assert resume.validated is False
    assert resume.file_size == 1024
    loaded = store.get_resume(USER, resume.id)
    assert loaded.original_filename == "cv.pdf"
    events = store.list_parse_events(resume.id)
    assert [e.event_type for e in events] == ["uploaded"]


def test_upload_rejects_bad_mime_and_zero_size(store):
    with pytest.raises(ResumeValidationError) as mime_err:
        _upload(store, mime_type="text/plain")
    assert mime_err.value.path == "mime_type"
    with pytest.raises(ResumeValidationError) as size_err:
        _upload(store, file_size=0)
    assert size_err.value.path == "file_size"
    with pytest.raises(ResumeValidationError) as user_err:
        _upload(store, user_id="")
    assert user_err.value.path == "user_id"


def test_duplicate_checksum_is_allowed_and_flagged(store):
    first = _upload(store, checksum="same-hash")
    second = _upload(store, filename="cv-copy.pdf", checksum="same-hash")
    assert first.id != second.id
    types = [e.event_type for e in store.list_parse_events(second.id)]
    assert "uploaded" in types
    assert "duplicate_detected" in types
    dup = next(e for e in store.list_parse_events(second.id) if e.event_type == "duplicate_detected")
    assert dup.detail["existing_resume_id"] == first.id


def test_parse_lifecycle_updates_status_and_events(store):
    resume = _upload(store)
    store.record_status(USER, resume.id, "queued")
    store.record_status(USER, resume.id, "parsing")
    store.record_status(USER, resume.id, "failed", parsing_error="encrypted pdf")
    failed = store.get_resume(USER, resume.id)
    assert failed.processing_status == "failed"
    assert failed.parsing_error == "encrypted pdf"
    types = [e.event_type for e in store.list_parse_events(resume.id)]
    assert types == ["failed", "started", "queued", "uploaded"]


def test_parse_success_writes_children_and_validated(store):
    resume = _upload(store)
    snapshot = _snapshot(
        contact=ResumeContact(
            resume_id=resume.id,
            full_name="Jane Doe",
            email="jane@example.com",
            updated_at=utc_now(),
        ),
        skills=[_skill("Python"), _skill("Azure")],
        experiences=[_experience()],
    )
    parsed = store.record_parse_success(
        USER, resume.id, snapshot, parsing_confidence=88
    )
    assert parsed.processing_status == "parsed"
    assert parsed.parsed_at is not None
    assert parsed.validated is True
    assert parsed.validated_at is not None
    assert parsed.contact is not None
    assert parsed.contact.source == "parsed"
    assert [s.name for s in parsed.skills] == ["Python", "Azure"]
    assert [s.order_index for s in parsed.skills] == [0, 1]
    assert parsed.skills[0].parsing_confidence == 88
    assert store.list_parse_events(resume.id)[0].event_type == "succeeded"


def test_partial_parse_stays_unvalidated(store):
    resume = _upload(store)
    parsed = store.record_parse_success(USER, resume.id, _snapshot())
    assert parsed.processing_status == "parsed"
    assert parsed.validated is False
    assert parsed.skills == []
    assert parsed.contact is None


def test_date_and_current_constraints(store):
    resume = _upload(store)
    store.record_status(USER, resume.id, "failed", parsing_error="empty")
    with pytest.raises(ResumeValidationError):
        store.replace_structured_data(
            USER,
            resume.id,
            _snapshot(experiences=[_experience(start_date="2022-01", end_date="2020-01")]),
            last_edited_by=USER,
        )
    with pytest.raises(ResumeValidationError):
        store.replace_structured_data(
            USER,
            resume.id,
            _snapshot(
                experiences=[_experience(is_current=True, end_date="2024-01", start_date="2020-01")]
            ),
            last_edited_by=USER,
        )
    # Failed parse still allows a valid edit.
    edited = store.replace_structured_data(
        USER,
        resume.id,
        _snapshot(experiences=[_experience(is_current=True, end_date=None, start_date="2020-01")]),
        last_edited_by=USER,
    )
    assert edited.processing_status == "failed"
    assert edited.last_edited_by == USER
    assert edited.experiences[0].source == "manual"
    assert edited.validated is True


def test_one_contact_per_resume(store):
    resume = _upload(store)
    contact = ResumeContact(
        resume_id=resume.id,
        full_name="Jane",
        email="jane@example.com",
        updated_at=utc_now(),
    )
    parsed = store.record_parse_success(
        USER, resume.id, _snapshot(skills=[_skill("Go")], contact=contact)
    )
    assert parsed.contact is not None
    assert parsed.contact.email == "jane@example.com"
    replaced = store.replace_structured_data(
        USER,
        resume.id,
        _snapshot(
            skills=[_skill("Go")],
            contact=ResumeContact(
                resume_id=resume.id,
                full_name="Jane D",
                email="jane.d@example.com",
                updated_at=utc_now(),
            ),
        ),
        last_edited_by=USER,
    )
    assert replaced.contact.email == "jane.d@example.com"


def test_library_hides_deleted_and_orders_by_updated_at(store):
    older = _upload(store, filename="old.pdf", checksum="c1")
    newer = _upload(store, filename="new.pdf", checksum="c2")
    store.record_status(USER, older.id, "queued")
    listed = store.list_resumes(USER)
    assert [r.id for r in listed] == [older.id, newer.id]
    store.soft_delete(USER, older.id)
    assert [r.id for r in store.list_resumes(USER)] == [newer.id]
    including = store.list_resumes(USER, include_deleted=True)
    assert {r.id for r in including} == {older.id, newer.id}
    deleted = store.get_resume(USER, older.id)
    assert deleted.is_deleted is True
    assert deleted.deleted_at is not None
    preview = library_preview(deleted)
    assert preview.blob_uri is None
    assert preview.preview_blob_uri is None
    assert preview.text_preview == "Jane Doe — engineer"
    live = library_preview(store.get_resume(USER, newer.id))
    assert live.blob_uri is not None


def test_soft_delete_is_idempotent(store):
    resume = _upload(store)
    first = store.soft_delete(USER, resume.id)
    second = store.soft_delete(USER, resume.id)
    assert first.deleted_at == second.deleted_at
    assert [e.event_type for e in store.list_parse_events(resume.id)].count("deleted") == 1


def test_run_selection_is_one_per_run_and_rejects_invalid(store):
    ready = _upload(store, checksum="ready")
    store.record_parse_success(USER, ready.id, _snapshot(skills=[_skill("Python")]))
    other = _upload(store, checksum="other")
    store.record_parse_success(USER, other.id, _snapshot(skills=[_skill("Java")]))
    not_ready = _upload(store, checksum="queued")
    deleted = _upload(store, checksum="del")
    store.record_parse_success(USER, deleted.id, _snapshot(skills=[_skill("C")]))
    store.soft_delete(USER, deleted.id)

    first = store.set_run_selection(run_id="run-1", user_id=USER, resume_id=ready.id)
    assert first.id == "run-1"
    assert first.resume_id == ready.id
    replaced = store.set_run_selection(run_id="run-1", user_id=USER, resume_id=other.id)
    assert replaced.resume_id == other.id
    assert store.get_run_selection("run-1").resume_id == other.id

    with pytest.raises(ResumeSelectionRejectedError):
        store.set_run_selection(run_id="run-2", user_id=USER, resume_id=not_ready.id)
    with pytest.raises(ResumeSelectionRejectedError):
        store.set_run_selection(run_id="run-2", user_id=USER, resume_id=deleted.id)
    with pytest.raises(ResumeNotFoundError):
        store.set_run_selection(run_id="run-2", user_id=OTHER, resume_id=ready.id)


def test_deleting_active_resume_keeps_historical_selection(store):
    resume = _upload(store)
    store.record_parse_success(USER, resume.id, _snapshot(educations=[
        ResumeEducation(
            resume_id=resume.id,
            institution="MIT",
            start_date="2015-09",
            end_date="2019-06",
            updated_at=utc_now(),
        )
    ]))
    store.set_run_selection(run_id="run-keep", user_id=USER, resume_id=resume.id)
    store.soft_delete(USER, resume.id)
    historical = store.get_run_selection("run-keep")
    assert historical is not None
    assert historical.resume_id == resume.id
    with pytest.raises(ResumeSelectionRejectedError):
        store.set_run_selection(run_id="run-new", user_id=USER, resume_id=resume.id)


def test_cross_user_get_is_not_found(store):
    resume = _upload(store)
    with pytest.raises(ResumeNotFoundError):
        store.get_resume(OTHER, resume.id)
    assert store.list_resumes(OTHER) == []


def test_docx_is_accepted(store):
    resume = _upload(store, filename="cv.docx", mime_type=DOCX)
    assert resume.mime_type == DOCX


def test_invalid_processing_status_rejected(store):
    resume = _upload(store)
    with pytest.raises(ResumeValidationError):
        store.record_status(USER, resume.id, "parse_failed")  # type: ignore[arg-type]


def test_education_order_index_is_stable(store):
    resume = _upload(store)
    snapshot = _snapshot(
        educations=[
            ResumeEducation(
                resume_id=resume.id,
                institution="A",
                updated_at=utc_now(),
                order_index=99,
            ),
            ResumeEducation(
                resume_id=resume.id,
                institution="B",
                updated_at=utc_now(),
                order_index=99,
            ),
        ]
    )
    parsed = store.record_parse_success(USER, resume.id, snapshot)
    assert [e.institution for e in parsed.educations] == ["A", "B"]
    assert [e.order_index for e in parsed.educations] == [0, 1]


def test_new_id_is_unique():
    assert new_id() != new_id()
