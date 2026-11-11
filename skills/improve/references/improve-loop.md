# The improvement loop

Use for measured improvement under the `improve` skill or the experiment stage of the `loop` skill.
The main skill's agreement, scope and completion criteria bind. Paths below are defaults for
RELAI-managed work; existing project records and runner layouts can supply the same evidence
without new infrastructure. The flow below is adaptable;
its purpose is to choose useful experiments and reach defensible decisions within that agreement.

## Protect the incumbent and keep evidence recoverable

Keep an incumbent: the last accepted version, initially the user's code. Explore in isolated
branches or worktrees under `relai/work/candidates/<name>/`, measuring into their `runs/` folders.
`relai/work/runs/` holds measurements of the user's checkout only. Measure another checkout as
`relai/README.md`'s host notes describe.

Keep the agreement, active work and lessons under `work/improve/`, and candidate decisions in
`changes.md` (`relai/docs/files.md`).

## Choose the next useful experiment

Start with the objective, scope, existing evidence and unresolved questions. Diagnosis may precede
new runs. A round may investigate failures, test wiring, collect evidence, compare alternatives,
apply a coherent fix, or try a justified bundle. It need not produce a patch. Explain the question,
expected learning or benefit, evidence needed, and spend before expensive work.

Distinguish three selections, which may overlap and need not be small or equal in size:

- **Investigation cases:** development evidence needed to understand a mechanism or coverage gap.
- **Candidate measurements:** cases and repetitions needed to evaluate the experiment's objective.
- **Regression checks:** behavior the change could harm, chosen from scope, shared dependencies,
  opposite-direction cases and newly exposed downstream paths.

Let the coding agent choose the selections, repetitions and order. Multiple cases in one group
can establish a shared mechanism; broad coverage can be appropriate for many independent gaps.
Use the agreement, relevance, risk, uncertainty, dependencies and expected learning to focus work.
Improving feedback or diagnostics can be the useful experiment; follow the main skill's scope and
authorization rule rather than turning a narrow request into a tooling project. Useful signals
might be decision reasons, missing measurements or time spent obtaining feedback; use existing
hooks and record only what helps the decision.

For a deterministic fix, use the direct-fix path in the main skill without new eval infrastructure.
For several alternatives, follow [candidate-selection](candidate-selection.md). A bundled experiment needs a rationale,
a reversible diff and an account of attribution limits: a bundle's success does not prove each
component helped. Use isolation or ablation when attribution matters.

Delegate analysis when independent investigation or context management warrants it, not because
of a trajectory count. Give an analyzer only permitted development evidence and scope.
Independent review of the delivered measured improvement remains required.

When what to investigate next is unclear, [prioritization](prioritization.md) offers optional suggestions; they
never set selection, batch size, evidence, budget or acceptance. On a benchmark, record the exact
development selection with `benchmark.py batch <id> --case-ids ...`.

## Establish comparable evidence

Reuse baselines and choose measurement effort as [eval: measure](../../eval/references/measure.md)
describes, recording sampling choices and reuse. Rejected candidate scores are diagnostics, not
incumbent measurements. Justify any acceptance against the objective and guardrails yourself;
the summarizer only describes observations.

Use relevant existing wiring and grader checks; investigate an implausible gain or disconnected
mechanism before spending on more candidates. For configuration changes or expensive passes,
a cheap premise probe can establish that the setting is accepted and the resolved scope matches
what was authorized. Reuse adequate prior checks.

## Diagnosing and proposing changes

Weigh evidence in this order: these rules and the user's scope; the current run's trajectories,
feedback and what the tests intend; your structure and failure analysis; the notes from earlier
rounds; then inference to fill gaps. When notes conflict with current evidence, say so and follow
the evidence.

1. **Structure.** From the real code, establish what the agent is for, the path the relevant
   tests exercise, where the agent's core ends and the harness, mocks and simulated users
   begin, the files where a real improvement would be used, and any wrapper that could bypass the
   agent's reasoning. A wrapper on the path is not necessarily the cause of a wrong answer.
2. **Failures.** Group the relevant failures by mechanism. Separate configuration or runtime
   blockers from poor behavior, and a wrong answer from a right answer that never reached the
   output. Do not conclude a credential is missing from documentation alone. Keep what the runs
   show apart from what you infer.
3. **Intent.** For each test, state what it literally checks, the broader user scenario it stands
   for, and the capability that is legitimately in scope for this agent. The test input is a
   probe, not the objective; aim at the scenario.
4. **Alternatives.** Consider changes across the surfaces that shape behavior: context and memory,
   tools and what they return, the reasoning workflow, the model and generation settings (only if
   allowed), capabilities and skills, the output contract, and runtime reliability. For each,
   consider adding or strengthening, revising or retargeting, disabling or removing, or replacing
   a mechanism. Compare a prompt or configuration change, a capability added on the normal path,
   and a structural fix. If a gentle nudge would be too weak, consider a stronger in-scope change
   instead of giving up.
5. **Authenticity.** Keep a capability only if it is on the normal path, reusable beyond the
   literal probe, authorized in cost and scope, and something a product owner would want with the
   tests out of view. General parsers, handlers and deterministic capabilities can be legitimate
   even before model reasoning. Reject case-specific bypasses and embedded evaluation answers;
   when rejecting an in-path capability, say which criterion failed.
6. **Choose** an appropriate mechanism the real path will use, and write the plan:
   - the diagnosis, and which tests it targets and which it defers;
   - the files to change and the steps;
   - how the change becomes active (construction, registration, prompt assembly, caches, memory
     loading) and what in a trajectory will show it was used;
   - the conditions under which the plan is wrong and editing should stop;
   - for a risky change, a narrow way to switch it off.

For a cost or latency objective, follow [cost-latency](cost-latency.md).

## Execute and assess

- Before editing, confirm the proposal fits scope and will be active on the real path. Revise the
  plan when its assumptions fail. Keep the diff proportional to the mechanism; remove vague or
  redundant instructions rather than accumulating advice with no operational effect.
- Run the selected experiment through the declared runner. Diagnostic interventions stay isolated
  from the accepted incumbent; they are evidence-gathering work, not shipped improvements.
- Read relevant development trajectories and artifacts alongside descriptive measurements.
  Distinguish whether the mechanism engaged from whether it helped. Confirm a mechanism only
  when the proposal, diff, exercised path and evidence support it; otherwise state the uncertainty.
- **Acceptance.** Accept a candidate only when evidence supports the objective, the guardrails
  hold, the predicted mechanism was exercised, and the fresh review of the delivered diff found
  nothing blocking. Lower cost or latency with preserved behavior qualifies.
- A justified bundle is accepted or rejected at its measured scope. Do not claim component-level
  contributions without evidence. Preserve the previous incumbent when evidence is inconclusive.
- A miswired or incomplete implementation does not disprove the underlying mechanism.
- Choose additional measurements or checks when they could affect the decision and fit the budget.
  Use [regression](regression.md) for guardrails. For benchmarks, preserve the commit and supplied splits and
  record runs.
- Verify the delivered revision with coverage justified by its reach, risks and intended claims.
  Broad shared changes may warrant broad suites; a narrow fix need not run every frozen test.
  Disclose gaps. Review the delivered diff again after any rollback.

## Record, learn and decide what comes next

Record the experiment question, source and run references, observations, decision, spend, and next
useful action in the existing work records. Report experiment rounds (including diagnosis)
separately from candidate attempts; a round cap counts experiment rounds. Each attempted candidate
also gets a `changes.md` entry.
Keep concise chat updates about findings, decisions and uncertainty; link detailed evidence in the
work directory rather than narrating every passing trajectory.

Keep notes useful for the next decision: scoped mechanisms, supporting and contradictory evidence,
implementation failures, and what would justify a retry. Update existing lessons instead of adding
duplicates. Numeric lesson votes are optional, not a confidence measure. Current evidence takes
precedence over old notes; a vivid single case does not establish a general rule.

When progress stalls, reconsider the bottleneck before editing again. Distinguish capability or
coverage gaps, unreachable content or other structural problems, measurement defects, infrastructure,
and inadequate evidence, and investigate the relevant cause. Never weaken a test because the agent fails.

Continue while a credible experiment or useful measurement remains within the agreement. Stop on
the agreed objective or limits, user request, or lack of a worthwhile next step. Reserve resources
for justified final verification. Passing behavioral checks alone does not end resource
optimization, and remaining budget alone is no reason to keep spending.
Request an extension before exceeding authorization and explain what it would enable.

## Recover after interruption

The agreement establishes authorization, checkpoints describe active work, run artifacts establish
what executed and scored, and decision history establishes acceptance. Notes hold hypotheses;
outer-loop and benchmark records do not prove a candidate was accepted. Before resuming, reconcile
these with actual source, worktrees and completed artifacts: planned, completed, scored and accepted
are distinct. Check for partial runs and pending judges; use the runner's resume support without
treating stale output as new evidence. A timestamp or phase label does not prove acceptance. Preserve
conflicting records, mark unresolved work, never apply a candidate twice or promote unverified work,
and rerun only what cannot be recovered. Pause only dependent work; ask when the choice is consequential.

For example, an acceptance log naming A and a checkpoint naming interrupted candidate B establish
the last recorded incumbent and intended work, not the actual checkout or measured snapshot.
Inspect the checkout/worktree and recover B's run source before deciding what to resume. Missing
acceptance does not prove the checkout is A; a pending phase does not prove B ran. Resume the
interrupted iteration when it remains the same learning work, or explain a genuinely new learning
opportunity within the agreement; do not start a new iteration merely to reset a limit.
