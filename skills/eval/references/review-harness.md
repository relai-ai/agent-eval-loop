# Harness review brief

You review, with fresh eyes, a harness another agent built so the agent in this repository can
be evaluated. You only read; you change nothing. The harness is correct only when a trial is the
real agent doing its real work and the evaluators see what it actually did. Fail a property only
on evidence you can quote, never on speculation.

For project-native work, use the supplied project equivalents of the paths and results below,
plus the bundled [shared contract](../../start/template/README.md) when no project copy exists.
Missing RELAI filenames alone are not a finding; verify the same evidence and guarantees.

Read: `relai/README.md` and `relai/docs/`, `relai/relai.toml`, `relai/decisions.md`, everything under
`relai/harness/` (including the smoke test in `relai/harness/smoke/`), and the project files the
harness changed (`git diff`). Establish from the repository yourself how the real application
starts and uses the agent before reading the harness's claims.

## Passes

The review can run in up to three passes; you are told which one this is.

- **Code pass.** No trajectory yet (the smoke trial may still be running). Judge every property
  from the code; mark one unsure only where its answer depends on what a run records.
- **Trajectory pass.** You are given the smoke run's trajectory. Check that it shows the run the
  code implies: the real agent's model and tool events, the user input on every turn, and the
  deliverable where the evaluators read it. Settle every property left unsure, and change a
  verdict when the trajectory contradicts the code.
- **Recheck pass.** After fixes, you are given your earlier report and the diff since it. Check
  that each finding is fixed at its evidence and that the diff breaks no property that passed.
  Re-read beyond the diff only where it touches a property's evidence.

Judge each property, with a verdict of pass, fail or unsure, and quoted evidence (file:line,
or a trajectory step):

1. **Real agent.** The trial runs the same entrypoint and production path the application uses,
   from current source, with real model calls, prompts, tool selection and tool code. Files whose
   edits change behavior are read live, not baked into an image.
2. **Real configuration.** The integrated configuration is the one the repository presents as
   real use (README, defaults), not a test fixture; `relai.toml` names it and the evidence.
3. **Real input.** Input reaches the agent through its normal input path, including any preprocessing
   the application applies, and state is kept the way the application keeps it.
4. **Unchanged behavior.** The harness and any project edits change nothing the agent does:
   prompts, tool policies, model choice, data and control flow are as in production. Recording
   only observes. Permissions come from the agent's relevant operating settings, or, for
   interactive prompts, from the user's answer recorded in `decisions.md`.
5. **Declared stand-ins.** Anything not run for real is replaced only at a dependency's client
   boundary, is listed in `relai/harness/mocks/MOCKS.md`, and applicable authorization covers it
   (an approval or covering agreement).
6. **Truthful trajectory.** Every recorded step happened, in order, and nothing that matters is
   missing: inputs, model messages, tool calls with arguments and results tied to their calls, as applicable.
7. **Output reaches evaluators.** What the agent produces (a reply, a file, a record) is visible
   to the evaluators, and the smoke test's evaluators check a real outcome rather than activity
   and could fail. The smoke test is not frozen, so a check loosened until it passes fails this.
8. **Containment.** `[runner]` declares actual execution and isolation, and it meets the *Containment* rule (`relai/README.md`, Fixed rules),
   demonstrated by the integration rather than inferred from a config label. No secret appears in
   committed files.
9. **Runner contract.** The declared implementation writes truthful causal records (ATIF when using
   bundled consumers that require it) and evaluator scores plus feedback or explicit errors.
   Native grading was checked on synthetic passing,
   failing and empty cases. The runner's recorded identity changes only when what it measures
   changes, not with the path of the candidate being tested.

Report each property's verdict, then findings: for each failed or unsure property, what is wrong,
the quoted evidence, and the change that would fix it, marked blocking or advisory. Write the
report to `relai/records/reviews/harness-<date>-<pass>.md` if you can write files; otherwise return
it.
