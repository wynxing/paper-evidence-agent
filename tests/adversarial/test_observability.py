"""Observability export stays off by default (测试方案「对抗与安全」).

判定：Langfuse 默认关闭时零网络导出；未授权、配置缺失均不启用；启用后的故障
不改变核验状态、不增加业务重试。

导出面本身也在本维度：一条 ``ExecutionRecord`` 变成一条 span，属性只有允许清单里
的那几个标识；claim、正文段落、查询词与凭据都不出现在 span 里，也不出现在发给
接收方的 OTLP 载荷里。最后一条用例用本机 HTTP 接收器接住真实的 protobuf 请求，
验的是线上格式而不是内存对象。
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from doubles import CLAIM_MARKER, PARAGRAPH_MARKER, QUERY_MARKER, final_action, jats_with, query_action

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from paper_evidence.config import Settings
from paper_evidence.domain import Stage, TaskStatus
from paper_evidence.domain.contracts import ExecutionRecord
from paper_evidence.domain.records import TaskInput
from paper_evidence.tracing.otel import SPAN_ATTRIBUTES, build_recorder

PUBLIC_KEY = "pk-lf-test-public"
SECRET_KEY = "sk-lf-test-secret"


def _complete_env(monkeypatch, host: str = "http://127.0.0.1:9") -> Settings:
    """The full configuration that makes export effective, as environment only."""

    monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_ENABLED", "1")
    monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_HOST", host)
    monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_PUBLIC_KEY", PUBLIC_KEY)
    monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_SECRET_KEY", SECRET_KEY)
    monkeypatch.setenv("PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT", "External Reviewer")
    return Settings.from_env()


def test_langfuse_is_off_unless_explicitly_enabled(monkeypatch):
    """默认关闭；只有显式真值才启用（其余配置齐备时）。"""

    monkeypatch.delenv("PAPER_EVIDENCE_LANGFUSE_ENABLED", raising=False)
    assert Settings.from_env().observability.langfuse_enabled is False

    for value in ("", "0", "false", "no", "off"):
        monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_ENABLED", value)
        assert Settings.from_env().observability.langfuse_enabled is False, value

    for value in ("1", "true", "yes"):
        monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_ENABLED", value)
        monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_HOST", "http://127.0.0.1:9")
        monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_PUBLIC_KEY", PUBLIC_KEY)
        monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_SECRET_KEY", SECRET_KEY)
        monkeypatch.setenv("PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT", "External Reviewer")
        assert Settings.from_env().observability.langfuse_enabled is True, value


@pytest.mark.parametrize(
    "missing",
    [
        "PAPER_EVIDENCE_LANGFUSE_HOST",
        "PAPER_EVIDENCE_LANGFUSE_PUBLIC_KEY",
        "PAPER_EVIDENCE_LANGFUSE_SECRET_KEY",
        "PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT",
    ],
)
def test_a_partial_langfuse_configuration_is_not_enabled(monkeypatch, missing, caplog):
    """端点、两把密钥、观测接收方缺一，快照就不能写「在导出」。"""

    _complete_env(monkeypatch)
    monkeypatch.delenv(missing, raising=False)

    with caplog.at_level("WARNING"):
        settings = Settings.from_env()

    assert settings.observability.langfuse_enabled is False
    assert build_recorder(settings, exporter=InMemorySpanExporter()) is None
    assert any(missing in line for line in caplog.messages), caplog.messages


def test_a_missing_observability_recipient_stays_unset(monkeypatch):
    """配置缺失时不产生观测接收方。"""

    monkeypatch.delenv("PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT", raising=False)
    monkeypatch.delenv("PAPER_EVIDENCE_LANGFUSE_RECIPIENT", raising=False)
    assert Settings.from_env().observability.recipient is None


def test_a_blank_observability_recipient_counts_as_unset(monkeypatch):
    """全空白不是合法接收方标识。"""

    monkeypatch.setenv("PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT", "   ")
    assert Settings.from_env().observability.recipient is None


def test_enabling_observability_does_not_change_the_task(run_workflow, monkeypatch):
    """启用观测不改变核验状态，也不增加业务请求。"""

    text = "The treatment reduced mortality."
    _complete_env(monkeypatch)

    run = run_workflow(
        claim=text,
        jats_bytes=jats_with([text]),
        outputs=[query_action("mortality"), final_action(1, text)],
    )

    assert run.detail.status is TaskStatus.COMPLETED
    assert run.detail.label == "支持"
    # 一个查询生成 + 一个判断，观测开启不产生额外模型请求。
    assert len(run.gateway.request_ids) == 2


def test_each_step_becomes_one_span_in_the_task_trace(run_workflow, monkeypatch):
    """一条执行记录一条 span，全部挂在同一个 task trace 下。"""

    text = "The treatment reduced mortality."
    settings = _complete_env(monkeypatch)
    sink = InMemorySpanExporter()
    recorder = build_recorder(settings, exporter=sink)

    run = run_workflow(
        claim=text,
        jats_bytes=jats_with([text]),
        outputs=[query_action("mortality"), final_action(1, text)],
        tracing=recorder,
    )
    recorder.shutdown()
    assert run.detail.status is TaskStatus.COMPLETED

    spans = sink.get_finished_spans()
    root = next(span for span in spans if span.name == "paper-evidence check")
    children = [span for span in spans if span is not root]
    assert {span.name for span in children} >= {"fetch.full_text_source", "decision.model_gateway"}
    assert len({span.context.trace_id for span in spans}) == 1
    assert {span.parent.span_id for span in children} == {root.context.span_id}

    # 每条 span 都带同一份冻结配置摘要，才能按运行分组比较。
    assert {span.attributes["run.config_digest"] for span in spans} == {"adv"}
    fetch = next(span for span in children if span.name == "fetch.full_text_source")
    assert fetch.attributes["paper_evidence.stage"] == "fetch"
    assert fetch.attributes["paper_evidence.status"] == "success"
    assert fetch.attributes["run.prompt_version"].startswith("paper-prompt-")


def test_spans_carry_only_allow_listed_identifiers_and_never_the_content(
    run_workflow, monkeypatch
):
    """属性必须落在允许清单内；claim、正文、查询词一个都不能外泄。"""

    settings = _complete_env(monkeypatch)
    sink = InMemorySpanExporter()
    recorder = build_recorder(settings, exporter=sink)

    text = f"{QUERY_MARKER} reduced mortality by 20 percent ({PARAGRAPH_MARKER})."
    run = run_workflow(
        claim=CLAIM_MARKER,
        jats_bytes=jats_with([text]),
        outputs=[query_action(QUERY_MARKER), final_action(1, text)],
        tracing=recorder,
    )
    recorder.shutdown()
    assert run.detail.status is TaskStatus.COMPLETED

    spans = sink.get_finished_spans()
    assert spans
    for span in spans:
        assert set(span.attributes) <= SPAN_ATTRIBUTES, span.name
        blob = " ".join(str(value) for value in span.attributes.values())
        for marker in (CLAIM_MARKER, PARAGRAPH_MARKER, QUERY_MARKER):
            assert marker not in blob, span.name


def test_a_broken_exporter_changes_neither_the_result_nor_the_local_record(
    run_workflow, monkeypatch
):
    """接收方不可用只丢 span，不改核验状态，也不丢本地执行记录。"""

    class BrokenExporter(SpanExporter):
        def export(self, spans):
            raise RuntimeError("collector is down")

        def shutdown(self):
            return None

    text = "The treatment reduced mortality."
    settings = _complete_env(monkeypatch)
    recorder = build_recorder(settings, exporter=BrokenExporter())

    run = run_workflow(
        claim=text,
        jats_bytes=jats_with([text]),
        outputs=[query_action("mortality"), final_action(1, text)],
        tracing=recorder,
    )
    recorder.shutdown()

    assert run.detail.status is TaskStatus.COMPLETED
    assert run.detail.label == "支持"
    assert len(run.store.execution(run.task_id)) >= 3


def test_the_exporter_speaks_otlp_http_to_the_langfuse_path(monkeypatch, tmp_path):
    """真实 exporter、真实 HTTP：路径、认证头、protobuf 载荷都按 Langfuse 的约定。"""

    received: list[tuple[str, dict, bytes]] = []

    class Collector(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 - http.server naming
            length = int(self.headers.get("Content-Length", "0"))
            received.append((self.path, dict(self.headers), self.rfile.read(length)))
            self.send_response(200)
            self.send_header("Content-Type", "application/x-protobuf")
            self.end_headers()

        def log_message(self, *args):  # noqa: D102 - silence the test server
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Collector)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        settings = _complete_env(monkeypatch, host=f"http://127.0.0.1:{server.server_port}")
        recorder = build_recorder(settings)
        task = TaskInput(id="otel-1", claim="c", doi="10.1000/otel", config_digest="digest-1",
                         authorized_recipients=("Agnes",))
        recorder.begin(task)
        recorder.record(
            "otel-1",
            ExecutionRecord(
                stage=Stage.FETCH,
                span_id="span:otel-1:1",
                tool="full_text_source",
                status="success",
                error_code=None,
                duration_ms=12,
                round=None,
                request_id=None,
            ),
        )
        recorder.finish("otel-1")
        recorder.shutdown()
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert received, "exporter 没有发出请求"
    path, headers, body = received[0]
    assert path == "/api/public/otel/v1/traces"
    # http.server 保留客户端发来的头名大小写，取值时不依赖它。
    lowered = {name.lower(): value for name, value in headers.items()}
    assert lowered["authorization"] == "Basic cGstbGYtdGVzdC1wdWJsaWM6c2stbGYtdGVzdC1zZWNyZXQ="
    assert lowered["x-langfuse-ingestion-version"] == "4"

    request = ExportTraceServiceRequest()
    request.ParseFromString(body)
    names = {
        span.name
        for resource in request.resource_spans
        for scope in resource.scope_spans
        for span in scope.spans
    }
    assert {"paper-evidence check", "fetch.full_text_source"} <= names
    # 密钥在头里，不在载荷里；载荷里也没有 claim 或 DOI。
    assert SECRET_KEY.encode() not in body
    assert b"10.1000/otel" not in body


def test_export_off_by_default_builds_no_recorder(monkeypatch):
    """默认配置下没有 provider、没有导出线程，也就没有对外连接。"""

    monkeypatch.delenv("PAPER_EVIDENCE_LANGFUSE_ENABLED", raising=False)
    assert build_recorder(Settings.from_env()) is None


def test_a_sink_that_raises_does_not_fail_a_step(run_workflow):
    """观测写入抛异常时，步骤照常完成，本地执行记录照常落库。"""

    class BrokenSink:
        def begin(self, task):
            return None

        def record(self, task_id, event):
            raise RuntimeError("sink is broken")

        def finish(self, task_id):
            return None

    text = "The treatment reduced mortality."
    run = run_workflow(
        claim=text,
        jats_bytes=jats_with([text]),
        outputs=[query_action("mortality"), final_action(1, text)],
        tracing=BrokenSink(),
    )

    assert run.detail.status is TaskStatus.COMPLETED
    assert run.detail.label == "支持"
    assert len(run.store.execution(run.task_id)) >= 3
