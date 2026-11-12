# Coding task review brief

You review, with fresh eyes, an agent-neutral coding task that another agent built, before it is
frozen. You only read. A task is good when any correct fix passes it, the untouched code fails it,
nothing the agent can see gives the answer away, and it scores every coding agent the same way.
Judge on evidence you can quote.

Read: `relai/README.md` and `relai/docs/files.md`; the task directory (`task.toml`,
`instruction.md`, `environment/Dockerfile`, `solution/`, everything under `tests/`); the
*Evidence* section of its README; its latest oracle and nop runs; the wiki pages it covers;
and its source (the session, pull request or commit named in `origin`), if you can reach it.
Skip the README's *Author notes* and any other design rationale or proposed verdicts; form your
own conclusions from the requirements and artifacts.

Check, with a verdict (pass, fail, unsure) and quoted evidence for each:

1. **Faithful request.** With `request = "verbatim"`, `instruction.md` is the developer's request
   as given (redacted), with no file name, diagnosis, approach or test name they did not give. With
   `request = "symptom"`, it states only the symptom a developer would report, agrees with the
   source, and gives nothing of how the fix works. Either way, a correction the developer made in
   reaction to an agent's mistake is not in it; it is a check instead.
2. **No answer reachable.** The workspace's history stops at the start commit (`check_task.py`
   checked the bundle; the Dockerfile has the leak guard). Nothing under `environment/` or in the
   instruction repeats a hidden test or the fix. No install step pulls a later release of the
   project itself, or of a dependency at a version that contains the fix. If the fix can be found
   online, the network and server-side web tools are restricted, or the README records that the
   user chose open.
3. **Any correct fix passes.** The hidden tests check behavior through public interfaces, not
   names or structure the real fix happened to choose. Inspect the executable alternative's
   evidence against the request: does it challenge a shared assumption, and do the scope globs
   allow it? Check fixture time, ordering and initialization for accidental constraints.
4. **Validated environment and controls.** Inspect the [validation evidence](task-format.md#validation)
   for the final task: documented commands ran in a fresh environment as the agent user, with
   baseline failures explained; the reference fix passes every outcome check and untouched code
   fails the primary check. Verifier health is not evidence for omitted agent commands.
5. **Honest suite.** Tests that already fail at the start commit are deselected and listed in the
   README; the suite passes with the reference fix; it does not depend on the network. The suite and
   hidden-test commands call the test runner directly, or through a script inside the protected
   globs, so the agent cannot redefine them.
6. **Protected snapshot.** `protected` covers the existing tests, CI files and every file that
   configures this repository's test runner, `restore` the files that can steer a run, the hidden
   test paths fall inside `protected`, and `tests/protected/` with its manifest was written by
   `coding_checks.py protect` from the start commit; `tests/test.sh` and `tests/coding_checks.py`
   are the plugin's verifier, or an adapted copy that `decisions.md` explains and whose verifier
   tests passed.
7. **Right checks.** The primary check reads the workspace. Code checks settle exact facts;
   judgments about what the agent did are judges. The lesson from the source (what went wrong in the session, what the
   revert fixed) has a check, and nothing is checked that the source does not support.
8. **Fair judges.** Each rubric states its standards and what full and zero marks need; the
   review-ready standards come from the team's real review comments or approved requirements.
9. **Agent-neutral.** Nothing in the workspace, instruction or checks favors one agent: no agent's
   config files beyond what the repository had at the start commit, no tool names in checks. The
   README lists the agent instruction files the start commit holds.
10. **Provenance and privacy.** `origin`, the commits, `fix_date` and `public` are right; secrets
    and personal data are redacted; the source repository is in the scope.
11. **Reproducible.** The base image is pinned (tag or digest), dependencies install from the
    lockfile, and `[agent].timeout_sec` leaves an agent time to do the work
    ([comparing](comparing.md), *Before any paid run*).

Report each verdict, then findings: what is wrong, the evidence, and the change that would fix it,
marked blocking or advisory. Write the report to `relai/work/reviews/coding-task-<id>-<date>.md`
if you can write files; otherwise return it.
