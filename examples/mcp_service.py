#!/usr/bin/env python3
"""A mock service for an agent-neutral task: serves the task's tools over MCP from a sidecar container.

  python3 mcp_service.py --dir /service --port 8000 [--name mail]

Any agent Harbor installs reaches the same tools through the task's [[environment.mcp_servers]]
entry, so the task does not depend on one agent's harness. The --dir folder holds:

  tools.json   [{"name", "description", "inputSchema"}, ...]: the tools every agent sees
  handlers.py  one function per tool, named like the tool: handler(state, arguments) returns a
               JSON value for the agent; raise ToolError("message") for an error the agent should
               see (ToolError is provided, no import needed)
  state.json   the starting state; handlers read and change it in place

Endpoints:

  POST /mcp            MCP over streamable HTTP (initialize, tools/list, tools/call, ping), answered
                       as application/json
  GET  /healthz        200 once the service has loaded
  GET  /relai/journal  the call journal as JSON lines, for the verifier only
  GET  /relai/state    the current state as JSON, for the verifier only

The two /relai endpoints need "Authorization: Bearer <token>" with the token in the service's
RELAI_VERIFIER_TOKEN environment variable, set in environment/docker-compose.yaml and copied into
tests/, which reaches the agent's container only after the agent is done. Without the variable
they refuse every request.

Each journal line follows relai/docs/files.md (Mocks): target, operation, input, outcome
(matched, unmatched or error), response, and state_change (the top-level state keys the call
changed). A call to a tool that has no handler is answered with an error and journaled as
unmatched; nothing falls through to a real service. Standard library only.
"""

from __future__ import annotations

import argparse
import copy
import hmac
import importlib.util
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_PROTOCOL = "2025-06-18"


class ToolError(Exception):
    """An error the agent should see as the tool's result, the way the real service reports it."""


class Service:
    def __init__(self, folder: Path, name: str) -> None:
        self.name = name
        self.tools = json.loads((folder / "tools.json").read_text(encoding="utf-8"))
        if not isinstance(self.tools, list) or not all(isinstance(t, dict) and t.get("name") for t in self.tools):
            raise ValueError("tools.json must be a list of tool definitions, each with a name")
        state_file = folder / "state.json"
        self.state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {}
        spec = importlib.util.spec_from_file_location(f"relai_handlers_{name}", folder / "handlers.py")
        module = importlib.util.module_from_spec(spec)
        module.ToolError = ToolError
        sys.path.insert(0, str(folder.resolve()))
        spec.loader.exec_module(module)
        self.handlers = module
        self.journal: list[dict] = []
        self.lock = threading.Lock()

    def tool_names(self) -> set[str]:
        return {t["name"] for t in self.tools}

    def call(self, tool: str, arguments: dict) -> dict:
        entry = {"target": self.name, "operation": tool, "input": arguments}
        handler = getattr(self.handlers, tool, None) if tool in self.tool_names() else None
        with self.lock:
            if not callable(handler):
                text = f"unknown tool {tool!r}"
                entry.update(outcome="unmatched", response=text)
                self.journal.append(entry)
                return {"content": [{"type": "text", "text": text}], "isError": True}
            before = copy.deepcopy(self.state)
            try:
                value = handler(self.state, arguments)
                text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                entry.update(outcome="matched", response=value)
                result = {"content": [{"type": "text", "text": text}], "isError": False}
            except ToolError as exc:
                entry.update(outcome="matched", response={"error": str(exc)})
                result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
            except Exception as exc:
                entry.update(outcome="error", response={"error": f"{type(exc).__name__}: {exc}"})
                print(f"[mcp_service] handler {tool} failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                result = {"content": [{"type": "text", "text": "internal error"}], "isError": True}
            changed = sorted(k for k in set(before) | set(self.state) if before.get(k) != self.state.get(k))
            if changed:
                entry["state_change"] = changed
            self.journal.append(entry)
            return result

    def rpc(self, message: dict) -> dict | None:
        method, ident, params = message.get("method"), message.get("id"), message.get("params") or {}
        if ident is None:
            return None
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion") or DEFAULT_PROTOCOL,
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": self.name, "version": "1"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": self.tools}
        elif method == "tools/call":
            arguments = params.get("arguments") or {}
            if not isinstance(params.get("name"), str) or not isinstance(arguments, dict):
                return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": "tools/call needs a name and object arguments"}}
            result = self.call(params["name"], arguments)
        else:
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"method {method!r} not found"}}
        return {"jsonrpc": "2.0", "id": ident, "result": result}


def make_handler(service: Service, token: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return

        def send(self, status: int, body: bytes = b"", content_type: str = "application/json") -> None:
            self.send_response(status)
            if body:
                self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorized(self) -> bool:
            given = self.headers.get("Authorization", "")
            return bool(token) and hmac.compare_digest(given.encode(), f"Bearer {token}".encode())

        def do_GET(self) -> None:
            if self.path == "/healthz":
                self.send(200, b"ok", "text/plain")
            elif self.path in ("/relai/journal", "/relai/state"):
                if not self.authorized():
                    self.send(403, b"forbidden", "text/plain")
                    return
                with service.lock:
                    if self.path == "/relai/journal":
                        body = "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in service.journal)
                        self.send(200, body.encode(), "application/jsonl")
                    else:
                        self.send(200, json.dumps(service.state, ensure_ascii=False).encode())
            else:
                self.send(405 if self.path == "/mcp" else 404)

        def do_DELETE(self) -> None:
            self.send(405)

        def do_POST(self) -> None:
            if self.path != "/mcp":
                self.send(404)
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                message = json.loads(self.rfile.read(length) or b"null")
            except (ValueError, OSError):
                body = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
                self.send(400, json.dumps(body).encode())
                return
            if not isinstance(message, dict):
                body = {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "send one JSON-RPC object"}}
                self.send(400, json.dumps(body).encode())
                return
            reply = service.rpc(message)
            if reply is None:
                self.send(202)
            else:
                self.send(200, json.dumps(reply, ensure_ascii=False).encode())

    return Handler


def serve(folder: Path, port: int, name: str, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    service = Service(folder, name)
    server = ThreadingHTTPServer((host, port), make_handler(service, os.environ.get("RELAI_VERIFIER_TOKEN", "")))
    server.service = service
    return server


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="folder with tools.json, handlers.py and state.json")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--name", default=None, help="the service name recorded as each journal line's target")
    args = parser.parse_args()
    folder = Path(args.dir)
    try:
        server = serve(folder, args.port, args.name or folder.resolve().name)
    except (OSError, ValueError) as exc:
        print(f"[mcp_service] cannot start: {exc}", file=sys.stderr)
        return 2
    if not os.environ.get("RELAI_VERIFIER_TOKEN"):
        print("[mcp_service] RELAI_VERIFIER_TOKEN is unset, so the verifier cannot read the journal", file=sys.stderr)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
