# Scope: the eval project

## The repository

A repository of its own (recommended) or a folder in an existing one, set up with the
[start skill](../../start/SKILL.md). Make it private when tasks hold private code. It needs no
application-agent harness: Harbor installs supported coding agents. A custom coding agent needs
a suitable installer/adapter that executes the real agent and preserves the task/result contract;
inspect existing support before proposing new integration work. A team's setups (instruction
files, skills, hooks, MCP configuration) live under `relai/setups/<id>/`, laid out as in a repository root.

## Find out first

- **The agent in use** and its model, version and setup, from the team's machines and
  repositories (installed version, instruction files, skills, configuration).
- **How it authenticates**: a subscription login or an API key. Harbor accepts both for some
  agents (the [Harbor notes](../../eval/references/harbor-notes.md)).
- **Whether each source repository is public**, from its remote and hosting service. It decides
  contamination (a public fix may be in training data), whether the fix can be fetched during a
  run, and whether tasks could ever be shared. Ask only when it cannot be told.
- **Draft standards and never-do's** from the team's instruction files (CLAUDE.md, AGENTS.md),
  CONTRIBUTING, README, pull request templates, lint and CI configuration, and recent review
  comments, each with its source.

## Ask what is still open at the scope checkpoint

Show what you found as a short list (the agent, its version and authentication, which
repositories are public, the drafted standards), then ask only what remains open, following
"Working with the user" in `relai/README.md`:

1. **What to compare.** Recommend: the agent as the team uses it now, against the change they are
   considering (a model, a version, an instruction-file edit, a skill or hook) or a bare setup.
   Comparing other agents is optional; offer it, never assume it. When the user wants it, list
   each agent the same way, and whether to compare them bare or each with a matched setup
   ([comparing](comparing.md), *Comparing agents*).
2. **Source repositories** tasks may come from, and the **kinds of work** that matter, when the
   request does not say.
3. **Network**, only when some source is public: open by default; offer to restrict tasks whose
   fix can be found online.
4. **Where task code may live**, only when it could leave this repository: this repository only
   (default) or shareable. Never assume shareable.
5. **Budget** per comparison, with the cost model: trials = tasks × versions compared × attempts,
   at a cost (or plan usage and time) per trial measured on one task before any larger run.

Corrections to the drafted standards count as answers. With a subscription, say that runs count
against the plan's usage limits and that the user should check the plan allows automated runs;
it is information, not a question. The pass mark is asked after the first comparison.

For example, when models and sign-in methods remain open for a two-agent comparison:

> I'll give Codex and Claude the same repository instructions so the comparison is fair.
> Task code will stay in this private repo, and both agents will have internet access.
>
> **Which model should each agent use?** Name one for Codex and one for Claude, or choose
> “decide before running.”
>
> **How should each agent sign in for evaluation runs?** Existing subscription accounts
> (using each plan's allowance), API keys (incurring API charges), or decide before running.
> You can choose differently for each agent. I can build the tests while these choices remain open.

This illustrates presentation, not fixed defaults: use the discovered facts and agreed scope.
Keep installed versions in the setup summary unless they affect the choice.

## Record

- `[coding_evals]` in `relai.toml` (`relai/docs/files.md`), and every answer in `decisions.md`.
- The approved standards and never-do's as requirement pages under the
  [discover skill](../../discover/SKILL.md)'s rules, one per item, citing its source.
- **The shared evaluators** under `relai/evaluators/` (the eval skill's
  [shared evaluators](../../eval/references/shared-evaluators.md)): `safe-process`,
  `honest-report`, and `review-ready`, whose rubric lists the approved standards ([checks](checks.md)), plus any check the team
  wants on every task. Each task copies them; changing one is a change to every frozen task that
  carries it, under the freeze rule.

Route by the artifact and execution required, not source location. Use coding-evals for
agent-neutral coding tasks, including a custom coding agent developed here. Use the
[eval skill](../../eval/SKILL.md) for application-agent scenarios and harness evaluation.
