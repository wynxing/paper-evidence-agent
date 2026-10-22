"""The retry path carries the sensitive marker too (测试方案「对抗与安全」:91).

正常与失败路径已有覆盖：这两种情况下 redacted 包都会把论断换成占位符。重试不一样——
它会新建一条任务，并把原任务的论断原样复制过去。那条新任务如果没人检查，标记就会从
第三条路径漏出去，而恰恰是「重试」最容易被当成「同一件事」而不单独验。
"""

from dataclasses import replace

from paper_evidence.diagnosis.projector import REDACTION_PLACEHOLDER
from paper_evidence.domain.contracts import Observability, SourceRecord

DOI = "10.1000/xyz123"
MARKER = "PRIVATE-RETRY-MARKER-7f21"
RECIPIENT = "reviewer@example.org"


def _body(services):
    return {
        "claim": f"{MARKER} 治疗降低了死亡率。",
        "doi": DOI,
        "source_confirmed": True,
        "cloud_consent": True,
        "config_digest": services.settings.config_digest(),
        "authorized_recipients": [services.settings.primary_recipient],
    }


def _retry(client, services, task_id):
    return client.post(f"/api/checks/{task_id}/retry", json={
        "config_digest": services.settings.config_digest(),
        "authorized_recipients": [services.settings.primary_recipient],
        "cloud_consent": True,
        "source_confirmed": True,
    })


def test_the_retry_task_is_redacted_like_any_other_task(client, services):
    original = client.post("/api/checks", json=_body(services)).json()["id"]
    client.post(f"/api/checks/{original}/cancel")

    retried = _retry(client, services, original)
    assert retried.status_code == 202
    new_id = retried.json()["id"]
    assert retried.json()["previous_id"] == original

    packet = client.get(f"/api/checks/{new_id}/diagnostic-packet")
    assert packet.status_code == 200
    assert MARKER not in packet.text
    body = packet.json()
    assert body["input"]["claim"] == REDACTION_PLACEHOLDER
    assert body["input"]["privacy"] == "redacted"
    # 重试链在包里可追，且指向原任务。
    assert body["previous_id"] == original
    assert body["case_id"] == new_id


def test_the_retry_task_keeps_the_marker_only_where_consent_allows_it(client, services):
    """对照组：consented 包保留原句，说明上一条的「不可见」是脱敏而不是丢数据。"""

    services.settings = replace(
        services.settings,
        observability=Observability(langfuse_enabled=False, recipient=RECIPIENT),
    )
    original = client.post("/api/checks", json=_body(services)).json()["id"]
    client.post(f"/api/checks/{original}/cancel")
    new_id = _retry(client, services, original).json()["id"]
    # 来源范围检查需要一条已冻结记录；这是 consented 导出的前置条件。
    services.store.update_source(new_id, SourceRecord(
        title="Demo study", authors=["Ada Lovelace"], year=2026, doi=DOI, pmcid="PMC123",
        license="CC BY", version="1", access_url="https://example.org/a",
        retrieved_at="2026-10-01T00:00:00+00:00", version_hash="a" * 64, retrieval_form="full_text",
    ))

    denied = client.post(f"/api/checks/{new_id}/diagnostic-export", json={
        "recipient": "stranger@example.org", "semantic_export_consent": True,
    })
    assert denied.status_code == 400

    exported = client.post(f"/api/checks/{new_id}/diagnostic-export", json={
        "recipient": RECIPIENT, "semantic_export_consent": True,
    })
    assert exported.status_code == 200
    assert exported.json()["input"]["claim"].startswith(MARKER)
    assert exported.json()["input"]["privacy"] == "consented"
