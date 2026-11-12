---
name: loop
description: Use to improve the AI agent in this repository continuously from traces, feedback and evaluations ("improve this agent from ./traces", "keep improving it as new traces come in", "run the improvement loop", "make it better and cheaper with as little of my time as possible"). Not for a one-off test run (use the eval skill) or a single fix (use the improve skill), and not for running a prompt on a schedule or polling.
---

# Loop: learn from new traces, fix, repeat

Inspect existing evidence and runners. Read `relai/README.md`, or the bundled
[terms](../start/template/README.md#terms) when absent; use the [start skill](../start/SKILL.md)
for needed managed records without rebuilding working infrastructure. This skill coordinates
learning and verified improvement across the `discover`, `eval` and `improve` skills
under one contract.

**The flow below is a starting point.** Adapt, reorder, repeat or skip activities when that
better serves the request and the evidence, and load stage guidance only when relevant. The agreed
scope, budget, authorization, evidence requirements and stage rules still bind.

Goal: useful learning and evidence-backed improvement with human judgment used where needed.
Every kept change has comparable evidence and regression checks; every candidate decision is
recorded with its reason. An investigation can produce useful knowledge without a code change.
Maintain that knowledge when it helps future work under the
[shared policy](../start/template/README.md#maintain-useful-knowledge); do not fill an iteration
with artifact updates that add no durable value.

## Two levels: learning iterations and experiments

- An **iteration** is a learning cycle started by a credible learning opportunity: new inputs, an
  unresolved question, or a useful experiment using existing evidence. It need not include trace
  intake, new tests or code changes.
- An **experiment round** happens inside an iteration ([improve: improve-loop](../improve/references/improve-loop.md)). It can produce learning without a patch. Accepted candidates
  become the incumbent; other exploration remains isolated.

A round cap counts experiment rounds, including diagnosis; report candidate attempts separately.

## Done when

The paths below describe RELAI-managed records. Existing project contracts, iteration history,
candidate decisions and reporting may serve the same purpose when authorization and evidence
remain inspectable and recoverable; do not create duplicate state merely to match these filenames.

- **The contract was approved** (below) and saved in `relai/records/loop/state.json`
  (`relai/docs/files.md`), with a line in `decisions.md`.
- Before claiming an improvement, a comparable baseline exists for the objective and guardrails,
  measured or reused with a rationale. Investigation without a candidate records its findings and
  limits without an improvement claim.
- Each iteration is appended to `state.json` under `iterations`; each attempted candidate has a
  `relai/changes.md` entry.
- The loop stopped on a stopping condition, and you reported: the iterations run and what
  started each, experiments run, candidates tried and kept, the applicable objective/guardrail
  evidence and its limits, resource measurements,
  the regressions caught and changes rejected (and why), the
  user's decisions, total spend, benchmark coverage, and where the improved agent lives; the
  final split of a benchmark only when authorized. Relevant managed state or equivalent project
  reporting is current.

## Establish the loop agreement

Reuse an existing contract covering these choices. Ask only for missing consequential choices
or changed boundaries; establish a new contract before starting when none exists. The contract is
the improvement agreement (`relai/README.md`, Terms) and supplies the authorization for the
stage decisions it covers. It is not approval to skip an uncovered consequential decision.

- **Objective and guardrails:** what improves (test pass rate, or cost or latency with scores
  held), and the guardrails with their bounds and evidence requirements.
- **Scope:** what may change (prompts, tool descriptions, skills, memory or context
  construction, retry logic, agent code, model settings) and what is off-limits.
- **Inputs:** the trace folder or stream to learn from, if any, the test suites in play, and any
  benchmarks (with any agreed held-out sample and batch size per iteration). When traces will be
  triaged by a model, the provider and model, and the user's authorization to send trace text to
  it ([discover: trace-triage](../discover/references/trace-triage.md)); with that and the budget,
  the loop runs triage beyond the pilot size (`--yes` for the example script).
- **Length:** the most iterations to run, or "until there is nothing new"; and any experiment
  limit per iteration.
- **Budget and evidence:** a ceiling for the loop and any per-iteration limits, covering agent
  trials, judges and triage. Measurement effort is chosen per decision ([eval: measure](../eval/references/measure.md)).
- **When to ask the user** (recommend: only these): user intent is genuinely ambiguous; two
  requirements conflict; a behavior is irreversible or safety-sensitive; a judge and the user's
  past verdicts disagree; a product-policy decision is needed. They are asked as `relai/README.md`
  says ("When the user is asked"); everything else proceeds and appears in the digest.
- **Approvals:** `delegated` (default): fresh independent reviews stand in for scenario approval,
  grader previews and task lists, as [delegated approvals](../start/template/README.md#working-with-the-user)
  describe; or `supervised`: the user approves each scenario table, grader preview and kept change
  individually. Inside the loop this setting answers the build skills' "how involved" question.
- **Check-ins:** a short digest after every iteration (default), or only at the end.
- **Watch mode** (optional): instead of stopping when nothing is new, re-check the trace source
  on a schedule the user sets up and start an iteration only when new traces or answers have
  arrived. A check that finds nothing new exits quietly; report any host/model usage rather than
  promising that a scheduled check is free.
- **Delivery:** kept changes accumulate on a branch for review (default), never in the user's
  working tree unless the contract says so.

## The locked kernel

Hold measurement meaning and relevant comparison conditions stable within an iteration: frozen
tests and their evaluators, the held-out set and acceptance rule. Budget and authorization also
stay binding. Supporting implementation repairs or improvements may proceed within scope under
the shared [adaptation policy](../start/template/README.md#adapting-supplied-implementations);
changes to measurement meaning require controlled repair and comparable starting evidence. New tests join
only at an iteration's start, after their fresh review and freeze, and get a baseline on the
incumbent before any candidate is compared with them. The loop may propose a change to the
kernel (a rubric repair, a retired test, a new budget); only authorization covering that change permits it.

## Suggested learning flow

With adequate evaluations, begin at improvement; diagnosis may return to discovery when an
ambiguity appears. Record adaptations that affect evidence, scope or delivery. Keep the real
dependencies: comparable evidence precedes improvement claims, delivered revisions need
verification, and measurement changes go through the locked kernel.

0. **What is worth learning next?** New traces or answers, uncovered behavior, missing
   measurements, or a credible experiment on existing evidence. If none remains, stop or wait in
   watch mode rather than repeating activities for their own sake.
1. **Intake.** Triage traces that arrived since the last iteration ([discover: trace-triage](../discover/references/trace-triage.md); incremental by trace id) and read new feedback and answers.
2. **Filter by usefulness.** Routine runs with no signal are archived. Durable knowledge goes to
   the wiki: requirements from settled answers, evidence on risks, near misses. Reproducible
   behavior becomes test proposals: runs the user's feedback judged wrong, uncovered situations, co-occurring weak
   signals, harder rungs of tests the agent now passes. Questions the contract says to ask go to
   open questions or `feedback.md` and are asked together; the loop does not wait on them, it works on everything else.
3. **Grow the tests.** Build the strongest proposals (the `eval` skill): realistic, both
   directions, a fresh review standing in for scenario approval and grader preview when the contract's
   approvals are `delegated`, then freeze. Held-out tests are optional (the `eval` skill's Split rule).
4. **Establish starting evidence** for the objective and guardrails: reuse comparable
   incumbent runs or measure what is missing ([eval: measure](../eval/references/measure.md)). On
   benchmarks, use exact development selections (`benchmark.py batch --case-ids ...`) plus any
   agreed held-out sample; never the final split.
5. **Experiment** as [improve: improve-loop](../improve/references/improve-loop.md) describes; alternatives
   follow its candidate-selection reference.
6. **Verify the delivered candidate** with comparable before/after evidence and a fresh review of
   the actual delivered diff.
7. **Accept or roll back** by the improve loop's acceptance rule, judged over the
   iteration's delivered changes. Preserve the last verified incumbent, record dropped candidates
   as rejected, and reverify and review the resulting diff. An accepted iteration is a new
   generation of the agent.
8. **Record and report.** Append the iteration to `state.json` (`relai/docs/files.md`), update `relai/STATUS.md`, and
   send the digest: what started the iteration, what was learned, tests added, experiments and
   candidate outcomes, comparable measurements and their limits, spend so far; then ask the
   waiting questions.

## Stopping conditions and recovery

Stop when the agreed objective or limits are reached, the user asks, blocking judgment is needed,
or no worthwhile authorized experiment remains. Outside watch mode, do not start a new iteration
on unchanged inputs merely to evade a round cap. Stalls, extensions and recovery after
interruption follow [improve: improve-loop](../improve/references/improve-loop.md); `state.json` is an
orchestration summary, never evidence that a candidate ran or was accepted.
