# Evaluate and improve an agent you build

[Back to README](../README.md)

## Build evals and improve your agent

https://github.com/user-attachments/assets/53ce7659-21f8-4f42-897e-a5e3cc4d1ffa

For agents you build and deploy, on any framework. Run these requests from the agent's repository.
You can start at any step and reuse existing tests or evidence:

**1. Discover where it can fail**

```text
Use RELAI's discover skill to read this agent's code, prompts and the traces
in ./traces, and tell me where it is likely to fail
```

You get an **EvalsWiki** in `relai/wiki/`: what the agent must do, ranked risks with evidence,
and questions about intended behavior.

**2. Turn the risks into evals**

```text
Use RELAI's eval skill to build tests for the top five risks and get a baseline
```

You get tests that run the real agent end to end, with graders you preview before
they are frozen, and a baseline score for each risk.

**3. Improve without regressions**

```text
Use RELAI's improve skill to fix the failing tests without breaking the passing ones.
You may change prompts and tools, not the model
```

You get a branch with the change, before-and-after scores on the same frozen tests, and a
record of what was tried and rejected.

**Continue as new traces arrive:**

```text
Use RELAI's loop skill to keep improving this agent from ./traces;
optimize task success first, then cost
```

### Discover from code, documentation and traces

`discover` builds the EvalsWiki: what the agent must do, where it can fail and what remains unclear.

Point it at production traces and the coding agent can use focused checks, existing analytics, direct reading or scalable model triage for the question and budget. External processing requires appropriate data and cost authorization.

The optional triage example groups leads into three lanes:

- **Needs your judgment:** likely failures whose correct outcome is unclear. Your answer can become a regression eval or risk evidence.
- **Coverage gaps:** situations real users encounter that no eval covers, ranked by frequency.
- **Weak signals:** small slips that did not fail a run, informing harder or compound eval proposals.

Durable findings update EvalsWiki when they help future work. The wiki is not a transcript archive or a checklist of artifacts.

### Review traces in an app

```text
Use RELAI's trace-review skill to build a review app for ./traces
with hotkeys, filters and feedback on individual steps
```

The coding agent reuses your project's stack and trace tooling, then builds and verifies an
app you own. Browse complete interactions, search and filter runs, leave feedback, and resume
where you stopped. Traces stay read-only and data stays local by default. The app includes its
own run instructions and inspectable feedback storage; no eval setup or model access is required.
Source-linked feedback can later inform discovery, eval proposals or judge calibration.

### Bring your own benchmark

```text
Use RELAI's eval skill to bring in the benchmark at {path-to-benchmark}
(its own runner and scorer, train/validation/test)
```

RELAI first checks a small pilot against the benchmark's own scorer. It respects the benchmark's splits: fixes are learned from train, validation decides what is kept, and test is reserved for final assessment. The benchmark is pinned to its commit and never edited.

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
