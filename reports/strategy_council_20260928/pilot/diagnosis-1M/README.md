# Pilot v7r1, scripted arm: learning dynamics at 1M decisions

Date: 2026-09-30. This was read-only analysis of the logs, monitors, opponent outcome logs, checkpoint metadata, the s2901 diagnostic evaluation, the human-comparison files and 300 s2901 scripted-demonstration games. Nothing under `pilot/v7r1-launch/runs/` was modified. Code was read from the pinned snapshot `m0/runtime-snapshots/pilot-runtime-v1`. Its `train_recurrent.py`, `selfplay_env.py`, `model.py`, `council_pilot.py`, `council_opponents.py` and `public_action_mask.py` are byte-identical to the working tree.

- `diagnosis-1M.json`: every table below, plus the full per-update series for all three seeds.
- `analyze.py`: regenerates the JSON. Run it with the pilot venv under `OMP_NUM_THREADS=1 nice -n 15`.

Coverage: s2901 reached 1M (123 updates). s2902 is at update 87 and s2903 at update 45; both are still running.

## Short answer

The weights are changing, but the policy is not getting better at winning. The dominant drift does not come from the reward. It comes from the entropy bonus. The pilot uses the default `entropy_coef=0.01` on the entropy of the flattened joint action distribution. By the chain rule, that entropy is

`H = H(type over legal slots + wait) + sum_k p(slot k) * H(location | slot k)`

The second term is placement entropy weighted by the probability of playing. A wait action has no location, so increasing `p(play)` increases `H` by up to about 5 nats per playable state (troops have 190 legal tiles; Zap and Fireball have 548). The bonus therefore:

1. Pushes `p(play | anything affordable)` toward `sigmoid(H_loc)`, about 0.99.
2. Pushes the card choice toward `p_k ∝ exp(H_loc,k)`, which favours Zap and Log (2-cost spells with whole-map or wide masks) over troops and over buildings.
3. Drives placements toward uniform-random over legal tiles.

All three effects appear in all seeds, in this order, and win rates fall at the same time. The cheap, immediate spending itself was already present in the warm start, and to a lesser degree in the scripted teachers. RL removed the waiting that remained and randomized placement. There is no sign error and no masking or likelihood bug.

## 1. Is learning happening?

**Update count.** 1M decisions at 8,192 per update is 123 PPO updates (122.07, rounded up).

- Updates 1–20 are critic-only warm-up with the actor frozen (KL = 0).
- That leaves 103 actor updates. KL early stop fired in 55% of them, and they averaged 43.8 of 64 minibatch steps, so roughly 4,500 actor optimizer steps in total.
- s2903 stops early far more often: 92% of updates, averaging 24 steps.

### s2901 per-update trajectory (selected updates; full series in JSON)

"loc H / play" is `loc_ent / play rate`, an approximate placement entropy per card played.

| update | phase | policy | value | EV | KL | clip | opt steps | type H | mode H | card H | loc H | loc H / play | play | noop when playable | W/L |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | critic | -0.000 | 0.0002 | +0.14 | 0.0000 | 0.000 | 64 | 0.127 | 0.106 | 0.133 | 0.142 | 2.68 | 0.053 | 0.874 | 0/0 |
| 20 | critic | +0.000 | 0.0025 | +0.35 | 0.0000 | 0.000 | 64 | 0.098 | 0.088 | 0.109 | 0.153 | 3.06 | 0.050 | 0.875 | 2/2 |
| 21 | PPO | -0.055 | 0.0001 | +0.53 | 0.0080 | 0.020 | 4 | 0.086 | 0.079 | 0.050 | 0.123 | 2.24 | 0.055 | 0.847 | 1/2 |
| 30 | PPO | -0.131 | 0.0049 | +0.29 | 0.0053 | 0.029 | 16 | 0.059 | 0.052 | 0.028 | 0.211 | 3.84 | 0.055 | 0.787 | 2/10 |
| 40 | PPO | +0.001 | 0.0024 | +0.73 | 0.0066 | 0.037 | 64 | 0.029 | 0.025 | 0.009 | 0.278 | 4.56 | 0.061 | 0.570 | 3/2 |
| 50 | PPO | +0.023 | 0.0037 | +0.73 | 0.0101 | 0.035 | 30 | 0.016 | 0.010 | 0.007 | 0.288 | 4.36 | 0.066 | 0.226 | 0/11 |
| 60 | PPO | -0.010 | 0.0044 | +0.92 | 0.0047 | 0.031 | 41 | 0.016 | 0.010 | 0.008 | 0.252 | 4.20 | 0.060 | 0.247 | 2/9 |
| 70 | PPO | -0.001 | 0.0069 | +0.94 | 0.0018 | 0.015 | 64 | 0.006 | 0.001 | 0.005 | 0.354 | 5.21 | 0.068 | 0.019 | 3/8 |
| 80 | PPO | +0.044 | 0.0028 | +0.97 | 0.0022 | 0.009 | 30 | 0.007 | 0.002 | 0.006 | 0.295 | 5.09 | 0.058 | 0.016 | 2/9 |
| 100 | PPO | -0.001 | 0.0017 | +0.98 | 0.0016 | 0.019 | 64 | 0.004 | 0.000 | 0.003 | 0.303 | 4.81 | 0.063 | 0.002 | 0/9 |
| 123 | PPO | +0.104 | 0.0023 | +0.99 | 0.0024 | 0.019 | 15 | 0.009 | 0.008 | 0.000 | 0.274 | 4.03 | 0.068 | 0.093 | 0/1 |

### 20-update windows, all seeds

| seed | updates | EV | KL | clip | type H | card H | loc H / play (nats) | noop when playable | train win rate |
|---|---|---|---|---|---|---|---|---|---|
| s2901 | 1-20 | 0.31 | 0 | 0 | 0.109 | 0.093 | 3.05 | 0.846 | 0.37 |
| s2901 | 41-60 | 0.76 | 0.0054 | 0.028 | 0.018 | 0.006 | 4.34 | 0.316 | 0.28 |
| s2901 | 101-123 | 0.97 | 0.0025 | 0.015 | 0.005 | 0.003 | 4.91 | 0.029 | 0.32 |
| s2902 | 1-20 | 0.20 | 0 | 0 | 0.085 | 0.080 | 3.14 | 0.824 | 0.41 |
| s2902 | 41-60 | 0.69 | 0.0032 | 0.016 | 0.007 | 0.004 | 5.31 | 0.094 | 0.30 |
| s2902 | 61-80 | 0.96 | 0.0027 | 0.010 | 0.005 | 0.004 | 5.31 | 0.085 | 0.32 |
| s2903 | 1-20 | 0.26 | 0 | 0 | 0.112 | 0.087 | 3.23 | 0.853 | 0.44 |
| s2903 | 21-40 | 0.81 | 0.0071 | 0.035 | 0.086 | 0.071 | 3.92 | 0.849 | 0.34 |
| s2903 | 41-45 | 0.91 | 0.0052 | 0.031 | 0.048 | 0.021 | 5.25 | 0.742 | 0.36 |

What the windows show:

- **Policy loss** is noise around 0 (±0.13) with no trend.
- **Value loss** is flat at about 0.004.
- **KL and clip fraction** shrink after about update 60, and the entropy factors move steadily, so the actor is being updated.
- **EV is misleading.** It is measured against λ-returns, which are mostly the old value, so it rises toward 1 as advantages shrink. It is not evidence of a good critic.
- **Entropy factors.** Type, mode and card entropy collapse to near zero; card entropy is mechanically zero once only one card is ever affordable. Location entropy is the only factor that rises.
- **Placement.** Per placement, location entropy goes from about 3.0 nats (about 20 effective tiles) to 4.9–5.3 nats (130–200 tiles). log(190) = 5.25 is uniform over the legal tiles for a troop.
- **Order of events.** In s2903, the placement entropy rises first while noop-when-playable is still 0.74. This matches the mechanism: the bonus raises placement entropy directly, and the push toward playing scales with it.

### Training win rate by opponent

Counts are wins/games, by the learner policy in use when the game was assigned. s2901 excludes 97 replayed duplicate games; see bug 3.

| seed | learner policy | all | scripts | warm-start copy | random-control (untrained) |
|---|---|---|---|---|---|
| s2901 | warm start (actor frozen) | 42/119 (0.35) | 6/62 (0.10) | 14/26 (0.54) | 22/31 (0.71) |
| s2901 | after updates 21-40 | 77/193 (0.40) | 14/96 (0.15) | 18/42 (0.43) | 45/55 (0.82) |
| s2901 | after updates 41-60 | 54/207 (0.26) | 4/98 (0.04) | 16/51 (0.31) | 34/58 (0.59) |
| s2901 | after updates 61-80 | 51/206 (0.25) | 4/103 (0.04) | 13/51 (0.26) | 34/52 (0.65) |
| s2901 | after updates 81-100 | 55/211 (0.26) | 5/93 (0.05) | 16/53 (0.30) | 34/65 (0.52) |
| s2901 | after updates 101-120 | 57/167 (0.34) | 0/70 (0.00) | 14/38 (0.37) | 43/59 (0.73) |
| s2902 | warm start | 94/229 (0.41) | 24/111 (0.22) | 24/64 (0.38) | 46/54 (0.85) |
| s2902 | after updates 41-60 | 67/211 (0.32) | 10/97 (0.10) | 20/57 (0.35) | 37/57 (0.65) |
| s2902 | after updates 61-80 | 67/211 (0.32) | 13/97 (0.13) | 18/53 (0.34) | 36/61 (0.59) |
| s2903 | warm start | 103/235 (0.44) | 29/119 (0.24) | 30/61 (0.49) | 44/55 (0.80) |
| s2903 | after updates 21-40 | 69/215 (0.32) | 13/107 (0.12) | 16/48 (0.33) | 40/60 (0.67) |

- Against scripts, the learner falls from 10–24% to 0–13%.
- The untrained random-control opponent is 26–29% of games but supplies 63%, 52% and 50% of the learner's wins in s2901, s2902 and s2903. Strategy line 91 says random opponents are "controls, not a major source of rewarded wins".
- s2901 fixed evaluation on the holdout decks:
  - balanced: 4/32 at 1M vs 5/32 for the warm start;
  - pressure: 4/32 vs 9/32;
  - matched cells combined: 8/64 vs 14/64.

## 2. Why the policy collapses to cheap, immediate spending

### Card mix (monitor, 20-update rolling window)

Play-when-held is plays of a card divided by the learner's placements while that card was in hand.

| seed | update | mean play cost | share cost<=2 | share cost>=4 | play-when-held, cost 1/2/3/4/5 | Zap | Log | Cannon (building) | Archers |
|---|---|---|---|---|---|---|---|---|---|
| s2901 | 7 | 2.25 | 0.61 | 0.13 | 0.85/0.59/0.44/0.09/0.02 | 0.34 | 0.29 | 0.41 | 0.39 |
| s2901 | 60 | 2.18 | 0.64 | 0.07 | 0.95/0.87/0.64/0.04/0.00 | 0.79 | 0.80 | 0.55 | 0.65 |
| s2901 | 122 | 2.19 | 0.64 | 0.06 | 0.95/0.91/0.69/0.04/0.00 | 0.91 | 0.87 | 0.39 | 0.86 |
| s2902 | 7 | 2.30 | 0.59 | 0.15 | 0.88/0.59/0.45/0.13/0.02 | 0.31 | 0.29 | 0.30 | 0.51 |
| s2902 | 87 | 2.16 | 0.65 | 0.07 | 0.95/0.90/0.62/0.05/0.00 | 0.87 | 0.89 | 0.30 | 0.78 |

### Elixir at play

| source | elixir at play q25/q50/q75 | noop when playable |
|---|---|---|
| scripted teachers (300 s2901 demo games) | 2.04 / 3.02 / 4.03 | 0.83 |
| warm-start policy (u12 smoke sim, actor = init; only 2 games) | 1.17 / 2.07 / 3.03 | 0.85 (training, updates 1–20) |
| 1M policy (30 sim sides) | 1.08 / 2.05 / 2.81 | 0.03 (training, updates 101–123) |
| humans (p16) | 4.91 / 6.59 / 8.53 | – |

### Verdict on each candidate cause

**(a) Action factorization, together with (b) the entropy bonus: primary cause.** There is an entropy bonus. It is `entropy_coef = 0.01` on `distribution.entropy()` of the flattened joint distribution; `action_type_entropy_coef`, `location_entropy_coef` and `conditional_slot_entropy_coef` are unset or 0.

- With `p = p(play)` and placement entropy `H_loc`, `dH/dlogit_play = p(1-p)[H_loc + log((1-p)/p)]`. This is positive until `p = sigmoid(H_loc)`.
- At the warm start (p ≈ 0.13, H_loc ≈ 2.7–3.0), the push is about 0.005 per playable decision. That is equivalent to a constant +0.05σ advantage bonus for playing in every playable state.
- The entropy-maximizing noop-when-playable is 0.045 at the warm-start H_loc and 0.007 at the 1M H_loc. Observed: 0.85 at the start, about 0.03 at 1M. The observed type entropy (about 0.005) also matches the entropy-maximizing value.
- The slot pull `∝ exp(H_loc,k)` explains which cards gained most. Zap (548 legal tiles) rose 0.34→0.91 and Log (256) 0.29→0.87, more than any troop. Cannon (117 tiles) and Tesla (128) fell or stayed flat, while the 3-cost troops Archers and Knight (190) rose.
- The factorization also means `p(play)` is the sum over legal slots competing with a single wait logit. Under the bonus, wait is one leaf against hundreds of placement leaves. In the likelihood, wait has one correctly normalized log-probability, so it is not mis-weighted.

**(c) Reward shaping: not a cause.** The objective-v1 potential has only crown, tower, tiebreak and early-king terms; there is no elixir or board term. At scale 0.05 the measured shaping total over s2901 is −13.6, against −456 from terminal win/loss rewards (about 3%). Cheap plays cannot exploit it.

**(d) Credit assignment: contributing, because it lets the drift go unopposed.**

- With γ = 1 and λ = 0.95, the GAE horizon is about 20 decisions, or 5 s.
- The payoff from banking elixir arrives 5–15 s later and reaches the timing decision only through the critic, which has seen about 1,300 games.
- The play-vs-wait advantage gap would have to stay above about 0.05σ in favour of waiting, in every playable state, to cancel the bonus. Nothing suggests the signal is that strong.

**(e) Advantage normalization and value baseline: no evidence of a problem.** Advantages are normalized over all decisions, including the roughly 90% of states where only wait is legal and the policy gradient is zero. That does not change direction. EV is not a meaningful health metric here (see above).

**(f) Opponent mix: secondary.** It does not drive the collapse, which happens against every opponent type. But it degrades the reward signal: most wins come from beating an untrained random policy, which spam handles fine.

**(g) Warm start: the origin of the cheap spending, not of the collapse.**

- The teachers spend at a median of 3.0 elixir; the 1-epoch BC student, at about 2.1. Its slot accuracy is 0.36–0.43.
- At update 1, play-when-held was already 0.85–0.88 for 1-cost cards and 0.02 for 5-cost cards.
- RL removed the waiting that remained (noop-when-playable 0.85 → 0.03), halved the share of 4–5 cost plays (0.13–0.19 → 0.06–0.07), and randomized placement.
- The humans' 6.6-elixir median was never present to lose.

## 3. Bugs and defects

1. **No sign error.** The loss is `policy − entropy_bonus + 0.5·value`, and the terminal reward is +1 to the winner, −1 to the loser.
2. **No masking error.** A card is masked only when `cost > elixir + 1e-6`. In teacher data, Giant and Prince are legal on 190 tiles when held and affordable. The learner never waits long enough to afford them; nothing makes them illegal at high elixir.
3. **Resume does not restore RNG (real bug, small impact).** s2901 resumed at update 13 and replayed the first run's games and opponent assignments exactly: identical log lines for updates 13–24 and 1–12, and 97 duplicate outcome rows. Updates 13–20 fitted the critic on duplicate data. Any resumed run will repeat env and opponent seeds.
4. **Recipe defect: the entropy target is the flattened joint** (§2a). Code already present supports per-factor coefficients, and `entropy_components` has a comment about avoiding noisier placement, but the pilot recipe never sets them.
5. **Noisy KL early stop.** The KL check runs per 2-sequence (256-decision) minibatch, so early stopping is erratic: 55–92% of updates.
6. **EV is computed against λ-returns,** so it trends to 1 regardless of critic quality.
7. **Alarms fired but are monitoring-only.** `entropy_collapse_card` and `entropy_collapse_mode` fired at updates 42/48 (s2901) and 32/38 (s2902). That is correct behaviour by design.

## 4. Recommendations, ranked by expected impact

| # | change | expected impact | within approved levers? |
|---|---|---|---|
| 1 | Remove the play-weighted location entropy from the bonus. Config-only, using existing flags: `--location-entropy-coef 0 --action-type-entropy-coef 0 --conditional-slot-entropy-coef 0.003`. The conditional slot entropy is normalized by p(play), so it has no play/wait bias. A cleaner code change is binary mode entropy plus p-independent conditional location entropy. Restart from the warm start rather than continue from 1M, which has already collapsed. | High: removes the dominant drift and the placement randomization | **No.** Recipe change; needs the user's OK |
| 2 | Take the untrained random-control out of the reward-bearing mix, or cap it at about 5%. Replace it with scripts or warm-start copies, and in the league phase with more historical checkpoints. It is currently 26–29% of games and 50–63% of wins, against strategy line 91. The first-1M mixture is frozen by code, so this applies to the league phase and to reruns. | Medium on signal quality, low on the collapse itself | **Yes**, under "improve opponent diversity" |
| 3 | Raise λ from 0.95 to 0.98–0.99 (horizon 50–100 decisions), so elixir-banking and defence consequences reach the timing decision. Alternatively, bring forward the planned event-time policy head (strategy line 175). | Medium; more variance | **No**, recipe change |
| 4 | KL-to-init anchor (`--anchor-checkpoint .../initialization/scripted.pt --anchor-policy-kl-coef 0.01–0.05`). It would stop the drift, but it anchors to a policy that already spends at about 2 elixir, and it runs against the approved direction. "Reduce anchoring" cannot apply: anchor coefficients are already 0. | Medium, wrong direction | **No**, and it conflicts with the strategy |
| 5 | Leave shaping at 0.05. Raising it would reward tower chip, i.e. Zap-to-tower spam. Leave γ = 1. | – | – |
| 6 | Instrumentation and robustness: log the mean advantage of play vs wait at playable states, and per-factor entropy-gradient shares; compute EV against Monte Carlo returns; restore or offset RNG on resume; check KL per epoch. | Enables verification; fixes bug 3 | Engineering, not recipe; affects future launches only (runs are pinned) |
| 7 | Human-like banking will not come from these teachers, which spend at a 3.0 median. It needs better warm-start supervision, such as human data or teachers that bank elixir. | Long-term | **No**, recipe change |

**Decision for the user.** s2902 and s2903 continue toward 5M under the same entropy target. The evidence suggests further compute will deepen the play-immediately, random-placement regime rather than recover. Under strategy line 179, that is a failure under a defective update, not a failure "with correct updates".

**Limitations.**

- "loc H / play" is a ratio of means, so it is approximate.
- The warm-start elixir-at-play figure rests on 2 simulated games. The monitor's update-1 play-when-held figures corroborate it.
- The play-vs-wait advantage gap was not measured, because rollouts are not stored.
