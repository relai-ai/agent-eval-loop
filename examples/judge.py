#!/usr/bin/env python3
"""Reference LLM judge: scores each trial's judge evaluators on the host. Standard library only.

  python3 relai/bin/judge.py <job or run dir> [...] [--force]
  python3 relai/bin/judge.py --self-test relai/tests/<id>

For every Harbor or native trial under the given directories, it reads the task's
[[metadata.relai.evaluators]] with type = "judge", sends the rubric and the
trajectory (secret values removed) to the model in relai.toml [judge], and writes
<trial>/judges/<evaluator-id>.json = {"score", "feedback", "model", "judge": "api"}
or {"error": "..."}. A judge sees what its evaluator's `inputs` lists (default ["trajectory"]):
"trajectory", "instruction" (the task's instruction.md), or "verifier/<file>" (a file the verifier wrote
in the trial, such as the diff.patch and facts.json of an agent-neutral coding task). A judge whose
inputs are missing from a trial records an error, never a score. summarize.py reads those files. Existing scores are kept unless --force;
earlier errors are retried. Trials that crashed before verification are skipped.
Every new attempt is retained in judges/<id>.attempts.jsonl; <id>.json mirrors the latest.
The first retry also retains a valid legacy result. Count spend from the history when present,
otherwise from the legacy latest result, never both.
Optional relai.toml keys: [judge].effort (Anthropic effort, default "medium"); [pricing."<model>"]
(USD per million tokens, recorded by the coding agent at setup) to compute a call's cost when the
provider does not report one. Calls made outside a run (--self-test, and bin/preview.py) are
appended to relai/records/spend.jsonl, including billed calls that end in an error; judging a run
keeps its cost in judges/<id>.json, where summarize.py counts it.

--dry-run prints each judge's input size and estimated cost without calling a model. A judge
warns on stderr when it clips an input or receives a very large trajectory.

--self-test runs each judge of a task on a synthetic empty-reply trajectory and fails when a
judge gives it full marks (a judge that cannot fail is not measuring anything), unless the
task sets [metadata.relai].prohibition = true.

Keys: ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY or the variable [judge].api_key_env names,
from the environment (exported, or set by your secrets tool) or relai/.env. The script
reads the value to call the API and never prints it. The judge runs on the host, so the key
never enters a container.

Data sent: the judge's inputs go to the configured provider. Only the values of declared secret
variables are replaced before sending; everything else, including any personal or customer data
in the trajectory, is sent as recorded. Tell the user what goes where before the first paid call.

relai.toml:
  [judge]
  mode = "api"                # or "subagent": a fresh coding-agent subagent writes the same files
  provider = "anthropic"      # or "openai", "openrouter", "openai-compatible" (+ base_url, api_key_env)
  model = "<model id>"        # required: choose it deliberately, there is no default
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (
    declared_evaluators, evals_config, relai_root, load_json, load_toml, redact, redaction_values,
    resolve_task_dir, secret_values,
)

SYSTEM = """You grade one recorded run of an AI agent against a rubric. You get the inputs the rubric needs,
each under its own heading. A trajectory is ATIF: "user" steps are what the agent received, "agent"
steps are what it said and the tools it called, with tool results in "observation". Other inputs can
be the task's instruction, the diff of everything the agent changed, and facts the verifier
established (which tests passed, which files changed). Judge only what the inputs show; do not assume
actions that were not recorded.

- Score the whole relevant turn: all agent steps after a user step and before the next one.
- Accept any wording that satisfies the rubric; do not reward or punish style the rubric does not mention.
- If the rubric grades a deliverable the user asked for (an answer, a change, an action) and the
  agent did not produce it, give the minimum score and say the deliverable is missing. If declining
  or asking was the right response, nothing is missing.
- Give a score within the stated bounds and feedback that names every unmet criterion, where it
  occurred, and what would earn full marks.
Return JSON: {"score": <number>, "feedback": "<text>"}."""

SCHEMA = {"type": "object", "properties": {"score": {"type": "number"}, "feedback": {"type": "string"}},
          "required": ["score", "feedback"], "additionalProperties": False}


def api_key(name: str, relai_dir: Path) -> str:
    value = os.environ.get(name) or secret_values(relai_dir).get(name)
    if not value:
        raise SystemExit(f"error: {name} is not set; export it, set it with your secrets tool, or add it to "
                         "relai/.env (the script never prints it)")
    return value


def post(url: str, headers: dict, body: dict, attempts: int = 4) -> dict:
    """POST JSON; retries rate limits, server errors and dropped connections with backoff."""
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"content-type": "application/json", **headers})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=600) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            retryable = exc.code in (408, 409, 429) or exc.code >= 500
            if not retryable or attempt == attempts - 1:
                raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode(errors='replace')[:500]}") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == attempts - 1:
                raise RuntimeError(f"connection failed: {exc}") from None
        time.sleep(2 ** attempt * 5)
    raise RuntimeError("unreachable")


OPENAI_COMPATIBLE = {
    "openai": ("https://api.openai.com/v1/chat/completions", "OPENAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY"),
}


def redaction_secrets(config: dict, relai_dir: Path) -> dict[str, str]:
    """Read only declared runtime and provider variables, never the whole environment."""
    suite = evals_config(relai_dir)
    names = set((suite.get("runtime") or {}).get("env") or [])
    for selected in (config, suite.get("judge"), suite.get("triage")):
        if selected is None:
            continue
        provider = selected.get("provider", "anthropic")
        if provider == "anthropic":
            names.add("ANTHROPIC_API_KEY")
        elif provider in OPENAI_COMPATIBLE:
            names.add(OPENAI_COMPATIBLE[provider][1])
        elif provider == "openai-compatible":
            names.add(selected.get("api_key_env", "OPENAI_API_KEY"))
        if selected.get("api_key_env"):
            names.add(selected["api_key_env"])
    return redaction_values(relai_dir, names)


def call_model(config: dict, relai_dir: Path, prompt: str, system: str = SYSTEM, schema: dict = SCHEMA,
               name: str = "evaluation") -> tuple[dict, str]:
    verdict, model, _ = call_model_full(config, relai_dir, prompt, system, schema, name)
    return verdict, model


def cost_of(usage: dict | None) -> float | None:
    """The call's cost when the provider reports it (OpenRouter does); never estimated."""
    value = (usage or {}).get("cost")
    return float(value) if isinstance(value, (int, float)) and value >= 0 else None


def prices(relai_dir: Path, model: str | None) -> dict | None:
    table = (evals_config(relai_dir).get("pricing") or {}).get(model or "")
    if not isinstance(table, dict) or not isinstance(table.get("input"), (int, float)):
        return None
    prices_only = {k: v for k, v in table.items() if k in ("input", "output", "cache_write", "cache_read")}
    return table if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in prices_only.values()) else None


def priced_cost(relai_dir: Path, model: str | None, usage: dict | None) -> float | None:
    """The call's cost from reported token counts and [pricing] in relai.toml, or None."""
    table, usage = prices(relai_dir, model), usage or {}
    if table is None:
        return None
    fresh = (usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    written = usage.get("cache_creation_input_tokens") or 0
    read = usage.get("cache_read_input_tokens") or 0
    output = usage.get("output_tokens") or usage.get("completion_tokens") or 0
    cost = (fresh * table["input"] + written * table.get("cache_write", table["input"])
            + read * table.get("cache_read", table["input"]) + output * table.get("output", 0.0))
    return round(cost / 1e6, 6)


def record_spend(relai_dir: Path, tool: str, metadata: dict, ref: str) -> None:
    usage = metadata.get("usage") or {}
    entry = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tool": tool,
             "model": metadata.get("model"),
             "input_tokens": usage.get("input_tokens") or usage.get("prompt_tokens"),
             "output_tokens": usage.get("output_tokens") or usage.get("completion_tokens"),
             "cache_read_tokens": usage.get("cache_read_input_tokens"),
             "cost_usd": metadata.get("cost_usd"), "cost_source": metadata.get("cost_source"), "ref": ref}
    try:
        ledger = relai_dir / "records" / "spend.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError as exc:
        print(f"warning: could not append to records/spend.jsonl: {exc}", file=sys.stderr)


def call_model_full(config: dict, relai_dir: Path, prompt: str, system: str = SYSTEM, schema: dict = SCHEMA,
                    name: str = "evaluation", response_metadata: dict | None = None) -> tuple[dict, str, dict]:
    """Return verdict/model/usage; optionally retain billed response metadata before parsing fails."""
    provider = config.get("provider", "anthropic")
    if provider != "anthropic":
        if provider in OPENAI_COMPATIBLE:
            url, key_name = OPENAI_COMPATIBLE[provider]
        elif provider == "openai-compatible":
            base = config.get("base_url") or sys.exit("error: set [judge].base_url for provider openai-compatible")
            url, key_name = base.rstrip("/") + "/chat/completions", config.get("api_key_env", "OPENAI_API_KEY")
        else:
            sys.exit(f"error: unknown [judge].provider {provider!r}; use anthropic, openai, openrouter or openai-compatible")
        model = config.get("model") or sys.exit(MISSING_MODEL)
        body = {"model": model, "messages": [{"role": "system", "content": system},
                                             {"role": "user", "content": prompt}],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": name, "strict": True, "schema": schema}}}
        if provider == "openrouter":
            body["usage"] = {"include": True}
        data = post(url, {"authorization": f"Bearer {api_key(key_name, relai_dir)}"}, body)
        if response_metadata is not None:
            response_metadata.update(model=data.get("model", model), usage=data.get("usage") or {},
                                     cost_usd=cost_of(data.get("usage")))
        message = data["choices"][0]["message"]
        if message.get("refusal"):
            raise RuntimeError(f"the judge model refused: {message['refusal']}")
        return json.loads(message.get("content") or "{}"), data.get("model", model), data.get("usage") or {}
    model = config.get("model") or sys.exit(MISSING_MODEL)
    data = post("https://api.anthropic.com/v1/messages",
                {"x-api-key": api_key("ANTHROPIC_API_KEY", relai_dir), "anthropic-version": "2026-10-21",
                 "anthropic-beta": "server-side-fallback-2026-07-01"},
                {"model": model, "max_tokens": 16000, "system": system, "fallbacks": "default",
                 "messages": [{"role": "user", "content": prompt}],
                 "output_config": {"effort": config.get("effort", "medium"),
                                   "format": {"type": "json_schema", "schema": schema}}})
    if response_metadata is not None:
        response_metadata.update(model=data.get("model", model), usage=data.get("usage") or {},
                                 cost_usd=cost_of(data.get("usage")))
    if data.get("stop_reason") == "refusal":
        raise RuntimeError("the judge model declined to grade this trajectory")
    text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    return json.loads(text or "{}"), data.get("model", model), data.get("usage") or {}


MISSING_MODEL = ("error: set model in relai.toml's [judge] table (or [triage] for triage.py); there is no "
                 "default, so choose one deliberately: judging needs a capable model, triage a cheap one")


INPUT_LIMIT = 60_000


def clip(text: str) -> str:
    if len(text) <= INPUT_LIMIT:
        return text
    print(f"warning: a judge input of {len(text)} characters was clipped to {INPUT_LIMIT}; consider an evidence "
          "file written by the verifier (relai/docs/files.md, Scores)", file=sys.stderr)
    half = INPUT_LIMIT // 2
    return f"{text[:half]}\n[... {len(text) - INPUT_LIMIT} characters cut ...]\n{text[-half:]}"


def judge_inputs(ev: dict, task: Path, trial_dir: Path | None, trajectory: dict | None, secrets: dict,
                 synthetic: bool = False) -> str:
    """The text of each input the evaluator lists, with secret values removed. Raises ValueError when one is missing."""
    names = ev.get("inputs") or ["trajectory"]
    parts = []
    for name in names:
        if name == "trajectory":
            if trajectory is None:
                raise ValueError("no ATIF trajectory for this trial (the agent's runs are not recorded in ATIF), so "
                                 "this judge cannot score it")
            text, label = json.dumps(trajectory, indent=1), "Trajectory"
            if len(text) > 4 * INPUT_LIMIT:
                print(f"warning: the trajectory sent to this judge is {len(text)} characters; consider an evidence "
                      "file written by the verifier (relai/docs/files.md, Scores)", file=sys.stderr)
            parts.append(f"{label}:\n{redact(text, secrets)}")
            continue
        elif name == "instruction":
            text, label = (task / "instruction.md").read_text(encoding="utf-8"), "Task instruction"
        elif isinstance(name, str) and name.startswith("verifier/") and ".." not in name:
            path = trial_dir / name if trial_dir is not None else None
            if synthetic:
                text = "(empty)"
            elif path is None or not path.is_file():
                raise ValueError(f"{name} is missing from the trial; the verifier must write it before judges run")
            else:
                text = path.read_text(encoding="utf-8", errors="replace")
            label = {"verifier/diff.patch": "Diff of everything the agent changed",
                     "verifier/facts.json": "Facts the verifier established"}.get(name, name)
        else:
            raise ValueError(f"unknown judge input {name!r}: use trajectory, instruction or verifier/<file>")
        parts.append(f"{label}:\n{clip(redact(text, secrets))}")
    return "\n\n".join(parts)


def build_prompt(config: dict, relai_dir: Path, task: Path, ev: dict, trajectory: dict | None, secrets: dict,
                 trial_dir: Path | None = None, synthetic: bool = False) -> tuple[str, dict]:
    """The judge prompt with secret values removed, and the secrets used; raises ValueError or OSError."""
    secrets = {**secrets, **redaction_secrets(config, relai_dir)}
    low, high = ev.get("min_score", 0.0), ev.get("max_score", 1.0)
    rubric = (task / ev["rubric"]).read_text(encoding="utf-8")
    inputs = judge_inputs(ev, task, trial_dir, trajectory, secrets, synthetic)
    prompt = (f"Criterion: {ev.get('criterion', '')}\nScore bounds: {low} (worst) to {high} (best).\n\n"
              f"Rubric:\n{rubric}\n\n{inputs}")
    return redact(prompt, secrets), secrets


def estimate(config: dict, relai_dir: Path, prompt: str) -> dict:
    tokens = (len(SYSTEM) + len(prompt)) // 4
    table = prices(relai_dir, config.get("model"))
    cost = round(tokens * table["input"] / 1e6, 4) if table else None
    return {"input_chars": len(prompt), "input_tokens_estimate": tokens, "input_cost_usd_estimate": cost}


def judge_one(config: dict, relai_dir: Path, task: Path, ev: dict, trajectory: dict | None, secrets: dict,
              trial_dir: Path | None = None, synthetic: bool = False, ledger: bool = False) -> dict:
    low, high = ev.get("min_score", 0.0), ev.get("max_score", 1.0)
    try:
        prompt, secrets = build_prompt(config, relai_dir, task, ev, trajectory, secrets, trial_dir, synthetic)
    except (OSError, ValueError) as exc:
        return {"error": redact(str(exc), {**secrets, **redaction_secrets(config, relai_dir)})}
    metadata = {"judge": "api", "judged_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        verdict, model, usage = call_model_full(config, relai_dir, prompt, response_metadata=metadata)
        reported = cost_of(usage)
        computed = None if reported is not None else priced_cost(relai_dir, model, usage)
        metadata.update(model=model, usage=usage, cost_usd=reported if reported is not None else computed,
                        cost_source="provider" if reported is not None else "pricing" if computed is not None else None)
        if ledger:
            record_spend(relai_dir, "judge", metadata, spend_ref(relai_dir, trial_dir))
        score, feedback = verdict.get("score"), str(verdict.get("feedback", "")).strip()
        if not isinstance(score, (int, float)) or not math.isfinite(score) or not low <= score <= high:
            return {**metadata, "error": redact(f"judge returned score {score!r}, outside [{low}, {high}]", secrets)}
        if not feedback:
            return {**metadata, "error": "judge returned no feedback"}
        return {**metadata, "score": score, "feedback": feedback}
    except Exception as exc:
        if ledger and "usage" in metadata and "cost_source" not in metadata:
            computed = metadata.get("cost_usd")
            if computed is None:
                computed = priced_cost(relai_dir, metadata.get("model"), metadata.get("usage"))
            metadata.update(cost_usd=computed, cost_source=None if computed is None else
                            "provider" if cost_of(metadata.get("usage")) is not None else "pricing")
            record_spend(relai_dir, "judge", metadata, spend_ref(relai_dir, trial_dir))
        return {**metadata, "error": redact(f"{type(exc).__name__}: {exc}", secrets)}


def spend_ref(relai_dir: Path, trial_dir: Path | None) -> str:
    if trial_dir is None:
        return "self-test"
    resolved, root = Path(trial_dir).resolve(), relai_dir.resolve()
    return resolved.relative_to(root).as_posix() if resolved.is_relative_to(root) else Path(trial_dir).name


def write_result(out: Path, result: dict) -> None:
    """Keep each attempt once in history; the existing result path remains the latest view."""
    out.parent.mkdir(exist_ok=True)
    history = out.with_suffix(".attempts.jsonl")
    previous = None
    if out.is_file() and not history.exists():
        try:
            previous = load_json(out)
        except (OSError, ValueError):
            pass
    with history.open("a", encoding="utf-8") as handle:
        if isinstance(previous, dict):
            handle.write(json.dumps(previous) + "\n")
        handle.write(json.dumps(result) + "\n")
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def trials(paths: list[Path]):
    """Yield (trial dir, result) for every Harbor trial under the given directories."""
    for root in paths:
        for path in [root / "result.json", *root.glob("*/result.json"), *root.glob("*/*/result.json"),
                     *root.glob("*/*/*/result.json")]:
            try:
                data = load_json(path) if path.is_file() else None
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict) and "trial_name" in data:
                yield path.parent, data


def self_test(task: Path, config: dict, relai_dir: Path) -> int:
    toml = load_toml(task / "task.toml")
    judges = [ev for ev in declared_evaluators(toml) if ev.get("type") == "judge"]
    if not judges:
        print(f"{task.name}: no judge evaluators")
        return 0
    empty = {"schema_version": "ATIF-v1.7", "agent": {"name": "relai-synthetic", "version": "0"},
             "steps": [{"step_id": 1, "source": "user", "message": "Hello, I need help with my request."},
                       {"step_id": 2, "source": "agent", "message": ""}]}
    prohibition = toml.get("metadata", {}).get("relai", {}).get("prohibition", False)
    status = 0
    for ev in judges:
        result = judge_one(config, relai_dir, task, ev, empty, {}, synthetic=True, ledger=True)
        if "error" in result:
            print(f"FAIL {ev['id']}: {result['error']}")
            status = 1
        elif result["score"] >= ev.get("max_score", 1.0) and not prohibition:
            print(f"FAIL {ev['id']}: full marks for an empty reply, so this judge cannot fail. Feedback: {result['feedback']}")
            status = 1
        else:
            print(f"PASS {ev['id']}: empty reply scored {result['score']}")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="*", help="Harbor or native run directories or folders containing them")
    parser.add_argument("--self-test", metavar="TASK_DIR", help="check that a task's judges can fail")
    parser.add_argument("--force", action="store_true", help="re-judge trials that already have results")
    parser.add_argument("--dry-run", action="store_true", help="print input sizes and estimated cost; call no model")
    parser.add_argument("--relai-dir")
    args = parser.parse_args()
    relai_dir = relai_root(args.relai_dir)
    config = evals_config(relai_dir).get("judge", {}) or {}
    if config.get("mode") == "subagent":
        print("relai.toml [judge].mode is 'subagent': a fresh subagent writes judges/<id>.json instead of this script")
        return 2
    if args.self_test and args.dry_run:
        parser.error("--self-test calls the model; run it without --dry-run")
    if args.self_test:
        return self_test(Path(args.self_test).resolve(), config, relai_dir)
    if not args.runs:
        parser.error("name run directories, or use --self-test")
    secrets = secret_values(relai_dir)
    written = errors = unresolved = 0
    for trial_dir, result in trials([Path(p) for p in args.runs]):
        raw = str(((result.get("task_id") or {}).get("path")) or "")
        task = resolve_task_dir(raw, relai_dir, trial_dir.parent)
        if task is None:
            print(f"{trial_dir.name}: task {raw!r} not found; run Harbor with absolute task paths or judge from "
                  "the directory Harbor ran in")
            unresolved += 1
            continue
        trajectory_path = trial_dir / "agent" / "trajectory.json"
        crashed = result.get("exception_info") and result.get("verifier_result") is None
        toml = load_toml(task / "task.toml")
        neutral = bool((toml.get("metadata", {}).get("relai", {}) or {}).get("agent_neutral"))
        if crashed or (not trajectory_path.is_file() and not neutral):
            continue
        trajectory = load_json(trajectory_path) if trajectory_path.is_file() else None
        for ev in declared_evaluators(toml):
            if ev.get("type") != "judge":
                continue
            out = trial_dir / "judges" / f"{ev['id']}.json"
            if out.exists() and not args.force:
                try:
                    if "error" not in load_json(out):
                        continue
                except (OSError, json.JSONDecodeError):
                    pass
            if args.dry_run:
                try:
                    prompt, _ = build_prompt(config, relai_dir, task, ev, trajectory, secrets, trial_dir)
                except (OSError, ValueError) as exc:
                    print(f"{trial_dir.name} {ev['id']}: would error: {redact(str(exc), secrets)}")
                    continue
                guess = estimate(config, relai_dir, prompt)
                cost = guess["input_cost_usd_estimate"]
                print(f"{trial_dir.name} {ev['id']}: {guess['input_chars']} characters, about "
                      f"{guess['input_tokens_estimate']} input tokens, "
                      + (f"about ${cost:.4f} input cost" if cost is not None else "cost unknown (no [pricing] entry)"))
                continue
            result = judge_one(config, relai_dir, task, ev, trajectory, secrets, trial_dir)
            write_result(out, result)
            written += 1
            errors += "error" in result
            print(f"{trial_dir.name} {ev['id']}: " + (f"error: {result['error']}" if "error" in result
                                                       else f"{result['score']}"))
    if args.dry_run:
        return 1 if unresolved else 0
    print(f"judged {written} evaluator result(s), {errors} error(s), {unresolved} trial(s) whose task was not found")
    return 1 if errors or unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
