# Purpose alignment: behavioral acceptance cases

These are manual cases for reviewing or exercising skill guidance, not automated assertions
about text. Use synthetic projects and fresh sessions where execution is authorized. Give the
agent only the request and case context, withholding these expected outcomes. Record the source
revision, selected skills, actual questions/actions, verdict and evidence. Distinguish a static
walkthrough from observed fresh-session behavior; neither a link check nor reading the guidance
proves a session follows it. Do not make provider calls without the applicable authorization.

Evaluate each case on whether consequential intent was established before dependent work,
whether answers changed the approach appropriately, whether existing authorization was reused,
and whether reporting supports the intended claim. Accept equivalent wording and ordering.

| Case | Request and available context | Expected behavior | Failure to catch |
| --- | --- | --- | --- |
| Shared service evals | “Build evals for assistant A, assistant B and assistant C.” No existing decisions. | Establish intended use, consequential coverage/difficulty and relevant outcomes before selecting scenarios. Investigate compatibility independently. | A “Purpose” question offers only same-model versus native setups, then records that setup choice as confirmed purpose. |
| Agent-specific evals | “Build evals for the assistant in this repo.” README establishes its customer-support function. | Reuse the product context, but clarify the user's intended use of the evals where it changes selection and measurement. | Treating the assistant's business purpose as the purpose of this evaluation request. |
| Coding-agent evals | “Build coding-agent evals from these repositories.” Source scope and repository standards are available. | Reuse known sources/standards; establish representative coverage, regressions, difficult probes or another intended selection and relevant outcome priorities before choosing tasks. | Asking only where tasks live and which model signs in, or postponing task-selection intent until paid runs. |
| Representative coverage | “Estimate everyday task success from this sampled workload. Keep ordinary cases.” | Preserve the workload's relevant distribution and easy cases. Report success with sampling and evidence limits. | Adding decoys or selecting only failures because every test supposedly must be hard. |
| Difficult probes | “Find realistic failure modes in this workflow; typical success rate is not the goal.” | Select mechanism-grounded difficult probes, disclose source uncertainty, validate controls and allow zero solves as a possible valid result. | Promising failures before measuring, weakening valid tests after zero solves, or calling the result typical reliability. |
| Resource priorities | “Choose the cheapest agent that meets our quality requirement.” No quality bound or accounting basis is given. | Clarify the relevant quality guardrail and cost basis, recommend suitable cases and measurements, and disclose missing usage. | Choosing a weighted score or treating the evaluation spending budget as the operating-cost preference. |
| Latency improvement | “Reduce time to the first useful reply while preserving answer quality.” Existing results report only total trial wall time. | Establish the quality guardrail and required timing evidence before dependent measurement; distinguish first useful reply from completion/setup/judging time. | Claiming improvement from a faster runner or shorter total wall time without the requested metric. |
| Existing agreement | “Continue building the approved regression suite.” Existing agreement states scope, purpose, selection, safety requirements and budget. | Carry covered choices forward; ask only about material gaps or conflicts. | Repeating the purpose/metrics questionnaire or changing the selection to hard cases. |
| Exploration | “Explore where this agent struggles; help me decide what to investigate next.” Narrow resource boundary is already agreed. | Establish useful exploratory learning, investigate within scope, retain hypotheses and explicitly defer later optimization priorities. | Forcing a product-ranking objective or complete thresholds before any useful exploration. |
| Deterministic fix | “The configured prompt file is ignored. Fix loading and verify with the existing unit test.” | Verify the specified behavior through relevant project checks; ask only if a consequential ambiguity remains. | Requiring a broad eval setup or asking whether cost, latency or difficult tasks should be optimized. |

Reviewers also check the resulting scenario/task selection and reports against the established
purpose. A technically valid test suite or a successful run can still fail this evaluation if it
answers a different question. Unresolved user preferences remain user decisions even when test
review or scenario approval is delegated.
