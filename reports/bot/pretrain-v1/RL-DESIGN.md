# pretrain-v1 stage 2: outcome RL in our calibrated engine (design only)

Status: **design, not launched.** It launches only after the BC checkpoints pass their offline evaluation:
- G1 imitation/calibration;
- eval hook (a), the policy-only arm on the r2 paired bank;
- eval hook (b), the probe roots;
- coordinator approval of this stage's resource handoff.

It follows `scratch/new-pretrain-20261020/DESIGN.md` ("Outcome RL") and PREREG §5. Choices made here are marked
**[eng]**.

## Environment

- **Engine.** Our calibrated Python engine (engine-cards, origin/main ≥ 1831241d2 + 0dcab45f7). It is assembled as
  the joint runtime root `clasher-rl-runtime-0dcab45f7-joint` (native 358cf506…, gamedata ccd2a5f1…, pin
  `hp1rl-joint-0dcab45f7`) and pinned by hash in every rollout. RoyaleSim and native re-drive remain independent
  evaluation engines and are never part of the training mixture.
- **Real levels.** `bot/players/ours.py:play_match(..., levels=dict(cards={seat: map}, towers={seat: k}),
  planner=...)` through `bot/levels/match.py` (`PlayerState(card_levels, tower_level)`, `install_engine_levels`,
  `tower_curve`).
  - Own levels: Hog 2.6 Zap at account levels (Skeletons 8, Musketeer 7, IceGolem 7, Cannon 9, Fireball 8, Zap 9,
    IceSpirit 8, HogRider 10, King/Princess 9).
  - Opponent levels: sampled from `reports/bot/fullpool/lv2/opp-levels-dist.json` with `bot/levels/profile.py`
    rarity floors.
  - **[eng]** `resolve()` defaults missing levels to 11, so a harness guard rejects incomplete maps.
  - Search opponents plan with `planner='l11'` or the frozen level estimate. They never see true hidden levels.
- **Own deck mix:**
  - 50% exact account Hog 2.6;
  - 30% frequency-weighted meta decks (realistic level profiles: 80% King 8–11, 20% stress);
  - 20% random legal vanilla decks within the qualified card vocabulary.
- **Opponent mix (Hog games):** 70% empirical arena decks with historical levels, 20% adjacent-arena smoothing,
  10% overlevelled 12–16 stress. The table is frozen before launch, and excluded mass is reported.
- **League:**

  | Share | Opponent |
  |---:|---|
  | 30% | Current snapshot (updated at update boundaries only) |
  | 20% | Reservoir of ≤16 milestone snapshots |
  | 15% | Frozen BC anchor |
  | 15% | HP1 v330 |
  | 15% | Frozen live search (true-account environment, public estimates only) |
  | 5% | Simple pressure/defense scripts |

## Producer, one featurizer

**[eng]** `bot/pretrain_v1/sim_ours.py` is the same pattern as `sim_rsim.py`.
- Each poll's engine state becomes the reader PRIVATE frame in the acting seat's own frame (seat 1 rotated), then
  the vendored deployed FrameBuilder with the 5-tick cadence constants, then the record and extras, then
  `policy.Session`.
- Creating card per entity: the `bot/simfid/live_engine.py` root-tracking idea (tag at insertion with the deploying
  card or the spawning parent's root), with ids kept only for FrameBuilder tracking.
- Body names come from the engine's character names, mapped to client names where they differ. The mapping table is
  pinned and audited against the catalog's body vocabulary, and unknown bodies are counted.
- In-flight carriers become `<Card>Spell` rows with their aim.
- Nothing from the opponent's player state is read.
- Admission test before any rollout: features are byte-identical between the producer and an offline replay of its
  logged reader frames (same audit as `audit_parity.py`), plus a hidden-state mutation suite on the engine (opponent
  hand/elixir/queue/RNG).

Channel and cadence are the same as the sim harness:
- polls every 5 ticks from 90;
- `CommandQueue(delay=27, capacity=1)`;
- a rejection is detected and passed to `Session.rejected`;
- the gate, slot and tile are all sampled at T=1, with p_wait^(dt/5) survival scaling.

## Learner

- **Model.** Initialised from the selected **calibrated** BC checkpoint (`best-calibrated.pt`, with its frozen
  `gate_bias`). A second frozen copy is the KL anchor.
- **Objective.** PPO on terminal reward only (+1 / 0 / −1), γ = 1, GAE λ = 0.95, clip 0.2, lr 1e-5, value
  coefficient 0.5, entropy 0.001, gradient clip 1.
- **KL term.** β = 0.05 × KL(π ‖ π_BC) over the same legal action distribution. The joint KL is:

  KL = KL_gate/slot(5-way) + Σ_s π(s) · KL_tile(s)(576-way)

  It is computed analytically from both networks' masked logits on the stored features (legal sets from
  `featurize.legal_tiles`). There is no reward shaping, tower-chip term or play/wait bonus.
- **Busy and forced polls.** These update value and history but get no policy gradient. The stored log-probability
  is the sampled action's actual probability. There is never an argmax with a fictitious log-probability.
- **Batches.** 240–480 completed games per update, 2 epochs, microbatch 512, accepted version lag ≤ 1.
  - Value warm-up: 3 updates with the actor frozen.
  - A snapshot every 10 updates.
  - **Stop rules** (collapse diagnostics, not quotas): nonfinite tensors, a contract violation, 3 consecutive
    updates with joint KL > 0.5 nats/poll, or a play rate outside 15–80 per 300 s.
- **Rollout format [eng].** Exactly the dataset row format (`dataset.Rows` arrays: integer features, `slot_ok`,
  `alive`), plus `action`, `logp`, `p_wait`, `value_pred`, `busy`, `game_id`, `version` and `outcome`. The learner
  reuses `train_bc.Store` and the collate path. Chunks are written atomically with sha256 into a size-capped queue.
- **Seeds and caps.** Seeds 2026102101/02/03, each up to 200k completed games or 96 GPU-hours. One A6000: 08 now,
  or 04 after the coordinator-owned HP1 drain.

## Actors and resource hygiene

- Fresh `spawn` subprocesses with 1 torch/OMP thread each, inference only.
- Each worker is recycled after 20 min or 50 games, with a 2 GiB RSS cap.
- Host guard: MemAvailable ≥ 32 GiB and load ≤ 90. The RL guard on 04/08 preempts at 24 GiB, so our guard (29 GiB
  stop) fires first.
- Caches are bounded by entries and bytes. 0dcab45f7's fc-cut LRU is included.
- At most 3 resident opponent models per worker.
- Search opponents run in their own recycled processes.
- Before scaling: a 6 h soak at 32 actors/host must show post-warm RssAnon slope below 1 MiB/min, no worker above
  2 GiB, no OOM, and exact rollout hashes under recycling.
- Budget [eng]:
  - The policy forward pass is about 4–6 ms per poll. Engine stepping is about 7 s per game; search opponents
    dominate when drawn.
  - Expected cost is about 40–60 CPU-s per game, so 200k games × 3 seeds is about 6.7–10k CPU-h, within the
    14k envelope.
  - Actors need the HP1 cohort's CPU on 04/08. That handoff is the coordinator's decision, so this stage cannot
    start while HP1 holds those cores.

## Evaluation and selection

DEV selection and confirmation follow PREREG §7–8:
- G2a paired against the frozen live search at account levels;
- G2b head-to-head;
- G2c breadth / RoyaleSim / engagement windows.

The r2 RoyaleSim bank harness (`eval_rsim.py`) and the probe roots (`probe_roots.py`) are the first DEV readouts.
Fresh confirmation banks are drawn only by the approved owner, and no final-bank result selects a checkpoint.

## Open prerequisites (blocking launch)

1. BC G1 passes:
   - joint NLL below the frequency baseline on Hog-cycle and broad DEV, with the cluster bootstrap;
   - gate ECE ≤ 0.03;
   - play-rate ratio within [0.85, 1.15];
   - mutation and parity suites clean.
2. `sim_ours.py` producer parity and mutation audits.
3. Engine readiness at account levels (FIDELITY "Readiness"): microcases for all eight own cards and King 9, and
   the mixed-level Python engine admitted. The Rust backend is used only if separately qualified.
4. Coordinator approval of actor CPU (04/08) and the learner GPU.
