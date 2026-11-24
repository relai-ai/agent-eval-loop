# Evaluate your team's coding agent

[Back to README](../README.md)

Start with the [README walkthrough](../README.md#coding-agents-your-team-uses), expanding the
full walkthrough beneath the starter request. This guide covers task design and setup.

## Task sources and grading

The `coding-evals` skill turns your team's work into long-horizon tasks that any coding agent can run:

```text
Use RELAI's coding-evals skill to make a test from PR #412 in {repo-name}
Use RELAI's coding-evals skill to check whether our new CLAUDE.md helps on our tasks
```

- **From your real work.** Build tasks from a corrected coding session, pull request, revert or past fix in git history. Each task begins at the commit where the work started; the real fix is kept out of the workspace.
- **Any agent can run it.** Harbor installs the agent under test; the task brings the repository and its toolchain.
- **Your standards.** Draft "good" from CLAUDE.md, AGENTS.md, contributing guides, lint configuration and past review comments; when building a set, RELAI can also check the judges against how your maintainers reviewed recent pull requests. You confirm it.
- **Checks beyond task success.** Use hidden tests, existing tests as regression checks, and checks for edited tests, out-of-scope changes, unsafe work and claims that do not match what happened. A required review judge reads your repository to check that each fix sits where the behavior is owned and builds on what the codebase already has.
- **Comparable results.** Lead with five headline metrics (Solved, Merge-ready, Codebase fit, Trustworthy, Cost · Time) with their noise, and the tasks that separate the agents or setups being compared. Merge-ready and Trustworthy have fixed definitions ([comparing](../skills/coding-evals/references/comparing.md)); you can add your own yes-or-no marks per check.

Coding-agent evals live in an *eval project*: a repository whose `relai/` holds the tasks. Task source can come from the current or other scoped repositories; each evaluated workspace contains only its starting history.

## What happens, step by step

RELAI shows these stages at each checkpoint and when a long step starts, with the current one
marked. Its main questions
come with the task list (with a run plan when paid runs are planned: which agents and models, how
they sign in, attempts per task and the pilot's estimated cost), at your sign-off on the
reviewed checks, and after the pilot for the full-run budget unless a budget you set already
covers it; the [project contract](../skills/start/template/README.md#working-with-the-user) lists
every point. Every stage uses your coding agent's own session (the independent review is an
extra agent in it); the last column shows spending beyond that session.

| Stage | What RELAI does | Spends beyond your session? |
| --- | --- | --- |
| 1. Pick tasks | Finds candidate pull requests, sessions or fixes and shows you a task list | No |
| 2. Build | Writes each task (workspace at the start commit, request, hidden tests) | No |
| 3. Validate | Checks, with no model, that the real fix gets full marks, the untouched code fails the main check (the task's hidden tests) and a different correct fix also passes | No |
| 4. Independent review | A reviewer that did not build the task checks it, alongside stage 3; RELAI resolves what it finds | No |
| 5. Your sign-off | You (or a reviewer you delegate to) approve the reviewed checks once, with how the judges scored past pull requests when calibrated | Judge calls in API mode, when calibrating |
| 6. Freeze | RELAI freezes the tasks; later changes need a recorded reason and a fresh review | No |
| 7. Pilot run | One trial per agent or setup compared measures cost and time and confirms the setup loaded | Yes, agent runs |
| 8. Full run | The remaining runs, within your budget | Yes, agent runs |
| 9. Report | The headline metrics, cost and time per run, and what separated the agents or setups | Judge calls in API mode: the review judge makes up to about 20 calls per attempt while it reads the repository |

## Choose an eval project

The eval project can be the source repository or a separate repository. RELAI presents the
tradeoffs and recommends one from your context; you choose. Keeping evals beside the product
makes ownership convenient. A separate project can collect tasks across repositories and keep
large task artifacts apart from product code. A task's starting history must exclude the eval
project so earlier tasks and their answers cannot leak into the evaluated workspace.

## Interpret the results

Start by measuring the coding agent as your team uses it. Compare another model, version,
setup or agent when requested. Report the headline metrics (Solved, Merge-ready, Codebase fit,
Trustworthy, Cost · Time) with their uncertainty, and cases that distinguish the setups. Hidden tests and process checks provide evidence;
the verifier shares the container and is not isolation against a root-level attacker.
See [evaluation and review](evaluation-and-review.md) for frozen measurements, approvals and
limitations, and [installation requirements](installation.md#requirements) for runner setup.

## Data and credentials

- **Where tasks live:** each task holds your repository's history up to the commit where the task starts. Tasks stay where you choose, private to the eval project by default.
- **What is redacted:** session text quoted in tasks and trace excerpts kept in the wiki have secrets and personal data removed.
- **What model providers see:** the providers you configure receive what they need to run the agent, judge it and triage traces, including trajectories, and for the review judge, files of your repository at each task's start commit and the agent's changes. The example judge and triage scripts remove only secret values before sending, not personal or customer data, and RELAI tells you before the first such call.
- **Hosted runners:** only if you authorize one, it may also receive source, tasks, logs and build material. Running locally avoids that.
- **Credentials:** helper scripts read the named keys themselves; the coding agent never sees their values.
