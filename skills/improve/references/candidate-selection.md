# Choosing among candidates

Selecting the best of several alternatives needs the same agreed objective as a single
candidate, plus a rule fixed in advance, because picking the best of several adds selection
effects.

Before building the second alternative, record the selection rule in
`relai/work/improve/plan.json`, the loop contract or equivalent project records: objective metric,
tests, attempts, the evidence needed to
distinguish candidates, guardrails, and tie-break order. Give reviewers this agreement and the
selection results, separately from diagnostic notes. Follow the recorded rule.

- Respect explicit user priorities. For behavioral-score ties, the default order is lower measured
  cost (tokens and turns as supporting evidence), fewer runtime failures or turn-limit hits, then
  the smaller and more general change. Missing measurements cannot win a tie-break. For cost or
  latency objectives, use that metric first and agree remaining priorities before comparison.
- If evidence does not distinguish candidates on the objective, report an unresolved comparison or
  tie and apply only the declared tie-break. If distinguishing finalists is worthwhile and the
  budget permits, add attempts first on cases where they disagree.
- A heterogeneous aggregate from `summarize.py` does not override the agreed metric or guardrails.

## Held-out and final evidence

The split roles and permitted reuse are in the project's `relai/README.md`
([bundled terms](../../start/template/README.md#terms) when absent). When the held-out set is too small or
unrepresentative to support selection, explain the limitation and offer a relevant held-out
slice or a narrower claim; do not require an additional split to proceed. Final tests are not
for choosing ([eval: benchmarks](../../eval/references/benchmarks.md)).

## Reporting

Report how many candidates were tried, which rule chose the delivered one, any unresolved ties,
and repeated use of held-out or final evidence. An improved development or held-out score may be
reported with those limits; never label it an untouched final result.
