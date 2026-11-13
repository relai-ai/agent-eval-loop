# File contracts

The formats the checkers, the board and other coding agents rely on. The rules and terms they
serve are in `../README.md`.

## `relai.toml`

The judge/triage provider fields below describe the shipped example's implemented APIs, not a
closed list of valid integrations. Reuse a suitable project provider; adapt or replace the example
for other APIs while preserving the score/error, redaction, usage and data-authorization contracts.
Record that integration's configuration in project conventions rather than inventing a universal
provider registry. Secret values stay in the project's credential mechanism or `.env`, never here.

```toml
[target]
name = "retail customer-service agent"
configuration = "default retail domain"            # what was integrated
evidence = "README quick start runs --domain retail" # why it is the real configuration
live_paths = ["src/agent/prompts/**", "data/policy.md"]  # read live in every trial
entrypoints = ["python -m app.main"]               # real entrypoint, used only with reviewed containment

[judge]
mode = "api"                 # "api" (bin/judge.py, copied from the plugin) or "subagent"
provider = "anthropic"       # or "openai", "openrouter", "openai-compatible" (model required)
# base_url = "http://localhost:4000/v1"   # openai-compatible only (LiteLLM, vLLM, ...)
# api_key_env = "LITELLM_API_KEY"         # openai-compatible only: the key's variable name
model = "claude-opus-5-5"     # required; no default
effort = "medium"            # optional, Anthropic only

[triage]                     # optional table; needed only to run bin/triage.py (it never uses [judge])
provider = "openrouter"      # same keys as [judge]: a cheap model, one call per trace
model = "anthropic/claude-haiku-5.5"

[runtime]
env = ["OPENAI_API_KEY"]     # names needed in a trial; values from environment or relai/.env

[runner]
kind = "harbor"              # or "native"; a missing [runner] means Harbor in containers
isolation = "container"      # or authorized, reviewed "host" containment for native runners

[scoring]
pass_mark = 0.8              # example only: the user's choice after the first scored run, no default

[harbor]                     # Harbor only (docs/harbor.md)
version = "X.Y.Z"            # exact Harbor release; the latest stable when recorded
agent = "my_agent:MyEvalsAgent"                         # passed to `harbor run -a`
pythonpath = ["relai/harness"]                         # where Harbor imports it from
agent_env = { RELAI_PASS_ENV = "OPENAI_API_KEY" }       # passed as --ae; never secret values

[harbor.image]               # the harness image tasks start FROM
tag = "my-agent-relai:deps"  # the name task Dockerfiles use in FROM
dockerfile = "relai/harness/Dockerfile"   # paths relative to the repository root
context = "."

[benchmarks.bench-x]         # optional, one table per benchmark brought in
source = "https://github.com/org/bench-x"  # path or URL; read-only. A URL is cloned to
                             # ~/.cache/relai/benchmarks/<name>@<short commit>/
commit = "a1b2c3d"           # the version the cases come from; a new version is a new benchmark id
mode = "wrap"                # "import" (cases become tasks for the declared runner) or "wrap" (run its own runner)
run = "python run.py --agent relai/benchmarks/bench-x/agent.py --tasks {cases} --out {out}"  # wrap only
cases = "data/tasks.jsonl"   # where the case list lives in the benchmark
case_id = "task_id"          # field names in the benchmark's own format
split = "split"              # its split field ("" when it has none)
category = "domain"          # optional, for balanced sampling
scorer = "the benchmark's own reward (run.py --score)"
splits = { train = "development", validation = "held-out", test = "final" }

[coding_evals]               # optional: an eval project for coding agents (the coding-evals skill)
repos = { api = "https://github.com/acme/api", web = "../web" }  # where tasks may come from; read-only
task_code = "private"        # where tasks (which hold source code) may live: "private" or "shareable"

[[coding_evals.agents]]      # the agent as the team uses it (the baseline), plus any change or other agent compared
id = "<label>"
agent = "<Harbor agent name>"  # passed to `harbor run -a`
model = "<provider/model>"     # passed as -m
version = "<agent release>"    # the agent's own release, recorded before the first paid run; a change is a measurement change
auth = "subscription"          # or "api-key": how the agent authenticates in a trial
env = ["<CREDENTIAL_NAME>"]    # names only; values exported, from a secrets tool, or in relai/.env (written by the user)
training_cutoff = "YYYY-MM"    # optional: for reporting tasks whose public fix predates it
baseline = true                # the version other runs are compared against

[[coding_evals.setups]]      # optional: a team's setup to compare or improve
id = "team"
path = "setups/team"         # relative to relai/
agent = "<agent id>"         # optional: the agent whose files it is written in; matched setups share the same guidance
```

Invalid runner kinds or isolation values are errors.

## A test: `tests/<id>/task.toml`

A task with this shared metadata table. Harbor uses its full task format; native runners keep
what their integration needs alongside the metadata. A test's identity is its path relative to
`relai/` (`tests/<id>`, `benchmarks/<id>/cases/<case id>`), which `freeze.py` and `summarize.py`
use. A wrapped benchmark's cases are `benchmarks/<id>/<case id>` in `summarize.py`, pinned by
commit.

```toml
[metadata.relai]
id = "<id>"                          # equals the directory name
behavior = "One sentence: the behavior this test checks."
covers = ["refund-policy", "refund-before-lookup"]  # wiki page ids it checks: requirements and risks
split = "development"                # or "held-out" or "final" (README, Terms)
prohibition = false                  # true only if doing nothing is a pass

[[metadata.relai.evaluators]]
id = "looks-up-order"
type = "code"                        # scored by the verifier
method = "exact"                     # code can decide it with certainty
criterion = "Calls get_order_details with the order id the user gave."
min_score = 0.0
max_score = 1.0

[[metadata.relai.evaluators]]
id = "explains-refund"
type = "judge"                       # scored after the trial from the trajectory
method = "semantic"                  # open-ended meaning: always a judge
criterion = "Explains the refund timeline in a way the policy supports."
rubric = "tests/judges/explains-refund.md"   # relative to the test directory
min_score = 0.0
max_score = 1.0
```

### An agent-neutral coding task

A coding task any coding agent can run (the `coding-evals` skill): Harbor installs the
agent, so the task brings only the workspace and the checks, and needs no harness. Beside the table
above it declares:

```toml
[agent]
timeout_sec = 1800                   # required: Harbor has no default
# network_mode = "no-network"        # restricted by default when the fix can be found online, open otherwise

[metadata.relai]
agent_neutral = true

[metadata.relai.coding]
source = "pr"                        # session, pr, history, injected, anchor or written
origin = "acme/api#412"
request = "verbatim"                 # or "symptom": the developer's own words, or a symptom written from a PR or commit
repo = "api"                         # a key of [coding_evals].repos
start_commit = "<sha>"               # the workspace starts here, with its ancestors only
fix_commit = "<sha>"                 # the real fix, absent from the workspace
fix_date = "2026-05-01"
public = false                       # a public fix may be in a model's training data
kind = "bug-fix"
category = "billing"
workspace = "/app"
primary = "fixes-the-bug"            # the code evaluator that says the task was solved; reads the workspace
synthetic = false                    # an injected bug: reported apart

[[metadata.relai.evaluators]]
id = "review-ready"
type = "judge"
inputs = ["instruction", "verifier/diff.patch"]   # what the judge sees; default ["trajectory"]
# ...

[[metadata.relai.evaluators]]
id = "my-check"
type = "code"
trajectory = true                    # a code check that reads the run record: "not recorded" without one
# ...
```

Its `tests/` holds `test.sh` and `coding_checks.py`, the plugin's verifier (or a recorded adaptation that keeps its guarantees), a
`verify.py` that calls one check per code evaluator, and the judges' rubrics; `solution/solve.sh`
applies the reference fix. The verifier shares the agent's container and trusts only what arrives
with `tests/`:
`params.json` (with the start commit and the manifest of `tests/protected/`), the protected
snapshot and the hidden tests. Beside the score files it writes `/logs/verifier/diff.patch` and
`facts.json` for judges. `check_task.py` checks the leak guards and this layout. Without a
trajectory, evaluators that need one are "not recorded" and left out of the pass rule.

`tests/params.json`, read by `coding_checks.py`:

| Key | Value |
| --- | --- |
| `workspace` | the repository in the container (`/app`) |
| `start_commit`, `protected_manifest` | written by `protect`; the verifier diffs from the start commit |
| `hidden_tests` | `{"files": {"hidden/x": "path/in/repo"}, "command": "...", "timeout_sec": 900}` |
| `suite`, `build` | `{"command": "...", "timeout_sec": 1800}` |
| `protected` | globs (`**` for any directories) of files that must stay as they were: existing tests, CI files, test-runner configuration; hidden test paths inside |
| `new_files_ok` | protected globs where new files are welcome (new test files) |
| `restore` | globs of files put back before any command runs, never held against the agent (`pyproject.toml`, `package.json`) |
| `allowed_changes` | protected or restored globs the task allows to change |
| `scope` | `{"allowed": [globs], "max_files": n}` |
| `setup_files` | installed setup paths; installation is excluded, subsequent agent edits are counted |
| `setup_manifest` | trusted installed-state manifest generated by `coding_checks.py setup <installed-workspace> <task>` with snapshots in `tests/setup/`; required when `setup_files` is nonempty |
| `ignore_changes` | extra globs never counted as changes (what the image build or test run leaves untracked) |
| `must_not_exist`, `secrets.canary` | for those checks |

Missing params or hidden files are errors: the task itself is broken.

## The smoke test: `harness/smoke/`

A task for the declared runner whose only job is to prove the harness works: the real agent ran,
was recorded truthfully, and its output reached the evaluators. It is not an eval: never select
it for a measurement, regression check, benchmark, optimization or pull-request gate, and never
report its scores as agent quality. Rerun it after any harness change, and when a test fails at
runtime. Smoke failure implicates shared setup; smoke success narrows investigation but cannot rule
out a scenario-dependent harness defect. Inspect the failing trial before assigning its cause.
It is not frozen: fix its checks as the harness needs, and the harness review confirms
they check a real outcome and can fail.

## Scores

- Code evaluators (the verifier, `tests/test.sh`) write `/logs/verifier/reward.json`
  `{"<id>": number}` for every declared code evaluator, `/logs/verifier/feedback.json`
  `{"<id>": "text"}` for every score, and `/logs/verifier/errors.json` `{"<id>": "message"}`
  when a check could not run. The plugin's example `evaluate.py`, copied into a task's `tests/`,
  writes all three.
- A judge sees what its evaluator's `inputs` lists (default `["trajectory"]`; also
  `"instruction"` and `"verifier/<file>"`, a file the verifier wrote in the trial). A missing
  input is an error, never a score.
- Judges write `<trial dir>/judges/<id>.json` after the trial:
  `{"score": n, "feedback": "...", "model": "...", "judge": "api"|"subagent"}` or
  `{"error": "..."}`. The API example retains returned usage, cost and judging time on errors
  too. `judges/<id>.attempts.jsonl` preserves each attempt; `<id>.json` is its latest-result mirror.
  For spend, count the history when present, otherwise the legacy latest result, never both.
- A low score is evidence about the agent. An error, a missing score, or a failed trial is not:
  report them apart, never as zeros.
- A separate verifier sees only `tests/` and the files `task.toml` lists in `artifacts`, so list
  every file under `/logs/agent/` that a check reads.

For historical score interpretation, `summarize.py` prefers the optional original
`evaluator_definitions` recorded with the trial (`native.md`). Without them, it retains
available results using current task definitions and reports that limitation through
`evaluator_source` and a notice. Current bounds are not verified historical definitions.

**The pass rule.** An attempt (one trial) is scored when it has a trajectory (an agent-neutral
coding task's attempt needs none), the runner did not
end it before grading completed, and every evaluator the test declares has a score within its
bounds. The attempt's score is the mean, over those evaluators, of
`(score - min_score) / (max_score - min_score)`. A test passes when the mean of its scored
attempts' scores is at or above `pass_mark`. A test with no scored attempt has not passed: report
it apart, as a runtime failure, evaluator error or pending judge. `summarize.py` computes exactly
this as each test's `mean`.

**Subagent judges.** With `[judge] mode = "subagent"`, judges are fresh subagents that have not
seen the run being judged or the conversation around it; one subagent may judge several trials.
Give each the rubric file, the criterion, the score bounds, the paths of the inputs its evaluator
lists (the trajectory by default) and the output path `<trial dir>/judges/<id>.json`, plus the rules the example judge gives its model:

- Judge only what the trajectory shows; do not assume actions that were not recorded.
- Score the whole relevant turn: all agent steps after a user step and before the next one.
- Accept any wording that satisfies the rubric; do not reward or punish style it does not mention.
- If the rubric grades a deliverable the user asked for and the agent did not produce it, give the
  minimum and say it is missing. If declining or asking was the right response, nothing is missing.
- Give a score within the bounds and feedback that names every unmet criterion, where it occurred,
  and what would earn full marks.

## Mocks

Each mock is listed in `harness/mocks/MOCKS.md` with the dependency it replaces, its real hosts
or functions, why, and the applicable authorization (an approval or covering agreement). A mock
appends one JSON line per call to
`/logs/agent/mock-journal.jsonl` (or `agent/mock-journal.jsonl` in a native trial):
`{"target", "operation", "input", "outcome", "response"}`, where `outcome` is `matched`,
`unmatched` or `error`. A call that changes the mock's state also records the change as
`state_change`. No journal means no calls.

## `frozen.json`

Written only by `freeze.py`: each test's digest (all files except `README.md`), when it was
frozen, and the reason for every re-freeze. `repair` (`reason`, `since`) marks a repair in
progress (`freeze.py --begin-repair`), run only after the repair is agreed and recorded in
`decisions.md`; re-freezing removes it. It changes no score's meaning:
only editing hooks read it, to stop asking before each edit of that test.

## `changes.md`

One `## ` entry per attempted change to the agent, newest last: the date and a one-line title;
where the change lives (branch, commit or worktree); the diagnosis it acted on; the tests
targeted and checked; the before and after scores from comparable runs; the verdict (kept,
rejected, or left for review) with the reason. A rejected change stays recorded so nobody
retries it blindly.

## `decisions.md` and `UPSTREAM.md`

`decisions.md` is one line per decision, newest last:
`- 2026-11-12 · <the choice, in a sentence> · <asked: the user | assumed: the coding agent> · <source>`.
The source links to where the detail lives (a feedback item such as `feedback.md#FB-2026-11-traces-07`,
a wiki page, `records/eval/2026-11-12-scenarios.md`); link to it rather than copying the answer.
For approvals, identify the reviewed subset, revision or content identity and limits in that
record. For explicit deferrals, retain what was deferred and when or why to revisit it. Keep
these outcomes consistent with the source item, whether the answer arrived in chat or an app;
app-local reviewed flags and comments are not approval records.
`UPSTREAM.md` is one line per copied file or folder: its path here, the plugin path and version
or commit it came from, and a short note of local adaptations.

## `feedback.md`

Requests for the user's feedback on one specific run ("was this run right?") and judge checks.
It is not the place for general questions:

| | Open question (`wiki/open-questions/`) | Feedback item (`feedback.md`) |
| --- | --- | --- |
| Asks | How should the agent behave, in general? | Was this one run (or judge score) right? |
| Answer becomes | A requirement; the question page is deleted | A regression test, risk evidence, a judge-agreement point, or nothing |
| Lifetime | Temporary decision, resolved into durable knowledge | Closed once answered |

A feedback answer that exposes a general ambiguity also opens a question; answering a question
can settle pending feedback items. One `## ` item each, with an id `FB-<year>-<month>-<source>-<n>`
(the source being the trace batch or run it came from) so other files can link to it:

```markdown
## FB-2026-11-traces-07: Should the agent have refunded the lost tablet?
Status: pending
Trace: traces/2026-11/4411.json, messages 14-16; excerpt: wiki/attachments/2026-11-traces/4411.json
What happened: the user asked for a refund of a delivered tablet they lost; the agent transferred.
Recommended: no refund (out of policy), but it should have said so and kept helping.
Answer:
Outcome:
```

`Status` is `pending`, `answered` or `dismissed`. Add `Blocking: yes` only when work cannot go on
without the answer (a safety-sensitive or irreversible behavior, requirements that conflict). An
item a later change, a new requirement or a retired test has made moot is closed with
`Status: dismissed` and `Outcome: moot - <why>`. When the user answers, fill `Answer`, set the
status, and record in `Outcome` what the answer became. An open question page may carry the same
`Recommended:` and `Blocking:` lines.
An explicit deferral leaves the item pending; note its scope and revisit context on the item and
link the decision from `decisions.md`. Silence is not a user decision to defer. Review apps use
these same item identities and outcomes, or explicitly reconcile imports/exports before another
review; they must not silently maintain competing answers.

A **judge check** asks whether the user agrees with a judge's score on a real trial. It adds
`Kind: judge-check` and `Judge: tests/<id> · <evaluator id> · <job>/<trial>`, says what the judge
scored and why, and its `Answer` starts with `agree` or `disagree`.

## Wiki pages

`wiki/<requirements|risks|open-questions>/<id>.md`, where the file name is the id. Each starts
with a `# ` title. A requirement states one behavior the agent must show; a risk states its
mechanism, trigger and observable failure; an open question states what is unclear and why it
matters. Tests cite pages in `covers`. A risk page also carries short labelled lines:

```markdown
# Refund promised before the order lookup

Mechanism: the refund policy sits early in the prompt, so the agent answers from policy alone.
Trigger: a user asks "can I get a refund?" without giving an order id.
Observable failure: the agent promises a refund without calling get_order_details.
Impact: high. Confidence: medium. Triggerability: high.
Status: admitted
Threatens: refund-policy
Found at: 3f2a9c1 (agent: support-bot)
Evidence: src/agent/prompts/refunds.md:12; attachments/ingest-2026-11/42.json

## Probes
- tests/refund-without-order-id (2026-11-04): triggered
```

`Status` is one of `proposed`, `admitted`, `confirmed`, `refined`, `rejected` or `retired`.
Ratings are `low`, `medium`, `high` or `critical`. `Threatens` lists requirement ids.

## `records/`

Committed decision records, so teammates can see what was approved and reviewed:
`eval/<date>-scenarios.md` and `eval/<date>-grader-preview.md` (eval builds), `reviews/` (fresh
reviews of harnesses, tests, coding tasks and changes), `improve/` and `loop/` below. Keep them
short and redacted like wiki excerpts: link to runs and traces rather than copying their content,
and keep protected assessment contents out. Raw runs, candidates and scratch stay in `work/`.

## `records/improve/` and `work/improve/`

- `records/improve/plan.json`: the improvement agreement (README, Terms): objective, guardrails and their bounds,
  scope, the selection rule when several candidates compete, `budget_usd` and `since` (an ISO
  date; the board counts spend from it). During a loop, use its contract instead of duplicating
  covered agreement or budget fields here.
- `work/improve/state.json`: active experiment work, as a checkpoint for resuming.
- `records/improve/notes.md`: evidence-backed lessons, updated rather than appended.

## `records/loop/state.json`

`contract`: the loop's agreement (objective, guardrails, scope, inputs including any triage
provider and its data authorization, length, budget, when to ask, `approvals` (`delegated` or
`supervised`), check-ins, watch mode, delivery). When a monetary ceiling applies, record `budget_usd` and
`since` (the budget's ISO start time) in the contract. The board counts actual spend since that
time, including delegated improvement work; per-iteration limits supplement the overall ceiling.
`iterations`: one entry per iteration. `n`, `started`, `trigger`, `verdict`, `reason` and
`cost_usd` are required; the counts are optional summaries, filled when known (the authoritative
records are `changes.md`, `decisions.md` and the runs):

```json
{"n": 1, "started": "2026-11-10", "trigger": "new traces", "traces_triaged": 0, "wiki_updates": 0,
 "tests_added": 0, "rounds": 0, "candidates_tried": 0, "changes_kept": 0, "verdict": "none",
 "reason": "", "held_out_before": null, "held_out_after": null, "regressions_prevented": 0,
 "human_decisions": 0, "cost_usd": 0.0}
```

`trigger` names what started it (first run, new traces, new answers, new tests, user request,
investigation). `rounds` counts experiment rounds, including diagnosis; `candidates_tried` counts
actual candidate attempts; `changes_kept` counts accepted candidates. `verdict` is `accepted`
when delivered changes passed verification, `rejected` when candidates were tried and none
survived, or `none`. Held-out values are null without a held-out set. `human_decisions` counts
the answers, approvals and vetoes the user gave: the loop's measure of human time. This file
summarizes orchestration; it is never evidence that a candidate ran or was accepted.
