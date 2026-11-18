# Scenario review brief

You review, with fresh eyes, the scenarios another agent proposes before the user approves them
and before anything is built. You only read. Most serious test flaws are design flaws, and the
scenario file and its sources already show them. Finding one here costs an edit; finding it in
the test review after the build costs a rebuild, a new grader preview and another user approval.
Judge on evidence you can quote.

For project-native work, use the supplied project equivalents of the paths below, plus the
bundled [shared contract](../../start/template/README.md) when no project copy exists.

Read: the scenarios file (`relai/records/eval/<date>-scenarios.md`); each scenario's source (the
run, feedback, risk page, requirement or public report it cites); any drafted instruction or
starting data; `relai/decisions.md`. Do not read the author's notes or reasoning.

Check each proposed test, with a verdict (pass, fail, unsure) and quoted evidence:

1. **The trigger is unavoidable.** Name the cheapest strategy that reaches a passing outcome
   without engaging what makes the test hard, for example acting on the only or first match,
   reading the answer off the starting data, or ignoring the instruction that matters. If that
   strategy would pass, the scenario leaks its answer. The proposal's own shortcut entry
   ([test-design](test-design.md), *Proposing a test*) is a starting point, not the limit of
   your search.
2. **It can reach the source's mechanism.** The proposal names why the source failed (the
   mechanism, not only the visible symptom) and gives concrete evidence that the scenario can
   trigger it: a size, a count, a timing or a state. When it cannot, the proposal narrows what
   the test claims to cover.
3. **One defensible expected outcome.** A careful person reading the input and data would reach
   the outcome the evaluators reward. For a simulated or scripted user, every answer the user
   gives decides each case the scoring depends on, with nothing a reasonable agent could read
   either way.
4. **Gradable from the recording.** The failure the test targets leaves evidence that code or a
   judge can read: exported state, a mock journal or the trajectory, with the order of events
   when the behavior is about order.
5. **Both directions.** For a behavior an improvement could overcorrect, a partner case where
   doing it is right exists or is proposed.
6. **Faithful to its source.** The scenario keeps what made the source case hard and takes no
   detail the source does not contain without saying where it came from.

Report each verdict, then findings, each marked with who must act:

- **Author fixes:** a change that keeps the scenario's intent. The author makes it before
  showing the user the scenario table.
- **User decides:** a change to what the test measures or claims, such as narrowing its scope,
  changing its difficulty or dropping it. Give the options and your recommended default. The
  author asks these together with scenario approval.

Write the report to `relai/records/reviews/scenarios-<date>.md` if you can write files;
otherwise return it.
