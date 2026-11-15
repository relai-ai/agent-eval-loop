<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/hero-dark.svg">
    <img alt="agent-eval-loop by RELAI. Build evals first, then improve your agent against them. The loop: discover maps the behavior, eval builds the evals, improve makes measured changes, then repeat." src="assets/hero-light.svg" width="100%">
  </picture>
</p>

<p align="center">
  <b>Eval-driven improvement for AI agents.</b><br>
  A plugin for Claude Code, Codex and other coding agents, by RELAI (<i>Reliable AI</i>).
</p>

<p align="center">
  <a href="#installation"><img alt="Claude Code plugin" src="https://img.shields.io/badge/Claude%20Code-plugin-d97757?style=flat-square&labelColor=1b2430&logo=claude&logoColor=white"></a>
  <a href="#installation"><img alt="Codex plugin" src="https://img.shields.io/badge/Codex-plugin-5b7fff?style=flat-square&labelColor=1b2430"></a>
  <a href="#installation"><img alt="Agent Skills compatible" src="https://img.shields.io/badge/Agent%20Skills-compatible-2e9d6e?style=flat-square&labelColor=1b2430"></a>
  <a href="https://github.com/harbor-framework/harbor"><img alt="Evals are Harbor tasks" src="https://img.shields.io/badge/evals-Harbor%20tasks-d98a1f?style=flat-square&labelColor=1b2430"></a>
  <a href="LICENSE"><img alt="License: Apache 2.0" src="https://img.shields.io/badge/license-Apache%202.0-de5d4f?style=flat-square&labelColor=1b2430"></a>
  <a href="https://github.com/relai-ai/agent-eval-loop/discussions"><img alt="GitHub Discussions" src="https://img.shields.io/badge/community-discussions-8b6fd6?style=flat-square&labelColor=1b2430&logo=github&logoColor=white"></a>
</p>

<p align="center">
  <a href="#installation"><b>Install</b></a> ·
  <a href="#two-ways-to-use-it">Use cases</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#why-relai">Why RELAI</a> ·
  <a href="#faq">FAQ</a> ·
  <a href="DESIGN.md">Design</a>
</p>

---

## Two ways to use it

You can start at any step; you don't need to run the whole workflow.

### AI agents you build

https://github.com/user-attachments/assets/53ce7659-21f8-4f42-897e-a5e3cc4d1ffa

For agents you build and deploy, on any framework. Run these requests from the agent's
repository:

**1. Discover where it can fail**

```text
Use RELAI's discover skill to read this agent's code, prompts and the traces
in ./traces, and tell me where it is likely to fail
```

This creates an **EvalsWiki** in `relai/wiki/`: the agent's requirements, its risks ranked with
evidence, and questions about intended behavior that the code doesn't answer.

**2. Turn the risks into evals**

```text
Use RELAI's eval skill to build tests for the top five risks and get a baseline
```

This creates tests that run your agent end to end, graders you review before they are frozen,
and a baseline score for each risk.

**3. Improve without regressions**

```text
Use RELAI's improve skill to fix the failing tests without breaking the passing ones.
You may change prompts and tools, not the model
```

This creates a branch with the change, scores before and after on the same frozen tests, and a
record of the changes it tried and rejected.

To keep improving the agent as new traces arrive:

```text
Use RELAI's loop skill to keep improving this agent from ./traces;
optimize task success first, then cost
```

### Coding agents your team uses

https://github.com/user-attachments/assets/c8002907-e339-4679-9328-246a66a2bea1

For Claude Code, Codex, OpenHands or your own setup of one. Measure whether a new model,
CLAUDE.md or skill improves results on your own repositories instead of a public benchmark.
Run these requests from an eval project (a repository that holds the evals):

**1. Turn past work into evals**

```text
Use RELAI's coding-evals skill to build 20 evals from the last six months of
merged pull requests and reverts in {repository}
```

This creates evals in [Harbor](https://github.com/harbor-framework/harbor) format that any coding
agent can run. Each eval starts at the commit before the original fix, includes the repository and
its toolchain, and is graded by hidden tests and checks that the original fix passes.

**2. Evaluate your coding agent**

```text
Use RELAI's coding-evals skill to evaluate Claude Code on these evals and report
the solved rate and cost per solved task
```

**3. Improve your setup before you roll it out**

```text
Use RELAI's improve skill to improve our CLAUDE.md and skills against these evals
```

This creates a branch with the improved setup and reports, before and after, the solved rate
with its noise, the cost per solved task and the evals where the two setups differ.

RELAI drafts the grading criteria from CLAUDE.md, AGENTS.md, contributing guides, lint
configuration and past review comments, and you confirm them. Besides the hidden tests, each eval
runs the repository's existing tests as regression checks and flags edited tests, out-of-scope
changes, unsafe actions and claims that don't match what the agent did.

## Installation

### Claude Code

```bash
claude plugin marketplace add relai-ai/agent-eval-loop
claude plugin install relai@agent-eval-loop
```

### Codex

```bash
codex plugin marketplace add relai-ai/agent-eval-loop
codex plugin add relai@agent-eval-loop
```

Start a new session after installing. Codex asks you to review and trust the optional hooks
before they run.

<details>
<summary><b>Other agents, Skills CLI, and manual installation</b></summary>

**Skills CLI** (requires Node.js/npm):

```bash
npx skills add relai-ai/agent-eval-loop --skill '*'
```

Choose your coding agent when prompted. This installs into the current project; add `-g` for
all projects. Install all seven skills together, because they reference each other.
This method includes templates and checkers; for the optional scripts in
[`examples/`](examples/) and optional [hooks](hooks/), use a native plugin install or a full clone.

**Antigravity:**

```bash
agy plugin install https://github.com/relai-ai/agent-eval-loop.git
```

**Gemini CLI:**

```bash
gemini skills install https://github.com/relai-ai/agent-eval-loop.git --path skills
```

Add `--scope workspace` for the current project only.

**Manual installation:** clone once, then copy all seven skill folders into your agent's skills
directory. For agents that read `.agents/skills/`, run from your project:

```bash
git clone https://github.com/relai-ai/agent-eval-loop.git ~/agent-eval-loop
mkdir -p .agents/skills
cp -R ~/agent-eval-loop/skills/* .agents/skills/
```

Other project directories: `.cursor/skills/` (Cursor), `.windsurf/skills/` (Windsurf),
`.opencode/skills/` (OpenCode), `.github/skills/` (GitHub Copilot), `.kiro/skills/` (Kiro).
Copy each skill's whole folder, including the files next to `SKILL.md`, then reload your agent.

</details>

<a id="updating"></a>
<details>
<summary><b>Updating</b></summary>

Update using the same method and scope you installed with, then start a new session. Read the
[release notes](https://github.com/relai-ai/agent-eval-loop/releases) for migration steps.

| Installation | Update |
| --- | --- |
| Claude Code plugin | Enable auto-update for **agent-eval-loop** in the plugin manager's Marketplaces tab (off by default), or run `claude plugin marketplace update agent-eval-loop`. |
| Codex plugin | Run `codex plugin marketplace upgrade agent-eval-loop` and verify the installed version; use the plugin manager's install controls if it remains stale. |
| Skills CLI | Run `npx skills update`; keep all seven RELAI skills together. |
| Manual copy | Run `git -C ~/agent-eval-loop pull`, then copy the complete skill folders again, preserving local edits. |

Commands were checked with Claude Code 2.1.284 and Codex CLI 0.160.0. `main` can contain
unreleased changes; pin a tag where supported for a fixed release. Plugin updates do not replace
existing project files in `relai/` or frozen tasks; see the
[project-copy policy](skills/start/template/docs/upgrades.md).

</details>

## How it works

Not sure where to begin? Ask *"Use RELAI's start skill to look at this agent and suggest a first
step."* It reads your repository and recommends one. It doesn't run your agent or call any model
besides your coding agent.

| Skill | What it does | What you decide | Needs |
| --- | --- | --- | --- |
| **`start`** | Finds the right starting skill for your request and sets up `relai/` only if the task needs it. | Where to begin when the goal is unclear. | nothing |
| **`discover`** | Builds the **EvalsWiki** in `relai/wiki/` from code, documentation and traces: requirements, ranked risks and open questions. | Which risks matter; answers to open questions. | your code, optionally traces |
| **`trace-review`** | Builds or adapts a review app in your project, on your own stack, for reading traces and leaving feedback that is saved and linked to the step it refers to. | Review verdicts, expected behavior and the requested decisions. | your traces |
| **`eval`** | Builds evals from traces, generates them from the wiki's risks or brings in an existing benchmark, graded by code checks and LLM judges, then reviewed and frozen. | Which evals to build; whether the graders score the way you would. | a runner (Harbor or your own), model keys |
| **`improve`** | Compares scoped changes against the recorded baseline for an agreed behavioral, cost or latency objective, on a branch. | The objective, what may change and the budget. | working evals (built on the way if missing) |
| **`loop`** | Repeats discover, eval and improve as new traces, answers or tests arrive, choosing which of them each round needs. | The goal, scope, budget and limits; later, only ambiguous or safety-related choices. | working evals (built on the way if missing) |
| **`coding-evals`** | Mines coding sessions, pull requests and git history for tasks any coding agent can run, measures the team's agent on them and, when asked, compares setups or agents. | Which repositories and tasks; whether the checks score the way you would; what to compare. | Harbor, access to your repositories |

Bundled checkers and scripts need **Python 3.11+**. Running Harbor tasks needs
[uv](https://docs.astral.sh/uv/) and a container engine with a Docker-compatible CLI, or Podman.
RELAI reuses your existing runners, tests and credentials. The generated `relai/README.md`
([template](skills/start/template/README.md)) lists the prerequisites for each runner.

## Why RELAI

- **RELAI writes the evals.** It builds them from traces, or generates them from the agent's requirements and risks, including risks that haven't caused a failed run yet. You review the evals instead of writing them.
- **Evals run the whole agent.** Each eval is a [Harbor](https://github.com/harbor-framework/harbor) task: the agent runs end to end in a container, with its tools and data, for as many steps as the task needs. You can use your project's own runner instead.
- **You can check every score.** You preview the code checks and LLM judges before they are frozen, and a reviewer with fresh context checks the harness, evals and changes. Reports include noise ("too few attempts to tell" is a possible result) and keep infrastructure and judge errors separate from agent failures. Held-out evals are optional.
- **Comparisons use fixed evals.** Tests, graders and run conditions don't change while a change is measured, so the baseline and every candidate change, agent, model or setup are scored the same way. If a test is wrong, RELAI fixes it in a recorded change and measures the baseline again.
- **You approve the decisions.** You approve the risks, evals, graders, objective and budget; RELAI asks for input only at defined points ([full list](skills/start/template/README.md#working-with-the-user)). `relai/STATUS.md` shows what is waiting on you, each risk and the eval that tests it, recent runs with flaky ones flagged, how often each judge agrees with you, spend against your budget and the recommended next step.

## FAQ

<details>
<summary>Can I bring my own benchmark?</summary>

Yes. RELAI first checks a small pilot run against the benchmark's own scorer, then keeps its
splits: fixes are learned from train, validation decides what is kept, and test is reserved for
the final assessment. The benchmark is pinned to its commit and never edited.

```text
Use RELAI's eval skill to bring in the benchmark at {path-to-benchmark}
```

</details>

<details>
<summary>Does RELAI run my agent on my machine?</summary>

By default it runs your agent in a container. It runs the agent directly on your machine only if you authorize that and approve the sandboxing. In both cases it calls your agent's own entrypoint with the current source.

</details>

<details>
<summary>Can coding-agent tasks leak our code?</summary>

- **Where tasks live:** each task holds your repository's history up to the commit where the task starts. Tasks stay where you choose, private to the eval project by default.
- **What is redacted:** session text quoted in tasks and trace excerpts kept in the wiki have secrets and personal data removed.
- **What model providers see:** the providers you configure receive what they need to run the agent, judge it and triage traces, including trajectories. The example judge and triage scripts remove only secret values before sending, not personal or customer data, and RELAI tells you before the first such call.
- **Hosted runners:** if you authorize one, it also receives source, tasks, logs and build material. Running locally avoids this.
- **Credentials:** helper scripts read the named keys themselves; the coding agent never sees their values.

</details>

<details>
<summary>How do I stop or pause a long run or a loop?</summary>

Tell the coding agent to stop (or interrupt it). Progress is saved as it goes: finished trials,
the loop's iterations and decisions are in `relai/`, so asking it to continue later resumes from
there rather than starting over. A watch-mode loop runs on a schedule you set up with your host's
scheduler or cron; remove that schedule to stop it for good.

</details>

<details>
<summary>What does it cost?</summary>

The coding agent running RELAI (Claude Code, Codex, …) uses your plan or API tokens while it reads, builds and reviews; `start`, `discover`, `trace-review` and building coding-evals tasks use only that. Eval runs add model calls from the agent, simulated users and judges. RELAI estimates the cost before a paid run, and `relai/STATUS.md` tracks spend against the budget you set.

</details>

<details>
<summary>What do the optional hooks do?</summary>

The native Claude Code and Codex installs include hooks that act only in a project with a
`relai/` folder. Before an edit to a frozen test, Claude Code asks you (Codex warns the coding
agent instead), and after an edit under `relai/` the project's checkers run. Disable the plugin
or decline to trust the hooks in Codex to turn them off. The checkers still catch the same
problems when the coding agent runs them.

</details>

<details>
<summary>Can I use the results without the plugin?</summary>

Yes. Tests run through Harbor or a native runner, bundled checkers are standard-library Python,
and the integration records how to rerun the suite. Your project's `relai/` folder keeps working
if you remove the plugin.

</details>

<details>
<summary>Will it change my code?</summary>

`improve` changes your agent only within the scope you agreed to, on a separate branch by default. Setting up evals can also make small integration changes, such as adding hooks that record runs or excluding `relai/` from tool configuration. RELAI tells you about any significant edit to your project and makes it only if you authorized it. Approving setup doesn't approve unrelated changes.

</details>

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup,
validation, and review guidance, and follow our [code of conduct](CODE_OF_CONDUCT.md).
Report suspected vulnerabilities privately using [SECURITY.md](SECURITY.md).
Ask questions and share examples in [Discussions](https://github.com/relai-ai/agent-eval-loop/discussions).
