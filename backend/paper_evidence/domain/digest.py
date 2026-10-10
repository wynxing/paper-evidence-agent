"""Canonical JSON digests for criteria and frozen configuration.

The rules come from 术语表「调用账与版本归属」: object keys are sorted by
Unicode code point, separators are compact, non-ASCII is not escaped, array
order is preserved, numbers are integers or the shortest exponent-free decimal
string, and digests are SHA-256 over the UTF-8 bytes of that canonical JSON.
The digest functions never add a BOM or a trailing newline.
"""

import json
from decimal import Decimal
from hashlib import sha256

__all__ = ["canonical_json", "digest_of"]


def _number(value: float) -> str:
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("NaN and Infinity are not valid canonical numbers")
    if value == 0:
        return "0"
    text = format(Decimal(repr(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _dump(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _number(value)
    if isinstance(value, str):
        return _string(value)
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_dump(item) for item in value) + "]"
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise TypeError("canonical JSON object keys must be strings")
        items = sorted(value.items(), key=lambda item: item[0])
        return "{" + ",".join(f"{_string(key)}:{_dump(item)}" for key, item in items) + "}"
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json(value: object) -> bytes:
    """Serialize a JSON-compatible value to canonical UTF-8 bytes."""

    return _dump(value).encode("utf-8")


def digest_of(value: object) -> str:
    """Return the lowercase SHA-256 hex digest of the canonical JSON bytes."""

    return sha256(canonical_json(value)).hexdigest()
