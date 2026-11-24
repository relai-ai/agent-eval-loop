# Running: the baseline, then changes, setups and agents

## Before any paid run

Every task is frozen and healthy. Pilot one attempt of each task with each version run (its cost,
or with a subscription its plan usage and time); when the set is too large for that, pilot at
least one task from each repository and each builder. This pilot is itself paid: state its
expected cost and get the user's yes (or a covering agreement) first, then use it to estimate the
full run for the budget question. It also shows that the agent installs, reaches its model
and does work, so a trial with no model calls is fixed before any larger run. The pilot is the
first run of an agent's own work against the checks. When every version fails a check or a trial
changes no code, inspect solvability, integration, grading and the trajectory before scaling up;
these outcomes alone do not establish a task defect. When no task changes after the pilot, its
trials count as the full run's first attempt. Then follow "Cost before spend" in `relai/README.md`.
Choose attempts for the decision, observed variability and budget; coding agents can vary between
runs. Reuse deterministic work only when it preserves the uncertainty being measured.

**Agent timeout.** Set `[agent].timeout_sec` at build for an agent doing the work, never from
the reference fix, which runs instantly. Preserve an agreed latency limit when speed is part of
the outcome. Otherwise use measured trials to check whether setup or execution limits obstruct
the intended measurement. Repair accidental limits under the *Frozen tests* rule and establish
comparable evidence; do not silently discard genuine time-budget failures.

## Running

The first run measures the agent as the team uses it now: the baseline. On its own it says how the
agent does on the team's work and what it gets wrong, and later runs reuse it. When the user asks,
compare one change against it: a model, a version, or a setup (below). Comparing other
agents works the same way, with the extra care in *Comparing agents* below. Run each
version as `relai/docs/harbor.md` describes, with `-a <agent> -m <model>`, the agent's recorded
version (the [Harbor notes](../../eval/references/harbor-notes.md) say how), its credential, each
task's network setting, and each version's runs in their own directory under `relai/work/runs/`.
Score the judges, then `summarize.py` each run; when comparing, pass the baseline with `--baseline`.

## Reading the results

- **Solved** is the primary evaluator at full marks, per task, averaged over attempts;
  `summarize.py` prints it per test and overall, apart from the mean over every recorded check,
  which goes beside it, and the pass rule once `[scoring].pass_mark` is set. An agent can solve more and pass less (it fixes the bug but
  edits tests or skips verification). Show scored/attempted counts and missing-result reasons;
  unknown scores are not failures. Rerun missing evidence when useful and authorized, or limit
  the conclusion to what was recorded.
- **Headline metrics.** Lead with five, each answering one question a team lead asks, with the
  checks behind them below as detail:
  - **Solved** (does it work?), as above.
  - **Merge-ready** (would we merge it as it is?): the scored attempts that met every mark in
    `[scoring].marks` (`relai/docs/files.md`, *Marks*), usually set on the main check,
    `no-regressions`, `tests-untouched`, `in-scope` and `code-review`. Which checks and marks is
    the user's choice, with no default; until they choose, show `code-review`'s spread instead.
  - **Codebase fit** (does it look like our code?): `code-review`'s Codebase fit criterion
    (`codebase-fit`) over every scored attempt, with how many scored none, so agents are compared on the same tasks.
  - **Trustworthy** (can I trust what it did and said?): counts, not one verdict: attempts with a
    false claim (Report accuracy, `honest-report`, at none) and attempts that failed Process safety
    (`safe-process` at none), saying from its feedback whether for skipped verification or an
    unsafe action. Without a task that plants an
    unsafe instruction (*Security tasks* in [checks](checks.md)), say unsafe actions were not
    tested rather than reporting none found as a result.
  - **Cost · Time** (what did it take?), as below.
- **Paired, task by task**, when comparing. Compare the same tasks for both sides. A difference within the run's
  spread, or on few tasks, supports no claim either way.
- **Per check**: how often each behavior held. Checks with errors were not recorded for that
  agent. Report a check whose meaning differs between tasks separately for each meaning:
  `tests-untouched` covers existing tests where they are `protected`, and only CI and runner
  files where they are restored; group tasks by whether `params.json` lists the existing tests
  under `restore` ([checks](checks.md)).
- **By kind of work**: suggest routing only when a difference holds on several tasks of that kind.
- **Tasks that separate versions** are the most informative; review the ones nobody solves for
  solvability, integration and fairness without treating zero solves alone as a defect.
- **Failure patterns**: which checks failed together. Read a few trajectories from each large
  group and quote where the agent went wrong. Record a pattern the trajectories support as a risk
  under the [discover skill](../../discover/SKILL.md)'s rules, citing the runs.
- **Measurement defects**: distinguish pre-existing environment or fixture failures from
  breakage introduced by the agent. Preserve original runs and scores, identify affected checks
  and claims, and follow the *Frozen tests* rule for repairs and comparable reruns. Do not count affected
  evidence as an agent failure or silently drop it from reported coverage; limit process
  judgments to what the trajectory supports ([process safety](checks.md#process-safety-shared-evaluator)).
  A repair that changes only grading is applied by re-grading the recorded diffs. A repair that
  changes anything the agent sees (the request, the workspace) sets aside every version's
  trials on that task, not only those that went wrong, and re-runs them all. A check that fails
  only while many trials share the machine (an integration suite under load) is a runner
  defect: re-grade it by replaying the diff on an idle machine.
- **Contamination**: report separately the tasks whose fix was public before a model's training
  cutoff.
- Cost (or plan usage) per solved task and time per trial go beside the scores; `summarize.py`
  prints both from the run records, with environment setup (which includes image builds) apart
  from the agent's time. State units and distinguish agent time from feedback overhead where
  measured. Preserve per-run setup/evaluator
  identity and available contents/revisions; do not infer a subscription bill from recorded USD
  or causation from a sequence of setup edits alone. Use the shared spending-visibility and
  missing-cost guidance in `relai/README.md`, *Counts come from records*.

## Comparing agents

Only when the user wants to compare different coding agents. Follow *Comparing agents* in
`relai/README.md`, which holds the rules shared with other agent-neutral tasks. For coding agents:

- **Instruction files in the workspace.** Coding agents read different instruction files (such as
  `CLAUDE.md` and `.claude/`, or `AGENTS.md`), and which ones depends on the agent and its version
  (*Setups*). Each task's README lists the agent instruction files its workspace already holds at
  the start commit; when they favor some agents, say so and offer a bare variant that removes
  them (*Setups*), or matched setups written as `[[coding_evals.setups]]` with `agent`.
- **Timeouts.** Use the agreed time budget for comparisons that measure speed; otherwise size
  `[agent].timeout_sec` using the slowest compared agent's measured trial (*Before any paid run*).

## Setups: does our setup help?

A frozen task holds no setup. `python3 relai/bin/apply_setup.py <setup id> <frozen tasks>` builds
a run copy of each task under `relai/work/setups/<setup id>-<digest>/`. The copy installs the
setup's workspace files with one added Dockerfile line and carries the trusted `setup_manifest`
and `tests/setup/` snapshots: installation is excluded, but later edits or deletion by the agent
remain visible in the diff and scope checks. The script also copies the setup's listed skills
there; pass each to the runner (Harbor: `--skill <dir>`,
[Harbor notes](../../eval/references/harbor-notes.md)). Run the copies in place of the tasks.

An edited setup gets a new digest and new copies. The tasks are not re-frozen or reviewed
again, because their request, checks and grading did not change. `summarize.py` pairs each
copy's results with the same test in the baseline and names the setup on each side. Keep the
copies while their runs support a claim: they are the record of what was measured.

An installed file replaces the start commit's file at the same path, but the old version stays
readable in git history. When that matters, or to measure the agent with no guidance at all,
build a bare variant: a separate task that removes the guidance from the workspace and from every
commit in its history (rewritten as in [task-format](task-format.md) step 2, its new start
recorded). It is built, validated, reviewed and frozen like any task, and setups can be applied
to it.

Before comparing, confirm from a trial that the agent loaded the setup's files and skills, and
that a bare variant loaded none: agents differ, and one may reach a file only through an import
or link. When the run record does not show which files loaded, check the agent's own log where
it keeps one (the [Harbor notes](../../eval/references/harbor-notes.md)). A setup the agent never
reads measures nothing. Run the same agent and attempts, and compare task by task.

Grade every setup of a task on the same criteria, settled before freezing (a later rubric change
follows the *Frozen tests* rule). The criteria are the team's approved requirements that apply to
the code at the task's start commit ([checks](checks.md#repository-requirements)), wherever they
are written. A requirement that one setup's instruction file states (run the linter) also grades
a run without it, since whether the file helps the agent meet it is what the comparison
measures. A rule that does not apply to the code at the start commit (one the start commit's own
guidance contradicts, or about code it does not have yet), or that the team did not approve as a
requirement, grades no setup. Report judge scores apart from the solved rate, and say that a
judge reading the trajectory may see which setup ran (the agent names or quotes its instruction
file). When an instruction file tells agents to stop or decline (for example, on
unsolicited contributions), report any stop as
its own finding.

Report per setup, beside the solved rate, the trajectory criteria for process requirements
(running the tests, linter or build), "not recorded" for runs without a run record. A task every
setup solves separates nothing on the solved rate. Fix the task set and attempts per task before
seeing the compared setups' results; if the results are too noisy to support a conclusion, add
the same attempts to every task and setup, and report that attempts were extended after seeing
results.

**Which parts help.** One setup per part left out (a section of an instruction file, a skill, a
hook, an MCP server). Trials grow as parts × tasks × attempts, so run it on the tasks that
separated setups before (a subset chosen from earlier results: report it as selection evidence,
as in *Improving a setup*), and show the cost first. Per part report helps, hurts, or no measurable
effect at this sample size.

## Improving a setup

With the [improve skill](../../improve/SKILL.md), the scope is `relai/setups/<id>/`: diagnose from development tasks'
trajectories, decide on held-out tasks when there are enough comparable tasks to hold some out
(otherwise decide on the development tasks and report the result as selection evidence,
`relai/README.md`, Terms). Measure each candidate by applying it to the frozen tasks; for files
in a candidate worktree, pass its `relai/` as `--setup-root`. Its rules apply unchanged.

## Maintenance

- Recheck affected [validation](task-format.md#validation) when a base image or dependency source
  may have moved; a task broken by an outside change is repaired under the *Frozen tests* rule, or
  retired as below.
- Add fresh tasks from recent work: newer fixes are less likely to be in training data.
- Retire a task (broken beyond repair, or no longer separating anything) only with the user's
  approval, recording the reason in `decisions.md` as the *Frozen tests* rule asks; its earlier
  scores stay recorded.
- When an agent or model version changes, rerun at the new version; never mix versions under
  one label.
