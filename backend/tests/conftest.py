"""Shared fixtures for Azure Functions app indexing."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def function_names() -> set[str]:
    import function_app

    return {fn.get_function_name() for fn in function_app.app.get_functions()}
