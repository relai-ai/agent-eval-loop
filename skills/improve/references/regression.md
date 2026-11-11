# Check a change for regressions

Goal: evidence about whether the change affected behavior the selected tests cover.
Use existing project checks directly when sufficient. The frozen-test, run-layout and summarizer
steps below apply to RELAI-managed evaluations; project equivalents need the same evidence and
honest coverage limits, not a new RELAI directory.

## Done when

- You chose the tests that could catch harm from this change, and said why each was chosen and
  what the selection leaves uncovered.
- Relevant frozen tests ran before and after the change as comparable runs (`relai/README.md`,
  Terms), or you said why there was no relevant test or no recoverable baseline.
- You reported the before/after results (`summarize.py <after> --baseline <before>` for RELAI
  artifacts) and named supported regressions, observed changes and unresolved comparisons.

## Rules

- Choose by the change's mechanism, the runtime path it touches, the product surface, and what
  each test's evaluators check, not by tags alone. Never select the smoke test.
- Run the baseline before the edit, or from the pre-change revision in a separate checkout
  (`relai/README.md`, host notes).
- Run and score tests as [eval: measure](../../eval/references/measure.md) describes.
- Separate observed changes from justified conclusions: an unchanged mean or no observed
  regression is not proof of safety. Report uncertainty, differing attempt counts and uncovered
  behavior.

## Approach

### Choosing the checks

- Add structural adjacency to the mechanism and surface: code the change shares a module, prompt
  section or tool with.
- Prefer tests whose scores can be compared before and after; explain any differences in conditions
  rather than treating a computed delta as proof of comparability. Leave out checks that only show
  the agent ran and tests whose scoring is not settled, and say why for each. When none are left,
  report "no independent regression coverage" plainly.
- Use wiki requirements and risks to find what the change could break, but treat them as history,
  not as the current test definitions. Past scores are advisory and comparable only when the same
  test and setup produced them.
- Fewer checks, including none, are fine when you can say why. When you cap the selection,
  name the highest-risk tests you left out and what they would have caught, and any pool you did
  not screen (for example benchmark rows you never looked at).

### Gaps become tests

When the change touches an important behavior that no test measures, say so and propose a test
for it (the `eval` skill). Do not run unrelated tests to fill the space.

### Reading the results

- A low score or a failed run needs investigating before you call the change safe.
- A high score on one test does not prove the change is safe overall.
- When no baseline can be recovered, run only after the change and state the limits of that
  evidence.
