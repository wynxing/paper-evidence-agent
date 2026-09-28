"""Static checks for repository documentation; no network, models or dependencies."""
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

SPEC_DOCS = ("glossary", "prd", "architecture", "test-plan", "tech-stack", "evaluation")
LIMITS = dict(main_requests=3, repair_requests=1, attempts_per_request=2, supplemental_rounds=1)
TIMEOUTS = dict(model_attempt_seconds=45, source_request_seconds=15, task_seconds=180)
PACKET_KEYS = set("schema_version case_id run_id trace_id previous_id cancel_requested status label error_code input source run_config evidence_candidates decision execution model_calls criteria accounting".split())
ERROR_TOKEN = re.compile(r"\b(?:DOI|METADATA|REGISTRATION_AGENCY|SOURCE|LICENSE|CONTENT|RETRIEVAL|UPSTREAM|TASK|BUDGET|MODEL|QUOTE)_[A-Z][A-Z_]+\b")


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f"non-JSON constant: {value}")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def blocks(text):
    """Return prose and fenced blocks; support backtick/tilde fences, fail unclosed."""
    prose, found, body = [], [], []
    fence = None
    language = ""
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if fence is None and match:
            fence, language = match[1], match[2].strip()
            body = []
        elif fence is not None:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                found.append((language, "\n".join(body)))
                fence = None
            else:
                body.append(line)
        else:
            prose.append(line)
    if fence is not None:
        raise ValueError("unclosed code fence")
    return "\n".join(prose), found


def anchors(prose):
    used = set()
    for title in re.findall(r"^\s{0,3}#{1,6}\s+(.+?)(?:\s+#+)?$", prose, re.M):
        title = re.sub(r"`|\*|<[^>]+>", "", title).lower()
        base = "".join(c for c in title if c in "-_ " or unicodedata.category(c)[0] in "LN").replace(" ", "-")
        slug, suffix = base, 0
        while slug in used:
            suffix += 1
            slug = f"{base}-{suffix}"
        used.add(slug)
    return used


def check_markdown(root, paths):
    errors, stats, parsed = [], Counter(), {}
    for path in paths:
        try:
            prose, fenced = blocks(path.read_text(encoding="utf-8-sig"))
            parsed[path.resolve()] = (prose, anchors(prose))
            stats["markdown"] += 1
            for kind, raw in fenced:
                if kind == "json":
                    strict_json(raw)
                    stats["json"] += 1
                if kind == "mermaid":
                    if not re.match(r"\s*(flowchart|graph|stateDiagram-v2)\b", raw):
                        raise ValueError("unsupported Mermaid diagram type")
                    stats["mermaid_fences_only"] += 1
        except (ValueError, OSError) as exc:
            errors.append(f"{path.name}: {exc}")
    for path, (prose, _) in parsed.items():
        for match in re.finditer(r"!?\[[^\]\n]*\]\((<[^>]+>|[^)\n]+)\)", prose):
            href = match[1]
            href = href[1:-1] if href.startswith("<") else href.split(' "', 1)[0]
            url = urlsplit(href)
            if url.scheme or url.netloc:
                continue
            target = (path.parent / unquote(url.path)).resolve() if url.path else path
            stats["local_links"] += 1
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                errors.append(f"{path.name}: missing/outside local target {href}")
            elif url.fragment:
                if target not in parsed or unquote(url.fragment) not in parsed[target][1]:
                    errors.append(f"{path.name}: missing anchor {href}")
    return errors, stats


def check_contracts(docs):
    errors, stats = [], Counter()
    def need(condition, message):
        if not condition:
            errors.append(message)
    try:
        glossary = docs["docs/glossary.md"]
        versions = [re.search(r"^版本：(\S+?)\\?$", docs[f"docs/{name}.md"], re.M)[1] for name in SPEC_DOCS]
        need(len(set(versions)) == 1, "document versions disagree")
        error_section = glossary.split("## 4. 错误码", 1)[1].split("## 5.", 1)[0]
        mapping = dict(re.findall(r"^\| `([A-Z_]+)` \| .*? \| `([A-Z_]+)` \|$", error_section, re.M))
        states_section = glossary.split("## 2. 任务状态", 1)[1].split("## 3.", 1)[0]
        states = set(re.findall(r"^\| `([A-Z_]+)` \|", states_section, re.M))
        stats.update(error_codes=len(mapping), task_states=len(states))
        referenced = set(ERROR_TOKEN.findall("\n".join(docs.values())))
        need(referenced == set(mapping), f"unregistered error codes: {sorted(referenced-set(mapping))}")
        other_docs = "\n".join(v for k, v in docs.items() if k != "docs/glossary.md")
        for code in mapping:
            need(code in other_docs, f"error code has no reference outside glossary: {code}")
        architecture = docs["docs/architecture.md"]
        state_diagram = next(raw for kind, raw in blocks(architecture)[1] if kind == "mermaid" and "stateDiagram-v2" in raw)
        need(set(re.findall(r"\b[A-Z][A-Z_]+\b", state_diagram)) == states, "state diagram differs from glossary")
        examples = [strict_json(raw) for body in docs.values() for kind, raw in blocks(body)[1] if kind == "json"]
        packets = [obj for obj in examples if isinstance(obj, dict) and "schema_version" in obj]
        need(len(packets) == 1, "expected one diagnostic packet example")
        schema = re.search(r"\| `schema_version` \| 固定 `([^`]+)`", glossary)[1]
        packet_table = glossary.split("### 输入诊断包", 1)[1].split("| 候选字段", 1)[0]
        documented_keys = set()
        for row in packet_table.splitlines():
            if row.startswith("| "):
                for field in re.findall(r"`([^`]+)`", row.split("|")[1]):
                    documented_keys.add(field.split(".")[0].removesuffix("[]"))
        need(documented_keys == PACKET_KEYS, "diagnostic field table differs from contract")
        for obj in examples:
            if not isinstance(obj, dict):
                continue
            if obj.get("agent") == "paper":
                need(set(obj) == set("agent label rationale supported_parts scope_differences limitations evidence validation".split()), "decision example fields mismatch")
                need(obj["label"] in {"支持", "部分支持", "相矛盾", "证据不足"} and obj["validation"] == "pass", "decision label/validation invalid")
                for evidence in obj["evidence"]:
                    need(set(evidence) == set("paragraph_id quote section source_url paragraph_hash validation".split()), "evidence fields mismatch")
                    need(evidence["validation"] == "pass", "published evidence is invalid")
            if "outcome" in obj:
                need(set(obj) == {"outcome", "findings"} and obj["outcome"] in {"confirmed", "suspected", "insufficient_evidence"}, "review example shape invalid")
                for finding in obj["findings"]:
                    need(set(finding) == set("stage error_code observation evidence_refs cause_hypothesis reproduction_steps regression_assertion uncertainty".split()), "review finding fields mismatch")
                    need(finding["error_code"] in mapping, "review finding error undefined")
            if obj.get("status") == "CANCELLED":
                need(all(obj.get(k) is None for k in ("label", "decision", "error_code")), "cancelled example must have null result")
                need(obj.get("cancel_requested") is True, "cancelled example missing accepted flag")
        for packet in packets:
            need(set(packet) == PACKET_KEYS, "diagnostic packet fields differ from contract")
            need(packet["schema_version"] == schema == "2.2", "diagnostic schema version mismatch")
            config = packet["run_config"]
            need(set(config) == set("profile config_digest snapshot_ref authorized_recipients limits timeouts observability".split()), "run_config fields mismatch")
            need(config["limits"] == LIMITS and config["timeouts"] == TIMEOUTS, "budget/timeout example drift")
            for key, value in {**LIMITS, **TIMEOUTS}.items():
                need(f"{key}={value}" in glossary, f"budget field table mismatch: {key}")
            need(config["observability"] == {"langfuse_enabled": False, "recipient": None}, "example observability must be disabled by default")
            need(set(packet["criteria"]) == set("version digest snapshot_ref implementation_revision".split()), "criteria fields mismatch")
            status, code = packet["status"], packet["error_code"]
            need(status in states and mapping.get(code) == status, "packet error/state mismatch")
            if status != "COMPLETED":
                need(packet["decision"] is None, "non-completed packet has decision")
            calls = packet["model_calls"]
            request_ids = [c["request_id"] for c in calls]
            need(len(request_ids) == len(set(request_ids)), "duplicate request ID")
            attempts = [a for c in calls for a in c["attempts"]]
            need(len({a["attempt_id"] for a in attempts}) == len(attempts), "duplicate attempt ID")
            for call in calls:
                need(len(call["attempts"]) <= LIMITS["attempts_per_request"], "attempt budget exceeded")
                need([a["attempt_index"] for a in call["attempts"]] == list(range(1,len(call["attempts"])+1)), "attempt ordering invalid")
                for attempt in call["attempts"]:
                    need(attempt["recipient"] in config["authorized_recipients"], "unauthorized example recipient")
                    need(attempt["error_code"] is None or attempt["error_code"] in mapping, "unknown attempt error")
            for step in packet["execution"]:
                need(step["request_id"] is None or step["request_id"] in request_ids, "unlinked execution request")
            account = packet["accounting"]
            need(set(account) == set("verification main_requests_used repair_requests_used supplemental_rounds_used upstream_attempts_used observed_upstream_attempts reason".split()), "accounting fields mismatch")
            need(account["observed_upstream_attempts"] == len(attempts), "observed attempts mismatch")
            repairs = sum(c["purpose"] == "output_repair" for c in calls)
            need(account["main_requests_used"] == len(calls)-repairs and account["repair_requests_used"] == repairs, "logical request accounting mismatch")
            need(account["main_requests_used"] <= LIMITS["main_requests"] and repairs <= LIMITS["repair_requests"], "logical budget exceeded")
            if account["verification"] == "verified":
                need(account["upstream_attempts_used"] == len(attempts) and account["reason"] is None, "verified accounting inconsistent")
            else:
                need(account["verification"] == "unverified" and account["upstream_attempts_used"] is None and bool(account["reason"]), "unverified accounting inconsistent")
        # Deliberately narrow patterns: historical discussion and negations are allowed.
        active_docs = "\n".join(docs.get(f"docs/{name}.md", "") for name in SPEC_DOCS)
        for old in ("请求 3 再要求补读或任何即将超出授权预算", "最后一步继续申请补读、或即将超过调用预算", "只允许一次调用", "不使用 LiteLLM Proxy。"):
            need(old not in active_docs, f"superseded rule remains: {old}")
    except (KeyError, IndexError, TypeError, ValueError, StopIteration) as exc:
        errors.append(f"contract shape missing or malformed: {exc}")
    return errors, stats


def main():
    root = Path(__file__).resolve().parents[1]
    # Tracked files plus this task's untracked files; never scan ignored caches/secrets.
    output = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root)
    paths = [root / name for name in output.decode("utf-8").split("\0") if name]
    md = [p for p in paths if p.suffix == ".md"]
    errors, stats = check_markdown(root, md)
    docs = {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8-sig") for p in md if p.parent == root / "docs"}
    contract_errors, contract_stats = check_contracts(docs)
    errors.extend(contract_errors)
    stats.update(contract_stats)
    secret = re.compile(r"(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|Bearer [A-Za-z0-9._-]{24,})")
    for path in paths:
        if path.suffix in {".md", ".py", ".json", ".yaml", ".yml"}:
            if secret.search(path.read_text(encoding="utf-8-sig")):
                errors.append(f"{path.relative_to(root)}: possible credential (value suppressed)")
    for error in errors:
        print(f"FAIL: {error}")
    print(json.dumps(dict(stats), ensure_ascii=False, sort_keys=True))
    print("Static documentation checks only; no application/model/semantic test coverage.")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
