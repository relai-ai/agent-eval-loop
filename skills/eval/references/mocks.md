# Mock a dependency

Without a harness, build it first ([harness](harness.md)).

Goal: the agent runs for real with only the dependency's client boundary replaced, and evaluators
can see what the agent tried to do.

## Done when

- Each mock is listed in `relai/harness/mocks/MOCKS.md` and journals every call, both as
  `relai/docs/files.md` describes under Mocks.
- In a trial, the agent's calls reach the mock, and calls to the real hosts fail instead of
  escaping.
- Evaluators that grade side effects (a refund issued, an email sent) read the journal rather than
  the agent's claims.
- The smoke test passes after the change, and any frozen test that gained a state file was
  re-frozen under the *Frozen tests* rule.

## Rules

- Prefer running the real dependency inside the trial (the project's own compose file, image or
  seed data) over mocking it.
- Mock at the client boundary (a base URL, an MCP server command, the client function) through the
  project's own configuration (`relai/README.md`, Fixed rules: *Mocks*).
- Side effects must stay within authorized, isolated test dependencies or sandbox accounts.
  Mock actions when a real dependency cannot meet those containment and authorization guarantees;
  reachability alone does not authorize a production action.

## Ask the user

Ask only for mock choices or side-effect destinations not covered by existing authorization,
naming the dependency and reason. Group related open choices when useful. If a mock is declined,
use an authorized isolated real dependency when suitable; otherwise ask how trials should handle
it. Do not substitute production actions for an unavailable mock or sandbox.

## Approach

### Keep what the agent sees unchanged

A mock changes where calls go, never what the agent's model sees or what its code handles.

- A mocked tool server (an MCP server, for example) copies the real server's tool names,
  descriptions and input and output schemas, so the model sees the same tools.
- A mocked function replaces only its implementation, never its name, signature, docstring or
  tool schema.
- Errors use the exception types and error shapes the agent's code already handles. A failure the
  agent should see is returned the way the real service returns it, not raised inside the mock.

### Fail closed

- A call that no rule matches fails loudly and is journaled as unmatched. It never gets an
  invented default reply and never falls through to the real service.
- A mock installed by patching code is patched from harness code under `relai/harness/`, only
  when a RELAI variable is set, so the project's normal runs are untouched and project code
  never reads that variable.
- Blocking the real hosts (pointing them at loopback inside the container) makes a call that
  misses its mock fail. It does not catch a client that connects to a hard-coded IP address or
  through an HTTP proxy, and `localhost` cannot be blocked this way. Confirm in the journal that
  the calls actually arrived.

### Keep mock files out of the agent's view

Mock definitions, handlers and data live outside the agent’s readable boundary, whether the
runner uses a container or reviewed host containment.
A mock's fixtures can hold exactly what a test checks for, and an agent that can read them is no
longer being tested.

### Shared mocks and per-test state

- A dependency's mock logic lives once in `relai/harness/mocks/`. Each test adds only a small file
  with its own starting state and arguments.
- Keep matching to routing (which call is this?). Put business rules in handler code that reads
  and updates state, and vary replies per test by branching on arguments or state, not by copying
  a mock.

### Deterministic and self-contained

- Keep mutable data in an explicit state object, never in module globals, so it starts fresh in
  each trial and its changes can be journaled.
- Use a seeded clock, random source and id sequence instead of the wall clock, `random` or `uuid`.
- Beyond its journal, mock code writes no files, makes no outbound network calls and starts no
  subprocesses of its own. A mock served at a base URL or as an MCP server listens only inside
  the trial.
- Never import the agent's own project: a mock simulates the dependency, not the agent.

### Read a near miss as evidence

When a call does not match, decide whether the agent's call was legitimate. If it was, fix the
rule. If not, fix the scenario or the wiring. Never loosen a rule until it accepts anything; that
hides the very behavior a test should see.
