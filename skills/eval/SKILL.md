---
name: eval
description: Use to build and run evals for the AI agent in this repository - the harness that runs the real agent (first time), hard realistic tests from risks, requirements, failed runs or traces, harder or combined tests, benchmarks, and shared evaluators ("create evals", "turn this failure into a test", "set up the harness", "bring in this benchmark"); or to run them and report where the agent stands ("run the evals", "get a baseline"). Also to fix a test or evaluator that errors or cannot fail, or to mock a dependency trials cannot reach. For agent-neutral coding tasks from sessions or PRs, use the coding-evals skill, including for a custom coding agent developed in this repository.
---

# Build and run evals

Inspect existing tests, runners and results first. Read the relevant terms and guarantees in
`relai/README.md`, or the bundled [contract](../start/template/README.md#terms) when absent.
Use the [start skill](../start/SKILL.md)
when RELAI's managed artifacts are needed, not to replace working evaluation infrastructure.
Choose the mode for the request; the methods below are starting points, not a required full journey.
For unsuitable or failing supplied code, use the shared
[adaptation guidance](../start/template/README.md#adapting-supplied-implementations).

Goal: each important behavior has a test that fails when the agent lacks it and passes when it
has it, runs the real agent the way users do, and was reviewed and frozen before its first run;
and the user has honest numbers on how the agent does on those tests.

Across Build and Run, maintain knowledge for future usefulness under the
[shared policy](../start/template/README.md#maintain-useful-knowledge), respecting read-only work.
Useful discoveries can update existing records without reproducing a wiki or board checklist.

## Pick the mode

- **Build** (default when the behavior has no test yet) - the harness on first use, then new or
  harder tests, with scenario approval and grader preview below.
- **Run** - run selected frozen tests, score them and report where the agent stands
  ([measure](references/measure.md); its *Done when* applies). On a benchmark, follow
  [benchmarks](references/benchmarks.md). To compare runs before and after a change, use the `improve` skill.

## Done when (build)

The outcomes below apply to the selected tests. The listed paths and commands are the
RELAI-managed implementation; a working project suite can meet the same guarantees through its
own task definitions, grading checks, reviewed test version, run records and reporting. Record
the guarantees they provide: faithful execution, graders checked against meaningful pass/fail
examples, a recoverable reviewed test version before real trials, and traceable results. RELAI
filenames are not required.

- **Harness ready** (first time only, [harness](references/harness.md); not needed when the only tests are
  a wrapped benchmark, whose own runner runs the agent).
- **Scenarios approved:** the user, or an independent reviewer when the approval is delegated
  (by an agreement or a recorded choice in `decisions.md`),
  approved the scenario table below.
- Each test is a task under `relai/tests/<id>/` (or a benchmark row) meeting
  `relai/docs/files.md`, with a `README.md` stating behavior, scenario, risk probed and each
  evaluator; `check_task.py` passes, plus `--verifier` for Harbor or synthetic
  passing/failing/empty grading checks for a native runner; with API judges, every judge is shown
  able to fail (`relai/bin/judge.py --self-test`, or a synthetic violating trajectory for a
  prohibition judge).
- **Graders previewed:** the user, or the delegated independent reviewer, approved the preview below.
- A fresh test review ([review-test](references/review-test.md)) approved each test; `freeze.py` ran before its
  first real trial; one real trial per test scored every evaluator without an error.
- You showed the results (representative development failures with relevant trajectory evidence;
  protected evidence only through permitted assessment summaries), added and asked judge checks
  for each new judge evaluator using the protected-evidence boundary in
  [measure](references/measure.md#judge-checks-does-the-judge-score-the-way-the-user-would) and, when
  `[scoring].pass_mark` is unset, the pass mark ([measure](references/measure.md)), recorded each probe on
  its risk page when useful, and updated relevant knowledge or state for future work.

## Rules

- One test per behavior. Extend an existing test rather than near-duplicating it; a frozen test
  changes only under the *Frozen tests* rule.
- Hard but realistic: real data instances, the ambiguity and competing cues that make the
  behavior hard, a simulated user whose instructions hold only the user's goal and knowledge.
  Never put the answer, a diagnosis or a hint in the agent's input.
- Exact criteria are code, meaning is a judge, each criterion its own evaluator; expected values
  live in `tests/params.json`, not in evaluator code ([test-design](references/test-design.md)).
- **Both directions.** For any behavior an improvement could overcorrect (escalating, refusing,
  asking, searching, calling a tool), also test a case where doing it is right, so an agent
  that never does it cannot pass.
- **Split.** Development is the default; held-out tests are optional (`relai/README.md`, Terms).
  Recommend one only when comparable cases and task distribution make it meaningful, not from the
  count alone: many unique, issue-specific tests are not a useful random split.
- A failure caused by the trial itself (a refused action, a broken harness, a killed container)
  is inconclusive, not evidence about the agent; fix the probe.
- **Where tests come from**, in this order: runs the user's feedback judged wrong (replay the run,
  [test-design](references/test-design.md)); admitted risks, highest first; coverage gaps and co-occurring
  weak signals from a triage (`relai/work/discover/<ingest-id>/lanes.json`); requirements no test
  covers; and harder or combined versions of passing tests ([hardening](references/hardening.md), always as
  new tests).
- Specialized cases: a benchmark ([benchmarks](references/benchmarks.md)), a criterion shared across tests or
  an evaluator to repair ([shared-evaluators](references/shared-evaluators.md)), a dependency trials cannot reach or
  must not call ([mocks](references/mocks.md)).

## Ask the user

The user is asked at up to three points in a build: once at the start, at scenario approval and
at the grader preview (or once for both, when the user chose one sitting below). Skip any
question that the request, `relai/decisions.md`, the wiki or an agreement already answers. At the
start, ask together only what is still open:

- **Where to start**, only when the wiki has no open risks and the request names no behavior,
  run or benchmark: run the `discover` skill first (recommend this, more strongly when traces of
  real runs exist), build from risks read in the code now ([test-design](references/test-design.md),
  *Hard cases*), or test one behavior the user names.
- **What the results will decide**, when not evident: catching regressions before merge, gating
  a release, comparing models or prompts, or seeing where the agent stands. It sets the split
  recommendation, attempts and spend.
- On first use, the harness questions still open ([harness](references/harness.md), *Ask the user*).
- **How involved to be**, when nothing says
  ([delegated approvals](../start/template/README.md#working-with-the-user)): approve the
  scenarios and grader preview yourself (recommended for the first build), or delegate both to a
  fresh independent review and see the results with the build's report. For a build of one or two
  tests, the user may also choose one sitting: build first (building runs no agent), then show the
  scenario with its grader preview together. Record the choice in `decisions.md`.

Name any missing credential variable and the project's credential mechanism (or `relai/.env`)
as an instruction, not a question. Reuse existing setup and continue work that does not need it.

## Approve the scenarios

Unless the approval is delegated or the user chose one sitting, wait for a yes before building. Write each proposed
test's full design to `relai/records/eval/<date>-scenarios.md` ([test-design](references/test-design.md),
*Proposing a test*). In chat, show one compact table, in the order you recommend building: the
behavior, its source, the scenario in one line naming the real data and the trigger that makes
it hard, what failing looks like, and its opposite-direction partner, if any. Below it, give the
cost and time of one trial per test plus judging, in total; a yes approves that as this build's
budget, and you ask again only before exceeding it. Ask which tests to build: all, only
the first few, or change the list.

## Preview the graders before freezing

Freezing stops anyone tuning a test to the agent's results, so preview without running the agent:
score each test's evaluators on synthetic trajectories (a passing one, a failing one that commits
the risk's observable failure, an empty reply) and on any real recorded traces that fit the
scenario. Write every test's full table (evaluator × case → score and the first line of
feedback) to `relai/records/eval/<date>-grader-preview.md`. Size chat previews by the shared
[decision-effort rule](../start/template/README.md#working-with-the-user), reviewing manageable
subsets when needed while keeping the complete artifact and pending decisions visible. For the
subset being approved, show every judge evaluator's rows and every score that differs from what
its case should get (a failing case not scored low,
a passing one below full marks, a missing required deliverable above the minimum; see
[test-design](references/test-design.md#rules), *Missing deliverables and prohibitions*). For a
pure prohibition, preview an actual violation to show that check can fail.
Summarize the rest per test in
one line, such as "4 code checks scored as expected". Ask whether the current subset needs scoring
changes or is missing anything the user cares about; separate independent choices as the shared
guidance describes. Iterate until the answer is no, then review and freeze. When this decision
is delegated, the fresh test review stands in for the user. Build/freeze only the subset whose required decisions
are resolved; do not treat partial review as approval of the remaining tests.

## Approach

- Start from admitted risks, highest impact first, then requirements no test covers. With no
  risks, follow the user's answer to *Where to start*. For each test, write down the trigger,
  passing, failing and what would make the probe invalid before building.
- Prefer the agent's real configuration, real data and real user simulator. Grade outcomes from
  exported state (database changes, files, mock journals) with code; keep judges for meaning.
