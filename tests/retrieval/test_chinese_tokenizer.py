"""unicode61 下中文正文的子词召回盲区（测试方案 `test-plan.md:72`）。

判据原文：*使用 unicode61 验证中文词汇在连续中文正文的子词召回盲区*。

这里验证的是**已经存在的限制**，不是期待它被修好。`paragraphs_fts` 用
`tokenize='unicode61'`（`storage/sqlite.py:103-106`），unicode61 按「非字母数字
字符」切词，而汉字属于字母类，所以一段连续中文（中间没有空格、标点）整体成
**一个词元**。后果有两条，两条都钉在下面：

1. **子词查不到**：正文是「……无统计学意义」，查「统计学意义」命中不了，
   因为 FTS5 的词元边界不是词边界，是标点/空白边界。
2. **不等于中文不可检索**：标点切出来的整段（如「无统计学意义」）能命中。
   所以每一条「查不到」的断言都配了一条「查得到」的正对照——否则全空结果也
   能骗过测试。

这条限制在交稿范围里属于「已知限制」而非缺陷：换成 `simple` 分词器或外挂
中文分词器会改变 `paragraph_hash` 之外的一切检索行为，属于功能变更，功能已
按 `v0.3.0-test-freeze` 冻结。哪天真的换了分词器，本文件会红——那是提醒改
措辞，不是提醒放宽断言。
"""

from paper_evidence.domain.contracts import SourceRecord
from paper_evidence.domain.records import SourceSnapshot
from paper_evidence.retrieval.jats import parse_jats
from paper_evidence.retrieval.local import StoreRetriever
from paper_evidence.retrieval.query import compile_match
from paper_evidence.storage.sqlite import SqliteStore

VERSION_HASH = "c" * 64

# 一段连续中文里只有一处标点，正好卡出词元边界：
#   「上斜方肌……显著减轻」← 一个词元（长）
#   「该差异」← 一个词元（短，用来做子词对照）
#   「无统计学意义」← 一个词元（标点之后）
CONTINUOUS = "上斜方肌肌筋膜疼痛综合征患者在接受干预后疼痛显著减轻"
AFTER_PUNCTUATION = "无统计学意义"
CHINESE_JATS = f"""<?xml version="1.0" encoding="UTF-8"?>
<article xml:lang="en"><front><article-meta/></front><body>
<sec id="s1"><title>结果</title>
<p id="c1">{CONTINUOUS}，该差异（p=0.43）{AFTER_PUNCTUATION}。</p>
<p id="c2">干预组与对照组之间差异无统计学意义。</p>
</sec></body></article>
""".encode("utf-8")


def _retriever(tmp_path):
    record = SourceRecord(
        title="Demo", authors=["Ada Lovelace"], year=2026, doi="10.1000/zh", pmcid="PMC321",
        license="CC BY", version="1", access_url="https://example.org/zh",
        retrieved_at="2026-10-01T00:00:00+00:00", version_hash=VERSION_HASH,
        retrieval_form="full_text",
    )
    source = SourceSnapshot(source_id=f"PMC321:{VERSION_HASH}", metadata=record, jats_bytes=CHINESE_JATS)
    store = SqliteStore(tmp_path / "zh.sqlite3")
    store.index_source(source.source_id, source.metadata, source.jats_bytes)
    store.index_paragraphs(source.source_id, parse_jats(source))
    return store, StoreRetriever(store, context_limit=10), source.source_id


def test_a_whole_chinese_token_between_punctuation_is_recallable(tmp_path):
    """正对照：标点切出来的整段能命中，证明中文正文确实进了索引。

    缺了这条，「子词查不到」可能只是整张索引为空——那两条断言就都不承重了。
    """

    store, retriever, source_id = _retriever(tmp_path)
    try:
        hits = retriever.search(source_id, [AFTER_PUNCTUATION])
        assert [p.native_jats_id for p in hits] == ["c1"]

        # 同一段的另一个整段词元也能命中，说明不是「只有第一个词元进索引」。
        assert [p.native_jats_id for p in retriever.search(source_id, ["该差异"])] == ["c1"]
    finally:
        store.close()


def test_a_chinese_sub_word_inside_a_continuous_run_is_not_recallable(tmp_path):
    """盲区本身：连续中文里的真子词查不到，即使它逐字出现在正文里。

    「肌筋膜疼痛」是正文第 1 段的连续子串，但 unicode61 把整段长句当成一个
    词元，所以按子词查命中 0 条。这是限制的准确形状：不是「中文召回率为零」，
    而是「召回单位是词元而不是词」。
    """

    store, retriever, source_id = _retriever(tmp_path)
    try:
        # 前提断言：子串确实逐字在正文里，排除「原文里没有这句话」这种假阳性解释。
        indexed = retriever.search(source_id, [AFTER_PUNCTUATION])
        assert len(indexed) == 1
        assert "肌筋膜疼痛" in indexed[0].text
        assert "统计学意义" in indexed[0].text

        assert retriever.search(source_id, ["肌筋膜疼痛"]) == []
        assert retriever.search(source_id, ["统计学意义"]) == []

        # 但写成整段词元就能命中——同一个段落、同一个查询词，只差词元边界。
        assert [p.native_jats_id for p in retriever.search(source_id, [CONTINUOUS])] == ["c1"]
    finally:
        store.close()


def test_a_chinese_query_still_cannot_become_a_match_operator():
    """中文照样走引号包裹，模型给的中文不会被当成 FTS5 语法。"""

    assert compile_match(["死亡率 AND 下降"]) == '"死亡率" OR "AND" OR "下降"'
    assert compile_match(['说"引号']) == '"说""引号"'
