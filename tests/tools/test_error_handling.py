"""Exercise handlers on isolated test routes; production business routes stay 501."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.exceptions import HTTPException

from paper_evidence.api.app import app, handle_contract_error, handle_http_exception
from paper_evidence.domain import ContractError, ErrorCode, Stage, TaskStatus
from paper_evidence.domain.contracts import ApiError, ConflictResponse


@pytest.mark.parametrize("code,status", [
    (ErrorCode.DOI_INVALID, 400),
    (ErrorCode.DOI_UNRESOLVABLE, 404),
    (ErrorCode.METADATA_NOT_FOUND, 422),
    (ErrorCode.REGISTRATION_AGENCY_UNSUPPORTED, 422),
    (ErrorCode.UPSTREAM_AUTH_FAILED, 502),
    (ErrorCode.UPSTREAM_INVALID_REQUEST, 502),
    (ErrorCode.UPSTREAM_RATE_LIMITED, 503),
    (ErrorCode.UPSTREAM_UNAVAILABLE, 503),
    (ErrorCode.UPSTREAM_TIMEOUT, 504),
])
def test_preview_contract_errors_keep_machine_readable_codes(code, status):
    test_app = FastAPI()
    test_app.add_exception_handler(ContractError, handle_contract_error)

    @test_app.get("/api/sources/resolve")
    def fail():
        raise ContractError(code, "PRIVATE-claim-and-token")

    with TestClient(test_app) as client:
        response = client.get("/api/sources/resolve")
    assert response.status_code == status
    error = ApiError.model_validate(response.json())
    assert error.error_code == code
    assert error.message
    assert "PRIVATE" not in response.text


@pytest.mark.parametrize("path,method,code", [
    ("/api/sources/resolve", "GET", ErrorCode.CONTENT_INCOMPLETE),
    ("/api/sources/resolve", "GET", None),
    ("/api/sources/resolve", "POST", ErrorCode.DOI_UNRESOLVABLE),
    ("/api/checks", "GET", ErrorCode.DOI_UNRESOLVABLE),
])
def test_unmapped_contract_errors_are_not_reclassified(path, method, code):
    test_app = FastAPI()
    test_app.add_exception_handler(ContractError, handle_contract_error)
    failure = ContractError(code, "unmapped failure")

    @test_app.api_route(path, methods=[method])
    def fail():
        raise failure

    with TestClient(test_app) as client, pytest.raises(ContractError) as raised:
        client.request(method, path)
    assert raised.value is failure


def test_framework_http_errors_preserve_headers_and_log_only_safe_structure(caplog):
    test_app = FastAPI()
    test_app.add_exception_handler(HTTPException, handle_http_exception)

    @test_app.get("/framework-error")
    def fail():
        raise HTTPException(404, detail={
            "error_code": "DOI_UNRESOLVABLE", "PRIVATE-field": "PRIVATE-token",
        }, headers={"X-Test-Header": "preserved"})

    with TestClient(test_app) as client:
        response = client.get("/framework-error")
    assert response.status_code == 404
    assert response.headers["X-Test-Header"] == "preserved"
    assert response.json() == {"error_code": None, "message": "请求的资源不存在"}
    assert "type=dict, size=2, error_code=DOI_UNRESOLVABLE" in caplog.text
    assert "PRIVATE" not in caplog.text + response.text


@pytest.mark.parametrize("kwargs,expected", [
    ({"json": {}}, "body.claim: missing"),
    ({"json": {"claim": {"PRIVATE-field": "PRIVATE-value"}}}, "body.claim: string_type"),
    ({"json": {"PRIVATE-field": "PRIVATE-value"}}, "body.<unknown>: extra_forbidden"),
    ({"content": '{"claim": "PRIVATE-value",', "headers": {"Content-Type": "application/json"}}, "json_invalid"),
])
def test_validation_errors_expose_locations_without_input_values(kwargs, expected):
    with TestClient(app) as client:
        response = client.post("/api/checks", **kwargs)
    assert response.status_code == 422
    assert set(response.json()) == {"error_code", "message"}
    assert response.json()["error_code"] is None
    assert expected in response.json()["message"]
    assert "PRIVATE" not in response.text


def test_validation_errors_locate_query_fields_and_array_indices():
    with TestClient(app) as client:
        query = client.get("/api/checks", params={"status": "PRIVATE-value"})
        body = client.post("/api/checks", json={"authorized_recipients": [{"PRIVATE-field": "PRIVATE-value"}]})
    assert query.status_code == body.status_code == 422
    assert "query.status: enum" in query.json()["message"]
    assert "body.authorized_recipients.0: string_type" in body.json()["message"]
    assert "PRIVATE" not in query.text + body.text


def test_creation_conflict_needs_no_task_and_task_conflict_requires_state():
    schema = app.openapi()
    responses = schema["paths"]["/api/checks"]["post"]["responses"]
    assert responses["409"]["content"]["application/json"]["schema"]["$ref"].endswith("/ApiError")
    ApiError(error_code=None, message="配置已更改，请重新确认")
    with pytest.raises(ValidationError):
        ConflictResponse(error_code=None, message="当前状态不允许该操作")
    conflict = ConflictResponse(error_code=None, message="当前状态不允许该操作", status=TaskStatus.RUNNING, stage=Stage.FETCH)
    assert conflict.status is TaskStatus.RUNNING
