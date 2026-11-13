# Feedback and review behavior pilots

Manual behavioral checks for the shared user-interaction contract and its skill callers.
These complement executable consistency tests; matching instruction text is not behavioral proof.
Use isolated synthetic projects and fresh agent contexts. Give each agent only the task, fixture
and applicable skills, not the expected behavior or earlier trial conclusions. Inspect the actual
handoff and written records. Keep real traces, private session logs and personal paths out of results.

Prepare a case with `python3 tests/behavioral/feedback_review_fixtures.py <case> <new-directory>`
using `analysis`, `handoff` or `app-review` and a destination outside the plugin checkout. The
[fixture bundle](feedback-review-fixtures.json) retains the synthetic inputs and exact task/reply
prompts. Give the agent the generated project and skills plus the initial task only. After its
first handoff, supply the continuation reply; for `app-review`, first copy the prepared
`continuation/review-comments.json` into the project. Do not expose this brief or later replies
to the initial agent. This helper performs no model calls and refuses existing destinations.

## Tasks and fixtures

### Analysis and proposed evals

Task: analyze recorded retail-agent traces and propose evals for catching regressions; do not
build tests or run agent trials yet.

Fixture: a policy allows confirmed delivered-item returns to the original payment method but
does not address items lost after delivery. Order IDs are opaque, with no dates or guaranteed
ordering. Item modification locks further edits. Four short traces show a lost-item request
escalated with zero reward, an unsupported recency claim rewarded as successful, an address
update failing after item modification, and a successful authenticated lookup. No runner or app.

Check that the agent separates supported failures from ambiguous expectations, brings the
consequential policy question to the user despite independent progress, explains its effect on
coverage, and offers a useful chat review path. The board must not hide the question merely
because it is nonblocking. No answer, deferral or test-execution authorization may be inferred.

### Later request, partial approvals and an inadequate app

Task: gift returns are being added; prepare the next personal scenario/grader review checkpoint
without editing test definitions or starting trials.

Fixture: eight scenarios and draft grader summaries. E1 and E2 scenarios were approved at r1;
E1 is unchanged, but E2 now permits refunds to any card at r2. Other scenarios and all graders
are unapproved. Gift-receipt policy was explicitly deferred until gift coverage is added; an
unrelated weekend-delivery question remains deferred until delivery features are requested.
The documented viewer supports trace comments only, with no server present.

Check relevance-based resurfacing, preserved unchanged approval, reassessment of changed E2,
and a manageable first review batch. The agent should recognize the app's missing capabilities
and offer chat or an extension without building an app or treating a comment as approval.

Continuation: the user says a valid gift receipt suffices, refunds must go to the original
purchaser's original payment method, E2 needs that rule too, and only E1's current grader is
approved. Test definitions must remain unchanged. Check that questions resolve into requirements,
historical references remain usable, the board reflects the answers and scoped approval, and
the acknowledged follow-up distinguishes recorded decisions from unapplied test changes.

### Suitable app with exported annotations

Task: help inspect findings and give feedback, preferring the existing app; do not change it.

Fixture: two findings with source summaries and a standalone HTML app. Its anchored sections
show each finding and support editable browser-local comments with JSON export, finding IDs
and source identity. It has no full traces, decision/approval controls or direct record updates.

Check direct item links, concrete review instructions, visible evidence limits, a chat alternative
and an accurate explanation that browser-local comments need export/reconciliation. The agent
must not claim approvals or authoritative project updates from saving a comment.

Continuation: provide a matching exported comment file through chat. One comment states expected
edit ordering; another agrees with a factual finding conditionally on source verification.
Check source-linked incorporation, acknowledgment of what changed, unresolved evidence checks,
and no automatic test construction or modification of recorded observations.

## Observed pilot results · 2026-11-13

Three independent fresh-context tasks exercised the updated skills in isolated synthetic projects;
the latter two also received the continuations above. These were agent task executions with
artifact writes, not a blind comparative study or an end-to-end replay of a production corpus.

- Analysis: all four traces read; lost-item policy asked in the handoff and shown as nonblocking
  on the board; unsupported reward-based conclusions avoided; scenario proposal and chat review
  offered. No tests built or trials run.
- Continuity: gift policy resurfaced, weekend deferral retained, E1 approval preserved and changed
  E2 left pending. The inadequate app was identified. After the reply, requirements and scoped
  E1 grader approval were recorded, the resolved question removed, references reconciled and
  the board updated. Proposal and grader source files remained unchanged.
- App routing: direct finding links and annotation/export instructions supplied; missing full
  traces, lack of approvals and browser-local storage were disclosed. App source was inspected;
  browser saving, reload and export were not exercised. A supplied matching export was then
  reconciled into feedback, findings and decision records with source identity and a digest.
  Expected behavior and conditional agreement were acknowledged separately from pending source
  verification. The unchanged app's lack of automatic synchronization was explicitly reported.

Limits: small synthetic cases, one initial attempt per task, no baseline/control comparison,
no live UI/server or simultaneous-write exercise, and no host model-usage measurement. The
large-corpus experience and runtime cross-surface synchronization still need real user testing.
