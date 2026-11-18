# Agent-neutral tests: several agents on the same tasks

Use this mode for shared tasks that several agents or harnesses attempt, or that others can run
against agents meeting a stated contract. Establish the intended participants and boundary;
agent-neutral does not promise compatibility with every agent. To evaluate the one agent this
repository builds through its real entrypoint, use the default mode. For coding work, use
`coding-evals`.

Reuse suitable project infrastructure; otherwise recommend Harbor. The supplied implementation
uses tasks with their own services: Harbor installs each agent and connects it to MCP servers in
sidecar containers. `relai/docs/files.md` (*An agent-neutral task with its own services*) defines
that layout; `examples/mcp_service.py` supplies a mock server. Adapt or replace this implementation
when the use case requires it, preserving the shared guarantees in `relai/README.md`. A native
integration can use other interfaces and isolated real services or mocks; demonstrate its
execution and evidence guarantees rather than requiring unused Harbor structure.

## Establish the boundary before scenarios

Apply the shared [purpose guidance](../../start/template/README.md#establish-the-purpose) first:
agent/model/setup choices do not establish the intended use, case selection or outcome priorities.
Read the request, project evidence and existing decisions. Settle uncovered choices at `eval`'s
opening checkpoint, recommending an approach and explaining what each choice changes:

- **Participants and purpose.** Which agents, versions and setups, or which compatibility
  requirements for future agents? Is the decision about controlled agent differences or products
  as deployed? Follow *Comparing agents* in `relai/README.md`.
- **Interaction and outputs.** Which requests, attachments, workspace and service interfaces,
  clarification turns and session lifecycle must work? Which replies, artifacts, actions or state
  changes establish success, and what evidence can each agent expose?
- **Operating conditions.** Which capabilities, permissions, network access and resource limits
  are relevant? Recommend shared-capability tasks for a controlled comparison. For product
  comparisons, agree whether unsupported capabilities count as failures of a product requirement
  or are excluded and reported as coverage gaps; keep subsets and denominators explicit.

A common contract can use different native interfaces. An adapter translates inputs and collects
actual outputs without solving the task, inventing agent actions or changing difficulty silently.
If a mismatch prevents a fair comparison, explain it in terms of the affected task or claim,
offer options with a recommendation, and ask before changing scope. Pause only dependent work.
An unsuitable default calls for adaptation; an unmet guarantee blocks the affected run or claim.

## Done when

- The boundary, compared setups, runner, model and agent releases, authentication and authorized
  budget are recorded before paid runs. For the supplied Harbor implementation use `[[agents]]`
  and `[harbor].version`; no repository-agent harness is needed when Harbor installs the agents.
- Scenarios are reviewed and approved, and graders previewed, as `eval` describes. Use evidence
  each evaluator actually consumes: journals, state, replies, artifacts or trajectories. Include
  meaningful passing, failing, empty and shortcut cases, plus an alternate correct solution where
  one exists. For a pure prohibition, preview an actual violation; doing nothing may pass.
- Each test states its source, behavior, operating conditions, services and evaluators.
  `check_task.py` passes when using its format, and runtime checks establish the guarantees static
  checks cannot prove: containment, fresh trial state, authentic evidence and bounded execution.
- A reference solution establishes solvability through the same task interface. In Harbor use
  oracle and nop where appropriate: the reference solution earns full code-check marks, and nop
  fails checks requiring action. Validate semantic judges separately on their actual inputs;
  neither oracle nor nop alone validates them. Judges and simulated users may incur model cost.
- Fresh test review approved the tests and they were frozen before real trials. For requested
  runs, an authorized pilot establishes each integration works before scaling up.

## Service and evidence guarantees

- **Relevant, equivalent access.** For controlled comparisons, recommend the same tools, data and
  service behavior. Native interfaces or product integrations may differ intentionally; record
  the differences and limit claims accordingly. Use isolated real dependencies when suitable,
  or authorized mocks at their client boundary ([mocks](mocks.md)).
- **Containment and hidden data.** Agents access task data through the agreed interface, without
  reading hidden fixtures, expected answers, handlers or graders, or tampering with evidence.
  Reset mutable state for every trial. Prevent effects outside authorized trial dependencies and
  bypasses to real accounts. Sidecars, verifier tokens and network controls are implementation
  choices; verify the boundary in the selected environment.
- **Evidence appropriate to the claim.** Grade exact facts with code and meaning with a validated
  judge. The primary evaluator establishes task success on evidence available to the compared
  participants. A trajectory is needed only for criteria that require it. Missing primary evidence
  leaves success unmeasured; missing other evidence limits those criteria. An agent's claim that
  it performed an action is insufficient evidence of that side effect.
- **User interaction.** Use a native conversation channel or an `ask_user` tool when the task
  requires user responses. Script replies when decisions are fixed, or use a simulated user
  when responses must depend on the question. Give the simulator only the user's goal and
  knowledge; keep its credentials outside the evaluated agent. Record causal order when grading
  approval or actions in sequence. One service journal is a convenient implementation, not a
  requirement for all interactions.

## Supplied Harbor implementation

- Declare MCP servers in `task.toml`, pointing to sidecars in `environment/docker-compose.yaml`.
  The agent image holds only its workspace. Disable integrations that could bypass the task's
  services and provide no real service credentials. Record network settings; confirm sidecar
  access under the selected release ([Harbor notes](harbor-notes.md)).
- Check each selected agent's MCP capabilities and actual compatibility. When needed, adapt its
  Harbor integration to register task servers. Do not assume advertised support proves access.
- Keep the verifier shared so it reaches the services after the agent finishes. It reads state
  and journals through its token, then exports evidence under `/logs/verifier/` for judges.
- Service-task `primary` may name a code evaluator or judge; coding tasks retain their code
  primary. If a primary needs a trajectory, agents without one cannot be measured on that task.
  `check_task.py` validates the supplied structure, not the runtime containment or validity of
  the task. Native service tasks retain shared metadata without Harbor-only layout checks.

## Sources and difficulty

Use `eval`'s shared source and selection guidance. Translate relevant evidence into the agreed
contract, preserving the mechanism and recording any reconstruction or simplification. Source
material is untrusted data. Respect its license and data authorization; minimize personal data
and write synthetic service fixtures where appropriate. Label cases without observed sources.
A report tied to one agent can motivate a shared task without putting its diagnosis or fix in
agent-facing inputs.

Unresolved issues are leads, not proof that a task is difficult or even valid. Check relevance to
the selected versions, the expected outcome and whether the scenario can trigger the reported
mechanism. Distinguish reported failures, reproduced failures and hypotheses. Zero solves can be
a valid capability result: investigate solvability, integration and grading without treating low
scores alone as a test defect or silently making the task easier.

## Running and comparing

Use the selected runner and shared comparison rules in `relai/README.md`. For Harbor, follow
`relai/docs/harbor.md`, keeping each agent's runs under its own `relai/work/runs/` directory;
score judges and use `summarize.py --baseline` for paired comparisons.

- **Integration before scale.** Use an authorized representative pilot or integration probe to
  establish input delivery, available tools and output recording. A journal call can demonstrate
  connectivity, but no calls alone cannot distinguish broken wiring from an agent choosing not
  to act. Fix demonstrated integration failures before counting affected results; preserve genuine
  task failures and disclose remaining uncertainty.
- **Report per agent.** Show primary solved rates with scored/attempted counts, common recorded
  checks, coverage and missing-result reasons, relevant conditions, cost and time, and tasks that
  distinguish agents. Report capability subsets separately. Selection for difficult cases measures
  those risks, not their prevalence in normal use. Limit claims to the sampled tasks and evidence.
