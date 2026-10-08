"""Keep the declared vocabulary aligned with the authoritative glossary."""

import importlib
import re
import tomllib
from importlib.metadata import PackageNotFoundError, requires
from pathlib import Path

from paper_evidence.domain import ContractError, ErrorCode, ResultLabel, Stage, TaskStatus
from paper_evidence.domain.contracts import default_limits, default_timeouts
from paper_evidence.domain.records import Paragraph, TaskInput
from paper_evidence.storage.ports import TaskRepository
from paper_evidence.worker.__main__ import main

ROOT = Path(__file__).resolve().parents[2]


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


def test_worker_entry_drains_an_empty_queue(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PAPER_EVIDENCE_DATA_DIR", str(tmp_path))
    assert main() == 0
    assert "队列已空" in capsys.readouterr().err
    assert (tmp_path / "paper-evidence.sqlite3").exists()


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
    return re.split(r"[<>=;\[]", requirement, maxsplit=1)[0].strip().lower().replace("_", "-")


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
    closure = set(declared)
    pending = set(declared)
    while pending:
        name = pending.pop()
        try:
            dependencies = requires(name) or []
        except PackageNotFoundError:
            continue
        for requirement in dependencies:
            if "extra ==" in requirement:
                continue
            dependency = _distribution_name(requirement)
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
