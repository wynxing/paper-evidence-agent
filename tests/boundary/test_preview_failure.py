"""A failed preview must not leave a fabricated BLOCKED task (测试方案「边界与异常」:106).

预览是只读的：上游不可用时返回对应状态与独立错误码，既不创建任务，也不留下一条
「BLOCKED」记录。BLOCKED 只在任务已入队、来源重查失败时出现——两者混在一起，
作者会以为「这篇文献不能用」，而实际只是刚才那次请求没打通。
"""

import pytest

from paper_evidence.domain import ContractError, ErrorCode

DOI = "10.1000/xyz123"


class _BrokenSource:
    """The port the API depends on, failing the way an upstream would."""

    def __init__(self, code: ErrorCode) -> None:
        self._code = code

    async def resolve(self, doi, deadline=None):
        raise ContractError(self._code, "upstream failed")


@pytest.mark.parametrize("code,status", [
    (ErrorCode.DOI_UNRESOLVABLE, 404),
    (ErrorCode.METADATA_NOT_FOUND, 422),
    (ErrorCode.REGISTRATION_AGENCY_UNSUPPORTED, 422),
    (ErrorCode.UPSTREAM_RATE_LIMITED, 503),
    (ErrorCode.UPSTREAM_TIMEOUT, 504),
])
def test_a_failed_preview_returns_an_error_envelope_and_creates_no_task(
    client, services, monkeypatch, code, status
):
    monkeypatch.setattr(services, "source_service", lambda: _BrokenSource(code))

    response = client.get("/api/sources/resolve", params={"doi": DOI})

    assert response.status_code == status
    payload = response.json()
    # 不是任务形状：没有 status / stage / label，只有 error_code 与 message。
    assert set(payload) == {"error_code", "message"}
    assert payload["error_code"] == code.value
    assert client.get("/api/checks").json() == []


def test_a_failed_preview_does_not_fabricate_a_blocked_task(client, services, monkeypatch):
    """预览失败后既无任务、也无 BLOCKED：那条终态属于「已入队后来源重查失败」。"""

    monkeypatch.setattr(services, "source_service",
                        lambda: _BrokenSource(ErrorCode.UPSTREAM_UNAVAILABLE))

    response = client.get("/api/sources/resolve", params={"doi": DOI})
    assert response.status_code == 503

    assert client.get("/api/checks").json() == []
    assert services.store.list() == []


def test_the_same_route_still_succeeds_once_the_source_answers(client, services, monkeypatch):
    """反向对照：只证明「失败没建任务」不够，还得证明这条路由本来能成功。"""

    class _Ok:
        async def resolve(self, doi, deadline=None):
            from paper_evidence.domain.contracts import SourcePreview

            return SourcePreview(doi=doi, title="Demo", authors=["Ada"], year=2026)

    monkeypatch.setattr(services, "source_service", lambda: _Ok())

    response = client.get("/api/sources/resolve", params={"doi": DOI})

    assert response.status_code == 200
    assert response.json()["title"] == "Demo"
    assert client.get("/api/checks").json() == []
