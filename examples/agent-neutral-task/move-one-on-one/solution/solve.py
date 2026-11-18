"""Reference solution: does what a correct assistant would, through the same MCP tools every agent gets."""

from __future__ import annotations

import json
import urllib.request

URL = "http://office:8000/mcp"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def rpc(method: str, params: dict, ident: int) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": ident, "method": method, "params": params}).encode()
    with urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=HEADERS), timeout=30) as response:
        reply = json.loads(response.read())
    if "error" in reply or reply["result"].get("isError"):
        raise SystemExit(f"{method} failed: {reply}")
    return reply["result"]


def call(tool: str, arguments: dict, ident: int) -> dict:
    return rpc("tools/call", {"name": tool, "arguments": arguments}, ident)


rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "reference-solution", "version": "1"}}, 1)
call("update_event", {"id": "evt-1", "start": "2026-11-20T10:00", "end": "2026-11-20T10:30"}, 2)
call("send_email", {"to": ["dana.lee@example.com"], "subject": "Re: Thursday 1:1", "in_reply_to": "m-101",
                    "body": "Hi Dana,\n\nNo problem. I moved our 1:1 to Friday at 10:00.\n\nAlex"}, 3)
