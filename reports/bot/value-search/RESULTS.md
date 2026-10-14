# Value-search: does a better leaf evaluator make K4S-st stronger? (exploration)

2026-10-14, bot-lead implementation sub-agent. Exploration tier: no preregistration. Design: [DESIGN.md](DESIGN.md);
log: [PROGRESS.md](PROGRESS.md). Code: `bot/value/` (features, fit, model, players, run, report, gen, probe), registered
as `K4SV-<model>[-h<T>][-x<P>][-e<P>][-nost]` in `bot/eval/headline.py` make_player.

**Answer: no, not in these forms.** A learned outcome value at the leaf makes K4S-st much *weaker* (−26 to −43 pp
paired). Mixed in at λ = 0.25 it is null (+0.003 [−0.057, +0.063]). Recalibrating phi's elixir↔board exchange rate is
flat (0.5×/2×) or harmful (4×). K4S-st stays the best bot.

## What was built
- **Exact leaf access.** `NativeScripts.rollout_commands(root, seat, a, [], style, 27, 27, 1, 1, 160, 10, 10, ew, True,
  False, False)` reproduces `rollout_e1` bit for bit (max |Δphi| = 0 on 5 roots, all plays + WAIT) and also returns
  the leaf `BattleState`. Timed waits 2401/2402 stay on `rollout_e1` and get the WAIT leaf's residual (V − phi) for the
  same opponent style.
- **Equivalence.** `K4SV-<m>-x0` (λ = 0) and `K4SV-phi` reproduce K4S-st's `command_sha256` on 4/4 and 6/6 HEADLINE
  R3a cases. Every arm differs from K4S-st only in the leaf number (or ew).
- **Features** (fair: public view of the planner's root/leaf, which includes only the belief-sampled hidden hand):
  phi's 7 `evaluation_parts`, both elixirs, 6 tower fractions, crowns alive, time/double/overtime, per-side per-lane
  per-half board value (cost × hp fraction), buildings / win-condition value / counts, optional own-hand multi-hot.
  `public_view` costs 0.1 ms; the whole V costs ~0.3 ms per leaf vs ~4.5 ms per rollout (+~7%).
- **Model.** Antisymmetric z = g(F(me)) − g(F(them)), BCE against the final outcome (draws 0.5); `lin` (option c) or
  2×64/128 MLP (option a). Used in phi units: logit / k_phi, where k_phi = 13.4 is the slope of a phi-only logistic
  fit. Clipped to ±1.99 so the frozen WAIT bonus and the |x| < 2 terminal rule keep their meaning.
- **Data.** 1,670 K4S-st games vs R3a/v1 (alternating) on fresh bank BASE 3041844146963296, disjoint from HEADLINE.
  ~117 search roots per game. Fit on the first 925 games (108k roots; game-level split, 183 test games).

## Offline (held-out games, `bot-value-fit1/fit*.json` on 03)

| model | AUC | notes |
|---|---:|---|
| phi (k·phi) | **0.800** | the frozen potential |
| lin1 (option c, 35 base features) | 0.787 | |
| mlp1 (128, +hand) | 0.792 | overfit (train LL 0.17); best at step 250 |
| mlp3 (64, no hand, wd .1, dropout .3) | 0.796 | |
| mlp4 (64, +hand, wd .1, dropout .3) | 0.809 | log-loss worse than phi |

Learned V is at **parity** with phi in global outcome prediction. Global AUC is dominated by tower state and deck matchup,
so it says nothing about ranking candidates within one decision.

## Deployment: HEADLINE-v1, our engine, cases 0–149, paired vs K4S-st on the same cases

K4S-st rows come from `bot-search-bc` (03). "both" = equal-weight mean over R3a and v1, cases resampled within opponent,
4,000 draws. "changed" = fraction of searched decisions where phi alone would have picked a different action from the
same rollouts.

| arm | leaf | vs R3a (paired) | vs v1 (paired) | **both** | changed | CPU s/dec† | rollouts/dec |
|---|---|---|---|---|---:|---:|---:|
| K4SV-lin1 | V (linear) at 160 t | −0.373 [−0.453, −0.287] | −0.187 [−0.273, −0.100] | **−0.280 [−0.340, −0.220]** | 0.245 | 0.277 | 32.7 |
| K4SV-mlp3 | V (MLP) at 160 t | −0.327 [−0.413, −0.240] | −0.193 [−0.273, −0.107] | **−0.260 [−0.320, −0.197]** | 0.248 | 0.281 | 33.1 |
| K4SV-mlp4 | V (MLP + hand) at 160 t | −0.387 [−0.473, −0.300] | −0.167 [−0.260, −0.080] | **−0.277 [−0.340, −0.213]** | 0.269 | 0.266 | 33.7 |
| K4SV-lin1-h80 | V at 80 t | −0.567 [−0.647, −0.487] | −0.240 [−0.327, −0.153] | **−0.403 [−0.460, −0.347]** | 0.275 | 0.156 | 32.1 (×80 t) |
| K4SV-mlp3-h80 | V at 80 t | −0.540 [−0.620, −0.460] | −0.327 [−0.413, −0.240] | **−0.433 [−0.493, −0.377]** | 0.283 | 0.164 | 32.3 (×80 t) |
| K4SV-mlp4-x25 | phi + 0.25 (V − phi) | +0.000 [−0.080, +0.087] | +0.007 [−0.073, +0.087] | **+0.003 [−0.057, +0.063]** | 0.128 | 0.218 | 36.6 |
| K4SV-phi-e50 | phi, elixir_weight 0.5 | −0.047 [−0.127, +0.033] | +0.027 [−0.047, +0.100] | −0.010 [−0.067, +0.047] | – | 0.278 | 36.9 |
| K4SV-phi-e200 | phi, elixir_weight 2 | −0.033 [−0.113, +0.047] | +0.020 [−0.053, +0.093] | −0.007 [−0.063, +0.050] | – | 0.235 | 36.1 |
| K4SV-phi-e400 | phi, elixir_weight 4 | −0.213 [−0.300, −0.127] | −0.160 [−0.247, −0.073] | −0.187 [−0.247, −0.127] | – | 0.213 | 34.6 |
| K4S-st (baseline) | phi, ew 1 | 0.740 | 0.840 | – | – | 0.306 | 37.0 |

† Process time inside `act` on searched decisions, on a shared, loaded 03. It is comparable only within a run. V adds
~0.3 ms per leaf (+~7%; microbenchmark). h80 halves the cost (0.16 s), but at a 40 pp loss.

RoyaleSim was **not run**. Every V arm is −26 pp or worse in our engine with CIs far from 0, and the phi re-weightings
are null, so no arm qualified for the primary engine. The HEADLINE gate needs a positive our-engine screen first.

## Why the learned V fails
- Play rate is unchanged (K4S-st 12.6 own plays/min, lin1 13.1, mlp3 12.2). V does not spam cards; it picks *which*
  card and where worse.
- In phi units, the fitted linear V puts ≈ 0 weight on board value (−0.0005 vs phi's 0.08) and a **negative** weight on
  own elixir advantage (−0.008 per elixir vs phi's +0.005). Within 160 ticks, candidates differ almost only in board
  value, elixir and danger. V's exchange rate between them is learned from on-policy states, where the policy makes
  elixir and board co-vary: a high own elixir means the opponent has a push on the board. So the rate is confounded,
  and V re-ranks ~25% of decisions on spurious terms.
- Shorter rollouts + V are worse still (−40 pp). The 160-tick scripted rollout is what resolves the near-term
  consequences of a placement; V cannot substitute for it.
- phi's own exchange rate is near a flat optimum. Halving or doubling `elixir_weight` is null (−0.01 ± 0.06), and ×4
  hurts (−0.19).

## Not tried, and why
- **(b) Student-policy rollouts.** The ExIt student consumes v5 packets built from the Python engine. A clasher_core
  leaf has no v5 encoder, so this needs a new native or Python packet path. It would also need a Python step loop with
  ~16 NN calls per rollout (~600 forwards per decision), so ≥3× the CPU. The h320 result (longer scripted play hurts)
  and the null student-as-proposer result argue against expected value here.
- **More outcome data.** The failure is identification (confounding), not variance: AUC was already at parity on 925
  games. 10× the games would not fix the sign of the elixir term.

## Recommendation
- Keep **K4S-st** (phi leaf, elixir_weight 1, 160-tick rollouts) as the best bot. Do not ship a learned outcome V as
  the leaf.
- If leaf evaluation is revisited, the target must be **action-conditioned**, not on-policy outcome. For example:
  - paired data from the *same* root with different first actions, continued by real players (K4S-st vs opponent) to
    the end of the game. That is an expensive counterfactual-rollout dataset, but it identifies the exchange rate.
  - a value trained only on tower-HP/time terms (no elixir/board), used as an additive time-aware correction.
- The cheaper lever stays **candidate quality** (search-scaling: st +5 pp). Leaf re-weighting is flat.

Raw logs on 127x03, under `/mpac/sdicks02/jobs/clasher/`:
- `bot-value-screen{1,2,3}`: arms;
- `bot-value-eq*`: equivalence checks;
- `bot-value-fit1`: models, fit json, cache;
- `bot-value-gen-127x03` and `bot-value-data/`: training roots.

Generator outputs on 04/08 are in `bot-value-gen-127x0{4,8}`. Models are in `bot-value-models/` on 03/04/08.

Reproduce with `python -m bot.value.report --base-dirs <bot-search-bc>,<bot-search-st-p1> --dirs <screen dirs>`.
