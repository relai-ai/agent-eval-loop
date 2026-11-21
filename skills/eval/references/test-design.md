# Designing a test

How to design each test for the `eval` skill, whose Rules bind; this adds the method.

## Rules

- Reuse the selected integration (`relai/harness/` when used). A test adds its scenario, inputs
  and evaluators; shared execution behavior stays in the integration. If it cannot support the
  test, repair it under [harness](harness.md) and rerun its smoke test (`relai/harness/smoke/`
  when used). Never use the smoke test as an agent-quality eval.
- Use a behavior-class scenario for a general expectation and an exact instance when the request,
  trace or value itself is the point.
- From a failed run plus feedback: keep the original input faithful and put the lesson in the
  evaluators.
- Score whole turns, not just the last message.
- **Missing deliverables and prohibitions** (the one home of this rule): a required deliverable the
  agent did not produce scores the minimum. A pure prohibition is met by doing nothing, so an empty
  reply may pass it; show it can fail on a synthetic violating example instead.
- When the recording lacks the structure a check reads, let the check raise (an error), never
  score it as zero.
- When behavior depends on a user's response, use an interaction channel matching real use.
  Script fixed decisions; use a simulated user when replies must respond to the question.
  Check valid alternative paths, including proactive answers, against the user's goal and the
  intended challenge. Do not require an incidental dialogue sequence when equivalent behavior
  exercises the same challenge. If the challenge was not exercised, report that limit rather
  than treating completion alone as evidence of the capability.
- Run and score tests as [eval: measure](measure.md) describes.

## Ask the user

- When the target, expected outcome or how to evaluate it is still ambiguous after reading the
  code, requirements and prior decisions, including a proposed criterion's applicability. Batch related
  questions in manageable groups, recommendation first, with each independent decision in a
  separate prompt or labeled row, as the
  [shared user-interaction guidance](../../start/template/README.md#working-with-the-user) describes.
- Whether an ambiguous change request updates an existing test or needs a new one.

## Approach

### Choosing code or a judge

Ask of each criterion: could two correct replies differ in how they satisfy it?

- **Code** when the answer is no: a fact a program can decide with certainty from the recording
  or exported state. Tool calls and their arguments, the order of steps, a state change (a record
  written, a file edited), a JSON shape or field value, a required literal, an exact number.
  Code is deterministic, free and repeatable, so prefer it whenever it can decide the criterion.
- **A judge** when the answer is yes: meaning that a correct reply can express in many ways.
  Refusing or redirecting, explaining, tone and helpfulness, whether a claim in prose is correct,
  whether an answer is equivalent to an expected one. A keyword list or regex cannot cover every
  valid phrasing, however complete it looks.
- Code may match the agent's text only for a literal the applicable requirement specifies (an id,
  a code, a fixed phrase). Derive the match boundary and any permitted normalization from that
  requirement; a required whole response cannot be checked by substring alone.
- Never use a judge for a fact code could check: it adds noise and cost to something certain.
- Split a criterion with both parts. "Looks up the order and explains the refund window" is a
  code evaluator for the lookup and a judge for the explanation, so either failure shows on its
  own.
- When the outcome lives in exported state rather than the reply (a database row, a mock call),
  check the state with code, not the agent's description of it.

### Execution cost

Consider the expected repeated cost of agent execution and grading before committing to a test
portfolio. Use representative records or an authorized pilot and the
[shared resource policy](../../start/template/README.md#resources-and-expectations).
Reuse deterministic processing and shared evidence extraction where useful. Separate criteria
need distinguishable scores and feedback, but need not duplicate model work. Use only relevant
judge context when meaningful pass/fail examples validate that reduction; retain inspectable
source evidence. Efficiency changes must preserve measurement meaning or follow controlled repair.

### Choosing what to evaluate from a run and feedback

For each criterion, identify the intended behavior, its requirement source and when it applies.
Use existing rubric text, metadata or links to the task, policy, interface contract or approved
evaluation objective; no separate requirement document is needed. Distinguish facts used to check
correctness from facts the agent must communicate or act on. A fixture, reference answer or prior
trace alone does not establish an obligation. A grader's feedback can suggest a criterion but
cannot establish its own authority.

Sort the dimensions the log and feedback suggest:

- **Established**: an applicable requirement or the user's decision supports it. Cover it, or say
  why the recording cannot show it. Reuse established requirements without asking again.
- **Candidate**: the log or feedback suggests a useful expectation whose authority or applicability
  remains ambiguous. Investigate the sources, then ask about consequential unresolved choices.
  Keep consequential unresolved expectations as
  [open questions](../../start/template/README.md#working-with-the-user) until settled; do not use
  them as mandatory passing conditions.
- **Unsupported**: there is no reliable expected behavior or source of truth. Do not evaluate it.

Keep distinct confirmed criteria in separate evaluators, so one failure cannot hide behind
another. Do not turn wording or values that only happen to appear in the log into exact checks,
and handle changing expected values under [validity across runs](#validity-across-runs).

### Validity across runs

Apply the shared [reproducible-task rule](../../start/template/README.md#fixed-rules).
Identify dependencies that could change the scenario's meaning, correct answer or claimed
challenge between trials, such as time, policy revisions, external data or service behavior.
Record relevant assumptions and how they are controlled or checked in the existing scenario
and integration records; no separate artifact is required.

For time-dependent cases, inspect where the agent learns the time, including runtime prompts,
the operating system and tools. Establish the relevant time zone and reference time for each
trial. Keep prompts, fixtures, simulated users and evaluators consistent with that choice.
Preserve relationships such as an event being past, a deadline being actionable or a holiday
changing an answer. Relative dates alone do not establish them: Wednesday this week is still
in the future on Monday.

Investigate feasible approaches before recommending one:

- Generate scenarios relative to actual time when the agent retains its normal clocks.
  Instances can differ in difficulty, so validate the relationships that make the probe useful.
- Control relevant time sources when the integration can demonstrate consistent time without
  violating the agreed operating conditions. Mocking one service's clock does not establish
  control of the agent's other clocks.
- Keep fixed dates for an explicitly historical scenario when that preserves the intended task.
- Retain a validity window when the intended scenario genuinely requires it, with the guard and
  reporting required by the shared rule. Documentation alone does not enforce the restriction.

At the existing harness or scenario checkpoint, surface uncovered choices that materially
change realism, coverage, participant compatibility, maintenance effort or cost. Use the shared
[user-interaction guidance](../../start/template/README.md#working-with-the-user): present the
evidence, feasible alternatives, consequences and a recommendation; carry prior decisions forward
and pause only dependent work. Recording a choice does not replace asking about it.

Derive changing expected answers from the instantiated scenario and give judges those facts
through their declared evidence inputs ([Scores](../../start/template/docs/files.md#scores)).
Keep hidden keys outside the evaluated agent's readable boundary. A rubric should explain how
to use the facts rather than embed a stale answer or independently interpret today's date.

In grader preview, choose contrasting conditions that could break the relevant assumptions.
For calendar cases these may be weekday, month or year boundaries, holidays, or daylight-saving
changes when relevant. Check correct alternatives, failures and shortcuts against the affected
evaluators under those conditions. A correct answer remaining correct does not establish that
the claimed challenge remains exercised. Choose effort by consequences and uncertainty; use
deterministic fixture and evaluator checks where sufficient. An offline time override does not
prove control of the evaluated agent's clocks during real execution.

Repair existing tests through the *Frozen tests* rule. Check whether a proposed repair changes
coverage: company closures can exercise counting around closures while omitting public-holiday
knowledge. Preserve earlier evidence and disclose such differences before making comparisons.

### Checking compatible criteria

During design and grader preview, compare overlapping criteria against their sources and the
scenarios where they apply. Different scores for distinct dimensions can be valid; a conflict
arises when applicable criteria demand incompatible behavior or interpret the same requirement
inconsistently. Resolve discrepancies using established authority and recorded decisions.

When a consequential ambiguity remains, ask the coding agent's user with the conflicting
expectations, their consequence and a recommendation, following the
[shared question timing](../../start/template/README.md#working-with-the-user). Ask immediately
when valid scoring or acceptance depends on the answer; otherwise raise it at the next review
checkpoint, before freezing or relying on the affected measurement. Pause only dependent work.
Existing frozen evaluators require controlled repair; preserve their original results.

Calibrate the relevant overlapping evaluators on the same examples. Choose contrasts that could
expose a defect: correct behavior omitting optional facts, a valid alternative path, or apparent
task success that violates a consequential requirement. Check required literals at their actual
match boundaries. Include tool arguments and downstream summaries when the criterion covers
them, and verify that cited evidence supports the verdict. Hidden verification facts can establish
outcomes, but do not make unobserved information something the agent should have known. Missing
evidence or an unexercised challenge must remain distinguishable from a violation.

### Feedback the agent's owner can act on

Follow the shared [feedback contract](../../start/template/docs/files.md#feedback) for code checks
and judges. Make requirement sources available in the evaluator's inputs or packaged rubric;
a link the grader cannot access is insufficient context.

### Reusable code evaluators

Keep the values a code evaluator expects (tool names, arguments, required fields, literals,
expected answers) in a data file under `tests/`, such as `tests/params.json` read relative to the
evaluator, not as constants in its code. Another test of the same shape can then reuse the code.

### Hard cases that test the risk

- Start from open wiki risks (`proposed`, `admitted` or `refined`), highest priority first by the
  the `discover` skill's ratings, or from where the agent's code looks fragile. Record a new risk as the *Risks* section of [discover: wiki-rules](../../discover/references/wiki-rules.md) describes (where to look,
  no duplicates or re-proposals) before building for it.
- Make two separate judgments: is the risk worth probing, and is this test a valid probe of it?
  A worthwhile risk with a flawed test means revising the test; a weak risk is retired. A badly
  built test is never evidence against the risk.
- Look for concrete failure boundaries: ambiguous inputs, adversarial phrasing, conflicting
  instructions, state transitions, error paths, unsafe assumptions, malformed or extreme values,
  ordering and concurrency, partial dependency failures, and regressions seen in earlier runs.
- Do not repeat an existing test or one the user rejected. Propose a harder variant of an existing
  test only when you can say what makes it materially harder. Propose fewer cases rather than
  filler.
- Before building, write down what passing looks like, what failing looks like, the condition
  that triggers the risk, and what would make the probe invalid (a trial refusing an action, a
  scenario the agent cannot reach).
- Name the criteria whose failure *is* the risk's observable failure, and give each its own
  evaluator where you can. The risk is confirmed only when one of those evaluators fails; a
  failure caught by another evaluator, or one with a cause the risk excludes, does not confirm it.
- After the first real run, record the probe on the risk's wiki page (test, date, outcome) and
  update its status: `confirmed` when it triggered, `refined` when it did not trigger. An
  inconclusive probe leaves the status unchanged; fix the probe.

### Proposing a test

For scenario approval, write each proposed test's full design to the scenarios file: its source (a risk, a
requirement, the user's feedback on a run, a triage gap with how many real runs it stands for, a
compound of named signals or tests, or a harder rung of an existing test); the risks and
requirements it covers; the scenario, naming the real data it uses; relevant operating conditions
and intended difficulty; what passing and failing look like; its opposite-direction partner, if
any; its split; and what would make the probe invalid, including relevant changing dependencies
and how they are controlled or checked under [validity across runs](#validity-across-runs).
Link to the agreed purpose, selection and outcome priorities in the existing records, explaining
how this case contributes. Also state:

- **The mechanism:** for a failure or difficult probe, why the source failed or the risk is
  plausible, and evidence that this scenario can trigger it. For ordinary coverage, state the
  behavior exercised without inventing a failure mechanism. Narrow unsupported coverage claims.
- **The shortcut:** a strategy that skips required behavior or a claimed risk trigger, and why
  the affected evaluator fails it. The grader preview scores it ([eval](../SKILL.md), *Preview
  the graders before freezing*). A cheap correct solution is valid; do not add artificial
  difficulty simply to make it fail.

When the request calls for coverage of a defined set of behaviors or findings, account for each
within the agreed scope with a scenario that exercises it and an observable passing/failing
distinction, or explain the remaining gap. For prioritized or exploratory requests, match the
selection and detail to the requested outcome. Group related behaviors when their distinctions
remain clear.

### Updating a test

Classify the request before editing: a correction of how the test checks (same evaluators,
better verifier), an extension of the same behavior, a change of intent, or something unrelated.
Unrelated work is a new test. Keep the test's id and every case the change does not touch, and
follow the *Frozen tests* rule.

### Tests on an earlier revision of code

When the agent works on a codebase and the test needs it at an earlier revision:

- Give the trial a Git bundle of that revision and its ancestors only. Later commits would leak
  the fix; a raw tree with a fresh repository leaves the agent no history.
- Install the toolchain that revision pins (toolchain files, lockfiles, CI configuration), or the
  release current at its commit date when it pins nothing, first on the agent's `PATH`.
- Record the checks that already fail at that revision under `tests/`, so evaluators do not blame
  the agent for them. If the revision cannot build in a trial, choose another.
