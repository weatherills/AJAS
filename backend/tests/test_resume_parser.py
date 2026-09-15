"""Unit tests for resume parsing, normalization, blob adapter, and metrics."""

from __future__ import annotations

from app.metrics import reset, snapshot
from app.resumes.blobs import InMemoryBlobStore, scan_antivirus
from app.resumes.constants import CANONICAL_SCHEMA_VERSION, HEURISTIC_SOURCE_VERSION, PARSE_BACKOFF_SECONDS
from app.resumes.errors import FileRejectedError
from app.resumes.parser import HeuristicResumeParser
from app.resumes.service import ResumeService, _backoff_seconds
from tests.resume_factories import sample_docx_bytes, sample_pdf_bytes, write_sample_assets


def test_heuristic_parser_extracts_contact_skills_titles_experience_education():
    text = "\n".join(
        [
            "Skills: Python, Azure, Kubernetes",
            "Experience: Staff Engineer at Acme",
            "Education: MIT Computer Science",
        ]
    )
    snapshot_data = HeuristicResumeParser().parse(resume_id="r1", text=text)
    assert [s.name for s in snapshot_data.skills] == ["Python", "Azure", "Kubernetes"]
    assert snapshot_data.experiences[0].title == "Staff Engineer at Acme"
    assert snapshot_data.educations[0].institution == "MIT Computer Science"


def test_normalization_sets_schema_and_source_version():
    from app.resumes.memory import InMemoryResumeStore
    from app.resumes.queueing import InMemoryParseQueue

    service = ResumeService(
        store=InMemoryResumeStore(),
        blobs=InMemoryBlobStore(),
        queue=InMemoryParseQueue(),
        parser=HeuristicResumeParser(),
    )
    resume = service.upload(
        user_id="user-1",
        filename="cv.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        data=sample_docx_bytes("Skills: Python"),
    )
    service.process_parse_job(service.queue.messages[0], dequeue_count=1)
    parsed = service.get("user-1", resume.id)
    assert parsed.schema_version == CANONICAL_SCHEMA_VERSION
    assert parsed.source_version == HEURISTIC_SOURCE_VERSION
    assert parsed.parsed_version == 1


def test_blob_put_get_delete_and_signed_url():
    store = InMemoryBlobStore()
    path = store.put(user_id="u", resume_id="r", filename="cv.pdf", data=sample_pdf_bytes(), mime_type="application/pdf")
    assert store.get(path)[:4] == b"%PDF"
    url = store.sas_url(path, minutes=10)
    assert "se=" in url and "sp=r" in url
    store.delete(path)
    try:
        store.get(path)
        raise AssertionError("expected missing blob")
    except FileNotFoundError:
        pass


def test_antivirus_stub_rejects_eicar():
    try:
        scan_antivirus(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!")
        raise AssertionError("expected AV reject")
    except FileRejectedError as exc:
        assert exc.code == "AV_REJECTED"


def test_parse_backoff_is_exponential():
    assert PARSE_BACKOFF_SECONDS == (1, 4, 16)
    assert _backoff_seconds(1) == 1
    assert _backoff_seconds(2) == 4
    assert _backoff_seconds(3) == 16


def test_sample_assets_and_metrics():
    reset()
    pdf_path, docx_path = write_sample_assets()
    assert pdf_path.exists() and docx_path.exists()
    from app.resumes.memory import InMemoryResumeStore
    from app.resumes.queueing import InMemoryParseQueue

    service = ResumeService(
        store=InMemoryResumeStore(),
        blobs=InMemoryBlobStore(),
        queue=InMemoryParseQueue(),
        parser=HeuristicResumeParser(),
    )
    resume = service.upload(
        user_id="user-1",
        filename="cv.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        data=docx_path.read_bytes(),
    )
    service.process_parse_job(service.queue.messages[0], dequeue_count=1)
    service.patch("user-1", resume.id, {"skills": ["Python", "Go"]})
    counters = snapshot()["counters"]
    assert counters["resume.upload"] == 1
    assert counters["resume.parse.ok"] == 1
    assert counters["resume.edit"] == 1
