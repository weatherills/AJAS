"""HTTP GET seam used by Greenhouse/Lever crawlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener


@dataclass
class FetchResponse:
    status_code: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)
    url: str = ""

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def header(self, name: str) -> str | None:
        lower = name.lower()
        for key, value in self.headers.items():
            if key.lower() == lower:
                return value
        return None


class HttpFetcher(Protocol):
    def get(self, url: str, timeout: tuple[float, float] = (10.0, 20.0)) -> FetchResponse: ...


class UrllibFetcher:
    def get(self, url: str, timeout: tuple[float, float] = (10.0, 20.0)) -> FetchResponse:
        import urllib.request

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
                return None

        opener = build_opener(_NoRedirect)
        request = Request(url, method="GET", headers={"User-Agent": "AJAS-job-source/1.0", "Accept": "application/json"})
        read_timeout = timeout[1] if timeout else 20.0
        try:
            with opener.open(request, timeout=read_timeout) as resp:
                headers = {k: v for k, v in resp.headers.items()}
                return FetchResponse(int(getattr(resp, "status", 200)), resp.read(), headers, resp.geturl())
        except HTTPError as exc:
            headers = {k: v for k, v in (exc.headers.items() if exc.headers else [])}
            body = exc.read() if hasattr(exc, "read") else b""
            return FetchResponse(int(exc.code), body, headers, url)
        except URLError as exc:
            raise TimeoutError(str(exc.reason or exc)) from exc
