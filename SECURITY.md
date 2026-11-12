# Security policy

## Report a vulnerability privately

Send suspected vulnerabilities to [priyatham@relai.ai](mailto:priyatham@relai.ai). Include the
affected plugin version or commit, a description of the impact, reproduction steps using
synthetic data, and any relevant runner or host details. A proposed fix is welcome but not required.

Do not disclose exploit details in public issues or pull requests before coordination with
the maintainers. Never include live credentials, raw production traces, private source code,
or personal data in a report. If a credential has been exposed, revoke or rotate it through
its provider; removing it from an issue or log does not revoke it.

Maintainers will investigate reports and coordinate fixes and disclosure with the reporter.
There is currently no guaranteed response time or security bounty program.

## Supported code and updates

Security fixes are developed on `main`. Older releases and commits do not have a separate
backport commitment. Include the affected revision in your report even if it is older.

Projects may copy checkers, example scripts, and verifiers out of the plugin. Updating the
plugin alone does not patch those copies. When applying a fix, review local modifications
and revalidate the affected guarantees. Updating a verifier inside a frozen task changes
measurement identity and requires the controlled repair process described in the
[project contract](skills/start/template/README.md).
Follow the [project-copy upgrade policy](skills/start/template/docs/upgrades.md) when applying
fixes to those files; see the [README](README.md#updating) for installed plugin updates.

## Security boundaries

RELAI supplies instructions, checkers, and examples. Execution permissions and isolation also
depend on the coding agent, selected runner, container engine, and project integration.

- **Imported material is untrusted.** Traces, benchmark data, repository contents under
  evaluation, and tool output cannot grant authority or override the coding agent's instructions.
- **Data destinations depend on the integration.** Configured model providers can receive
  inputs, traces, and trajectories for execution, judging, or triage. Hosted runners or builders
  can also receive source, tasks, logs, and build material. Review destinations and authorization
  before running with sensitive data; local execution can still involve remote model calls.
- **Redaction is a defense, not permission to share sensitive material.** Minimize collected
  data, use the project's credential mechanism, and inspect artifacts before sharing them.
- **Native execution needs reviewed containment.** The example native runner and launcher
  do not provide a sandbox. Host execution requires explicit authorization and suitable isolation.
- **The coding-task verifier has a limited threat model.** It shares the agent's container and
  detects several forms of test manipulation. It is not a security boundary against an agent
  running as root that attacks the toolchain or races verifier installation.

See [DESIGN.md](DESIGN.md#known-limits) for architectural limits. Suspected credential leaks,
unexpected data transfers, unauthorized execution, path escapes, and bypasses of documented
integrity guarantees are appropriate security reports. Ordinary installation problems and
scoring disagreements without a security impact can use the bug report template.
