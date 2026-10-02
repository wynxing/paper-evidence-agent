"""Verify the documented HTTP surface and the explicit, side-effect-free stubs."""

import re
import socket
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paper_evidence.api.app import app

ROOT = Path(__file__).resolve().parents[2]
AUTHORIZATION = {
    "config_digest": "unimplemented-config",
    "authorized_recipients": ["unimplemented-recipient"],
    "cloud_consent": True,
    "source_confirmed": True,
}
REQUESTS = [
    ("GET", "/api/sources/resolve", {"params": {"doi": "10.1234/unimplemented"}}),
    ("GET", "/api/run-config", {}),
    ("POST", "/api/checks", {"json": {"claim": "Synthetic input, no paper evidence", "doi": "10.1234/unimplemented", **AUTHORIZATION}}),
    ("GET", "/api/checks", {"params": {"status": "QUEUED"}}),
    ("GET", "/api/checks/test-id", {}),
    ("GET", "/api/checks/test-id/diagnostic-packet", {}),
    ("POST", "/api/checks/test-id/diagnostic-export", {"json": {"recipient": "unimplemented-recipient", "semantic_export_consent": True}}),
    ("POST", "/api/checks/test-id/feedback", {"json": {"comment": "Synthetic feedback"}}),
    ("POST", "/api/checks/test-id/retry", {"json": AUTHORIZATION}),
    ("POST", "/api/checks/test-id/cancel", {}),
    ("DELETE", "/api/checks/test-id", {}),
]
SUCCESS_CODES = {
    ("POST", "/api/checks"): {"202"},
    ("POST", "/api/checks/{id}/retry"): {"202"},
    ("POST", "/api/checks/{id}/cancel"): {"200", "202"},
}
ERROR_CODES = {
    ("GET", "/api/sources/resolve"): {"400": "ApiError", "404": "ApiError", "422": "ApiError", "502": "ApiError", "503": "ApiError", "504": "ApiError"},
    ("POST", "/api/checks"): {"400": "ApiError", "404": "ApiError", "409": "ConflictResponse"},
    ("GET", "/api/checks/{id}"): {"404": "ApiError"},
    ("GET", "/api/checks/{id}/diagnostic-packet"): {"404": "ApiError"},
    ("POST", "/api/checks/{id}/diagnostic-export"): {"400": "ApiError", "404": "ApiError", "409": "ConflictResponse"},
    ("POST", "/api/checks/{id}/feedback"): {"404": "ApiError"},
    ("POST", "/api/checks/{id}/retry"): {"400": "ApiError", "404": "ApiError", "409": "ConflictResponse"},
    ("POST", "/api/checks/{id}/cancel"): {"404": "ApiError", "409": "ConflictResponse"},
    ("DELETE", "/api/checks/{id}"): {"404": "ApiError", "409": "ConflictResponse"},
}


def documented_routes() -> set[tuple[str, str]]:
    text = (ROOT / "docs/architecture.md").read_text()
    found = re.findall(r"^### `(GET|POST|DELETE) ([^`]+)`", text, re.MULTILINE)
    return {(method, path) for method, path in found if path.startswith("/api/")}


def declared_routes(schema: dict) -> set[tuple[str, str]]:
    routes = set()
    for path, operations in schema["paths"].items():
        if not path.startswith("/api/"):
            continue
        for method in operations:
            if method in {"get", "post", "delete", "put", "patch"}:
                routes.add((method.upper(), path))
    return routes


def response_schema_name(operation: dict, status: str) -> str:
    schema = operation["responses"][status]["content"]["application/json"]["schema"]
    ref = schema["$ref"]
    return ref.rsplit("/", 1)[-1]


def test_documented_routes_have_typed_openapi_contracts():
    schema = app.openapi()
    documented = documented_routes()
    assert declared_routes(schema) == documented
    for method, path in documented:
        operation = schema["paths"][path][method.lower()]
        for status in SUCCESS_CODES.get((method, path), {"200"}):
            assert "schema" in operation["responses"][status]["content"]["application/json"]
        for status, name in ERROR_CODES.get((method, path), {}).items():
            assert response_schema_name(operation, status) == name
    packet = schema["components"]["schemas"]["DiagnosticPacket"]
    assert packet["properties"]["schema_version"]["const"] == "2.2"
    validation = schema["paths"]["/api/checks"]["post"]["responses"]["422"]
    assert response_schema_name({"responses": {"422": validation}}, "422") == "ApiError"
    assert "HTTPValidationError" not in schema["components"]["schemas"]


@pytest.mark.scaffold
def test_scaffold_routes_declare_pending_response():
    schema = app.openapi()
    for method, path in documented_routes():
        assert "501" in schema["paths"][path][method.lower()]["responses"]


@pytest.mark.scaffold
@pytest.mark.parametrize("method,path,kwargs", REQUESTS)
def test_business_routes_are_pending_without_network_or_database(method, path, kwargs, monkeypatch, tmp_path):
    """Relative writes under the temp directory stay empty.

    Absolute paths are outside this assertion. The guard covers connection
    setup, not the event-loop self-pipe, so Windows can enter TestClient.
    """

    def forbidden(*args, **kwargs):
        pytest.fail("A scaffold route attempted network or database I/O")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    with TestClient(app) as client:
        response = client.request(method, path, **kwargs)
    assert response.status_code == 501
    assert response.json() == {"error_code": None, "message": "Not Implemented：功能待实现"}
    assert list(tmp_path.iterdir()) == []


def test_health_is_live():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invalid_requests_use_the_api_error_envelope():
    with TestClient(app) as client:
        missing = client.post("/api/checks", json={})
        unknown = client.get("/api/nope")
        wrong_method = client.put("/api/checks/test-id")
    assert missing.status_code == 422
    assert missing.json() == {"error_code": None, "message": "请求不合法"}
    assert unknown.status_code == 404
    assert unknown.json()["error_code"] is None
    assert "detail" not in unknown.json()
    assert wrong_method.status_code == 405
    assert wrong_method.json()["error_code"] is None
    assert "detail" not in wrong_method.json()
