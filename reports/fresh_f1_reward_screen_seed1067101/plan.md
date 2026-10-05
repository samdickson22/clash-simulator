# Fresh F1 reward screen — seed 1067101

This is a predeclared causal reward experiment, not a checkpoint promotion.

All three arms resume the same current-client, causal-frame, structured-memory F1
checkpoint and use the same 1,720-deck card-balanced training pool, seed, rollout
schedule, opponent league, optimizer, frozen-policy KL, and simulator-native
rehearsal. Each arm receives exactly 20 PPO updates.

The only treatment is:

1. `legacy`: `Phi(s_next) - Phi(s)` and the existing full-elixir leak penalty;
2. `gamma`: `0.995 * Phi(s_next) - Phi(s)`, terminal potential zero, leak retained;
3. `gamma_noleak`: gamma-correct shaping with the leak penalty disabled.

The training screen rejects any numerically unstable arm. Development evaluation
uses new matched seeds across all six strategy bots, random play, and direct
parent play. Human-camera timing and card metrics are diagnostic no-regression
evidence only, because the YouTube corpus cannot supply game-outcome credit.
Only one arm may advance to a fresh held-out deck/archetype evaluation; the other
two arms and all development seeds become quarantine evidence.

No new handcrafted reward terms, defense scenarios, architecture changes, or
per-arm hyperparameter tuning are permitted in this screen.
