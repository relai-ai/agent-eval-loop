# Bring in a benchmark

Import mode runs cases in RELAI's harness, so build it first if it is missing
([harness](harness.md)). Wrap mode does not need it: the benchmark's own runner runs the agent,
so skip the harness and smoke test, declare a native runner, check the prerequisites in
`relai/README.md`, and get the benchmark's own environment working (its setup steps, images and
keys by name). The `eval` skill's rules apply to every case a benchmark adds.

Goal: a benchmark, usually from another repository and often large, scores the agent exactly as
the benchmark itself would, with its splits respected, and a small budget still covers it over time.

## Done when

- `relai.toml` has a `[benchmarks.<id>]` entry (`relai/docs/files.md`): source and
  commit, mode (import or wrap), format or run command, scorer, case id, split and category fields.
- `relai/benchmarks/<id>/README.md` says where the cases come from (repository and commit), how
  they reach the agent, how they are scored, and how the benchmark's splits map to RELAI's roles.
- `python3 relai/bin/benchmark.py init <id> ...` wrote the coverage record, and you showed the
  user the supplied split counts and any proposed held-out sample, its distribution and limits;
  any derived split was explicitly agreed.
- **The fidelity check passed** (`benchmark.py fidelity`): on a small pilot (Defaults), RELAI's
  per-case scores equal the benchmark's own scorer's on the same runs. No score counts before this.
- For import mode, a fresh test review ([review-test](review-test.md)) approved the template and one
  generated case, and `freeze.py` ran on every generated case before its first real run.
- `relai/STATUS.md` shows the benchmark's coverage line.

## Rules

- **The benchmark is read-only and pinned.** Never edit the benchmark repository or its cases;
  handle awkward cases in code. Record the commit. A new benchmark version is a new benchmark id
  (for example `<name>-<short commit>`) with its own coverage record, never mixed with the old.
- **Its scorer is the truth.** When the benchmark has a scorer, apply exactly that, by running it
  or porting its exact logic; never substitute your own. When cases carry a prose rubric and no
  scorer exists, score it with a judge against that column, and say so in the README.
- **Expected outputs go only to the scorer,** never into the agent's input. The agent may not
  read the benchmark repository at run time; the change review checks diffs for case inputs,
  expected answers and case ids.
- **Splits.** Map the benchmark's own splits to RELAI's roles and keep them:

  | Benchmark split | RELAI role | Used for |
  | --- | --- | --- |
  | train | `development` |
  | validation / dev | `held-out` |
  | test | `final` |

  What each role allows is in `relai/README.md`, Terms. Preserve supplied splits. Without splits,
  cases remain development; without a validation split, do not carve out a held-out set automatically. Only when
  explicitly agreed, `benchmark.py init --derive-splits` derives them (proportions: Defaults).
  Existing ledgers remain unchanged.
- **Errors are not scores.** A case that crashed, timed out or broke the benchmark's own
  environment is a runtime failure or evaluator error, reported apart and rerun, never a zero.

## A benchmark given as a link

- Clone it outside the user's repository, under `~/.cache/relai/benchmarks/<name>@<short commit>/`
  (under the home directory, so container mounts see it), at the commit the user
  names or else the default branch's latest, and record it. Never copy the benchmark into the
  agent's repository.
- Before downloading, check its size. Ask first when it is large (Git LFS, separately fetched
  datasets, roughly 1 GB or more) or needs credentials, naming what will be downloaded and where.
- `relai.toml`'s `source` is the link and `commit` the pinned commit; the benchmark's README in
  `relai/benchmarks/<id>/` says where the clone lives and how to recreate it.

## Import or wrap: recommend the fit

- **Import** when the cases are data (CSV, JSONL, a folder of task files) and scoring is per case.
  Generate one task for the declared runner per case under `relai/benchmarks/<id>/cases/<case id>/` from one
  template, so each case is its own frozen, separately scored test whose `[metadata.relai].split`
  is its role. One template serves every case: never branch on a case id. Every field that
  affects a case is used, by the agent's input or by the scorer. Headers and field names are
  arbitrary: read them and choose the mapping yourself.
- **Wrap** when the benchmark brings its own environment and runner (simulators, databases,
  per-task containers) whose results are the source of truth. Write a small adapter under
  `relai/benchmarks/<id>/` that runs the benchmark's own command against the agent checkout being
  measured, for the case ids given, and writes `relai-results.jsonl` into the run directory (one
  attempt per line: `benchmark`, `case`, `split`, `attempt`, `status`, `score` normalized to 0-1,
  `error`, `cost_usd`, `trajectory`, `benchmark_commit`; see `summarize.py`). Keep the
  benchmark's own logs beside it. Map its error states to `runtime failure` or `evaluator error`,
  never to a score. Run it where the benchmark expects to run (its containers, its environment
  variables by name), contained as Fixed rule 3 requires.

## Fidelity first

Run a small pilot, then run the benchmark's own scorer on the same trajectories and write its
scores as JSONL (`{"case", "score"}`). `benchmark.py fidelity <id> <run> --reference <file>`
must report OK. If the benchmark publishes reference results for a known agent, reproduce a few.
A mismatch means the integration is wrong, not the agent: fix it before any other run.

## A small budget on a large benchmark

- When validation cases exist, `benchmark.py init` draws a **fixed held-out sample**
  (`--held-out-n`; Defaults). Size it from the budget and show its resolution and distribution
  limits. Compare candidates and incumbent on the same agreed sample. Without one, compare the
  agreed development targets and guardrails and disclose selection on development evidence.
- `benchmark.py batch <id> --case-ids ...` records the exact development selection, preserving
  order and rejecting unknown/protected or duplicate IDs before changing the ledger. The agent
  chooses size and relevance. It records scheduled cases, not completed runs.
- The optional `benchmark.py batch <id> --n N` strategy gives a suggested **working batch**: mostly development cases never
  played, category-balanced, plus earlier failures to fix and a few earlier passes to recheck.
  Choose scope from the objective, distribution, risks, uncertainty and budget; this helper is not a mandate.
- After every run, `benchmark.py record <id> <run> --agent <revision>` updates the coverage
  record, so the next run, or the next loop iteration, can identify cases not played yet. Coverage
  counts span history; score summaries expose contributing agent revisions and omit combined
  means when those revisions are mixed or unknown. Use revision-specific run evidence for comparisons.
- Run a small split whole rather than sampling it (Defaults).
- Run the final split only under authorization covering its timing, cost and use; ask for any
  uncovered consequential choice rather than repeating an agreed assessment decision. `record`
  counts each final run and the board shows how many there were. Scoring
  several alternatives on it needs explicit authorization, a line in `decisions.md`, and
  disclosure of the best-of-k selection; those results are then no longer independent.

## Ask the user

Ask only about consequential choices the request or agreement leaves open:

- Import or wrap, the split mapping, any derived splits or held-out sample, and batch size,
  with recommendations and the relevant counts and costs.
- Whether to reuse a scorer you found, or how strictly to judge a prose rubric, when the
  benchmark does not say.
- Before a final-split run when its timing, cost or use is outside existing authorization.

## Updating a benchmark

A new version is a new id with a new coverage record and a new fidelity check; report scores on
the two versions separately. Within a version, replace an evaluator rather than removing it, and
fix a failing one rather than deleting it. Never weaken the benchmark to get around a missing
dependency; make the dependency available or ask the user. Never pad the benchmark with invented
cases; if it cannot support what was asked, say what is missing.
