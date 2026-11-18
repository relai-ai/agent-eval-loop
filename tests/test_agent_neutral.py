"""Tests for agent-neutral tasks with their own services: the example MCP service, a minimal task
built from it and check_task.py's service checks.
Run: python3 -m unittest discover -s tests"""

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

from helpers import EXAMPLES, Repo, harbor_job, harbor_trial

TOKEN = "test-token"

TASK_TOML = """\
[task]
name = "relai-tests/save-a-note"
version = "0.1.0"
description = "A minimal task with its own service"

[agent]
timeout_sec = 600

[verifier]
timeout_sec = 120

[[environment.mcp_servers]]
name = "notes"
transport = "streamable-http"
url = "http://notes:8000/mcp"

[metadata.relai]
id = "save-a-note"
behavior = "Saves the note the user asked for."
split = "development"
agent_neutral = true

[metadata.relai.services]
source = "written"
origin = "a minimal fixture for the plugin's tests"
primary = "saved-the-note"
category = "notes"

[[metadata.relai.evaluators]]
id = "saved-the-note"
type = "code"
method = "exact"
criterion = "The notes service holds a note with the expected text."
min_score = 0.0
max_score = 1.0

[[metadata.relai.evaluators]]
id = "reports-the-note"
type = "judge"
method = "semantic"
criterion = "The agent tells the user the note was saved."
rubric = "tests/judges/reports-the-note.md"
inputs = ["verifier/mock-journal.jsonl"]
min_score = 0.0
max_score = 1.0
"""

COMPOSE = f"""\
services:
  main:
    depends_on:
      notes:
        condition: service_healthy
  notes:
    build:
      context: ./notes
    expose:
      - "8000"
    environment:
      RELAI_VERIFIER_TOKEN: "{TOKEN}"
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)"]
      interval: 2s
      retries: 15
"""

TOOLS = [
    {"name": "save_note", "description": "Save a note.",
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "get_note", "description": "Read one note by its id.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}},
    {"name": "list_notes", "description": "List every note.", "inputSchema": {"type": "object", "properties": {}}},
]

HANDLERS = '''\
"""Handlers for the notes service. ToolError is provided by mcp_service.py."""


def save_note(state, arguments):
    text = str(arguments.get("text") or "").strip()
    if not text:
        raise ToolError("text is required")
    note = {"id": f"note-{len(state['notes']) + 1}", "text": text}
    state["notes"].append(note)
    return note


def get_note(state, arguments):
    for note in state["notes"]:
        if note["id"] == arguments.get("id"):
            return note
    raise ToolError(f"no note with id {arguments.get('id')!r}")


def list_notes(state, arguments):
    return state["notes"]
'''

SOLVE = '''\
import json
import urllib.request

URL = "http://notes:8000/mcp"


def rpc(method, params, ident):
    body = json.dumps({"jsonrpc": "2.0", "id": ident, "method": method, "params": params}).encode()
    request = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())["result"]


rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}}, 1)
rpc("tools/call", {"name": "save_note", "arguments": {"text": "Buy milk"}}, 2)
'''

VERIFY = '''\
import json
import os
import urllib.request
from pathlib import Path

from evaluate import Results

TESTS = Path(os.environ.get("RELAI_TESTS", "/tests"))
LOGS = Path(os.environ.get("RELAI_LOGS", "/logs"))
PARAMS = json.loads((TESTS / "params.json").read_text())


def fetch(path):
    request = urllib.request.Request(PARAMS["services"]["notes"] + path,
                                     headers={"Authorization": f"Bearer {PARAMS['token']}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def main():
    results = Results(["saved-the-note"])
    with results.check("saved-the-note"):
        (LOGS / "verifier" / "mock-journal.jsonl").write_bytes(fetch("/relai/journal"))
        notes = json.loads(fetch("/relai/state"))["notes"]
        saved = any(n["text"] == PARAMS["expected"] for n in notes)
        results.score("saved-the-note", 1.0 if saved else 0.0,
                      "Saved the note." if saved else f"No note reads {PARAMS['expected']!r}; full marks need one.")
    results.write(LOGS / "verifier")


if __name__ == "__main__":
    main()
'''

TEST_SH = """\
#!/bin/bash
set -u
rm -rf /logs/verifier
mkdir -p /logs/verifier
python3 -I -S -c "import runpy, sys; sys.path.append('/tests'); runpy.run_path('/tests/verify.py', run_name='__main__')"
"""


def write_task(root: Path) -> Path:
    """A minimal agent-neutral task with one notes service, laid out as relai/docs/files.md describes."""
    files = {
        "task.toml": TASK_TOML,
        "instruction.md": "Save a note that says: Buy milk.\n",
        "README.md": "# save-a-note\n\nA minimal fixture for the plugin's tests.\n",
        "environment/Dockerfile": "FROM python:3.12-slim-bookworm\nWORKDIR /app\n",
        "environment/docker-compose.yaml": COMPOSE,
        "environment/notes/Dockerfile": ('FROM python:3.12-slim-bookworm\nCOPY . /service\nEXPOSE 8000\n'
                                         'CMD ["python3", "/service/mcp_service.py", "--dir", "/service", "--port", "8000"]\n'),
        "environment/notes/tools.json": json.dumps(TOOLS, indent=2),
        "environment/notes/handlers.py": HANDLERS,
        "environment/notes/state.json": json.dumps({"notes": [{"id": "note-1", "text": "Seeded note"}]}),
        "environment/notes/mcp_service.py": (EXAMPLES / "mcp_service.py").read_text(),
        "solution/solve.sh": "#!/bin/bash\nset -euo pipefail\npython3 /solution/solve.py\n",
        "solution/solve.py": SOLVE,
        "tests/test.sh": TEST_SH,
        "tests/verify.py": VERIFY,
        "tests/evaluate.py": (EXAMPLES / "evaluate.py").read_text(),
        "tests/params.json": json.dumps({"services": {"notes": "http://notes:8000"}, "token": TOKEN,
                                         "expected": "Buy milk"}),
        "tests/judges/reports-the-note.md": "Full marks when the agent says the note was saved.\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if rel.endswith(".sh"):
            path.chmod(0o755)
    return root


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TaskFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="relai-neutral-"))
        self.task = write_task(self.tmp / "save-a-note")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class ServiceJournalTest(TaskFixture):
    def setUp(self) -> None:
        super().setUp()
        module = load(EXAMPLES / "mcp_service.py", "journal_service")
        self.service = module.Service(self.task / "environment" / "notes", "notes")

    def test_later_state_changes_preserve_the_response_previously_seen_by_the_agent(self):
        result = self.service.call("list_notes", {})
        observed = json.loads(result["content"][0]["text"])
        self.service.call("save_note", {"text": "A later note"})
        self.assertEqual(self.service.journal[0]["response"], observed)
        self.assertEqual(len(self.service.state["notes"]), len(observed) + 1)

    def test_a_handler_retaining_arguments_cannot_rewrite_the_recorded_input_or_response(self):
        def retain_request(state, arguments):
            state["request"] = arguments
            return arguments

        arguments = {"nested": {"text": "original"}}
        with patch.object(self.service.handlers, "list_notes", side_effect=retain_request):
            result = self.service.call("list_notes", arguments)
        observed = json.loads(result["content"][0]["text"])
        self.service.state["request"]["nested"]["text"] = "changed later"
        self.assertEqual(self.service.journal[0]["input"], observed)
        self.assertEqual(self.service.journal[0]["response"], observed)


class ServiceFixture:
    def __init__(self, folder: Path) -> None:
        self.module = load(EXAMPLES / "mcp_service.py", "example_mcp_service")
        with patch.dict("os.environ", {"RELAI_VERIFIER_TOKEN": TOKEN}):
            self.server = self.module.serve(folder, 0, "notes", host="127.0.0.1")
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


class MCPServiceTest(TaskFixture):
    def setUp(self) -> None:
        super().setUp()
        self.service = ServiceFixture(self.task / "environment" / "notes")

    def tearDown(self) -> None:
        self.service.close()
        super().tearDown()

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
        self.assertEqual(names, {"save_note", "get_note", "list_notes"})

    def test_calls_change_state_and_are_journaled(self):
        result = self.service.call("save_note", {"text": "Buy milk"})
        self.assertFalse(result["isError"])
        refused = self.service.call("get_note", {"id": "note-404"})
        self.assertTrue(refused["isError"])
        self.assertIn("no note", refused["content"][0]["text"])
        unknown = self.service.call("delete_everything", {})
        self.assertTrue(unknown["isError"])
        entries = self.journal()
        self.assertEqual([e["outcome"] for e in entries], ["matched", "matched", "unmatched"])
        self.assertEqual(entries[0]["state_change"], ["notes"])
        self.assertNotIn("state_change", entries[1])
        status, body = self.service.get("/relai/state")
        self.assertEqual(json.loads(body)["notes"][-1]["text"], "Buy milk")

    def test_journal_and_state_need_the_verifier_token(self):
        self.assertEqual(self.service.get("/relai/journal", token=None)[0], 403)
        self.assertEqual(self.service.get("/relai/state", token="wrong")[0], 403)
        self.assertEqual(self.service.get("/healthz", token=None)[0], 200)

    def test_a_crashing_handler_is_an_error_not_a_result(self):
        with patch.object(self.service.server.service.handlers, "list_notes", side_effect=KeyError("notes")):
            result = self.service.call("list_notes", {})
        self.assertTrue(result["isError"])
        self.assertEqual(self.journal()[-1]["outcome"], "error")


class NoTokenTest(TaskFixture):
    def test_without_a_token_the_journal_is_never_served(self):
        module = load(EXAMPLES / "mcp_service.py", "example_mcp_service_no_token")
        with patch.dict("os.environ", {"RELAI_VERIFIER_TOKEN": ""}):
            server = module.serve(self.task / "environment" / "notes", 0, "notes", host="127.0.0.1")
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


class TaskVerdictTest(TaskFixture):
    def test_reference_solution_scores_full_marks_and_doing_nothing_fails_the_primary_check(self):
        for solve in (True, False):
            service = ServiceFixture(self.task / "environment" / "notes")
            try:
                tests = self.tmp / f"tests-{solve}"
                shutil.copytree(self.task / "tests", tests)
                params = json.loads((tests / "params.json").read_text())
                params.update(services={"notes": service.url}, token=TOKEN)
                (tests / "params.json").write_text(json.dumps(params))
                if solve:
                    script = (self.task / "solution" / "solve.py").read_text()
                    exec(compile(script.replace("http://notes:8000", service.url), "solve.py", "exec"), {})
                logs = self.tmp / f"logs-{solve}"
                (logs / "verifier").mkdir(parents=True)
                with patch.dict("os.environ", {"RELAI_TESTS": str(tests), "RELAI_LOGS": str(logs)}):
                    sys.path.insert(0, str(tests))
                    try:
                        load(tests / "verify.py", f"fixture_verify_{solve}").main()
                    finally:
                        sys.path.remove(str(tests))
                        sys.modules.pop("evaluate", None)
                reward = json.loads((logs / "verifier" / "reward.json").read_text())
                self.assertEqual(reward, {"saved-the-note": 1.0 if solve else 0.0})
                if solve:
                    self.assertTrue((logs / "verifier" / "mock-journal.jsonl").read_text().strip())
            finally:
                service.close()


class CheckServicesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = Repo()
        self.project.write("relai/relai.toml", '[harbor]\nversion = "0.26.0"\n\n[judge]\nmode = "subagent"\n')
        self.task = write_task(self.project.relai / "tests" / "save-a-note")

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

    def test_a_minimal_task_passes(self):
        out = self.check()
        self.assertIn("PASS: task tests/save-a-note", out)

    def test_a_server_that_is_not_a_sidecar_is_an_error(self):
        self.edit("task.toml", "http://notes:8000/mcp", "http://mail:8000/mcp")
        self.assertIn("not a sidecar service", self.check())

    def test_copying_a_sidecar_into_the_agent_image_is_an_error(self):
        self.edit("environment/Dockerfile", "WORKDIR /app\n", "COPY notes/state.json /app/\nWORKDIR /app\n")
        self.assertIn("build context of service 'notes'", self.check())
        self.edit("environment/Dockerfile", "COPY notes/state.json /app/\n", "COPY . /app/\n")
        self.assertIn("copies the whole context", self.check())

    def test_stdio_servers_warn_and_a_separate_verifier_is_an_error(self):
        self.edit("task.toml", 'transport = "streamable-http"\nurl = "http://notes:8000/mcp"',
                  'transport = "stdio"\ncommand = "python3"')
        self.assertIn("runs over stdio inside the agent's container", self.check())
        self.edit("task.toml", "[verifier]\n", '[verifier]\nenvironment_mode = "separate"\n')
        self.assertIn("shares the agent's container", self.check())

    def test_a_judge_primary_is_valid_but_an_unknown_primary_is_an_error(self):
        self.edit("task.toml", 'primary = "saved-the-note"', 'primary = "reports-the-note"')
        self.assertIn("PASS: task tests/save-a-note", self.check())
        self.edit("task.toml", 'primary = "reports-the-note"', 'primary = "missing"')
        self.assertIn("primary must name the declared evaluator", self.check())

    def test_a_neutral_task_without_either_table_is_an_error(self):
        self.edit("task.toml", "[metadata.relai.services]", "[metadata.relai.other]")
        self.assertIn("no [metadata.relai.services] table", self.check())


NATIVE_TASK_TOML = '''\
[metadata.relai]
id = "service-result"
behavior = "Produces a useful explanation from the service data."
agent_neutral = true

[metadata.relai.services]
source = "written"
origin = "a synthetic service contract fixture"
primary = "useful-explanation"

[[metadata.relai.evaluators]]
id = "useful-explanation"
type = "judge"
method = "semantic"
criterion = "The explanation answers the request using the service data."
rubric = "tests/judges/explanation.md"
inputs = ["verifier/reply.txt"]
min_score = 0.0
max_score = 1.0

[[metadata.relai.evaluators]]
id = "service-state"
type = "code"
method = "exact"
criterion = "The expected state is preserved."
min_score = 0.0
max_score = 1.0
'''


class NativeServiceTaskTest(unittest.TestCase):
    def setUp(self) -> None:
        self.project = Repo()
        self.project.write("relai/relai.toml", '[runner]\nkind = "native"\nisolation = "container"\n')
        self.task = self.project.write("relai/tests/service-result/task.toml", NATIVE_TASK_TOML).parent
        self.project.write("relai/tests/service-result/instruction.md", "Explain the service result.")
        self.project.write("relai/tests/service-result/tests/judges/explanation.md",
                           "Full marks for a useful explanation supported by the service result.")

    def tearDown(self) -> None:
        self.project.close()

    def check(self):
        return self.project.run("check_task.py", str(self.task))

    def test_native_service_metadata_needs_no_harbor_structure(self):
        out = self.check()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("static checks do not certify", out.stdout)
        self.assertFalse((self.task / "environment").exists())
        self.assertFalse((self.task / "solution").exists())

    def test_native_validation_retains_primary_and_secret_checks(self):
        path = self.task / "task.toml"
        path.write_text(NATIVE_TASK_TOML.replace('primary = "useful-explanation"', 'primary = "missing"'))
        out = self.check()
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("primary must name the declared evaluator", out.stdout)
        path.write_text(NATIVE_TASK_TOML)
        (self.task / ".env").write_text("SYNTHETIC_TOKEN=fixture-only\n")
        out = self.check()
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("secret values never go in a task", out.stdout)

    def test_native_judge_primary_requires_a_valid_rubric(self):
        (self.task / "tests" / "judges" / "explanation.md").unlink()
        out = self.check()
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("rubric", out.stdout)

    def trial(self, job, name, judgment=None, with_trajectory=False):
        trial = harbor_trial(job, name, self.task, {"service-state": 1.0},
                             feedback={"service-state": "state preserved"},
                             judges={"useful-explanation": judgment} if judgment is not None else None,
                             with_trajectory=with_trajectory)
        result_path = trial / "result.json"
        result = json.loads(result_path.read_text())
        result.update(runner="native", runner_id="fixture-service", runner_command="fixture")
        result_path.write_text(json.dumps(result))
        (trial / "verifier" / "reply.txt").write_text("An explanation from the service result.")
        return trial

    def summary(self, job):
        output = self.project.root / "summary.json"
        out = self.project.run("summarize.py", str(job), "--json", str(output))
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        return json.loads(output.read_text())["run"]

    def test_judge_primary_scores_and_keeps_pending_and_errors_out_of_solved_denominator(self):
        job = harbor_job(self.project.root / "runs", "job", 4)
        self.trial(job, "pass", {"score": 1.0, "feedback": "supported and useful"})
        self.trial(job, "fail", {"score": 0.0, "feedback": "does not answer the request"})
        self.trial(job, "pending")
        self.trial(job, "error", {"error": "judge unavailable"})
        run = self.summary(job)
        test = run["tests"]["tests/service-result"]
        self.assertEqual(test["solved"]["solved"], 1)
        self.assertEqual(test["solved"]["scored"], 2)
        self.assertEqual(test["solved"]["attempts"], 4)
        self.assertEqual(test["solved"]["rate"], 0.5)
        self.assertEqual(test["status_counts"]["judges pending"], 1)
        self.assertEqual(test["status_counts"]["evaluator error"], 1)
        self.assertEqual(run["solved"]["attempts"], 2)

    def test_a_primary_needing_a_missing_trajectory_cannot_establish_success(self):
        path = self.task / "task.toml"
        path.write_text(NATIVE_TASK_TOML.replace('inputs = ["verifier/reply.txt"]', 'inputs = ["trajectory"]'))
        self.assertEqual(self.check().returncode, 0)
        job = harbor_job(self.project.root / "runs", "job", 2)
        self.trial(job, "absent", {"score": 1.0, "feedback": "stale judgment"})
        self.trial(job, "present", {"score": 1.0, "feedback": "supported"}, with_trajectory=True)
        test = self.summary(job)["tests"]["tests/service-result"]
        self.assertEqual(test["status_counts"]["unscored"], 1)
        self.assertEqual(test["solved"]["solved"], 1)
        self.assertEqual(test["solved"]["scored"], 1)
        absent = next(t for t in test["trials"] if t["trial"] == "absent")
        self.assertEqual(absent["evaluators"]["useful-explanation"]["state"], "not recorded")
        self.assertIsNone(absent["score"])

    def test_a_missing_primary_input_invalidates_a_stale_judgment(self):
        for index, name in enumerate(("verifier/reply.txt", "instruction")):
            with self.subTest(input=name):
                (self.task / "task.toml").write_text(
                    NATIVE_TASK_TOML.replace('inputs = ["verifier/reply.txt"]', f'inputs = ["{name}"]'))
                job = harbor_job(self.project.root / "runs", f"job-{index}", 1)
                trial = self.trial(job, "missing", {"score": 1.0, "feedback": "stale judgment"})
                path = self.task / "instruction.md" if name == "instruction" else trial / name
                path.unlink()
                test = self.summary(job)["tests"]["tests/service-result"]
                self.assertEqual(test["solved"]["scored"], 0)
                self.assertIsNone(test["solved"]["rate"])
                self.assertEqual(test["status_counts"]["evaluator error"], 1)
                outcome = test["trials"][0]["evaluators"]["useful-explanation"]
                self.assertEqual(outcome["state"], "error")
                self.assertIn(name, outcome["message"])


if __name__ == "__main__":
    unittest.main()
