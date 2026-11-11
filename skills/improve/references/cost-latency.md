# Cutting cost or latency while holding scores

Use when the agreed objective is cost or latency. The scores on the agent's tests become constraints
(guardrails within agreed bounds) and cost or latency per trial is the target.

## Before the first change

- **Measure, don't estimate.** Read cost and tokens per trial from the trajectories' recorded
  usage (`final_metrics`), and wall-clock per trial from the declared runner's results. A number the runtime
  did not report is "not measured", never a guess.
- **Evidence and variability.** Choose repetitions and relevant cases for the expected resource
  gain, behavioral guardrails, observed variation and budget. No universal repetition count applies.
  If a stochastic build precedes evaluation, sample that build's variation when it matters;
  rescoring one build measures a different uncertainty.
- **Map where tokens and time go** (static prompt, history, tool definitions, tool output,
  internal model calls, retries, model choice), and write down what must stay exact
  (identifiers, paths, errors, user requirements).
- **Register the decision criteria:** meaningful resource improvement, behavioral bounds and
  evidence needed to justify acting.

## Levers, roughly cheapest and safest first

1. **Waste in the agent loop:** repeated or redundant tool calls, re-reading the same data,
   retries on errors that cannot succeed, tool results far larger than needed. Count them in the
   trajectories first; cost follows actions, not prompt length.
2. **Instructions that trigger work:** "verify twice", "be thorough", mandatory plans or summaries.
   Census how often the agent actually obeys each before removing it; text the agent ignores is
   cheap when cached and removing it saves little.
3. **Caching:** a stable prompt prefix, no dynamic content in it, cache reads visible in usage.
4. **Context size:** trim exposed tools and schemas, deduplicate or summarize tool output with a
   way to retrieve the full text, summarize history as state.
5. **Output length:** shorter replies save tokens and latency but change what users see; show
   the user the trade.
6. **Model and reasoning effort (if allowed):** route simple calls to a cheaper model; a stronger
   model at lower effort often takes fewer steps. Compare settings by measured cost with
   guardrails held.

## Adopting a change

Keep a change only when all three hold on comparable runs: behavioral guardrails preserved,
evidence supports the agreed resource improvement, and the predicted mechanism visible in the
trajectories (fewer tool calls, fewer turns, shorter outputs). Claim savings only
from comparable usage in both runs. A saving without its mechanism is an unexplained confound;
report it, don't ship it.
