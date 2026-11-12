# Triage a large trace set

Use when exhaustive reading is not justified by the question, scale or budget. Reuse suitable
project tooling or choose an approach that preserves trace references, coverage and failures.
The optional [triage example](../../../examples/triage.py), with
[judge.py](../../../examples/judge.py) beside it, can be copied to `relai/bin/` and adapted or
replaced in the project's language. Its three lanes are a useful starting point, not mandatory
categories:

| Lane | What it is | Where it goes |
| --- | --- | --- |
| A. Needs judgment | Likely failures, and runs whose right outcome the wiki does not settle | `relai/feedback.md`, resolved in risk review |
| B. Coverage gaps | Situations real users bring that no test covers | Test proposals for the [eval skill](../../eval/SKILL.md) |
| C. Weak signals | Problems short of failure and signals that co-occur | Near-miss evidence and compound test proposals |

## Choose useful processing

Inventory the selected set and reuse available summaries or mechanical checks from
[trace auditing](trace-audit.md). Check authorization only against the target's actual rules;
heuristics cannot establish that an unconfirmed action was unauthorized or that an unmatched
number was invented. Do not build a generic audit-script suite as a prerequisite.

For substantial work, follow [adaptive investigation and deliberate blind-spot review](trace-investigation.md):
use new mechanisms to revise checks and selection, including unflagged episodes inside familiar
traces. Keep the finding inventory distinct from the shortlist.

Choose a pilot and inspect its output against the source traces before scaling an unfamiliar
method. Revise the method if it misjudges outcomes or invents signals. Supply relevant target
policy and requirements when judging behavior; unresolved expectations remain uncertain.

Before paid processing or sending trace text to a provider, check the existing agreement for
cost and data authorization. Ask only for what it leaves open, naming the provider, material
sent and estimated spend. Say plainly that personal or customer data in the traces goes to the
provider as recorded unless you remove it first: the example removes only declared secret values.
Redaction does not itself authorize external processing.

## If using the example

- Normalize once to JSONL: `{"id", "trace": [{"role", "content", "tool_calls"?}, ...], "meta": {...}}`.
  Keep stable ids so incremental runs skip completed traces. The example resumes by id only;
  use a fresh ingest or adapt it when source content, policy or analysis assumptions change. Keep
  the adapter and normalized input under `relai/work/discover/<ingest-id>/`.
- The example needs `[triage]` with a cheap model in `relai.toml`; it never falls back to
  `[judge]`. Provide policy using `--context-file`. `estimate --input traces.jsonl` estimates
  tokens (and dollars with `--price-in`/`--price-out`); `run --limit 20` runs a pilot; `run --yes`
  processes the remaining traces once the user has approved the cost (without `--yes`, a run larger
  than the pilot stops before any call). Errors are recorded in `errors.jsonl`
  and retried by rerunning; they are not verdicts.
- `--max-chars` bounds each trace's model input, keeping its head and tail with an omission
  marker. Treat these as partial views, disclose truncation, and inspect the full source before
  relying on a lead. Adjust the bound or processing strategy when omitted material matters.
- `report --ingest <id>` writes `triage.md` and `lanes.json`. These remain leads, not evidence;
  the agent may regroup or prioritize them for the request.

## Verify leads and coverage

Read the source trace before promoting a lead to a feedback item, risk or test proposal. Check
relevant passages in context; do not infer what an omitted section contains. For coverage gaps,
verify representative traces before proposing tests. For recurring or co-occurring signals,
use checked excerpts and [wiki evidence rules](wiki-rules.md) before raising confidence or
proposing [compound tests](../../eval/references/hardening.md).

Inspect a justified sample in full across relevant task types, flagged and apparently successful
runs to look for misses. Choose its size and strata for the decision; this does not require
reading every trace after triage. Report selected and processed counts, errors, full reads,
sampling rationale, truncation and unresolved or unexamined material. A completed triage is not
an exhaustive correctness judgment.

Lead the handoff with findings, uncertainty and useful next decisions. Report why investigation
stopped and what credible signals or coverage remain unexamined. Maintain structured EvalsWiki
under the [ingestion default](../SKILL.md), respecting read-only requests and explicit opt-outs;
distill checked findings rather than copying the triage report into wiki pages. Keep raw-trace reports under `relai/work/`
or equivalent local work records; commit only checked, redacted excerpts under the applicable
authorization.
