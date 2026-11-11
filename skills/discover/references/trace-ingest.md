# Learn from traces

Goal: answer the trace question and maintain durable knowledge when it helps future work. Every
claim cites checked source evidence; retain redacted excerpts for claims persisted in the wiki.
Page rules are in [wiki rules](wiki-rules.md); trace safety, opt-outs and redaction are in the
[discover skill](../SKILL.md).

## Rules

- Establish the selected source set and useful coverage with [trace auditing](trace-audit.md)
  or [scalable triage](trace-triage.md); reuse the project's inventory where suitable.
- A requirement needs strong evidence of expected behavior (user feedback, corrections, policies).
- Traces where the agent succeeded only sharpen a risk (see *Evidence for risks*); they never
  raise confidence in it on their own.
- Preserve consequential unresolved expectations as open questions when future work needs them;
  respect a request not to write state. Ask about ambiguity when it affects the next decision,
  while continuing useful independent analysis.

## Evidence for risks

- Ground each pattern in checked source passages. When maintaining it as knowledge, retain a few
  short representative redacted excerpts. Never paste large raw traces into a page.
- A trace where the agent succeeded has a role; say which in its citation: a contrast to a
  failure, the expected path, a precondition, the edge of what triggers the risk, or evidence for
  how to design the evaluator.
- Raise a risk's confidence or triggerability only for something concrete: a mechanism you can
  point to, a fragility, a near miss, inconsistent behavior across similar traces, or recurrence.
