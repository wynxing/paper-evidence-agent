"""Canonical digests, text/location contract and terminal mappings."""

import hashlib

import pytest

from paper_evidence.domain import ErrorCode, TaskStatus
from paper_evidence.domain.digest import canonical_json, digest_of
from paper_evidence.domain.rules import (
    BLOCKED_CODES,
    FAILED_CODES,
    criteria_reference,
    criteria_snapshot,
    terminal_status,
)
from paper_evidence.domain.text import (
    is_blank_claim,
    normalize_paragraph_text,
    paragraph_hash,
    paragraph_id,
    quote_spans,
)


def test_canonical_json_sorts_keys_and_is_compact():
    value = {"b": 1, "a": {"d": [2, 1], "c": "值"}}
    assert canonical_json(value) == '{"a":{"c":"值","d":[2,1]},"b":1}'.encode("utf-8")
    assert b"\n" not in canonical_json(value) and not canonical_json(value).startswith(b"\xef\xbb\xbf")


def test_canonical_digest_rules_from_the_glossary():
    base = {"a": "x y", "b": [1, 2], "c": 0}
    # Key order does not change the digest.
    assert digest_of({"c": 0, "b": [1, 2], "a": "x y"}) == digest_of(base)
    # String whitespace and array order do change it.
    assert digest_of({**base, "a": "x  y"}) != digest_of(base)
    assert digest_of({**base, "b": [2, 1]}) != digest_of(base)
    assert len(digest_of(base)) == 64


def test_canonical_numbers_have_no_exponent_and_normalize_negative_zero():
    assert canonical_json(1e-05) == b"0.00001"
    assert canonical_json(-0.0) == b"0"
    assert canonical_json(1.50) == b"1.5"
    with pytest.raises(ValueError):
        canonical_json(float("nan"))
    with pytest.raises(ValueError):
        canonical_json(float("inf"))
    with pytest.raises(TypeError):
        canonical_json({"a", "b"})


def test_paragraph_normalization_and_identity():
    assert normalize_paragraph_text("  a\n\t b\u00a0c  ") == "a b c"
    frozen = normalize_paragraph_text("The \n treatment\u00a0worked.")
    assert paragraph_hash(frozen) == hashlib.sha256(frozen.encode("utf-8")).hexdigest()
    assert paragraph_id("PMC123", "abc", "jats-0.1.0", 2) == "p:PMC123:abc:jats-0.1.0:2"
    with pytest.raises(ValueError):
        paragraph_id("PMC123", "abc", "bad:version", 1)
    with pytest.raises(ValueError):
        paragraph_id("PMC123", "abc", "jats-0.1.0", 0)


def test_quote_spans_are_exact_and_can_repeat():
    text = "one two one"
    assert quote_spans(text, "one") == [(0, 3), (8, 11)]
    assert quote_spans(text, "") == []
    assert quote_spans(text, "One") == []
    # No trimming or fuzzy normalization of the quote; ' one' starts at offset 7.
    assert quote_spans(text, " one") == [(7, 11)]


def test_claim_blank_check_uses_a_temporary_copy():
    assert is_blank_claim("   \n ") is True
    assert is_blank_claim(" keep ") is False


def test_terminal_status_matches_the_glossary_tables():
    for code in BLOCKED_CODES:
        assert terminal_status(code) is TaskStatus.BLOCKED
    for code in FAILED_CODES:
        assert terminal_status(code) is TaskStatus.FAILED
    assert terminal_status(ErrorCode.RETRIEVAL_EMPTY) is TaskStatus.COMPLETED
    assert terminal_status(None) is TaskStatus.FAILED


def test_criteria_reference_is_stable_and_content_addressed():
    first = criteria_reference("abc123")
    second = criteria_reference("abc123")
    assert first == second
    assert first["snapshot_ref"] == f"criteria:sha256:{first['digest']}"
    assert first["implementation_revision"] == "abc123"
    assert criteria_snapshot()["text_rules"]["quote"] == "精确子串，不 trim，不模糊归一化"
