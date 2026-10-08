"""DOI normalization and format validation.

Format validation happens before any resolve call: 架构设计「GET
/api/sources/resolve」 maps a malformed DOI to DOI_INVALID without creating a
task or calling a model. Dropping the resolver prefix does not claim the DOI
exists; only the official services may do that.
"""

import re

from paper_evidence.domain import ContractError, ErrorCode

__all__ = ["is_valid_doi", "normalize_doi", "require_valid_doi"]

_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/", "doi:")
_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")


def normalize_doi(raw: str) -> str:
    """Lowercase and strip a resolver prefix; DOIs are case-insensitive."""

    value = raw.strip()
    lowered = value.lower()
    for prefix in _PREFIXES:
        if lowered.startswith(prefix):
            value = value[len(prefix):].strip()
            break
    return value.lower()


def is_valid_doi(raw: str) -> bool:
    return bool(_PATTERN.match(normalize_doi(raw)))


def require_valid_doi(raw: str) -> str:
    """Return the normalized DOI or raise DOI_INVALID."""

    if not is_valid_doi(raw):
        raise ContractError(ErrorCode.DOI_INVALID, "DOI 格式无效")
    return normalize_doi(raw)
