# Opponent model inside K4C-r16's rollouts: results (exploration)

2026-10-14, bot-lead implementation sub-agent, all games on 127x03. Exploration tier, not preregistered.
Design: [DESIGN.md](DESIGN.md); log: [PROGRESS.md](PROGRESS.md). Code: `bot/search/oppmodel.py` (`K4O-*`),
`bot/search/opp_run.py`.

**Answer: no.** No style aggregation, online style inference, or extra rollout opponent beat K4C-r16. The best arm
(C, `x25bd47`) gave +0.017 in our engine on two independent banks, below the +0.02 gate, and −0.008 in RoyaleSim.
K4C-r16 stays the best bot.

## Validity
- **Equivalence.** `K4O-mean` (the re-implemented reduction with the frozen arithmetic) reproduces K4C-r16's
  `command_sha256` on 620/620 games: 20 from the first version (`bot-opp-eq`) and 600 from the final code
  (`bot-opp-hl`, all HEADLINE cases × R3a and v1).
- **Determinism and errors.** No wall clock enters any decision. 0 errors in 12,507 games.
- **Weights fit on a separate bank.** Fixed weights and the B blend were chosen on the FIT bank (BASE
  2249738988533344, drawn with `os.urandom` before any result), never on HEADLINE.

## Table

- Paired = arm − K4C-r16 on the same cases; "both"/"pooled" = equal weight over opponents.
- 95% bootstrap CIs.
- **CPU** = process time in `act` per searched decision, in ours; arms within a block ran at similar load on 03.
  Load-matched K4C-r16 (= `K4O-mean`) is 0.416 s and 41.0 rollouts per decision.

| arm | what | CPU s/dec | rollouts/dec | decisions changed vs mean | FIT bank, ours (vs K4O-mean) | **HEADLINE, ours** | **HEADLINE, RoyaleSim (R3a, v1, rext-bc)** | fresh bank |
|---|---|---:|---:|---:|---|---|---|---|
| K4C-r16 (= K4O-mean) | mean of 3 styles | 0.416 | 41.0 | – | – | – | – | – |
| A1 `min` | pessimistic min | 0.423 | 41.1 | 7.5% | −0.030 [−0.063, +0.003] (R3a −0.080) | −0.007 [−0.042, +0.028] | not run (< +0.02) | – |
| A2 `w50.25.25` | best fixed weights on FIT | 0.425 | 41.0 | 1.7% | +0.002 [−0.028, +0.032] | −0.003 [−0.033, +0.027] | not run | – |
| A2 `w100.0.0` | balanced only (cheap) | 0.248 | 24.1 | – | −0.008 [−0.043, +0.027] | −0.012 [−0.047, +0.025] | not run | – |
| B `lo50.25.25-hi100.0.0` | online blend by the opponent's elixir at issue | 0.414 | 40.7 | 4.6% | +0.045 [+0.012, +0.077] | **−0.010 [−0.043, +0.027]** | not run | – |
| C `x25bd47` | + balanced opponent with 47-tick delay, weight 0.25 | 0.482 | 48.6 | 9.3% | +0.017 [−0.018, +0.052] | +0.017 [−0.017, +0.052] (R3a +0.043, v1 −0.010) | **−0.008 [−0.034, +0.019]** (R3a −0.013, v1 +0.010, rext-bc −0.020) | not run (rule: RoyaleSim ≥ +0.02) |
| C `x25di40` | + defense opponent deciding every 40 ticks | 0.435 | 48.1 | 8.0% | +0.018 [−0.017, +0.052] | +0.008 [−0.025, +0.042] | not run | – |
| C `x25bi30` | + balanced opponent deciding every 30 ticks | 0.457 | 47.6 | 3.9% | −0.007 [−0.043, +0.028] | not run | not run | – |

**Other FIT-bank grid rows (vs K4O-mean, both opponents):**
- `w0.0.100`: −0.022
- `w0.100.0`: −0.008
- `w25.25.50`: −0.003
- `w25.50.25`: −0.002

## Reading
- **The scripted styles are nearly interchangeable for ranking.**
  - Re-weighting them changes only 1.7–3% of decisions.
  - Dropping pressure and defense entirely (balanced only) costs −0.01 ± 0.035 for 41% fewer rollouts.
  - The 3-style refine is near-redundant; it is not where strength comes from.
- **min hurts vs R3a** (−0.08 on the FIT bank) and is null on HEADLINE. Pessimism over three bots that all lose to us
  mostly adds caution.
- **Online inference (B) can't be done over the 3 styles.**
  - In real games vs our bot, all three scripted styles play at about 2.9 elixir with the same placements. They are
    almost always under threat, and style only matters when they are not.
  - Real opponents differ sharply: v1 plays at 7.6 elixir, R3a at 4.2.
  - B therefore inferred an opponent *type* (low or high elixir) and blended the per-opponent best weights from the
    FIT bank. Its FIT-bank +0.045 was selection noise: −0.010 on HEADLINE.
- **A slower rollout opponent (C)** is the only lever with a repeatable signal in ours (+0.017 on two banks, mostly
  vs R3a). It does not transfer to RoyaleSim, the primary engine, and costs +18% rollouts.
- **Overall.** As in value-search and candidates, the binding constraint is not the opponent mixture inside 160-tick
  scripted rollouts. Changes that move only 2–9% of decisions cannot buy +0.02.

## Recommendation
- **Keep K4C-r16.** Do not ship any K4O arm.
- **`K4O-w100.0.0` (balanced-only refine) is a cost lever, not a strength lever:** 41% fewer rollouts at
  −0.012 [−0.047, +0.025]. Use it only if the compute is re-spent elsewhere (e.g. more candidates or roots).
- **Not tried: a human-like opponent in Rust (a new `rollout_e1` style fit to v1/IL statistics).**
  - It needs a new native build and pin.
  - The cheap proxies (slower or less frequent opponents) moved nothing in RoyaleSim, so the expected value is low.

Raw logs on 127x03, `/mpac/sdicks02/jobs/clasher/`:

| directory | contents |
|---|---|
| `bot-opp-eq` | equivalence and smoke |
| `bot-opp-cal` | style-feature calibration |
| `bot-opp-fitA`, `bot-opp-fitBC` | FIT bank |
| `bot-opp-hl`, `bot-opp-hl2` | HEADLINE, ours |
| `bot-opp-rsim` | HEADLINE, RoyaleSim |

Reproduce with:
- `python -m bot.search.report <dirs> --baseline K4C-r16|K4O-mean --opponents R3a,v1[,rext-bc]`
- runner: `bot-opp-run.sh {bot.search.opp_run|bot.eval.headline} ARGS`
