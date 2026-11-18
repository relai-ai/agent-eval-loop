"""Tests for agent-neutral tasks with their own services: the example MCP service, the ask_user
handlers, the example task and check_task.py's service checks. Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from helpers import EXAMPLES, Repo

EXAMPLE_TASK = EXAMPLES / "agent-neutral-task" / "move-one-on-one"
TOKEN = "test-token"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ServiceFixture:
    def __init__(self, folder: Path) -> None:
        self.module = load(EXAMPLES / "mcp_service.py", "example_mcp_service")
        with patch.dict("os.environ", {"RELAI_VERIFIER_TOKEN": TOKEN}):
            self.server = self.module.serve(folder, 0, "office", host="127.0.0.1")
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def rpc(self, method: str, params: dict | None = None, ident: int | None = 1) -> dict | None:
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if ident is not None:
            message["id"] = ident
        request = urllib.request.Request(self.url + "/mcp", data=json.dumps(message).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read()
            return json.loads(body) if body else {"status": response.status}

    def call(self, tool: str, arguments: dict) -> dict:
        return self.rpc("tools/call", {"name": tool, "arguments": arguments})["result"]

    def get(self, path: str, token: str | None = TOKEN) -> tuple[int, bytes]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url + path, headers=headers), timeout=10) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as exc:
            exc.close()
            return exc.code, b""


class MCPServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ServiceFixture(EXAMPLE_TASK / "environment" / "office")

    def tearDown(self) -> None:
        self.service.close()

    def journal(self) -> list[dict]:
        status, body = self.service.get("/relai/journal")
        self.assertEqual(status, 200)
        return [json.loads(line) for line in body.decode().splitlines()]

    def test_initialize_and_tools_list_serve_the_task_tools(self):
        init = self.service.rpc("initialize", {"protocolVersion": "2025-06-18"})["result"]
        self.assertEqual(init["protocolVersion"], "2025-06-18")
        self.assertIn("tools", init["capabilities"])
        self.assertEqual(self.service.rpc("notifications/initialized", ident=None), {"status": 202})
        names = {t["name"] for t in self.service.rpc("tools/list")["result"]["tools"]}
        self.assertIn("send_email", names)

    def test_calls_change_state_and_are_journaled(self):
        result = self.service.call("update_event", {"id": "evt-1", "start": "2026-11-20T10:00", "end": "2026-11-20T10:30"})
        self.assertFalse(result["isError"])
        refused = self.service.call("update_event", {"id": "evt-404"})
        self.assertTrue(refused["isError"])
        self.assertIn("no event", refused["content"][0]["text"])
        unknown = self.service.call("wipe_inbox", {})
        self.assertTrue(unknown["isError"])
        entries = self.journal()
        self.assertEqual([e["outcome"] for e in entries], ["matched", "matched", "unmatched"])
        self.assertEqual(entries[0]["state_change"], ["events"])
        self.assertNotIn("state_change", entries[1])
        self.assertEqual([e["seq"] for e in entries], [1, 2, 3])
        for entry in entries:
            self.assertLessEqual(entry["received_at"], entry["responded_at"])
        self.assertNotIn("seq", result["content"][0]["text"])
        status, body = self.service.get("/relai/state")
        self.assertEqual(json.loads(body)["events"][0]["start"], "2026-11-20T10:00")

    def test_a_created_event_never_reuses_a_seeded_id(self):
        created = json.loads(self.service.call("create_event", {
            "title": "Coffee", "start": "2026-11-21T09:00", "end": "2026-11-21T09:30"})["content"][0]["text"])
        status, body = self.service.get("/relai/state")
        ids = [e["id"] for e in json.loads(body)["events"]]
        self.assertEqual(len(ids), len(set(ids)), ids)
        self.assertIn(created["id"], ids)

    def test_journal_and_state_need_the_verifier_token(self):
        self.assertEqual(self.service.get("/relai/journal", token=None)[0], 403)
        self.assertEqual(self.service.get("/relai/state", token="wrong")[0], 403)
        self.assertEqual(self.service.get("/healthz", token=None)[0], 200)

    def test_a_crashing_handler_is_an_error_not_a_result(self):
        with patch.object(self.service.server.service.handlers, "search_email", side_effect=KeyError("inbox")):
            result = self.service.call("search_email", {"query": "dana"})
        self.assertTrue(result["isError"])
        self.assertEqual(self.journal()[-1]["outcome"], "error")


class NoTokenTest(unittest.TestCase):
    def test_without_a_token_the_journal_is_never_served(self):
        module = load(EXAMPLES / "mcp_service.py", "example_mcp_service_no_token")
        with patch.dict("os.environ", {"RELAI_VERIFIER_TOKEN": ""}):
            server = module.serve(EXAMPLE_TASK / "environment" / "office", 0, "office", host="127.0.0.1")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/relai/journal"
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": "Bearer "}), timeout=10)
            caught.exception.close()
            self.assertEqual(caught.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()


class AskUserTest(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(EXAMPLES))
        self.module = load(EXAMPLES / "ask_user.py", "example_ask_user")
        self.module.ToolError = type("ToolError", (Exception,), {})

    def tearDown(self) -> None:
        sys.path.remove(str(EXAMPLES))

    def test_the_simulated_user_answers_with_the_request_as_its_first_message(self):
        state = {"request": "Move my 1:1.", "user": {"instructions": "You are Alex.", "model": "anthropic:m"}}
        seen = {}

        def fake(spec, history, key):
            seen["history"] = [dict(m) for m in history]
            seen["key"] = key
            return "Friday at 10.", False

        with patch.object(self.module, "simulated_user_turn", fake), patch.dict("os.environ", {"RELAI_USER_SIM_KEY": "k"}):
            answer = self.module.ask_user(state, {"question": "Which day works?"})
        self.assertEqual(answer, "Friday at 10.")
        self.assertEqual(seen["history"], [{"role": "user", "content": "Move my 1:1."},
                                           {"role": "assistant", "content": "Which day works?"}])
        self.assertEqual(state["history"][-1], {"role": "user", "content": "Friday at 10."})

    def test_questions_stop_at_the_limit_and_a_missing_key_is_an_error(self):
        state = {"request": "r", "user": {}, "max_questions": 1,
                 "history": [{"role": "user", "content": "r"}, {"role": "assistant", "content": "q"}]}
        self.assertEqual(self.module.ask_user(state, {"question": "again?"}), self.module.NOTHING_TO_ADD)
        with patch.dict("os.environ", {"RELAI_USER_SIM_KEY": ""}), self.assertRaises(RuntimeError):
            self.module.ask_user({"request": "r", "user": {}}, {"question": "q"})
        with self.assertRaises(self.module.ToolError):
            self.module.ask_user({}, {"question": " "})

    def test_scripted_replies_answer_in_order_without_a_model(self):
        state = {"request": "Clean my inbox.", "replies": ["Delete the promotions.", "That's all."]}

        def no_model(spec, history, key):
            raise AssertionError("a scripted user must not call the model")

        with patch.object(self.module, "simulated_user_turn", no_model), patch.dict("os.environ", {"RELAI_USER_SIM_KEY": ""}):
            answers = [self.module.ask_user(state, {"question": q}) for q in ("Proposal?", "More?", "Anything else?")]
        self.assertEqual(answers, ["Delete the promotions.", "That's all.", "That's all."])
        self.assertEqual(state["history"][:3], [{"role": "user", "content": "Clean my inbox."},
                                                {"role": "assistant", "content": "Proposal?"},
                                                {"role": "user", "content": "Delete the promotions."}])


class ExampleTaskTest(unittest.TestCase):
    def test_copied_files_match_the_plugin_examples(self):
        self.assertEqual((EXAMPLE_TASK / "environment" / "office" / "mcp_service.py").read_text(),
                         (EXAMPLES / "mcp_service.py").read_text())
        self.assertEqual((EXAMPLE_TASK / "tests" / "evaluate.py").read_text(), (EXAMPLES / "evaluate.py").read_text())

    def test_reference_solution_scores_full_marks_and_doing_nothing_fails_the_primary_check(self):
        tmp = Path(tempfile.mkdtemp(prefix="relai-neutral-"))
        try:
            for solve in (True, False):
                service = ServiceFixture(EXAMPLE_TASK / "environment" / "office")
                try:
                    tests = tmp / f"tests-{solve}"
                    shutil.copytree(EXAMPLE_TASK / "tests", tests)
                    params = json.loads((tests / "params.json").read_text())
                    params.update(services={"office": service.url}, token=TOKEN)
                    (tests / "params.json").write_text(json.dumps(params))
                    if solve:
                        script = (EXAMPLE_TASK / "solution" / "solve.py").read_text()
                        exec(compile(script.replace("http://office:8000", service.url), "solve.py", "exec"), {})
                    logs = tmp / f"logs-{solve}"
                    (logs / "verifier").mkdir(parents=True)
                    with patch.dict("os.environ", {"RELAI_TESTS": str(tests), "RELAI_LOGS": str(logs)}):
                        sys.path.insert(0, str(tests))
                        try:
                            load(tests / "verify.py", f"example_verify_{solve}").main()
                        finally:
                            sys.path.remove(str(tests))
                            sys.modules.pop("evaluate", None)
                    reward = json.loads((logs / "verifier" / "reward.json").read_text())
                    if solve:
                        self.assertEqual(reward, {"moved-the-meeting": 1.0, "replied-to-dana": 1.0, "no-wrong-recipient": 1.0})
                        self.assertTrue((logs / "verifier" / "mock-journal.jsonl").read_text().strip())
                    else:
                        self.assertEqual(reward["moved-the-meeting"], 0.0)
                finally:
                    service.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class CheckServicesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = Repo()
        self.project.write("relai/relai.toml", '[harbor]\nversion = "0.26.0"\n\n[judge]\nmode = "subagent"\n')
        self.task = self.project.relai / "tests" / "move-one-on-one"
        shutil.copytree(EXAMPLE_TASK, self.task)

    def tearDown(self) -> None:
        self.project.close()

    def check(self) -> str:
        ran = self.project.run("check_task.py", str(self.task), "--no-harbor")
        return ran.stdout + ran.stderr

    def edit(self, rel: str, old: str, new: str) -> None:
        path = self.task / rel
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new))

    def test_the_example_task_passes(self):
        out = self.check()
        self.assertIn("PASS: task tests/move-one-on-one", out)

    def test_a_server_that_is_not_a_sidecar_is_an_error(self):
        self.edit("task.toml", "http://office:8000/mcp", "http://mail:8000/mcp")
        self.assertIn("not a sidecar service", self.check())

    def test_copying_a_sidecar_into_the_agent_image_is_an_error(self):
        self.edit("environment/Dockerfile", "WORKDIR /app\n", "COPY office/state.json /app/\nWORKDIR /app\n")
        self.assertIn("build context of service 'office'", self.check())
        self.edit("environment/Dockerfile", "COPY office/state.json /app/\n", "COPY . /app/\n")
        self.assertIn("copies the whole context", self.check())

    def test_stdio_servers_warn_and_a_separate_verifier_or_missing_primary_is_an_error(self):
        self.edit("task.toml", 'transport = "streamable-http"\nurl = "http://office:8000/mcp"',
                  'transport = "stdio"\ncommand = "python3"')
        self.assertIn("runs over stdio inside the agent's container", self.check())
        self.edit("task.toml", "[verifier]\n", '[verifier]\nenvironment_mode = "separate"\n')
        self.assertIn("shares the agent's container", self.check())
        self.edit("task.toml", 'primary = "moved-the-meeting"', 'primary = "confirms-new-time"')
        self.assertIn("must be a code evaluator that reads the services' journals", self.check())

    def test_a_neutral_task_without_either_table_is_an_error(self):
        self.edit("task.toml", "[metadata.relai.services]", "[metadata.relai.other]")
        self.assertIn("no [metadata.relai.services] table", self.check())


if __name__ == "__main__":
    unittest.main()
