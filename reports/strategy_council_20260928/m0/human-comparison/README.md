# Policy vs human behaviour diagnostic

`compare.py` puts a pilot policy's play behaviour next to human IL_Replay play on the 16 pilot cards. It covers card choice, tempo, elixir, timing, placement and reactions. Nothing here is fitted. It only reads the pilot run directories, it uses the pilot runtime snapshot read-only (`python -B`, temp numba cache), and it ran single-threaded under `nice -n 15`.

## Data sources

**Human, `p16`** (`human_plays_p16.jsonl.gz`): all 262 tier-(a) pilot-card matches from `../human-prior-scan`, with both sides human, giving 524 sides. **All of them are Hog 2.6 mirrors** (523 of 524 sides; one side has Knight instead of Ice Golem). This set therefore holds no human data for Giant, Prince, Tesla, Zap, Goblins, Archers or Dark Prince. The rest of the corpus is no different: of the 14,347 corpus sides whose deck is fully in P16, 14,305 are Hog 2.6. The 663 "≤2 missing per deck" matches are only indexed (decks, counts). Their event streams were never saved, so they cannot be used here.

**Human, `ext`** (`human_plays_ext.jsonl.gz`): this set covers the cards Hog 2.6 lacks. It holds 600 G66/S120 tier-(a) matches whose decks contain Giant, Prince, Dark Prince, Archers, Goblins, Tesla, Zap or Knight, picked round-robin with the rarest cards first. That gives 867 sides that contain at least one of those cards: Giant 100, Prince 83, Dark Prince 101, Goblins 62, Archers 119, Tesla 229, Zap 289 and Knight 374. The reference is **card-conditional**, because the other cards in those decks are outside the pilot roster.

**Re-simulation.** Both human sets were re-simulated open loop in the pilot-runtime scalar engine. The loop is the same as `resim_pilot.py`: L11, base forms, hand cycle reconstructed from first-play order. The re-sim supplies the hand and elixir at each play. Placement acceptance was 99.7%, and the hand had to be forced for 0.2% of plays. About 17% of human plays come after the simulated match has ended, typically because the sim leads on crowns at 180 s while the real match goes to overtime. Those plays are continued **economy-only**, using the engine's elixir, phase and refill rules without combat.

**Policy, monitor** (default): the latest row of a run's `training-monitor.jsonl`, which is a rolling 20-update window. It covers the learner's plays against every opponent kind, with decks from `roles_v2/training.json`. Match length comes from `opponents/worker-*-outcomes.jsonl` in the same window. Plays per match when a card is in the deck is computed as `card_share × plays_per_match / P(card in a sampled training deck)`.

**Policy, sim** (optional): `sim-policy` plays N games with a checkpoint against the fixed public scripted pool (balanced, pressure and defense, round-robin). It uses `clasher.rl.eval.evaluate`, stochastic decoding, a CPU and one torch thread. The candidate uses the Hog 2.6 deployment deck by default, so it matches the human `p16` deck. It records the same per-play data as the human re-sim. Runs with fewer than 20 games are reported but left out of the divergence ranking.

## Metrics (definitions in `results_*.json → definitions`)

- **Play-when-held** is the plays of a card divided by the own plays made while that card was in the 4-card hand. This is the monitor's `held_play_share`, computed the same way for humans. Plays per match, raw and per card while the card is in the deck.
- **Elixir at play** is the own elixir just before paying for the play.
- **Timing** uses four phases: early (0–60 s), mid (60–120 s), double (120–180 s) and overtime (180 s and later). For each phase it reports the share of plays and plays per minute spent in that phase, plus each card's first-play time.
- **Placement** uses canonical coordinates with your own side at the bottom. It reports the own-side share, the left-lane share, distance to the nearest bridge centre, and depth (y).
- **Reactions** are measured for each opponent play: the latency until your next play, the share answered within 2, 4 and 6 s, and the share of your plays that fall within 6 s of an opponent play. For each opponent card it also lists the top response cards and the share of responses placed in the same lane and on your own side.

## Results: seed 2901 scripted, monitor update 101 (827,392 decisions)

File: `results_seed-2901_scripted_u0101.json`. Console summary: `compare_s2901_scripted.log`.

Play-when-held, human reference against the policy monitor:

| Elixir cost | Human (mean) | Policy (mean) | Cards (human → policy) |
|---|---:|---:|---|
| 1 | 0.39 | 0.94 | Skeletons 0.38→0.94, Ice Spirit 0.39→0.93 |
| 2 | 0.28 | 0.90 | Ice Golem 0.31→0.93, Log 0.29→0.87, Zap 0.21→0.88, Goblins 0.31→0.93 |
| 3 | 0.31 | 0.70 | Cannon 0.21→0.62, Knight 0.34→0.78, Archers 0.38→0.70 |
| 4 | 0.23 | **0.036** | Hog 0.28→0.048, Musketeer 0.18→0.048, Fireball 0.10→0.013, Tesla 0.22→0.008, Dark Prince 0.37→0.064 |
| 5 | 0.32 | **0.004** | Giant 0.31→0.004, Prince 0.32→0.004 |

Plays per match while the card is in the deck, human against policy: Prince 4.8 vs 0.15, Giant 4.1 vs 0.17, Tesla 5.8 vs 0.41, Fireball 4.2 vs 0.53, Hog 7.8 vs 1.6, Musketeer 5.9 vs 1.6, Dark Prince 4.7 vs 1.9. Zap goes the other way at 3.7 vs 9.3. The cheap Hog 2.6 cards run 0.4–1.6 plays above human values, and Knight and Archers run 2–3 higher.

1. **Starvation tracks elixir cost.** Humans pick every card at a similar rate when it is held, roughly 0.2–0.4. The policy plays 1–2 elixir cards about 90% of the time they are held, 3-cost cards about 70%, 4-cost cards 4% and 5-cost cards 0.4%. Giant, Prince, Tesla and Fireball are not singled out: every card costing 4 or more is starved, including the deck's win condition, Hog.
2. **Elixir.** Humans play from a bank, with a median of 6.6 elixir at play in `p16` (7.5 in `ext`). 31% of their plays are made at 8 elixir or more, and 7–14% at full elixir. In the 2-game smoke, the policy played at a median of 2.1 elixir and never above 8. It spends whatever trickles in on the cheapest card, so it rarely reaches 4 or more. This is the likely cause of point 1.
3. **Tempo.** Humans make 13.7 plays per minute (9 in early and mid, 16.5–18 in double and overtime). The policy monitor shows 14.6 plays per minute, with 45.7 plays in 189 s matches against 58.9 in 259 s for humans. In the smoke games the policy reached 12 plays per minute early and 23–29 in double and overtime.
4. **Placement.** Human Hog goes at the bridge 99% of the time (y 14.5, 2.5 tiles from the bridge centre). Human Fireball lands on the opponent side 82% of the time and comes late (median first use at 88 s, 58% in overtime). Human Giant also goes at the bridge (median 1.8 tiles from the bridge centre). In the smoke games the policy put Musketeer deep (y 1.5–2.5) and opened with a Fireball at t=0 on empty ground.
5. **Reactions.** Humans answer half of opponent plays within 2 s and 84% within 6 s. They answer Hog 96% of the time within 6 s with a median of 1.75 s, using Cannon (31%) or Skeletons, Musketeer or Ice Golem, placed in the same lane 73% of the time. Overall policy latency in the smoke run looks similar (median 1.5 s, n=100), but n=2 is far too few to compare.
6. **The gap grows with training.** At update 12 (98k decisions, `--at-decisions 98304`), play-when-held was already skewed but milder: 0.87 for 1-cost cards, 0.59 for 2-cost, 0.46 for 3-cost, 0.10 for 4-cost and 0.021 for 5-cost. By update 101 it had become 0.94, 0.90, 0.70, 0.036 and 0.004.

Context from the same window: the learner won 2 of 69 games against the fixed scripts, and went 32–53 (wins–losses) against the initial checkpoints. The alarms `starved_card`, `entropy_collapse_card` and `entropy_collapse_mode` are active.

**Caveats.**
- Humans played L16 evo/hero cards in real matches. The re-sim uses L11 base forms, so human elixir and hand values come from the engine economy fed with the recorded timing. The re-sim matched the recorded timing in all but 0.01% of plays: elixir top-ups were almost never needed.
- The `ext` reference mixes in decks that are not pilot decks.
- Monitor statistics pool every opponent kind and deck in the training pool.
- The smoke run used `policy_v2_update_000012.pt` (98k decisions, the latest saved checkpoint at the time) and only 2 games. It shows the pipeline works and gives indicative elixir, placement and reaction numbers. It is not evidence about the update-101 policy.

## How to run

```bash
cd reports/strategy_council_20260928/m0/human-comparison
RT=../runtime-snapshots/pilot-runtime-v1
hc() { OMP_NUM_THREADS=1 nice -n 15 $RT/.venv/bin/python -B compare.py "$@"; }   # works in bash and zsh

# Human caches (already built; ~15 min and ~31 min, one core each)
hc extract-human --pool p16
hc extract-human --pool ext --limit 600

# Monitor-only comparison against a run's latest monitor row
hc compare --monitor ../../pilot/v7r1-launch/runs/s2901/seed-2901/scripted/training-monitor.jsonl
```

**At the 1M checkpoints.** The milestone file is `policy_decisions_<decisions:09d>.pt`, where the decision count is the first multiple of 8,192 at or above 1M. Use `--at-decisions` so the monitor row matches the checkpoint even after training has moved on. Each game takes about 12–18 s on one core, so 30 games take about 8 min per run.

```bash
for s in 2901 2902 2903; do for arm in scripted scratch; do
  RUN=../../pilot/v7r1-launch/runs/s$s/seed-$s/$arm
  CK=$(ls $RUN/policy_decisions_0010*.pt 2>/dev/null | head -1); [ -n "$CK" ] || continue
  DEC=$(basename $CK .pt | sed 's/policy_decisions_0*//')
  hc compare --monitor $RUN/training-monitor.jsonl --at-decisions $DEC \
      --checkpoint $CK --sim-games 30 --out results_s${s}_${arm}_1M.json
done; done
```

`--candidate-decks training` (or a path to a deck JSON) makes the simulated games use the training deck pool instead of Hog 2.6. Use `sim-policy` on its own to build a `policy_sim_*.jsonl.gz` cache, then pass it with `--policy-sim`; the flag can be repeated.

## Files

- `compare.py`: extraction, policy simulation, statistics and ranking.
- `human_plays_{p16,ext}.jsonl.gz`: one record per side. Each play is stored as `[t, card, x, y, elixir, hand, accepted, hand_forced, elixir_topup]` (`accepted` is null for plays after the sim match ended).
- `policy_sim_s2901-scripted-u12-smoke.jsonl.gz`: the 2-game smoke run, in the same format.
- `results_seed-2901_scripted_u0101.json`, `compare_s2901_scripted.log`: the current comparison.
- `extract_{p16,ext}.log`: extraction logs.
