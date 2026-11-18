# move-one-on-one

An example agent-neutral task with its own services, for the `eval` skill's agent-neutral mode. Copy the
folder to `relai/tests/move-one-on-one/` to try the format; build real tasks from real requests
and failures instead ([agent-neutral tasks](../../../skills/eval/references/agent-neutral.md)).

## Evidence

- **Source:** written for the plugin as an example; no real user or issue behind it.
- **Behavior:** a contact asks by email to move a meeting. The assistant moves the existing
  event (no duplicate, nothing left at the old time), replies to that contact, and writes to no
  one else. The inbox also holds mail from Dan Leeds, whose name is close to Dana Lee's.
- **Services:** one sidecar, `office`, serves email and calendar tools over MCP
  (`environment/office/`, served by the plugin's `examples/mcp_service.py`). Agents reach it
  through `[[environment.mcp_servers]]`; its data and journal are not in the agent's container.
- **Evaluators:**
  - `moved-the-meeting` (primary, code): one event with Dana on Friday 10:00 to 10:30, none at
    the old time. A deleted and recreated event passes as well as a moved one.
  - `replied-to-dana` (code): an email reached dana.lee@example.com.
  - `no-wrong-recipient` (code): no email to anyone else.
  - `confirms-new-time` (judge): reads the service journal, so it scores every agent, whether
    or not the agent leaves a trajectory.
- **Validation:** Harbor's oracle agent (`solution/solve.sh`, which calls the same MCP tools)
  scores full marks on every code check; the nop agent fails the primary check.

## Author notes

The verifier shares the agent's container and reads the service over its network with a token
that arrives only with `tests/` (`tests/params.json`) and in the sidecar's environment
(`environment/docker-compose.yaml`), which the agent's image never copies.
