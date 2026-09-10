from app.mail.scan import EICAR_SIGNATURE, LocalSignatureScanner, scan_attachment, set_scanner_factory


def test_eicar_is_flagged():
    result = scan_attachment(EICAR_SIGNATURE, file_name="invoice.txt")
    assert result.clean is False
    assert result.reason == "eicar_signature"


def test_exe_extension_is_blocked():
    result = scan_attachment(b"not malware", file_name="setup.exe")
    assert result.clean is False
    assert result.reason == "blocked_extension"


def test_clean_pdf_passes():
    result = scan_attachment(b"%PDF-1.4 demo", file_name="resume.pdf")
    assert result.clean is True


def test_scanner_factory_is_swappable():
    class AlwaysClean:
        def scan(self, content, *, file_name):
            from app.mail.scan import ScanResult

            return ScanResult(clean=True, engine="noop")

    set_scanner_factory(lambda: AlwaysClean())
    try:
        result = scan_attachment(EICAR_SIGNATURE, file_name="bad.bin")
        assert result.engine == "noop"
        assert result.clean is True
    finally:
        set_scanner_factory(None)
    assert LocalSignatureScanner().scan(EICAR_SIGNATURE, file_name="x").clean is False
