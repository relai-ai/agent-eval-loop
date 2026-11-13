# Contributing to agent-eval-loop

Contributions are welcome: clearer instructions, reproducible bug reports, portability fixes,
examples, and tests of how the skills guide a coding agent all help.

Read our [code of conduct](CODE_OF_CONDUCT.md). Report suspected vulnerabilities privately
using [SECURITY.md](SECURITY.md), rather than an issue or pull request.
See [MAINTAINERS.md](MAINTAINERS.md) for the maintainers and review ownership.

## Find a useful starting point

Ask usage questions in [Q&A](https://github.com/relai-ai/agent-eval-loop/discussions/categories/q-a)
and share examples in [Show and tell](https://github.com/relai-ai/agent-eval-loop/discussions/categories/show-and-tell).
Keep shared material synthetic or redacted, just as you would for an issue.

Search existing issues and pull requests before opening a new one. For a substantial change,
open an issue describing the problem, proposed behavior, and tradeoffs before investing in an
implementation. Small corrections can go straight to a pull request.

Bug reports should include a minimal reproduction, expected and observed behavior, the plugin
version or commit, and relevant environment details. Use synthetic data or short redacted
excerpts. Never upload credentials, raw production traces, private repository contents, or
personal information. Feature requests should explain the user need and how success could be
observed; a complete implementation proposal is optional.

## Set up a local checkout

Fork the repository if you do not have write access, clone your fork, and create a branch for
your change. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run
from the repository root:

```sh
uv sync --locked --python 3.12
uv run --locked python -m unittest discover -s tests
```

The development environment lives in `.venv/`. `pyproject.toml` declares the test dependencies
and `uv.lock` records their resolved versions; commit both when changing dependencies. Use
`uv lock --upgrade-package pytest` to deliberately update pytest and its required dependencies,
review the lockfile diff, and rerun the tests. No shell activation is needed with `uv run`.

Python 3.11 or newer is supported by the bundled checkers and examples, which use the standard
library. The uv project is for plugin development only; no Python package is built or installed,
and plugin users do not need this development environment. For a standard-library-only run,
`python3 -m unittest discover -s tests` still works, with prerequisite-dependent skips.

GitHub Actions runs the suite, including manifest version consistency and referenced-file
checks, on every pull request and manual dispatch, using Python 3.12 on Linux.
CI installs uv and syncs the locked development dependencies; container tests detect an available compatible
engine. The logs show each test outcome, and the job summary lists every skipped test with its reason.
Skipped tests do not establish integration coverage. To use the same runner locally:

```sh
uv run --locked python .github/scripts/run_tests.py
```

Some tests have additional prerequisites and skip when those are absent:

- Coding-verifier integration tests use `pytest`, installed in your development environment.
- Harbor validation tests use `uv` and may download the plugin test suite's fixture release.
- Container tests need a running engine with a Docker-compatible CLI, or Podman.

Read the test summary and include relevant skips in your pull request. Install only the tools
needed for the work you are validating. Provider requests in the example tests use fixtures;
the unit suite does not need real model credentials. Real-agent trials are separate work:
record their model access, data destinations, cost budget, and execution boundaries first.

## Understand the repository

Before changing the plugin, read [AGENTS.md](AGENTS.md),
[DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md), and [DESIGN.md](DESIGN.md).

| Location | Purpose |
| --- | --- |
| `skills/*/SKILL.md` | Skill entrypoints, routing, and essential constraints |
| `skills/*/references/` | Methods and review guidance loaded when needed |
| `skills/start/template/` | Project-owned contracts, documentation, and shared checkers |
| `skills/coding-evals/verifier/` | Verifier copied into coding tasks |
| `examples/` | Optional integration scripts a project can adopt or replace |
| `tests/` | Checker, verifier, runner, example, and plugin consistency tests |

Keep guidance portable across coding agents, project languages, container engines, and CPU
architectures. Refer to skills by name in plain language. Projects record their own Harbor
release in `relai.toml`; fixed tool versions belong only in plugin test fixtures. Give each
requirement one authoritative home and link to it instead of duplicating it.

## Validate the change

Match verification to what changed:

- **Documentation and templates:** check links, paths, examples, and consistency with the
  design. A prose-only correction usually needs no new test.
- **Checkers, verifiers, and examples:** add or adjust focused tests for meaningful behavior,
  including relevant failing cases, and run the suite. Preserve the distinction between an
  agent failure and a measurement or infrastructure error.
- **Skill guidance:** describe the scenario and expected agent behavior. For consequential
  changes, exercise a representative task and retain redacted evidence, including undesirable
  outcomes and untested paths. A text consistency test alone does not establish agent behavior.
  The [feedback and review pilots](tests/behavioral/feedback-review.md) provide synthetic tasks
  for question timing, review handoffs and continuity across interaction surfaces.
- **Copied contracts or verifier code:** explain the effect on existing project copies and
  frozen tasks. Updating the plugin does not automatically update those copies. Changes to
  measurement meaning require a documented repair and a comparable baseline.

Use synthetic fixtures where possible. Keep frozen evaluation evidence stable while comparing
changes, and qualify improvement claims with the attempts, costs, uncertainty, and limitations.

## Open a pull request

Feature PRs do not bump versions. Describe behavior and project-copy migrations in the PR;
GitHub generates release notes from the merged work. The manually triggered Release workflow
prepares and tests a snapshot of `main`, then pushes the release commit directly to `main` with a tag and
GitHub release. See [RELEASING.md](RELEASING.md) for that process.
User update instructions are in the [README](README.md#updating).

Keep each pull request focused. Explain the problem, observable behavior changes, and validation
results using the provided template. Note compatibility concerns, skipped checks, and any
effect on generated or copied artifacts. Link related issues when relevant.

Review any contribution made with coding-agent assistance yourself. You are responsible for
its correctness, provenance, and supporting claims; report what actually ran.

Maintainers may request changes to scope, design, or evidence before merging. Contributions
are made under this repository's [Apache 2.0 license](LICENSE).
