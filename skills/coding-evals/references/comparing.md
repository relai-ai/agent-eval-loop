# Running: the baseline, then changes, setups and agents

## Before any paid run

Every task is frozen and healthy. Measure one trial per version run (its cost, or with a
subscription its plan usage and time); it also shows that the agent installs, reaches its model
and does work, so a trial with no model calls is fixed before any larger run. Then follow "Cost before spend" in `relai/README.md`.
Choose attempts for the decision, observed variability and budget; coding agents can vary between
runs. Reuse deterministic work only when it preserves the uncertainty being measured.

**Agent timeout.** Set `[agent].timeout_sec` at build for an agent doing the work, never from
the reference fix, which runs instantly. When the measured trial of any version runs near it,
raise it under the freeze rule before the run counts.

## Running

The first run measures the agent as the team uses it now: the baseline. On its own it says how the
agent does on the team's work and what it gets wrong, and later runs reuse it. When the user asks,
compare one change against it: a model, a version, or a setup variant (below). Comparing other
agents works the same way, with the extra care in *Comparing agents* below. Run each
version as `relai/docs/harbor.md` describes, with `-a <agent> -m <model>`, the agent's recorded
version (the [Harbor notes](../../eval/references/harbor-notes.md) say how), its credential, each
task's network setting, and each version's runs in their own directory under `relai/work/runs/`.
Score the judges, then `summarize.py` each run; when comparing, pass the baseline with `--baseline`.

## Reading the results

- **Solved** is the primary evaluator at full marks (its per-attempt scores in
  `summarize.py --json`), per task, averaged over attempts; the mean over every recorded check
  goes beside it, and the pass rule once `[scoring].pass_mark` is set. An agent can solve more and pass less (it fixes the bug but
  edits tests or skips verification). Show scored/attempted counts and missing-result reasons;
  unknown scores are not failures. Rerun missing evidence when useful and authorized, or limit
  the conclusion to what was recorded.
- **Paired, task by task**, when comparing. Compare the same tasks for both sides. A difference within the run's
  spread, or on few tasks, supports no claim either way.
- **Per check**: how often each behavior held. Checks with errors were not recorded for that
  agent.
- **By kind of work**: suggest routing only when a difference holds on several tasks of that kind.
- **Tasks that separate versions** are the most informative; review the ones nobody solves for
  fairness.
- **Failure patterns**: which checks failed together. Read a few trajectories from each large
  group and quote where the agent went wrong. Record a pattern the trajectories support as a risk
  under the [discover skill](../../discover/SKILL.md)'s rules, citing the runs.
- **Measurement defects**: distinguish pre-existing environment or fixture failures from
  breakage introduced by the agent. Preserve original runs and scores, identify affected checks
  and claims, and follow the freeze rule for repairs and comparable reruns. Do not count affected
  evidence as an agent failure or silently drop it from reported coverage; limit process
  judgments to what the trajectory supports ([safe process](checks.md#safe-process-shared-evaluator)).
- **Contamination**: report separately the tasks whose fix was public before a model's training
  cutoff.
- Cost (or plan usage) per solved task and time per trial go beside the scores. State units and
  distinguish agent time from feedback overhead where measured. Preserve per-run setup/evaluator
  identity and available contents/revisions; do not infer a subscription bill from recorded USD
  or causation from a sequence of setup edits alone.

## Comparing agents

Only when the user wants to compare different coding agents. The tasks need no change; what
differs between agents is what they read, what is recorded and what they cost.

- **What each agent reads.** Agents read different instruction files (Claude Code `CLAUDE.md` and
  `.claude/`, Codex and many others `AGENTS.md`). Each task's README lists the agent instruction
  files its workspace already holds at the start commit; when they favor some agents, say so and
  offer a bare variant that removes them, or matched setups. Compare either bare against bare, or
  each agent with its **matched setup**: the same team guidance written into each agent's own
  files (`[[coding_evals.setups]]` with `agent`). Never one agent's setup against another bare.
- **Same conditions.** The same frozen tasks, attempts, network setting and web-tool setting for
  every agent, with `[agent].timeout_sec` covering the slowest compared agent's normal runs
  (*Before any paid run*); a timed-out run is graded and counts as that agent's result, so report
  timeouts per agent.
- **A fair basis.** The headline is the primary check's solved rate, which every agent and the
  oracle are scored on. Beside it, compare only the checks recorded for every agent compared, and
  show each agent's recording coverage: a judge that reads the run record is "not recorded" for an
  agent Harbor records without one, so the pass rule over all checks covers different checks per
  agent.
- **Cost in one unit.** Report tokens and time per trial and per solved task; dollars only when
  every compared agent pays per token.
- **Paired against a baseline.** Pick one agent as the baseline and compare each other agent with
  it task by task (`summarize.py --baseline`); report the agents side by side from those runs.

## Setups: does our setup help?

A variant copies a task and installs its setup on top of the start commit in its Dockerfile, with
`setup_files` in `params.json` listing the installed files. Before the first run/freeze, capture
the installed pre-agent state with `python3 <task>/tests/coding_checks.py setup <installed-workspace>
<task>` (use absolute paths or state their base). This writes the trusted `setup_manifest` in
`tests/params.json` and snapshots under `tests/setup/`; installation is excluded, but later edits
or deletion by the agent remain visible in the diff and scope checks. Missing baseline evidence
is a task error, not permission to ignore those files.

The task request, grading logic, checks and all unrelated `tests/` content stay identical; only
the setup declaration/manifest and its snapshot differ as intended. A bare variant installs no
setup; when the start commit already holds guidance, the variant also removes it from the
workspace and from every commit in its history (rewritten as in [task-format](task-format.md)
step 2, its new start recorded), since the agent can read it from git. Before running a variant,
confirm from the agent version's documentation or a trial's trajectory that it loads the
variant's files: agents differ, and one that reads only its own file (such as `CLAUDE.md`) reaches
`AGENTS.md` or shared skills only through an import or link. A variant the agent never reads
measures nothing. Check these differences before comparing, run the same agent and attempts, and compare
task by task. Adopting this verifier for frozen tasks follows the freeze rule; do not silently
rewrite user-owned copies or mix earlier scores with changed measurement.

**Which parts help.** One variant per part left out (a section of an instruction file, a skill, a
hook, an MCP server). Trials grow as parts × tasks × attempts, so run it on the tasks that
separated setups before, and show the cost first. Per part report helps, hurts, or no measurable
effect at this sample size.

## Improving a setup

With the [improve skill](../../improve/SKILL.md), the scope is `relai/setups/<id>/`: diagnose from development tasks'
trajectories, decide on held-out tasks, and measure each candidate as a variant. Its rules apply
unchanged.

## Maintenance

- Recheck affected [validation](task-format.md#validation) when a base image or dependency source
  may have moved; a task broken by an outside change is repaired or retired under the freeze rule.
- Add fresh tasks from recent work: newer fixes are less likely to be in training data.
- Retire tasks that no longer separate anything only with the user's approval.
- When an agent or model version changes, rerun at the new version; never mix versions under
  one label.
