---
name: improve
description: Use to fix the AI agent's code, improve the agent (or LLM app, chatbot or pipeline) against its evaluations, compare prompts, models or settings for it, reduce its cost or latency while preserving behavior, or check a change to it for regressions ("fix this crash in the agent", "make the agent pass X", "compare these two prompts for the agent", "does this change help the agent", "make it cheaper", "did this change break the agent"). Not for general code bugs outside an AI agent. For an ongoing loop that also learns from new traces, use the loop skill. To only run evaluations, use the eval skill.
---

# Improve the agent

Goal: a verified improvement against the agreed objective with its guardrails held, or a clear
account of why no change was kept.

## Choose the verification path first

- **Direct deterministic fix:** repository tests can reproduce and verify a code defect or missing
  deterministic capability. Use relevant project checks and existing agent evals when needed. No
  harness, frozen suite or optimization loop is required for this path. Review the diff
  proportionally. A unit test of prompt loading does not prove better agent behavior.
- **Measured improvement:** claims about agent performance need comparable behavioral evidence.
  Inspect existing runners, tests and results first. Read `relai/README.md`, or the bundled
  [terms](../start/template/README.md#terms) when absent. Use the [start skill](../start/SKILL.md)
  only when you need RELAI's managed records or checkers, and the [eval skill](../eval/SKILL.md)
  only for missing measurement capabilities or coverage. Reuse working project infrastructure.
  Follow [improve-loop](references/improve-loop.md), and [cost-latency](references/cost-latency.md) for a cost or latency
  objective.
- **Check a change:** use the relevant available checks and state uncovered behavior. For an
  existing agent suite, follow [regression](references/regression.md); do not build unrelated infrastructure.

An existing-results assessment may finish with a recommendation and evidence limits, without a
candidate or new run. Read only the guidance needed for that assessment; do not start an experiment
merely to complete the flow. Across all paths, maintain useful knowledge under the
[shared policy](../start/template/README.md#maintain-useful-knowledge), respecting read-only work.

## Establish the improvement agreement

Reuse existing instructions or a loop contract that cover the agreement (`relai/README.md`,
Terms). Ask only for missing consequential choices, conflicts, or work outside it. For a new
measured-improvement agreement, settle before editing:

- **Objective and guardrails:** behavioral success, lower cost, or lower latency; the targeted
  tests and measures; the required improvement and the guardrails' bounds. Unrelated
  issue-specific tests are guardrails, not targets. Do not invent a weighted objective for
  conflicting goals.
- **Scope:** allowed agent files, model and settings changes, any supporting process improvements,
  and off-limits surfaces.
- **Budget and evidence:** the decision to support, the relevant task distribution, measurement
  effort and estimated spend ([eval: measure](../eval/references/measure.md)). No universal repetition
  count applies.
- **Check-ins and delivery:** rounds or stopping rule; a branch or worktree for review by
  default, or the user's working tree if already authorized.

For managed measured work, record the agreement in `relai/records/improve/plan.json` (`relai/docs/files.md`),
or use the covering loop contract. Existing project records may serve the same purpose when they
preserve the agreement and evidence. Record consequential user choices alongside that agreement.
Tell the user when the authorized budget is exhausted, and ask before exceeding it.

In an eval project for coding agents, the thing improved is a team's setup (`relai/setups/<id>/`:
instruction files, skills, hooks) rather than code in this repository: the scope is those files,
each candidate is measured as a variant of the frozen tasks
([comparing](../coding-evals/references/comparing.md)), and everything below applies unchanged.

## Done when

- Direct fix: the correction has relevant repository evidence and a proportional diff review, and
  you reported the verified behavior, checks, delivery location and remaining uncertainty.
- Regression check: you reported relevant before/after evidence, regressions and uncovered
  behavior, or explained a missing test or baseline rather than implying complete coverage.
- Measured improvement:
  - Baseline and candidate runs are comparable; test selections and sampling, including baseline
    reuse, differing counts and unmatched cases, are recorded. Candidates stay within the agreed
    scope; changes to supporting tooling follow the shared
    [adaptation policy](../start/template/README.md#adapting-supplied-implementations), preserving
    measurement meaning or restoring comparable evidence before claiming improvement.
  - Evidence supports meaningful improvement on the objective, guardrails hold, and the predicted
    mechanism is exercised.
  - A fresh review ([review-change](references/review-change.md)) of the delivered diff and its evidence found
    nothing blocking. Any later change to the delivered revision is reviewed again.
  - Every attempted change is recorded in `relai/changes.md` or the project's equivalent history;
    update `relai/STATUS.md` when using managed state. You reported the objective, before/after evidence, remaining failures, candidates tried, selection
    basis, spend, delivery location and evidence limits, or why no change survived.

## Shared rules

Use the evidence appropriate to the selected path: repository tests and error reports can establish
a deterministic fix; claims about agent performance need behavioral measurements. Adapt the
suggested methods to the request while preserving authorization and honest evidence.

- Confirm changed mechanisms are loaded on the real product path. Check opposite-direction
  behavior, newly exposed downstream behavior, and other users of shared code or instructions;
  otherwise scope the change and conclusion to the behavior actually tested.
- A crash in the agent's own code is a defect you may fix within scope. Distinguish it from failures
  of the measurement infrastructure.
- Consider better observability, evaluation signals or faster feedback when they materially help
  the requested outcome. The skill grants no additional authorization: proceed with covered
  implementation work, but explain the benefit, effort and tradeoffs and ask before broadening the
  assignment or resolving an uncovered consequential choice. Keep unrelated ideas as follow-ups.
  A faster feedback runner is not evidence of a faster agent; separate the claims.

## Additional rules for measured improvement

- Diagnose from development trajectories only (`relai/README.md`, Terms). On a benchmark, record
  runs with `benchmark.py record`.
- Choose the next useful experiment yourself and state its purpose and attribution limits. No
  test inputs, expected answers, evaluator wording or case-specific bypasses in the agent;
  general in-scope capabilities are legitimate ([improve-loop](references/improve-loop.md), Authenticity).
- Separate runtime failures and evaluator errors from behavioral scores; investigate and rerun
  missing evidence when useful and authorized; otherwise report the limits rather than implying
  the missing evidence supports a conclusion. Summarizer notices inform this judgment; successful
  execution of a comparison does not establish comparability.
- Stop optimizing against a suspected bad test; investigate it through the `eval` skill separately,
  record justified repairs under the *Frozen tests* rule (`relai/README.md`; `freeze.py
  --begin-repair` once the repair is agreed) and establish comparable measurements before resuming. A low score
  alone does not establish a test defect. No change kept is a valid result.

## Choosing among candidates

For several alternatives, follow [candidate-selection](references/candidate-selection.md). When what to investigate
next is unclear, [prioritization](references/prioritization.md) offers an optional suggestion.
