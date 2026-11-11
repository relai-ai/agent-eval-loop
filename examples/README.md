# Example scripts

Working examples to copy, adapt or replace with a project-native equivalent that meets the same
contract in `relai/README.md` and `relai/docs/`. None is part of `relai/` until the integration chooses it; once
copied it is project code the user owns. For a failure or an unsuitable implementation, follow the
[adaptation guidance](../skills/start/template/README.md#adapting-supplied-implementations): preserve
the relevant guarantee and verify it with focused checks. Each example is standard-library Python.

| Example | Copy to | What it does |
| --- | --- | --- |
| `harbor_agent.py`, `launcher.py` | `relai/harness/` | Harbor agent class and the in-container launcher that drives a conversation with your adapter |
| `native_runner.py` | `relai/bin/` | Runs a per-trial command for each test × attempt and writes the native trial layout; not a sandbox |
| `judge.py` | `relai/bin/` | API judge: scores each trial's judge evaluators on the host (`--self-test` shows a judge can fail) |
| `triage.py` | `relai/bin/`, with `judge.py` | Cheap-model triage of a large trace set (see [trace triage](../skills/discover/references/trace-triage.md)) |
| `evaluate.py` | a task's `tests/` | Helper that writes the verifier's reward, feedback and error files |

`judge.py`, `native_runner.py` and `triage.py` import `_common.py`, so they run from `relai/bin/`.
