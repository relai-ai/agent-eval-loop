---
name: start
description: Orient the user when they ask how to use RELAI or what to do next, or initialize RELAI records when a selected workflow needs them. Route an already clear request directly to the appropriate skill, reusing existing project infrastructure.
---

# Start here

RELAI helps teams understand and improve agent behavior. Choose the smallest useful workflow:

- [discover](../discover/SKILL.md): requirements, risks and open questions from code, docs or traces.
- [eval](../eval/SKILL.md): build missing evaluations, reuse a benchmark, or measure current behavior.
- [improve](../improve/SKILL.md): a direct fix, regression check, or measured behavioral, cost or latency improvement.
- [loop](../loop/SKILL.md): coordinate ongoing learning and experiments under one agreement.
- [coding-evals](../coding-evals/SKILL.md): agent-neutral coding tasks from sessions, pull requests
  and history, including for a custom coding agent developed here.

## Route before setting up

Inspect the request and existing project tests, runners and results. A deterministic fix or a
regression check using project tests goes directly to `improve`; that handoff completes this skill
without requiring evaluation setup or a board. Maintain durable knowledge when useful as the
[knowledge policy](template/README.md#maintain-useful-knowledge) describes; a small task may yield
a valuable constraint or lesson. Do not ask the user to choose a step they already requested.
Other workflows reuse working infrastructure and initialize only the RELAI artifacts they need.

For shared terms, knowledge maintenance and user interaction, read the relevant sections of the
project's `relai/README.md`, otherwise the bundled [terms](template/README.md#terms),
[knowledge policy](template/README.md#maintain-useful-knowledge) and
[user interaction guidance](template/README.md#working-with-the-user). Plugin methods are linked from each skill; `relai/`
paths refer to project artifacts, not files inside the plugin.

## Initialize or recover managed state when needed

- A README beginning `<!-- relai` identifies RELAI state. If an unrelated folder occupies `relai/`,
  explain the collision and ask how to resolve it. Do not move or overwrite it; another state root
  is not currently supported by these workflows.
- When initialization is needed and authorized, copy [template/](template/) to the repository's
  `relai/`, skipping caches, and rename `gitignore` to `.gitignore`. Explain what will be added;
  ask only when existing instructions do not authorize it.
- If setup was interrupted, restore missing template files needed for the selected work. Preserve
  project modifications. If an existing file is incompatible with the needed operation, explain
  the difference and resolve that file rather than silently replacing the project copy.
- This is orientation and setup: do not run a model or container here. Name a credential only
  when a later step needs it, using the project's existing credential mechanism where suitable.

## Orient and hand off

When using managed state, read its contract and update `relai/STATUS.md` using the
[board contract](template/docs/board.md). Show the current request, relevant progress, pending
decisions and the useful next action. Missing optional stages are not prerequisites.

Start the already requested skill. If the goal remains unclear, offer the relevant choices with
a recommendation. This skill is complete when the request has been routed, or the user understands
the project's relevant state and next action; setup and a board are required only on the managed-state path.
