---
name: improve
description: Fix or improve an AI agent or LLM application, compare prompts, models or settings, reduce cost or latency, or check changes for regressions. Excludes ordinary bugs outside an AI agent. Use eval for measurement alone and loop for continuous learning from new evidence.
---

# Improve the agent

Goal: a verified improvement against the agreed objective with its guardrails held, or a clear
account of why no change was kept.

## Choose the verification path first

Apply the shared [purpose guidance](../start/template/README.md#establish-the-purpose) to the
requested outcome before choosing verification or optimization. For measured work, connect the
objective and guardrails to the relevant case distribution and outcome priorities. A clear
deterministic fix needs no unrelated evaluation questionnaire.

- **Direct deterministic fix:** repository tests can reproduce and verify a code defect or missing
  deterministic capability. Use relevant project checks and existing agent evals when needed. No
  harness, frozen suite or optimization loop is required for this path. Review the diff
  proportionally. A unit test of prompt loading does not prove better agent behavior.
- **Measured improvement:** claims about agent performance need comparable behavioral evidence.
  Inspect existing runners, tests and results first. Read `relai/README.md`, or the bundled
  [terms](../start/template/README.md#terms) when absent. Use the [start skill](../start/SKILL.md)
  only when you need RELAI's managed records or checkers, and the [eval skill](../eval/SKILL.md)
  only for missing measurement capabilities or coverage. Reuse working project infrastructure.
  Follow [improve-loop](references/improve-loop.md) for focused analysis batches, repeated synthesis and
  staged behavioral experiments; choose their size, concurrency and timing within the agreement.
  Use [cost-latency](references/cost-latency.md) for a cost or latency objective.
- **Check a change:** use the relevant available checks and state uncovered behavior. For an
  existing agent suite, follow [regression](references/regression.md); do not build unrelated infrastructure.

An existing-results assessment may finish with a recommendation and evidence limits, without a
candidate or new run. Read only the guidance needed for that assessment; do not start an experiment
merely to complete the flow. Across all paths, maintain useful knowledge under the
[shared policy](../start/template/README.md#maintain-useful-knowledge), respecting read-only work.

## Establish the improvement agreement

Reuse existing instructions or a loop contract that cover the agreement (`relai/README.md`,
Terms). Apply the shared purpose guidance and
[resource policy](../start/template/README.md#resources-and-expectations) to distinguish user
authorization from your experimental plan. Build and revise the plan yourself within the agreement;
ask only about uncovered intent, authorization, conflicts or changes to its boundaries. Establish
these from the request and project evidence before dependent work:

- **Objective and guardrails:** the intended outcome, decision metric and applicable bounds.
  Unrelated issue-specific tests are guardrails, not targets. Clarify conflicting priorities
  rather than inventing a weighted objective or an improvement threshold the user did not request.
- **Scope:** the allowed agent files, model/settings changes, supporting work and off-limits surfaces.
- **Resources:** applicable allowances, limits and their coverage. Ask for a missing limit when
  paid execution or the integration requires it; do not require every kind of cap for every task.
- **Evidence and delivery:** record your provisional measurement and verification approach
  ([eval: measure](../eval/references/measure.md)) under the shared policy. Reuse covered expectations
  and check-ins. Use a branch or worktree for review by default, or the user's working tree if
  already authorized. Preserve explicit user limits and requirements while adapting the approach.

For managed measured work, record the agreement in `relai/records/improve/plan.json` (`relai/docs/files.md`),
or use the covering loop contract. Existing project records may serve the same purpose when they
preserve the agreement and evidence. Record consequential user choices alongside that agreement.
Tell the user when the authorized budget is exhausted, and ask before exceeding it.

In an eval project for coding agents, the thing improved is a team's setup (`relai/setups/<id>/`:
instruction files, skills, hooks) rather than code in this repository: the scope is those files,
each candidate is measured as a variant of the frozen tasks
([comparing](../coding-evals/references/comparing.md)), and everything below applies unchanged.
With agent-neutral tests that several agents run, improve one agent at a time: its setup files,
or its code when this repository develops it. The other agents' scores are context for the
report, never targets ([agent-neutral](../eval/references/agent-neutral.md)).

## Done when

- Direct fix: the correction has relevant repository evidence and a proportional diff review, and
  you reported the verified behavior, checks, delivery location and remaining uncertainty.
- Regression check: you reported relevant before/after evidence, regressions and uncovered
  behavior, or explained a missing test or baseline rather than implying complete coverage.
- Measured work:
  - Comparisons use comparable baseline and candidate runs; test selections and sampling, including baseline
    reuse, differing counts and unmatched cases, are recorded. Candidates stay within the agreed
    scope; changes to supporting tooling follow the shared
    [adaptation policy](../start/template/README.md#adapting-supplied-implementations), preserving
    measurement meaning or restoring comparable evidence before claiming improvement.
  - Accept an improvement only when evidence supports meaningful improvement within the claimed
    scope, the agreed guardrails hold within their bounds with supporting evidence, and the
    predicted mechanism is exercised. Material unmeasured risks can block acceptance; disclosed
    gaps do not establish that guardrails hold.
  - A kept improvement has a fresh review ([review-change](references/review-change.md)) of the delivered diff and its evidence that found
    nothing blocking. Any later change to the delivered revision is reviewed again.
  - Every attempted change is recorded in `relai/changes.md` or the project's equivalent history;
    update `relai/STATUS.md` when using managed state. You reported the objective, before/after evidence, remaining failures, candidates tried, selection
    basis, spend, delivery location and evidence limits, or why no change survived.
  - When the agreement is exploration only, report what was learned and what would need further
    verification without claiming an accepted improvement. Preserve the incumbent when acceptance
    is not established; promising candidates can remain available for follow-up.

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
- Stop optimizing against a suspected bad test and investigate through the `eval` skill separately
  ([criterion sources and conflicts](../eval/references/test-design.md#checking-compatible-criteria)).
  Preserve raw scores and the evidence for disagreement, including defects missed by favorable
  grades. When repair is outside scope, pause affected optimization and continue unaffected work
  only where the original objective and guardrails remain assessable. Ask when the disagreement
  changes the acceptance decision; do not silently drop criteria or revise the selection rule.
  Authorized repairs follow the *Frozen tests* rule (`relai/README.md`; `freeze.py --begin-repair`
  once agreed), with comparable measurements restored before reuse. A score alone does not
  establish a test defect. No change kept is a valid result.

## Choosing among candidates

For several alternatives, follow [candidate-selection](references/candidate-selection.md). When what to investigate
next is unclear, [prioritization](references/prioritization.md) offers an optional suggestion.
