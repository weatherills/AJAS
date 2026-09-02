"""Smoke tests that the backend skeleton imports and wires up cleanly."""
import json


def test_function_app_imports_and_registers_health():
    # Importing the app builds the FunctionApp and registers blueprints; this
    # fails loudly if the skeleton wiring or any imported module breaks.
    import function_app

    functions = function_app.app.get_functions()
    names = {f.get_function_name() for f in functions}
    assert "health" in names


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
