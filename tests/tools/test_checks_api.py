"""Task routes: creation, authorization, lifecycle control and diagnostics."""

from dataclasses import replace

from paper_evidence.domain.contracts import Observability, SourceRecord

DOI = "10.1000/xyz123"


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
        title="Demo study", doi=DOI, pmcid="PMC123", license="CC BY", version="1",
        access_url="https://pmc.ncbi.nlm.nih.gov/articles/PMC123/",
        retrieved_at="2026-10-01T00:00:00+00:00", version_hash="a" * 64,
    ))


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
