"""Smoke tests that the backend skeleton imports and wires up cleanly."""
import json


def test_function_app_imports_and_registers_health(function_names):
    # azure.functions.FunctionRegister.get_functions() is not idempotent, so
    # names are cached once in the session fixture.
    assert "health" in function_names


def test_health_reports_live_features(monkeypatch):
    import azure.functions as func

    from app.config import get_settings
    from app.features.health import health

    monkeypatch.delenv("COSMOS_CONNECTION_STRING", raising=False)
    monkeypatch.setenv("AUTH_MODE", "dev")
    get_settings.cache_clear()
    resp = health(
        func.HttpRequest(
            method="GET",
            url="http://localhost/api/health",
            headers={},
            params={},
            route_params={},
            body=b"",
        )
    )
    body = json.loads(resp.get_body())
    assert resp.status_code == 200
    assert body["status"] == "ok"
    assert body["service"] == "ajas-backend"
    assert body["authMode"] == "dev"
    assert body["storage"] == "memory"
    assert body["features"] == ["health", "review", "auto-apply", "settings", "resume", "jobs", "matching"]


def test_json_response_shape():
    from app.http import json_response

    resp = json_response({"status": "ok"}, status_code=200)
    assert resp.status_code == 200
    assert json.loads(resp.get_body()) == {"status": "ok"}


def test_error_response_envelope():
    from app.http import error_response

    resp = error_response("BAD_INPUT", "nope", status_code=400, details=["x"])
    assert resp.status_code == 400
    body = json.loads(resp.get_body())
    assert body["error"]["code"] == "BAD_INPUT"
    assert body["error"]["details"] == ["x"]
