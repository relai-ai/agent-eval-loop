# Measure: run tests and report

Reuse an existing runner and evidence layout. Build missing capabilities only when the question
requires them ([harness](harness.md)). Paths and commands below describe RELAI-managed work;
use project equivalents when they preserve the needed evidence.

Goal: a clear, honest picture of how the agent behaves on the selected tests.

## Done when

- The selected tests ran under `relai/work/runs/<run-id>/` with the declared runner.
- Every judge evaluator was scored, with `relai/bin/judge.py <run dir>` in API mode or
  by fresh subagents as `relai/docs/files.md` describes in subagent mode, or you reported the blocker
  that prevented it.
- You reported `summarize.py <run dir>` with findings, evidence limits and links to detailed
  results, and updated `relai/STATUS.md`. The agent, tests and measurement logic did not change.

## Rules

- Pick the smallest selection that answers the question, and enough attempts per test to tell a
  real difference from noise when the result will be compared with another run. Never select the
  smoke test. Choose repetitions or adaptive effort for the uncertainty that matters. Reuse/cache
  deterministic work when it preserves the question being measured; caching stochastic agent or
  judge outputs changes sampling and must not masquerade as independent attempts.
- Use the declared runner; for Harbor, follow `relai/docs/harbor.md` and
  [harbor-notes](harbor-notes.md). Pass only required variables, and judge trials by their result
  files, never by exit status.
- Use a representative prior trial, or a pilot when needed, to estimate batch duration and cost.
- Never change the agent or the tests while measuring. If a test looks broken, say so; fixing it
  is Build mode's job and follows the *Frozen tests* rule.
- Report scored passes and failures, evaluator errors, runtime failures and unscored runs
  separately; an error or a failed trial is never scored as an agent failure, though when its
  permitted trajectory shows the agent's own code crashed, say so. For development failures,
  show representative evaluator feedback and the earliest relevant wrong turn from the trajectory.
  Group repeated failures by mechanism and link remaining cases. Do not fill gaps the trajectory
  does not show. For held-out or final evidence, report permitted assessment summaries; content
  inspection follows the [isolated review boundary](../../improve/references/review-change.md).
- Mention every test `summarize.py` reports as unfrozen or changed since frozen.

## Approach

### Deciding whether to run

A simulation is a targeted measurement, not a default step after every change.

- Reuse tests that already cover the behavior, preferring ones the change updated. Name the exact
  tests and attempts before running.
- Never fall back to the whole suite, a broad selection or unrelated tests because they are
  convenient.
- When no test covers the behavior, say so and recommend the next step: nothing, a wiki update,
  or a new test (the `eval` skill).

### Showing what happened

Lead with the answer or decision, its uncertainty and the next useful action. Add relevant coverage
and resource measurements, leaving optional future mechanics afterward. Group development failures
by mechanism and include representative permitted evidence and all
material new problems. Do not narrate every passing run or repeat the same failure walkthrough.
Use `summarize.py --details` to inspect complete tables; `--json <work-path>` retains the complete
summary, per-attempt evidence references and integrity warnings. Link those files and trajectories
for inspection. Use available per-run source, setup and evaluator identities, explicit resource
units and missing status reasons; a label without recoverable contents is only an assertion. Separate agent time
from feedback time when known, and do not equate recorded dollars with verified subscription
billing. Label partial runs and missing measurements explicitly; do not hide unfavorable
attempts or infrastructure problems behind an aggregate. The status board remains a detailed view.

### Outcomes beyond pass and fail

- A run with no scores and no evaluator errors has no verdict: point to the verifier's output in
  the trial and to the test's evaluators.
- A judge refused by its model provider (an invalid key, a spent budget or quota) blocks scoring;
  it is not an agent failure. Report the blocker and the runs it left unscored.

### Evaluator errors

Report each one with its message, and offer to fix it through [eval: shared-evaluators](shared-evaluators.md) as separate
work, since measuring changes no test. Once it is fixed, the recorded runs can be rescored instead
of rerunning the agent; never widen that rescore to a larger selection.

### Running in parallel

Score judges for finished trials while later trials run. Run tests one at a time when they share
an external dependency or mock state that cannot take concurrent calls.

### Choose measurement effort for the decision

You choose selections, repetitions and stopping criteria within the agreement. A narrow
deterministic fix, a stochastic behavioral gain and a resource optimization need different
evidence: identify the meaningful change, relevant distribution, guardrails and uncertainties
before spending, consider observed variation, consequences and budget, and record sampling
choices and revisions as evidence arrives.

Reuse a baseline only for comparable runs (`relai/README.md`, Terms), and record why;
re-baseline when comparability is uncertain, not merely because a new round began. When a commit
plus an unexplained dirty tree is all you have, recover its snapshot or rerun. When evidence is
inadequate or unrepresentative, say so rather than inventing a resolution.

`summarize.py` reports observations (Terms). Zero spread over identical scores is not certainty,
and unavailable estimates are null. `noise` and `se` are descriptive, not decision thresholds:
the per-test estimate assumes independent attempts, and the across-test one summarizes matched
deltas, not transfer to new tasks. There is no default confidence gate.

Collect more evidence when it could change the decision and fits authorization; stop when it is
not worthwhile or the agreed limit is reached; an inconclusive result is valid. Retain every
attempt, including infrastructure reruns, which also consume budget. When builds upstream of
scoring are stochastic, resample them, not only rescore one fixed artifact.

### Judge checks: does the judge score the way the user would?

After a test's judges first score real development trials, and again after any rubric change, add
judge checks per judge evaluator to `relai/feedback.md` (how many: Defaults): pick a high and a low score, quote the turn
the judge graded and its feedback, and recommend agree or disagree. Ask them at the end of that run,
while it is fresh, with the question tool (inside the `loop` skill, in the iteration's digest). A
judge the board flags for low agreement is repaired ([shared-evaluators](shared-evaluators.md)) and its
runs rescored, not trusted.

For protected-only runs, do not open trajectories or copy their feedback into optimizer-visible
judge checks. If content inspection is needed, use the existing isolated reviewer procedure and
return only permitted assessment outcomes and limitations. Report any uncompleted calibration;
neither create another split automatically nor imply those contents were checked by the optimizer.

### The pass mark

While `[scoring].pass_mark` is unset, report means without pass or fail. After the first run
that scores real trials, ask for it alongside that run's judge checks: explain the pass rule
(`relai/docs/files.md`), show each test's mean and the spread of its attempts, and recommend a
value from those scores and what the results will decide, saying which tests it would pass and
fail today. There is no default, so never present a number as one. Write the answer to
`relai.toml` and `decisions.md`. Changing it later changes every pass and fail on the board, so
ask again only when the user raises it.
