"""Local stand-ins for every upstream the app talks to, so the UI main path
runs end to end without the network.

测试方案要求界面主路径「不调用 Claude 或 Cursor」。这里把四类来源端点与模型
网关都换成本机进程内的替身：

* ``/crossref/works/{doi}``、``/crossref/works/{doi}/agency`` —— Crossref 元数据
* ``/doi/{doi}`` —— DOI 官方解析探针（返回 302，客户端不跟随）
* ``/pmc/idconv`` —— DOI → PMCID 转换
* ``/pmc/oai`` —— PMC OAI-PMH 的 GetRecord 响应（含真 JATS 的 ``<article>``）
* ``/openalex/works/doi:{doi}`` —— 开放获取线索
* ``POST /v1/chat/completions`` —— OpenAI 兼容模型网关

替身回的是**构造数据**：它能验证界面流程、状态流转与记账口径，**不能**用来
产出论文语义结论或性能数字（Issue #26 已写明这条边界）。真值判定在
`tests/functional/` 的冻结样本里，不在这里。

两个控制端点让用例可以按需改变上游行为，而不必重启进程：

* ``POST /_stub/delay {"seconds": N}`` —— 模型回复前等待 N 秒
* ``POST /_stub/mode {"mode": "ok" | "unavailable"}`` —— 让模型返回 503
* ``GET /_stub/state`` —— 当前状态，兼作就绪探针
"""

import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

__all__ = ["main"]

DOI = "10.1000/e2e-1"
PMCID = "PMC9900001"
TITLE = "E2E Demo Study of Antiplatelet Treatment"
#: 与下面 JATS 正文逐字一致，所以 decision 里的 quote 一定能通过 quote_spans 校验。
QUOTE = "reduced mortality by twenty percent"
#: 与正文用词一致，保证 FTS5 检索能命中这一条段落。
QUERIES = ["mortality", "treatment"]
PARAGRAPH = (
    "Treatment with aspirin reduced mortality by twenty percent in the older cohort "
    "compared with placebo."
)

ARTICLE = f"""<article xml:lang="en" version="1">
 <front><article-meta>
   <article-id pub-id-type="doi">{DOI}</article-id>
   <title-group><article-title>{TITLE}</article-title></title-group>
   <permissions><license license-type="cc-by">CC BY 4.0</license></permissions>
 </article-meta></front>
 <body><sec id="s1"><title>Results</title>
   <p id="n1">{PARAGRAPH}</p>
 </sec></body>
</article>
"""

OAI_ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
    "<responseDate>2026-01-01T00:00:00Z</responseDate>"
    "<request verb=\"GetRecord\">stub</request>"
    "<GetRecord><record><header><identifier>stub</identifier></header><metadata>"
    + ARTICLE
    + "</metadata></record></GetRecord></OAI-PMH>"
).encode("utf-8")


STATE = {"delay": 0.0, "mode": "ok"}
LOCK = threading.Lock()


def _model_reply(prompt: str) -> str:
    """Answer the one prompt shape the app sends, deterministically.

    查询生成与判断用的是同一份系统提示词风格，靠提示词里出现的关键片段区分：
    判断提示词带 ``"action":"final"``，查询提示词不带。
    """

    if '"action":"final"' not in prompt:
        return json.dumps({"queries": list(QUERIES)}, ensure_ascii=False)

    found = re.search(r"\[(p:[^\]]+)\]", prompt)
    if not found:
        # 没有候选段落时只能申请检索；空 queries 会被判非法，所以给固定词。
        return json.dumps(
            {"action": "retrieve", "queries": list(QUERIES), "neighbor_paragraph_ids": []},
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "action": "final",
            "decision": {
                "label": "支持",
                "rationale": "构造的上游回复，仅用于验证界面流程与状态流转。",
                "supported_parts": ["死亡率下降"],
                "scope_differences": [],
                "limitations": ["本回复由本机替身生成，不构成论文语义结论。"],
                "evidence": [{"paragraph_id": found.group(1), "quote": QUOTE}],
            },
        },
        ensure_ascii=False,
    )


def _model_body(prompt: str) -> bytes:
    payload = {
        "id": "chatcmpl-e2e-stub",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "agnes-2.5-flash",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": _model_reply(prompt)},
             "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ---------------------------------------------------------------- plumbing

    def log_message(self, *args) -> None:  # noqa: D102 - keep the run output readable
        pass

    def _send(self, status: int, payload: bytes, content_type: str, **headers) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        for name, value in headers.items():
            self.send_header(name.replace("_", "-"), value)
        self.end_headers()
        try:
            self.wfile.write(payload)
        except ConnectionError:
            # 应用在超时或取消时主动断开是**被覆盖的行为**（`04-upstream-timeout`
            # 与 `03-cancel` 就是靠它成立的），不是替身故障。BaseHTTPRequestHandler
            # 默认会把这类断开打成完整 traceback，刷掉真正的用例输出，所以这里吞掉。
            pass

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except ConnectionError:
            # 同上：客户端在读请求行前就断开，属于取消/超时的正常伴随现象。
            self.close_connection = True

    def _json(self, payload, status: int = 200) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except ValueError:
            return {}

    # -------------------------------------------------------------------- reads

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's naming
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if path == "/_stub/state":
            self._json(dict(STATE))
            return
        if path.startswith("/crossref/works/"):
            if path.endswith("/agency"):
                self._json({"message": {"agency": {"id": "crossref"}}})
                return
            self._json({"message": {
                "title": [TITLE],
                "author": [{"given": "Ada", "family": "Lovelace"}],
                "published-print": {"date-parts": [[2026]]},
            }})
            return
        if path.startswith("/doi/"):
            self._send(302, b"", "text/plain", Location=f"/stub/{DOI}")
            return
        if path == "/pmc/idconv":
            self._json({"records": [{"pmcid": PMCID, "doi": query.get("ids", [DOI])[0]}]})
            return
        if path == "/pmc/oai":
            self._send(200, OAI_ENVELOPE, "application/xml")
            return
        if path.startswith("/openalex/works/"):
            self._json({"open_access": {"is_oa": True},
                        "locations": [{"landing_page_url": "https://example.test/stub-landing"}]})
            return
        self._json({"message": f"未定义的替身路径 {path}"}, status=404)

    # ------------------------------------------------------------------- writes

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's naming
        path = unquote(urlparse(self.path).path)
        if path == "/v1/chat/completions":
            self._chat()
            return
        if path == "/_stub/delay":
            with LOCK:
                STATE["delay"] = float(self._body().get("seconds") or 0)
            self._json(dict(STATE))
            return
        if path == "/_stub/mode":
            with LOCK:
                STATE["mode"] = str(self._body().get("mode") or "ok")
            self._json(dict(STATE))
            return
        self._json({"message": f"未定义的替身路径 {path}"}, status=404)

    def _chat(self) -> None:
        payload = self._body()
        prompt = ""
        for message in payload.get("messages") or []:
            if isinstance(message, dict) and message.get("role") == "user":
                prompt = str(message.get("content") or "")
        with LOCK:
            delay, mode = STATE["delay"], STATE["mode"]
        if delay:
            time.sleep(delay)
        if mode == "unavailable":
            body = b'{"error": {"message": "stub upstream unavailable"}}'
            self._send(503, body, "application/json")
            return
        self._send(200, _model_body(prompt), "application/json")


def main() -> int:
    port = int(os.environ.get("PAPER_EVIDENCE_E2E_STUB_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
