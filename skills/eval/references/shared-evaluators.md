# Shared and repaired evaluators

Goal: a criterion applied consistently to every test it fits, able to fail, with feedback that
says what full marks need.

## Done when

- `relai/evaluators/<id>/` holds the evaluator (code, or a judge rubric) and a `README.md` stating
  the criterion, its method, concrete scoring criteria (what earns full marks, partial credit and
  zero), and which tests it applies to and why, or that it applies to none.
- Each test it applies to declares it and carries it under its own `tests/` (a separate verifier
  sees only `tests/`).
- `check_task.py` passes, plus `--verifier` for Harbor or synthetic grading checks for native tests, and with API judges `relai/bin/judge.py --self-test`
  shows the judge can fail (or a synthetic violating example does so for a pure prohibition).
- Every frozen test you changed went through the freeze rule (review: [review-test](review-test.md)).

## Rules

- The method decides the type: exact criteria are code, semantic ones are judges. [test-design](test-design.md)'s
  "Choosing code or a judge" explains how to tell them apart.
- Adding an evaluator to a frozen test changes what its score measures. `summarize.py --baseline`
  still describes numeric differences and raises a notice; those numbers alone cannot establish
  improvement. Rescore recoverable evidence or establish a fresh comparable baseline.
- An evaluator error is not a score. Fix its cause, then rescore the recorded runs into a new
  directory instead of rerunning the agent, keeping the originals intact (Harbor:
  `harbor trial regrade` with `-o`, see [harbor-notes](harbor-notes.md); it cannot see unexported
  state). `relai/bin/judge.py <run>` retries judge errors. After a rubric change, establish a
  comparable baseline.
- A missing required deliverable scores the minimum. A pure prohibition may correctly reward
  inactivity; show it can fail on a synthetic violating example instead. A check must measure its
  stated outcome rather than activity alone.

## Ask the user

- When an existing evaluator overlaps the new criterion unclearly, or two evaluators would score
  the same thing differently.
- Before reducing a frozen test's coverage by removing or loosening an evaluator, when existing
  authorization does not cover that decision.

## Approach

### Check existing coverage first

Before writing a shared evaluator, decide whether an existing one already covers the criterion:
fully (reuse it), partly (extend it, or add a narrower one), or not at all (write it).

### Write it for every test it applies to

A shared evaluator cannot know each test's scenario in advance, so it reads it from the
trajectory.

- A shared judge's rubric reads the user turns to learn what the scenario asks, then judges the
  replies against that: they address what was asked, are correct and consistent with what the
  agent could know from the conversation and its tools, and are clear and complete without
  invented details. Its feedback names the turns behind the score and what would score higher.
- Decide whether a deliverable is required from the user's request in the trajectory, not from
  the evaluator: when asking or declining is the right response, nothing is missing.

### Repairing it

A repair keeps the evaluator's id. Change its type only when the criterion was misclassified: a
semantic criterion a code check was standing in for becomes a judge.
