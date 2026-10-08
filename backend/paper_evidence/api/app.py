"""HTTP surface: health, run-config preview, source preview and task routes.

Business failures are mapped at the API boundary instead of raising structured
``HTTPException``. The source-preview mapping keeps its own real error codes; the
other routes map their own domain failures so a business 422 stays distinct from
a request-validation 422. Task execution itself never runs in this process.
"""

import logging
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from paper_evidence.api.deps import Services, get_services
from paper_evidence.config import narrowed_snapshot
from paper_evidence.domain import ContractError, ErrorCode, TaskStatus
from paper_evidence.domain.contracts import (
    ApiError,
    CancelResponse,
    CheckCreateRequest,
    CheckCreated,
    CheckDeleted,
    CheckDetail,
    CheckSummary,
    ConflictResponse,
    DiagnosticExportRequest,
    DiagnosticPacket,
    FeedbackRequest,
    FeedbackSaved,
    HealthResponse,
    RetryCreated,
    RetryRequest,
    RunConfigPreview,
    SourcePreview,
)
from paper_evidence.domain.records import TaskInput
from paper_evidence.domain.text import is_blank_claim
from paper_evidence.sources.doi import require_valid_doi
from paper_evidence.storage.sqlite import TERMINAL_STATUSES

logger = logging.getLogger(__name__)

# Only the source preview has an HTTP mapping for these domain failures.
SOURCE_PREVIEW_ERRORS = {
    ErrorCode.DOI_INVALID: (400, "DOI 格式无效"),
    ErrorCode.DOI_UNRESOLVABLE: (404, "DOI 无法解析"),
    ErrorCode.METADATA_NOT_FOUND: (422, "未找到文献元数据"),
    ErrorCode.REGISTRATION_AGENCY_UNSUPPORTED: (422, "暂不支持该 DOI 注册机构"),
    ErrorCode.UPSTREAM_AUTH_FAILED: (502, "上游认证或授权失败"),
    ErrorCode.UPSTREAM_INVALID_REQUEST: (502, "上游参数或协议不兼容"),
    ErrorCode.UPSTREAM_RATE_LIMITED: (503, "上游请求受到限流"),
    ErrorCode.UPSTREAM_UNAVAILABLE: (503, "上游服务暂不可用"),
    ErrorCode.UPSTREAM_TIMEOUT: (504, "上游请求超时"),
}


def _api_error(message: str) -> dict[str, None | str]:
    return {"error_code": None, "message": message}


def _fail(status: int, error_code: ErrorCode | None, message: str) -> JSONResponse:
    payload = ApiError(error_code=error_code, message=message).model_dump(mode="json")
    return JSONResponse(status_code=status, content=payload)


def _conflict(conflict: ConflictResponse) -> JSONResponse:
    return JSONResponse(status_code=409, content=conflict.model_dump(mode="json"))


app = FastAPI(
    title="Paper Evidence Agent",
    version="0.1.0",
    description="单条论断与指定被引文献之间的证据关系核验；模型调用经本机网关，任务由单独执行器处理。",
)


def _validation_location(request: Request, location: tuple[str | int, ...]) -> str:
    """Expose declared field names and array/JSON offsets, never extra input keys."""

    origin = location[0] if location and location[0] in {"body", "query", "path"} else "request"
    route = request.scope.get("route")
    names: set[str] = set()
    if origin == "body":
        body_field = getattr(route, "body_field", None)
        model = body_field.field_info.annotation if body_field is not None else None
        if isinstance(model, type) and issubclass(model, BaseModel):
            names = {field.alias or name for name, field in model.model_fields.items()}
    else:
        dependant = getattr(route, "dependant", None)
        names = {field.alias for field in getattr(dependant, f"{origin}_params", [])}
    parts = [origin]
    for part in location[1:]:
        if isinstance(part, int):
            parts.append(str(part))
        elif len(parts) == 1 and part in names:
            parts.append(part)
        else:
            parts.append("<unknown>")
    return ".".join(parts)


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    failures = [f"{_validation_location(request, error['loc'])}: {error['type']}" for error in exc.errors()]
    message = "请求不合法：" + "；".join(failures)
    return JSONResponse(status_code=422, content=_api_error(message))


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    if not isinstance(exc.detail, str):
        # Business failures must use ContractError. Log structure and a known
        # code only: raw keys/values may contain claims, credentials or URLs.
        code = exc.detail.get("error_code") if isinstance(exc.detail, dict) else None
        known_code = code if isinstance(code, str) and code in {item.value for item in ErrorCode} else None
        size = len(exc.detail) if isinstance(exc.detail, (dict, list, tuple)) else None
        logger.warning(
            "Structured HTTPException detail: type=%s, size=%s, error_code=%s",
            type(exc.detail).__name__, size, known_code,
        )
    message = {404: "请求的资源不存在", 405: "请求方法不被允许"}.get(
        exc.status_code, exc.detail if isinstance(exc.detail, str) else "请求不被允许"
    )
    return JSONResponse(status_code=exc.status_code, content=_api_error(message), headers=exc.headers)


@app.exception_handler(ContractError)
async def handle_contract_error(request: Request, exc: ContractError) -> JSONResponse:
    """Map preview failures only; task execution failures have their own boundary."""

    if (
        request.method != "GET"
        or request.url.path != "/api/sources/resolve"
        or exc.error_code not in SOURCE_PREVIEW_ERRORS
    ):
        raise exc
    status, message = SOURCE_PREVIEW_ERRORS[exc.error_code]
    content = ApiError(error_code=exc.error_code, message=message).model_dump(mode="json")
    return JSONResponse(status_code=status, content=content)


def _error_responses(*codes: int, task_conflict: bool = True) -> dict[int, dict[str, object]]:
    """Declare only the error statuses the architecture assigns to a route."""

    spec: dict[int, dict[str, object]] = {}
    for code in codes:
        model = ConflictResponse if code == 409 and task_conflict else ApiError
        spec[code] = {"model": model}
    return spec


def custom_openapi() -> dict[str, object]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
    api_error = {"$ref": "#/components/schemas/ApiError"}
    validation = {
        "description": "请求不合法时 error_code 为 null。来源预览的 422 还可携带 METADATA_NOT_FOUND 或 REGISTRATION_AGENCY_UNSUPPORTED。",
        "content": {"application/json": {"schema": api_error}},
    }
    for path_item in schema.get("paths", {}).values():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "delete", "patch"}:
                continue
            responses = operation.get("responses", {})
            if "422" in responses:
                responses["422"] = validation
    schemas = schema.setdefault("components", {}).setdefault("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


# --------------------------------------------------------------------- routes


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/sources/resolve", response_model=SourcePreview, responses=_error_responses(400, 404, 422, 502, 503, 504))
async def resolve_source(
    doi: Annotated[str, Query()],
    services: Annotated[Services, Depends(get_services)],
) -> SourcePreview:
    require_valid_doi(doi)  # DOI_INVALID is mapped by the preview handler
    return await services.source_service().resolve(doi)


@app.get("/api/run-config", response_model=RunConfigPreview, responses=_error_responses())
def get_run_config(services: Annotated[Services, Depends(get_services)]) -> RunConfigPreview:
    settings = services.settings
    return RunConfigPreview(
        profile=settings.profile,
        config_digest=settings.config_digest(),
        primary_recipient=settings.primary_recipient,
        fallback_recipients=list(settings.fallback_recipients),
        model_alias=settings.model_alias,
        data_scope=list(settings.data_scope),
        limits=settings.limits,
        timeouts=settings.timeouts,
        observability=settings.observability,
        criteria=settings.criteria(),
    )


@app.post(
    "/api/checks",
    response_model=CheckCreated,
    status_code=202,
    responses=_error_responses(400, 404, 409, task_conflict=False),
)
def create_check(
    body: CheckCreateRequest,
    services: Annotated[Services, Depends(get_services)],
) -> CheckCreated | JSONResponse:
    invalid = _validate_common(services, body.doi, body.claim, body.source_confirmed, body.cloud_consent,
                               body.authorized_recipients, body.config_digest)
    if invalid is not None:
        return invalid
    if body.previous_id is not None and services.store.get(body.previous_id) is None:
        return _fail(404, None, "关联的原任务不存在")
    task_id = uuid.uuid4().hex
    services.store.create(
        TaskInput(id=task_id, claim=body.claim, doi=body.doi, config_digest=body.config_digest,
                  authorized_recipients=tuple(body.authorized_recipients), previous_id=body.previous_id),
        narrowed_snapshot(services.settings, tuple(body.authorized_recipients)),
        services.settings.criteria(),
    )
    return CheckCreated(id=task_id, status="QUEUED")


@app.get("/api/checks", response_model=list[CheckSummary], responses=_error_responses())
def list_checks(
    services: Annotated[Services, Depends(get_services)],
    status: Annotated[TaskStatus | None, Query()] = None,
) -> list[CheckSummary]:
    return services.store.list(status)


@app.get("/api/checks/{id}", response_model=CheckDetail, responses=_error_responses(404))
def get_check(id: str, services: Annotated[Services, Depends(get_services)]) -> CheckDetail | JSONResponse:
    detail = services.store.get(id)
    if detail is None:
        return _fail(404, None, "任务不存在")
    return detail


@app.get("/api/checks/{id}/diagnostic-packet", response_model=DiagnosticPacket, responses=_error_responses(404))
def get_diagnostic_packet(
    id: str,
    services: Annotated[Services, Depends(get_services)],
) -> DiagnosticPacket | JSONResponse:
    if services.store.get(id) is None:
        return _fail(404, None, "任务不存在")
    return services.projector.redacted(id)


@app.post(
    "/api/checks/{id}/diagnostic-export",
    response_model=DiagnosticPacket,
    responses=_error_responses(400, 404, 409),
)
def export_diagnostic_packet(
    id: str,
    body: DiagnosticExportRequest,
    services: Annotated[Services, Depends(get_services)],
) -> DiagnosticPacket | JSONResponse:
    detail = services.store.get(id)
    if detail is None:
        return _fail(404, None, "任务不存在")
    if not body.semantic_export_consent:
        return _fail(400, None, "缺少语义导出授权")
    if services.store.source_record(id) is None:
        return _conflict(ConflictResponse(error_code=None, status=detail.status, stage=detail.stage,
                                          message="来源使用范围不允许导出"))
    run_config = services.store.get_run_config(id)
    authorized = run_config.authorized_recipients if run_config is not None else []
    if body.recipient not in authorized:
        return _fail(400, None, "接收方未获授权")
    return services.projector.consented(id, body.recipient)


@app.post("/api/checks/{id}/feedback", response_model=FeedbackSaved, responses=_error_responses(404))
def save_feedback(
    id: str,
    body: FeedbackRequest,
    services: Annotated[Services, Depends(get_services)],
) -> FeedbackSaved | JSONResponse:
    if not services.store.add_feedback(id, body.comment):
        return _fail(404, None, "任务不存在")
    return FeedbackSaved(id=id, saved=True)


@app.post(
    "/api/checks/{id}/retry",
    response_model=RetryCreated,
    status_code=202,
    responses=_error_responses(400, 404, 409),
)
def retry_check(
    id: str,
    body: RetryRequest,
    services: Annotated[Services, Depends(get_services)],
) -> RetryCreated | JSONResponse:
    detail = services.store.get(id)
    if detail is None:
        return _fail(404, None, "任务不存在")
    if detail.status not in TERMINAL_STATUSES:
        return _conflict(ConflictResponse(error_code=None, status=detail.status, stage=detail.stage,
                                          message="任务尚未结束，不能重试"))
    raw = services.store.get_input(id) or {}
    invalid = _validate_common(services, raw.get("doi", ""), raw.get("claim", ""), body.source_confirmed,
                               body.cloud_consent, body.authorized_recipients, body.config_digest)
    if invalid is not None:
        return invalid
    task_id = uuid.uuid4().hex
    services.store.create(
        TaskInput(id=task_id, claim=raw.get("claim", ""), doi=raw.get("doi", ""),
                  config_digest=body.config_digest, authorized_recipients=tuple(body.authorized_recipients),
                  previous_id=id),
        narrowed_snapshot(services.settings, tuple(body.authorized_recipients)),
        services.settings.criteria(),
    )
    return RetryCreated(id=task_id, status="QUEUED", previous_id=id)


@app.post(
    "/api/checks/{id}/cancel",
    response_model=CancelResponse,
    responses={200: {"model": CancelResponse}, 202: {"model": CancelResponse}, **_error_responses(404, 409)},
)
def cancel_check(id: str, services: Annotated[Services, Depends(get_services)]) -> JSONResponse:
    outcome = services.store.request_cancel(id)
    if outcome is None:
        return _fail(404, None, "任务不存在")
    if isinstance(outcome, ConflictResponse):
        return _conflict(outcome)
    status = 200 if outcome.status is TaskStatus.CANCELLED else 202
    return JSONResponse(status_code=status, content=outcome.model_dump(mode="json"))


@app.delete("/api/checks/{id}", response_model=CheckDeleted, responses=_error_responses(404, 409))
def delete_check(id: str, services: Annotated[Services, Depends(get_services)]) -> CheckDeleted | JSONResponse:
    detail = services.store.get(id)
    if detail is None:
        return _fail(404, None, "任务不存在")
    result = services.store.delete(id)
    if result == "conflict":
        return _conflict(ConflictResponse(error_code=None, status=detail.status, stage=detail.stage,
                                          message="任务尚未结束，不能删除"))
    return CheckDeleted(id=id, deleted=True, message="已删除本地记录；此操作不能撤回此前已经发生的云模型调用。")


def _validate_common(
    services: Services,
    doi: str,
    claim: str,
    source_confirmed: bool,
    cloud_consent: bool,
    authorized_recipients: list[str],
    config_digest: str,
) -> JSONResponse | None:
    """Shared create/retry input and authorization validation."""

    if not (source_confirmed and cloud_consent):
        return _fail(400, None, "需要同时确认来源与云调用授权")
    if is_blank_claim(claim):
        return _fail(400, None, "论断不能为空")
    try:
        require_valid_doi(doi)
    except ContractError:
        return _fail(400, ErrorCode.DOI_INVALID, "DOI 格式无效")
    if not authorized_recipients or services.settings.primary_recipient not in authorized_recipients:
        return _fail(400, None, "授权缺少主接收方")
    full = tuple({services.settings.primary_recipient, *services.settings.fallback_recipients})
    allowed = {
        services.settings.config_digest(full),
        services.settings.config_digest(tuple(authorized_recipients)),
    }
    if config_digest not in allowed:
        return _fail(409, None, "配置已更改，请重新预览并确认")
    return None
