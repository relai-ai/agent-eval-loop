# Evaluate your team's coding agent

[Back to README](../README.md)

Start with the [README walkthrough](../README.md#coding-agents-your-team-uses), expanding the
full walkthrough beneath the task-building request. This guide covers task design and setup.

## Task sources and grading

The `coding-evals` skill turns your team's work into long-horizon tasks that any coding agent can run:

```text
Use RELAI's coding-evals skill to make a test from PR #412 in {repo-name}
Use RELAI's coding-evals skill to check whether our new CLAUDE.md helps on our tasks
```

- **From your real work.** Build tasks from a corrected coding session, pull request, revert or past fix in git history. Each task begins at the commit where the work started; the real fix is kept out of the workspace.
- **Any agent can run it.** Harbor installs the agent under test; the task brings the repository and its toolchain.
- **Your standards.** Draft "good" from CLAUDE.md, AGENTS.md, contributing guides, lint configuration and past review comments; you confirm it.
- **Checks beyond task success.** Use hidden tests, existing tests as regression checks, and checks for edited tests, out-of-scope changes, unsafe work and claims that do not match what happened.
- **Comparable results.** Report solved rate with its noise, cost per solved task and the tasks that separate the agents or setups being compared.

Coding-agent evals live in an *eval project*: a repository whose `relai/` holds the tasks. Task source can come from the current or other scoped repositories; each evaluated workspace contains only its starting history.

## Choose an eval project

The eval project can be the source repository or a separate repository. RELAI presents the
tradeoffs and recommends one from your context; you choose. Keeping evals beside the product
makes ownership convenient. A separate project can collect tasks across repositories and keep
large task artifacts apart from product code. A task's starting history must exclude the eval
project so earlier tasks and their answers cannot leak into the evaluated workspace.

## Interpret the results

Start by measuring the coding agent as your team uses it. Compare another model, version,
setup or agent when requested. Report solved rate with its uncertainty, cost per solved task,
and cases that distinguish the setups. Hidden tests and process checks provide evidence;
the verifier shares the container and is not isolation against a root-level attacker.
See [evaluation and review](evaluation-and-review.md) for frozen measurements, approvals and
limitations, and [installation requirements](installation.md#requirements) for runner setup.

## Data and credentials

- **Where tasks live:** each task holds your repository's history up to the commit where the task starts. Tasks stay where you choose, private to the eval project by default.
- **What is redacted:** session text quoted in tasks and trace excerpts kept in the wiki have secrets and personal data removed.
- **What model providers see:** the providers you configure receive what they need to run the agent, judge it and triage traces, including trajectories. The example judge and triage scripts remove only secret values before sending, not personal or customer data, and RELAI tells you before the first such call.
- **Hosted runners:** only if you authorize one, it may also receive source, tasks, logs and build material. Running locally avoids that.
- **Credentials:** helper scripts read the named keys themselves; the coding agent never sees their values.
