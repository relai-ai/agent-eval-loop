# Harbor: things that fail silently

Run Harbor as `relai/docs/harbor.md` describes. Everything below was observed in Harbor 0.25.0's
source; none of it raises an error that explains itself. When `[harbor].version` is newer, re-check
a note against that release before relying on it, and update this file.

- **Exit status lies.** `harbor run` exits 0 even when every trial errored. Read each
  trial's `result.json` (`exception_info`, `verifier_result`), or run `summarize.py`. A trial whose
  agent exited non-zero or ran past `[agent].timeout_sec` is still graded on whatever it left, so
  its rewards can sit beside an exception.
- **Telemetry is on by default.** Set `HARBOR_TELEMETRY=0` in Harbor's environment.
- **Host values leak into Harbor.** Harbor loads `.env.local` from its working directory and
  every value in `--env-file` into its own process, and `${VAR}` in `task.toml` copies host
  values into containers (after an interactive prompt that `-y` skips). Run Harbor from a
  directory without `.env.local`, pass only the variables the agent needs (`--ae NAME=...`
  or Harbor's environment), and keep `${...}` out of `task.toml`.
- **A separate verifier gets no tests.** With `[verifier] environment_mode = "separate"` and a
  `tests/Dockerfile`, Harbor builds the verifier from `tests/` and does not upload `tests/` into
  it, so that Dockerfile must `COPY . /tests/`. Without a `tests/Dockerfile` or a verifier
  `docker_image`, Harbor quietly builds the verifier from `environment/` instead. Without
  `environment_mode` set, the verifier runs inside the agent's container.
- **A shared verifier gets `tests/` only after the agent is done.** Without `environment_mode`,
  Harbor uploads `tests/` into the agent's container when verification starts and removes
  `reward.json` and `reward.txt` first, but nothing else the agent may have written under
  `/logs/verifier` or `/tests`. The verifier runs among whatever the agent left (files,
  processes), so it must trust only what came with `tests/`.
- **Installed agents get their model host through the network limit.** With
  `[agent] network_mode = "no-network"` or `"allowlist"`, Harbor adds the installed agent's
  inference host to the allowlist; an explicit `--allow-agent-host` list replaces that inference.
  An environment that cannot change its network policy after start refuses a run whose setup or
  verifier policy is broader than the agent's.
- **A network limit also switches off web tools.** Server-side web tools (search or fetch at the
  model provider) are outside the container's network. When the agent's network is not
  `public`, Harbor switches off the native web tools of every installed agent that has them,
  through one shared option (`--ak disable_web_search=true` sets it explicitly); for an agent with
  none it logs that it had nothing to switch off.
- **Installed agents can use a subscription.** Claude Code takes `CLAUDE_CODE_OAUTH_TOKEN` (with
  `CLAUDE_FORCE_OAUTH`, a run fails at once when that token is missing); Codex uses its `auth.json` login with
  `CODEX_FORCE_AUTH_JSON` or `CODEX_AUTH_JSON_PATH`, which conflicts with an API key and with an
  external model provider. Other agents take the provider's API key. Pass credentials by name
  through Harbor's environment, as for any key.
- **An installed agent's release is a kwarg.** Pass `--ak version=<release>`; without it Harbor
  installs whatever is newest, so runs on different days compare different agents.
  `[agent].user` runs the agent as that user instead of the image's default (often root).
- **`.harborignore` hides grader inputs.** Files it matches under `tests/` or `solution/` are
  left out of the upload and of the task checksum, so a grader can run without them and two
  different test trees can hash the same. `check_task.py` rejects it.
- **The verifier sees only declared artifacts.** In separate mode, list
  `artifacts = ["/logs/agent/trajectory.json"]` (plus any other file under `/logs/agent/` the
  checks read) at the top of `task.toml`. A symlink that leaves an artifact, or a special file,
  is dropped with only a log line, so write the trajectory as a regular file.
- **Hidden 600-second defaults.** `[verifier].timeout_sec` and `[environment].build_timeout_sec`
  default to 600; a slow build or judge-free verifier past that fails as an exception, not a
  low score. Set them explicitly when a phase can run long. `[agent].timeout_sec` has no default.
- **Build context is the task's `environment/` directory only.** A Dockerfile there cannot
  COPY files from elsewhere in the repository; build the shared harness image from
  `[harbor.image]` in `relai.toml` and start from it (`FROM <its tag>`), or copy inputs in at
  trial time.
- **Cloud builds see only registries.** With `-e modal`, Harbor builds `environment/Dockerfile`
  in Modal's cloud with no build arguments and no registry credentials, so a `FROM` naming a tag
  built on your machine fails there. Credentials go only to
  `[environment].docker_image` tasks, and Harbor then ignores their Dockerfile. `relai/docs/harbor.md`
  says how a runner supplies the harness image instead.
- **`-p` takes one path.** Pass a directory of tasks and filter with `-i <glob>`, or list the
  tasks in a job config (`-c job.yaml`, repeatable; `harbor job schema` prints its schema). Directories
  that are not valid tasks are skipped without a message, and unknown `task.toml` keys are
  ignored, so check the trial count.
- **Local engines differ.** `-e docker` drives whatever engine the `docker` CLI points at
  (Docker Desktop, OrbStack, Colima, Rancher Desktop). `-e podman` never gates startup on
  healthchecks, so a task compose file with `depends_on: condition: service_healthy` hangs.
  Podman and `-e apple-container` keep their own image stores, so build the harness image with
  the same engine that runs the trials.
- **Images are deleted after each trial** (`--delete` is the default). During setup,
  `--no-delete` keeps them for the next trial.
- **A custom agent class is imported from Harbor's tool environment.** `uv tool run` does not
  add the working directory to `sys.path`; set `PYTHONPATH` to the directory holding it.
- **A missing reward file is an exception**, and `reward.txt` holds one number. Write
  `reward.json` with one key per evaluator.
- **ATIF**: Harbor validates `ATIF-v1.0` to `v1.8`
  (`python -m harbor.utils.trajectory_validator <file>`); `check_trajectory.py` runs it.
- **Rescoring**: `harbor trial regrade <trial dir> -p <task>` reruns only the verifier on a
  recorded run; `harbor job resume -p <job dir>` finishes an interrupted job.
