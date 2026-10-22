"""指标记录 `docs/metrics-live-86.md` 的离线回归（`#86` / `#110`）。

为什么需要这份测试
------------------
`live_metrics.py` 563 行，产出的却是交付物里**唯一一组真模型数字**（22/24、
macro-F1 0.92、冲突识别 1.00……）。它此前零测试、CI 也不跑：算术写错、`--from`
重算路径坏掉、或者有人改了 `report.metrics` 的口径，都不会有人发现，直到数字被
写进介绍文档和视频。

这里不调用模型、不花一分钱：`docs/metrics-live-86.run.json` 是**已经发生过的一次
运行的快照**（原始回复、逐条计数、余额变化），`--from` 只按当前答案集重算。
既然重算是确定性的，就可以像 `semantic-report.md --check` 那样比对**内容**——
重生成的结果必须与仓库里发布的记录完全一致（换行按平台归一，见 :func:`content`）。

三层断言，越往下越具体
----------------------
1. **内容一致**：重生成 == 已提交文件（CRLF 归一后逐字节相等）。抓任何渲染/口径漂移，
   报错信息指向行。
2. **独立重算**：测试自己按行算一遍 22/24、macro-F1、定位率、拒判错误率，
   再验证这些数字确实出现在文档里。逐字节相等只说明「和上次一样」，这一层说明
   「和这批数据算出来的一样」。
3. **重算读的是当前答案集**：快照里的 `expected` 是当时的金标（c07 还是「证据
   不足」），重算必须用 `tests/functional/sources/` 现在的值。这条正是 `#117`
   改签后 `--from` 存在的理由，也是唯一能防止「拿旧金标冒充新指标」的断言。
"""

import json
from pathlib import Path

import pytest

import live_metrics
from live_metrics import REPO, answer_set_stats, render_from, run_live, source_fingerprint

RECORD = REPO / "docs" / "metrics-live-86.md"
SNAPSHOT = REPO / "docs" / "metrics-live-86.run.json"
SOURCES = REPO / "tests" / "functional" / "sources"


def content(path: Path) -> bytes:
    """按内容比较，不按字节比较：换行由运行平台决定。

    `render()` 用 `Path.write_text`，Windows 写 CRLF、Linux 写 LF。直接比原始字节
    会让这条断言只在生成记录的那台机器上过——`report.py:366` 的
    `sample_fingerprint()` 踩过同一个坑（哈希原始字节 → 本地过、CI 才现形）。
    这里比的是**内容**；换行风格由仓库约定（`docs/*.md` 为 CRLF）另行约束，
    不该由一条跨平台的回归测试来判。
    """

    return path.read_bytes().replace(b"\r\n", b"\n")

#: 快照里仍然写着旧金标的那一条：`#117` 把它从「证据不足」改判为「部分支持」。
RELABELLED = "PMC8806060-c07"


def current_answers() -> dict[str, str]:
    """读当前签核过的答案集（唯一真值来源，不从快照里抄）。"""

    answers: dict[str, str] = {}
    for path in sorted(SOURCES.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for claim in payload["claims"]:
            answers[claim["claim_id"]] = claim["expected_label"]
    return answers


def snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def test_regenerating_from_the_recorded_run_reproduces_the_published_record(tmp_path):
    """逐字节：`--from` 重生成的结果必须与仓库里发布的记录完全一致。

    这是整个回归的锚。它同时钉住了三件事：`report.metrics` 的口径没变、渲染模板
    没变、记录文件本身没被手改过（手改过的记录一定重生成不出来）。
    """

    out = tmp_path / "regen.md"
    assert render_from(out, SNAPSHOT) == 0
    assert content(out) == content(RECORD), (
        "重生成的记录与 docs/metrics-live-86.md 不一致；"
        "若答案集或渲染口径确有变更，请重跑 live_metrics.py 并提交新记录")


def test_the_recompute_uses_the_current_answer_set_not_the_recorded_one(tmp_path):
    """`--from` 必须用现在的金标，而不是快照里记着的旧金标。

    快照的 `fingerprint_at_run` 是那次运行时的答案集指纹（旧金标），而记录里印的是
    重算用的当前指纹。两者不同是**正常的**，因为重算的语义就是「模型输出不变、
    人工答案换成最新的」。这条用例把那个语义钉死：c07 在快照里是「证据不足」，
    在现在的答案集里是「部分支持」，重算后的逐条表必须按后者写。
    """

    answers = current_answers()
    recorded = {row["case_id"]: row["expected"] for row in snapshot()["rows"]}

    # 前提：这条确实被改签过，否则下面的断言在空转。
    assert recorded[RELABELLED] != answers[RELABELLED]
    assert answers[RELABELLED] == "部分支持"

    out = tmp_path / "regen.md"
    assert render_from(out, SNAPSHOT) == 0
    text = out.read_text(encoding="utf-8")

    assert f"| `{RELABELLED}` | 部分支持 | 部分支持 |" in text
    # 记录表头印的是当前答案集指纹，与运行时指纹分开写。
    assert source_fingerprint() in text


def test_the_headline_numbers_are_what_this_run_supports(tmp_path):
    """独立重算：22/24、macro-F1 0.92、定位 44/44、拒判错误率 0.25。

    逐字节比对只能说明「和上次渲染的一样」。这一层不看模板，直接按行算：标签一致
    数、三类等权 macro-F1、引文定位、应拒判样本上的错误确定判断。算完再验证文档
    里印的确实是这些数——否则「文档和代码一致地错」是能一起骗过第一层的。
    """

    answers = current_answers()
    rows = snapshot()["rows"]
    assert len(rows) == len(answers) == 24

    matched = sum(1 for row in rows if row["actual"] == answers[row["case_id"]])
    assert matched == 22

    labels = ("支持", "部分支持", "相矛盾")
    scores = {}
    for label in labels:
        tp = sum(1 for row in rows if answers[row["case_id"]] == label and row["actual"] == label)
        fp = sum(1 for row in rows if answers[row["case_id"]] != label and row["actual"] == label)
        fn = sum(1 for row in rows if answers[row["case_id"]] == label and row["actual"] != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores[label] = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    macro = sum(scores.values()) / len(labels)
    assert round(macro, 2) == 0.92, scores

    located = sum(row["quotes_located"] for row in rows)
    total = sum(row["quotes_total"] for row in rows)
    assert (located, total) == (44, 44)

    refusals = [row for row in rows if answers[row["case_id"]] == "证据不足"]
    wrong = [row for row in refusals if row["actual"] in labels]
    assert (len(wrong), len(refusals)) == (1, 4)

    out = tmp_path / "regen.md"
    assert render_from(out, SNAPSHOT) == 0
    text = out.read_text(encoding="utf-8")
    assert "| 语义标签正确数/总数 | 22/24 |" in text
    assert "| **macro-F1** | **0.92** |" in text
    assert f"| 摘录定位有效率 | 100.0%（{located}/{total}）" in text
    assert "| 应拒判集错误确定判断率 | 0.25 |" in text
    # 答分与分母对账：D+I+B+F+C+X+U 必须等于 N。
    assert "校验：D+I+B+F+C+X+U = 24，与 N 一致。" in text


def test_an_unknown_case_is_refused_instead_of_scored(tmp_path):
    """快照与答案集对不上时拒绝重算，而不是用旧期望值凑一个数。

    这是「不得为变绿而放宽」的具体形态：找不到对应的签核答案就退出码 2，
    一个文件都不写。
    """

    broken = snapshot()
    broken["rows"][0]["case_id"] = "PMC0000000-c99"
    path = tmp_path / "broken.run.json"
    path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")

    out = tmp_path / "never.md"
    assert render_from(out, path) == 2
    assert not out.exists()


def test_the_live_run_refuses_before_any_call_without_a_provider(tmp_path, monkeypatch):
    """没显式指定模型时直接拒绝：CI 里不会因为忘了变量而真花钱。

    记录必须写明「实际调用的是哪个模型」，所以不允许有默认 provider。这条同时是
    成本闸门——它证明 `run_live` 在任何网络调用之前就返回了。
    """

    monkeypatch.delenv("PAPER_EVIDENCE_PROVIDER_MODEL", raising=False)
    monkeypatch.delenv("PAPER_EVIDENCE_MODEL_API_KEY", raising=False)

    out = tmp_path / "live.md"
    assert run_live(out) == 2
    assert not out.exists()
    assert not out.with_suffix(".run.json").exists()


def test_the_published_record_states_where_its_model_outputs_came_from():
    """记录必须自报来源：模型、提示词版本、提交、运行时间、密钥标签。

    这些字段不是装饰——没有它们，「22/24」说不清是哪一版提示词、哪个模型、哪天
    跑的。`evaluation.md` §4 要求记录归因，缺一栏这条记录就不能被引用。
    """

    data = snapshot()
    for field in ("provider_model", "prompt_version", "started_at", "commit",
                  "balance_before", "balance_after", "key_label", "rows"):
        assert data.get(field), f"快照缺 {field}"

    text = RECORD.read_text(encoding="utf-8")
    assert data["provider_model"] in text
    assert data["prompt_version"] in text
    # 余额必须能被读成「花了多少」，否则成本一栏只能写「未知」。
    # 这两个值是字符串形式的金额（`"15.10"`），既要可解析，也要真的减少。
    spent = float(data["balance_before"]) - float(data["balance_after"])
    assert spent > 0, f"余额没有减少，记录不到成本：{data['balance_before']} → {data['balance_after']}"
    assert live_metrics.answer_set_stats()["agreed"] == answer_set_stats()["total"] == 24
