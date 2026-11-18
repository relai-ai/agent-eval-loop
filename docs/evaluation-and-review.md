# Understand evaluation and review

[Back to README](../README.md)

RELAI connects evaluation results to the tests, evaluated revisions and decisions behind them.
This guide explains what you review and how to interpret those results. The generated project
contract remains authoritative for [terms](../skills/start/template/README.md#terms) and
[working with the user](../skills/start/template/README.md#working-with-the-user).

## Review and approve the work

You review the relevant risks, test scenarios and grader previews, then agree on the improvement
objective, scope, guardrails and budget. Existing instructions can supply or delegate approval;
RELAI carries that authorization forward within its boundaries. Review handoffs offer a guided
chat walkthrough or a suitable app view. Chat, app and status board share the underlying records.
Open questions concern intended behavior; feedback concerns a particular run or judge score.
Your answers can update requirements, risk evidence, regression tests or grader calibration.

Your coding agent uses your plan or API tokens during reading, setup and review. Eval runs
add model calls from the evaluated agent, simulated users and judges; optional model-assisted
trace triage can add calls during discovery. RELAI estimates paid-run costs and records spend
against the agreed budget. Before additional processing, resolve any uncovered authorization
for cost and data movement, including which provider receives trace material. Existing agreed
limits carry forward; a new iteration does not reset the budget.

## Inspect progress and decisions

`relai/STATUS.md` can show:

- what is waiting on you and RELAI's recommended answers;
- every risk and the eval that probes it;
- recent runs, with flaky ones flagged;
- how often each LLM judge agrees with you;
- spend against the approved budget;
- iterations, observed results and the decisions still needed from you.

To follow a run yourself while it is going, run `python3 relai/bin/summarize.py <run dir>`. It
reads the run records and shows trials finished of the total, trials not finished, outcomes and
recorded cost, without estimates.

Questions wait for a natural decision point: the end of `discover`; the start of an `eval` build, its scenario approval and grader preview; `coding-evals` scope, task and check approval and the budget before the first paid run; the first time LLM judges are scored; or a loop iteration's summary. You can hand build approvals to an independent review instead. Only a blocking safety call or conflicting requirement interrupts dependent work. The full list is in the [project contract](../skills/start/template/README.md#working-with-the-user).

## Check tests and graders

Each eval passes these checks before it counts. Who approves each step, you or an independent
review, follows the agreement above.

- **Grounded scenarios.** Each proposal names its source (a trace, feedback, a risk, a
  requirement, a past fix or a public failure report), why the source failed, the trigger that
  makes the case hard, and the cheapest strategy that would skip it.
- **Scenario review** (application-agent evals). Before you see the scenarios, a reviewer with
  fresh context checks that the answer cannot be read off the input or starting data, that the
  scenario can trigger the source's failure, that one outcome is clearly right, and that the
  failure leaves evidence a check can read. RELAI fixes what keeps the scenario's intent and
  brings the rest to you with a recommended answer.
- **Passing and failing controls.** Validate graders in the selected environment. A reference
  solution scores full marks on code checks (Harbor's oracle when used); doing nothing fails
  checks requiring action (Harbor's nop), but may pass a prohibition. Use an actual violation for
  that check, and another correct solution where one exists. Preview judges on their declared
  evidence too. Scripted controls need no model; judges and simulated users may call one.
  Investigate unexpected control results before freezing.
- **Grader preview.** You see each check's scores on passing, failing and empty runs, on recorded
  traces that fit, and on the shortcut, which must fail. A shortcut that passes means the eval
  leaks its answer, and RELAI fixes the scenario before freezing.
- **Test review.** A reviewer that did not build the eval checks each one before it is frozen:
  it measures the stated behavior, holds no answer in its input, can fail fairly, uses code for
  facts and judges for meaning, gives useful feedback and stays faithful to its source.
- **Freeze and pilot.** Frozen evals are fingerprinted; later changes need a recorded reason and
  a fresh review. A paid pilot confirms the agent runs and every check scores before larger runs.

Across the work:

- Evals are frozen before comparison, with fresh-context reviews of the harness, evals and changes.
- Measurement effort is chosen for the decision; "too few attempts to tell" is a valid result.
- Optional held-out evals can be scored without reading their contents while improving the agent.
- Infrastructure and judge errors are reported separately from agent results.
- You preview how each judge grades before freezing it, and agreement is tracked.
- Tests use shared metadata and result contracts through Harbor or a native runner, with instructions for rerunning the suite, including in CI.

## Compare like with like

A frozen test has fingerprinted files, so later edits are visible. Hold tests, graders and
relevant execution conditions stable while comparing a baseline with candidate changes.
If measurement is defective, pause optimization against affected tests, investigate the defect,
record and review the justified repair, and establish a comparable baseline before using them
again. A low score alone does not prove the test is wrong.

Runner speedups are reported separately from changes to the agent's own cost or latency.
Changing a runner or grader can change measurement meaning; it is not automatically an agent gain.

## Interpret uncertainty and held-out results

Read sample sizes, variation, unsuccessful trials, missing measurements and coverage gaps
alongside scores. With too few attempts, the appropriate conclusion can be that the evidence
is inconclusive. Infrastructure and judge failures are reported separately from agent failures.

Development evidence can guide diagnosis and selecting changes. Optional held-out evals check
changes without exposing their contents during improvement, but repeatedly selecting on those
results can also overfit and must be disclosed. A benchmark's final test split stays reserved
for final assessment. See [benchmark import](agent-evals.md#bring-your-own-benchmark).

Results support claims about the evaluated scenarios and operating conditions. They do not
prove that an agent is correct everywhere or that no regression is possible. Fresh-context
reviews help inspect the work; they do not replace adequate measurement or containment.
