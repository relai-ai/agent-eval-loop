"""Reference Harbor agent: runs launcher.py inside the trial container. Use it, adapt it, or replace it.

Harbor imports this class on the host (it runs inside Harbor's own process) and calls run()
once per trial. It uploads launcher.py into the container and runs it there with the
adapter command you configure; the launcher drives the turns and writes the ATIF trajectory
to /logs/agent/trajectory.json, which Harbor exports.

Run it with:
  PYTHONPATH=relai/harness uv tool run --python 3.12 --from harbor==<[harbor].version> harbor run \
    -e docker -p <task or dir of tasks> -a harbor_agent:EvalsAgent \
    --ae RELAI_ADAPTER_COMMAND="python3 /app/adapter.py" ...

Options, passed with --ae (or set in Harbor's environment):
  RELAI_ADAPTER_COMMAND  required; the command that starts your adapter in the container
  RELAI_SCENARIO         scenario file inside the container (default /app/scenario.json)
  RELAI_PASS_ENV         comma-separated names whose values (from Harbor's environment) the
                         adapter needs, such as the agent's own model key
  RELAI_USER_SIM_KEY_ENV name of the variable holding the simulated user's model key; it is
                         given to the launcher only, never to the adapter
  RELAI_TURN_TIMEOUT     seconds to wait for each reply (launcher default 1800)
  RELAI_USER_SIM_BASE_URL base URL of an OpenAI-compatible server for a compatible: simulated user
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

LAUNCHER = Path(__file__).with_name("launcher.py")
CONTAINER_LAUNCHER = "/tmp/relai/launcher.py"
TRAJECTORY = "/logs/agent/trajectory.json"
SETTINGS = {"RELAI_TRAJECTORY_PATH", "RELAI_TURN_TIMEOUT", "RELAI_HIDE_ENV", "RELAI_USER_SIM_BASE_URL"}  # not secrets; never redacted


class EvalsAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "relai-reference"

    def version(self) -> str:
        return "0.1.0"

    def _option(self, key: str, default: str | None = None) -> str | None:
        return self._extra_env.get(key) or os.environ.get(key) or default

    async def setup(self, environment: BaseEnvironment) -> None:
        await environment.exec(command="mkdir -p /tmp/relai", user="root")
        await environment.upload_file(source_path=LAUNCHER, target_path=CONTAINER_LAUNCHER)

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        command = self._option("RELAI_ADAPTER_COMMAND")
        if not command:
            raise ValueError("set RELAI_ADAPTER_COMMAND (harbor run --ae RELAI_ADAPTER_COMMAND=...)")
        scenario = self._option("RELAI_SCENARIO", "/app/scenario.json")
        env = {"RELAI_TRAJECTORY_PATH": TRAJECTORY}
        for name in ("RELAI_TURN_TIMEOUT", "RELAI_HIDE_ENV", "RELAI_USER_SIM_BASE_URL"):  # launcher settings
            if value := self._option(name):
                env[name] = value
        for name in filter(None, (n.strip() for n in (self._option("RELAI_PASS_ENV") or "").split(","))):
            value = self._extra_env.get(name) or os.environ.get(name)
            if value is not None:
                env[name] = value
        sim_key_env = self._option("RELAI_USER_SIM_KEY_ENV")
        if sim_key_env:
            value = self._extra_env.get(sim_key_env) or os.environ.get(sim_key_env)
            if not value:
                raise ValueError(f"RELAI_USER_SIM_KEY_ENV names {sim_key_env}, which is not set in Harbor's "
                                 "environment; set it (or pass it with --ae) so the simulated user can call its model")
            env["RELAI_USER_SIM_KEY"] = value  # the launcher keeps this from the adapter

        result = await environment.exec(
            command=(f"python3 {CONTAINER_LAUNCHER} --scenario {shlex.quote(scenario)} "
                     f"--trajectory {TRAJECTORY} --adapter {shlex.quote(command)}"),
            env=env,
        )
        log = (result.stdout or "") + (result.stderr or "")
        for name in env:  # never leave values in the host-side log
            if name not in SETTINGS and len(env[name]) >= 8:
                log = log.replace(env[name], f"[redacted {name}]")
        (self.logs_dir / "launcher.log").write_text(log, encoding="utf-8")
        self._record_usage(context)
        if result.return_code != 0:
            raise RuntimeError(f"launcher exited {result.return_code}; last output:\n{log[-4000:]}")

    def _record_usage(self, context: AgentContext) -> None:
        path = self.logs_dir / "trajectory.json"
        try:
            metrics = json.loads(path.read_text(encoding="utf-8")).get("final_metrics") or {}
        except (OSError, json.JSONDecodeError):
            return
        pairs = {"n_input_tokens": "total_prompt_tokens", "n_cache_tokens": "total_cached_tokens",
                 "n_output_tokens": "total_completion_tokens", "cost_usd": "total_cost_usd"}
        for field, key in pairs.items():
            value = metrics.get(key)
            if isinstance(value, (int, float)) and value >= 0:
                setattr(context, field, value)
