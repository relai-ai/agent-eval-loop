# The board: `STATUS.md`

When using managed state, update `STATUS.md` from recorded evidence for the current request.
Link measurements to the revision they describe; exploratory candidate results are not current
incumbent results. Candidate runs still count toward spend. Show relevant sections:

- **Current request and progress:** show the relevant capabilities (discovery, harness, tests,
  measurement, improvement) as ready, pending or not applicable. Judge readiness for the selected
  work: an absent wiki does not block regression checks, and a targeted measurement need not run
  every test. An entry in `changes.md` records an attempt, not proof of improvement.
- **Next action:** continue the user's request or resolve its actual missing prerequisite. A
  question blocks only dependent work. Show broader coverage, hardening or new trace analysis as
  optional opportunities, not mandatory next stages. If the request is complete, say so.
- **Waiting on the user:** open questions, proposed risks, pending feedback items, unfrozen tests,
  a judge flagged for low agreement, and a spent budget.
- **Next to answer:** a manageable batch sized by actual judgment effort, using "When the user
  is asked" in `../README.md`, each with its kind (marked blocking where it is), recommendation
  and source, and how many remain. A large table does not automatically count as one small choice.
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
