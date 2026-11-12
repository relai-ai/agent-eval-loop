# Scope: the eval project

## The repository

`relai/` in the repository the tasks come from, or in a separate repository or a folder outside
the source repository, set up
with the [start skill](../../start/SKILL.md). Neither is the default; choose from what you found:

- **The source repository** suits tasks from it alone, with modest history, owned with the code.
  Keep `relai/tests/` out of its own test collection and CI (hidden tests are copies of its
  tests). Tasks must start before `relai/` was committed, or the workspace would carry other
  tasks' hidden tests, fixes and bundles (`check_task.py` refuses such a bundle); fresh tasks from
  recent work then need a separate place.
- **A separate repository or outside folder** suits tasks from several repositories, an eval set owned or
  shared apart from the code, tasks that must stay away from the agents and CI working on the
  product, a public product repository with private task code, or history too large to repeat
  in it. Make it private when tasks hold private code.

Each task carries the history up to its start ([task-format](task-format.md), step 2), so size
one bundle before proposing many. When the facts point one way, state the choice and why in a
line with the findings; when they do not, or the choice matters, ask at the scope checkpoint
with a recommendation. It needs no
application-agent harness: Harbor installs supported coding agents. A custom coding agent needs
a suitable installer/adapter that executes the real agent and preserves the task/result contract;
inspect existing support before proposing new integration work. A team's setups (instruction
files, skills, hooks, MCP configuration) live under `relai/setups/<id>/`, laid out as in a repository root.

## Size it to the request

Start with what the request needs and grow the scope when later requests need more. A test from
one pull request or session needs the source repository, where task code may live, and standards
drafted from the instruction files and contributing docs at hand, shown with the task list rather
than in a round of their own. Mining review comments, other repositories and kinds of work suits
a request to mine a repository or build a set. The agent's model, version and authentication wait
for the first paid run. Adding standards to a shared evaluator later changes frozen tasks that
carry it, under the freeze rule; new tasks pick it up.

## Find out first

- **Which agent is under test.** When a source repository builds an agent itself (OpenHands, the
  team's own) and the request does not say, ask whether to evaluate the coding agent the team
  works with on it, or the agent it builds; the second may belong to the
  [eval skill](../../eval/SKILL.md) (below). The answer changes every task's purpose.
- **The agent in use** and its setup (instruction files, skills, configuration) from the team's
  repositories; its model and installed version before the first paid run.
- **How it authenticates**, before the first paid run (building calls no model): a subscription
  login or an API key. Harbor accepts both for some agents (the
  [Harbor notes](../../eval/references/harbor-notes.md)).
- **Whether each source repository is public**, from its remote and hosting service. It decides
  contamination (a public fix may be in training data), whether the fix can be fetched during a
  run, and whether tasks could ever be shared. Ask only when it cannot be told.
- **Draft standards and never-do's** from the team's instruction files (CLAUDE.md, AGENTS.md),
  CONTRIBUTING, README, pull request templates, lint and CI configuration, and recent review
  comments, each with its source.

## Ask what is still open at the scope checkpoint

Show what you found as a short list (the agent and its setup, which repositories are public,
the drafted standards), then ask only what remains open, following
"Working with the user" in `relai/README.md`:

1. **Source repositories** tasks may come from, and the **kinds of work** that matter, when the
   request does not say.
2. **Where task code may live** (`task_code`), only when it could leave the eval project's
   repository: `"private"`, kept there (default), or `"shareable"`. Never assume shareable.

When some fix can be found online (a public source, a published release), state the network default with the findings: tasks whose fix can be
found online run without network ([task-format](task-format.md), *The network and web tools*).
Corrections to the drafted standards, or to that default, count as answers. The pass mark is
asked after the first run.

## Ask before the first paid run

These change the runs, not the tasks, so building does not wait for them. Ask when the request
raises them or a paid run is next, unless already answered:

1. **What to measure.** By default, unasked: the agent as the team uses it now (the baseline).
   Compare only when the user names a change (a model, a version, an instruction-file edit, a
   skill or hook) or another agent; after a baseline, you may mention once that these are
   possible. When the user compares agents, list each the same way, and whether to compare them
   bare or each with a matched setup ([comparing](comparing.md), *Comparing agents*).
2. **Budget**, with the cost model: trials = tasks × versions × attempts, at a cost (or plan
   usage and time) per trial measured on one task before any larger run. With a subscription,
   say that runs count against the plan's usage limits and that the user should check the plan
   allows automated runs; it is information, not a question.

For example, when the user asked to compare two agents and models, sign-in and budget remain
open:

> I'll give Codex and Claude the same repository instructions so the comparison is fair.
> Task code will stay in this private repo, and both agents will have internet access.
>
> **Which model should each agent use?** Name one for Codex and one for Claude, or choose
> “decide before running.”
>
> **How should each agent sign in for evaluation runs?** Existing subscription accounts
> (using each plan's allowance), API keys (incurring API charges), or decide before running.
> You can choose differently for each agent.
>
> **Budget:** one trial on one task cost about $0.80; 12 tasks × 2 agents × 3 attempts is about
> $58. Approve up to $60, or name another limit. The tests are already built.

This illustrates presentation, not fixed defaults: use the discovered facts and agreed scope.
Keep installed versions in the setup summary unless they affect the choice.

## Record

- `[coding_evals]` in `relai.toml` (`relai/docs/files.md`), and every answer in `decisions.md`.
- The approved standards and never-do's, each citing its source, in the `review-ready` rubric;
  also as requirement pages under the [discover skill](../../discover/SKILL.md)'s rules when the
  project keeps a wiki or the task set will grow.
- **The shared evaluators** under `relai/evaluators/` (the eval skill's
  [shared evaluators](../../eval/references/shared-evaluators.md)): `safe-process`,
  `honest-report`, and `review-ready`, whose rubric lists the approved standards ([checks](checks.md)), plus any check the team
  wants on every task. Each task copies them; changing one is a change to every frozen task that
  carries it, under the freeze rule.

Route by the artifact and execution required, not source location. Use coding-evals for
agent-neutral coding tasks, including a custom coding agent developed here. Use the
[eval skill](../../eval/SKILL.md) for application-agent scenarios and harness evaluation.
