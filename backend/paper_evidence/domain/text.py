"""Text and location contract from 术语表「文本与定位契约」.

These helpers freeze paragraph text, paragraph identity and quote spans. They do
not trim or fuzzy-normalize quotes: a quote is valid only when it appears as an
exact substring of the frozen paragraph text. Case, quotes, hyphens and Unicode
normalization form are never rewritten.
"""

import re
from hashlib import sha256

__all__ = [
    "normalize_paragraph_text",
    "paragraph_hash",
    "paragraph_id",
    "quote_spans",
    "is_blank_claim",
]

# A run of Unicode whitespace collapses to a single U+0020.
_WHITESPACE_RUN = re.compile(r"\s+")


def is_blank_claim(claim: str) -> bool:
    """Empty claims are rejected using a whitespace-trimmed temporary copy.

    The persisted claim keeps the author's original string.
    """

    return not claim.strip()


def normalize_paragraph_text(raw: str) -> str:
    """Collapse in-paragraph whitespace runs and trim paragraph ends."""

    return _WHITESPACE_RUN.sub(" ", raw).strip()


def paragraph_hash(frozen_text: str) -> str:
    """SHA-256 of the frozen paragraph text encoded as UTF-8."""

    return sha256(frozen_text.encode("utf-8")).hexdigest()


def paragraph_id(source_key: str, version_hash: str, parser_version: str, ordinal: int) -> str:
    """Build the local paragraph id ``p:<source-key>:<version-hash>:<parser>:<ordinal>``.

    ``source_key`` is the normalized PMCID, ``parser_version`` must not contain a
    colon, and ``ordinal`` starts at 1 in body document order.
    """

    if ":" in parser_version:
        raise ValueError("parser_version must not contain ':'")
    if ordinal < 1:
        raise ValueError("ordinal starts at 1")
    return f"p:{source_key}:{version_hash}:{parser_version}:{ordinal}"


def quote_spans(text: str, quote: str) -> list[tuple[int, int]]:
    """Return every half-open Unicode code-point span where quote occurs exactly.

    Repeated matches return all spans so the interface can disambiguate. An empty
    quote returns no spans instead of matching everywhere.
    """

    if not quote:
        return []
    spans: list[tuple[int, int]] = []
    start = text.find(quote)
    while start != -1:
        spans.append((start, start + len(quote)))
        start = text.find(quote, start + 1)
    return spans
