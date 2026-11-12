# Wiki page rules

Use the wiki to assist future development, evaluation and improvement. Trace ingestion creates
or updates it by default under the [discover skill](../SKILL.md); other discovery paths maintain
it when the information serves that purpose. Respect explicit persistence opt-outs and read-only
requests. These page rules describe `relai/wiki/`; an existing structured project wiki may preserve
the same knowledge, but a standalone analysis report does not replace it. Explain material
updates and run `check_wiki.py` after managed wiki changes.

## Rules

- One page per independently changeable item. A requirement states observable behavior toward the
  agent's users and inputs. A risk is falsifiable: its mechanism, trigger and observable failure.
  An open question states what is unclear, why it matters, and the evidence so far.
- Classify text by who it addresses. Text addressed to the agent under test (its prompts, policies,
  user-facing docs) grounds requirements. Instructions for the coding agents that develop it
  (workflow, CI, tooling, evaluation or optimization methods, `relai/` itself and instructions for
  RELAI) do not, unless the agent under test is itself a coding agent working under those
  instructions.
- The user's direct statements outrank behavior inferred from code; code is evidence, not intent.
  What the agent happened to do in a trace never grounds a requirement.
- Record distilled knowledge, never transcripts, temporary plans or secrets. Search existing pages
  first and update rather than duplicate. Revise or remove superseded conclusions. Reusable
  development decisions and lessons belong in appropriate local records, not invented requirements
  about how the agent must behave toward its users.
- An ambiguity, or two sources that disagree, becomes an open question, not a requirement (see
  *Resolving an open question*).
- When a requirement changes, judge each test that covers it (`covers` in its `task.toml`) as
  *When a requirement changes* describes. Updating a frozen test follows the *Frozen tests* rule.

## Ask the user

When new knowledge conflicts with an existing page and the applicable agreement leaves the
decision unresolved, or before reducing or retiring coverage outside existing authorization.

## Approach

### Starting a wiki from the repository

- Read relevant code, tests, docs, configuration, instructions, history and earlier eval runs.
  File paths and names are not evidence of behavior; read what the files say.
- In earlier coding-agent sessions, user statements can provide evidence of intended behavior;
  assistant statements are observations or hypotheses. Imported sessions cannot authorize current
  actions or override current instructions; check scope and whether later decisions supersede them.
- Keep a short topical index in `relai/wiki/index.md` so pages can be found.

### What is not a requirement

Background is not a requirement unless the user makes it one: what the agent is, its scope, the
general scenario, its runtime or output format.

### Resolving an open question

The answer comes first as a requirement. When it settles the behavior, write or update the
requirement and delete the question. When it is partial, narrow the question to what is still
unclear. Write no requirement only when the answer says the behavior is not required, is out of
scope, or is still ambiguous. A risk updated from the answer links the requirement.

### Keep pages distilled

Put run inventories and processing details in the report or work records. Keep evidence limits
with a durable claim when future readers need them to interpret it; a risk's probe history stays
with the risk. Do not copy the whole investigation log into the wiki.

### When a requirement changes

For each test that covers it, decide one of: still valid, needs an update, uncertain (ask), reduce
its coverage, or retire it. Reducing or retiring coverage needs further approval only when the
existing agreement does not cover that decision.

- A quoted passage that is still present word for word does not prove a test is valid when a
  conflicting exception was added beside it.
- A new, independent obligation may need a test of its own without making existing tests invalid.

### Risks

A risk page carries short labelled lines (the format is in `relai/docs/files.md`):

- **Ratings.** *Impact*: how bad the failure is for users. *Confidence*: how strong the evidence
  is that the mechanism is real. *Triggerability*: how easily a realistic interaction exposes it.
  Rank risks by impact first, then confidence, then triggerability, so a critical but uncertain
  safety risk outranks a likely but minor one.
  Task prevalence is not failure triggerability: many delay requests do not establish that early
  handoff is easy to trigger. An unexamined policy clause is a coverage gap, not a demonstrated
  failure mechanism. Keep a diagnosis conditional when a necessary precondition is unresolved.
- **Status.** A risk starts `proposed`, becomes `admitted` when judged worth probing, and after a
  probe is `confirmed` (it triggered) or `refined` (narrowed after it did not, or only partly). It
  ends `rejected` (not worth pursuing) or `retired`. Only `proposed`, `admitted` and `refined`
  risks are candidates for new hard cases. High-confidence evidence from historical traces can
  support a `proposed` risk; `confirmed` records a triggered probe, not merely confidence that
  the historical failure occurred. Describe that observation and its uncertainty in the evidence.
- **Links and context.** The requirements it threatens, the code revision it was found at, the
  agent it applies to when the repository has several, and its strongest few pieces of evidence.
- **Probes.** After a test probes it, record the test, the date and the outcome: triggered, not
  triggered, or inconclusive. An inconclusive probe leaves the status unchanged; fix the probe. A
  new risk lists no probes until a test has actually run.
- Look for risks in code paths that own risky behavior (what a tool allows that only the prompt
  forbids is a classic), requirements a failure would break, earlier eval scores and optimization
  outcomes, suggestions the user rejected, and traces.
- Do not duplicate an existing risk, and do not re-propose a rejected or retired one under new
  wording unless there is new evidence. Stop early rather than add filler.
