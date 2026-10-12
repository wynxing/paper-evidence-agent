"""The report's denominators must follow 评测口径 §4, edge cases included.

These tests pin the rules that are easy to get subtly wrong: a zero denominator
is N/A (never 0 or 100%), a refusal or an execution failure stays in the recall
denominator as a false negative, and "no decision was published" makes the
locatability metric 不适用 rather than perfect.
"""

import pytest

from report import Outcome, metrics, render


def case(case_id, expected, status="COMPLETED", label=None, quotes=1, located=1):
    return Outcome(case_id=case_id, expected=expected, status=status, label=label,
                   quotes_total=quotes, quotes_located=located)


def test_the_identity_holds_and_every_slot_lands_in_exactly_one_bucket():
    """`N = D + I + B + F + C + X + U`，每个槽位只进一个桶。"""

    outcomes = [
        case("a", "支持", label="支持"),
        case("b", "相矛盾", label="证据不足"),      # 过度拒判 -> I
        case("c", "支持", status="FAILED"),         # F
        case("d", "部分支持", status="CANCELLED"),  # C
        case("e", "证据不足", label="证据不足"),    # I
        case("f", "支持", status="RUNNING"),        # U
    ]
    m = metrics(outcomes)

    assert m["counts"] == {"D": 1, "I": 2, "B": 0, "F": 1, "C": 1, "X": 0, "U": 1}
    assert sum(m["counts"].values()) == m["total"] == len(outcomes)
    assert "与 N 一致" in render(outcomes, sample_fingerprint="test")


def test_a_zero_denominator_is_rendered_as_not_applicable():
    """分母为零记 N/A，不补成 0 或 100%。"""

    # 真值全部是「证据不足」-> 真值可判定子集为空 -> 覆盖率分母为 0。
    outcomes = [case("a", "证据不足", label="证据不足", quotes=0, located=0)]
    m = metrics(outcomes)

    assert m["truth_decidable_n"] == 0
    assert m["coverage_truth_decidable"] is None, "分母为零必须是 N/A"
    assert m["locatability"] is None, "没有发布摘录时不得给出定位率"
    assert "N/A" in render(outcomes, sample_fingerprint="test")


def test_a_zero_over_a_non_empty_denominator_is_a_real_zero():
    """分母非零时 0 是真实结果，不能被写成 N/A。"""

    outcomes = [case("a", "支持", status="FAILED")]  # 真值可判定，但没做出判断
    m = metrics(outcomes)

    assert m["truth_decidable_n"] == 1
    assert m["coverage_truth_decidable"] == 0.0, "0/1 是真实结果，不是 N/A"
    assert m["r_error_rate"] is None, "R 中没有 COMPLETED，这里才是 N/A"


def test_refusal_and_failure_stay_in_the_recall_denominator():
    """真值为相矛盾但系统拒判或执行失败的样本计入该类 FN。"""

    outcomes = [
        case("a", "相矛盾", label="相矛盾"),
        case("b", "相矛盾", label="证据不足"),  # 拒判
        case("c", "相矛盾", status="FAILED"),   # 执行失败
    ]
    row = metrics(outcomes)["per_label"]["相矛盾"]

    assert row["truth_n"] == 3
    assert row["tp"] == 1
    assert row["fn"] == 2, "拒判与失败不得从召回率分母移除"
    assert row["recall"] == pytest.approx(1 / 3)


def test_locatability_is_not_applicable_when_nothing_was_published():
    """没有确定判断时不写 100%，写「不适用」。"""

    outcomes = [case("a", "证据不足", label="证据不足", quotes=0, located=0)]
    text = render(outcomes, sample_fingerprint="test")

    assert "不适用" in text
    assert "100.0%" not in text
    assert metrics(outcomes)["locatability"] is None


def test_macro_f1_excludes_classes_whose_denominator_is_zero():
    """分母为零的类从平均中排除，并报告实际参与平均的类别。"""

    outcomes = [case("a", "支持", label="支持"), case("b", "支持", label="支持")]
    m = metrics(outcomes)

    assert m["f1_by_label"]["部分支持"] is None
    assert m["f1_by_label"]["相矛盾"] is None
    assert m["macro_f1"] == pytest.approx(1.0)
    assert m["macro_f1_labels"] == ["支持"], "必须报告参与平均的类别"


def test_the_refusal_error_rate_is_na_when_the_refusal_set_never_completed():
    """R 中没有 COMPLETED 时该比率是 N/A，不是 0。"""

    m = metrics([case("a", "证据不足", status="FAILED")])

    assert m["r_total"] == 1
    assert m["r_completed"] == 0
    assert m["r_error_rate"] is None
    assert m["r_error_rate_all"] == 0.0


def test_pending_slots_mark_the_whole_report_provisional():
    """U>0 时报告必须是暂定，不得当作最终结论。"""

    outcomes = [case("a", "支持", label="支持"), case("b", "支持", status="QUEUED")]
    text = render(outcomes, sample_fingerprint="test")

    assert metrics(outcomes)["pending"] == 1
    assert "暂定" in text


def test_misjudgement_and_over_refusal_are_reported_separately():
    """误判与过度拒判分别列出，不只报条件准确率。"""

    outcomes = [
        case("a", "支持", label="相矛盾"),      # 误判
        case("b", "支持", label="证据不足"),    # 过度拒判
        case("c", "支持", label="支持"),        # 正确
    ]
    m = metrics(outcomes)

    assert m["misjudged"] == ["a"]
    assert m["over_refused"] == ["b"]
    assert m["labels_correct"] == 1


def test_the_report_never_hardcodes_a_sample_count():
    """第 0 节的样本数必须由 metrics 派生。

    旧文案把「首版 n=1 单次抽样」写死在同一节里，与 `N = 7` 直接打架，
    而没有任何断言覆盖那段文字。
    """

    outcomes = [case(f"c{i}", "支持", label="支持") for i in range(3)]
    text = render(outcomes, sample_fingerprint="sha256:test")

    assert metrics(outcomes)["total"] == 3
    assert "N = 3" in text
    assert "n=1" not in text and "n=7" not in text


def test_the_macro_f1_label_list_keeps_the_definition_order():
    """参与平均的类别按 DEFINITIVE 顺序，与上方 F1 表一致（不按码位排序）。"""

    outcomes = [
        case("a", "支持", label="支持"),
        case("b", "部分支持", label="部分支持"),
        case("c", "相矛盾", label="相矛盾"),
    ]
    m = metrics(outcomes)

    assert m["macro_f1_labels"] == ["支持", "部分支持", "相矛盾"]
    assert "参与平均的类别：支持、部分支持、相矛盾。" in render(
        outcomes, sample_fingerprint="sha256:test")


def test_the_report_carries_no_commit_dependent_field():
    """报告里不能有随 commit 漂移的字段，否则「重新生成后比对」在 CI 恒红。"""

    text = render([case("a", "支持", label="支持")], sample_fingerprint="sha256:abc123")

    assert "sha256:abc123" in text, "样本集指纹必须出现在正文，作为可复现的溯源"
    assert "工作区有未提交改动" not in text, "不得再写入工作区脏标记"


def test_the_sample_fingerprint_tracks_the_sample_set(tmp_path):
    """指纹在同一批样本上稳定，内容或样本名一变就变。"""

    from report import sample_fingerprint

    (tmp_path / "a.json").write_text('{"v": 1}', encoding="utf-8")
    first = sample_fingerprint(tmp_path)

    assert first.startswith("sha256:")
    assert first == sample_fingerprint(tmp_path), "同一样本集必须得到同一指纹"

    (tmp_path / "a.json").write_text('{"v": 2}', encoding="utf-8")
    assert sample_fingerprint(tmp_path) != first, "样本内容变化必须改指纹"

    (tmp_path / "a.json").write_text('{"v": 1}', encoding="utf-8")
    (tmp_path / "b.json").write_text('{"v": 1}', encoding="utf-8")
    assert sample_fingerprint(tmp_path) != first, "新增样本必须改指纹"
