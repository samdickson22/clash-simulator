# HP1 RL: ExIt distillation set (spec for `bot.rl.learner --aux-data`)

Purpose: outcome RL **plus** distillation of the live search's decisions (DX1, reports/bot/pq/DX1-RESULTS.md:
75% of search's regret over v2 is play/wait timing; then Zap/ElectroSpirit/Cannon placement). The learner adds
`aux_coef ×` a weighted cross-entropy toward the teacher's action to every policy step. PPO, the KL anchor to v2 and
the terminal reward are unchanged.

## File: one `.npz`, rows = decision states of OUR seat where the policy can act and has a legal play
- Token features exactly as `bot.rl.actor.pack_records` writes them: `b_<key>` for every key of
  `imitation.model.inference.single_features(packet, d1, costs)` on the decision's model packet and D1 state. Ragged
  token keys (`ids, types, numeric, valid`) are concatenated with per-row counts in `ntok` (int32); every other key is
  stacked.
- `aux_play` (bool): teacher plays now (False = WAIT, including timed holds 2400–2402).
- `aux_slot` (int16, 0–3) and `aux_tile` (int16, 0–575): the teacher's play, action = slot·576 + tile (ignored when
  `aux_play` is False). A row whose play label is illegal under its masks is dropped from the loss entirely.
- `aux_w` (float32 ≥ 0): row weight, e.g. DX1's margin-based confidence: 0 for tied or unscored, larger for clear
  refined margins, with a per-game cap.
- Optional provenance arrays (`aux_game`, `aux_tick`, `aux_source`) are kept but not read.

## Sources (in order of value)
1. **Student trajectories (DAgger):** the RL policy plays and the live search (`res-lb-RF-wintp`, serial twin) is
   queried in shadow on the same packets. This covers the states the student actually reaches.
2. **DX1 search trajectories:** the DX1 cases replayed deterministically (same driver, tree, seeds; rows are
   deterministic) with a feature recorder that saves `single_features` output at each decision. The recorded DX1
   summaries lack full packets, masks and D1 history, so features must never be rebuilt from them.

Features must always be **recorded live** at the decision, through the same packet/mask/D1 path the actor's
`RLPolicy.sample` uses.

Every source records its sha256 and row count in reports/bot/hp1/RL-RESULTS.md before use. Selection uses a disjoint
validation split, never the G-S banks.

## A/B (registered when the first set exists)
run1 (outcome only) vs an arm started from the same snapshot with `--aux-data <set> --aux-coef λ` (λ from {0.1, 0.3}),
same league and deck mix, compared on the G-E/G-S screens.
