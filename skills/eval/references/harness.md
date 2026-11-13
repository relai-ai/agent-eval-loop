# Set up the harness

Goal: the repository's real agent runs through the declared runner the way a user would use it, each
run records the causal sequence of what it actually did, and a smoke test that checks a
real outcome passes.

Project-native records may keep their format when they preserve the shared evidence guarantees.
Use ATIF and the bundled trial layout when integrating consumers that require them; the paths
and checker commands below describe that implementation, with project-native equivalents allowed.

## Start

Read the [relevant execution guarantees](../../start/template/README.md#fixed-rules) in the project
contract and only the `relai/docs/` formats this integration uses; check its
prerequisites for the selected runner and fix what fails.

## Done when

- `relai.toml` names the target, the configuration you integrated and the evidence that it is
  the real one, the live paths, the entrypoints, and the judge settings. Its `[runner]` table
  declares execution/isolation, and `[harbor]` holds agent/image settings when used, so a runner with
  only a clean clone can run every test.
- `relai/harness/` runs the agent through its real entrypoint with reviewed containment, from the current
  source, and records its real model messages, tool calls and results in causal order (ATIF for
  the bundled trajectory consumers).
  For Harbor, `[harbor].version` holds the latest stable Harbor release (`relai/docs/harbor.md`),
  its image builds from `[harbor.image]` alone with the container engine that runs the trials,
  and tasks use dependencies authorized for their execution environment. For the bundled hosted
  recipe, `check_task.py --cloud` checks its additional build constraints (`relai/docs/harbor.md`).
  Native integrations meet the shared result contract.
- `relai/harness/smoke/` is a task for the selected runner with a representative interaction (several turns if
  real use has several; a tool call if the agent has tools) and evaluators that check a real
  outcome. It proves the harness works and is not an eval, so it is not frozen (see
  `relai/docs/files.md`). `check_task.py` passes, grading is demonstrated on synthetic passing/failing/empty cases
  (`--verifier` for Harbor), a real run scores it,
  `check_trajectory.py` passes on that run's trajectory, and `summarize.py` reports it scored.
- You have shown that live files are live: an edit to one, made only in a scratch copy, changes
  what the next trial does.
- A fresh reviewer given [review-harness](review-harness.md) and the paths reports no blocking
  finding after its code and trajectory passes. Fix each finding at its evidence, then have the
  reviewer recheck the fixes.
- The repository's own checks covering any project file you touched still pass, and its test
  runner collects nothing under `relai/` (confirm from the runner's own listing).

## Rules

- Reuse a suitable project or benchmark runner; otherwise Harbor is the supported default.
  Record `[runner].kind` and `.isolation` with their reason. The plugin's `examples/` (two levels
  above this skill's folder) has a native runner to copy to `relai/bin/`; prefer project-native
  adapters where practical. If `examples/` is not installed, see the project contract's
  *Checkers* section for where to get it.
- When Harbor cannot run here (no `uv`, no running container engine, or Harbor failing on this
  machine), say so plainly with the cause, and lay out the options with a recommendation: start or
  install a container engine Harbor supports (any Docker-compatible engine or Podman); a native
  runner, the project's own or the example, with containment the user authorizes
  (`relai/docs/native.md`); or a hosted runner (`relai/docs/harbor.md`). Keep building what does
  not need execution meanwhile. Never fall back to an uncontained run on your own.
- With `[judge] mode = "api"`, copy the example `judge.py` to `relai/bin/judge.py` (or write an
  equivalent meeting the judge contract in `relai/docs/files.md`) before the first judged trial.
  Example providers are not a closed supported set: reuse a suitable project provider and adapt
  or replace the example for its API and credential mechanism. Preserve data authorization,
  credential redaction, score/error outputs and honest usage reporting; do not claim the shipped
  example implements a provider it does not.
- Contain every trial (`relai/README.md`, Fixed rules: *Containment*). Never run an uncontained agent as a workaround.
- Integrate the configuration the repository presents as real use: what its README leads with,
  its defaults. Never a fixture that exists for its own tests. When several are plausible, ask.
- Drive the agent through its real entrypoint and native lifecycle (a long-lived object, replayed
  history, or a session id). The adapter changes nothing about the agent and never branches on a
  test, scenario or expected answer.
- Keep recorder code under `relai/harness/`. Attach it through an extension point the project
  already has (a callback, hook or tracing option). If there is none, add the smallest optional
  one in the project's own style, off by default, with a test. Project code never imports RELAI
  code or reads RELAI variables.
- Record only what happened, in causal order: the model's actual messages, tool calls with their
  ids, and results attributed to those calls. Never merge messages or rebuild them from final
  state. Redact credentials and anything secret before writing.
- When the agent needs a service, database or credential, run the real thing inside the trial or
  declare the credential by name. Mock only at a client boundary, under applicable authorization
  ([mocks](mocks.md)). Never stub the agent, its model calls, or a tool's own logic.
- When the agent gets its permissions from settings, use its relevant operating settings.
  When it would ask a person interactively, use the user's answer on how prompts are answered in
  trials. Add no permission policy of your own.
- Use absolute paths in trials. Smoke-test one turn through the selected runner before a full
  run. Harbor uses container paths; native integrations declare their actual per-trial paths.
- Nothing you add under `relai/` may be picked up by the project's own test, lint or build
  tooling, and no cache folders may land in a build context.

## Ask the user

Settle from the repository whatever it answers and reuse existing authorization. Ask uncovered
choices in a useful batch at the start of
the `eval` skill, and ask what only comes up later (mocks, prompts) together when it comes up:

- How judges should run: a coding-agent subagent or an existing suitable provider integration.
  Establish what leaves the environment and which authorization covers it, and tell the user in
  plain terms before the first API-judged trial: which provider receives the trajectories, and
  that the example judge removes only declared secret values, not personal or customer data. Name
  the judge model with the user; the example has no default. The example judge's
  implemented providers are listed in `relai/docs/files.md`; other APIs may use an adapted or
  project-native judge meeting the same output contract. The example hosted runner uses API
  judging; another integration must demonstrate its own execution and credential setup.
- Which configuration to integrate, only when several are plausible as real use.
- How interactive permission prompts should be answered in trials, only when the agent asks a
  person for them.
- Once you know every dependency trials cannot reach or must not call, approval for all the mocks
  together, and how to handle each action with real side effects ([mocks](mocks.md)).

Secrets are not questions: name each variable the agent or the judge needs and tell the user to
make it available through the project's credential mechanism or `relai/.env`. Never ask for
the value or read the secret file.

The pass mark is not asked here: it is chosen after the first real scores
([measure](measure.md), *The pass mark*).

Record every answer, and every consequential choice you made yourself, in `relai/decisions.md`.

## Approach

### The input channel

The launcher replaces the application's own shell: its prompt loop, blank-input skipping, exit
or quit commands and signal handling never reach the agent, so the adapter neither reproduces
them nor needs a project edit to get around them. Input handling whose result the agent receives,
such as normalization, guardrails or middleware, is part of the real path and stays on the
adapter's path.

### Getting the deliverable to the evaluators

Evaluators see the trajectory and the files a test lists in `artifacts`, nothing else.

- Return the agent's actual reply, and record it as the last agent step's message.
- When the agent writes its result to a file, point that write at a per-trial path under
  `/logs/agent/` under Harbor, or the native trial’s `agent/` directory, and declare it in the
  grading contract (`artifacts` for Harbor). When it writes to another store, read the result
  back after the turn.
- When evaluators need what a run changed, write the changed paths and one unified diff per
  changed file, not whole files.
- Never add steps the agent did not produce: an agent step written by the harness falsifies the
  trajectory and replaces the agent's final reply.
- Keep provenance (digests, revisions, input hashes) out of what evaluators read.

### Recording

- Before writing the recorder, inspect the installed framework's actual event types and field
  names; a guessed field that is absent silently drops events.
- One turn can hold several model messages. Keep the text before a tool call apart from the reply
  after its result, and keep separate completed messages separate even within one response.
  Stream deltas are fragments of their own message; join only fragments with the same message
  identity. A tool-only output has an empty message; never invent text for it.
- Record model names, timings, token usage and cost only when the runtime reports them; never
  estimate.
- Write the whole cumulative trajectory each time, atomically (a unique temporary file beside it,
  then a rename), so every snapshot keeps the earlier steps as an exact prefix. When callbacks can
  overlap, route every write through one writer. Finish pending writes before each reply and
  before exit, including on errors.
- Keep the partial trajectory when the agent fails, without changing or suppressing its error.
  A recording failure goes to stderr and never turns a successful run into a failed one.

### Redaction

- Filter every value that can reach the trajectory (tool arguments, results, errors, metadata,
  reasoning) recursively, keeping keys and structure and replacing secret values with a clear
  marker.
- Catch secrets by field and header name (authorization, cookie, token, password, secret, API key,
  credential, in any case) and by text that carries them (authorization headers, environment
  assignments, private keys).
- Also remove the values of the variables listed in `relai.toml` under `[runtime].env`, wherever
  they appear. Read only those named variables; never enumerate the environment to build the
  list.
- Filter at the final write as well as in any event helper, so no field slips past. Keep any
  redaction the project already does, and never let recording skip it.

### Repairing

Report environment blockers and continue independent work. Never evade containment, silently
change measurement semantics, or replace missing evidence with made-up output to get past one.

### Keeping setup fast

Overlap the review's code pass and the live-files proof with the first smoke trial. Send the
same reviewer the trajectory for its trajectory pass, and the earlier report plus the diff for
rechecks; it stays fresh because it has seen only the artifacts, never your reasoning.

### Shared harness and the smoke test

Every later test reuses `relai/harness/` unchanged: the image, adapter, recorder and shared mocks
belong there. Keep what only the smoke scenario needs in `relai/harness/smoke/`. When a later test
fails because the shared harness is broken, repair the harness here, not inside that test.

### Smoke evaluators

Decide what proves the integration before the first run, from the project itself: the tools that
must be called, with the arguments that matter and short fragments of their results, and the
smallest representative number of turns. Never guess long reply text. Choose the minimum
evidence that the real agent did real work. The smoke test is not frozen, but loosening a check
only to make it pass hides a broken harness; the review looks for that.

## Finish

Tell the user what you integrated and why, every project file you changed outside `relai/`, the
repository checks you ran and their results, the smoke test's scores from `summarize.py`, your
assumptions, and the commands to run it themselves.

The plugin's `examples/` has a working Harbor pattern (`harbor_agent.py` with `launcher.py`; copy
both into `relai/harness/` to use them), and [harbor-notes](harbor-notes.md) lists Harbor behaviors
that fail silently. Using the examples is optional.
