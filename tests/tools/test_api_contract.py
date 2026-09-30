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


def test_documented_routes_have_typed_openapi_contracts():
    documented = set(re.findall(r"^### `(GET|POST|DELETE) ([^`]+)`", (ROOT / "docs/architecture.md").read_text(), re.MULTILINE))
    schema = app.openapi()
    declared = {(method.upper(), path) for path, operations in schema["paths"].items() if path.startswith("/api/") for method in operations}
    assert declared == documented
    for method, path in documented:
        operation = schema["paths"][path][method.lower()]
        assert "501" in operation["responses"]
        success_status = "202" if (method, path) in {("POST", "/api/checks"), ("POST", "/api/checks/{id}/retry")} else "200"
        assert "schema" in operation["responses"][success_status]["content"]["application/json"]
    assert schema["components"]["schemas"]["DiagnosticPacket"]["properties"]["schema_version"]["const"] == "2.2"


@pytest.mark.parametrize("method,path,kwargs", REQUESTS)
def test_business_routes_are_pending_without_network_or_database(method, path, kwargs, monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("A scaffold route attempted network or database I/O")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
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


def test_missing_request_fields_do_not_look_like_a_created_task():
    with TestClient(app) as client:
        response = client.post("/api/checks", json={})
    assert response.status_code == 422
    assert "id" not in response.json()
