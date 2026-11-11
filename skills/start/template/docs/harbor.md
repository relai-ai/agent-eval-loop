# Harbor runs and hosted runners

`[harbor]` and `[harbor.image]` in `relai.toml` (`files.md`) declare how Harbor runs the tests.

## Harbor version

`[harbor].version` is the exact Harbor release every run and checker uses. When setting up a
suite, record the latest stable release on PyPI at that moment (never a pre-release or a range).
Record upgrades in `decisions.md` and check the installed `eval` skill's Harbor notes against
the new release when available. Assess which execution or grading behavior changed and which
comparisons remain supported. Justify baseline reuse or remeasure when relevant comparability
cannot be established; a release identity alone is not a verdict.

## Running a test

From the repository root:

1. Build the harness image with the local engine's CLI, for example
   `docker build -f <dockerfile> -t <tag> <context>` (or `podman build`).
   Declare any required preparation so the selected environment can reproduce it.
2. Run each task: `PYTHONPATH=<pythonpath, joined with :> HARBOR_TELEMETRY=0 uv tool run
   --python 3.12 --from harbor==<[harbor].version> harbor run -e <environment>
   -p <absolute task dir> -a <agent> --ae NAME=value ...`, with `-e docker` for any engine with
   a Docker-compatible CLI (Docker Desktop, OrbStack, Colima, Rancher Desktop) or `-e podman` for
   Podman, one `--ae` per `agent_env` entry and each `[runtime].env` name set in Harbor's
   environment. Harbor records `-p` as typed, so
   use absolute task paths.
3. Score the judges the way `[judge]` says, writing `<trial dir>/judges/<id>.json` (`files.md`,
   Scores). `bin/judge.py`, the plugin's example, implements this.
4. Apply the pass rule (`files.md`), or run `summarize.py`.

Harbor's task checksum covers the whole task directory (except what a `.harborignore` hides,
which `check_task.py` rejects), so even a README edit can change its identity. Explain whether
the change affects measurement rather than treating the checksum alone as proof of non-comparability.

## Hosted runners

Local execution may use authorized private or local images; it need not satisfy a cloud builder's
restrictions. The recipe below is one hosted implementation. Use `check_task.py --cloud` when
checking its portability requirements, or verify an alternative hosted implementation's equivalent
guarantees. Containment, credential protection and evidence requirements apply in either case.

This hosted recipe measures a pull request against a combined tree:

- `relai/` comes from `relaiSha`, the default-branch commit the test selection was built from:
  `relai.toml`, the harness and its Dockerfile, and the tests.
- Everything else comes from the pull request's `headSha`: the agent's source and its
  dependency files.

So a pull request is measured with its own agent and dependencies, but with the default branch's
tests, harness and `[harbor]`. Its own edits under `relai/` are not used. A harness context that
spans both trees builds from both: with context `.` and a Dockerfile that copies `pyproject.toml`
and `uv.lock`, the recipe comes from `relaiSha` and the dependency files from `headSha`. Keep
every harness file under `relai/`, have the Dockerfile copy from outside it only what the agent
itself owns, and keep live paths outside `relai/`, or a pull request's edits to them are never
measured. Locally, both trees are the one checkout.

This hosted recipe follows the steps above from the root of that tree. It needs
`[judge] mode = "api"`: with subagent judges there is no coding agent to judge with, so those
judges stay pending and their tests can never pass.

### Supplying the harness image without editing a frozen test

A task Dockerfile that uses the harness starts `FROM <tag>` (`environment/Dockerfile`, or
`tests/Dockerfile` for a separate verifier). Locally, step 1 puts that tag in the engine's image
store. A cloud builder has no such store, so a hosted runner calls `harbor run -e <module:Class>`
with its own subclass of Harbor's Modal environment, which builds `[harbor.image]` in the cloud
from the combined tree and applies the rest of each task Dockerfile on top of it, after the
`FROM` line and with the same context (Modal's `Image.dockerfile_commands`). Tests stay
byte-identical, so frozen digests and Harbor's task checksums match local runs.

For the substitution to be exact, a Dockerfile that starts FROM the harness image has no other
`FROM`, no instruction before it, and no parser directive (`# syntax=`, `# escape=`). Comments
are fine. `check_task.py --cloud` checks those substitution constraints and every `FROM`, `COPY --from` and
`RUN --mount=from=` image:

- no build argument;
- no registry on this machine or its private network, and no tag that exists only on the machine
  that built it;
- that the image's registry serves it anonymously, which it asks the way a cloud builder pulls.

It warns about a `FROM` pinned to a literal platform, and cannot tell whether a public image has a
variant for the runner's architecture. When a registry cannot be
reached, it notes that rather than failing, so run it with network access before relying on it.
