# Learn from traces

Goal: answer the trace question, seek broad useful signals and maintain EvalsWiki under the
[ingestion default](../SKILL.md). Every claim cites checked source evidence; retain redacted
excerpts for claims persisted in the wiki.
Page rules are in [wiki rules](wiki-rules.md); trace safety, opt-outs and redaction are in the
[discover skill](../SKILL.md).

## Rules

- Establish the selected source set and useful coverage with [trace auditing](trace-audit.md)
  or [scalable triage](trace-triage.md); reuse the project's inventory where suitable.
  For substantial work use [adaptive investigation and blind-spot review](trace-investigation.md).
- Keep the full finding inventory distinct from the priority shortlist. Repeated examples may
  strengthen an existing finding; do not let them crowd out other mechanisms, lower-priority
  findings or useful uncertainty. Keep unverified leads labelled in work records rather than
  promoting them to requirements or established failures.
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

## Validate exported evidence

Redact structured values before serialization; text substitution over serialized JSON can break
syntax or alter claim-bearing facts. Reopen the final exported artifact using its format parser
and check representative claim-bearing passages against the read-only source. Preserve numeric
values and relationships needed for the claim when permitted; otherwise omit or qualify the
claim rather than silently corrupt the evidence. Keep aliases consistent within the cited batch
and record their scope when cross-batch comparisons would otherwise imply shared identities.

Check redaction against identity-bearing values and context in the original source, including
free text and shortened or transformed identifiers. Checking only the values collected by the
exporter cannot reveal what its collection missed. Preserve ordinary language and claim-bearing
facts when a short identifier also has a common meaning.

Run the existing managed `check_wiki.py` after wiki changes. It checks attachment JSON syntax
as well as wiki links; it cannot certify redaction, factual fidelity or semantic support. Check
those separately, including source references. When reusing an older local checker, inspect its
capabilities and validate any uncovered format with an available parser; do not assume template
updates have upgraded project-owned copies. Fix exports and rerun checks before handoff.
