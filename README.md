<h1 align="center">agent-eval-loop</h1>

<p align="center">
  <b>Eval-driven improvement for AI agents:</b> build evals first, then improve your agent against them.
</p>

<p align="center">
  A plugin for Claude Code, Codex and other coding agents, by RELAI (<i>Reliable AI</i>). No CLI, server or account.
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/workflow-dark.svg">
    <img alt="RELAI workflow: discover maps the behavior, eval builds the evals, improve makes measured changes, and loop learns, tests, fixes and repeats" src="assets/workflow-light.svg" width="100%">
  </picture>
</p>

<p align="center">
  <a href="#quickstart"><img alt="Claude Code plugin" src="https://img.shields.io/badge/Claude%20Code-plugin-2e7d57"></a>
  <a href="#quickstart"><img alt="Codex plugin" src="https://img.shields.io/badge/Codex-plugin-2e7d57"></a>
  <img alt="Agent Skills" src="https://img.shields.io/badge/Agent%20Skills-compatible-2e7d57">
  <img alt="Harbor tasks" src="https://img.shields.io/badge/evals-Harbor%20tasks-555">
</p>

---

## Two ways to use it

- **🤖 Agent applications and business workflows.** The agents you build and ship, whatever
  framework they use. RELAI builds evals from your traces, or generates them from the agent's code,
  docs and risks, then improves prompts, tools, workflow, memory or model, keeping a change only
  when the evals show it helped and the guardrails held.
- **🏭 Coding agents and software factories.** The coding agents your team uses: Claude Code, Codex,
  OpenHands or your own setup of one. RELAI turns your coding sessions, pull requests and git history
  into tasks any coding agent can run, then shows whether a new model, CLAUDE.md, skill or agent
  actually helps on *your* code.

## Quickstart

### 1. Install the plugin

Pick your coding agent below. Claude Code, Codex and Antigravity install RELAI as a native
plugin, and Gemini CLI installs its skills directly. Other agents load its six skills
(`start`, `discover`, `eval`, `improve`, `loop`, `coding-evals`) from their skills folder. Copy
each skill's whole folder: skills use the files bundled next to their `SKILL.md`.

<details>
<summary><b>Claude Code</b></summary>

In Claude Code:

```text
/plugin marketplace add relai-ai/agent-eval-loop
/plugin install relai@relai-local
```

Or from a shell:

```bash
claude plugin marketplace add relai-ai/agent-eval-loop
claude plugin install relai@relai-local
```

For local development, load a checkout directly:

```bash
claude --plugin-dir /path/to/agent-eval-loop
```

</details>

<details>
<summary><b>Codex</b></summary>

Install as a native Codex plugin:

```bash
codex plugin marketplace add relai-ai/agent-eval-loop
codex plugin add relai@relai-local
```

For local development, add your checkout as the marketplace instead:

```bash
codex plugin marketplace add /path/to/agent-eval-loop
codex plugin add relai@relai-local
```

</details>

<details>
<summary><b>Cursor</b></summary>

```bash
git clone https://github.com/relai-ai/agent-eval-loop.git ~/agent-eval-loop
mkdir -p ~/.cursor/skills && cp -R ~/agent-eval-loop/skills/* ~/.cursor/skills/
```

For one project only, copy into `.cursor/skills/` in that project. Reload Cursor afterwards.

</details>

<details>
<summary><b>Antigravity</b></summary>

Install as a native Antigravity plugin:

```bash
agy plugin install https://github.com/relai-ai/agent-eval-loop.git
```

Or from a local clone:

```bash
git clone https://github.com/relai-ai/agent-eval-loop.git
agy plugin install ./agent-eval-loop
```

Run `agy plugin list` to check that it is active.

</details>

<details>
<summary><b>Gemini CLI</b></summary>

Install the skills from the repository:

```bash
gemini skills install https://github.com/relai-ai/agent-eval-loop.git --path skills
```

Or from a local clone:

```bash
git clone https://github.com/relai-ai/agent-eval-loop.git
gemini skills install ./agent-eval-loop/skills/
```

Add `--scope workspace` to install for the current project only.

</details>

<details>
<summary><b>Windsurf</b></summary>

```bash
git clone https://github.com/relai-ai/agent-eval-loop.git ~/agent-eval-loop
mkdir -p ~/.codeium/windsurf/skills && cp -R ~/agent-eval-loop/skills/* ~/.codeium/windsurf/skills/
```

For one project only, copy into `.windsurf/skills/` in that project.

</details>

<details>
<summary><b>OpenCode</b></summary>

```bash
git clone https://github.com/relai-ai/agent-eval-loop.git ~/agent-eval-loop
mkdir -p ~/.config/opencode/skills && cp -R ~/agent-eval-loop/skills/* ~/.config/opencode/skills/
```

For one project only, copy into `.opencode/skills/` in that project.

</details>

<details>
<summary><b>GitHub Copilot</b> (CLI, cloud agent and IDE agent mode)</summary>

```bash
git clone https://github.com/relai-ai/agent-eval-loop.git ~/agent-eval-loop
mkdir -p ~/.copilot/skills && cp -R ~/agent-eval-loop/skills/* ~/.copilot/skills/
```

For one project, or for the cloud agent, copy into `.github/skills/` in that repository. In
Copilot CLI, run `/skills reload` to pick them up without restarting.

</details>

<details>
<summary><b>Kiro</b> (IDE and CLI)</summary>

```bash
git clone https://github.com/relai-ai/agent-eval-loop.git ~/agent-eval-loop
mkdir -p ~/.kiro/skills && cp -R ~/agent-eval-loop/skills/* ~/.kiro/skills/
```

For one project only, copy into `.kiro/skills/` in that project.

</details>

<details>
<summary><b>Other coding agents</b></summary>

Any agent that supports [Agent Skills](https://agentskills.io) can load RELAI: copy the folders
under `skills/` into that agent's skills directory. Many agents also read `~/.agents/skills/` or a
project's `.agents/skills/`.

</details>

To update a copied install, run `git -C ~/agent-eval-loop pull` and copy the skills again. Skills folder
locations were checked against each agent's documentation in November 2026; if one has moved,
your agent's docs list the current location.

### 2. Choose where to start

For an agent application or business workflow, open its repository and ask:

```text
Use RELAI's discover skill to map this agent's behavior and where it can fail
```

Or start from production traces:

```text
Use RELAI's loop skill to improve this agent from ./traces;
optimize task success and cost
```

For a software factory, open an eval project and ask:

```text
Use RELAI's coding-evals skill to mine ../api for tasks from the last six months,
then compare our coding agents
```

### 3. Follow the request

RELAI checks the prerequisites needed for the task, names missing credentials and reuses existing runners and tests. It uses your project's credential mechanism or `relai/.env`; coding agents never read credential values, while executable helpers use them for authentication and redaction.

You can start at any skill without completing the full workflow.

## See one complete example

> **Before publishing:** Add one real example from the current OSS product showing:
>
> 1. the source requirement, trace or coding session;
> 2. the EvalsWiki entry created by `discover`;
> 3. one generated eval and its grader;
> 4. the recorded baseline;
> 5. the output of one `improve` or `coding-evals` run.
>
> Use actual repository files and results. Do not use illustrative or fabricated output.
> The repository currently includes helper scripts and test fixtures, but no linked source → wiki → eval/grader → baseline → improvement run with recorded results.

## Why RELAI

- **Evals are the hard part. RELAI builds them.** Evals come from traces, or are generated from what the agent must do and where it can break, including risks that never appeared as failed runs. You review them; you do not write them.
- **Realistic, long-horizon environments.** Evals are [Harbor](https://github.com/harbor-framework/harbor)-format tasks: the agent runs end to end in a container, with its tools, data and as many steps as the work takes. Your project's own runner works too.
- **Scores you can inspect.** Code checks and LLM judges are reviewed and frozen before the first run. RELAI reports variation, supports optional held-out evals and separates infrastructure or judge errors from agent results.
- **The same evals support improvement and comparison.** Run the current agent, record a baseline and compare candidate changes, agents, models or setups against the same frozen evals.
- **You stay in charge.** You approve the risks, evals, graders, objective and budget. RELAI asks only when your judgment is needed.

## How it works

| Step | What happens | What you decide |
| --- | --- | --- |
| **`start`** | Routes the request, initializes useful records when justified and shows relevant progress. | Where to begin when the goal is unclear. |
| **`discover`** | Builds the **EvalsWiki** from code, documentation and traces: requirements, ranked risks and open questions. | Which risks matter; answers to open questions. |
| **`eval`** | Builds evals from traces, generates them from the wiki's risks or brings in an existing benchmark. Evals use Harbor tasks or suitable project-native equivalents, graded by code checks and LLM judges, then reviewed and frozen. | Which evals to build; whether the graders score the way you would. |
| **`improve`** | Runs the agent against the evals and compares scoped changes against the recorded baseline for an agreed behavioral, cost or latency objective. | The objective, what may change and the budget. |
| **`loop`** | Repeats discover → eval → improve when new traces, answers or tests arrive. | The goal, scope, budget and limits; then real ambiguity or safety calls. |
| **`coding-evals`** | Mines coding sessions, pull requests and git history for tasks any coding agent can run, then compares agents and setups on them. | Which agents and repositories; which tasks to build; whether the checks score the way you would. |

When RELAI-managed state is useful, `relai/STATUS.md` shows the current request, relevant progress, what is waiting on you and the recommended next step.

## Agent applications and business workflows

### Discover from code, documentation and traces

`discover` builds the EvalsWiki: what the agent must do, where it can fail and what remains unclear.

Point it at production traces and the coding agent can use focused checks, existing analytics, direct reading or scalable model triage for the question and budget. External processing requires appropriate data and cost authorization.

The optional triage example groups leads into three lanes:

- **Needs your judgment:** likely failures whose correct outcome is unclear. Your answer can become a regression eval or risk evidence.
- **Coverage gaps:** situations real users encounter that no eval covers, ranked by frequency.
- **Weak signals:** small slips that did not fail a run, informing harder or compound eval proposals.

Durable findings update EvalsWiki when they help future work. The wiki is not a transcript archive or a checklist of artifacts.

### Bring your own benchmark

```text
Use RELAI's eval skill to bring in the benchmark at ../bench-x
(its own runner and scorer, train/validation/test)
```

RELAI first checks a small pilot against the benchmark's own scorer. It respects the benchmark's splits: fixes are learned from train, validation decides what is kept, and test is reserved for final assessment. The benchmark is pinned to its commit and never edited.

## Coding agents and software factories

The `coding-evals` skill turns your team's work into long-horizon tasks that any coding agent can run:

```text
Use RELAI's coding-evals skill to make a test from PR #412 in acme/api
Use RELAI's coding-evals skill to check whether our new CLAUDE.md helps on our tasks
```

- **From your real work.** Build tasks from a corrected coding session, pull request, revert or past fix in git history. Each task begins at the commit where the work started; the real fix is kept out of the workspace.
- **Any agent can run it.** Harbor installs the agent under test; the task brings the repository and its toolchain.
- **Your standards.** Draft "good" from CLAUDE.md, AGENTS.md, contributing guides, lint configuration and past review comments; you confirm it.
- **Hard to game.** Use hidden tests, existing tests as regression checks, and checks for edited tests, out-of-scope changes, unsafe work and claims that do not match what happened.
- **Comparable results.** Report solved rate with its noise, cost per solved task and the tasks that separate the agents or setups being compared.

Coding-agent evals live in an *eval project*: a repository whose `relai/` holds the tasks. Task source can come from the current or other scoped repositories; each evaluated workspace contains only its starting history.

## Improve and repeat

An iteration begins with new traces, answers, tests or existing evidence. The coding agent adapts, reorders, combines or skips activities to fit the request:

```text
1. learn    triage new traces → EvalsWiki + proposed evals
2. measure  establish or reuse comparable evidence for the objective and guardrails
3. explore  investigate, measure or make a scoped change
4. check    run scope-based checks and optional held-out evals; review the results
5. record   what was learned, results, fixes kept or rejected, and spend
```

An experiment can investigate or collect evidence without producing a patch. Baseline reuse requires comparable source and measurement conditions. During an iteration, measurement meaning and relevant comparison conditions stay stable; budget and authorization remain binding. Supporting tooling can improve within the agreed scope. Changes to evaluation meaning, coverage or acceptance criteria need controlled repair and comparable evidence. The coding agent asks before broadening the assignment or resolving a consequential choice your agreement does not cover; a faster feedback runner alone does not establish a faster agent.

The OSS workflow provides scoped evidence for comparison. It does not establish universal correctness or prove that every possible regression has been prevented.

## You remain in control

`relai/STATUS.md` can show:

- what is waiting on you and RELAI's recommended answers;
- every risk and the eval that probes it;
- recent runs, with flaky ones flagged;
- how often each LLM judge agrees with you;
- spend against the approved budget;
- iterations, observed results and the decisions still needed from you.

Questions wait for a natural decision point: the end of `discover`, the first time LLM judges are scored or the summary of a loop iteration. Only a blocking safety call or conflicting requirement interrupts dependent work.

## Built to be inspected

- Evals are frozen before comparison, with fresh-context reviews of the harness, evals and changes.
- Measurement effort is chosen for the decision; "too few attempts to tell" is a valid result.
- Optional held-out evals can be scored without reading their contents while improving the agent.
- Infrastructure and judge errors are reported separately from agent results.
- You preview how each judge grades before freezing it, and agreement is tracked.
- Tests use shared metadata and result contracts through Harbor or a native runner, with instructions for rerunning the suite, including in CI.

## Requirements

- **Python 3.11+** for bundled checkers and reference scripts; project-native integrations are supported.
- **Harbor execution:** [uv](https://docs.astral.sh/uv/) and a locally supported container engine with a Docker-compatible CLI, or Podman.
- **Native execution:** the project or benchmark runner's own prerequisites; unused Harbor or container tools are not required.
- **Model access** for the agent, simulated users and judges, through your project's credential mechanism or `relai/.env`.

The generated `relai/README.md` lists the prerequisites for each runner (see the [bundled contract](skills/start/template/README.md)).

## FAQ

<details>
<summary>Does RELAI run my agent on my machine?</summary>

Containers are the default. Running on the host requires explicit authorization and reviewed sandboxing. Integrations use the real entrypoint and current source.

</details>

<details>
<summary>What is the difference between an open question and feedback?</summary>

An open question asks how the agent should behave in general. Your answer becomes a requirement in the wiki. Feedback asks about one specific run or judge score. Your answer can become a regression eval or evidence on a risk.

</details>

<details>
<summary>Can coding-agent tasks leak our code?</summary>

Each task holds the repository up to the commit where it starts. Tasks stay where you specify, private to the eval project by default. Quoted session text is redacted of secrets and personal data. Configured model providers receive relevant agent inputs, traces and trajectories for execution, judging and triage. Separately authorized hosted runners or builders may also receive source, tasks, logs and build material; local execution avoids that hosted transfer. The selected integration makes destinations and side effects explicit. Excerpts kept in the wiki are redacted; executable helpers read named credentials without exposing their values to the coding agent.

</details>

<details>
<summary>What does it cost?</summary>

You pay for model calls from the agent, simulated users and judges. RELAI estimates the cost before a paid run, and the board tracks spend against the budget you set.

</details>

<details>
<summary>Can I use the results without the plugin?</summary>

Yes. Tests run through Harbor or a native runner. Bundled checkers are standard-library Python, and the integration records how to rerun the suite.

</details>

<details>
<summary>Will it change my code?</summary>

`improve` changes behavior within existing or newly agreed scope, by default on a separate branch for review. Evaluation setup can also make small integration changes, such as recording hooks or tooling exclusions. Material project edits are disclosed and must be covered by your authorization; setup is not permission for unrelated changes.

</details>

## What's inside

```text
relai/
├── skills/
│   ├── start/         # the relai/ template and checkers
│   ├── discover/      # requirements, risks, open questions, trace triage
│   ├── eval/          # harness, test design, hardening, mocks, benchmarks, running and scoring
│   ├── improve/       # regression checks, agent-chosen experiments, cost and latency
│   ├── loop/          # contract, new evidence, iterations and experiment rounds
│   └── coding-evals/  # agent-neutral tasks for coding agents: sources, checks and comparison
├── examples/          # example launcher, judge, triager and native-runner scripts
├── tests/             # tests for the checkers and examples
├── DESIGN.md          # the design and the reasons behind it
└── README.md
```

Once set up, the repository gets a `relai/` folder. Its contract is in `relai/README.md` (template: [skills/start/template/README.md](skills/start/template/README.md)).

## Contributing

Issues and pull requests are welcome. Run the checker tests with:

```text
python3 -m unittest discover -s tests
```

Tests that build images require a running Docker-compatible engine or Podman and are skipped without one. The reasoning behind each design choice is in [DESIGN.md](DESIGN.md).
