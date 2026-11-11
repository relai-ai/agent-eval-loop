# Optional priority suggestions

When the choice of what to investigate next is not obvious, one way to decide is to weigh
exploitation (items whose recent loss is high) against exploration (items rarely or never
measured). This is a suggestion for your own reasoning, not a procedure: explore differently when
you judge that better, and say why. Rankings never set batch size, evidence requirements, budget
or acceptance.

Define normalized loss for the current objective and record the definition. For behavioral success
this might be `1 - score`; resource objectives need an explicit normalization of avoidable cost or
latency. Do not silently equate expensive cases with bad ones. Use development evidence only;
exclude incompatible setups, and do not mix rejected candidates' scores into the incumbent's
history as if they described the current agent.

A simple bandit-style heuristic, per item (a test or case) and per group of related items, over
observations oldest first:

- Effective attempts update as `decay * previous + 1` on every observation, including an attempt
  that produced no usable loss.
- The first usable loss sets the mean; later ones update it as `decay * mean + (1 - decay) * loss`.
- Priority is `mean_loss + exploration * sqrt(log(total_effective_attempts + 1) / effective_attempts)`,
  with `decay` and `exploration` from Defaults in `relai/README.md`.
- Never-tried items are exploration opportunities. Items with only failed measurements have
  unknown loss: investigate the measurement before ranking them.

These are suggestions, not confidence estimates or expected gains. Record the selection rationale
and any overrides in the experiment records.
