# Making tests harder

Use when the agent passes a test reliably, a risk's probe came back "not triggered", a triage
found weak signals that occur together, or the user wants existing tests combined into a harder
one. The aim is a realistic case that exposes a real failure, not a trick.

## Ground rules

- **A harder test is a new test.** The easier one stays as a regression check. Name the new test for its behavior and list its sources in its `README.md`.
- **Realistic only.** Every added difficulty must be something real users or real data do: check
  it against traces, the domain's data, or the user's word. Unrealistic pressure finds failures
  nobody will meet.
- **Attributable.** Keep one evaluator per observable failure you are probing, so a failure says
  which behavior broke. Its `covers` lists every requirement and risk it probes.
- **Verify the ingredients exist.** Before building, confirm in the data that the scenario is
  possible (the second matching order exists, the decoy variant is in stock, the state
  transition can happen) and that each ingredient alone is in scope for the agent.

## The hardening ladder

These are useful difficulty dimensions, not a required order. Isolate one when attribution
matters, or combine justified dimensions when that better probes the mechanism:

1. **Ambiguity:** remove the detail that made the right choice obvious; add a second candidate
   that also fits (two orders with the item, two users with the name).
2. **Decoys:** add near-miss options that are cheaper, closer or listed first (a variant that
   differs in the one attribute the user cared about).
3. **Order and timing:** put the out-of-scope request first, the critical detail late, a request
   right after a state change (after an item modification, after a cancellation), or a change
   of mind mid-conversation.
4. **Load:** more orders, items, steps or history the agent must search before acting.
5. **User behavior:** passive ("Okay."), impatient, insistent after a refusal, vague, offering
   someone else's details; always within the simulated user's goal and knowledge.
6. **Combination:** two or more of the above, or a compound case (below).

## Compound cases

Two behaviors that each hold up alone can fail together: the agent's attention is split, or the
first behavior changes the state the second depends on. Build one when:

- **Weak signals co-occur** in real runs (a triage's lane C pairs): the scenario reproduces the
  situation in which both appeared, so it stands for real traffic;
- **two tests combine naturally:** one user could plausibly bring both requests in one
  conversation, the data supports both at once (same user, or one user whose state allows both),
  and neither precondition undoes the other. Combine the scenarios into one simulated user's goal
  and carry over each source test's evaluators, renamed if needed;
- **a refined risk** (its single test did not trigger) sits on the same mechanism as a confirmed
  one: pair it with the trigger that works.

Combine only situations that can occur together for the actual agent and user. Two or three
behaviors are a useful starting point; choose complexity from realism, attribution, runtime and
budget rather than a fixed cap.

## Reporting

A harder test the agent passes is "not triggered under these conditions": useful, record it on
the risk page. Report a failure with its difficulty dimensions or combination and whether each
source test alone still passes, distinguishing supported causes from hypotheses.
