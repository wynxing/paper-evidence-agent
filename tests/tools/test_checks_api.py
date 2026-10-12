"""Task routes: creation, authorization, lifecycle control and diagnostics."""

from dataclasses import replace

from paper_evidence.config import Settings
from paper_evidence.domain import TaskStatus
from paper_evidence.domain.contracts import EvidenceCandidate, Observability, SourceRecord
from paper_evidence.domain.records import SourceSnapshot
from paper_evidence.retrieval.jats import parse_jats

DOI = "10.1000/xyz123"

CONTEXT_JATS = b"""<?xml version="1.0" encoding="UTF-8"?>
<article xml:lang="en"><front><article-meta/></front><body>
<sec><title>Methods</title><p id="m1">First method paragraph.</p><p id="m2">Second method paragraph.</p></sec>
<sec><title>Results</title><p id="r1">The treatment reduced mortality.</p></sec>
</body></article>
"""


def body(services, **overrides):
    payload = {
        "claim": "The intervention reduced mortality.",
        "doi": DOI,
        "source_confirmed": True,
        "cloud_consent": True,
        "config_digest": services.settings.config_digest(),
        "authorized_recipients": [services.settings.primary_recipient],
    }
    payload.update(overrides)
    return payload


def create(client, services, **overrides):
    response = client.post("/api/checks", json=body(services, **overrides))
    return response


def record_source(services, task_id):
    """Give the task a licensed source so the export range check can pass."""

    services.store.update_source(task_id, SourceRecord(
        title="Demo study", authors=["Ada Lovelace"], year=2026, doi=DOI, pmcid="PMC123",
        license="CC BY", version="1",
        access_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC123/",
        retrieved_at="2026-10-01T00:00:00+00:00", version_hash="a" * 64,
    ))


def index_context_source(services, task_id, version_hash="a" * 64):
    """Freeze a three-paragraph source so a quoted one has real neighbours."""

    source_id = f"PMC123:{version_hash}"
    record = SourceRecord(
        title="Demo study", authors=["Ada Lovelace"], year=2026, doi=DOI, pmcid="PMC123",
        license="CC BY", version="1",
        access_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC123/",
        retrieved_at="2026-10-01T00:00:00+00:00", version_hash=version_hash,
    )
    snapshot = SourceSnapshot(source_id=source_id, metadata=record, jats_bytes=CONTEXT_JATS)
    paragraphs = parse_jats(snapshot)
    services.store.link_task_source(task_id, source_id)
    services.store.index_source(source_id, record, CONTEXT_JATS)
    services.store.index_paragraphs(source_id, paragraphs)
    return source_id, paragraphs


def retrieved(paragraph, rank=1):
    return EvidenceCandidate(paragraph_id=paragraph.paragraph_id, section=paragraph.section,
                             quote=paragraph.text, paragraph_hash=paragraph.paragraph_hash,
                             source_url=paragraph.source_url, round=0, rank=rank, entered_context=True)


def citing(paragraph):
    return {"agent": "paper", "label": "支持", "rationale": "原文支持该论断。",
            "supported_parts": [], "scope_differences": [], "limitations": [],
            "evidence": [{"paragraph_id": paragraph.paragraph_id, "quote": paragraph.text,
                          "section": paragraph.section, "source_url": paragraph.source_url,
                          "paragraph_hash": paragraph.paragraph_hash, "validation": "pass"}],
            "validation": "pass"}


def test_run_config_exposes_the_frozen_digest(client, services):
    response = client.get("/api/run-config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["config_digest"] == services.settings.config_digest()
    assert payload["limits"]["main_requests"] == 3
    assert payload["timeouts"]["task_seconds"] == 180
    assert payload["observability"]["langfuse_enabled"] is False
    assert payload["criteria"]["snapshot_ref"].startswith("criteria:sha256:")


def test_create_requires_confirmations_and_a_valid_doi(client, services):
    assert create(client, services, cloud_consent=False).status_code == 400
    assert create(client, services, source_confirmed=False).status_code == 400
    assert create(client, services, claim="   ").status_code == 400

    bad_doi = create(client, services, doi="not-a-doi")
    assert bad_doi.status_code == 400
    assert bad_doi.json()["error_code"] == "DOI_INVALID"

    missing_primary = create(client, services, authorized_recipients=["SomeoneElse"])
    assert missing_primary.status_code == 400


def test_create_rejects_a_stale_config_digest_without_a_task(client, services):
    response = create(client, services, config_digest="0" * 64)
    assert response.status_code == 409
    assert set(response.json()) == {"error_code", "message"}
    assert client.get("/api/checks").json() == []


def test_create_rejects_recipients_outside_the_configured_scope(client, services):
    """授权接收方必须是已配置范围的子集，附带匹配的摘要也不行。"""

    widened = [services.settings.primary_recipient, "Arbitrary Reader"]
    refused = create(client, services, authorized_recipients=widened,
                     config_digest=services.settings.config_digest(tuple(widened)))
    assert refused.status_code == 400
    assert client.get("/api/checks").json() == []


def test_authorized_recipients_may_narrow_but_never_widen(client, services):
    services.settings = replace(services.settings, fallback_recipients=("Bob",))
    primary = services.settings.primary_recipient

    # Narrowing to the primary recipient is allowed and recorded as narrowed.
    narrowed = create(client, services, authorized_recipients=[primary],
                      config_digest=services.settings.config_digest((primary,)))
    assert narrowed.status_code == 202
    packet = client.get(f"/api/checks/{narrowed.json()['id']}/diagnostic-packet").json()
    assert packet["run_config"]["authorized_recipients"] == [primary]

    # The full configured set still matches its own preview digest.
    assert create(client, services, authorized_recipients=[primary, "Bob"]).status_code == 202
    # An unconfigured fallback is refused even with a self-consistent digest.
    assert create(client, services, authorized_recipients=[primary, "Carol"],
                  config_digest=services.settings.config_digest((primary, "Carol"))).status_code == 400


def test_create_then_read_detail_and_history(client, services):
    created = create(client, services)
    assert created.status_code == 202
    assert created.json()["status"] == "QUEUED"
    task_id = created.json()["id"]

    listing = client.get("/api/checks").json()
    assert [item["id"] for item in listing] == [task_id]
    assert listing[0]["label"] is None

    detail = client.get(f"/api/checks/{task_id}").json()
    assert detail["status"] == "QUEUED"
    assert detail["stage"] == "wait"
    assert detail["decision"] is None
    assert detail["criteria"]["version"] == "0.6"
    assert detail["accounting"] == {
        "verification": "verified", "main_requests_used": 0, "repair_requests_used": 0,
        "supplemental_rounds_used": 0, "upstream_attempts_used": 0, "observed_upstream_attempts": 0,
        "reason": None,
    }
    assert detail["limits"]["main_requests"] == 3

    assert client.get("/api/checks/unknown").status_code == 404
    assert client.get("/api/checks/unknown/diagnostic-packet").status_code == 404


def test_previous_id_must_exist(client, services):
    assert create(client, services, previous_id="nope").status_code == 404


def test_cancel_queued_then_repeat_and_unknown(client, services):
    task_id = create(client, services).json()["id"]
    first = client.post(f"/api/checks/{task_id}/cancel")
    assert first.status_code == 200
    assert first.json()["status"] == "CANCELLED"
    assert first.json()["cancel_requested"] is True
    assert first.json()["label"] is None and first.json()["decision"] is None

    repeat = client.post(f"/api/checks/{task_id}/cancel")
    assert repeat.status_code == 200
    assert repeat.json()["status"] == "CANCELLED"

    assert client.post("/api/checks/unknown/cancel").status_code == 404


def test_retry_requires_a_terminal_task_and_links_the_original(client, services):
    task_id = create(client, services).json()["id"]
    conflict = client.post(f"/api/checks/{task_id}/retry", json={
        "config_digest": services.settings.config_digest(),
        "authorized_recipients": [services.settings.primary_recipient],
        "cloud_consent": True, "source_confirmed": True,
    })
    assert conflict.status_code == 409
    assert conflict.json()["status"] == "QUEUED"
    assert conflict.json()["stage"] == "wait"

    client.post(f"/api/checks/{task_id}/cancel")
    retry = client.post(f"/api/checks/{task_id}/retry", json={
        "config_digest": services.settings.config_digest(),
        "authorized_recipients": [services.settings.primary_recipient],
        "cloud_consent": True, "source_confirmed": True,
    })
    assert retry.status_code == 202
    assert retry.json()["previous_id"] == task_id
    assert retry.json()["id"] != task_id
    # The original record is kept.
    assert client.get(f"/api/checks/{task_id}").json()["status"] == "CANCELLED"


def test_delete_only_terminal_tasks_and_reports_the_cloud_boundary(client, services):
    task_id = create(client, services).json()["id"]
    blocked = client.delete(f"/api/checks/{task_id}")
    assert blocked.status_code == 409
    assert blocked.json()["status"] == "QUEUED"

    client.post(f"/api/checks/{task_id}/cancel")
    removed = client.delete(f"/api/checks/{task_id}")
    assert removed.status_code == 200
    assert removed.json()["deleted"] is True
    assert "云模型调用" in removed.json()["message"]
    assert client.get(f"/api/checks/{task_id}").status_code == 404
    assert client.delete("/api/checks/unknown").status_code == 404


def test_feedback_is_stored_separately(client, services):
    task_id = create(client, services).json()["id"]
    saved = client.post(f"/api/checks/{task_id}/feedback", json={"comment": "looks right"})
    assert saved.status_code == 200
    assert saved.json() == {"id": task_id, "saved": True}
    assert client.post("/api/checks/unknown/feedback", json={"comment": "x"}).status_code == 404


def test_diagnostic_packet_is_redacted_and_export_needs_consent(client, services):
    task_id = create(client, services).json()["id"]

    packet = client.get(f"/api/checks/{task_id}/diagnostic-packet")
    assert packet.status_code == 200
    payload = packet.json()
    assert payload["schema_version"] == "2.2"
    assert payload["input"]["doi"] == DOI
    assert payload["input"]["claim"] == "<redacted>"
    assert payload["input"]["privacy"] == "redacted"
    assert payload["decision"] is None

    no_consent = client.post(f"/api/checks/{task_id}/diagnostic-export",
                             json={"recipient": services.settings.primary_recipient,
                                   "semantic_export_consent": False})
    assert no_consent.status_code == 400

    # No licensed source was recorded for this queued task, so the range blocks it.
    range_blocked = client.post(f"/api/checks/{task_id}/diagnostic-export",
                                json={"recipient": services.settings.primary_recipient,
                                      "semantic_export_consent": True})
    assert range_blocked.status_code == 409
    assert range_blocked.json()["status"] == "QUEUED"

    unauthorized = client.post(f"/api/checks/{task_id}/diagnostic-export",
                               json={"recipient": "SomeoneElse", "semantic_export_consent": True})
    assert unauthorized.status_code in (400, 409)


def test_diagnostic_export_needs_a_configured_diagnostic_recipient(client, services):
    """没有配置观测/诊断接收方时不能导出，即使模型接收方已获授权。"""

    task_id = create(client, services).json()["id"]
    record_source(services, task_id)

    blocked = client.post(f"/api/checks/{task_id}/diagnostic-export",
                          json={"recipient": services.settings.primary_recipient,
                                "semantic_export_consent": True})
    assert blocked.status_code == 400
    assert set(blocked.json()) == {"error_code", "message"}


def test_diagnostic_export_accepts_only_the_observation_recipient(client, services):
    services.settings = replace(
        services.settings,
        observability=Observability(langfuse_enabled=False, recipient="External Reviewer"),
    )
    task_id = create(client, services).json()["id"]
    record_source(services, task_id)

    # 模型接收方（已授权模型调用）不等于诊断接收方。
    as_model = client.post(f"/api/checks/{task_id}/diagnostic-export",
                           json={"recipient": services.settings.primary_recipient,
                                 "semantic_export_consent": True})
    assert as_model.status_code == 400

    allowed = client.post(f"/api/checks/{task_id}/diagnostic-export",
                          json={"recipient": "External Reviewer", "semantic_export_consent": True})
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["input"]["recipient"] == "External Reviewer"
    assert payload["input"]["privacy"] == "consented"
    assert payload["run_config"]["observability"]["recipient"] == "External Reviewer"


def test_history_and_detail_expose_the_claim_bibliography_and_timing(client, services):
    task_id = create(client, services).json()["id"]

    row = client.get("/api/checks").json()[0]
    assert row["id"] == task_id
    assert row["claim_excerpt"] == "The intervention reduced mortality."
    assert row["created_at"]

    detail = client.get(f"/api/checks/{task_id}").json()
    assert detail["claim"] == "The intervention reduced mortality."
    assert detail["source"] is None
    # 排队阶段没有开始与结束时刻，界面据此显示真实计时而不是占位文案。
    assert detail["created_at"]
    assert detail["started_at"] is None and detail["finished_at"] is None

    record_source(services, task_id)
    with_source = client.get(f"/api/checks/{task_id}").json()
    assert with_source["source"]["title"] == "Demo study"
    assert with_source["source"]["authors"] == ["Ada Lovelace"]
    assert with_source["source"]["year"] == 2026


def test_history_is_filterable_and_keeps_the_claim_excerpt(client, services):
    task_id = create(client, services).json()["id"]
    assert [row["id"] for row in client.get("/api/checks", params={"status": "QUEUED"}).json()] == [task_id]
    assert client.get("/api/checks", params={"status": "COMPLETED"}).json() == []


def test_the_input_route_returns_exactly_what_was_submitted(client, services):
    """详情视图只在 `source` 里给 DOI，而 `source` 在来源身份解析成功前为 null —— 这是**详情视图**的空窗。

    本接口提供不必先列历史即可按任务取回提交原文，并给出该任务冻结的授权范围。
    它并非取得提交 DOI 的唯一路径：`CheckSummary` 也带 DOI，工作台早已从历史行
    回退预填「修改原句」「拆分论断」（`originalDoi` 的第二优先级即该行）。
    """

    submitted = "  The intervention reduced mortality.  "
    task_id = create(client, services, claim=submitted).json()["id"]

    response = client.get(f"/api/checks/{task_id}/input")
    assert response.status_code == 200
    assert response.json() == {
        "id": task_id,
        "claim": submitted,                       # 逐字返回，不折叠空白也不截断
        "doi": DOI,
        "previous_id": None,
        "config_digest": services.settings.config_digest(),
        "authorized_recipients": [services.settings.primary_recipient],
    }
    # 同一时刻的详情视图给不出 DOI —— 这是详情视图在该阶段的空窗。
    assert client.get(f"/api/checks/{task_id}").json()["source"] is None
    assert client.get("/api/checks/unknown/input").status_code == 404


def test_the_input_route_keeps_the_link_to_the_original_task(client, services):
    original = create(client, services).json()["id"]
    services.store.request_cancel(original)

    retried = create(client, services, previous_id=original).json()["id"]
    payload = client.get(f"/api/checks/{retried}/input").json()
    assert payload["previous_id"] == original
    assert payload["claim"] == "The intervention reduced mortality."


def test_evidence_context_reads_the_frozen_paragraphs_and_their_neighbours(client, services):
    task_id = create(client, services).json()["id"]
    source_id, paragraphs = index_context_source(services, task_id)
    # 序号 2 被检索到并进入上下文，序号 3 被最终判断引用。
    services.store.record_candidates(task_id, [retrieved(paragraphs[1])])
    assert services.store.finish(task_id, status=TaskStatus.COMPLETED, stage="evidence_validation",
                                 error_code=None, label="支持",
                                 decision=citing(paragraphs[2])) is True
    finished_at = client.get(f"/api/checks/{task_id}").json()["finished_at"]

    response = client.get(f"/api/checks/{task_id}/evidence-context")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == task_id
    assert payload["source_id"] == source_id
    # 两处锚点各自展开 ordinal±1，合起来正是 1..3 且按序号升序。
    assert [item["paragraph_id"] for item in payload["paragraphs"]] == [
        paragraph.paragraph_id for paragraph in paragraphs
    ]

    flags = {item["paragraph_id"]: (item["entered_context"], item["cited"])
             for item in payload["paragraphs"]}
    assert flags[paragraphs[0].paragraph_id] == (False, False)   # 仅作为邻段进入
    assert flags[paragraphs[1].paragraph_id] == (True, False)
    assert flags[paragraphs[2].paragraph_id] == (False, True)

    quoted = payload["paragraphs"][2]
    assert quoted["text"] == paragraphs[2].text                  # 冻结原文，不是脱敏占位
    assert quoted["section"] == "Results"
    assert quoted["paragraph_hash"] == paragraphs[2].paragraph_hash
    assert quoted["source_url"] == paragraphs[2].source_url
    assert "validation" not in quoted                            # 邻段只作上下文，不是证据

    # 只读投影：读过之后任务状态与结束时刻都不变。
    after = client.get(f"/api/checks/{task_id}").json()
    assert after["status"] == "COMPLETED" and after["finished_at"] == finished_at


def test_evidence_context_is_empty_until_a_source_is_frozen(client, services):
    """空数组表示「暂时没有内容」，不是「来源不存在」，也不是失败。"""

    task_id = create(client, services).json()["id"]
    response = client.get(f"/api/checks/{task_id}/evidence-context")
    assert response.status_code == 200
    assert response.json() == {"id": task_id, "source_id": None, "paragraphs": []}
    assert client.get("/api/checks/unknown/evidence-context").status_code == 404


def test_evidence_context_never_reads_across_sources(client, services):
    """跨来源段落标识解析为空：邻段读取只在冻结来源内，不泄漏别处的段落。"""

    task_id = create(client, services).json()["id"]
    source_id, _paragraphs = index_context_source(services, task_id)
    services.store.record_candidates(task_id, [
        EvidenceCandidate(paragraph_id=f"p:PMC999:{'b' * 64}:jats-0.1.0:2", section="Results",
                          quote="foreign paragraph", paragraph_hash="f" * 64,
                          source_url="https://example.invalid/elsewhere", round=0, rank=1,
                          entered_context=True),
    ])

    payload = client.get(f"/api/checks/{task_id}/evidence-context").json()
    assert payload["source_id"] == source_id
    assert payload["paragraphs"] == []


def test_a_frozen_digest_stops_being_accepted_once_the_effective_config_changes(client, services):
    """`/input` 给的是冻结摘要，而 POST 校验当前摘要——两者不等时必须 409。

    这是接前端时最容易踩的一处：把 `/input` 的 `config_digest` 直接回填进
    「修改原句」的重提请求，只要有效配置没变就能通过，配置一旦变过就会 409。
    """

    task_id = create(client, services).json()["id"]
    frozen = client.get(f"/api/checks/{task_id}/input").json()["config_digest"]
    # 刚创建的任务，冻结摘要就是当前有效摘要。
    assert frozen == services.settings.config_digest()

    # 有效配置未变：冻结摘要仍在允许集合内，重提被接受。
    assert create(client, services, config_digest=frozen, previous_id=task_id).status_code == 202

    # 有效配置改变后，同一个冻结摘要不再属于允许集合，重提被拒。
    services.settings = replace(
        services.settings, retrieval_context_limit=services.settings.retrieval_context_limit + 1
    )
    assert services.settings.config_digest() != frozen
    rejected = create(client, services, config_digest=frozen, previous_id=task_id)
    assert rejected.status_code == 409
    assert rejected.json() == {"error_code": None, "message": "配置已更改，请重新预览并确认"}


def test_diagnostic_export_rejects_a_blank_recipient_and_normalizes_spacing(client, services):
    """空白收件人不是合法标识；带首尾空格的已授权收件人按归一化值接受。"""

    services.settings = replace(
        services.settings,
        observability=Observability(langfuse_enabled=False, recipient="External Reviewer"),
    )
    task_id = create(client, services).json()["id"]
    record_source(services, task_id)

    for blank in ("", "   "):
        refused = client.post(f"/api/checks/{task_id}/diagnostic-export",
                              json={"recipient": blank, "semantic_export_consent": True})
        assert refused.status_code == 400
        assert set(refused.json()) == {"error_code", "message"}

    padded = client.post(f"/api/checks/{task_id}/diagnostic-export",
                         json={"recipient": "  External Reviewer  ", "semantic_export_consent": True})
    assert padded.status_code == 200
    assert padded.json()["input"]["recipient"] == "External Reviewer"


def test_recipient_configuration_is_trimmed(monkeypatch):
    """配置写成 "A, B" 时不产生带首尾空格的收件人名，前后端与摘要才一致。"""

    monkeypatch.setenv("PAPER_EVIDENCE_PRIMARY_RECIPIENT", "  Agnes  ")
    monkeypatch.setenv("PAPER_EVIDENCE_FALLBACK_RECIPIENTS", " Bob ,, Carol ")
    monkeypatch.setenv("PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT", "  External Reviewer ")
    settings = Settings.from_env()
    assert settings.primary_recipient == "Agnes"
    assert settings.fallback_recipients == ("Bob", "Carol")
    assert settings.observability.recipient == "External Reviewer"


def test_blank_recipient_configuration_counts_as_unset(monkeypatch):
    monkeypatch.setenv("PAPER_EVIDENCE_PRIMARY_RECIPIENT", "   ")
    monkeypatch.setenv("PAPER_EVIDENCE_FALLBACK_RECIPIENTS", " , ")
    monkeypatch.setenv("PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT", "   ")
    settings = Settings.from_env()
    assert settings.primary_recipient == "Agnes"
    assert settings.fallback_recipients == ()
    assert settings.observability.recipient is None


def test_the_in_process_sdk_is_the_default_transport(monkeypatch):
    """A gateway process must not be a prerequisite for calling a model."""

    from paper_evidence.config import MODEL_TRANSPORT_SDK

    monkeypatch.delenv("PAPER_EVIDENCE_MODEL_TRANSPORT", raising=False)
    assert Settings.from_env().model_transport == MODEL_TRANSPORT_SDK


def test_an_unknown_transport_falls_back_to_the_default(monkeypatch):
    from paper_evidence.config import MODEL_TRANSPORT_GATEWAY, MODEL_TRANSPORT_SDK

    monkeypatch.setenv("PAPER_EVIDENCE_MODEL_TRANSPORT", "  Gateway ")
    assert Settings.from_env().model_transport == MODEL_TRANSPORT_GATEWAY
    monkeypatch.setenv("PAPER_EVIDENCE_MODEL_TRANSPORT", "nonsense")
    assert Settings.from_env().model_transport == MODEL_TRANSPORT_SDK


def test_the_snapshot_records_which_kind_of_endpoint_is_reached(monkeypatch):
    """The preview must not describe a route other than the one in use."""

    from paper_evidence.config import MODEL_TRANSPORT_GATEWAY, config_snapshot

    monkeypatch.delenv("PAPER_EVIDENCE_MODEL_API_BASE", raising=False)
    settings = Settings.from_env()
    assert config_snapshot(settings)["model"]["transport"] == "sdk"
    assert config_snapshot(settings)["model"]["base_url_class"] == "provider_default"
    assert config_snapshot(replace(settings, model_api_base="https://models.test/v1"))[
        "model"]["base_url_class"] == "configured_endpoint"
    assert config_snapshot(replace(settings, model_transport=MODEL_TRANSPORT_GATEWAY))[
        "model"]["base_url_class"] == "local_gateway"


def test_the_transport_is_part_of_the_frozen_digest(services):
    from paper_evidence.config import MODEL_TRANSPORT_GATEWAY

    assert replace(services.settings, model_transport=MODEL_TRANSPORT_GATEWAY).config_digest() != (
        services.settings.config_digest()
    )


def test_the_configured_transport_decides_which_gateway_is_built(services):
    from paper_evidence.api.deps import Services
    from paper_evidence.config import MODEL_TRANSPORT_GATEWAY
    from paper_evidence.models.gateway import OpenAIChatGateway

    assert not isinstance(services.gateway(), OpenAIChatGateway)
    proxied = Services(replace(services.settings, model_transport=MODEL_TRANSPORT_GATEWAY))
    try:
        built = proxied.gateway()
        assert isinstance(built, OpenAIChatGateway)
        assert built.model_alias == "paper-default"
    finally:
        proxied.close()
