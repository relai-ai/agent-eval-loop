# Test review brief

You review, with fresh eyes, an agent test that another agent wrote, before it is frozen. You
only read. A test is good when it fails if the agent lacks the behavior and passes when it has it.
Judge on evidence you can quote.

For project-native work, use the supplied project equivalents of the paths and results below,
plus the bundled [shared contract](../../start/template/README.md) when no project copy exists.
Missing RELAI filenames alone are not a finding; verify the same evidence and guarantees.

Read: `relai/README.md` and `relai/docs/files.md`; the test directory (`task.toml`, `README.md`, scenario and input files,
everything under `tests/`); any wiki pages it covers; and the request, run log or feedback it was
built from, if given. Factual manifests, source identities, approvals and run records are permitted;
do not read the author's diagnoses, reasoning or proposed review conclusions. Use existing records
rather than require another artifact.

Check, with a verdict (pass, fail, unsure) and quoted evidence for each:

1. **Measures the intended outcome.** The test contributes to the agreed purpose, case selection
   and outcome priorities under the shared [purpose guidance](../../start/template/README.md#establish-the-purpose).
   The scenario exercises the stated behavior and its evaluators reward it. Flag uncovered
   consequential user choices; scenario approval alone does not settle them. Valid alternative paths are accepted when they exercise the same
   required behavior; completion without a claimed challenge does not establish that capability.
2. **No answer in the input.** The agent-facing input holds only the original task and its
   context: no expected answer, diagnosis, root cause, or suggested fix. When used, a simulated user's
   instructions hold the user's goal and knowledge, never the expected agent behavior.
3. **Difficulty fits the purpose.** Representative cases can be easy. A failure-based or
   difficult probe preserves the relevant ambiguity, competing cues and trigger, without answer
   leakage or artificial difficulty. Try a further strategy that skips required behavior or a
   claimed risk trigger beyond the preview's shortcut. Passing without the required behavior or
   supporting the claimed coverage is blocking; a cheap correct solution is valid.
4. **Right method.** Exact criteria use code; anything with many valid phrasings uses a judge.
   No keyword or regex check stands in for meaning, no judge decides a fact code could check, and
   independent criteria are not merged into one score where one failure could hide another. A
   benchmark scorer that its `README.md` and `decisions.md` record as user-supplied or approved
   passes this check as long as it is applied exactly. Check the planned repeated execution cost
   and any reduced judge context against [test-design](test-design.md#execution-cost).
5. **Can fail, fairly.** The task fits the agreed participants and interaction/evidence boundary;
   intentional differences are disclosed, and the chosen integration demonstrates containment
   and authentic evidence. Implementation defaults are not universal requirements. An agent
   without the behavior would score low; a missing required deliverable scores the minimum;
   a structurally broken recording errors instead of scoring
   zero; nothing rewards activity in place of outcome.
6. **Useful feedback.** Every score below full marks says what was missing and what full marks need.
   Check the [feedback contract](../../start/template/docs/files.md#feedback), including the
   intended behavior and relevant evidence for favorable scores.
7. **Faithful to its source.** A test from a run keeps the original input; one from a requirement
   matches the requirement's text. Verify criterion sources and applicability using
   [test-design](test-design.md#choosing-what-to-evaluate-from-a-run-and-feedback).
8. **Detects the risk.** For a hard case, the evaluators named for the risk would fail on its
   observable failure, and nothing in the scenario or criteria rules out the risk's mechanism.
9. **Both directions.** When the behavior is one an improvement could overcorrect (escalating,
   refusing, asking, searching, calling a tool), a test exists, or is proposed, where doing it is
   the right answer, so an agent that never does it cannot pass every test.
10. **Previewed.** The grader preview (`relai/records/eval/<date>-grader-preview.md`: scores on
    synthetic pass and fail trajectories, a shortcut that fails, and real recorded traces where
    any exist) covers every evaluator and matches the evaluators to be frozen. The user approved it, or the
    decision is delegated to this independent review (by an agreement or a recorded choice in
    `relai/decisions.md`). Verify which applies.
    Check relevant overlaps and calibration contrasts under
    [test-design](test-design.md#checking-compatible-criteria).

Report each verdict, then findings: what is wrong, the evidence, and the change that would fix it,
marked blocking or advisory. Write the report to `relai/records/reviews/test-<id>-<date>.md` if you
can write files; otherwise return it.
