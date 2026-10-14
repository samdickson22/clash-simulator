# Step 4: engine decision (exploration), 2026-10-14

**Decision:**
- **Planning and training stay on our engine,** the Rust core (Python reference for the match loop).
- **The trusted number comes from RoyaleSim** (0.1.34, 15.535.29 rules). From now on the HEADLINE's primary engine
  is RoyaleSim.
- **Our engine gets calibrated** toward the native recordings, one rule at a time. Each fix is gated by the
  577-fixture fidelity harness, RoyaleSim's scoring method applied to our data. It is not tuned toward RoyaleSim
  itself.

## Evidence

| question | result | source |
|---|---|---|
| Which engine matches the real game (native 15.535 recordings, 577 train+val matches)? | RoyaleSim 15.535: 78.8% of non-tower units within ¼ tile, HP exact 81.8%. Ours: 51.4%, 65.1%. Paired +26.1 pp for RoyaleSim, better in 530/577 matches; ours is worse on 47/48 cards | FIDELITY.md |
| Which is faster for search? | Our Rust core steps at 34k ticks/s with a 5 µs clone. RoyaleSim steps at 14k on its faithful arm (31k on 16.402); its branch costs 5 ms, or 9.8 µs with our fork's `restore_from` | SPEED.md, RSIM-CLONE-SPIKE.md |
| How much strength does our planner lose when the game runs on the faithful engine? | **Little and not significant.** K4S-b64 pool score: ours 0.864 [0.847, 0.882], RoyaleSim 0.851 [0.833, 0.869]. Paired RoyaleSim − ours on the same 300 cases: vs v1 −0.033 [−0.093, +0.023], vs R3a −0.017 [−0.077, +0.047], vs scripted ≈0 | STRENGTH.md, HEADLINE.md |
| What would a RoyaleSim-native planner cost? | Clone and determinism are solved (fork, 9.8 µs). The scripted rollout policies and the leaf scorer (`rollout_e1`, Rust) would need porting: days of work, and 2.4× slower stepping | RSIM-CLONE-SPIKE.md, inventory §3 |
| Where is our engine wrong? | A long tail of card-specific rules, each with a concrete root cause | divergence/*.md |

The card-specific rules in that last row:
- Spirit HP data: ElectroSpirit and FireSpirits have 90 base HP against the native 84 × 2.56.
- The lane-2 spawn-ring mirror for formations of 5 or more units.
- The Goblinstein formation.
- Hut first-spawn delays.
- The Miner's underground route and tower coverage.
- Ghost reveal timing.
- One-tick-late tower damage in 6 of 8 first divergences.

## Why this split

- **Model mismatch is cheap at today's strength.** A W-screen8 search that plans on a 51%-faithful model loses at
  most a few points when the game is played on the 79%-faithful engine. The planner's value comes from tactical
  timing (WAIT screen, tempo) and robust scoring, not exact unit trajectories.
- **Porting the planner** to RoyaleSim would cost days and halve the rollout throughput, for a gain bounded by that
  measured difference, which is ns, ≤ ~9 pp at the CI edge.
- **Evaluation should use the faithful engine.** It is cheap: about 1 CPU-minute per game, the same as ours. Every
  candidate is now evaluated in RoyaleSim, with ours as a second column.
  - If a candidate's two numbers start to diverge (paired difference significant), that's the signal that model
    mismatch has started to matter. Then planner porting gets reopened.
- **Calibrating ours is still worth doing**, cheaply.
  - The fixes are rule-level and verifiable in 48 s on 577 fixtures.
  - The data-level fix (spirit HP) propagates to the Rust core through the shared card config.
  - Rule fixes need Python + Rust parity, so they're batched.
  - Each fix requires no regression on any card, and a new runtime snapshot is cut before bots use it.

## Limits

- The strength comparison uses our own opponents, v1 and R3a. They are model-free, so engine-agnostic, but they see
  RoyaleSim through the translator, which has known gaps (rsim-adapter/NOTES.md).
- "RoyaleSim ≈ real game" is itself an approximation: 79%, not 100%. The live client is 16.x, while the corpus and
  arm are 15.535.
- Fidelity is measured on scripted bot-vs-bot matches.
- All results are exploration tier: one seed bank, 300 cases per opponent.

## What runs next (training at scale)

1. **ExIt (`bot/exit/`, 08 GPU):** on-policy K4S labels on student-visited states, then a student warm-started from
   R3a, iterated. Judged by HEADLINE in RoyaleSim and ours, paired vs R3a.
2. **Search scaling (`bot/search/`, 03):** multiple determinizations, wider candidates, longer horizon; judged the
   same way.
3. **Engine calibration batch 1:** spirit HP data, then the swarm flip and the Goblinstein formation. Gated by the
   fidelity harness.
4. **Rule:** deployed policies always use a calibrated play threshold, calibrated on-policy. A sampled gate costs
   about 24 pp, and an off-policy threshold costs about 45 pp for v1 (STRENGTH.md).
