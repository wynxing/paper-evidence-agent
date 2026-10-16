"""Freeze real PMC sources into a committed inventory — C1's *source* half.

测试方案要求首版用「小规模**真实 PMC 来源集**」，人工核对 DOI、版本、许可、原文位置与预期
判断。那份工作分两半，本文件只做**不需要人判断**的那一半：

* 本文件：把真实来源取回并冻结成一份**可复查的清单**——来源身份、许可、逐段序号/章节/哈希。
* 人的那一半（本文件**不做**，也不该由脚本做）：为每段写论断、核对预期标签与引文，并由
  **另一人复核**。落在清单的 ``claims`` 字段里，默认是空数组。

**为什么清单里不放正文全文。** 这里刻意只存哈希与短预览，不把文章正文提交进仓库：

1. 许可虽为 CC BY，但仓库规范要求"不将论文全文提交到仓库"时先取得明确许可，本文件不替团队
   做这个决定；
2. 更重要的是，**把快照烘进仓库会让内容漂移变得不可见**。只存哈希、运行时重新取回并比对，
   PMC 一旦改了正文就会立刻显形（``--check`` 退出非零），而不是悄悄换掉验收依据。

为什么判据是 ``article_sha256``（``#84`` 之后实现已与术语表对齐）
----------------------------------------------------------

`glossary` 说 ``source.version_hash`` 是「取得的 JATS 原始字节 SHA-256」。**``#84`` 之前**
实现里 ``jats_bytes`` 存的是**整个 OAI-PMH 响应**，而那个信封带一个 ``<responseDate>``
时间戳、**每次请求都不同**，于是 ``version_hash``、``source_id`` 与 ``paragraph_id``
**每次取回都变**（`#67`）。实测（2026-10-15，`PMC1182327`）：相隔 4 秒取两次，
``responseDate`` 由 ``12:27:19Z`` 变为 ``12:27:23Z``，整包 SHA-256 与 ``version_hash`` 都变，
而逐段 ``paragraph_hash`` 与段落数完全一致。``#84`` 之后 ``sources/pmc.py`` 的 ``_article_bytes``
从响应字节里**切出** ``<article>`` 子树，上述三个标识已跨次稳定（实测 2026-10-16：两次都是
73 797 字节、``sha256=caf353df06c98af8…``），本节下面三条判据不变。

所以本清单：

* 用 ``article_sha256``（``<article>`` 子树字节的 SHA-256）作**漂移判据**——它是稳定的；
* 用逐段 ``ordinal`` / ``section`` / ``paragraph_hash`` 作**段落判据**——它们也稳定；
* **不记录** ``paragraph_id``：本清单冻于 `#84` 之前，那时的 ``paragraph_id`` 内嵌一个每次都变的 ``version_hash``，作为跨次引用是错的（`#84` 之后它已稳定，见 `#67`）；
* 把 ``response_sha256`` 与 ``version_hash`` 原样记下来，但**不参与比对**，只作为「当次取回
  应用看到的是什么」的痕迹。注意 ``#84`` 之后 ``jats_bytes`` 已是 ``<article>`` 子树，因此
  **新冻结出来的清单里 ``response_sha256`` 会等于 ``article_sha256``**；已提交的清单里它仍是
  旧口径（整包响应）的值，两者不同不是漂移。

用法::

    python tests/functional/freeze_sources.py --out tests/functional/sources 10.1371/journal.pmed.0020124
    python tests/functional/freeze_sources.py --check        # 重新取回并比对已提交的清单
"""

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

# ``backend/.venv`` is editable-installed against **one** checkout. Running this
# script from a different worktree would otherwise import that checkout's backend
# silently, and it can be many commits behind (measured 2026-10-15: the main
# worktree sat 13 commits behind main and its ``Paragraph`` had no ``ordinal``).
# Put this worktree's backend first so the tool always describes the code it ships
# with. Under pytest the ``pythonpath`` setting already does this.
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from paper_evidence.api.deps import Services  # noqa: E402
from paper_evidence.config import Settings  # noqa: E402
from paper_evidence.domain import ContractError  # noqa: E402
from paper_evidence.retrieval.jats import parse_jats  # noqa: E402

SOURCES = Path(__file__).parent / "sources"
SCHEMA = 2
DEADLINE_SECONDS = 120.0
PREVIEW_CHARS = 120


def article_bytes(raw: bytes) -> bytes:
    """The ``<article>`` subtree of an OAI response, byte-exact.

    Sliced rather than re-serialised so the digest is over the upstream bytes, and
    it excludes the per-request ``<responseDate>`` that makes the full response
    unstable.
    """

    start = raw.find(b"<article")
    end = raw.rfind(b"</article>")
    if start == -1 or end == -1:
        raise ValueError("响应里没有 <article> 子树，无法计算稳定哈希")
    return raw[start:end + len(b"</article>")]


async def _with_backoff(call, *, attempts: int = 4, pause: float = 6.0):
    """Retry a live fetch with a pause; ``Fetcher``'s own retry has no backoff."""

    last = None
    for index in range(attempts):
        try:
            return await call()
        except ContractError as error:
            last = error
            if index + 1 < attempts:
                await asyncio.sleep(pause)
    raise last


def freeze(doi: str, work: Path, *, with_text: bool = False) -> dict:
    """Fetch one real record and describe it as a frozen inventory entry."""

    async def run():
        services = Services(replace(Settings.from_env(), data_dir=work, contact_email=""))
        try:
            service = services.source_service()
            snapshot = await _with_backoff(
                lambda: service.fetch(doi, time.monotonic() + DEADLINE_SECONDS)
            )
        finally:
            services.close()
        return snapshot

    snapshot = asyncio.run(run())
    return describe(snapshot, with_text=with_text)


def describe(snapshot, *, with_text: bool = False) -> dict:
    """The inventory entry for one frozen snapshot. No article text beyond a preview."""

    metadata = snapshot.metadata
    paragraphs = parse_jats(snapshot)
    entry = {
        "schema": SCHEMA,
        "case_id": metadata.pmcid or snapshot.source_id,
        "provenance": {
            "doi": metadata.doi,
            "pmcid": metadata.pmcid,
            "title": metadata.title,
            "authors": list(metadata.authors),
            "year": metadata.year,
            "license": metadata.license,
            "version": metadata.version,
            "access_url": metadata.access_url,
        },
        # Stable: the article payload without the per-request OAI envelope.
        "article_sha256": hashlib.sha256(article_bytes(snapshot.jats_bytes)).hexdigest(),
        # Unstable by nature — recorded for traceability, never compared.
        "response_sha256": hashlib.sha256(snapshot.jats_bytes).hexdigest(),
        "version_hash": metadata.version_hash,
        "response_bytes": len(snapshot.jats_bytes),
        "paragraph_count": len(paragraphs),
        "paragraphs": [
            {
                # ``ordinal`` is the stable reference. ``paragraph_id`` is not, and
                # is deliberately not recorded: it embeds the per-fetch version hash.
                "ordinal": item.ordinal,
                "section": item.section,
                "paragraph_hash": item.paragraph_hash,
                "text_length": len(item.text),
                "native_jats_id": item.native_jats_id,
                "preview": item.text[:PREVIEW_CHARS],
            }
            for item in paragraphs
        ],
        # Filled in by hand during the human pass (C2) and reviewed by a second
        # person (C4). A script must never fill this in.
        "claims": [],
    }
    if with_text:
        # Opt-in only: embedding the article makes drift invisible (see module
        # docstring), so it must be an explicit choice rather than a default.
        entry["jats_text"] = snapshot.jats_bytes.decode("utf-8")
    return entry


def differences(live: dict, stored: dict) -> list[str]:
    """Every way the live source no longer matches the committed inventory.

    ``response_sha256`` / ``version_hash`` are deliberately **not** compared: they
    change on every fetch and would report drift always. See the module docstring.
    """

    found: list[str] = []
    if live["article_sha256"] != stored["article_sha256"]:
        found.append(
            f"正文（<article>）哈希变了：清单 {stored['article_sha256'][:16]}…，"
            f"现在 {live['article_sha256'][:16]}…"
        )
    for key in ("license", "version", "pmcid"):
        if live["provenance"].get(key) != stored["provenance"].get(key):
            found.append(
                f"provenance.{key} 变了：清单 {stored['provenance'].get(key)!r}，"
                f"现在 {live['provenance'].get(key)!r}"
            )
    if live["paragraph_count"] != stored["paragraph_count"]:
        found.append(
            f"段落数变了：清单 {stored['paragraph_count']}，现在 {live['paragraph_count']}"
        )
    stored_by_ordinal = {item["ordinal"]: item for item in stored["paragraphs"]}
    live_by_ordinal = {item["ordinal"]: item for item in live["paragraphs"]}
    for ordinal in sorted(set(stored_by_ordinal) | set(live_by_ordinal)):
        old, new = stored_by_ordinal.get(ordinal), live_by_ordinal.get(ordinal)
        if old is None:
            found.append(f"多出 ordinal {ordinal}")
        elif new is None:
            found.append(f"少了 ordinal {ordinal}")
        elif old["paragraph_hash"] != new["paragraph_hash"]:
            found.append(f"ordinal {ordinal} 的段落正文变了（哈希不再一致）")
        elif old["section"] != new["section"]:
            found.append(
                f"ordinal {ordinal} 的章节变了：{old['section']!r} → {new['section']!r}"
            )
    return found


def path_for(out_dir: Path, case_id: str) -> Path:
    return out_dir / f"{case_id}.json"


def load_all(out_dir: Path) -> list[dict]:
    return [
        json.loads(item.read_text(encoding="utf-8"))
        for item in sorted(out_dir.glob("*.json"))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dois", nargs="*", help="要冻结的 DOI；--check 时忽略")
    parser.add_argument("--out", type=Path, default=SOURCES)
    parser.add_argument("--check", action="store_true", help="重新取回并比对已提交的清单")
    parser.add_argument("--with-text", action="store_true",
                        help="连同 JATS 正文一起冻结（会失去漂移可见性，见模块说明）")
    args = parser.parse_args()

    work = Path(tempfile.mkdtemp(prefix="freeze-sources-"))

    if args.check:
        stored = load_all(args.out)
        if not stored:
            print(f"{args.out} 下没有清单可比对", file=sys.stderr)
            return 2
        failed = 0
        for entry in stored:
            live = freeze(entry["provenance"]["doi"], work)
            found = differences(live, entry)
            if found:
                failed += 1
                print(f"[漂移] {entry['case_id']}")
                for line in found:
                    print(f"    - {line}")
            else:
                print(f"[一致] {entry['case_id']}（{entry['paragraph_count']} 段）")
        if failed:
            print(f"\n{failed}/{len(stored)} 个来源与清单不一致；"
                  "正文变了就要重新核对 claims，别只更新哈希", file=sys.stderr)
            return 1
        print(f"\n{len(stored)} 个来源都与清单一致")
        return 0

    if not args.dois:
        print("请给出至少一个 DOI（或用 --check）", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    for doi in args.dois:
        entry = freeze(doi, work, with_text=args.with_text)
        target = path_for(args.out, entry["case_id"])
        target.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"已写入 {target}（{entry['paragraph_count']} 段，许可 {entry['provenance']['license']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
