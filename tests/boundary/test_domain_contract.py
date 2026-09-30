"""Keep the declared vocabulary aligned with the authoritative glossary."""

import importlib
import re
from pathlib import Path

from paper_evidence.domain import ErrorCode, ResultLabel, Stage, TaskStatus
from paper_evidence.worker.__main__ import main

ROOT = Path(__file__).resolve().parents[2]


def test_enums_match_glossary():
    glossary = (ROOT / "docs/glossary.md").read_text()
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


def test_worker_reports_pending(capsys):
    assert main() == 2
    assert "Not Implemented" in capsys.readouterr().err
