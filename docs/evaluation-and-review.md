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
