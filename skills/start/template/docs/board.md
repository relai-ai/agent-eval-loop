# The board: `STATUS.md`

When using managed state, update `STATUS.md` from recorded evidence for the current request.
Run `bin/status.py` first: it writes `STATUS.json` (`files.md`) from the records and prints the
plain-text status that opens every board and checkpoint, so every coding agent shows the same
thing. Record the active stage with `bin/status.py --stage <skill> <n>` when it changes.
Link measurements to the revision they describe; exploratory candidate results are not current
incumbent results. Candidate runs still count toward spend.

Keep it scannable. Always open with three short sections, in this order, then add the other
sections below only when they have content:

```markdown
# RELAI status · <date>
## Now
<the current request and where it stands, in one or two lines>
## Next action
<the single most useful next step, or "Done">
## Waiting on you
<count and the top items, or "Nothing">
```

## Stages

Number the active skill's stages from this table and mark the decision points (★). Each skill's
detail (the risk board, the candidate lineage, the task list) is one line in the journey until
expanded. Where the user has a plan of their own, show both: `Step 5 · eval 6/10`.

| Skill | Stages |
| --- | --- |
| `discover` | 1 Scope · 2 Read sources · 3 Investigate · 4 Write wiki · 5 Review risks and questions ★ · 6 Report |
| `eval` (build) | 1 Scope · 2 Scenarios ★ · 3 Harness (first use) · 4 Build tests · 5 Grader check ★ · 6 Independent review · 7 Freeze · 8 Run · 9 Judge checks and pass mark ★ · 10 Report |
| `eval` (run) | 1 Select · 2 Cost ★ · 3 Run · 4 Judge · 5 Report |
| `improve` | 1 Agreement ★ · 2 Diagnose · 3 Build candidate · 4 Measure · 5 Compare · 6 Keep or reject ★ · 7 Independent review · 8 Deliver |
| `loop` (each iteration) | 1 Gather evidence · 2 Discover · 3 Eval · 4 Improve · 5 Digest ★ |
| `coding-evals` | 1 Pick tasks · 2 Build · 3 Validate · 4 Independent review · 5 User sign-off ★ · 6 Freeze · 7 Pilot run · 8 Full run · 9 Report |
| `review-app` | 1 Build or extend views · 2 The user reviews ★ · 3 Write answers back |

Item states use the same glyphs everywhere, with letters as a fallback: `○` not started or
suspected, `◐` in progress, `●` confirmed, `✓` done or resolved, `✗` rejected or failed,
`⚠` needs attention. Items are risks in `discover`, `eval` and `improve`, tasks in `coding-evals`
and case batches for benchmarks. A change within noise is labelled so, never shown as a gain.

The sections:

- **Current request and progress:** show the relevant capabilities (discovery, harness, tests,
  measurement, improvement) as ready, pending or not applicable. Judge readiness for the selected
  work: an absent wiki does not block regression checks, and a targeted measurement need not run
  every test. An entry in `changes.md` records an attempt, not proof of improvement.
- **Next action:** continue the user's request or resolve its actual missing prerequisite. A
  question blocks only dependent work. Show broader coverage, hardening or new trace analysis as
  optional opportunities, not mandatory next stages. If the request is complete, say so.
- **Background work:** delegated reviewers, readers and runs still in progress, and what each is
  waiting on.
- **Candidates:** for `improve`, the lineage from the current version: each candidate's parent,
  verdict with a one-line reason, the ideas it adds or drops, and its scores against the
  current version. Above about 15 tests, show pass count, mean with spread and moved up, down or
  held counts, and name regressions.
- **Waiting on the user:** consequential decisions, feedback and approvals relevant to the
  request, including nonblocking open questions awaiting resolution or explicit deferral, and
  resource limits. Distinguish actual blockers from choices independent work can proceed without.
  Link explicitly deferred items separately with their revisit context; do not report "Nothing"
  merely because unanswered questions do not block execution. Keep future opportunities visible
  without presenting them as current blockers.
- **Next to answer:** a manageable batch sized by actual judgment effort, using "When the user
  is asked" in `../README.md`, each with its kind (marked blocking where it is), recommendation
  and source, and how many remain. A large table does not automatically count as one small choice.
  Link the same underlying records used in chat and any review app, including a direct review
  view when available; the board summarizes those records rather than maintaining another queue.
- **Wiki:** counts of requirements, risks and open questions, and per risk its impact / confidence
  / triggerability, status, and the tests that probe it (from `covers` and the page's `## Probes`).
- **Tests:** the runner, isolation and pass mark ("not set yet" until it is chosen); per test, its split, whether it is frozen, its
  latest mean against the pass mark, and its recent runs (flaky when they both pass and fail;
  counts as in `../README.md`, *Counts come from records*).
  Per benchmark: development cases played of total, the held-out sample's mean, final-split runs,
  cost per case and fidelity, never case by case. Coverage spans history; performance summaries
  identify their contributing revision. Mixed or unknown revisions retain counts and a notice
  rather than a combined assessment mean.
- **The loop** (from `records/loop/state.json`), if it ran: iterations and what started each,
  verified fixes kept of candidates tried, experiment rounds, regressions prevented, tests added,
  held-out score first to last, the user's decisions and loop spend.
- **Coding evals** (agent-neutral tasks), if any: tasks by kind and source, which are healthy
  (the latest oracle run scored every outcome check at full marks and the latest nop run failed
  the primary check, both on the task as it is now), and the last comparison's solved rate per
  agent or setup with scored/attempted counts. An eval project for coding agents needs no harness:
  its next step is building tasks, then health, freezing and comparing.
- **Judges:** each judge's agreement with the user's judge checks (`feedback.md`).
- **Spend** as runtimes reported it (agent trials including candidates, judges, triage), never
  estimated. Use the active agreement: `records/loop/state.json`'s contract during a loop, otherwise
  `records/improve/plan.json`. Show the applicable ceiling and actual consumption since its `since`
  time, including candidates and delegated work. Missing resource measurements are unknown, not
  zero. Do not invent or duplicate a budget; show recent entries from `changes.md`. For runs,
  copy trial and judge spend from `bin/summarize.py` where it applies (`../README.md`, *Counts come
  from records*), and add spend it does not read: paid helper calls outside runs from
  `records/spend.jsonl`, and triage from its own records.

Lengths of history and the agreement threshold are in `../README.md`, Defaults.

## Cleanup

Mention cleanup when it is due, and do it only with the user's agreement: a rejected candidate's
worktree under `work/candidates/<name>/` once `changes.md` records it (`git worktree remove`, then
`git worktree prune`); run directories under `work/runs/` that no baseline or report still cites;
and container images built for tests that are no longer used (the engine's image commands).
Never delete `records/`, `changes.md`, `decisions.md` or runs a current claim relies on.
