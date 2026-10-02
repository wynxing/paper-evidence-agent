"""HTTP skeleton. Only health is implemented; all business routes return 501."""

from typing import Annotated, NoReturn

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from paper_evidence.domain import TaskStatus
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


class UnimplementedRoute(Exception):
    """A declared interface whose business implementation is pending."""


def pending() -> NoReturn:
    raise UnimplementedRoute


def _api_error(message: str) -> dict[str, None | str]:
    return {"error_code": None, "message": message}


app = FastAPI(
    title="Paper Evidence Agent — 项目骨架",
    version="0.1.0",
    description="业务接口尚未实现；符合请求类型的调用返回 501，不创建任务或核验结果。",
)


@app.exception_handler(UnimplementedRoute)
async def handle_pending(request: Request, exc: UnimplementedRoute) -> JSONResponse:
    return JSONResponse(status_code=501, content=_api_error("Not Implemented：功能待实现"))


@app.exception_handler(RequestValidationError)
async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content=_api_error("请求不合法"))


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "请求不被允许"
    return JSONResponse(status_code=exc.status_code, content=_api_error(message))


def _error_responses(*codes: int) -> dict[int, dict[str, object]]:
    """Declare only the error statuses the architecture assigns to a route.

    501 is a scaffold-only response. Remove it when that route is implemented.
    """

    spec: dict[int, dict[str, object]] = {501: {"model": ApiError, "description": "功能待实现"}}
    for code in codes:
        model = ConflictResponse if code == 409 else ApiError
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


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/sources/resolve", response_model=SourcePreview, responses=_error_responses(400, 404, 422, 502, 503, 504))
def resolve_source(doi: Annotated[str, Query()]) -> SourcePreview:
    pending()


@app.get("/api/run-config", response_model=RunConfigPreview, responses=_error_responses())
def get_run_config() -> RunConfigPreview:
    pending()


@app.post(
    "/api/checks",
    response_model=CheckCreated,
    status_code=202,
    responses=_error_responses(400, 404, 409),
)
def create_check(body: CheckCreateRequest) -> CheckCreated:
    pending()


@app.get("/api/checks", response_model=list[CheckSummary], responses=_error_responses())
def list_checks(status: Annotated[TaskStatus | None, Query()] = None) -> list[CheckSummary]:
    pending()


@app.get("/api/checks/{id}", response_model=CheckDetail, responses=_error_responses(404))
def get_check(id: str) -> CheckDetail:
    pending()


@app.get(
    "/api/checks/{id}/diagnostic-packet",
    response_model=DiagnosticPacket,
    responses=_error_responses(404),
)
def get_diagnostic_packet(id: str) -> DiagnosticPacket:
    pending()


@app.post(
    "/api/checks/{id}/diagnostic-export",
    response_model=DiagnosticPacket,
    responses=_error_responses(400, 404, 409),
)
def export_diagnostic_packet(id: str, body: DiagnosticExportRequest) -> DiagnosticPacket:
    pending()


@app.post("/api/checks/{id}/feedback", response_model=FeedbackSaved, responses=_error_responses(404))
def save_feedback(id: str, body: FeedbackRequest) -> FeedbackSaved:
    pending()


@app.post(
    "/api/checks/{id}/retry",
    response_model=RetryCreated,
    status_code=202,
    responses=_error_responses(400, 404, 409),
)
def retry_check(id: str, body: RetryRequest) -> RetryCreated:
    pending()


@app.post(
    "/api/checks/{id}/cancel",
    response_model=CancelResponse,
    responses={
        200: {"model": CancelResponse},
        202: {"model": CancelResponse},
        **_error_responses(404, 409),
    },
)
def cancel_check(id: str) -> CancelResponse:
    pending()


@app.delete("/api/checks/{id}", response_model=CheckDeleted, responses=_error_responses(404, 409))
def delete_check(id: str) -> CheckDeleted:
    pending()
