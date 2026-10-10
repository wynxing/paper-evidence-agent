"""Compile plain query phrases into an FTS5 MATCH expression.

Per 技术选型 D4 the model submits ordinary word groups, never MATCH programs.
Each query is split on Unicode whitespace, every word has its inner double quotes
doubled and is wrapped in double quotes, and the deduplicated terms are joined
with a program-fixed ``OR``. The result is always bound as a SQL parameter, so
model text can never become a MATCH operator or SQL fragment.
"""

import re

__all__ = ["NoIndexableTerms", "compile_match"]

# A word needs at least one letter or digit to be indexable.
_INDEXABLE = re.compile(r"[^\W_]", re.UNICODE)


class NoIndexableTerms(ValueError):
    """Raised when query phrases contain no indexable term (MODEL_INVALID_OUTPUT)."""


def _quote_term(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def compile_match(queries: list[str]) -> str:
    """Return the FTS5 MATCH expression for a list of plain query phrases.

    Raises ``NoIndexableTerms`` when no term survives, which the workflow maps to
    MODEL_INVALID_OUTPUT and may repair once.
    """

    terms: list[str] = []
    for query in queries:
        for word in query.split():
            if not _INDEXABLE.search(word):
                continue
            quoted = _quote_term(word)
            if quoted not in terms:
                terms.append(quoted)
    if not terms:
        raise NoIndexableTerms("queries 不含可索引词项")
    return " OR ".join(terms)
