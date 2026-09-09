"""Resume Management Backend PRD — HTTP API, auth, parse worker."""

from __future__ import annotations

import json
from io import BytesIO

import azure.functions as func
import pytest
from pypdf import PdfWriter

from app.features import resume_management as routes
from app.resumes.blobs import InMemoryBlobStore, sas_is_expired
from app.resumes.memory import InMemoryResumeStore
from app.resumes.parser import HeuristicResumeParser
from app.resumes.queueing import InMemoryParseQueue
from app.resumes.runtime import set_service
from app.resumes.service import ResumeService
from datetime import datetime, timedelta, timezone


USER = "user-1"
OTHER = "user-2"


@pytest.fixture
def svc():
    service = ResumeService(
        store=InMemoryResumeStore(),
        blobs=InMemoryBlobStore(),
        queue=InMemoryParseQueue(),
        parser=HeuristicResumeParser(),
    )
    set_service(service)
    yield service
    set_service(None)


def _pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("secret")
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _docx(text: str = "Skills: Python, Azure") -> bytes:
    from docx import Document

    document = Document()
    document.add_paragraph(text)
    buf = BytesIO()
    document.save(buf)
    return buf.getvalue()


def _req(
    method: str,
    url: str,
    *,
    user: str | None = USER,
    params: dict | None = None,
    route: dict | None = None,
    json_body=None,
    file: tuple[str, str, bytes] | None = None,
) -> func.HttpRequest:
    headers = {}
    body = b""
    if user:
        headers["Authorization"] = f"Bearer {user}"
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(json_body).encode()
    if file:
        filename, mime, data = file
        boundary = "----AjasBoundary"
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return func.HttpRequest(
        method=method,
        url=url,
        headers=headers,
        params=params or {},
        route_params=route or {},
        body=body,
    )


def _body(resp: func.HttpResponse):
    raw = resp.get_body()
    return json.loads(raw) if raw else None


def test_function_app_registers_resume_routes(function_names):
    assert "upload_resume" in function_names
    assert "parse_resume_job" in function_names
    assert "health" in function_names


def test_unauthenticated_is_401(svc):
    resp = routes.list_resumes(_req("GET", "http://localhost/api/resumes", user=None))
    assert resp.status_code == 401


def test_upload_pdf_creates_resume_and_enqueues(svc):
    resp = routes.upload_resume(
        _req(
            "POST",
            "http://localhost/api/resumes",
            file=("cv.pdf", "application/pdf", _pdf()),
        )
    )
    assert resp.status_code == 201
    payload = _body(resp)
    assert payload["status"] == "uploaded"
    assert payload["id"]
    assert len(svc.queue.messages) == 1
    assert svc.queue.messages[0]["resumeId"] == payload["id"]
    stored = svc.store.get_resume(USER, payload["id"])
    assert stored.blob_uri.endswith("cv.pdf")
    assert stored.checksum_sha256


def test_upload_rejects_type_size_and_encrypted(svc, monkeypatch):
    bad_type = routes.upload_resume(
        _req("POST", "http://localhost/api/resumes", file=("cv.txt", "text/plain", b"hi"))
    )
    assert bad_type.status_code == 415
    encrypted = routes.upload_resume(
        _req(
            "POST",
            "http://localhost/api/resumes",
            file=("cv.pdf", "application/pdf", _encrypted_pdf()),
        )
    )
    assert encrypted.status_code == 400
    assert _body(encrypted)["error"]["code"] == "ENCRYPTED_FILE"

    monkeypatch.setattr(
        "app.resumes.files.get_settings",
        lambda: type("S", (), {"resume_max_upload_bytes": 10, "resume_max_pdf_pages": 20})(),
    )
    huge = routes.upload_resume(
        _req("POST", "http://localhost/api/resumes", file=("cv.pdf", "application/pdf", _pdf()))
    )
    assert huge.status_code == 413


def test_list_get_patch_delete_and_isolation(svc):
    created = _body(
        routes.upload_resume(
            _req("POST", "http://localhost/api/resumes", file=("cv.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", _docx()))
        )
    )
    listed = _body(routes.list_resumes(_req("GET", "http://localhost/api/resumes")))
    assert listed["items"][0]["id"] == created["id"]
    assert listed["items"][0]["fileName"] == "cv.docx"

    other = routes.get_resume(
        _req("GET", "http://localhost/api/resumes/x", user=OTHER, route={"id": created["id"]})
    )
    assert other.status_code == 404

    detail = _body(
        routes.get_resume(_req("GET", "http://localhost/api/resumes/x", route={"id": created["id"]}))
    )
    assert detail["id"] == created["id"]

    patched = routes.patch_resume(
        _req(
            "PATCH",
            "http://localhost/api/resumes/x",
            route={"id": created["id"]},
            json_body={"skills": ["Python"], "experience": [{"title": "Eng", "company": "Acme", "startDate": "2020-01", "endDate": "2021-01"}]},
        )
    )
    assert patched.status_code == 200
    assert _body(patched)["skills"] == ["Python"]

    invalid = routes.patch_resume(
        _req(
            "PATCH",
            "http://localhost/api/resumes/x",
            route={"id": created["id"]},
            json_body={"experience": [{"title": "Eng", "startDate": "2022-01", "endDate": "2020-01"}]},
        )
    )
    assert invalid.status_code == 400
    assert _body(invalid)["error"]["details"][0]["path"].startswith("/")

    deleted = routes.delete_resume(
        _req("DELETE", "http://localhost/api/resumes/x", route={"id": created["id"]})
    )
    assert deleted.status_code == 204
    listed_after = _body(routes.list_resumes(_req("GET", "http://localhost/api/resumes")))
    assert listed_after["items"] == []
    assert routes.get_resume(_req("GET", "http://localhost/api/resumes/x", route={"id": created["id"]})).status_code == 404
    # idempotent
    assert routes.delete_resume(_req("DELETE", "http://localhost/api/resumes/x", route={"id": created["id"]})).status_code == 204


def test_preview_url_and_expiry(svc):
    created = _body(
        routes.upload_resume(
            _req("POST", "http://localhost/api/resumes", file=("cv.pdf", "application/pdf", _pdf()))
        )
    )
    preview = _body(
        routes.preview_url(
            _req("GET", "http://localhost/api/resumes/x/preview-url", route={"id": created["id"]})
        )
    )
    assert preview["expiresInSeconds"] == 600
    assert "se=" in preview["url"]
    assert not sas_is_expired(preview["url"])
    assert sas_is_expired(
        preview["url"],
        now=datetime.now(timezone.utc) + timedelta(minutes=11),
    )
    routes.delete_resume(_req("DELETE", "http://localhost/api/resumes/x", route={"id": created["id"]}))
    assert (
        routes.preview_url(
            _req("GET", "http://localhost/api/resumes/x/preview-url", route={"id": created["id"]})
        ).status_code
        == 404
    )


def test_parse_worker_success_and_failure(svc):
    created = _body(
        routes.upload_resume(
            _req(
                "POST",
                "http://localhost/api/resumes",
                file=(
                    "cv.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    _docx("Skills: Python, Azure"),
                ),
            )
        )
    )
    msg = svc.queue.messages[0]
    svc.process_parse_job(msg, dequeue_count=1)
    detail = _body(routes.get_resume(_req("GET", "http://localhost/api/resumes/x", route={"id": created["id"]})))
    assert detail["status"] == "parsed"
    assert "Python" in detail["skills"]

    class Boom:
        def parse(self, **kwargs):
            raise RuntimeError("openai down")

    svc.parser = Boom()
    created2 = _body(
        routes.upload_resume(
            _req(
                "POST",
                "http://localhost/api/resumes",
                file=(
                    "cv2.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    _docx("Skills: Go"),
                ),
            )
        )
    )
    with pytest.raises(RuntimeError):
        svc.process_parse_job(svc.queue.messages[-1], dequeue_count=1)
    svc.process_parse_job(svc.queue.messages[-1], dequeue_count=3)
    failed = _body(routes.get_resume(_req("GET", "http://localhost/api/resumes/x", route={"id": created2["id"]})))
    assert failed["status"] == "parse_failed"
    assert failed["lastParseError"]


def test_patch_promotes_failed_to_parsed(svc):
    created = _body(
        routes.upload_resume(
            _req("POST", "http://localhost/api/resumes", file=("cv.pdf", "application/pdf", _pdf()))
        )
    )
    svc.store.record_status(USER, created["id"], "failed", parsing_error="empty")
    patched = _body(
        routes.patch_resume(
            _req(
                "PATCH",
                "http://localhost/api/resumes/x",
                route={"id": created["id"]},
                json_body={"skills": ["Python"]},
            )
        )
    )
    assert patched["status"] == "parsed"
    assert patched["skills"] == ["Python"]


def test_active_resume_one_per_run_and_revoke_on_delete(svc):
    first = _body(
        routes.upload_resume(
            _req("POST", "http://localhost/api/resumes", file=("a.pdf", "application/pdf", _pdf()))
        )
    )
    second = _body(
        routes.upload_resume(
            _req("POST", "http://localhost/api/resumes", file=("b.pdf", "application/pdf", _pdf()))
        )
    )
    set_resp = routes.set_active_resume(
        _req(
            "POST",
            "http://localhost/api/runs/run-1/active-resume",
            route={"runId": "run-1"},
            json_body={"resumeId": first["id"]},
        )
    )
    assert set_resp.status_code == 200
    replaced = _body(
        routes.set_active_resume(
            _req(
                "POST",
                "http://localhost/api/runs/run-1/active-resume",
                route={"runId": "run-1"},
                json_body={"resumeId": second["id"]},
            )
        )
    )
    assert replaced["resumeId"] == second["id"]
    got = _body(
        routes.get_active_resume(
            _req("GET", "http://localhost/api/runs/run-1/active-resume", route={"runId": "run-1"})
        )
    )
    assert got["resumeId"] == second["id"]

    assert (
        routes.get_active_resume(
            _req(
                "GET",
                "http://localhost/api/runs/run-1/active-resume",
                user=OTHER,
                route={"runId": "run-1"},
            )
        ).status_code
        == 404
    )

    routes.delete_resume(_req("DELETE", "http://localhost/api/resumes/x", route={"id": second["id"]}))
    assert (
        routes.get_active_resume(
            _req("GET", "http://localhost/api/runs/run-1/active-resume", route={"runId": "run-1"})
        ).status_code
        == 404
    )
    rejected = routes.set_active_resume(
        _req(
            "POST",
            "http://localhost/api/runs/run-2/active-resume",
            route={"runId": "run-2"},
            json_body={"resumeId": second["id"]},
        )
    )
    assert rejected.status_code == 400


def test_list_includes_hash_and_retry_parse(svc):
    created = _body(
        routes.upload_resume(
            _req("POST", "http://localhost/api/resumes", file=("cv.pdf", "application/pdf", _pdf()))
        )
    )
    listed = _body(routes.list_resumes(_req("GET", "http://localhost/api/resumes")))
    assert listed["items"][0]["fileHash"]
    assert "validated" in listed["items"][0]
    svc.store.record_status(USER, created["id"], "failed", parsing_error="empty")
    retried = routes.retry_parse(
        _req("POST", "http://localhost/api/resumes/x/retry-parse", route={"id": created["id"]})
    )
    assert retried.status_code == 200
    assert _body(retried)["status"] == "uploaded"
    assert svc.queue.messages[-1]["resumeId"] == created["id"]


def test_patch_contact(svc):
    created = _body(
        routes.upload_resume(
            _req("POST", "http://localhost/api/resumes", file=("cv.pdf", "application/pdf", _pdf()))
        )
    )
    patched = _body(
        routes.patch_resume(
            _req(
                "PATCH",
                "http://localhost/api/resumes/x",
                route={"id": created["id"]},
                json_body={
                    "contact": {
                        "fullName": "Jane Doe",
                        "email": "jane@example.com",
                        "phone": "+15555550100",
                        "linkedinUrl": "https://linkedin.com/in/jane",
                    },
                    "education": [{"institution": "MIT", "startDate": "2015-09", "endDate": "2019-06"}],
                },
            )
        )
    )
    assert patched["contact"]["fullName"] == "Jane Doe"
    assert patched["contact"]["email"] == "jane@example.com"
    assert patched["contact"]["linkedinUrl"] == "https://linkedin.com/in/jane"
