"""OpenTelemetry span recording, with Langfuse as an optional OTLP/HTTP sink.

The local ``execution`` table stays the diagnostic source of truth: the same
``ExecutionRecord`` that is written to SQLite is also turned into one span. The
span carries identifiers, stages, tool names, durations, error codes and the run's
``config_digest`` — never claims, DOIs, prompts, model output, quotes or
credentials. Redaction happens by construction (an allow-list of attributes), not
by filtering afterwards: a field that is not named here cannot be exported.

Export is off unless the endpoint, both keys and an authorized observability
recipient are configured (see ``tech-stack.md``「观测与归因」 and the decision in
``decisions.md``). When off, ``build_recorder`` returns ``None`` and the workflow
records locally only — no socket is opened, no span is created.

Failures never travel upstream: every method swallows its own exceptions and logs a
local warning. ``BatchSpanProcessor`` already exports on its own thread with a
bounded queue, so a slow or unreachable collector drops spans instead of blocking
the worker, and no business retry is added.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from typing import TYPE_CHECKING

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.trace import (
    NonRecordingSpan,
    Span,
    SpanContext,
    Status,
    StatusCode,
    TraceFlags,
    set_span_in_context,
)

from paper_evidence.config import PROMPT_VERSION
from paper_evidence.domain.contracts import ExecutionRecord

if TYPE_CHECKING:  # pragma: no cover - import cycle is type-only
    from paper_evidence.config import Settings
    from paper_evidence.domain.records import TaskInput

__all__ = ["OtelTraceRecorder", "build_recorder", "trace_id_for"]

TRACER_NAME = "paper_evidence"
SERVICE_NAME = "paper-evidence-agent"
LANGFUSE_TRACES_PATH = "/api/public/otel/v1/traces"
#: Langfuse 的实时摄取开关。不带头部时直接摄入的数据可能延迟十分钟才可见。
INGESTION_HEADERS = {"x-langfuse-ingestion-version": "4"}
#: Export must never become the slowest part of a task: the batch processor drops
#: what it cannot deliver inside this budget.
EXPORT_TIMEOUT_SECONDS = 3.0
MAX_QUEUE_SIZE = 512
MAX_EXPORT_BATCH = 128
SCHEDULE_DELAY_MS = 2000

#: Every attribute a span may carry. This is the redaction boundary: claims,
#: prompts, quotes, DOIs and credentials are not in the vocabulary, so a filter can
#: never be forgotten and no allow-list has to be re-derived from the record.
SPAN_ATTRIBUTES = frozenset(
    {
        "paper_evidence.task_id",
        "paper_evidence.span_id",
        "paper_evidence.stage",
        "paper_evidence.tool",
        "paper_evidence.status",
        "paper_evidence.error_code",
        "paper_evidence.duration_ms",
        "paper_evidence.round",
        "paper_evidence.request_id",
        "run.config_digest",
        "run.profile",
        "run.model_alias",
        "run.prompt_version",
    }
)

logger = logging.getLogger(__name__)


def trace_id_for(task_id: str) -> int:
    """A stable 128-bit trace id for a task.

    Deterministic rather than random so a retried or re-imported task keeps the
    same trace id: Langfuse groups by trace, and two runs of the same task that
    look unrelated would be hard to compare. OTLP trace ids must be non-zero.
    """

    return int.from_bytes(hashlib.sha256(task_id.encode("utf-8")).digest()[:16], "big") or 1


def _span_id_for(task_id: str) -> int:
    return int.from_bytes(hashlib.sha256(task_id.encode("utf-8")).digest()[16:24], "big") or 1


def build_recorder(settings: "Settings", *, exporter: SpanExporter | None = None) -> "OtelTraceRecorder | None":
    """Build the recorder, or ``None`` when observability export is off.

    ``exporter`` exists for tests and for callers that already own a collector; when
    omitted the Langfuse OTLP/HTTP exporter is built from the environment.
    """

    if not settings.observability.langfuse_enabled:
        return None
    sink = exporter if exporter is not None else langfuse_exporter(settings)
    if sink is None:
        return None

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": "0.1.0",
            "deployment.environment": settings.profile,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            sink,
            max_queue_size=MAX_QUEUE_SIZE,
            max_export_batch_size=MAX_EXPORT_BATCH,
            schedule_delay_millis=SCHEDULE_DELAY_MS,
            export_timeout_millis=int(EXPORT_TIMEOUT_SECONDS * 1000),
        )
    )
    return OtelTraceRecorder(provider, settings)


def langfuse_exporter(settings: "Settings") -> SpanExporter | None:
    """The OTLP/HTTP exporter for Langfuse, or ``None`` when it is not configured.

    The endpoint is ``<host>/api/public/otel/v1/traces`` and the credential is HTTP
    Basic over ``public_key:secret_key``. Neither the keys nor the encoded header is
    logged, stored in the snapshot or included in the digest.
    """

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    host = (settings.langfuse_host or "").strip().rstrip("/")
    public = os.environ.get(settings.langfuse_public_key_env) or ""
    secret = os.environ.get(settings.langfuse_secret_key_env) or ""
    if not host or not public or not secret:
        # ``from_env`` already refuses to mark this effective, so reaching here means
        # the object was built by hand; stay silent in export, loud in the log.
        logger.warning("Langfuse 端点或凭据不完整，观测导出未启用（本地轨迹照常记录）")
        return None

    credential = base64.b64encode(f"{public}:{secret}".encode("utf-8")).decode("ascii")
    headers = {"Authorization": f"Basic {credential}", **INGESTION_HEADERS}
    return OTLPSpanExporter(
        endpoint=f"{host}{LANGFUSE_TRACES_PATH}",
        headers=headers,
        timeout=EXPORT_TIMEOUT_SECONDS,
    )


class OtelTraceRecorder:
    """Turn one ``ExecutionRecord`` into one span under a per-task root span.

    The root span is what makes the stages of a task one trace in Langfuse; its
    duration is the task's, so the waterfall starts at the first stage. Child spans
    use the record's own duration rather than "time since the record was written",
    because the record is written when the step is already over.
    """

    def __init__(self, provider: TracerProvider, settings: "Settings") -> None:
        self._provider = provider
        self._tracer = provider.get_tracer(TRACER_NAME)
        self._roots: dict[str, Span] = {}
        self._digests: dict[str, str] = {}
        self._run_attributes = {
            "run.profile": settings.profile,
            "run.model_alias": settings.model_alias,
            "run.prompt_version": PROMPT_VERSION,
        }

    # ------------------------------------------------------------ lifecycle

    def begin(self, task: "TaskInput") -> None:
        """Open the task's root span. Never raises."""

        try:
            root = self._tracer.start_span(
                name="paper-evidence check",
                attributes={
                    "paper_evidence.task_id": task.id,
                    "run.config_digest": task.config_digest,
                    **self._run_attributes,
                },
                start_time=time.time_ns(),
            )
            self._roots[task.id] = root
            self._digests[task.id] = task.config_digest
        except Exception as error:  # noqa: BLE001 - observation must not fail a task
            logger.warning("观测根 span 创建失败，已跳过导出：%s", type(error).__name__)

    def record(self, task_id: str, event: ExecutionRecord) -> None:
        """Emit one span for a finished step. Never raises."""

        try:
            end = time.time_ns()
            started = end - int((event.duration_ms or 0) * 1_000_000)
            span = self._tracer.start_span(
                name=f"{event.stage.value}.{event.tool}",
                context=set_span_in_context(self._parent_context(task_id)),
                start_time=started,
                attributes=self._attributes(task_id, event),
            )
            if event.status in {"error", "blocked"}:
                # The code, not the message: messages can quote the model output.
                span.set_status(Status(StatusCode.ERROR, event.error_code.value if event.error_code else event.status))
            span.end(end_time=end)
        except Exception as error:  # noqa: BLE001
            logger.warning("观测 span 写入失败，已跳过：%s", type(error).__name__)

    def finish(self, task_id: str) -> None:
        """Close the task's root span and release it. Never raises."""

        try:
            root = self._roots.pop(task_id, None)
            self._digests.pop(task_id, None)
            if root is not None:
                root.end(end_time=time.time_ns())
        except Exception as error:  # noqa: BLE001
            logger.warning("观测根 span 关闭失败：%s", type(error).__name__)

    def shutdown(self) -> None:
        """Flush pending spans within the export budget, then stop the worker thread."""

        try:
            self._provider.shutdown()
        except Exception as error:  # noqa: BLE001 - shutdown runs in process teardown
            logger.warning("观测导出关闭失败：%s", type(error).__name__)

    # -------------------------------------------------------------- internals

    def _parent_context(self, task_id: str):
        root = self._roots.get(task_id)
        if root is not None:
            return root
        # ``finish`` was never called (an interrupted process, a test that only
        # records): keep the deterministic trace id so the span is not orphaned
        # into a fresh trace of its own.
        return NonRecordingSpan(
            SpanContext(
                trace_id=trace_id_for(task_id),
                span_id=_span_id_for(task_id),
                is_remote=True,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )
        )

    def _attributes(self, task_id: str, event: ExecutionRecord) -> dict[str, object]:
        attributes: dict[str, object] = {
            "paper_evidence.task_id": task_id,
            "paper_evidence.span_id": event.span_id,
            "paper_evidence.stage": event.stage.value,
            "paper_evidence.tool": event.tool,
            "paper_evidence.status": event.status,
            "run.config_digest": self._digests.get(task_id, ""),
            **self._run_attributes,
        }
        if event.duration_ms is not None:
            attributes["paper_evidence.duration_ms"] = event.duration_ms
        if event.error_code is not None:
            attributes["paper_evidence.error_code"] = event.error_code.value
        if event.round is not None:
            attributes["paper_evidence.round"] = event.round
        if event.request_id is not None:
            attributes["paper_evidence.request_id"] = event.request_id
        return attributes
