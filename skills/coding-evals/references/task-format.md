# The agent-neutral task format

Write each task from the contract in `relai/docs/files.md` (*An agent-neutral coding task*). The
plugin ships only the [verifier](../verifier/): `coding_checks.py` and `test.sh`, copied into each
task's `tests/`, used as they are unless adapted under [checks](checks.md) (*Adapting the
verifier*).
Record each verifier copy's source and adaptations using the
[project-copy policy](../../start/template/docs/upgrades.md); updating the plugin does not
update an existing task, and frozen copies follow controlled repair.

```
relai/tests/<id>/
├── task.toml            # [agent].timeout_sec, [verifier].timeout_sec, [metadata.relai] with agent_neutral = true and [metadata.relai.coding]
├── instruction.md       # the developer's request (redacted)
├── README.md            # "Evidence" (source, request origin, behavior, evaluators, known failures, contamination, network, agent instruction files at the start, validation and health) and "Author notes" (design reasoning, validity risks)
├── environment/
│   ├── Dockerfile       # authorized base image, toolchain, the repository at the start commit, the leak guard
│   └── repo.bundle      # the start commit and its ancestors only
├── solution/solve.sh    # applies the reference fix; Harbor's oracle agent runs it
└── tests/               # reaches the container only after the agent is done
    ├── test.sh, coding_checks.py   # the plugin's verifier (or a recorded, tested adaptation)
    ├── verify.py        # one call per code evaluator (the library's docstring shows one)
    ├── params.json      # commands, globs, the start commit and the protected manifest
    ├── protected/       # the start commit's protected files
    ├── hidden/          # hidden test files
    └── judges/          # copies of the shared judge evaluators' rubrics
```

## Steps

1. **Commits.** The start and fix commits ([sources](sources.md)) and the fix date; whether the
   source is public comes from scope.
2. **Workspace history.** Bundle the start commit's history alone: fetch the start commit into an
   empty bare repository as `refs/heads/main`, then bundle that explicit ref. Clone with
   `git clone -b main <bundle> /app` rather than relying on the bare repository's default HEAD.
   Resolve source and bundle paths from the stated build context; never change the source
   repository. The full history up to the start is what agents see in real use, so do not
   shorten it to save space without the user's agreement, recorded as a measurement choice.
   Every task repeats a similar copy: check one bundle's size, multiply by the planned tasks, and
   show that estimate and where the tasks will live with the task table, before building. When that is too much for where tasks live, a large public repository
   can be fetched in the Dockerfile at the start commit instead, or the tasks can live in a
   separate repository ([scope](scope.md), *The repository*). The start commit must not hold the
   eval project itself (`relai/`), which `check_task.py` refuses.
   A shallow bundle does not clone. When the user agrees to a shorter history, fetch the start
   commit at depth N and rewrite the cut-off commit into a parentless root with fixed author,
   committer, dates and message, so every build yields the same commits; bundle that or do it in
   the Dockerfile. The rewritten start is the task's `start_commit`: assert it as HEAD in the
   Dockerfile, keep the leak guard, and record N and the rewrite in the README.
3. **Dockerfile.** An authorized base image pinned by tag or digest (public for the bundled hosted
   recipe; local/private infrastructure is allowed by the shared contract). Digest pinning is
   optional when a tag meets the reproducibility requirement. Use the toolchain the start
   commit pins, `git`, `curl`, `bash` (agents install with them) and `python3` 3.8+ (the
   verifier). The repository at `/app` as the working directory, dependencies installed from its
   lockfile, and the leak guard `RUN ! git -C /app cat-file -e <fix commit>`. A rewritten history
   (a setup variant, a shortened history) changes commit ids but not file contents, so also
   guard on content: on the host, take the blob id of each file the fix adds or changes
   (`git rev-parse <fix>:<path>`) and add `RUN ! git -C /app cat-file -e <blob>`, skipping any
   blob the start history already holds (a revert restores an earlier version). Never install a
   later release of the project itself.
   An image rebuilds from its first changed line: put guards, task-specific lines and a setup
   variant's installed files after the dependency install, so a fix to them or a variant does
   not reinstall dependencies. Run health checks with `--no-delete` so later rounds reuse the
   image, and remove the images once the task is frozen. When several tasks come from one large
   repository, a shared, pinned base image holding its toolchain saves rebuilding it per task;
   it must not hold the repository or a dependency version later than a task's start pins, and
   the bundled hosted recipe needs it public.
4. **Request.** `instruction.md`: the developer's words, redacted, with no file names, diagnosis
   or approach they did not give; or, when they left none, a symptom written from the source
   (`request = "symptom"`, [sources](sources.md)).
5. **Reference fix.** `git diff <start> <fix>` over the source files, without the test files that
   become hidden tests, applied by `solution/solve.sh`.
6. **Hidden tests.** The fix's added or changed tests in `tests/hidden/`, mapped in
   `params.json` `hidden_tests.files`, with a command that runs only them. Rewrite assertions on
   names the fix happened to introduce so they check behavior through a public interface. With no
   tests in the fix, write some.
7. **Suite.** `suite.command` runs the repository's tests, deselecting those that already fail at
   the start (list them in the README). Add `build.command` when the project has a build or type
   check. Commands call the test runner directly, not a script the agent can edit unless that
   script is protected. Time the suite on the first task: it runs in every trial and health
   run, so cost grows with its runtime. When it is slow, offer the runner's own selection of
   tests related to the changed files (`vitest related`, `jest --findRelatedTests`) as the user's
   choice, stating its limit (a regression outside the selection goes unseen), and record it.
8. **Globs and the snapshot.** `protected`: CI files, and the existing tests unless
   [checks](checks.md) puts them in `restore`. Every hidden test path must match `protected`
   (the verifier refuses otherwise); with the existing tests in `restore`, list the hidden files'
   own paths. `scope.allowed`: where any correct fix may go, generously. Then run
   `coding_checks.py protect` (its docstring).
9. **Evaluators.** The standard set and the project's shared evaluators ([checks](checks.md)),
   plus the lesson's checks; declare each in `task.toml` under the id `verify.py` or the judge
   uses. Link each applicable repository requirement to its evaluator in the task record;
   process requirements must reach a judge with `trajectory` in its inputs
   ([repository requirements](checks.md#repository-requirements)).
10. **Check.** `python3 relai/bin/check_task.py relai/tests/<id>`.
11. **Validate.** Establish environment readiness, evaluator validity and oracle/nop health
    as below; record the evidence in the task record.
12. **Review, preview the checks, freeze.**

## Validation

Oracle/nop health alone does not establish that the agent can work normally or that every
legitimate solution passes. Before freezing, collect evidence for all three:

- **Agent environment.** In a fresh instance of the final task environment, before verifier
  restoration or hidden-test installation, run the repository's documented test/build commands
  as the agent's execution user, with its permissions and runtime settings. Start without caches
  or artifacts left by health runs. Record commands, user, outcomes, known baseline failures and
  intentional differences from verifier commands. Failures due to the starting bug are expected;
  setup must allow normal verification, including required cache and output writes. Check with
  the reference fix when needed to distinguish baseline behavior from an environment defect.
  Then list what the image and those commands left in the workspace (`git status --porcelain
  --ignored`). A file under a `protected` or `restore` glob (a build output written into a
  protected folder) is deleted before the verifier's commands, which can break them, and under
  `protected` it also scores every agent that runs the documented commands as changing tests.
  Exclude it from those globs or stop creating it; `new_files_ok` stops only the score.
- **Evaluator validity.** Identify an assumption the tests share with the reference fix and
  demonstrate that a requirement-consistent alternative passes, using another solution or a
  targeted executable probe. Cite why the request permits it and record the observed result;
  merely different code or a hypothetical pass is insufficient. Control incidental time,
  randomness and initialization state in fixtures. Where ordering matters, ensure timestamps and
  insertion order express the intended scenario; do not impose an order the request leaves open.
  For dependencies that can change task validity between runs, apply
  [validity across runs](../../eval/references/test-design.md#validity-across-runs).
  Preview process judges on synthetic run records that satisfy and violate each applicable rule,
  keeping the final output identical where possible. For a required lint run after edits, include
  a successful run, a skipped run and a run followed by another relevant edit. Also check a
  conditional rule when it does not apply, a blocked command and an incomplete recording, using
  the evidence limits in [safe process](checks.md#safe-process-shared-evaluator).
- **Shortcuts.** Before review, try the cheap ways an agent could pass a check without the fix
  or leave it unable to see: fix the bug outside the repository (in an installed dependency the
  request names), change the git configuration or environment variables the commands read, add
  a configuration in a subfolder that turns off a format or lint check
  ([checks](checks.md#what-the-verifier-guards-against)), and follow every documented setup
  command with the task's network setting. Fix what gets through,
  or record why a check cannot see it.
- **Health controls.** Run Harbor's `oracle` and `nop` agents on the final task, then
  `summarize.py`: the reference fix must score every outcome check at full marks and untouched
  code must fail the primary check. When the task records a first attempt
  ([sources](sources.md), *Check the first attempt*), run it as a third control: it should fail
  the primary check. Investigate unexpected scores rather than assuming the
  reference fix or evaluator is right. A hidden-test command that chains cases (`a && b`) shows
  only the first failure: run each case alone on the untouched code and record which fail; a
  case that passes there shows nothing about the fix. Resolve the findings from validation and
  the independent review before rerunning the controls, since each round rebuilds images and
  repeats the full suite in every graded run: while a task is still changing, get its verdicts
  from local controls (*Trusted commands and offline preparation*), and run Harbor's on the
  revision you send for final confirmation. These controls call no model.

## Trusted commands and offline preparation

Test commands must use trusted tooling rather than workspace substitutes. For a standard-library
Python suite, one starting recipe is:

```sh
python3 -I -S -B -c 'import unittest, sys; sys.path.append("/app"); unittest.main(module=None)' discover -s tests
```

This loads the runner before exposing project imports, keeps standard-library paths ahead of
`/app`, and disables bytecode explicitly (`-I` ignores environment flags). Adapt for the real
layout/toolchain and verify that tests genuinely execute, including a failing control. This does
not protect against an agent modifying the interpreter or the entire toolchain; keep the existing
scope/integrity checks and protect other command-steering inputs relevant to the repository.

When the execution engine is unavailable, tell the user what is missing and the options
(`relai/README.md`, Prerequisites). Then, and while tasks are still changing, useful preparation
can proceed in disposable copies: clone the bundle with its explicit branch, check that the fix is absent, apply the
reference solution in one copy, leave a no-fix control in another, and exercise the original
verifier's local hooks (`RELAI_WORKSPACE`, `RELAI_LOGS`, `RELAI_PARAMS`). Use absolute paths for
those hooks and separate logs per control. Run `verify.py` with trusted verifier imports and
`-I -S -B`; **never run `tests/test.sh` on the host**, because its cleanup stops every other process
(it refuses when it can tell it is not in a task container, but do not rely on that).
Exercise the evaluator-validity probe above where possible. Local preparation does
not establish image build, dependency access, containment or Harbor health: leave those pending.

After the last artifact-changing check, rerun `check_task.py` on the delivered task and inspect
its contents. Keep generated caches and temporary probes out of it. Do not present a static check
from before later edits or test-generated files as validation of the final artifact.

## The network and web tools

A task whose fix can be found online (a public repository, a published release of the project
that contains the fix) can be gamed by fetching it, and reading trajectories catches only some of
that, so such tasks run restricted by default; the rest run open, as in real use, since a
container cannot reach a private fix. State the default once per project at the scope checkpoint
rather than asking; the user may choose open, for a project or a task. Record the setting in each
task's README and say in the report which tasks ran open. Dependencies are already installed in
the image, so restricting rarely breaks a task; the agent-environment
[validation](#validation), run with the task's network setting, shows it. `check_task.py` flags
only `public = true` with an open network; a fix in a published release is yours to spot. To restrict, set `[agent] network_mode = "no-network"`, or
`"allowlist"` with `allowed_hosts` for a dependency mirror; Harbor lets an installed agent reach
its model host (the [Harbor notes](../../eval/references/harbor-notes.md)). Server-side web tools
run at the model provider, past any network limit; restricting the network also switches them off
(the Harbor notes). On an open network every compared agent uses the same web-tool setting. On an open network, still read the trajectories of surprising
passes for a fetched fix.

## One request per task

The bundled Harbor coding-task path supplies one instruction and no follow-up. Stopping before
a risky change can serve as a limited proxy, but does not establish that the agent asks well,
understands approval and finishes afterward. State that limit in the task and claims. When the
full interaction matters, use a suitable existing interactive runner or propose the missing
capability within scope; do not imply that a one-shot proxy measures the whole interaction.
