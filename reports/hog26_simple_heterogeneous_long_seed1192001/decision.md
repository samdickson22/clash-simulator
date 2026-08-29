# Seed 1192001 short-sequence termination decision

Date: 2026-08-29

## Decision

Terminate the run after its exact update-85 checkpoint.  Do not promote any
checkpoint from this lineage.  Preserve the artifacts as a rejected temporal
credit-assignment control.

## Evidence

- The first paired free-running screen at update 65 regressed from the parent's
  6-6 to 5-7 and lost 0.667 crowns/game relative to the parent.
- A retrospective screen of the earlier same-design update 60 also regressed
  from 6-6 to 4-8.
- Training remained finite and stable; this was not a numerical or MPS failure.
- The PPO rollout and recurrent backpropagation length was eight decisions.
  At eight simulator ticks per decision and 50 ms/tick, each learned sequence
  spans only 3.2 seconds of battle time.
- GAE is computed independently inside each eight-step rollout.  Terminal
  outcome advantage therefore reaches at most eight decisions directly, while
  critic bootstrapping must propagate value across many later episodes.
- Opponent elixir pacing, four-card cycle evidence, counterpush construction,
  and most defensive sequences operate over tens of seconds.  The current
  recurrent update horizon is structurally mismatched to those behaviors.

## Replacement

Keep the same parent, total transition budget, paired heterogeneous opponent
league, reward, masks, anchor, and optimizer settings.  Increase rollout and
truncated-backpropagation length from 8 to 64 decisions (3.2 to 25.6 seconds),
reducing updates from 512 to 64 while preserving 262,144 learner transitions.
This crosses the full terminal boundary roughly every 12 updates and exposes
five complete match cycles per row within the same sample budget.
