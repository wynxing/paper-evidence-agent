"""HTTP skeleton. Only health is implemented; all business routes return 501."""

from typing import Annotated, NoReturn

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from paper_evidence.domain import TaskStatus
from paper_evidence.domain.contracts import (
    ApiError,
    CancelResponse,
    CheckCreateRequest,
    CheckCreated,
    CheckDeleted,
    CheckDetail,
    CheckSummary,
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


app = FastAPI(
    title="Paper Evidence Agent — 项目骨架",
    version="0.1.0",
    description="业务接口尚未实现；符合请求类型的调用返回 501，不创建任务或核验结果。",
)


@app.exception_handler(UnimplementedRoute)
async def handle_pending(request: Request, exc: UnimplementedRoute) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"error_code": None, "message": "Not Implemented：功能待实现"},
    )


PENDING_RESPONSE = {501: {"model": ApiError, "description": "功能待实现"}}


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/sources/resolve", response_model=SourcePreview, responses=PENDING_RESPONSE)
def resolve_source(doi: Annotated[str, Query()]) -> SourcePreview:
    pending()


@app.get("/api/run-config", response_model=RunConfigPreview, responses=PENDING_RESPONSE)
def get_run_config() -> RunConfigPreview:
    pending()


@app.post("/api/checks", response_model=CheckCreated, status_code=202, responses=PENDING_RESPONSE)
def create_check(body: CheckCreateRequest) -> CheckCreated:
    pending()


@app.get("/api/checks", response_model=list[CheckSummary], responses=PENDING_RESPONSE)
def list_checks(status: Annotated[TaskStatus | None, Query()] = None) -> list[CheckSummary]:
    pending()


@app.get("/api/checks/{id}", response_model=CheckDetail, responses=PENDING_RESPONSE)
def get_check(id: str) -> CheckDetail:
    pending()


@app.get("/api/checks/{id}/diagnostic-packet", response_model=DiagnosticPacket, responses=PENDING_RESPONSE)
def get_diagnostic_packet(id: str) -> DiagnosticPacket:
    pending()


@app.post("/api/checks/{id}/diagnostic-export", response_model=DiagnosticPacket, responses=PENDING_RESPONSE)
def export_diagnostic_packet(id: str, body: DiagnosticExportRequest) -> DiagnosticPacket:
    pending()


@app.post("/api/checks/{id}/feedback", response_model=FeedbackSaved, responses=PENDING_RESPONSE)
def save_feedback(id: str, body: FeedbackRequest) -> FeedbackSaved:
    pending()


@app.post("/api/checks/{id}/retry", response_model=RetryCreated, status_code=202, responses=PENDING_RESPONSE)
def retry_check(id: str, body: RetryRequest) -> RetryCreated:
    pending()


@app.post("/api/checks/{id}/cancel", response_model=CancelResponse, responses=PENDING_RESPONSE)
def cancel_check(id: str) -> CancelResponse:
    pending()


@app.delete("/api/checks/{id}", response_model=CheckDeleted, responses=PENDING_RESPONSE)
def delete_check(id: str) -> CheckDeleted:
    pending()
