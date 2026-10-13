"""Untrusted source text cannot redirect the task (测试方案「对抗与安全」).

被测模块：``graph/`` 对不可信输入的处理，以及 ``sources/`` 的端点限制。
判定：来源文本里的指令不得改变任务目标，不得让模型指定任意网址，也不得让
连接器离开官方只读端点。
"""

import asyncio

import httpx

from doubles import (
    CLAIM_MARKER,
    INJECTION,
    PMCID,
    VERSION_HASH,
    final_action,
    jats_with,
    query_action,
)

from paper_evidence.agents.prompts import UNTRUSTED_NOTICE
from paper_evidence.domain import ErrorCode, TaskStatus
from paper_evidence.sources.crossref import CrossrefClient, DoiResolver
from paper_evidence.sources.http import Fetcher

OFFICIAL_CROSSREF = "https://api.crossref.org"
OFFICIAL_DOI = "https://doi.org"


def test_an_instruction_inside_the_source_reaches_the_model_as_data(run_workflow):
    """注入指令会进入 prompt，但必须以不可信数据的身份进入。"""

    text = f"The treatment reduced mortality. {INJECTION}"
    run = run_workflow(
        claim="The treatment reduced mortality.",
        jats_bytes=jats_with([text]),
        outputs=[query_action("mortality"), final_action(1, text)],
    )

    decision_prompt = next(p for p in run.gateway.prompts if "候选原文片段" in p)
    # 若注入文本没进 prompt，本用例就在测别的东西。
    assert "evil.example" in decision_prompt
    assert UNTRUSTED_NOTICE in decision_prompt, "候选段落必须被标为不可信数据"
    assert run.detail.status is TaskStatus.COMPLETED
    assert run.detail.label == "支持"


def test_the_injection_does_not_reach_the_query_stage_and_keeps_the_task_goal(run_workflow):
    """任务目标与来源绑定不因注入文本改变；查询阶段看不到正文。"""

    claim = f"The treatment reduced mortality. {CLAIM_MARKER}"
    text = f"The treatment reduced mortality. {INJECTION}"
    run = run_workflow(
        claim=claim,
        jats_bytes=jats_with([text]),
        outputs=[query_action("mortality"), final_action(1, text)],
    )

    assert run.detail.claim == claim, "提交的原句未被改写"
    assert run.detail.source.doi == "10.1000/adversarial", "来源绑定未被改写"

    query_prompt = next(p for p in run.gateway.prompts if "候选原文片段" not in p)
    # 查询生成发生在取回之前，正文里的指令不该出现在这里。
    assert INJECTION not in query_prompt
    assert "evil.example" not in query_prompt


def test_the_model_cannot_cite_a_paragraph_that_never_entered_the_context(run_workflow):
    """模型不能为未进入上下文的段落作证。"""

    texts = ["The treatment reduced mortality."]
    run = run_workflow(
        claim="The treatment reduced mortality.",
        jats_bytes=jats_with(texts),
        # 第 2 段不存在；修复请求给出同样的错误引用。
        outputs=[query_action("mortality"), final_action(2, "irrelevant"), final_action(2, "irrelevant")],
    )

    assert run.detail.status is TaskStatus.FAILED
    assert run.detail.error_code is ErrorCode.QUOTE_MISMATCH
    assert run.detail.label is None, "拒判时不得发布确定判断"


def test_the_model_cannot_supply_the_bibliography(run_workflow):
    """来源字段只能来自冻结原文，模型输出无法改写它们。"""

    text = "The treatment reduced mortality."
    run = run_workflow(
        claim=text,
        jats_bytes=jats_with([text]),
        outputs=[query_action("mortality"), final_action(1, text)],
    )

    source = run.detail.source
    assert source is not None
    assert source.pmcid == PMCID
    assert source.version_hash == VERSION_HASH
    # 模型输出里只有 paragraph_id 与 quote 两个字段，其余由系统从冻结段落填充。
    assert source.title == "frozen"
    assert run.detail.decision.evidence[0].section == "Results"
    assert run.detail.decision.evidence[0].paragraph_hash


def test_a_hostile_doi_cannot_move_a_request_off_the_official_endpoint(recorded_transport):
    """输入里的 URL 不能让 connector 离开配置的官方端点。"""

    seen, transport = recorded_transport
    client = httpx.AsyncClient(transport=transport)

    async def run() -> None:
        fetcher = Fetcher(client, request_seconds=5.0)
        crossref = CrossrefClient(fetcher, OFFICIAL_CROSSREF)
        resolver = DoiResolver(fetcher, OFFICIAL_DOI)
        for hostile in ("http://evil.example/steal", "//evil.example/x", "../../../evil"):
            await crossref.metadata(hostile, None)
            await resolver.resolvable(hostile, None)
        await client.aclose()

    asyncio.run(run())

    assert seen, "应至少发出一次请求"
    for url in seen:
        assert url.startswith(OFFICIAL_CROSSREF) or url.startswith(OFFICIAL_DOI), url
