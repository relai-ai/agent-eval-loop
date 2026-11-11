# RELAI: design

This document records the current architecture and its rationale. The
[Plugin Design Principles](DESIGN_PRINCIPLES.md) guide future development.

**Eval-driven improvement for AI agents.** Build evals first, then improve the agent against them.

RELAI is a plugin-only framework: seven skills, a small set of shared checkers, and example scripts
(a launcher, a judge, a trace triager, a native runner) that stay in the plugin until an
integration chooses one, with no CLI and no backend. The user's coding agent builds and runs
everything specific to the user's agent; the plugin fixes what results must look like and what
must stay true, and asks the user wherever a choice is theirs.

## Where things live

| Home | Holds |
| --- | --- |
| `skills/start/template/README.md` (installed as `relai/README.md`) | Shared guarantees and terms, managed layout and checker contracts. Read relevant parts; use the bundled copy when project state is absent |
| `skills/start/template/docs/` | File formats, Harbor and hosted runners, the native trial layout, the board. Read only when the work touches them |
| `skills/start/template/bin/` | The shared checkers, copied into `relai/bin/` and used as they are |
| `skills/<skill>/SKILL.md` | Each skill's routing, prerequisites, completion criteria and essential constraints |
| `skills/<skill>/references/` | Suggested methods and review briefs, linked relative to their caller and loaded only when needed |
| `examples/` | Example scripts, copied into a project only when an integration chooses one |
| `skills/coding-evals/verifier/` | The coding-task verifier (`coding_checks.py`, `test.sh`), copied into each task's `tests/`; used as it is by default, adapted only when its guarantees are kept and its tests pass |

Contracts the user's repository depends on live in the template, so `relai/` stays usable
without the plugin. Methods for the coding agent live in the skills.

## Skills

| Skill | Outcome | Decisions requiring uncovered approval |
| --- | --- | --- |
| `start` | The request is routed, or needed managed state and a useful board exist | none (orientation) |
| `discover` | Requirements, ranked falsifiable risks and open questions, every trace-derived claim cited | Risks reviewed, consequential open questions answered or deferred |
| `trace-review` | A project-owned app for full traces, keyboard navigation, filters and persistent source-linked feedback | External data movement or broader hosting when not already authorized |
| `eval` | Harness (first time), then frozen, reviewed tests that can fail and pass fairly; honest runs that show where the agent stands | Scenarios and grader preview |
| `improve` | Direct fixes with bounded evidence, regression checks, or measured improvement against an agreed objective | Improvement agreement, unless existing instructions cover it |
| `loop` | discover → eval → improve as new evidence arrives, with agent-chosen experiments per iteration | One agreement covers delegated decisions; measurement changes are controlled |
| `coding-evals` | Agent-neutral tasks from real sessions, pull requests and history, healthy (solvable, can fail) and frozen; comparisons of coding agents and setups | Scope, task list and check preview |

These skills are independent entrypoints, not mandatory stages. Existing instructions can supply
or delegate approval; method references do not expand authorization. Examples are optional project
implementations. Project paths such as `relai/docs/files.md` refer to generated artifacts, while
Markdown links to references resolve within the plugin.

## Why it is built this way

Field testing of the full journey (trace ingest, tests, optimization rounds) and user feedback
shaped these choices:

| Choice | Evidence |
| --- | --- |
| A `loop` skill composes the others under one contract and a locked verification kernel, asking only about ambiguity, conflicts, safety or policy | The value is a system that keeps improving with little human time; repeating covered approvals would interrupt a long run |
| A standalone `trace-review` skill builds or adapts a project-owned viewer, leaving the UI stack and trace adapters to the coding agent | Human review needs a working app independently of discovery or eval setup; feedback retains source references without becoming an automatic requirement or score change |
| Few skills, with specialized work (benchmarks, mocks, shared evaluators) as references inside them | Users could not tell which of many skills to use or in what order |
| `start` routes from the request and existing infrastructure, with useful next actions | Without prior RELAI knowledge the user would not know the order |
| Useful knowledge and state in project-owned records, with `relai/` as the default | Users need inspectable context for future development; artifacts are maintained for that value, not as prerequisites to every answer |
| Sign-off on risks, test scenarios, graders and the improvement agreement, each skipped when already agreed | Test scenarios and verifiers felt like a black box; ingest asked nothing; improvement never asked about cost |
| Questions answered in chat with a recommended answer, at set moments, capped per sitting, moot ones closed first | Users did not know whether to edit the Markdown; a large triage could ask dozens at once |
| Trace analysis chooses exhaustive reading or scalable triage, using focused checks where useful | A shortened transcript missed a recurring failure; source verification and explicit coverage matter without mandating full reads at scale |
| The optional triage example groups leads into judgment, coverage gaps and weak signals; projects can adapt the method | Reading every trace does not scale past dozens |
| `feedback.md` for per-run questions, apart from open questions | A user's verdict on a real run is the strongest evidence of expected behavior; it closes once answered, while open questions become requirements |
| Measurement effort chosen per decision, with observations reported as observations | On identical code, single-attempt scores flipped between runs; a "fixed" test passed only because the simulated user phrased its request differently |
| Both-directions tests; checks for what a change unmasks | A change that cut unnecessary transfers had no test where transferring was right, and once escalation stopped, the agent exchanged an item for itself |
| Changes to shared instructions are measured on their other users or scoped | A rule added to instructions shared by every domain conflicted with another domain's policy |
| Project-native or adapted judge providers, with API examples kept optional | The agent ran on OpenRouter; a judge that supported only two providers blocked it |
| Benchmarks imported or wrapped, pinned by commit, and checked for fidelity against their own scorer | A reimplemented scorer that disagrees silently invalidates every result |
| A benchmark's splits map to development, held-out and final, with a coverage record handing out new batches | Repeated keep-or-reject decisions on one set tune the agent to it; small budgets could play only a few cases per run |
| A hardening ladder and compound tests, always as new tests | Passing tests stop teaching; behaviors that hold alone can fail together |
| `changes.md`, with candidate runs kept under `work/candidates/` | Rejected changes and their lessons lived only in scratch notes |
| Shared checkers preserve common guarantees; examples and integrations may be adapted in the project's language | Copied code is a maintained surface; focused verification preserves guarantees without mandating incidental implementation details |
| A separate `coding-evals` skill for the coding agents a team uses, sharing the task format, freezing, reviews, judges and scoring | The other skills speak of "the agent in this repository"; a request about a coding agent in a repository with no agent matched none of them |
| Agent-neutral coding tasks: Harbor installs the agent, the primary check reads the workspace, checks that need a trajectory are "not recorded" when a run has none | A task built around one agent's tools or logs cannot score another, and the oracle has no trajectory |
| The workspace history stops at the start commit and the image fails to build if the fix is present; the network is open by default, restricted by the user's choice where the fix can be found online | Coding agents read history; a leaked fix would inflate every score silently. Most fixes are in private repositories a container cannot reach, and restricting every task would make runs unlike real use |
| One agent by default, comparing changes to its model, version or setup; other agents optional | Teams usually use one coding agent; their question is whether a change helps |
| Standards drafted from the team's files; the judges are shared evaluators; no task template, only the verifier | Asking open-ended questions about "good" ignored what the repository already says. A copied task template would be a maintained surface holding nothing a capable agent cannot write from the contract |
| The verifier trusts only what arrives with `tests/`, in a shared library adapted only with its guarantees kept and its tests rerun | In two rounds of review, an added `conftest.py`, pytest options in `pyproject.toml`, a symlinked `tests/`, a stale `.pyc`, a rewritten start marker, a hostile git config, a planted `reward.json` and a leftover process each defeated an earlier draft |
| The verifier library checks only exact facts and knows no ecosystem; each task names its protected and restored files; what the agent did is judged by `safe-process` | Built-in file lists and command regexes for every ecosystem misfire on specific repositories, and parsing tool names favored the agents whose naming was anticipated |
| A hang or broken test run caused by the agent's change scores 0 | Errors are left out of averages, so counting the agent's own breakage as an error raised its solved rate |

## The loop

The loop's flow is suggested: the agent adapts, reorders, combines, repeats or skips activities
to fit the request and the evidence. An iteration need not include trace intake, new tests or
code changes. Scope, budget, authorization and evidence requirements stay binding: comparable
evidence precedes improvement claims, delivered revisions are verified and independently
reviewed, and changes to measurement meaning go through controlled repair. Improvements to
observability and feedback tooling can support the user's objective within scope; they do not
authorize broader work or establish agent gains by themselves.

`prioritization.md` describes an optional bandit-style way to weigh loss against how little an
item has been measured. It is a suggestion; the agent may explore differently when it judges that
better. Recovery after interruption is instruction-led (reconcile the agreement, checkpoints,
actual source, run artifacts and candidate decisions) rather than a state engine.

Lessons about stalled experiments, mechanism engagement and instruction hygiene are informed by
Anthropic's [hillclimbing guide](https://github.com/anthropics/skills/blob/main/skills/claude-api/shared/evals/eval-hillclimb.md).
Our scope-based verification, optional held-out coverage and authorization boundaries take
precedence.

## Integrity

- **Frozen tests.** `freeze.py` records each test's digest before its first real trial;
  `summarize.py` reports changed or mixed identities as notices while retaining observed numeric differences. The agent judges comparability and limits its claims.
- **Fresh-context reviews** of the harness, each test, and each delivered change, using development evidence or isolated protected assessment, against briefs
  in the skills' `references/review-*.md`.
- **Optional held-out tests**, scored without being read for diagnosis; repeated selection on
  them is disclosed, and final assessment stays separate.
- **The grader preview** shows the user each test's scoring on synthetic and recorded
  trajectories before freezing, without running the agent.

## Known limits

- With few fixed parts, harness and test quality depend on the coding agent and model.
- Held-out tests guard against overfitting only when there are enough comparable tests to hold
  some out.
- Native containment must be demonstrated by the integration; the example launcher supplies none.
- The coding-task verifier shares the agent's container: it catches an agent that works around
  the tests, not one running as root that attacks the toolchain or races Harbor's upload of
  `tests/`.
- Each coding task carries its own copy of the verifier library inside its frozen digest, so
  upgrading the library is a measurement change for every task that takes it.
- Fresh-session hypothetical navigation and UX pilots have been run; real agent improvement and teammate UX remain unvalidated.
- Recovery has documented responsibilities but no automatic reconciliation; priority suggestions
  and observed deltas are not confidence gates.
