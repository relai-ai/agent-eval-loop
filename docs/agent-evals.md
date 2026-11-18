# Evaluate and improve an agent you build

[Back to README](../README.md)

Start with the [README walkthrough](../README.md#ai-agents-you-build), expanding the full
walkthrough beneath the discovery request. This guide covers specialized options and operation.

## Discover from code, documentation and traces

`discover` builds the EvalsWiki: what the agent must do, where it can fail and what remains unclear.

Point it at production traces and the coding agent can use focused checks, existing analytics, direct reading or scalable model triage for the question and budget. External processing requires appropriate data and cost authorization.

The optional triage example groups leads into three lanes:

- **Needs your judgment:** likely failures whose correct outcome is unclear. Your answer can become a regression eval or risk evidence.
- **Coverage gaps:** situations real users encounter that no eval covers, ranked by frequency.
- **Weak signals:** small slips that did not fail a run, informing harder or compound eval proposals.

Durable findings update EvalsWiki when they help future work. The wiki is not a transcript archive or a checklist of artifacts.

## Review traces in an app

```text
Use RELAI's trace-review skill to build a review app for ./traces
with hotkeys, filters and feedback on individual steps
```

The coding agent reuses your project's stack and trace tooling, then builds and verifies an
app you own. Browse complete interactions, search and filter runs, leave feedback, and resume
where you stopped. Traces stay read-only and data stays local by default. The app includes its
own run instructions and inspectable feedback storage; no eval setup or model access is required.
Source-linked feedback can later inform discovery, eval proposals or judge calibration.

## Bring your own benchmark

```text
Use RELAI's eval skill to bring in the benchmark at {path-to-benchmark}
(its own runner and scorer, train/validation/test)
```

RELAI first checks a small pilot against the benchmark's own scorer. It respects the benchmark's splits: fixes are learned from train, validation decides what is kept, and test is reserved for final assessment. The benchmark is pinned to its commit and never edited.

## Compare several agents on the same evals

```text
Use RELAI's eval skill to build agent-neutral evals from {issue reports, requests
or traces}, and compare {agent A} and {agent B} on them
```

Each test brings its own mock services (mail, calendar, files, a simulated user) as MCP servers
in sidecar containers. Harbor installs each agent under test and connects it to those servers, so
every agent gets the same tools and data. The checks read what the services recorded, so every
agent is scored the same way, whether or not it leaves a trajectory. RELAI validates each test
without a model: a scripted reference solution must pass and doing nothing must fail. See
[agent-neutral tests](../skills/eval/references/agent-neutral.md).

## Use a project-native runner

RELAI can reuse a suitable project or benchmark runner instead of Harbor. The integration must
run the real agent, record results and demonstrate containment; native execution does not
require unused Harbor or container tools. Running on the host requires explicit authorization
and reviewed sandboxing. See the [native execution contract](../skills/start/template/docs/native.md).

## Continue with an improvement loop

An iteration begins with new traces, answers, tests or existing evidence. The coding agent adapts, reorders, combines or skips activities to fit the request:

```text
1. learn    triage new traces → EvalsWiki + proposed evals
2. measure  establish or reuse comparable evidence for the objective and guardrails
3. explore  investigate, measure or make a scoped change
4. check    run scope-based checks and optional held-out evals; review the results
5. record   what was learned, results, fixes kept or rejected, and spend
```

In practice:

- **Investigation is a useful outcome.** An iteration can gather evidence without shipping a change.
- **Keep measurements comparable.** While an iteration runs, the tests, graders and run conditions do not change, so before and after numbers stay comparable. If a test itself turns out to be wrong, it is repaired openly, recorded, and the baseline is measured again.
- **Your limits hold.** The agreed budget and scope apply throughout. The coding agent asks before going beyond them or making a consequential choice you have not covered.
- **Attribute speed improvements.** Report test-runner speedups separately from changes to the agent.

The results are evidence on the tests you have, not proof that the agent is correct everywhere or that no regression is possible.

### Stop, resume or schedule a loop

Tell the coding agent to stop, or interrupt it. Finished trials, iterations and decisions are
saved under `relai/`. Ask it to continue later; it reconciles saved progress with the actual
source and run artifacts before resuming. Recovery is instruction-led, not an automatic state engine.
A watch-mode loop uses a schedule you set up with your host's scheduler or cron. Remove that
schedule to stop future invocations.

See [evaluation and review](evaluation-and-review.md) for approval points, score interpretation
and the status board, and [installation requirements](installation.md#requirements) before runs.
