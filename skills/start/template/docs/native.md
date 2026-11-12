# Native runners: trial layout

A project-native runner may keep its own formats when they preserve the shared execution and
evidence guarantees in `../README.md`. The layout below, including an ATIF trajectory, is for
interoperability with the bundled consumers; it is not required for every native integration.

For that interoperability, a native runner writes what a Harbor job writes, as far as the checkers read it, so
`summarize.py`, `check_trajectory.py` and the judges work unchanged. Containment follows the
*Containment* rule in `../README.md` (Fixed rules). Per run directory:

- `result.json` for the run: `{"n_total_trials", "stats": {"n_errored_trials",
  "n_completed_trials"}, "runner": "native", "runner_id", "runner_command", "batches": [{"git_head",
  "git_dirty", "started", ...settings}]}`.
- One directory per trial (test x attempt), unique per test path, with `result.json`:
  `{"trial_name", "runner": "native", "runner_id": "<name>", "runner_command": "<command template>",
  "task_id": {"path": "<absolute test dir>"}, "task_checksum": "<dir_digest of the test dir>",
  "verifier_result": {"rewards": {...}} or null, "exception_info": {"exception_type"} or null,
  "agent_result": {"n_input_tokens", "n_output_tokens", "cost_usd"}, "git_head", "git_dirty"}`.
- The example captures original `evaluator_definitions` before executing a trial:
  `[{"id", "type", "min_score", "max_score"}, ...]`, with bounds materialized. This optional
  result field lets summaries interpret old scores without substituting today's definitions.
  Legacy results remain usable with an explicit current-definition interpretation notice.
- In each trial directory: `agent/trajectory.json`, `verifier/reward.json`, `verifier/feedback.json`,
  `verifier/errors.json` as in `files.md` Scores (paths relative to the trial directory instead
  of `/logs`), `judges/` after judging, and the run's own logs.

A code evaluator may call the benchmark's own grader, but still writes a score and feedback per
declared evaluator, or an error; a grader that could not run is an error, never a zero. A trial
whose run failed has `verifier_result` null and an `exception_info`. Never trust the runner's
exit status; the files decide. A trial rerun after an interruption starts from an empty
directory.

Runs from different runners, or native runs with different `runner_id`s, produce comparison notices. Keep
the `runner_id` for a before/after pair whose commands differ only in paths or the candidate's
configuration; change it when how trials run or are graded changes. Explain whether observed
differences across identities support the intended claim. Validate grading on
synthetic passing, failing and empty trajectories.

The plugin's example `native_runner.py` (copied to `bin/`) writes this layout around a per-trial
command and passes the agent only the variables named with `--pass-env`.
