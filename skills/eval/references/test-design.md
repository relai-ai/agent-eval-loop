# Designing a test

How to design each test for the `eval` skill, whose Rules bind; this adds the method.

## Rules

- Reuse `relai/harness/`. A test adds its scenario, inputs and evaluators; it does not redefine
  how the agent runs. If the harness cannot support the test, fix the harness under [harness](harness.md) and rerun the smoke test (`relai/harness/smoke/`). Never write agent tests there.
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
- Use a simulated user (a model playing the user) when the behavior depends on how a user
  responds.
- Run and score tests as [eval: measure](measure.md) describes.

## Ask the user

- When the target, expected outcome or how to evaluate it is still ambiguous after reading the
  code and wiki, including criteria a run log suggests but feedback does not state. Ask every
  question at once, recommendation first.
- Whether an ambiguous change request updates an existing test or needs a new one.

## Approach

### Choosing a useful set

Compare candidates by important failures they expose beyond existing or already-selected tests,
the evidence that those failures matter, and the effort to build and maintain them. Ask which
plausible wrong behavior could still pass the set, and which candidate would distinguish it.
A shared evaluator covers another condition only when a scenario actually exercises that condition;
a broad rubric alone does not establish coverage. Keep unrelated behaviors independently
interpretable rather than packing them into one scenario. Explain consequential omissions and
uncertainty without elaborating a full backlog that the decision does not need.

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
- Code may match the agent's text only for a literal the task requires (an id, a code, a fixed
  phrase), after ignoring Markdown, punctuation and case.
- Never use a judge for a fact code could check: it adds noise and cost to something certain.
- Split a criterion with both parts. "Looks up the order and explains the refund window" is a
  code evaluator for the lookup and a judge for the explanation, so either failure shows on its
  own.
- When the outcome lives in exported state rather than the reply (a database row, a mock call),
  check the state with code, not the agent's description of it.

### Choosing what to evaluate from a run and feedback

Sort every dimension the log and feedback suggest:

- **Explicit**: the feedback or the user's answer states it. Cover it, or say why the recording
  cannot show it.
- **Candidate**: the log suggests it but the feedback does not. Ask before evaluating it; present
  related candidates at the same checkpoint, keeping independent choices separately answerable.
- **Unsupported**: there is no reliable expected behavior or source of truth. Do not evaluate it.

Keep distinct confirmed criteria in separate evaluators, so one failure cannot hide behind
another. Do not turn wording or values that only happen to appear in the log into exact checks,
and avoid expected values that change over time unless that exact instance is the point.

### Feedback the agent's owner can act on

Below full marks, name every unmet condition, where it happened (the turn, call or file), what
was observed, and what would be accepted. When a check needs an exact string or pattern, state
the full accepted string or pattern, not an example; when equivalent wording is accepted, say so.

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
requirements it covers; the scenario, naming the real data it uses; the trigger that makes it
hard; what passing and failing look like; its opposite-direction partner, if any; its split; and
what would make the probe invalid.

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
