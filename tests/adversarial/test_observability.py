"""Observability export stays off by default (测试方案「对抗与安全」).

判定：Langfuse 默认关闭时零网络导出；未授权、配置缺失均不启用；启用后的故障
不改变核验状态、不增加业务重试。

说明：本仓库尚未实现 Langfuse 导出（``tracing/`` 只有本地 SQLite 记录器），
因此"启用后的故障隔离"没有可测对象，相关断言只覆盖"启用不改变核验结果"。
"""

import pytest

from conftest import final_action, jats_with, query_action

from paper_evidence.config import Settings
from paper_evidence.domain import TaskStatus


def test_langfuse_is_off_unless_explicitly_enabled(monkeypatch):
    """默认关闭；只有显式真值才启用。"""

    monkeypatch.delenv("PAPER_EVIDENCE_LANGFUSE_ENABLED", raising=False)
    assert Settings.from_env().observability.langfuse_enabled is False

    for value in ("", "0", "false", "no", "off"):
        monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_ENABLED", value)
        assert Settings.from_env().observability.langfuse_enabled is False, value

    for value in ("1", "true", "yes"):
        monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_ENABLED", value)
        assert Settings.from_env().observability.langfuse_enabled is True, value


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
    monkeypatch.setenv("PAPER_EVIDENCE_LANGFUSE_ENABLED", "1")
    monkeypatch.setenv("PAPER_EVIDENCE_OBSERVABILITY_RECIPIENT", "External Reviewer")

    run = run_workflow(
        claim=text,
        jats_bytes=jats_with([text]),
        outputs=[query_action("mortality"), final_action(1, text)],
    )

    assert run.detail.status is TaskStatus.COMPLETED
    assert run.detail.label == "支持"
    # 一个查询生成 + 一个判断，观测开启不产生额外模型请求。
    assert len(run.gateway.request_ids) == 2
