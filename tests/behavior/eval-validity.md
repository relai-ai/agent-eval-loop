# Eval validity: behavioral acceptance cases

These are manual cases for reviewing or exercising skill guidance, not assertions about text.
Use synthetic projects and fresh sessions where execution is authorized. Give the agent only
the request and case context, withholding expected outcomes. Record the source revision, skills
used, decisions, actions, verdict and supporting evidence. Distinguish static walkthroughs from
observed fresh-session behavior. Do not make provider calls without applicable authorization.

Evaluate whether the agent preserves the scenario, correct outcomes and claimed challenge under
the shared [reproducible-task rule](../../skills/start/template/README.md#fixed-rules). Accept
equivalent implementations and wording. Existing approvals cover choices within their boundaries.

| Case | Request and available context | Expected behavior | Failure to catch |
| --- | --- | --- | --- |
| Historical task | Build a regression from a dated invoice dispute. The request explicitly asks what was owed on that historical date. | Keep fixed dates and historical framing; establish that scoring uses that period's facts. | Rewriting all dates relative to today or rejecting the test because it contains calendar literals. |
| Mixed clocks | Build shared personal-assistant evals. Services can report a seeded date; runtime prompts and OS tools expose actual time. No clock strategy is agreed. | Inspect the participants' time sources. Explain feasible strategies and their effects on realism, compatibility, effort and cost; recommend one and ask before dependent construction. | Mocking the service clock alone and assuming the whole trial uses that date, or silently choosing a materially different setup. |
| Prior authorization | Continue an approved suite whose decision record chooses actual time and generated relative scenarios. The integration already demonstrates consistent inputs and evidence. | Reuse that decision and validate relevant scenario relationships. Ask again only for a material uncovered tradeoff. | Repeating the clock-strategy question for every test. |
| Future past event | A mileage scenario says the user already drove on Wednesday this week. Construction and preview occurred on Friday. | Exercise a contrasting earlier weekday and repair or disclose the invalid relationship before relying on the test. | Treating relative dates as sufficient proof of validity. |
| Lost challenge | A business-day probe generates a closure near the reference date, but at one boundary the closure lies outside the counted interval. Correct answers still pass. | Check that a weekday-only shortcut fails the affected evaluator under relevant contrasts. Repair the scenario or narrow coverage through the existing decision process. | Checking only whether the reference answer passes at multiple dates. |
| Judge key | Fixtures and prompts use a trial-relative due date; the semantic rubric embeds the build date's expected answer. | Derive the expected answer from the instantiated scenario and supply it through declared hidden judge evidence. | Leaving a static key in the rubric, asking the judge to infer today's date, or exposing the hidden key to the evaluated agent. |
| Expiring batch | Repeat a suite with an approved validity window that closes midway through the batch. | Check the boundary before spending where possible; use a per-trial executable guard and retain actual conditions. Report affected attempts separately from scored successes and agent failures. | Scheduling expiring tests first as the sole safeguard, trusting README prose, or letting invalid numeric scores enter success rates. |
| Changed policy | Reuse a baseline after a live refund policy changes; frozen task files have identical digests. | Check which policy each trial exercised and whether the scenario and expected outcome remain valid. Qualify comparability and use controlled repair or re-baselining when needed. | Treating matching digests or valid scores as proof of a comparable measurement. |
| Changed coverage | Repair a frozen public-holiday lookup test by replacing the holiday with a company closure. | Explain the loss of public-holiday lookup coverage and surface the uncovered scope choice. Preserve prior results and follow controlled repair before renewed comparison claims. | Calling the successor equivalent because both tests count business days. |

During review, also check that preview effort follows the relevant dependencies and consequences,
rather than a fixed number of dates or paid runs. Fixture and evaluator checks do not establish
control of the evaluated agent's runtime clocks. A remaining difficulty difference between
generated instances must limit comparison claims even when both instances are valid.
