# Change review brief

You review, with fresh eyes, a change another agent made to improve the AI agent in this
repository on some tests. You only read. Judge on evidence you can quote.

For project-native work, use the supplied project equivalents of the paths and results below,
plus the bundled [shared contract](../../start/template/README.md) when no project copy exists.
Missing RELAI filenames alone are not a finding; verify the same evidence and guarantees.

Read: `relai/README.md` (its Terms define comparable runs, splits and the agreement); the diff of the change; the baseline and after summaries
(`summarize.py` output); development target tests and regression checks (their `task.toml`, inputs
and evaluators); and development trajectories from both runs where the result is unclear.
Use only permitted aggregate summaries for held-out or final evidence. Do not read the author's
notes or reasoning.

If protected contents need inspection, use a separate reviewer authorized to see them. Its report
to the optimizer gives assessment outcomes, counts and limitations, not protected inputs, rubric
details, trajectory excerpts or content-specific fixes. Diagnose needed changes using development
evidence; using protected material for diagnosis changes its assessment role and must be recorded
under the agreement rather than presented later as untouched evidence.

Check, with a verdict (pass, fail, unsure) and quoted evidence for each:

1. **General, not shaped to the tests.** No evaluation-only inputs, expected answers or rubric
   details are embedded to match probes. Legitimate domain rules and capabilities have product
   justification. The change would still make sense if the tests did not exist.
2. **On the normal path.** The change works through the agent's normal reasoning and tools; no
   test-shaped bypass or embedded expected answer. General deterministic capabilities are valid
   when they belong on the real product path, even if they run before model reasoning.
3. **Actually used.** The changed prompt, configuration or code is loaded on the path the tests
   exercise, and the after-run trajectories show its effect.
4. **In scope.** Changes stay within the agreed surfaces, including any authorized supporting
   tooling. Check measurement adaptations against the shared policy and verify that the evidence
   supports the claimed outcome; tooling gains alone do not establish agent gains. No
   model or paid-tool change the user did not allow. No benchmark leakage: the diff holds no
   benchmark case inputs, expected answers or case ids, and the agent does not read the benchmark
   repository at run time.
5. **Objective improvement.** Read the factual objective, guardrails and selection rule from
   `records/improve/plan.json` (or the loop contract or equivalent project agreement), without the author's diagnostic notes. Verify
   improvement against that objective and the exercised mechanism. Preserved behavioral performance
   with lower cost or latency is valid. For multiple candidates, selection followed the recorded
   rule, ties were reported as ties, and best-of-k assessment reuse was authorized and disclosed.
   Bundles have justified scope and do not claim individual effects without evidence.
   The reviewed diff is the delivered revision; any later change requires another review.
6. **No hidden harm.** Regression coverage fits the change’s reach and plausible risks; relevant
   guardrails have evidence, gaps are disclosed, and credible harm beyond the checked cases is
   investigated. In particular:
   - a change that makes the agent do something less (escalate, refuse, ask) has a check where
     doing it is still right;
   - a change that blocks one path has been checked for the next action the agent reaches for
     instead, which can expose a failure the old path masked;
   - a change to shared instructions or code is either measured on the other users of that code
     (other domains, flows, agents) or kept to the scope it was tested on.
7. **Honest numbers.** Before and after are comparable runs, with any baseline reuse justified and
   differing counts and unmatched cases disclosed. Observed higher/lower/equal labels are not
   taken as a win or as safety. Held-out contents were not used for diagnosis, and repeated
   selection on them is disclosed. Differences in benchmark versions, runner identities or other
   conditions are explained and the claim is limited accordingly; summarizer notices are not
   an automatic verdict about comparability. Final tests
   were not used for selection unless authorized and disclosed as best-of-k. The `changes.md`
   entry matches the runs.

Report each verdict, then findings with evidence and the fix, marked blocking or advisory. Write
the report to `relai/records/reviews/change-<date>.md` if you can write files; otherwise return it.
