"""Live check: the committed real-source inventory still describes today's PMC.

The real-source set is the input half of the semantic acceptance (测试方案「采样与
分母」/ `#20`). It deliberately commits only **hashes and previews**, not the article
text, so that content drift stays visible — this file is what makes that visibility
real: it re-fetches each frozen DOI and compares.

A failure here means the frozen basis moved. It is **not** something to fix by
rewriting the hashes: the human-checked ``claims`` for that source were written
against the old text and must be re-checked (and re-reviewed by a second person)
before the hashes are updated.

Skipped unless ``PAPER_EVIDENCE_LIVE_SOURCES=1``: CI has no network egress, so a
green CI run says nothing about this file. **A skipped run is not a passing run.**
"""

import os
import tempfile
from pathlib import Path

import pytest

from freeze_sources import SOURCES, SCHEMA, differences, freeze, load_all

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("PAPER_EVIDENCE_LIVE_SOURCES") != "1",
        reason="live upstream checks are opt-in; CI has no network egress",
    ),
]

#: The licences the frozen set may carry; an acceptance sample nobody may reuse is
#: not usable evidence (AGENTS.md「论文证据与资料」).
SUPPORTED_LICENSES = {"CC BY", "CC0"}

#: Read at collection time — no network, just the committed files. A guard entry
#: keeps an empty directory from turning the parametrised test into a collection error.
ENTRIES = load_all(SOURCES)
CASE_IDS = [entry["case_id"] for entry in ENTRIES] or ["<empty>"]


@pytest.fixture(scope="module")
def stored():
    assert ENTRIES, f"{SOURCES} 下没有冻结清单，本组用例会空跑通过"
    return ENTRIES


def test_the_frozen_set_has_the_expected_shape(stored):
    """A malformed inventory must fail here rather than quietly shrink coverage."""

    assert len(stored) >= 3, f"真实来源集只有 {len(stored)} 个来源"
    for entry in stored:
        assert entry["schema"] == SCHEMA, f"{entry['case_id']} 的 schema 版本不是 {SCHEMA}"
        assert isinstance(entry["claims"], list), f"{entry['case_id']} 的 claims 必须是数组"
        assert entry["paragraph_count"] == len(entry["paragraphs"])
        assert entry["paragraph_count"] > 0
        # No article text beyond the preview: hashing instead is the whole point.
        assert "jats_text" not in entry, f"{entry['case_id']} 内嵌了正文，漂移将不再可见"


def test_every_frozen_source_is_under_a_supported_licence(stored):
    """Only licences the product auto-processes may enter the acceptance set."""

    for entry in stored:
        assert entry["provenance"]["license"] in SUPPORTED_LICENSES, (
            f"{entry['case_id']} 的许可是 {entry['provenance']['license']!r}，不在首版支持范围"
        )


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_a_frozen_source_still_matches_today_upstream(case_id, stored):
    """Re-fetch one frozen DOI and require the inventory to describe it exactly."""

    entry = next((item for item in stored if item["case_id"] == case_id), None)
    assert entry is not None, f"{case_id} 不在冻结清单里"

    with tempfile.TemporaryDirectory(prefix="frozen-drift-") as work:
        live = freeze(entry["provenance"]["doi"], Path(work))

    drifted = differences(live, entry)
    assert not drifted, (
        f"{case_id} 与冻结清单不一致（PMC 侧内容变了）：\n  - "
        + "\n  - ".join(drifted)
        + "\n  该来源的人工核对结论（claims）针对的是旧正文，必须先重新核对再更新哈希。"
    )
