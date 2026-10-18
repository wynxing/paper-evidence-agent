"""Keep the declared vocabulary aligned with the authoritative glossary."""

import importlib
import json
import re
import sys
import tomllib
from xml.etree import ElementTree

import pytest
from importlib.metadata import PackageNotFoundError, requires
from pathlib import Path

from paper_evidence.agents.prompts import PaperPromptBuilder
from paper_evidence.config import Settings, config_snapshot
from paper_evidence.domain import ContractError, ErrorCode, ResultLabel, Stage, TaskStatus
from paper_evidence.domain.contracts import SourcePreview, default_limits, default_timeouts
from paper_evidence.domain.records import Paragraph, TaskInput
from paper_evidence.storage.ports import TaskRepository
from paper_evidence.worker.__main__ import main

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "tests/functional/samples"


def test_enums_match_glossary():
    glossary = (ROOT / "docs/glossary.md").read_text(encoding="utf-8")
    statuses = glossary.split("## 2. 任务状态\n")[1].split("## 3.")[0]
    stages = glossary.split("## 3. 阶段\n")[1].split("## 4.")[0]
    errors = glossary.split("## 4. 错误码\n")[1].split("## 5.")[0]
    assert {item.value for item in TaskStatus} == set(re.findall(r"^\| `([A-Z_]+)` \|", statuses, re.MULTILINE))
    assert {item.value for item in Stage} == set(re.findall(r"^\| `([a-z_]+)` \|", stages, re.MULTILINE))
    assert {item.value for item in ErrorCode} == set(re.findall(r"^\| `([A-Z_]+)` \|", errors, re.MULTILINE))
    labels = glossary.split("## 1. 结果标签\n")[1].split("## 2.")[0]
    assert {item.value for item in ResultLabel} == set(re.findall(r"^\| (支持|部分支持|相矛盾|证据不足|无法核验来源) \|", labels, re.MULTILINE))


def test_module_boundaries_are_importable():
    for module in ("storage", "sources", "retrieval", "agents", "models", "graph", "diagnosis", "tracing", "worker"):
        importlib.import_module(f"paper_evidence.{module}.ports")


def test_the_prompt_version_on_calls_is_the_one_the_frozen_snapshot_pins():
    """调用账记的提示词版本与冻结快照里的必须是同一个（Issue #62）。

    `ModelCall.prompt_version` 取 `PaperPromptBuilder.version`，冻结配置快照的
    `prompts.version` 取 `PROMPT_VERSION`；诊断包要用这两处对账。两处各写一个字面量
    时，只改一处不会有任何检查变红，而记录会与真实提示词不符——那本身又是一类
    「记录与实际不符」。本用例挡住重新写回第二个字面量。
    """

    assert config_snapshot(Settings.from_env())["prompts"]["version"] == PaperPromptBuilder().version


def test_the_decision_prompt_carries_the_label_criteria_not_just_the_names():
    """四个标签的**判据**必须进提示词（Issue #78）。

    术语表把「数量、对象、因果性或范围有重要差异」划给部分支持，把相矛盾定义为「对应条件下
    有明确相反证据」；提示词此前只列了四个名字，模型只能用自己的先验去切，而它的先验在这条
    边界上与项目判据不一致——两轮实测 10 次最终标签里有 3 次越界，且**全部同向**
    （期望部分支持 → 答相矛盾）。判据不在提示词里，换上游也修不好，所以这里直接钉住它：
    删掉判据（回到只列四个名字）就变红，而不是等下一轮付费复测才发现。
    """

    prompt = PaperPromptBuilder().decision("论断原句", [], final_only=True)

    assert "部分支持＝" in prompt and "相矛盾＝" in prompt, "四个标签名之外必须有判据"
    assert "数量、对象、因果性或范围" in prompt, "部分支持的判据要写明四个维度"
    assert "没搜到支持证据不能推出相矛盾" in prompt, "相矛盾不能被「未检索到」冒充"
    assert "方向一致、只在数量或范围上有出入时，归部分支持" in prompt, (
        "边界规则要写成一句可照做的优先级，且必须带上「方向一致」这个前提："
        "只写「数量或范围的出入归部分支持」会把「论断说降一半、原文说没有下降」也判成部分支持"
    )
    assert "明确否定论断的对象或因果关系时，取相矛盾" in prompt, (
        "部分支持的判据把对象、因果性也算进去了，相矛盾必须有一条对称的出口，"
        "否则漂移只会从一边挪到另一边"
    )
    assert "证据不足＝" in prompt and "检索已完成" in prompt, "证据不足要有可判定的条件"


def _shared_run(left: str, right: str, size: int = 5) -> str:
    """返回 ``left`` 与 ``right`` 共有的任意一段 ``size`` 字连续文本，没有则返回空串。"""
    left = " ".join(left.split())
    right = " ".join(right.split())
    if len(left) < size or len(right) < size:
        return ""
    windows = {right[index : index + size] for index in range(len(right) - size + 1)}
    for index in range(len(left) - size + 1):
        window = left[index : index + size]
        if window in windows:
            return window
    return ""


def _rendered_prompts() -> dict[str, str]:
    """用中立占位材料渲染全部提示词模板，避免把被测样本的话自己带进来。"""

    builder = PaperPromptBuilder()
    paragraph = Paragraph(
        paragraph_id="p:prompt-guard:0000000:jats-0.0.0:1",
        source_id="prompt-guard",
        section="结果",
        ordinal=1,
        text="占位段落正文，只用来观察模板本身。",
        paragraph_hash="0" * 64,
        source_url="https://example.org/prompt-guard",
    )
    source = SourcePreview(doi="10.1000/prompt.guard", title="占位文献", authors=["占位作者"], year=2020)
    return {
        "decision": builder.decision("占位论断", [paragraph], final_only=False),
        "decision_final_only": builder.decision("占位论断", [paragraph], final_only=True),
        "query_generation": builder.query_generation("占位论断", source),
    }


def _sample_texts(sample: dict) -> set[str]:
    """样本里凡是被拿来当「题面」的话：论断、期望摘录、以及冻结正文的每个段落。"""

    texts = {sample["claim"], *sample.get("quotes", {}).values()}
    for paragraph in ElementTree.fromstring(sample["jats"]).iter("p"):
        texts.add("".join(paragraph.itertext()))
    return {text for text in texts if text}


def test_the_prompt_examples_are_not_taken_from_the_functional_samples():
    """提示词里的示例不得取自功能样本（Issue #78 的评审意见）。

    提示词示例与被测样本重合时，复测答对有两种解释同时成立：判据生效，或模型认出了例子。
    PR #89 的第一版正是这个形态——示例里的「所有年龄组」「约 50%」逐项对应
    `partial_population_scope` / `partial_quantity`，而这两例恰好是第三轮复测里仅剩的
    两条失败点，于是那一轮复测对「判据有没有用」没有解释力。判据本身也没法证明：模型照着
    例子认题同样能答对。

    判据取「连续 5 个字符相同」。中文里 5 字重合几乎不可能是巧合，而当时的污染形态
    「所有年龄组」正好 5 字，这条能挡住；同时不会因为「证据」「论断」这类两三个字的
    通用词误报。改动提示词示例或改动样本都会重新触发它，逼两边不要互相抄。
    """

    prompts = _rendered_prompts()
    collisions = []
    for path in sorted(SAMPLES.glob("*.json")):
        sample = json.loads(path.read_text(encoding="utf-8"))
        for name, prompt in prompts.items():
            for text in _sample_texts(sample):
                shared = _shared_run(prompt, text)
                if shared:
                    collisions.append(f"{path.name} ↔ {name}: 「{shared}」")

    assert not collisions, "提示词与功能样本重合，那一轮复测会失去解释力：\n" + "\n".join(collisions)


def test_the_dispatched_provider_model_is_part_of_the_frozen_digest(monkeypatch):
    """冻结快照必须钉住真正被派发的模型（Issue #68）。

    `configured_model` 是一个常量（`DEFAULT_CONFIGURED_MODEL`），`from_env()` 里没有
    任何一行读它的环境变量；换上游只改 `PAPER_EVIDENCE_PROVIDER_MODEL`。只把常量写进
    快照时，调 Agnes 与调 DeepSeek 的两次运行会声称**同一份有效配置**，`config_digest`
    也就无法支撑 `docs/evaluation.md` §3 的「固定模型部署」断言。本用例挡住那个形态。
    """

    from dataclasses import replace

    from paper_evidence.config import DEFAULT_CONFIGURED_MODEL, DEFAULT_PROVIDER_MODEL

    monkeypatch.delenv("PAPER_EVIDENCE_PROVIDER_MODEL", raising=False)
    settings = Settings.from_env()
    assert config_snapshot(settings)["model"]["provider_model"] == DEFAULT_PROVIDER_MODEL
    # 冻结的常量与真正派发的名字是两个值：前者区分不了两次运行。
    assert settings.configured_model == DEFAULT_CONFIGURED_MODEL != DEFAULT_PROVIDER_MODEL

    switched = replace(settings, provider_model="deepseek/deepseek-flash")
    assert config_snapshot(switched)["model"]["provider_model"] == "deepseek/deepseek-flash"
    # 只改这一个字段，摘要必须跟着变。
    assert switched.config_digest() != settings.config_digest()


def test_worker_entry_drains_an_empty_queue(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PAPER_EVIDENCE_DATA_DIR", str(tmp_path))
    assert main() == 0
    assert "队列已空" in capsys.readouterr().err
    assert (tmp_path / "paper-evidence.sqlite3").exists()


def test_worker_entry_reports_a_blocked_queue_instead_of_an_empty_one(tmp_path, monkeypatch, capsys):
    """队列里还有任务时不能说「队列已空」：在途任务挡住了这次领取。

    #44 第 3.2 条：``run_once`` 返回 ``False`` 既可能是队列已空，也可能是别的进程正
    在跑任务；一次性 ``drain`` 一律当结束，于是「队列已空」会被打到一次明明还有
    ``QUEUED`` 任务的运行上，让操作者以为没有活可干。
    """

    import time
    from dataclasses import replace

    from paper_evidence.config import Settings
    from paper_evidence.domain.contracts import RunConfigSnapshot
    from paper_evidence.domain.records import TaskInput
    from paper_evidence.domain.rules import criteria_reference
    from paper_evidence.storage.sqlite import SqliteStore
    from paper_evidence.worker.__main__ import main

    monkeypatch.setenv("PAPER_EVIDENCE_DATA_DIR", str(tmp_path))
    settings = replace(Settings.from_env(), data_dir=tmp_path, contact_email="")
    store = SqliteStore(tmp_path / "paper-evidence.sqlite3")
    try:
        for task_id in ("t1", "t2"):
            store.create(
                TaskInput(id=task_id, claim="The treatment reduced mortality.", doi="10.1000/xyz",
                          config_digest="d", authorized_recipients=("Agnes",)),
                RunConfigSnapshot(profile="daily", config_digest="d", snapshot_ref="r",
                                  authorized_recipients=["Agnes"], limits=settings.limits,
                                  timeouts=settings.timeouts, observability=settings.observability),
                criteria_reference("rev"),
            )
        assert store.claim_next(time.time() + 180) is not None  # t1 在途，时限未到

        assert main() == 0
        err = capsys.readouterr().err
        assert "队列已空" not in err
        assert "t1" in err and "RUNNING" in err
        assert store.get("t2").status is TaskStatus.QUEUED
    finally:
        store.close()


def test_worker_reports_an_interrupt_and_exits_zero(tmp_path, monkeypatch, capsys):
    """常驻模式只能靠中断结束，入口把它当作正常停止而不是失败。

    Windows 的控制台控制事件会在 Python 处理之前结束进程，进程外的真实信号
    不可移植，因此这里在入口层固定退出码与提示文案。
    """

    from paper_evidence.worker import __main__ as entry

    monkeypatch.setenv("PAPER_EVIDENCE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["paper_evidence.worker", "--loop"])
    calls = []

    async def interrupted(_worker, interval):
        calls.append(interval)
        raise KeyboardInterrupt

    monkeypatch.setattr(entry, "drain_forever", interrupted)
    assert entry.main() == 0
    assert calls == [entry.DEFAULT_INTERVAL]
    assert "worker 收到中断，已停止。" in capsys.readouterr().err


def test_worker_loop_options_come_from_arguments_or_environment():
    from paper_evidence.worker.__main__ import DEFAULT_INTERVAL, MIN_INTERVAL, parse_options

    assert parse_options([], {}) == (False, DEFAULT_INTERVAL)
    assert parse_options(["--loop"], {}) == (True, DEFAULT_INTERVAL)
    assert parse_options([], {"PAPER_EVIDENCE_WORKER_LOOP": "YES"})[0] is True
    assert parse_options([], {"PAPER_EVIDENCE_WORKER_LOOP": "0"})[0] is False
    assert parse_options(["--interval", "2.5"], {})[1] == 2.5
    assert parse_options([], {"PAPER_EVIDENCE_WORKER_POLL_SECONDS": "3"})[1] == 3.0
    # 参数覆盖环境变量；非法与非正值回落到安全默认，不会忙等。
    assert parse_options(["--interval", "9"], {"PAPER_EVIDENCE_WORKER_POLL_SECONDS": "3"})[1] == 9.0
    assert parse_options(["--interval", "nonsense"], {})[1] == DEFAULT_INTERVAL
    assert parse_options(["--interval", "0"], {})[1] == MIN_INTERVAL
    assert parse_options(["--interval"], {})[1] == DEFAULT_INTERVAL


def test_drain_forever_keeps_polling_and_stops_on_cancellation():
    """常驻模式：队列空时按间隔等待，停止时能退出，而不是把任务留在 QUEUED。"""

    import asyncio

    from paper_evidence.worker.runner import drain_forever

    class FakeWorker:
        def __init__(self) -> None:
            self.calls = 0
            self.processed = 0

        async def run_once(self) -> bool:
            self.calls += 1
            if self.processed >= 2:
                return False
            self.processed += 1
            return True

    async def scenario() -> tuple[int, int]:
        worker = FakeWorker()
        task = asyncio.create_task(drain_forever(worker, 0.01))
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return worker.processed, worker.calls

    processed, calls = asyncio.run(scenario())
    assert processed == 2
    # 队列空后仍继续轮询（而不是退出），这正是让 QUEUED 任务被执行的前提。
    assert calls > processed


def test_drain_forever_survives_a_failing_iteration():
    """#16 第 1 条：一个任务失败不能让 worker 退出。

    没有这条兜底时，异常穿过循环结束进程，此后每个任务都停在 QUEUED，而客户端
    还在轮询一个永远不会执行它的服务。
    """

    import asyncio

    from paper_evidence.worker.runner import drain_forever

    class FlakyWorker:
        def __init__(self) -> None:
            self.calls = 0

        async def run_once(self) -> bool:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("claim or settle blew up")
            return self.calls < 4

    async def scenario() -> int:
        worker = FlakyWorker()
        task = asyncio.create_task(drain_forever(worker, 0.01))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return worker.calls

    # 第一轮抛错后循环还在继续领取，而不是随异常一起结束。
    assert asyncio.run(scenario()) > 3


def test_run_once_settles_a_task_whose_workflow_cannot_be_built(tmp_path):
    """构造工作流也会抛异常；已领取的那笔任务必须落成失败而不是留在 RUNNING。"""

    import asyncio
    from dataclasses import replace

    from paper_evidence.config import Settings
    from paper_evidence.domain.contracts import RunConfigSnapshot
    from paper_evidence.domain.records import TaskInput
    from paper_evidence.domain.rules import criteria_reference
    from paper_evidence.storage.sqlite import SqliteStore
    from paper_evidence.worker.runner import SingleTaskWorker

    settings = replace(Settings.from_env(), data_dir=tmp_path, contact_email="")
    store = SqliteStore(tmp_path / "runner.sqlite3")
    try:
        store.create(
            TaskInput(id="t1", claim="The treatment reduced mortality.", doi="10.1000/xyz",
                      config_digest="d", authorized_recipients=("Agnes",)),
            RunConfigSnapshot(profile="daily", config_digest="d", snapshot_ref="r",
                              authorized_recipients=["Agnes"], limits=settings.limits,
                              timeouts=settings.timeouts, observability=settings.observability),
            criteria_reference("rev"),
        )

        def exploding_factory(_task):
            raise RuntimeError("cannot build the workflow")

        assert asyncio.run(SingleTaskWorker(store, exploding_factory, settings).run_once()) is True
        stored = store.get("t1")
        assert stored.status is TaskStatus.FAILED
        assert stored.error_code is None      # 未分类失败保持 null 错误码
        assert stored.finished_at is not None
        # 已领取的任务不再回到队列，避免同一笔被执行两次。
        assert asyncio.run(SingleTaskWorker(store, exploding_factory, settings).run_once()) is False
    finally:
        store.close()


def test_frontend_literals_match_python_contracts():
    source = (ROOT / "frontend/src/api/contracts.ts").read_text(encoding="utf-8")

    def union(name: str) -> set[str]:
        match = re.search(rf"export type {name} =((?:.|\n)*?)\nexport ", source)
        assert match, name
        return set(re.findall(r"'([^']+)'", match.group(1)))

    assert union("TaskStatus") == {item.value for item in TaskStatus}
    assert union("Stage") == {item.value for item in Stage}
    assert union("ErrorCode") == {item.value for item in ErrorCode}
    assert union("AcademicLabel") | {"无法核验来源"} == {item.value for item in ResultLabel}
    assert "schema_version: '2.2'" in source
    assert "reason: 'attempt_records_missing' | null" in source


def _distribution_name(requirement: str) -> str:
    """The distribution a requirement names.

    Metadata renders a requirement either as ``name<1`` or, from older
    setuptools — which botocore still uses — as ``name (<1,>=x)``. Splitting on
    the first space, bracket or version operator covers both.
    """

    return re.split(r"[<>=;\[\s(]", requirement, maxsplit=1)[0].strip().lower().replace("_", "-")


def _requested_extras(requirement: str) -> set[str]:
    """The extras a ``dep[extra]`` requirement asks for, if it asks for any."""

    match = re.search(r"\[([^\]]*)\]", requirement)
    return {part.strip() for part in match.group(1).split(",") if part.strip()} if match else set()


def _extra_marker(requirement: str) -> str | None:
    """The extra named in an ``extra == "..."`` marker, if there is one."""

    match = re.search(r"""extra\s*==\s*["']([^"']+)["']""", requirement)
    return match.group(1) if match else None


def test_lockfile_matches_declared_dependency_closure():
    pyproject = tomllib.loads((ROOT / "backend/pyproject.toml").read_text(encoding="utf-8"))
    lock = (ROOT / "backend/requirements.lock").read_text(encoding="utf-8")
    pinned = {
        line.split("==", 1)[0].lower().replace("_", "-")
        for line in lock.splitlines()
        if "==" in line and not line.startswith("#")
    }
    declared = {
        _distribution_name(raw)
        for raw in [
            *pyproject["project"]["dependencies"],
            *pyproject["project"]["optional-dependencies"]["dev"],
            *pyproject["build-system"]["requires"],
        ]
    }
    assert declared <= pinned
    # A requirement can carry an extra either as a marker (``x; extra == "e"``) or
    # in its own name (``x[e]``). Both pull real packages in, so both belong to the
    # closure; litellm declares httpx[http2] the second way. An extra nobody asks
    # for stays out, which is what keeps unrequested optional deps unpinned. The
    # marker names an extra of the distribution being read, not of the dependency.
    requested: dict[str, set[str]] = {}
    closure = set(declared)
    pending = set(declared)
    while pending:
        name = pending.pop()
        try:
            dependencies = requires(name) or []
        except PackageNotFoundError:
            continue
        for requirement in dependencies:
            marker = _extra_marker(requirement)
            if marker is not None and marker not in requested.get(name, set()):
                continue
            dependency = _distribution_name(requirement)
            extras = _requested_extras(requirement)
            if extras - requested.setdefault(dependency, set()):
                requested[dependency] |= extras
                pending.add(dependency)  # read it again now the extra is asked for
            if dependency not in closure:
                closure.add(dependency)
                pending.add(dependency)
    assert pinned <= closure


def test_repository_exposes_conditional_cancel_operations():
    assert {"request_cancel", "settle_orphaned_running", "save"} <= set(TaskRepository.__protocol_attrs__)
    assert "previous_id" in TaskInput.__annotations__
    assert "native_jats_id" in Paragraph.__annotations__
    assert ContractError(None).error_code is None


def test_default_budgets_match_glossary_and_return_independent_instances():
    glossary = (ROOT / "docs/glossary.md").read_text(encoding="utf-8")
    for name, factory in (("limits", default_limits), ("timeouts", default_timeouts)):
        row = re.search(rf"^\| `run_config\.{name}` \| ([^\n]+)\|$", glossary, re.MULTILINE)
        assert row, name
        documented = {field: int(value) for field, value in re.findall(r"([a-z_]+)=([0-9]+)", row.group(1))}
        first, second = factory(), factory()
        assert first.model_dump() == documented
        assert second.model_dump() == documented
        assert first is not second
        field = next(iter(documented))
        setattr(first, field, documented[field] + 1)
        assert factory().model_dump() == documented
        assert second.model_dump() == documented
