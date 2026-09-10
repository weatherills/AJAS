"""Attachment malware scan hook (local signature + pluggable scanner)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

# Standard EICAR test file — scanners treat this as malware without being a real virus.
EICAR_SIGNATURE = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class AttachmentScanner(Protocol):
    def scan(self, content: bytes, *, file_name: str) -> "ScanResult": ...


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    reason: str | None = None
    engine: str = "local-signature"


class LocalSignatureScanner:
    def scan(self, content: bytes, *, file_name: str) -> ScanResult:
        if EICAR_SIGNATURE in (content or b""):
            return ScanResult(clean=False, reason="eicar_signature", engine="local-signature")
        lowered = (file_name or "").lower()
        if lowered.endswith((".exe", ".bat", ".cmd", ".scr")):
            return ScanResult(clean=False, reason="blocked_extension", engine="local-signature")
        return ScanResult(clean=True, engine="local-signature")


_scanner_factory: Callable[[], AttachmentScanner] | None = None


def set_scanner_factory(factory: Callable[[], AttachmentScanner] | None) -> None:
    global _scanner_factory
    _scanner_factory = factory


def get_scanner() -> AttachmentScanner:
    if _scanner_factory is not None:
        return _scanner_factory()
    return LocalSignatureScanner()


def scan_attachment(content: bytes, *, file_name: str) -> ScanResult:
    """Hook used by ingest and outbound send. Swap the scanner in tests or production."""
    return get_scanner().scan(content or b"", file_name=file_name or "file")
