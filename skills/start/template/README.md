<!-- relai 0.1.0 -->
# relai/

This directory holds RELAI's state for the agent in this repository: what the agent must do and
where it can fail (`wiki/`), tests that run the real agent through its declared runner and score
what it did (`tests/`), and the measured record of changes made to it (`changes.md`). `STATUS.md`
shows where things stand and what to do next. It was set up by the RELAI plugin, but nothing here
needs the plugin to run: any coding agent or person can read, run and extend it with the declared
runner and the bundled Python checkers.

This file holds shared guarantees and terms. Read the parts relevant to the selected task;
direct fixes and project-native regression checks need no evaluation setup. Maintain useful
knowledge as described below. The layout below is the
default for RELAI-managed work: reuse existing project records when they preserve the needed
evidence, and use checker-specific formats only when using those checkers. File formats and
runner details are in `docs/`, read when the work touches them:

| File | Read it when |
| --- | --- |
| `docs/files.md` | Writing or reading `relai.toml`, a test, scores, judges, mocks, the wiki, `feedback.md`, `changes.md` or the state under `work/` |
| `docs/harbor.md` | Running Harbor, or setting up a hosted runner for pull requests |
| `docs/native.md` | Writing or using a native runner |
| `docs/board.md` | Rewriting `STATUS.md` |
| `docs/upgrades.md` | Copying or upgrading supplied files, including task verifiers |

## Fixed rules

Everything else (how the agent starts, adapters, Dockerfiles, test design, how the runner is
invoked) is the choice of whoever builds the tests.

1. **Declared runner.** Every test uses the declared runner: Harbor at the release in `[harbor].version` (the supported
   default), or a native
   project or benchmark runner meeting the shared trial contract (`docs/native.md`). Record the
   choice and reason.
2. **Recorded trials.** Each trial records the causal sequence of real model messages, tool calls and results, and
   each declared evaluator yields a score within its bounds plus feedback, or an explicit error.
   Project-native records may preserve this evidence in their own format. ATIF and the bundled
   trial layout are required when using integrations or checkers that consume them (`docs/native.md`). An
   agent-neutral coding task is scored from the workspace when a run has no trajectory (Harbor's
   oracle, or an agent it records without one); its evaluators that need one are "not recorded".
3. **Containment.** Trials are contained. Containers are the default. Host execution needs explicit authorization
   (an existing agreement may cover it) and reviewed sandboxing or simulated tool boundaries that
   prevent access to hidden tests, graders, credentials, other trials and unrelated user files,
   and effects outside the trial. A process launcher, working directory or environment allowlist
   alone is not isolation, and the plugin's example native runner is not a sandbox.
4. **Live source.** Files whose edits change the agent's behavior (`[target].live_paths` in `relai.toml`) reach
   each trial from the current source, never baked into an image.
5. **Frozen tests.** A frozen test does not change silently: a change needs a reason (`freeze.py --reason`), a
   line in `decisions.md`, and a fresh review. `freeze.py --begin-repair` records an agreed repair
   as open, so editing hooks stop asking before each of its edits until it is re-frozen. Independent review uses a reviewer with fresh context;
   review effort scales to the consequences, with proportional diff review for routine direct fixes.
6. **Secrets.** Secret values use the project's credential mechanism or `relai/.env`, written by the user.
   Coding agents never read or print them; files refer to them by name. Executable helpers may
   read the named credentials for authentication and redaction without exposing values to the agent.
7. **Mocks.** A mock replaces only a dependency's client boundary, never the agent, its model, or a
   tool's own logic. Its use needs authorization, which an existing agreement may cover
   (`decisions.md`).
8. **Reproducible tasks.** Tasks are reproducible in their selected execution environment using declared, authorized
   dependencies. Hosted portability is required only when the work needs it. The bundled
   hosted-builder recipe has additional image and build constraints (`docs/harbor.md`); other
   integrations may demonstrate equivalent execution guarantees through their own infrastructure.

## Terms

- **Splits.** Every test is `development` (the default: its runs may be read for diagnosis),
  `held-out` (optional: scored to decide whether a change is kept, never read for diagnosis), or
  `final` (a benchmark's test split: reported only, at the end or when the user asks). Scores
  used repeatedly for keep-or-reject decisions are selection evidence, not an independent final
  assessment; say so when reporting them.
  Held-out scores may continue supporting selection under the agreement with that disclosure;
  reuse does not automatically exhaust them. Diagnostic inspection changes their assessment
  role: record that change, and do not later call the inspected evidence untouched assessment.
- **Comparable runs.** Identify the intended intervention: the agent's code, prompts, model or
  settings may change. Hold the relevant measurement conditions (tests, grading, runner behavior,
  tool versions and external conditions) stable, or explain differences and which conclusions they
  support. Each side's measured source must be recoverable; a commit plus an unexplained dirty tree
  is not. `summarize.py` computes observed differences for matched case identifiers and raises
  notices about evidence limitations, including changed tests or runners. A numeric delta or
  successful exit does not establish comparability. Reuse a baseline with a rationale, and report
  unmatched cases and each side's scored/attempted counts.
- **Observations, not verdicts.** `summarize.py` describes means and variability. A higher mean
  is not a win, an equal mean is not equivalence or absence of harm, and a stronger claim needs
  its own justified method.
- **Agreement.** The objective, guardrails, scope, budget, check-ins and delivery for improvement
  work: the user's existing instructions, an improvement agreement (`records/improve/plan.json`), or
  a loop contract (`records/loop/state.json`). The **objective** is the measure that must improve
  (behavioral success, cost or latency); **guardrails** are the other measures a change must
  keep within agreed bounds. During a loop its contract is the active agreement, including
  covered improvement work; otherwise use the current improvement agreement. Do not create
  conflicting duplicate budgets.
- **Incumbent.** The last accepted version of the agent, initially the user's code.

## Maintain useful knowledge

Across all skills, actively maintain EvalsWiki (`wiki/` here) and relevant local state when the
information will assist future development, evaluation or improvement. Initialize them when
justified; respect read-only requests and user opt-outs. Reuse suitable project records, update
existing entries and revise or remove superseded conclusions. Retain durable requirements,
decisions, supported risks, corrections and reusable lessons rather than transient plans or
speculative filler. Explain material updates in the normal report without repeating covered
approval requests. Setup serves that future value; it is not a prerequisite to answering the
immediate question. Give substantive knowledge one authoritative home; link to it with concise
summaries in reports, boards or proposals rather than repeating the full analysis. Keep useful
state current as work progresses without turning every intermediate observation into another
artifact. Preserve independently maintainable requirements, risks and consequential questions;
less duplication must not mean losing their evidence or uncertainty. Do not put protected
assessment contents into optimizer-visible knowledge.

Actively maintain reusable project-local assets when they will make future analysis or development
easier. Inspect and reuse existing scripts, adapters, queries or other suitable assets; improve or
consolidate them when the current work reveals a concrete need, preserving user modifications.
Leave useful nontrivial work runnable and understandable in the project's language and conventions.
Match maintenance effort to expected reuse and ownership cost, within authorized scope; respect
read-only requests and opt-outs. Asset creation is not a completion checklist or a reason to build
generic infrastructure without a concrete need.

## Layout

| Path | What it holds | Committed |
| --- | --- | --- |
| `STATUS.md` | Progress board and next step (`docs/board.md`) | yes |
| `relai.toml` | Target and its configuration, live paths, runner, judge settings | yes |
| `changes.md` | Every attempted change to the agent: what, why, before/after, kept or not | yes |
| `feedback.md` | The user's feedback on specific runs and judge scores, and what each answer became | yes |
| `decisions.md` | The user's choices and the coding agent's stated assumptions, newest last | yes |
| `UPSTREAM.md` | Source versions/commits and adaptations of copied files (`docs/upgrades.md`); an existing equivalent record is fine | yes |
| `docs/` | The detailed contracts listed above | yes |
| `bin/` | The shared checkers (below), plus any example script copied from the plugin | yes |
| `harness/` | How the agent runs in a trial: adapter, recorder, image recipe; `mocks/` with `MOCKS.md`; `smoke/`, the smoke test | yes |
| `wiki/` | `requirements/`, `risks/`, `open-questions/`: one page per item; `index.md`; `attachments/` for cited trace excerpts | yes |
| `tests/<id>/` | One test per behavior | yes |
| `benchmarks/<id>/` | A benchmark from another repository: its README, and its case template and `cases/` (import) or its adapter (wrap) | yes |
| `evaluators/<id>/` | Criteria shared across tests | yes |
| `setups/<id>/` | A team's setup for coding agents, laid out as in a repository root (the `coding-evals` skill) | yes |
| `frozen.json` | Digests of frozen tests (written by `freeze.py`) | yes |
| `records/` | Decision records teammates need: scenario tables and grader previews (`eval/`), fresh reviews (`reviews/`), the improvement agreement and lessons (`improve/`), the loop contract and iterations (`loop/`) | yes |
| `.env` | Secret values | never |
| `work/` | `runs/` (measurements of this checkout), `candidates/<name>/` (worktrees and runs of proposed changes, never mixed into `runs/`), `improve/state.json` (resume checkpoint), `benchmarks/<id>/ledger.json`, scratch | never |

## Checkers

Shared tools implement the guarantees above. Use a suitable one directly; adaptation follows
[Adapting supplied implementations](#adapting-supplied-implementations). They are read-only
except `freeze.py`, `benchmark.py` (which writes only `work/benchmarks/`) and explicitly requested
summary exports. Python 3.11+, standard library; Harbor-based checks use `[harbor].version` through `uv`.
Exit status: 0 nothing wrong, 1 findings (including a changed frozen test), 2 a usage or
environment error; errors go to stderr. `--json` prints machine-readable output on stdout, except
`summarize.py --json <path>`, which also writes the full evidence to that file.

| Command | Use it |
| --- | --- |
| `python3 relai/bin/check_task.py relai/tests/<id> [--cloud] [--verifier [--fixture DIR]]` | After writing or changing a test. `--cloud` additionally checks the bundled hosted-builder recipe; local checks do not require anonymous public images. `--verifier` (Harbor only) runs the verifier in the local container engine on a synthetic normal and empty-reply trajectory; `--fixture DIR` adds files to `/logs/agent` |
| `python3 relai/bin/check_trajectory.py <trajectory.json> [--turns N]` | On a trajectory from a trial |
| `python3 relai/bin/check_wiki.py [relai]` | After changing the wiki or a test's `covers`; checks managed attachment JSON syntax, not factual fidelity |
| `python3 relai/bin/summarize.py <run dir> [--baseline <dir>] [--details] [--json <path>]` | After a run; concise by default, `--details` for full tables, `--json` for complete per-attempt evidence and candidate/baseline/comparison warnings. Notices do not change the exit status. Comparison JSON reports `observed_change` (`higher`, `lower`, `equal`, `not-comparable`) and descriptive `noise`/`se` |
| `python3 relai/bin/freeze.py relai/tests/<id>` | Before a test's first real run; `--reason` to re-freeze a change, `--begin-repair --reason` to open an agreed repair, `--check` to report |
| `python3 relai/bin/benchmark.py init\|sample\|batch\|record\|fidelity\|coverage <id>` | For a benchmark: `init` its splits and sample, choose a `batch`, `record` after every run, check `fidelity` against its own scorer |

Example scripts (a Harbor agent and launcher, a native runner, an API judge, a trace triager and
a code-evaluator helper) live in the plugin's `examples/`. None is part of `relai/` until an
integration chooses it; then it is copied, owned and adapted like any project code, or replaced
by a project-native equivalent that meets the same contract.

## Adapting supplied implementations

Examples and shared helpers serve execution, recording, measurement and safety guarantees; their
implementation details are not universal requirements. If a script fails or does not fit, inspect
the cause and repair, adapt, replace or bypass it within the authorized scope. Preserve the
purpose it served, verify the affected guarantees with focused checks, and disclose material
limitations. Reuse relevant plugin tests when available; the full plugin suite is not a
prerequisite to a project adaptation. A script failure alone neither proves an agent failure nor
requires stopping independent work.

Distinguish implementation repair from changing what is measured. A corrected adapter or parser
may preserve semantics; verify the affected guarantees and record differences relevant to the
claim. Changing grading meaning, test coverage, relevant measurement conditions or acceptance
criteria needs the controlled repair process and comparable evidence before optimization resumes.
Never remove a failing check merely to declare its guarantee satisfied.

## Prerequisites

Check these before the first trial, and again when a trial fails for an environment reason. Check
keys by name only: confirm `NAME=` is present in the environment or `relai/.env` without reading
or printing the value.

- **Every runner:** Python 3.11+ for the checkers; every key `relai.toml` names is set:
  `[runtime].env`, and with API judges `[judge].api_key_env` or the provider's default
  (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`).
- **Harbor:** `uv`; a running container engine Harbor drives locally (`docs/harbor.md`) that runs
  containers and shows temp-directory files through bind mounts. A mount the engine
  cannot see arrives empty without an error (VM-based engines such as Colima may share only the
  home directory), so keep mounted paths, including `TMPDIR` for the checkers, under the home
  directory. A task with a restricted network also needs the engine's image builder for Harbor's
  egress sidecar (`docker buildx` on a Docker CLI; the Harbor notes).
- **Native:** the integration declares and checks its own runtime and containment (Fixed rules, *Containment*).
- **When Harbor or a container engine is missing:** tell the user what is missing and the
  alternatives: start or install a supported engine, a native runner with authorized containment
  (`docs/native.md`), or a hosted runner (`docs/harbor.md`). Agent-neutral coding tasks need
  Harbor-compatible execution, locally or hosted.

## Working with the user

RELAI is something the user steers, not a black box.

- **Approval points.** Unless existing instructions cover or delegate the decision, get approval
  for the risk list, test scenarios, grader previews before freezing, and the improvement
  agreement. These are named decisions within independent workflows, not a sequence every task
  must complete. Ask only about what remains open; restate consequential changes after discussion.
  When nothing says how involved the user wants to be, offer once to delegate scenario, grader and
  check approvals to a fresh independent review, and record the answer.
- **Recommendation first.** Ask with the host's structured question tool when it has one (for
  example `AskUserQuestion` or `request_user_input`), otherwise in ordinary chat, your
  recommendation first. Pause only work that depends on the answer.
  Never ask the user to edit a file to answer. Append every answer to `decisions.md`, and every
  consequential choice you made yourself as an assumption.
- **Clear questions.** State the decision and why it matters in the user's terms; explain
  unfamiliar terms through their practical effect. Separate findings and proposed defaults from
  choices needing an answer. Give concrete options, their consequences and a recommendation when
  supported; make clear what the answer approves and what can wait. Each prompt should make sense
  on its own. Batch related choices at a checkpoint, but give independently answerable choices
  separate prompts or labeled rows rather than compressing them into one sentence.
- **When the user is asked.** Questions wait for a natural moment; only a blocking item
  interrupts a step.

  | Moment | What is asked |
  | --- | --- |
  | End of `discover` | The risk table, open questions, and feedback on the runs just read |
  | Start of an `eval` build | Only what is still open: where to start when there are no risks, what the results will decide, and on first use the harness setup questions |
  | `eval` scenario approval and grader preview | Approval of the scenario table (with the build's cost) and of the grader preview, in manageable subsets |
  | End of an `eval` run whose judges scored real trials for the first time, or after a rubric change | That run's judge checks, while the run is fresh, and the pass mark if it is unset |
  | `coding-evals` scope and task selection | Unresolved scope and task selection, combined when ready; reuse existing authorization |
  | `coding-evals` check preview before freezing | Scoring and coverage approval still needed, in manageable subsets; a delegated independent review may cover it |
  | Before the first paid `coding-evals` run | What to compare, if the request named a change or another agent, and the run budget |
  | End of the first `coding-evals` run that scored real trials | Its judge checks, and the pass mark if it is unset |
  | Each `loop` iteration's digest | Everything pending; a blocking item is asked at once, and only it pauses the loop |
  | Whenever the user asks | Everything pending |

  Size the sitting by actual decision effort, not the number of prompts.
  A table with many independent judgments is not automatically one small question. Group related
  decisions or recommend a useful top batch, with explicit bulk recommendations where appropriate.
  Prioritize blocking items, likely failures, judge checks, then open questions and the rest.
  Close moot items first (`docs/files.md`, `feedback.md`), say how many remain, and leave
  them on the board. An answer of "later" leaves an item pending.
- **Updates.** Lead with the answer or decision, uncertainty and the next useful action; put
  optional future mechanics and supporting detail afterward or in existing files. When another
  action is useful, name it and why; a completed request need not be routed into another stage.
  Update `STATUS.md` when using RELAI-managed state.
- **Cost before spend.** Before any paid run, state trials × attempts and the cost and time per
  trial, measured from a previous trial when one exists, otherwise marked as an estimate. During a
  run, report trials done, time left and running cost.

### Host notes

- Measuring another checkout (a worktree for a change, or the pre-change revision for a
  baseline): it gets the same `relai/` (copy it if it is not committed, and link `relai/.env`
  without reading it), and the harness runs that checkout's source.
- When independent review is required, use a reviewer with fresh context, such as a subagent
  without inherited history. Give it the review brief and the paths, never your own conclusions.

## Defaults

Starting points, not rules. Change them here or in an agreement, and record why in `decisions.md`.

| Default | Value |
| --- | --- |
| Questions per sitting | 8 |
| Judge flagged for low agreement | below 90% over 3 or more judge checks |
| Judge checks per new or changed judge | 1 or 2 (a high and a low score) |
| Traces that call for triage instead of reading each in full | about 50 or more |
| Triage pilot before a full run | 20 traces |
| Benchmark fidelity pilot | 3 to 5 cases |
| Benchmark split small enough to run whole | under about 50 cases |
| Benchmark held-out sample (`benchmark.py init --held-out-n`) | 80 cases |
| Derived benchmark splits (`--derive-splits`, only when agreed) | 60/20/20 by category; or a fifth of development when only the validation split is missing |
| Board history | last 5 runs per test; last 5 changes |
| Priority suggestion (the `improve` skill's `prioritization.md`) | decay 0.7, exploration 0.3 |
