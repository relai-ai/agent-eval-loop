"""Release snapshots and atomic publication in disposable repos; GitHub CLI is stubbed."""

from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import tomllib
import unittest

from helpers import PLUGIN

spec = importlib.util.spec_from_file_location("relai_release", PLUGIN / "scripts/release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="relai-release-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "checkout"
        self.root.mkdir()
        for name in (*release.VERSION_FILES, "scripts/release.py", ".gitignore"):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(PLUGIN / name, destination)
        (self.root / "CHANGELOG.md").write_text("Release notes live in GitHub Releases.\n")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Release test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.source = self.commit()
        self.current = release.check(self.root)
        self.target = release.next_version(self.current)

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def snapshot(self):
        return {name: (self.root / name).read_bytes() for name in release.VERSION_FILES}

    def bump(self, target=None, dry_run=False):
        with redirect_stdout(io.StringIO()):
            release.bump(self.root, target or self.target, dry_run)

    def remote(self):
        path = Path(self.temp.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(path)], check=True)
        self.git("remote", "add", "origin", str(path))
        self.git("push", "-q", "origin", "main")
        return path

    def prepare(self, target=None):
        return release.prepare(self.root, target)

    def workflow_step(self, name):
        workflow = (PLUGIN / ".github/workflows/release.yml").read_text()
        step = workflow.split(f"      - name: {name}\n", 1)[1].split("      - name:", 1)[0]
        lines = []
        for line in step.split("        run: |\n", 1)[1].splitlines():
            if line.strip() and not line.startswith("          "):
                break
            lines.append(line)
        return textwrap.dedent("\n".join(lines)).rstrip()

    def publisher(self, snapshot, early_access="true"):
        stub = Path(self.temp.name) / "stub"
        stub.mkdir(exist_ok=True)
        executable = stub / "gh"
        executable.write_text(
            "#!/usr/bin/env python3\nimport json, os, sys\n"
            'with open(os.environ["GH_LOG"], "a") as log: log.write(json.dumps(sys.argv[1:]) + "\\n")\n')
        executable.chmod(0o755)
        python = stub / "python"
        python.write_text("#!/usr/bin/env python3\nimport os, sys\n"
                          f"os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])\n")
        python.chmod(0o755)
        env = {"PATH": os.pathsep.join((str(stub), str(Path(sys.executable).parent), os.defpath)),
               "VERSION": snapshot["version"], "RELEASE_SHA": snapshot["sha"],
               "SOURCE_SHA": snapshot["source_sha"], "PRERELEASE": early_access,
               "PROJECT_COPY_NOTES": "Preserve local adaptations.", "GH_TOKEN": "fixture",
               "GH_REPO": "example/fixture", "GH_LOG": str(Path(self.temp.name) / "gh-calls"),
               "RUNNER_TEMP": self.temp.name}
        result = subprocess.run(["bash", "-c", self.workflow_step("Publish tested snapshot")],
                                cwd=self.root, env=env, capture_output=True, text=True)
        return result

    def test_bump_preserves_dependencies_metadata_and_changelog(self):
        lock_before = tomllib.loads((self.root / "uv.lock").read_text())
        manifest_before = json.loads((self.root / "plugin.json").read_text())
        self.bump()
        self.assertEqual(release.check(self.root, self.target), self.target)
        lock_after = tomllib.loads((self.root / "uv.lock").read_text())
        lock_before["package"][0]["version"] = self.target
        self.assertEqual(lock_before, lock_after)
        manifest_before["version"] = self.target
        self.assertEqual(manifest_before, json.loads((self.root / "plugin.json").read_text()))
        self.assertEqual((self.root / "CHANGELOG.md").read_text(), "Release notes live in GitHub Releases.\n")

    def test_dry_run_and_invalid_versions_write_nothing(self):
        before = self.snapshot()
        self.bump(dry_run=True)
        self.assertEqual(before, self.snapshot())
        for target in (self.current, "0.0.0", "v1.0.0", "1.01.0", "1.0", "1.0.0-beta", "1.0.0\n"):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    self.bump(target)
                self.assertEqual(before, self.snapshot())

    def test_inconsistent_lockfile_is_rejected_before_writes(self):
        path = self.root / "uv.lock"
        path.write_text(path.read_text().replace(f'version = "{self.current}"', 'version = "99.0.0"', 1))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "versions disagree"):
            self.bump()
        self.assertEqual(before, self.snapshot())

    def test_snapshot_is_only_a_version_commit_and_next_release_uses_main_version(self):
        first = self.prepare()
        self.assertEqual(first["version"], self.target)
        self.assertEqual(first["source_sha"], self.source)
        self.assertEqual(set(self.git("diff", "--name-only", self.source, first["sha"]).splitlines()),
                         set(release.VERSION_FILES))
        self.assertEqual(self.git("rev-parse", "main"), self.source)
        self.git("update-ref", "refs/heads/main", first["sha"])
        self.git("checkout", "-q", "main")
        self.assertEqual(release.check(self.root), first["version"])
        (self.root / "feature.txt").write_text("new feature\n")
        second_source = self.commit()
        second = self.prepare()
        self.assertEqual(second["version"], release.next_version(first["version"]))
        self.assertEqual(second["source_sha"], second_source)
        self.assertEqual((self.root / "feature.txt").read_text(), "new feature\n")
        self.assertEqual(self.git("merge-base", first["sha"], second["sha"]), first["sha"])
        self.assertEqual(self.git("rev-parse", "main"), second_source)
        self.assertEqual(json.loads(self.git("show", "main:plugin.json"))["version"], first["version"])

    def test_first_release_can_use_current_manifest_version_without_metadata_changes(self):
        before = self.snapshot()
        first = self.prepare(self.current)
        self.assertEqual(first["version"], self.current)
        self.assertEqual(first["source_sha"], self.source)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.git("diff", "--name-only", self.source, first["sha"]), "")
        self.assertEqual(self.git("rev-parse", "HEAD^"), self.source)
        self.assertEqual(self.git("rev-parse", "main"), self.source)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.git("tag", f"v{self.current}")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.prepare(self.current)
        next_release = self.prepare()
        self.assertEqual(next_release["version"], self.target)

    def test_prepare_rejects_existing_tag_dirty_checkout_and_old_versions(self):
        before = self.snapshot()
        self.git("tag", f"v{self.target}")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.prepare()
        self.assertEqual(before, self.snapshot())
        self.git("tag", "-d", f"v{self.target}")
        (self.root / "CHANGELOG.md").write_text("dirty\n")
        with self.assertRaisesRegex(ValueError, "clean tracked"):
            self.prepare()
        self.git("checkout", "--", "CHANGELOG.md")
        with self.assertRaisesRegex(ValueError, "greater than"):
            self.prepare("0.0.0")
        self.git("tag", "v0.0.1")
        with self.assertRaisesRegex(ValueError, "greater than"):
            self.prepare(self.current)
        self.assertEqual(before, self.snapshot())

    def test_requested_version_must_exceed_current_main_release(self):
        higher = f"{release.version_tuple(self.current)[0] + 1}.0.0"
        published = self.prepare(higher)
        self.git("update-ref", "refs/heads/main", published["sha"])
        self.git("checkout", "-q", "main")
        with self.assertRaisesRegex(ValueError, "greater than"):
            self.prepare(self.target)

    def assert_publication(self, early_access, target=None):
        self.remote()
        snapshot = self.prepare(target)
        result = self.publisher(snapshot, early_access)
        self.assertEqual(result.returncode, 0, result.stderr)
        refs = self.git("ls-remote", "origin")
        self.assertIn(f'{snapshot["sha"]}\trefs/heads/main', refs)
        self.assertIn(f'{snapshot["sha"]}\trefs/tags/v{snapshot["version"]}', refs)
        self.assertNotIn("refs/heads/release", refs)
        calls = [json.loads(line) for line in (Path(self.temp.name) / "gh-calls").read_text().splitlines()]
        self.assertEqual(calls[0], ["auth", "setup-git"])
        self.assertEqual(calls[1][:3], ["release", "create", f'v{snapshot["version"]}'])
        self.assertIn("--verify-tag", calls[1])
        self.assertIn("--generate-notes", calls[1])
        self.assertEqual("--prerelease" in calls[1], early_access == "true")
        self.assertIn("Preserve local adaptations.", (Path(self.temp.name) / "release-notes.md").read_text())

    @unittest.skipUnless(shutil.which("bash"), "publication integration needs bash")
    def test_publication_pushes_tested_branch_and_tag_then_creates_preview(self):
        self.assert_publication("true")

    @unittest.skipUnless(shutil.which("bash"), "publication integration needs bash")
    def test_publication_can_create_a_regular_release(self):
        self.assert_publication("false", self.current)

    @unittest.skipUnless(shutil.which("bash"), "publication integration needs bash")
    def test_rejected_branch_update_does_not_leave_a_remote_tag(self):
        self.remote()
        snapshot = self.prepare()
        self.git("checkout", "-q", "main")
        (self.root / "concurrent.txt").write_text("another writer\n")
        self.commit()
        new_main = self.git("rev-parse", "HEAD")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "--detach", snapshot["sha"])
        result = self.publisher(snapshot)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("ls-remote", "--tags", "origin"), "")
        self.assertIn(new_main, self.git("ls-remote", "--heads", "origin", "main"))
        calls = (Path(self.temp.name) / "gh-calls").read_text()
        self.assertNotIn('"release", "create"', calls)

    @unittest.skipUnless(shutil.which("bash"), "publication integration needs bash")
    def test_mismatched_or_dirty_snapshot_stops_before_remote_writes(self):
        self.remote()
        snapshot = self.prepare()
        invalid = {**snapshot, "sha": "0" * 40}
        self.assertNotEqual(self.publisher(invalid).returncode, 0)
        (self.root / "CHANGELOG.md").write_text("changed after tests\n")
        self.assertNotEqual(self.publisher(snapshot).returncode, 0)
        self.assertEqual(self.git("ls-remote", "--tags", "origin"), "")
        self.assertIn(self.source, self.git("ls-remote", "--heads", "origin", "main"))
        self.assertFalse((Path(self.temp.name) / "gh-calls").exists())


if __name__ == "__main__":
    unittest.main()
