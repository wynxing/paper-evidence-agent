"""Verify the documented HTTP surface and the explicit, side-effect-free stubs."""

from copy import deepcopy
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


def documented_contracts(schema: dict, text: str | None = None) -> dict[tuple[str, str], dict[str, str]]:
    """Read route-local response tables plus the documented shared 404/422 rules."""

    if text is None:
        text = (ROOT / "docs/architecture.md").read_text(encoding="utf-8")
    sections = re.split(r"^### `(GET|POST|DELETE) ([^`]+)`\n", text, flags=re.MULTILINE)
    shared = re.findall(r"^\| (路由包含 `\{id\}`|含请求体或路径/查询参数) \| `([1-5][0-9]{2})` \| `([^`]+)` \|$", sections[0], re.MULTILINE)
    contracts = {}
    for index in range(1, len(sections), 3):
        method, path, section = sections[index:index + 3]
        if not path.startswith("/api/"):
            continue
        match = re.search(r"\| HTTP 状态 \| 响应类型 \|\n\| --- \| --- \|\n((?:\|[^\n]+\n)+)", section)
        assert match, f"Missing response table: {method} {path}"
        rows = re.findall(r"^\| `([1-5][0-9]{2})` \| `([^`]+)` \|$", match.group(1), re.MULTILINE)
        responses = dict(rows)
        assert rows and len(rows) == len(match.group(1).splitlines()), f"Malformed response table: {method} {path}"
        assert len(responses) == len(rows), f"Duplicate responses: {method} {path}"
        operation = schema["paths"][path][method.lower()]
        for condition, status, model in shared:
            applies = "{id}" in path if condition == "路由包含 `{id}`" else bool(operation.get("parameters") or operation.get("requestBody"))
            if applies:
                assert status not in responses or responses[status] == model, (method, path, status)
                responses[status] = model
        contracts[method, path] = responses
    return contracts


def documented_routes() -> set[tuple[str, str]]:
    return set(documented_contracts(app.openapi()))


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
    if schema.get("type") == "array":
        return schema["items"]["$ref"].rsplit("/", 1)[-1] + "[]"
    return schema["$ref"].rsplit("/", 1)[-1]


def assert_response_contracts(schema: dict, text: str | None = None) -> None:
    documented = documented_contracts(schema, text)
    assert declared_routes(schema) == set(documented)
    for (method, path), expected in documented.items():
        operation = schema["paths"][path][method.lower()]
        # 501 is temporary and checked separately by scaffold-marked tests.
        actual = set(operation["responses"]) - {"501"}
        assert actual == set(expected), (method, path, actual, set(expected))
        for status, model in expected.items():
            assert response_schema_name(operation, status) == model, (method, path, status)


def test_documented_routes_have_typed_openapi_contracts():
    schema = app.openapi()
    assert_response_contracts(schema)
    packet = schema["components"]["schemas"]["DiagnosticPacket"]
    assert packet["properties"]["schema_version"]["const"] == "2.2"
    assert "HTTPValidationError" not in schema["components"]["schemas"]
    assert "ValidationError" not in schema["components"]["schemas"]

    def check_refs(value):
        if isinstance(value, dict):
            if "$ref" in value:
                target = schema
                for part in value["$ref"].removeprefix("#/").split("/"):
                    target = target[part]
            for child in value.values():
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)
    check_refs(schema)


@pytest.mark.parametrize("change", ["extra", "missing", "wrong_model", "docs_added", "docs_removed", "shared_removed"])
def test_response_comparison_detects_drift_in_both_directions(change):
    schema = deepcopy(app.openapi())
    text = (ROOT / "docs/architecture.md").read_text(encoding="utf-8")
    responses = schema["paths"]["/api/sources/resolve"]["get"]["responses"]
    if change == "extra":
        responses["418"] = deepcopy(responses["400"])
    elif change == "missing":
        del responses["404"]
    elif change == "wrong_model":
        responses["400"]["content"]["application/json"]["schema"]["$ref"] = "#/components/schemas/ConflictResponse"
    elif change == "docs_added":
        text = text.replace("| `504` | `ApiError` |", "| `504` | `ApiError` |\n| `418` | `ApiError` |", 1)
    elif change == "docs_removed":
        text = text.replace("| `504` | `ApiError` |\n", "", 1)
    else:
        text = text.replace("| 含请求体或路径/查询参数 | `422` | `ApiError` |\n", "", 1)
    with pytest.raises(AssertionError):
        assert_response_contracts(schema, text)


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
        wrong_method = client.post("/api/run-config")
    assert missing.status_code == 422
    assert missing.json()["error_code"] is None
    assert "body.claim: missing" in missing.json()["message"]
    assert set(missing.json()) == {"error_code", "message"}
    assert unknown.status_code == 404
    assert unknown.json() == {"error_code": None, "message": "请求的资源不存在"}
    assert wrong_method.status_code == 405
    assert wrong_method.json() == {"error_code": None, "message": "请求方法不被允许"}
    assert wrong_method.headers["allow"] == "GET"
