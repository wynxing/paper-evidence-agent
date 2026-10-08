"""Task routes: creation, authorization, lifecycle control and diagnostics."""

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
