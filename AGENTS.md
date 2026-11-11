# Agent instructions

Before changing this plugin, read [DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md) and follow it.
For the current architecture and its rationale, see [DESIGN.md](DESIGN.md).

## Stay portable across users' setups

The plugin runs inside whatever coding agent, toolchain and machine the user has. Guidance and
shipped code must not assume one of them (principles 11 and 12).

- **Any coding agent.** Do not write agent-specific invocation syntax, such as `/plugin:skill`
  slash commands. Refer to a skill by name ("the `eval` skill"); users start skills with a
  plain-language request.
- **No pinned tool versions in the plugin.** The plugin never names a version of a tool it
  runs, such as Harbor. At setup, the coding agent records the latest stable release in the
  user's project (`[harbor].version` in `relai.toml`), and every run and checker uses that.
  Upgrading is a recorded measurement change, never a silent float. Tests of the plugin
  itself may use a fixed fixture version.
- **Any container engine the tool supports.** Do not require Docker itself. Write for any
  engine with a Docker-compatible CLI (Docker Desktop, OrbStack, Colima, Rancher Desktop) or
  Podman, as Harbor supports. Checkers detect a running engine rather than assume one.
- **No fixed architecture.** Do not pin a CPU architecture or `--platform`. The machine that
  runs a test, local or cloud, decides it.
- **Version-specific notes say which release they were checked against.** When a note
  describes a tool's behavior, such as `skills/eval/references/harbor-notes.md`, name the
  release it was observed in, and re-check it before relying on it with a newer release.
