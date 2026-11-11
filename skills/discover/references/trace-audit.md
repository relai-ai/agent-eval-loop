# Audit traces for the question at hand

Choose checks for the target agent's policies, failure mechanisms and the user's question.
Reuse existing analysis tools, inspect directly, or write focused scripts when scale warrants
them. Script outputs and model flags are leads; cite the source trace after checking it.

## Establish scope and coverage

Inventory enough of the source set to choose useful coverage: stable trace ids, task types,
lengths, endings, errors and available recordings. Existing metadata may already provide this.
For exhaustive work, read every trace in the selected scope untruncated. When that investment
does not fit the question or budget, use [scalable triage](trace-triage.md) instead.

## Check claims against available evidence

Investigate consequential claims about amounts, identifiers, state and completed actions against
the preceding user messages, policy, tool results and other evidence the agent had. Values may
be calculated or derived; absence of a verbatim match does not establish fabrication. Verify
candidate discrepancies in context, including relevant long messages and omitted tails.

## Check actions against actual authority

Derive authorization, identity checks and confirmation obligations from the target's policy and
the user's delegated scope. An earlier instruction can authorize multiple actions; an explicit
confirmation before every write is required only when the applicable rules say so. Likewise,
looking up multiple identities is not itself a violation.

Useful questions include whether the action affects an authorized target, whether ambiguity
needed resolution, and whether a policy restriction relies on the agent because the tool does
not enforce it. Distinguish observed breaches from missing evidence about authorization.

## Follow the behavior through

Look for claims of completion unsupported by actions, ignored tool errors, circular calls,
premature escalation, partial delivery and the downstream action after an earlier failure is
removed. Interpret these against the user's actual goal: an announced action may legitimately
be deferred, and escalation or clarification may be correct.

## Report what was examined

State the scope, checks used, traces processed, traces inspected in full, samples, failures to
process and truncation or other omissions. Link findings to the relevant source passages. A
coverage table is useful when it makes this clearer; do not label unexamined traces clean or
claim that a heuristic absence of flags proves correct behavior.

When reported findings or counts depend on nontrivial analysis code, retain a rerunnable check
under the shared maintenance policy. Reuse or improve existing project assets rather than leave
competing copies. Record its inputs, invocation and limits, distinguishing mechanical results
from leads requiring contextual judgment. Prefer project-native locations; otherwise
`relai/work/discover/<ingest-id>/` can hold local analysis. One-off inspection commands need not
become scripts, and this handoff does not require a generic audit suite.
