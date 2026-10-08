"""FTS5 query compilation, JATS freezing and source-scoped retrieval."""

import pytest

from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.domain.contracts import SourceRecord
from paper_evidence.domain.records import SourceSnapshot
from paper_evidence.retrieval.jats import parse_jats
from paper_evidence.retrieval.local import StoreRetriever
from paper_evidence.retrieval.query import NoIndexableTerms, compile_match
from paper_evidence.storage.sqlite import SqliteStore

VERSION_HASH = "b" * 64

JATS = b"""<?xml version="1.0" encoding="UTF-8"?>
<article xml:lang="en">
  <front><article-meta><title-group><article-title>Demo</article-title></title-group></article-meta></front>
  <body>
    <sec id="s1"><title>Results</title>
      <p id="n1">The treatment reduced mortality by 20 percent.</p>
      <p id="n2">No   effect was observed in the control group.</p>
    </sec>
  </body>
</article>
"""


def snapshot(jats: bytes = JATS) -> SourceSnapshot:
    record = SourceRecord(
        title="Demo", doi="10.1000/xyz", pmcid="PMC123", license="CC BY", version="1",
        access_url="https://example.org/article", retrieved_at="2026-10-01T00:00:00+00:00",
        version_hash=VERSION_HASH,
    )
    return SourceSnapshot(source_id=f"PMC123:{VERSION_HASH}", metadata=record, jats_bytes=jats)


# --------------------------------------------------------------------- query


def test_compile_match_quotes_terms_and_joins_with_or():
    assert compile_match(["mortality reduction", "control"]) == '"mortality" OR "reduction" OR "control"'


def test_compile_match_doubles_inner_quotes_and_dedupes():
    assert compile_match(['sa"y', 'sa"y']) == '"sa""y"'


def test_compile_match_never_emits_bare_operators():
    match = compile_match(["AND OR NOT NEAR(x) colon: star* (paren)"])
    # Every surviving term is quoted, so FTS operators stay literal text.
    assert match == '"AND" OR "OR" OR "NOT" OR "NEAR(x)" OR "colon:" OR "star*" OR "(paren)"'


def test_compile_match_rejects_punctuation_only_queries():
    with pytest.raises(NoIndexableTerms):
        compile_match(["*** ---"])


# ---------------------------------------------------------------------- jats


def test_parse_jats_is_deterministic_and_freezes_text():
    first = parse_jats(snapshot())
    second = parse_jats(snapshot())
    assert [p.paragraph_id for p in first] == [p.paragraph_id for p in second]
    assert [p.paragraph_hash for p in first] == [p.paragraph_hash for p in second]
    assert first[0].paragraph_id == f"p:PMC123:{VERSION_HASH}:jats-0.1.0:1"
    assert first[1].text == "No effect was observed in the control group."
    assert first[0].section == "Results"
    assert first[0].native_jats_id == "n1"
    assert first[0].source_url == "https://example.org/article"


def test_parse_jats_rejects_unparsable_content():
    with pytest.raises(ContractError) as raised:
        parse_jats(snapshot(b"<article><body><p>broken"))
    assert raised.value.error_code is ErrorCode.CONTENT_INCOMPLETE


def test_new_version_hash_produces_a_new_namespace():
    other = snapshot()
    other = SourceSnapshot(source_id=other.source_id, metadata=other.metadata.model_copy(update={"version_hash": "c" * 64}), jats_bytes=other.jats_bytes)
    ids = {p.paragraph_id for p in parse_jats(other)}
    assert all(f":{'c' * 64}:" in item for item in ids)


# ----------------------------------------------------------------- retrieval


@pytest.fixture
def store(tmp_path):
    db = SqliteStore(tmp_path / "retrieval.sqlite3")
    yield db
    db.close()


def test_retrieval_is_source_scoped_and_fault_aware(store):
    source = snapshot()
    store.index_source(source.source_id, source.metadata, source.jats_bytes)
    store.index_paragraphs(source.source_id, parse_jats(source))
    retriever = StoreRetriever(store, context_limit=10)

    hits = retriever.search(source.source_id, ["mortality"])
    assert [p.native_jats_id for p in hits] == ["n1"]

    # A paragraph id from another source resolves to nothing.
    foreign = store.read_neighbors("PMC999:" + VERSION_HASH, [hits[0].paragraph_id])
    assert foreign == []
    assert retriever.read_neighbors(source.source_id, [hits[0].paragraph_id])[0].text == hits[0].text


def test_retrieval_index_fault_is_retrieval_failed(store):
    source = snapshot()
    store.index_source(source.source_id, source.metadata, source.jats_bytes)
    store.index_paragraphs(source.source_id, parse_jats(source))
    retriever = StoreRetriever(store, context_limit=10)
    store._conn.execute("DROP TABLE paragraphs_fts")  # simulate an index fault

    with pytest.raises(ContractError) as raised:
        retriever.search(source.source_id, ["mortality"])
    assert raised.value.error_code is ErrorCode.RETRIEVAL_FAILED


def test_retrieval_reports_unindexable_queries_as_output_problem(store):
    retriever = StoreRetriever(store, context_limit=10)
    with pytest.raises(ContractError) as raised:
        retriever.search("PMC123:" + VERSION_HASH, ["***"])
    assert raised.value.error_code is ErrorCode.MODEL_INVALID_OUTPUT
