"""Tests for controls.py (an agent-neutral coding task's controls in containers), freeze.py --require-controls and
check_task.py's controls and --frozen checks. Container runs are exercised through a fake engine and local
workspaces, so no container engine is needed.
Run: python3 -m unittest discover -s tests"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from helpers import TEMPLATE, Repo, harbor_trial
from test_coding_evals import CALC, fill_task, have_pytest, make_bundle, make_source_repo, protect, sh


def load_controls():
    spec = importlib.util.spec_from_file_location("relai_controls", TEMPLATE / "bin" / "controls.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(TEMPLATE / "bin"))
    spec.loader.exec_module(module)
    return module


UNFORMATTED = ("diff --git a/pkg/mod.py b/pkg/mod.py\nnew file mode 100644\n--- /dev/null\n+++ b/pkg/mod.py\n"
               "@@ -0,0 +1 @@\n+x = 1   \n")
REGRESSION = ("diff --git a/calc.py b/calc.py\n--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n"
              "-    return a + b\n+    return a - b\n")
EXCLUDE_HONORING_TOOL = (
    "import fnmatch, pathlib, sys\n"
    "root = pathlib.Path('.').resolve()\n"
    "def excluded(path):\n"
    "    for folder in path.parents:\n"
    "        exclude = folder / '.git' / 'info' / 'exclude'\n"
    "        if exclude.is_file() and any(fnmatch.fnmatch(str(path.relative_to(folder)), p.strip())\n"
    "                                     for p in exclude.read_text().splitlines() if p.strip()):\n"
    "            return True\n"
    "        if folder == root:\n"
    "            return False\n"
    "bad = [p for p in root.rglob('*.py') if '.git' not in p.parts and not excluded(p)\n"
    "       and any(line.endswith(' ') for line in p.read_text().splitlines())]\n"
    "sys.exit(1 if bad else 0)\n")


class ControlsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="relai-controls-"))
        self.src = make_source_repo(self.tmp)
        self.project = Repo()
        self.project.write("relai/relai.toml", f'[harbor]\nversion = "0.25.0"\n\n[scoring]\npass_mark = 0.8\n\n'
                                               f'[coding_evals]\nrepos = {{ calc = "{self.src["repo"]}" }}\n')
        self.bundle = make_bundle(self.src, self.tmp / "repo.bundle")
        self.task = fill_task(self.project, self.src, self.bundle)
        self.controls = load_controls()

    def tearDown(self) -> None:
        self.project.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def declare(self, config: dict, patches: dict | None = None) -> None:
        folder = self.task / "controls"
        folder.mkdir(exist_ok=True)
        for name, text in (patches or {}).items():
            (folder / name).write_text(text)
        (folder / "controls.json").write_text(json.dumps(config))

    def standard(self) -> None:
        self.declare({"first_command": {"command": "python -m pytest -q tests", "timeout_sec": 60},
                      "controls": [{"id": "regression", "solve": True, "patch": "regression.patch",
                                    "expect": {"no-regressions": 0}},
                                   {"id": "unformatted", "solve": True, "patch": "unformatted.patch",
                                    "expect": {"formatted": 0}, "hide": True}]},
                     {"regression.patch": REGRESSION, "unformatted.patch": UNFORMATTED})
        toml = self.task / "task.toml"
        toml.write_text(toml.read_text() + '\n[[metadata.relai.evaluators]]\nid = "formatted"\ntype = "code"\n'
                                           'method = "exact"\ncriterion = "formatted."\nmin_score = 0.0\nmax_score = 1.0\n')

    def workspace(self) -> Path:
        ws = Path(tempfile.mkdtemp(prefix="ws-", dir=self.tmp))
        shutil.rmtree(ws)
        sh(self.tmp, "git", "clone", "-q", "-b", "main", str(self.bundle), str(ws))
        return ws

    def verify(self, ws: Path, verify_py: str | None = None) -> dict:
        tests = Path(tempfile.mkdtemp(prefix="tests-", dir=self.tmp)) / "tests"
        shutil.copytree(self.task / "tests", tests)
        if verify_py:
            (tests / "verify.py").write_text(verify_py)
        logs = Path(tempfile.mkdtemp(prefix="logs-", dir=self.tmp))
        (logs / "verifier").mkdir()
        script = (f"import runpy, sys; sys.path.append({str(tests)!r}); "
                  f"runpy.run_path({str(tests / 'verify.py')!r}, run_name='__main__')")
        ran = subprocess.run([sys.executable, "-I", "-S", "-c", script], cwd=tests, capture_output=True, text=True,
                             env={**os.environ, "RELAI_WORKSPACE": str(ws), "RELAI_LOGS": str(logs)})
        self.assertEqual(ran.returncode, 0, ran.stderr)
        return json.loads((logs / "verifier" / "reward.json").read_text())

    def test_the_plan_has_the_built_in_controls_and_four_hiding_probes_per_hidden_control(self):
        self.standard()
        settings, controls = self.controls.plan(self.task)
        ids = [c["id"] for c in controls]
        self.assertEqual(ids, ["start", "reference", "first-command", "shadow-imports", "regression", "unformatted",
                               "unformatted/git-exclude", "unformatted/root-exclude", "unformatted/ignore-files",
                               "unformatted/nested-repo"])
        by_id = {c["id"]: c for c in controls}
        self.assertEqual(by_id["start"]["expect"], {"fixes-the-bug": 0.0})
        self.assertEqual(by_id["reference"]["expect"]["formatted"], 1.0)
        self.assertEqual(by_id["first-command"]["timeout"], 60.0)
        self.assertIn("pkg/.git/info/exclude", by_id["unformatted/git-exclude"]["script"])
        self.assertEqual(settings["workspace"], "/app")
        ran = self.project.run("controls.py", str(self.task), "--plan")
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("unformatted/nested-repo: solution/solve.sh then git apply controls/unformatted.patch; "
                      "expect {'formatted': 0}", ran.stdout)

    def test_a_hiding_probe_catches_a_tool_that_honors_a_nested_exclude(self):
        self.standard()
        params = json.loads((self.task / "tests" / "params.json").read_text())
        tool = self.task / "tests" / "fmt_tool.py"
        tool.write_text(EXCLUDE_HONORING_TOOL)
        params["build"] = {"command": f"{sys.executable} {tool}", "timeout_sec": 60}
        (self.task / "tests" / "params.json").write_text(json.dumps(params))
        verify_py = 'from coding_checks import Task\n\ntask = Task()\ntask.build("formatted")\ntask.write()\n'
        _, controls = self.controls.plan(self.task)
        verdicts = {}
        for control in [c for c in controls if c["id"].startswith("unformatted")]:
            ws = self.workspace()
            sh(ws, "git", "apply", str(self.task / "solution" / "fix.patch"))
            sh(ws, "git", "apply", str(self.task / "controls" / "unformatted.patch"))
            if control.get("script"):
                subprocess.run(["bash", "-c", control["script"]], cwd=ws, check=True, capture_output=True)
            scores = self.verify(ws, verify_py)
            verdicts[control["id"]] = self.controls.verdict(control["expect"], scores)[0]
        self.assertEqual(verdicts, {"unformatted": True, "unformatted/git-exclude": False,
                                    "unformatted/root-exclude": False, "unformatted/ignore-files": True,
                                    "unformatted/nested-repo": True},
                         "a check that harden_workspace does not protect fails the exclude probes")

    @unittest.skipUnless(have_pytest(), "pytest is not installed on this host")
    def test_the_shadow_probe_catches_a_planted_module_that_exits_zero(self):
        params = json.loads((self.task / "tests" / "params.json").read_text())
        paths = self.controls.shadow_plan(self.task, params)
        self.assertEqual(paths, ["calc.py", "tests/calc.py"])
        ws = self.workspace()
        subprocess.run(["bash", "-c", self.controls.shadow_script(paths)], cwd=ws, check=True)
        self.assertEqual((ws / "calc.py").read_text(), CALC, "an existing module is never overwritten")
        self.assertTrue(self.controls.verdict({"fixes-the-bug": 0.0}, self.verify(ws))[0],
                        "the planted tests/calc.py is under protected tests/** and is removed: no hole")
        hidden = self.task / "tests" / "hidden" / "test_mean.py"
        hidden.write_text("import fractions\n" + hidden.read_text())
        paths = self.controls.shadow_plan(self.task, params)
        self.assertIn("fractions.py", paths)
        ws = self.workspace()
        subprocess.run(["bash", "-c", self.controls.shadow_script(paths)], cwd=ws, check=True)
        self.assertFalse(self.controls.verdict({"fixes-the-bug": 0.0}, self.verify(ws))[0],
                         "python -m pytest puts the workspace first, so /app/fractions.py exits 0 and the untouched "
                         "start passes: the probe reports the hole")

    def test_run_control_judges_scores_hangs_and_unrunnable_commands(self):
        module = self.controls

        class FakeEngine(module.Engine):
            def __init__(self, replies):
                super().__init__("fake")
                self.replies, self.scripts = list(replies), []

            def start(self, image, cpus, memory_mb):
                return "c1"

            def copy(self, name, source, dest):
                self.scripts.append(f"copy {source.name} {dest}")

            def run(self, name, script, user="root", workdir=None, timeout=None):
                self.scripts.append(f"{user}: {script}")
                return self.replies.pop(0) if self.replies else (0, "")

            def remove(self, name):
                self.scripts.append("remove")

        settings = {"workspace": "/app", "agent_user": "coder", "cpus": 2, "memory_mb": 4096}
        first = {"id": "first-command", "command": "npm run test:unit", "timeout": 5.0, "stand_in": False}
        for reply, ok in (((None, "timed out after 5.0 s"), False), ((127, "npm: not found"), False),
                          ((1, "1 failing"), True)):
            engine = FakeEngine([reply])
            result = module.run_control(engine, "img", self.task, settings, first)
            self.assertEqual(result["ok"], ok, result)
            self.assertEqual(engine.scripts[-1], "remove")
        self.assertIn("did not finish within 5 s",
                      module.run_control(FakeEngine([(None, "")]), "img", self.task, settings, first)["detail"])
        control = {"id": "regression", "solve": True, "patch": "regression.patch", "expect": {"no-regressions": 0}}
        self.standard()
        engine = FakeEngine([(0, ""), (0, ""), (0, ""), (0, ""), (0, '{"no-regressions": 1.0}')])
        result = module.run_control(engine, "img", self.task, settings, control)
        self.assertFalse(result["ok"])
        self.assertEqual(result["detail"], "no-regressions 1.0 (expected 0)")
        self.assertIn("root: bash /solution/solve.sh", engine.scripts)
        self.assertIn("coder: git apply --whitespace=nowarn /tmp/relai-controls/regression.patch", engine.scripts)
        engine = FakeEngine([(0, ""), (0, ""), (1, "error: patch failed")])
        self.assertIn("patch failed (exit 1)", module.run_control(engine, "img", self.task, settings, control)["detail"])


class ControlsGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="relai-gate-"))
        self.src = make_source_repo(self.tmp)
        self.project = Repo()
        self.project.write("relai/relai.toml", '[harbor]\nversion = "0.25.0"\n\n[scoring]\npass_mark = 0.8\n')
        self.task = fill_task(self.project, self.src, make_bundle(self.src, self.tmp / "repo.bundle"))
        sys.path.insert(0, str(TEMPLATE / "bin"))
        import _common
        self.common = _common

    def tearDown(self) -> None:
        self.project.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def freeze(self, *args: str) -> subprocess.CompletedProcess:
        return self.project.run("freeze.py", str(self.task), *args)

    def record(self, **changes) -> Path:
        record = {"task": "tests/mean-empty", "digest": self.common.dir_digest(self.task), "partial": False,
                  "ok": True, "controls": [{"id": "start", "ok": True}]}
        record.update(changes)
        path = self.common.controls_record(self.project.relai, "tests/mean-empty")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record))
        return path

    def test_freezing_requires_a_passing_complete_record_for_the_current_files(self):
        ran = self.freeze("--require-controls")
        self.assertEqual(ran.returncode, 1)
        self.assertIn("no controls record", ran.stderr)
        for changes, message in (({"digest": "0" * 64}, "not the current files"), ({"partial": True}, "partial run"),
                                 ({"ok": False, "controls": [{"id": "reference", "ok": False}]},
                                  "controls failed: reference")):
            with self.subTest(message=message):
                self.record(**changes)
                ran = self.freeze("--require-controls")
                self.assertEqual(ran.returncode, 1, ran.stdout)
                self.assertIn(message, ran.stderr)
        self.assertFalse((self.project.relai / "frozen.json").exists())
        self.record()
        ran = self.freeze("--require-controls")
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn("frozen", ran.stdout)

    def harbor(self, oracle: dict, nop: dict, started: datetime) -> Path:
        jobs = self.tmp / "jobs"
        for agent, rewards in (("oracle", oracle), ("nop", nop)):
            trial = harbor_trial(jobs / f"mean-empty--{agent}", f"mean-empty__{agent}", self.task, rewards)
            data = json.loads((trial / "result.json").read_text())
            data.update(agent_info={"name": agent}, started_at=started.isoformat().replace("+00:00", "Z"))
            (trial / "result.json").write_text(json.dumps(data))
        return jobs

    def test_harbor_oracle_and_nop_trials_can_clear_the_gate(self):
        full = {"fixes-the-bug": 1.0, "no-regressions": 1.0, "tests-untouched": 1.0, "in-scope": 1.0}
        later = datetime.now(timezone.utc) + timedelta(minutes=1)
        cases = [({**full, "fixes-the-bug": 0.0}, {**full, "fixes-the-bug": 0.0}, later,
                  "oracle scored below full marks on fixes-the-bug"),
                 (full, full, later, "nop scored 1.0 on the primary check fixes-the-bug"),
                 (full, {**full, "fixes-the-bug": 0.0}, later - timedelta(days=1), "started before the test's files"),
                 (full, {**full, "fixes-the-bug": 0.0}, later, None)]
        for oracle, nop, started, message in cases:
            with self.subTest(message=message):
                shutil.rmtree(self.tmp / "jobs", ignore_errors=True)
                jobs = self.harbor(oracle, nop, started)
                ran = self.freeze("--controls", str(jobs))
                if message is None:
                    self.assertEqual(ran.returncode, 0, ran.stderr)
                else:
                    self.assertEqual(ran.returncode, 1, ran.stdout)
                    self.assertIn(message, ran.stderr)


class CheckTaskControlsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="relai-check-controls-"))
        self.src = make_source_repo(self.tmp)
        self.project = Repo()
        self.project.write("relai/relai.toml", f'[harbor]\nversion = "0.25.0"\n\n[scoring]\npass_mark = 0.8\n\n'
                                               f'[coding_evals]\nrepos = {{ calc = "{self.src["repo"]}" }}\n')
        self.task = fill_task(self.project, self.src, make_bundle(self.src, self.tmp / "repo.bundle"))

    def tearDown(self) -> None:
        self.project.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def check(self, *args: str) -> subprocess.CompletedProcess:
        return self.project.run("check_task.py", *args, "--no-harbor")

    def test_controls_json_is_validated_and_a_failing_test_control_is_asked_for(self):
        out = self.check(str(self.task)).stdout
        self.assertIn("no control makes no-regressions fail", out)
        self.assertIn("declares no first_command", out)
        (self.task / "controls").mkdir()
        (self.task / "controls" / "regression.patch").write_text(REGRESSION)
        (self.task / "controls" / "controls.json").write_text(json.dumps({
            "first_command": {"command": "python -m pytest -q"},
            "controls": [{"id": "regression", "solve": True, "patch": "regression.patch",
                          "expect": {"no-regressions": 0}}]}))
        ran = self.check(str(self.task))
        self.assertEqual(ran.returncode, 0, ran.stdout)
        self.assertNotIn("no control makes no-regressions fail", ran.stdout)
        self.assertNotIn("first_command", ran.stdout)
        (self.task / "controls" / "controls.json").write_text(json.dumps({"controls": [
            {"id": "start", "patch": "missing.patch", "expect": {"lint": 0}, "hide": True}]}))
        ran = self.check(str(self.task))
        self.assertNotEqual(ran.returncode, 0)
        for message in ("id must be a new lowercase slug", "patch 'missing.patch' is not a file in controls/",
                        "expect 'lint' must be a declared code evaluator"):
            self.assertIn(message, ran.stdout)

    def test_a_repair_copy_is_compared_with_the_frozen_test_it_names(self):
        self.assertEqual(self.project.run("freeze.py", str(self.task)).returncode, 0)
        copy = self.project.relai / "work" / "repairs" / "mean-empty"
        shutil.copytree(self.task, copy)
        out = self.check(str(copy), "--frozen", "tests/mean-empty").stdout
        self.assertIn("identical to the frozen tests/mean-empty", out)
        (copy / "tests" / "judges" / "code-review.md").write_text("Stricter.\n")
        (copy / "README.md").write_text("notes only\n")
        out = self.check(str(copy), "--frozen", "tests/mean-empty").stdout
        self.assertIn("changed since it was frozen as tests/mean-empty", out)
        self.assertIn("differs from tests/mean-empty in 1 file(s): tests/judges/code-review.md", out)
        self.assertNotIn("changed since it was frozen", self.check(str(copy)).stdout,
                         "without --frozen the copy's own path has no frozen record")
        ran = self.check(str(copy), "--frozen", "tests/other")
        self.assertNotEqual(ran.returncode, 0)
        self.assertIn("has no test with that key", ran.stdout)


if __name__ == "__main__":
    unittest.main()
