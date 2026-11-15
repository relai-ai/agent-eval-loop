# Agent instructions

Before changing this plugin, read [DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md) and follow it.
For the current architecture and its rationale, see [DESIGN.md](DESIGN.md).

## Write in clear, plain language

Write the README, docs and skills for a technical reader who is new to this plugin. Say what
the plugin does and what the user gets, in specific terms.

- **Plain words over slogans.** Write "RELAI writes the evals; you review them", not "Evals are
  the hard part. RELAI builds them." Avoid marketing words (seamless, powerful, robust,
  realistic, game-changer) and phrases that flatter the reader ("questions only you can
  answer").
- **Name who acts.** Prefer "you preview the judges" or "RELAI repairs the test" over passive
  sentences with no actor ("judges are previewed", "a test is repaired openly").
- **No rhetorical patterns.** No "not X, it's Y" contrasts, runs of short dramatic sentences,
  aphorisms ("the yardstick holds still"), forced groups of three or empty "from X to Y" ranges.
- **Define project terms once,** then use the same word each time. Don't switch between
  synonyms for one thing.
- **Punctuation and formatting.** Use commas, colons, periods or parentheses instead of em
  dashes. Use bold only where a reader scans for it, and don't put emojis in headings.

## Keep the README focused

The README should help a new reader understand RELAI, choose a use case, install it and make
one useful first request. Aim for 1,000–1,200 readable words, about 5–6 minutes at an assumed
200 words per minute, excluding linked guides and videos. This is an editorial target, not
a hard limit or a claim about observed reading speed. Count visible prose, tables and code
examples; exclude markup and link destinations when estimating reading time.

Keep essential information about cost, data movement, authorization and evaluation limits
visible. Put detailed workflows, alternative setup methods and review procedures in top-level
`docs/` guides, with descriptive links from the relevant README section. Preserve linked anchors
when moving content. Project contracts remain authoritative in `skills/start/template/`; link
to them rather than maintaining competing rules in the guides.

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
