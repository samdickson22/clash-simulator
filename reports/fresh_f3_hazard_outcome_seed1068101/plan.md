# Fresh F3 cumulative-hazard outcome screen — seed 1068101

Ordinary causal rehearsal was rejected at coefficients 0.01 and 0.025. Both
arms matched the 1.24% human base rate with excellent Brier/ECE but had no
ranking skill and deterministically went all-wait, 0-12 versus both random and
balanced opponents. Conversely, outcome-only PPO learned useful gameplay but
predicted play on every held-out replay frame.

This fresh architecture separates the two jobs:

- the existing PPO mode/card/tile policy learns strategic value;
- a dedicated public-frame urgency head learns play-event hazard with square-
  root class weighting (9.0 for the measured 80.99:1 wait/play imbalance);
- the model subtracts the exact weighting log-odds to recover calibrated hazard;
- calibrated hazards accumulate in model-owned recurrent state using
  `1 - (1 - cumulative) * (1 - instantaneous)`;
- deterministic inference plays when cumulative hazard reaches 0.5, the median
  event threshold, then resets internally after the actual card play;
- no external timer, action override, simulator state, or target-conditioned
  mask is used.

The control is a fresh 1,697,877-parameter current-client model, SHA-256
`97c03ebca6a1225bef4d5cf3eaab66c3362f42642b0687d7d10d101a495e9470`.
The first screen is 40,960 random-opponent PPO transitions with causal hazard
coefficient 1.0. The measured initial hazard gradient norm is 0.0405 versus
recent PPO norms near 0.17. Advancement requires stable optimization, a
noncollapsed deterministic simulator policy, improved held-out hazard average
precision, and no random/balanced regression. It cannot authorize held-out or
promotion evaluation.
