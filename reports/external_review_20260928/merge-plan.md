# Merge plan: best parts of ClashAI, Hasty-CR and Clasher

Date: 2026-09-28. Sources: [clashai.md](clashai.md), [hasty-cr.md](hasty-cr.md), and the approved council strategy (SHA 2be09f05…). This plan applies implementer-level choices inside the approved strategy. It does not change the strategy's architecture, arms, objective, budgets or admission rules.

## What each project does best

| Project | Strongest part | Weakness |
|---|---|---|
| ClashAI | Fast closed loop against a real engine (~2.5 s per full match, ~26–35 ms per decision); engine-search teacher; half-tile placement lattice evidence; a 230-class screen detector | No license (ideas only); imitation of pro placements is its main metric; no strength evidence against humans |
| Hasty-CR | Pragmatic BC→PPO recipe and training hygiene (critic warm-up, KL guard, collapse alarms, keeping initial policies in the league); engine ~5.4× faster; MIT screen-capture path | Its simulator diverges from native (towers, shields, Log, Tesla, strides); its evaluation grades itself |
| Clasher | Simulator checked against the pinned native reference; strict prospective admission (Tier A/B); public-information actor; varied decks and levels | Slow native measurement path; no trained policy yet; no perception |

Keep Clasher's foundation, meaning the native-checked simulator and the admission gates. Adopt ClashAI's fast native loop and Hasty-CR's training hygiene.

## Before the final runtime freeze (these change the source or instrument Tier A binds)

1. **Native measurement speed, Phase A** (in progress, `m0/native-speed/`):
   - one persistent probe session and fewer redundant reads;
   - `render off` if it does not change gameplay;
   - branching from the already-attested snapshot/restore.
   It is usable only if the equivalence study on development roots shows identical commands, packets and outcomes.
2. **Native speed, Phase B** (after disk recovers): read public levels inside the probe in the atomic observation. Needs an NDK restore, a probe rebuild, a new attestation pin, a dual-read equivalence study and new floors. Levels stay per-frame; nothing is cached.
3. **Native development checks** (opened evidence only; the simulator is repaired only when native disagrees):
   - King wake-up under Zap or freeze (a triage regression candidate);
   - shield absorption on Dark Prince;
   - Hog blocked by three Skeletons;
   - Log pushback on heavy units;
   - lane choice after a Princess Tower falls.
4. **M0 audits, with no fitting:**
   - How often native and human placements land on half-tile lattice edges, especially the 2×2 buildings. This decides whether the strategy's optional sub-tile residual is needed.
   - An off-by-one check in the scripted demonstration adapter: wait rows must not carry the hand from after the play.

## Pilot recipe (before launch; applies to both arms unless noted)

5. **Critic warm-up** after the scripted warm start, with the actor frozen, for a short fixed number of updates. Warm-start arm only; the scratch arm has no actor to protect.
6. **Re-enable the existing target-KL early-stop guard** (currently 0 in `council_pilot.py`), with a fixed, recorded value.
7. **Training alarms, monitoring only:**
   - card-share collapse;
   - plays and waits per match;
   - win rate against the fixed scripts;
   - entropy per factor.
   Rollback stays manual and recorded. Nothing changes hyperparameters automatically.
8. **League:** after 1M decisions, count the initial policies as historical opponents inside the existing 25/50/25 split.

## After Tier A

9. **Harden oracle qualification:**
   - add force-play, random-candidate and wait-only controls to the 64-game screen;
   - add diagnostics for play-rate drift after distillation;
   - use common random futures across candidates.
   ClashAI's hard top-1 distillation copied the teacher's play rate without its judgement.
10. **Tier B targeted probes** from both projects' human-found bugs: lane choice, building pull, body block, charge blocking, Log pushback, shields.

## Later (perception and live play)

11. **Live capture:** Hasty-CR's `screenrecord` + PyAV capture path (MIT) as a starting point for our live adapter's `PublicVisionFrame`.
12. **Detector:** decide separately. Both projects use Ultralytics (AGPL), and the training data licenses are undocumented. Prefer training our own detector on data we can license.

## Explicitly not adopted

- Exact opponent elixir, hand or HP in actor inputs (breaks the public-information actor).
- Live-client memory reading for play.
- Non-reacting recorded opponents as strength evidence.
- Agreement with pros as a teacher gate.
- Hasty-CR's engine semantics, or tuning our simulator toward their numbers.
- Faster-engine rewrites inside the frozen runtime. At most ~12% rollout gain, because the engine is ~14% of rollout time.

## Licensing notes

- ClashAI has no license: ideas only.
- Hasty-CR is MIT: code may be copied with the notice, but none is planned except possibly the capture path.
- The FirstLight probe source in our cache has no license file. Use it locally for research only; do not redistribute a modified probe.
- Our public `clash-simulator` repo's README says MIT but the repo has no LICENSE file.
