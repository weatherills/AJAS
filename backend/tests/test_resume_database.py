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
    CHILD_CONTAINERS,
    CHILDREN_INDEXING_POLICY,
    CHILDREN_PARTITION_KEY,
    CONTACTS_CONTAINER,
    CONTACTS_INDEXING_POLICY,
    EDUCATIONS_CONTAINER,
    EVENTS_CONTAINER,
    EVENTS_PARTITION_KEY,
    EXPERIENCES_CONTAINER,
    RESUMES_CONTAINER,
    RESUMES_INDEXING_POLICY,
    RESUMES_PARTITION_KEY,
    SELECTIONS_CONTAINER,
    SELECTIONS_PARTITION_KEY,
    SKILLS_CONTAINER,
    VERSIONS_CONTAINER,
    VERSIONS_PARTITION_KEY,
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

    def delete_item(self, item: str, partition_key: str) -> None:
        key = (partition_key, item if isinstance(item, str) else item["id"])
        self.items.pop(key, None)

    def query_items(self, query: str, parameters=None, partition_key=None, **_kwargs):
        params = {p["name"]: p["value"] for p in (parameters or [])}
        rows = [dict(v) for v in self.items.values()]
        if partition_key is not None:
            rows = [r for r in rows if r.get(self.pk_field) == partition_key]
        if "@user_id" in params and "c.user_id" in query:
            rows = [r for r in rows if r.get("user_id") == params["@user_id"]]
        if "@resume_id" in params and "c.resume_id" in query:
            rows = [r for r in rows if r.get("resume_id") == params["@resume_id"]]
        if params.get("@include_deleted") is False:
            rows = [r for r in rows if not r.get("is_deleted")]
        if "ORDER BY c.updated_at DESC" in query:
            rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        if "ORDER BY c.created_at DESC" in query:
            rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        if "ORDER BY c.order_index" in query:
            rows.sort(key=lambda r: r.get("order_index") or 0)
        return rows


class FakeDatabase:
    def __init__(self) -> None:
        self._containers = {
            RESUMES_CONTAINER: FakeContainer("user_id"),
            SELECTIONS_CONTAINER: FakeContainer("run_id"),
            EVENTS_CONTAINER: FakeContainer("resume_id"),
            VERSIONS_CONTAINER: FakeContainer("resume_id"),
            CONTACTS_CONTAINER: FakeContainer("resume_id"),
            SKILLS_CONTAINER: FakeContainer("resume_id"),
            EXPERIENCES_CONTAINER: FakeContainer("resume_id"),
            EDUCATIONS_CONTAINER: FakeContainer("resume_id"),
        }
        self.created: list[dict] = []

    def get_container_client(self, name: str) -> FakeContainer:
        if name not in self._containers:
            self._containers[name] = FakeContainer("resume_id")
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
    assert set(specs) == {
        RESUMES_CONTAINER,
        SELECTIONS_CONTAINER,
        EVENTS_CONTAINER,
        VERSIONS_CONTAINER,
        CONTACTS_CONTAINER,
        SKILLS_CONTAINER,
        EXPERIENCES_CONTAINER,
        EDUCATIONS_CONTAINER,
    }
    assert specs[RESUMES_CONTAINER]["partition_key"] == RESUMES_PARTITION_KEY
    assert specs[SELECTIONS_CONTAINER]["partition_key"] == SELECTIONS_PARTITION_KEY
    assert specs[EVENTS_CONTAINER]["partition_key"] == EVENTS_PARTITION_KEY
    assert specs[VERSIONS_CONTAINER]["partition_key"] == VERSIONS_PARTITION_KEY
    for name in CHILD_CONTAINERS:
        assert specs[name]["partition_key"] == CHILDREN_PARTITION_KEY
    assert specs[CONTACTS_CONTAINER]["indexing_policy"] == CONTACTS_INDEXING_POLICY
    assert specs[SKILLS_CONTAINER]["indexing_policy"] == CHILDREN_INDEXING_POLICY
    assert specs[EXPERIENCES_CONTAINER]["indexing_policy"] == CHILDREN_INDEXING_POLICY
    assert specs[EDUCATIONS_CONTAINER]["indexing_policy"] == CHILDREN_INDEXING_POLICY
    assert specs[RESUMES_CONTAINER]["indexing_policy"] == RESUMES_INDEXING_POLICY
    composite = specs[RESUMES_CONTAINER]["indexing_policy"]["compositeIndexes"][0]
    paths = [part["path"] for part in composite]
    assert paths == ["/user_id", "/is_deleted", "/updated_at"]
    child_paths = [part["path"] for part in CHILDREN_INDEXING_POLICY["compositeIndexes"][0]]
    assert child_paths == ["/resume_id", "/order_index"]


def test_ensure_resume_containers_creates_prd_set():
    from app.resumes.containers import ensure_resume_containers

    db = FakeDatabase()
    ensure_resume_containers(db)
    assert {item["id"] for item in db.created} == {
        RESUMES_CONTAINER,
        SELECTIONS_CONTAINER,
        EVENTS_CONTAINER,
        VERSIONS_CONTAINER,
        CONTACTS_CONTAINER,
        SKILLS_CONTAINER,
        EXPERIENCES_CONTAINER,
        EDUCATIONS_CONTAINER,
    }
    resumes = next(item for item in db.created if item["id"] == RESUMES_CONTAINER)
    assert resumes["partition_key"].path == "/user_id"
    skills = next(item for item in db.created if item["id"] == SKILLS_CONTAINER)
    assert skills["partition_key"].path == "/resume_id"


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
    assert parsed.contact.id == resume.id
    assert [s.name for s in parsed.skills] == ["Python", "Azure"]
    assert [s.order_index for s in parsed.skills] == [0, 1]
    assert parsed.skills[0].parsing_confidence == 88
    assert store.list_parse_events(resume.id)[0].event_type == "succeeded"
    children = store.child_documents(resume.id)
    assert [s.name for s in children.skills] == ["Python", "Azure"]
    assert children.contact is not None
    assert children.contact.id == resume.id
    parent = store.get_resume(USER, resume.id)
    assert parent.skills[0].user_id == USER
    if isinstance(store, CosmosResumeStore):
        raw = store._resumes.items[(USER, resume.id)]  # noqa: SLF001
        assert "skills" not in raw
        assert "contact" not in raw
        assert "experiences" not in raw
        assert "educations" not in raw
        skill_rows = list(store._skills.items.values())  # noqa: SLF001
        assert {row["name"] for row in skill_rows} == {"Python", "Azure"}
        assert all(row["resume_id"] == resume.id for row in skill_rows)


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
    assert parsed.contact.id == resume.id
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
    assert replaced.contact.id == resume.id
    children = store.child_documents(resume.id)
    assert children.contact is not None
    assert children.contact.id == resume.id
    if isinstance(store, CosmosResumeStore):
        contacts = list(store._contacts.items.values())  # noqa: SLF001
        assert len(contacts) == 1
        assert contacts[0]["email"] == "jane.d@example.com"


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
        store.set_run_selection(run_id="run-3", user_id=USER, resume_id=deleted.id)
    with pytest.raises(ResumeNotFoundError):
        store.set_run_selection(run_id="run-4", user_id=OTHER, resume_id=ready.id)


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


def test_clear_selections_for_resume(store):
    resume = _upload(store)
    store.record_parse_success(USER, resume.id, _snapshot(skills=[_skill("Python")]))
    store.set_run_selection(run_id="run-x", user_id=USER, resume_id=resume.id)
    assert store.get_run_selection("run-x") is not None
    removed = store.clear_selections_for_resume(USER, resume.id)
    assert removed == 1
    assert store.get_run_selection("run-x") is None


def test_one_active_resume_per_user(store):
    first = _upload(store, checksum="a1")
    second = _upload(store, checksum="a2")
    store.record_parse_success(USER, first.id, _snapshot(skills=[_skill("Python")]))
    store.record_parse_success(USER, second.id, _snapshot(skills=[_skill("Go")]))
    active = store.set_user_active(USER, first.id)
    assert active.is_active is True
    replaced = store.set_user_active(USER, second.id)
    assert replaced.id == second.id
    assert store.get_resume(USER, first.id).is_active is False
    assert store.get_user_active(USER).id == second.id


def test_replace_clears_removed_child_rows(store):
    resume = _upload(store)
    store.record_parse_success(
        USER, resume.id, _snapshot(skills=[_skill("Python"), _skill("Go")])
    )
    store.replace_structured_data(
        USER,
        resume.id,
        _snapshot(skills=[_skill("Rust")]),
        last_edited_by=USER,
    )
    children = store.child_documents(resume.id)
    assert [skill.name for skill in children.skills] == ["Rust"]
    assert [skill.order_index for skill in children.skills] == [0]
    if isinstance(store, CosmosResumeStore):
        assert len(store._skills.items) == 1  # noqa: SLF001
        assert next(iter(store._skills.items.values()))["name"] == "Rust"  # noqa: SLF001


def test_edit_audit_keeps_old_and_new(store):
    resume = _upload(store)
    store.record_parse_success(USER, resume.id, _snapshot(skills=[_skill("Python")]))
    store.replace_structured_data(
        USER,
        resume.id,
        _snapshot(skills=[_skill("Go")]),
        last_edited_by=USER,
    )
    edited = next(e for e in store.list_parse_events(resume.id) if e.event_type == "edited")
    assert edited.detail["old"]["skills"] == ["Python"]
    assert edited.detail["new"]["skills"] == ["Go"]
    assert edited.detail["editor"] == USER
    parsed = store.get_resume(USER, resume.id)
    assert parsed.schema_version == "1"
    assert parsed.parsed_version >= 2


def test_schema_validate_requires_child_keys():
    from app.storage.schema_validate import SchemaValidationError, validate_item

    validate_item("resume_skills", {"id": "s1", "resume_id": "r1", "name": "Python"})
    validate_item("resume_contacts", {"id": "r1", "resume_id": "r1"})
    with pytest.raises(SchemaValidationError):
        validate_item("resume_skills", {"id": "s1", "resume_id": "r1"})
    with pytest.raises(SchemaValidationError):
        validate_item("resume_experiences", {"id": "e1"})


def test_failed_parse_is_not_selectable(store):
    resume = _upload(store)
    store.record_status(USER, resume.id, "failed", parsing_error="empty")
    with pytest.raises(ResumeSelectionRejectedError):
        store.set_run_selection(run_id="run-fail", user_id=USER, resume_id=resume.id)


def test_catalog_exposes_child_containers():
    from app.storage.catalog import container_by_id

    for name in CHILD_CONTAINERS:
        spec = container_by_id(name)
        assert spec.partition_key == "/resume_id"
        assert spec.feature == "resumes"
    contacts = container_by_id(CONTACTS_CONTAINER)
    assert contacts.logical_unique == ("resume_id",)
    assert contacts.entity == "ResumeContact"
    skills = container_by_id(SKILLS_CONTAINER)
    paths = [[part["path"] for part in index] for index in skills.indexing_policy["compositeIndexes"]]
    assert ["/resume_id", "/order_index"] in paths


def test_parent_document_omits_child_collections():
    from app.resumes.children import parent_document

    store = InMemoryResumeStore()
    row = store.create_resume(
        user_id=USER,
        original_filename="cv.pdf",
        mime_type=PDF,
        file_size=12,
        blob_uri="blob://cv.pdf",
        checksum_sha256="xyz",
    )
    store.record_parse_success(
        USER,
        row.id,
        _snapshot(
            skills=[_skill("Python")],
            contact=ResumeContact(
                resume_id=row.id, full_name="Ada", email="ada@example.com", updated_at=utc_now()
            ),
        ),
    )
    hydrated = store.get_resume(USER, row.id)
    payload = parent_document(hydrated)
    assert "skills" not in payload
    assert "contact" not in payload
    assert "experiences" not in payload
    assert "educations" not in payload
    assert payload["id"] == row.id
    assert hydrated.skills[0].name == "Python"


def test_legacy_embedded_children_migrate_to_containers():
    db = FakeDatabase()
    store = CosmosResumeStore(db)
    resume = _upload(store)
    parent = dict(store._resumes.items[(USER, resume.id)])  # noqa: SLF001
    parent["skills"] = [
        ResumeSkill(resume_id=resume.id, name="Legacy", order_index=0, updated_at=utc_now()).model_dump()
    ]
    parent["contact"] = ResumeContact(
        resume_id=resume.id, full_name="Legacy User", email="legacy@example.com", updated_at=utc_now()
    ).model_dump()
    store._resumes.items[(USER, resume.id)] = parent  # noqa: SLF001
    loaded = store.get_resume(USER, resume.id)
    assert [s.name for s in loaded.skills] == ["Legacy"]
    assert loaded.contact is not None
    assert loaded.contact.email == "legacy@example.com"
    children = store.child_documents(resume.id)
    assert [s.name for s in children.skills] == ["Legacy"]
    assert any(row["name"] == "Legacy" for row in store._skills.items.values())  # noqa: SLF001
    store.record_status(USER, resume.id, "queued")
    assert "skills" not in store._resumes.items[(USER, resume.id)]  # noqa: SLF001

