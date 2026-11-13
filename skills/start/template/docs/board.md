# The board: `STATUS.md`

When using managed state, update `STATUS.md` from recorded evidence for the current request.
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

The sections:

- **Current request and progress:** show the relevant capabilities (discovery, harness, tests,
  measurement, improvement) as ready, pending or not applicable. Judge readiness for the selected
  work: an absent wiki does not block regression checks, and a targeted measurement need not run
  every test. An entry in `changes.md` records an attempt, not proof of improvement.
- **Next action:** continue the user's request or resolve its actual missing prerequisite. A
  question blocks only dependent work. Show broader coverage, hardening or new trace analysis as
  optional opportunities, not mandatory next stages. If the request is complete, say so.
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
  latest mean against the pass mark, and its recent runs (flaky when they both pass and fail).
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
  zero. Do not invent or duplicate a budget; show recent entries from `changes.md`.

Lengths of history and the agreement threshold are in `../README.md`, Defaults.

## Cleanup

Mention cleanup when it is due, and do it only with the user's agreement: a rejected candidate's
worktree under `work/candidates/<name>/` once `changes.md` records it (`git worktree remove`, then
`git worktree prune`); run directories under `work/runs/` that no baseline or report still cites;
and container images built for tests that are no longer used (the engine's image commands).
Never delete `records/`, `changes.md`, `decisions.md` or runs a current claim relies on.
