"""Freeze licensed JATS full text into paragraph records.

The parser version is immutable and its output is deterministic: the same source
bytes and parser version always yield the same ids, text and hashes. Paragraph
text is taken in document order, JATS entities are resolved, in-paragraph
whitespace runs collapse to a single U+0020 and paragraph ends are trimmed. Case,
quotes, hyphens and Unicode normalization form are preserved.
"""

import xml.etree.ElementTree as ElementTree

from paper_evidence.config import PARSER_VERSION
from paper_evidence.domain import ContractError, ErrorCode
from paper_evidence.domain.records import Paragraph, SourceSnapshot
from paper_evidence.domain.text import normalize_paragraph_text, paragraph_hash, paragraph_id

__all__ = ["parse_snapshot", "parse_jats"]

# Paragraph elements that hold prose. Titles, captions and table cells are
# handled separately or not indexed in the first version.
_PARAGRAPH_TAGS = {"p", "list-item"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _section_title(element: ElementTree.Element) -> str | None:
    for child in element:
        if _local(child.tag) == "title":
            return normalize_paragraph_text("".join(child.itertext()))
    return None


def _walk(element: ElementTree.Element, section: str | None):
    """Yield (section, paragraph_element) in document order."""

    for child in element:
        name = _local(child.tag)
        if name in {"sec", "abstract"}:
            yield from _walk(child, _section_title(child) or section)
        elif name in _PARAGRAPH_TAGS:
            yield section, child
        else:
            yield from _walk(child, section)


def parse_jats(snapshot: SourceSnapshot) -> list[Paragraph]:
    """Parse one licensed JATS snapshot into frozen paragraph records."""

    source_key = snapshot.metadata.pmcid or snapshot.source_id
    version_hash = snapshot.metadata.version_hash or ""
    access_url = snapshot.metadata.access_url or ""
    try:
        root = ElementTree.fromstring(snapshot.jats_bytes)
    except ElementTree.ParseError as error:
        raise ContractError(ErrorCode.CONTENT_INCOMPLETE, "JATS 解析失败") from error

    body = None
    abstract = None
    for element in root.iter():
        name = _local(element.tag)
        if name == "body" and body is None:
            body = element
        elif name == "abstract" and abstract is None:
            abstract = element

    paragraphs: list[Paragraph] = []
    ordinal = 0
    seen_ids: set[str] = set()
    hashes: dict[str, str] = {}
    containers = [item for item in (abstract, body) if item is not None] or [root]
    for container in containers:
        for section, element in _walk(container, None):
            ordinal += 1
            text = normalize_paragraph_text("".join(element.itertext()))
            if not text:
                continue
            pid = paragraph_id(source_key, version_hash, PARSER_VERSION, ordinal)
            digest = paragraph_hash(text)
            if pid in seen_ids:
                raise ContractError(ErrorCode.CONTENT_INCOMPLETE, "段落 ID 重复")
            if hashes.get(digest, text) != text:
                # Same hash for different content would make the frozen text
                # ambiguous; identical repeated text is allowed.
                raise ContractError(ErrorCode.CONTENT_INCOMPLETE, "相同哈希对应不同内容")
            seen_ids.add(pid)
            hashes[digest] = text
            paragraphs.append(
                Paragraph(
                    paragraph_id=pid,
                    source_id=source_key,
                    section=section or "body",
                    text=text,
                    paragraph_hash=digest,
                    source_url=access_url,
                    native_jats_id=element.get("id"),
                )
            )
    return paragraphs


def parse_snapshot(snapshot: SourceSnapshot) -> list[Paragraph]:
    """Alias kept for callers that read better with an explicit snapshot name."""

    return parse_jats(snapshot)
