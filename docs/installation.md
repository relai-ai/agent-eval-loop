# Installation and maintenance

[Back to README](../README.md)

Install all seven skills together. Start with the method for your coding agent;
only install execution tools when your task needs them.

## Native plugins

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

## Other agents

**Skills CLI** (requires Node.js/npm):

```bash
npx skills add relai-ai/agent-eval-loop --skill '*'
```

Choose your coding agent when prompted. This installs into the current project; add `-g` for
all projects. Install all seven skills together so their cross-references stay available.
This method includes templates and checkers; for the optional scripts in
[`examples/`](../examples/) and optional [hooks](../hooks/), use a native plugin install or a full clone.

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

## Updating

Update using the same method and scope you installed with, then start a new session.
Read [release notes](https://github.com/relai-ai/agent-eval-loop/releases) for migration steps.

| Installation | Update |
| --- | --- |
| Claude Code plugin | Enable auto-update for **agent-eval-loop** in the plugin manager's Marketplaces tab (off by default), or run `claude plugin marketplace update agent-eval-loop`. |
| Codex plugin | Run `codex plugin marketplace upgrade agent-eval-loop` and verify the installed version; use the plugin manager's install controls if it remains stale. |
| Skills CLI | Run `npx skills update`; keep all seven RELAI skills together. |
| Manual copy | Run `git -C ~/agent-eval-loop pull`, then copy the complete skill folders again, preserving local edits. |

The Skills CLI and manual copies need explicit updates. Native refresh policies are described
in the [Claude Code](https://code.claude.com/docs/en/plugins/install#keep-plugins-updated) and
[Codex](https://developers.openai.com/plugins/build/plugins) docs; commands were checked with
Claude Code 2.1.284 and Codex CLI 0.160.0 on 2026-11-11. Internal installs need repository read
access. `main` can contain unreleased changes; pin a tag where supported for a fixed release.

Plugin updates do not replace existing project files in `relai/` or frozen tasks. Use the
[project-copy policy](../skills/start/template/docs/upgrades.md) to preserve adaptations and evidence.

## Hooks

The native Claude Code and Codex installs include optional hooks, active once the plugin is enabled
(Codex asks you to trust them first). They do nothing outside a project with a `relai/` folder.
Before an edit to a frozen test, Claude Code asks you; Codex cannot ask from a hook, so it warns the
coding agent instead. After an edit under `relai/`, the project's checkers run and report problems
to the agent. To turn them off, decline to trust them in Codex, or disable the plugin
(`claude plugin disable relai@agent-eval-loop`); Claude Code's `disableAllHooks` setting also works
but turns off every hook. The guarantees they surface still hold through the checkers.

## Uninstalling

| Installation | Uninstall |
| --- | --- |
| Claude Code plugin | `claude plugin uninstall relai@agent-eval-loop`, then optionally `claude plugin marketplace remove agent-eval-loop` |
| Codex plugin | `codex plugin remove relai@agent-eval-loop` |
| Skills CLI | Use the Skills CLI's remove command, or delete the seven RELAI skill folders it installed |
| Manual copy | Delete the seven skill folders you copied, and `~/agent-eval-loop` |

Commands were checked with Claude Code 2.1.322 and Codex CLI 0.167.1. Uninstalling leaves your
projects' `relai/` folders untouched; they keep working without the plugin.

**Removing RELAI from a project.** Remove candidate worktrees first (`git worktree list`, then
`git worktree remove` for those under `relai/work/candidates/`, and `git worktree prune`), delete
review branches you no longer want (`git branch --list`), then delete `relai/`. Keep
`relai/records/`, `changes.md` and `decisions.md` elsewhere if you want the history of what was
approved and tried. Container images built for tests can be removed with your engine's image
commands.

## Requirements

- **Python 3.11+** for bundled checkers and reference scripts; project-native integrations are supported. The optional hooks run the `python3` first on your `PATH`: with an older one (such as macOS's built-in 3.9) frozen tests are still guarded, but edits are not checked automatically, and the hook says so once.
- **Harbor execution:** [uv](https://docs.astral.sh/uv/) and a locally supported container engine with a Docker-compatible CLI, or Podman. Tasks with a restricted network also need the engine's image builder (`docker buildx` on a Docker CLI).
- **Native execution:** the project or benchmark runner's own prerequisites; unused Harbor or container tools are not required.
- **Model access** for the agent, simulated users and judges, through your project's credential mechanism or `relai/.env`.

The generated `relai/README.md` lists the prerequisites for each runner (see the [bundled contract](../skills/start/template/README.md)).

## Troubleshooting

After installing or updating, start a new coding-agent session. If skills are missing, check
that all seven complete skill folders were installed in the intended project or global scope.
Skills CLI and manual installs do not include all optional examples and hooks; use a native
install or full clone when you need them.

If an eval cannot run, ask the coding agent to check the selected runner's prerequisites and
credential names. Harbor needs a running supported container engine; a native runner uses its
own prerequisites. Keep credential values out of chat. The project's generated `relai/README.md`
records its runner-specific setup.
