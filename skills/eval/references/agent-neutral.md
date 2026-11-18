# Agent-neutral tests: several agents on the same tasks

Use this mode when the user wants to run several agents or agent harnesses on the same tests (for
example personal or business assistants, or general-purpose agents that Harbor installs), or
wants tests that people outside the project can run against their own agent. To evaluate the one
agent this repository builds, use the default mode, which runs that agent through its real
entrypoint. For tasks built from coding work, use the `coding-evals` skill.

In this mode each test is a Harbor task that brings its own services. Harbor installs the agent
under test, and the agent reaches the task's mock services (mail, calendar, files, a store, a
simulated user) as MCP servers running in sidecar containers. The verifier reads what the
services recorded, so every agent is scored the same way, with or without a trajectory.
`relai/docs/files.md` (*An agent-neutral task with its own services*) is the format and layout;
the plugin's `examples/mcp_service.py` serves a service from its `tools.json`, handlers and
starting state.

## Done when

- `relai.toml` lists the agents to run under `[[agents]]` (`relai/docs/files.md`), with the model,
  version and authentication of each recorded before the first paid run, and `[harbor].version`.
  No harness is needed: Harbor installs each agent.
- **Scenarios reviewed and approved** and **graders previewed** as the `eval` skill describes.
  The grader preview uses the oracle and nop runs below in place of synthetic trajectories, plus
  synthetic journals for each failure the test should catch and for the shortcut: the cheapest
  sequence of tool calls that skips the trigger, which must fail.
- Each test is under `relai/tests/<id>/` in that format, with a `README.md` stating its origin,
  behavior, services and evaluators; `check_task.py` passes.
- **Healthy:** Harbor's oracle agent (`solution/solve.sh`, which calls the same MCP tools an agent
  would) scored every code check at full marks, Harbor's nop agent failed the primary check, and
  a different correct solution also passes. These runs call no model, unless the reference
  solution asks a simulated user, whose model then answers.
- A fresh review ([review-test](review-test.md)) approved each test, and `freeze.py` ran before
  its first real trial.
- When the user asked to run agents: a pilot of one trial per agent showed that each agent
  connected to the task's MCP servers, and the run is reported per agent as *Running and
  comparing* below describes.

## Rules

- **Agents reach the task only through MCP.** Declare each service in `task.toml` as
  `[[environment.mcp_servers]]` pointing at a sidecar in `environment/docker-compose.yaml`. The
  agent's image holds the workspace the scenario needs and nothing of the services: no mock data,
  handlers or journal. Mock rules apply ([mocks](mocks.md)); the sidecar is the client boundary.
- **The task defines the tool set.** Every agent gets the same tools. When the scenario stands
  for a real service, copy that service's tool names and schemas where its MCP server is public;
  otherwise write one plain tool set and keep it across tests that share the service.
- **No way around the mocks.** Turn off each agent's own integrations for the same services and
  pass it no credentials for them, so no agent can reach a real mailbox or calendar. Limit its
  network to its model host (`[agent] network_mode`) only where the recorded Harbor release keeps
  the task's sidecars reachable under that limit; check it with the oracle run, since the
  [Harbor notes](harbor-notes.md) record a release where it does not. Record what you turned off
  per agent, and the network setting, in `decisions.md`.
- **Grading does not depend on the agent.** Code checks read the services' final state and
  journal through the verifier token, and the primary check is one of them. A judge that grades
  what the agent sent or wrote reads the journal (`verifier/mock-journal.jsonl`); a judge reads
  the trajectory only for how the agent worked, and is "not recorded" for an agent Harbor records
  without one.
- **The user's request is `instruction.md`.** When the behavior depends on how the user answers,
  add an `ask_user` tool (the plugin's `examples/ask_user.py`). Use scripted replies when the
  scenario fixes the user's decision: no model is called, so the oracle run stays free and the
  verdict does not depend on a user model. Write each reply so it settles every case the scoring
  depends on. Use a simulated user when the answer must respond to what the agent asks; its
  instructions hold only the user's goal and knowledge, and its model key goes in the service's
  environment, never in the agent's. When the scoring depends on what the agent did before or
  after asking, serve `ask_user` from the same service as the tools it guards, so one journal
  orders every call.
- **Real requests and failures first.** Build scenarios from public issue reports about the
  agents being compared (a reply to the wrong person, deleted data, a double booking, a request
  half done), real requests from datasets whose license allows it, and sessions users donated.
  Record each test's origin. Write the instruction and the service data yourself from the
  source; never copy a report's text, names or personal data into a task. Report scenarios you
  wrote without a source apart from the rest.
- **Never shape a task to one agent.** No agent's tool names, prompts, file names or memory
  layout in an instruction or a check. A task no agent solves, or one only a single agent can
  follow, is a suspected test problem: say why and ask before changing it.
- **Both directions.** For behaviors an agent can overdo (asking the user, sending, deleting),
  also test a case where doing it is right, as the `eval` skill's rules say.

## Agents and setups

- **Which agents.** Each entry in `[[agents]]` names a Harbor agent (`harbor run -a`), a model, the
  agent's own release and how it authenticates. Check that each one lists MCP server support
  among Harbor's agent capabilities for the release in `[harbor].version`; an agent without it
  needs a custom Harbor agent that registers the task's servers.
- **Say what the comparison is.** Running every agent on one model compares the harnesses;
  running each on its default model compares the products. Ask which the user wants, and report
  it with the results.
- **Setups.** For an assistant, the setup is its instruction, persona and memory files, its
  skills and its built-in integrations. Compare agents bare or each with a matched setup, as
  `relai/README.md` (*Comparing agents*) describes.
- **Features only some agents have** (memory across sessions, scheduled jobs, messaging
  channels) are outside agent-neutral tests. Test them in a separate set run only on the agents
  that have them, and report that set apart.

## Running and comparing

Run each agent as `relai/docs/harbor.md` describes, with `-a <agent> -m <model>` and its credential,
the same frozen tests, attempts and network setting for every agent, and each agent's runs in
their own directory under `relai/work/runs/`. Score the judges, then `summarize.py` each run with
the baseline agent's run as `--baseline`.

- **Pilot first.** Run one trial per agent before any larger run, and confirm from the service
  journal that the agent called the task's tools. An agent that never connects scores zero on
  every check, which measures the integration rather than the agent: report it as an
  integration failure and fix it before counting results. Then follow *Cost before spend* in
  `relai/README.md`. When an agent is new to the project, you can check its install while
  building, with no model call, as the [Harbor notes](harbor-notes.md) describe (*Installing
  without running*).
- **Report per agent:** the solved rate (the primary check at full marks), the mean over checks
  recorded for every agent compared, recording coverage, cost and time per trial, and the tasks
  that separate agents. Follow *Comparing agents* in `relai/README.md`.

## Improving one agent

Improve one agent at a time with the `improve` skill: its scope is that agent's setup files, or
its code when this repository develops it. The other agents' scores are context for the report,
never targets. Measure each candidate on the same frozen tests, and decide on held-out tests
when there are enough comparable tests to hold some out.
