# Live loop v4: perception, belief and actuation design

Research design, 2026-10-07. Read-only analysis of the L1, L2, search-noise, search-tuning and srp-public evidence.
Unless a path says otherwise, it is relative to `reports/strategy_council_20260928/`. "Established" means the repo's
measurements or code show it directly. "Hypothesis" means the evidence points that way but nothing has isolated it.
A few numbers come from my own reanalysis of L2 artifacts; they are marked (reanalysis), and Appendix A gives the method.

## 0. Decisions

1. **Why L2 lost:** the serial actor loop starved the event detector, and the player had no model of its own
   in-flight actions. Detector quality is the next limit once starvation is fixed. In L2 the v3 event detector found
   116 of 3,733 opponent plays, a 3.1% recall, compared with 64.3% in standalone L1. The cause is a 300 ms gap reset
   in `l1_events_v3.py`, which fired on 23.8% of inter-frame gaps. Own actions were rejected 77% of the time, mostly
   right after the player's own successful play. The noise study points to a third problem: the search consumes a
   single draw from an overdispersed opponent posterior.
2. **Architecture:** a pipelined, five-process runtime on the Mac. Capture, perception, belief, decision and
   actuation each get their own process, and shared-memory rings connect them. The perception process sees every
   frame, and nothing in it resets on a gap. All inference stays on the Mac: CoreML/ANE first, MPS as a fallback,
   and Rust search on 4 threads. The fleet only trains models, runs simulator experiments and stores data.
3. **Perception:** one shared per-frame backbone for bodies and HUD. Its features are cached and fed to a temporal
   event head that takes irregular time steps and regresses each event's age, so a play seen late still gets the
   correct execution time. The head is trained with frame-drop augmentation from 5 to 30 FPS, with gaps up to 1.2 s.
4. **Belief:** a multiple-hypothesis exact-derivation tracker (ELT) replaces the v3 particle filter. With perfect
   events it reduces to `srp-public/derived_public_state.py`. The search averages over K=4 hypothesis-stratified
   roots instead of one random draw.
5. **Actuation:** a persistent input channel, with no process spawned per tap. Each command follows the same cycle:
   pre-tap slot remap, tap, pixel verification, then at most one retry. Spending is optimistic until the play is
   verified, and only one command may be outstanding.
6. **Data:** a v4 collector on the renderer captures at 20 FPS (render backend pinned) with exact execution ticks
   for every play, and streams each finished match to 127x02. Phase A is 24 emulator-hours, about 21k deployments
   (7x v3). Phase B adds about 40 more emulator-hours if the learning curve is still rising.
7. **Gates:**
   - Opponent events: at least 95% recall and 95% precision at 500 ms, in the loop. This is provisional; experiment
     S1 can lower it, but never below 90/90.
   - Loop: at least 18 FPS processed, and frame-to-tap latency p99 of 400 ms or less.
   - Strength: a new native truth-oracle arm turns the L2 comparison into a controlled test. Pixel v4 must be
     non-inferior to the oracle within −10 pp on 96 paired seeds.
8. **First three tasks:** the v4 collector with fleet streaming (T1), the actuation bench (T2), and the
   noise-robust search study S1 on fleet CPUs (T3). They run in parallel.

## 1. Evidence and root causes

### 1.1 Measured facts

| Quantity | L1 v3 standalone | L2 integrated loop | Source |
|---|---:|---:|---|
| Processed perception rate | 17.7-19.2 FPS (inference only); stream captured at 9.6-9.9 FPS | 4.19 FPS | l1/PROGRESS.md (v3 infer lines); l2/metrics.json `processed_fps` |
| Inter-frame gap p50/p95/p99 | ~100 ms | 188 / 610 / 805 ms | l2/metrics.json `frame_gaps_ms` |
| Temporal-history resets (gap > 300 ms) | n/a | 14,423 of 60,586 gaps (23.8%) | l2/metrics.json `temporal_reset_gaps` |
| Opponent events, correct card within 500 ms | 180/280 = 64.3% recall, 66.7% precision | 116/3,733 = 3.1% recall; 435 predictions, 26.7% precision | l1/RESULTS-v3.md; l2/perception-audit.json |
| Derived opponent elixir MAE, 90% coverage, width | 2.11, 86%, 8.28 | 3.91, 32%, 7.47 | RESULTS-v3.md; metrics.json `opponent_elixir` |
| Own hand-slot accuracy | 99.7% (v1) | 91.5% (7,008/82,075 slots wrong) | l1/PROGRESS.md:283; perception-audit.json |
| Own elixir error | 97.1% integer-correct (v1) | MAE 0.648, p99 3.77 | same |
| Frame production → tap submission p50/p95/p99 | n/a | 409 / 842 / 1,138 ms (deployments: 633 / 992 / 1,305) | metrics.json |
| Search p50/p99, two taps p50/p95 | n/a | 105 / 225 ms; 174 / 449 ms | metrics.json |
| Deployment attempts / confirmed / rejected / unknown | n/a | 9,460 / 1,626 / 5,531 / 2,303 (77.3% of known rejected) | metrics.json `rejection` |
| Rejected with neither wrong card nor unaffordable | n/a | 3,570 of 5,531 (64.5%) | l2/action-audit.json (reanalysis) |
| Native speed | 1x | median 19.82 ticks/s | metrics.json |
| Wins | | pixels 27/48, simulator 48/48; −43.8 pp [−58.3, −29.2] | l2/RESULTS.md |

Simulator noise study (search-noise/RESULTS.md, 128 games per cell, against C56 scripts):

| | Score |
|---|---|
| Clean inputs (A) | 86.7% |
| Full noise (B) | 50.0% |
| B with events repaired (exact derivation) | 66.4%, +16.4 pp [+7.8, +25.0] |
| B with HP, HUD, latency or board repaired | between −0.8 and −4.7 pp; every CI includes 0 |
| B with a broad opponent prior (C) | −7.0 pp [−14.1, 0.0] |
| B with 90/90 events through the same frozen v3 filter (D) | −2.3 pp [−10.9, +5.5] |
| Hog 2.6 | 0% under B, versus 70% clean |

### 1.2 Root causes, ranked

**R1. Event starvation by the serial loop. Established mechanism; it dominates the L2 perception failure.**
- **Code:** in `src/clasher/vision/l1_events_v3.py:142-143` a gap longer than 300 ms clears the three-frame image
  history, the birth list and the spell buffer. Line 171 skips births on a gap frame, but the new tracks still go
  into `known_tracks`, so any unit spawned during a gap is never counted as a birth. Line 184 emits no candidates at
  all on a gap frame. The three-frame stack is then padded with copies of a single frame.
- **Why gaps happened:** in `l2/offline_loop.py` perception, search (105 ms p50) and two `adb shell input tap`
  subprocess spawns (174 ms p50) share one loop. A decision every 500 ms blocks the loop for about 280 ms, so gaps
  above 300 ms were routine (p95 610 ms).
- **Result:** 435 opponent-event predictions over 48 games, about 9 per game against 78 true plays per game. The
  opponent posterior then ran with almost no evidence, and its elixir coverage fell to 32%: miscalibrated, not
  merely wide.
- **Same sensitivity earlier:** v2 scored 85-89% recall on stepped frames but 24% on the continuous native-rate
  stream (l1/RESULTS-v2.md:34). The fusion is fragile to frame continuity by design.
- **Contributing, hypothesis:** the Mac was not quiet. The search-noise study ran three workers on the same host
  during L2 (COORDINATOR.md, 2026-10-05 entries). The L2 renderer used `-gpu swiftshader` on 2 cores
  (l2/emulator/launch.json). v3 collection apparently used host-GPU emulators: PROGRESS.md:515 mentions "host-GPU
  collectors", and there were `stop-emulator-host2` steps. The v3 launch receipts that would confirm this were
  deleted. If so, L2 frames were also outside the training render domain.

**R2. The own-action loop: stale own state, no pending-action model, retry storms. Established symptoms; the
mechanism is a strong hypothesis.**
- **Symptoms:**
  - 5.8 attempts per confirmed play.
  - Wrong card (1,599) and unaffordable (1,627) overlap in 1,159 attempts. Together they explain only 35.5% of
    rejections.
  - 3,570 rejections (64.5%) had the right card and enough elixir in the audited pre-tap observation.
- **What the reanalysis found:**
  - After a confirmed play, the next attempt was confirmed only 6.2% of the time (88/1,427 known). After a rejected
    attempt it was 28.3% (1,237/4,378). The median spacing between attempts is about 0.7 s.
  - Acceptance is flat across tile rows and columns (17-24%), which argues against a coordinate-mapping error.
  - Among attempts flagged neither wrong-card nor unaffordable, acceptance falls with card cost: Skeletons,
    Electro Spirit and Ice Spirit were accepted 37-46% of the time, Fireball, Musketeer and Hog Rider 9-14%.
- **Mechanism (hypothesis):** decisions come from frames about 400 ms old. Those frames don't yet show the
  player's last spend or slot refill. The player keeps no record of its in-flight command, so it re-plans and taps
  again before it can afford the play. The audit's "pre-tap observation" is taken up to 250 ms before the frame is
  received, so it also predates the spend. That would explain why these rejections look affordable.
- **Alternatives not excluded:** a card-select toggle or ordering problem between two separately spawned tap
  processes, or an unvalidated 1080x1920 hook mapping on the 1080x2280 display (SURVEY.md). L3's persistent
  transport does two taps in 44 ms mean (l3/transport-benchmark.json).
- **Strength cost:** unmeasured. The noise study never injected failed actions.

**R3. How the search consumes the belief: one draw from an overdispersed posterior. Established code fact; the
strength effect is a hypothesis.**
- Both `l2/pixel_player.py` and `search-noise/player.py` call the search on `posterior.sample(rng)`. That is a
  single particle from the 1,024-particle v3 filter.
- In the noise study, D (90/90 events) halved elixir MAE relative to B (1.545 → 0.747) and gained nothing
  (−2.3 pp). Its 90% interval was 6.6 elixir wide with 99.3% coverage, so it was overdispersed.
- Exact derivation from v3-quality events (events_clean) gained +16.4 pp.
- **Hypothesis:** what costs strength is the random root from a diffuse posterior, plus the filter's failure to
  concentrate hand and cycle hypotheses (v3: "0 concentrated samples"), not the error in the mean. Experiment S1
  (§4) tests this.

**R4. End-to-end latency. Established magnitude; the cost is a hypothesis.**
- **Measured:** frame production to tap submission was 409 ms p50 and 1,138 ms p99. The noise model assumed 150 ms
  of image lag plus about 100 ms of command delay, and latency repair was not significant there (−2.3 pp
  [−10.2, +5.5]).
- **Unknown:** the cost at the measured L2 latency is untested. It probably matters most for reactive defense, and
  Hog 2.6 fell to 0% even under the modelled latency.
- **Where the time goes:** search p99 is 225 ms. Most of the rest is tap spawning and frame waiting, which
  pipelining removes.

**R5. Detector quality ceiling. Established; it becomes the binding limit after R1 is fixed.**
- **Standalone v3:** 64/67 recall/precision. Recall was zero on Arrows, Goblin Barrel, Knight, Miner, Rocket and
  Royal Delivery, which are mostly flight, underground or no-birth mechanics. Precision was 20% or less on Log
  (22 predictions for 6 true plays), Tornado and Earthquake (l1/RESULTS-v3.md per-card table).
- **Data:** training covered only 3,070 deployments over 112 card-side classes, about 27 each.
- **Timing:** native timing residual p95 was 27 ms, which is small next to the 500 ms gate.

**R6. Execution differences between the renderer and the simulator. Unquantified.**
- The renderer ran at about 19.8 ticks/s, so speed is fine.
- 19 coherent-read timeouts across 5 matches delayed the scripted opponent; the longest gap was 2.83 s.
- The two arms use different RNG and engines.
- The pixel arm used a broader public card-roster prior. In the simulator, a broad prior cost −7 pp.
- None of this can be separated from perception in the L2 design. v4 adds a native truth-oracle arm (§5.3), so it
  is measured rather than argued.

**R7. Board identity and HP. Established error; the cost is untested.**
- 41% of matched bodies disagree with native summon metadata, though spawned and transformed units alias part of
  that. 72% have no HP, and King HP was never read.
- Board and HP repairs cost little in the simulator. However, the noise model kept identities correct
  (search-noise/PREREG.md), so identity noise was never priced. Low priority; it becomes a sensitivity cell in S1.

**Own hand (8.5% of slots wrong) and own elixir (MAE 0.65)** were near perfect standalone. In the loop they are
mostly staleness, which belongs under R2. The state tracking in §2.5 fixes them.

### 1.3 Direct answers to the candidate causes

| Candidate | Verdict |
|---|---|
| Event detection | In L2, starvation, not quality: 3.1% recall in the loop against 64.3% standalone, with a code-level mechanism. Quality (64/67) is the ceiling after the loop is fixed. Both need work. |
| Serial actor loop | Root of R1, R2 and R4. Established. |
| Stale capture vs actions | 409 ms median staleness. The retry-storm pattern (6.2% acceptance right after a confirmed play) points to stale own state as the main source of rejections. Hypothesis, resolved by T2 and T4. |
| Card and elixir misreads | Explain at most 35.5% of rejections, and L1 standalone accuracy of 99.7% suggests that much of this is staleness too. |
| Renderer vs simulator execution | Not quantified. Native speed is fine. Opponent read gaps and RNG differ. Controlled in v4 by the oracle arm. |

## 2. v4 architecture

### 2.1 Process layout (Mac mini, M4 Pro, 12 cores, 24 GB)

```
 emulator (renderer AVD now; official client later)
     │ gRPC screenshot stream, 20-30 FPS, produced_at/received_at stamps
 [P0 capture] ──► shm ring, 64 frames (seq, produced_at, received_at, pixels 540x1140)
     │
 [P1 perception]  every frame, in order; ANE/MPS
     │  backbone → bodies/tracks, HUD, clock; cached features → temporal event head
     ├──► shm: PerceptionFrame per frame
     └──► queue: EventCandidate(card dist, side, tile, exec-time estimate ± σ, existence q)
 [P2 belief]  per frame; CPU, 1 core
     │  ELT opponent hypotheses; own-state tracker (elixir phase lock, exact cycle); pending commands; board tracks
     └──► shm: BeliefSnapshot (versioned; hypotheses + weights; own state incl. pending)
 [P3 decision]  every 10 ticks, and on a trigger (new opponent event q ≥ 0.5, elixir crossing a threshold, verification result)
     │  srp-pub-mix in Rust, K=4 roots on 4 threads, 200 ms deadline; optional policy top-8 proposals
     └──► command queue (at most 1 outstanding)
 [P4 actuation]  persistent input channel
        pre-tap check on the latest frame → tap card → tap tile → verify within 600 ms → ≤1 retry → result to P2/P3
```

The processes are separate, which avoids GIL contention between Torch, the search driver and I/O. Each one
timestamps its outputs with the host monotonic clock. All of them log to compressed JSONL so a run can be replayed
offline. The same binary runs in a replay harness, where P0 reads a recorded H.264 stream at its true timestamps and
P4 is a recorder. That harness benchmarks throughput without an emulator.

### 2.2 Capture (P0)

- Use the emulator gRPC screenshot stream, already in `src/clasher/vision/l1_stream.py` and `l3/official_loop.py`.
  L3 measured 49.6 FPS, with 1.7 ms mean from screenshot production to receipt, on a host-GPU AVD
  (l3/transport-benchmark.json).
- Target 20 FPS or more, which is about one frame per native tick. P0 never blocks on consumers. If P1 falls behind
  by 150 ms or more, P0 marks frames as droppable, and P1 skips every other frame while keeping timestamps. The
  event head is trained for irregular steps (§2.4), so a skip costs resolution, not state.
- **Render backend:** pinned and identical across collection, evaluation and L2-v4, and recorded in every receipt.
  Default to `-gpu host` if T2 shows at least 20 FPS capture and stable native ticks. Otherwise use swiftshader with
  3 cores. Train on both if both appear in data.

### 2.3 Perception model (P1)

- **Shared backbone:** a YOLOv8s-class CNN, at most 12M parameters, on a 448x832 arena crop of the sanitized
  540x1140 frame. It has detection heads for bodies (identity, owner), HP-bar regression attached to each detection,
  and a small HUD branch for own hand, next card, elixir digits and bar fraction, clock and phase colour. Stride-16
  feature maps (about 28x52x64, fp16, about 186 KB) are cached per frame in a 32-frame ring.
- **Temporal event head** (§2.4): at most 4M parameters, run on the cached features every frame.
- **Tracker:** a ByteTrack-style association on detections. It feeds the board and the spawner-suppression logic
  kept from v3 (`SPAWN_SOURCES`, `GROUP_COUNTS`).
- **Runtime:**
  - CoreML (`mlprogram`, fp16) on the ANE, which leaves the GPU to the emulator. MPS is the fallback.
  - Budget per frame with the emulator running: p50 25 ms and p95 40 ms or less.
  - v3's frozen stack already did 17.7-19.2 FPS standalone on MPS (l1/PROGRESS.md v3 infer lines), and YOLOv8n
    alone ran at 39.9 FPS with the emulator off (l1/PROGRESS.md:87). The budget leaves room for the larger
    backbone.

### 2.4 Event detection (opponent and own)

The v3 failure modes were reset fragility, missing spell, flight and underground cues, and false positives on
Log, Tornado and Earthquake. These choices address them:

1. **Inputs:** cached features from the last T=16 frames, which is 0.8 s at 20 FPS and longer at lower rates.
   Each frame carries a learned embedding of its Δt to now. There is no reset path: missing frames are just absent
   tokens.
2. **Architecture:** factorized space-time. A 3x3 spatial conv mixes each frame, temporal self-attention runs per
   spatial cell over T, and two dilated global-context layers give an arena-wide receptive field so a projectile
   can be tied to its target, as in v3's context branch.
3. **Outputs:** produced on a half-tile grid (36x64):
   - an event heatmap per (card, side);
   - an age regression for the time since execution, in ms, with a predicted σ;
   - a top-3 card distribution at each peak.
   - Spells are additionally scored for cast origin: Rocket, Fireball, Arrows, Log and Goblin Barrel fly from the
     opponent's King-tower side.
4. **Training targets** come from exact execution ticks (§3.1). For each frame time t and each event executed at
   t_e with t − 1.5 s ≤ t_e ≤ t, the target is a Gaussian peak at the deploy tile, with age t − t_e. Negative
   windows are explicit. Underground and flight cards (Miner, Goblin Barrel, Royal Delivery) get their targets at
   the deploy tile, even before the visual arrives, so the head learns the tunnel or flight cue.
5. **Fusion:**
   - Peaks above a per-card threshold become candidates with an execution-time estimate of t − age and an
     existence probability q, calibrated by isotonic regression on validation.
   - Temporal NMS merges candidates with the same card and side, within 1.5 tiles, whose execution estimates are
     within 300 ms of each other.
   - v3's own-HUD corroboration rule is kept for own spells.
   - Births still feed the board but no longer decide events alone. They become a feature (count of new same-side
     tracks near the peak), concatenated before the final classifier.
6. **Frame-drop augmentation:** training draws irregular frame subsets at 5-30 FPS, with random gaps up to 1.2 s,
   so the same weights serve 20 FPS, 10 FPS and gappy streams. The gate in §5.1 tests the L2 gap distribution
   explicitly.
7. **Not available:** the 1v1 HUD has no opponent elixir bar or hand, and the sanitized frames contain only the
   arena, clock and own HUD (l1/README.md). v4 assumes no such cue. If official footage shows a transient deploy
   marker, add it as a feature later. Opponent elixir and cycle come from the fair exact derivation (§2.5).

### 2.5 Belief and state (P2)

**ELT (event-likelihood tracker)** for the opponent:
- **Per hypothesis:** an exact `DerivedPublicState` (8! deck orders × prior decks, integer-frame elixir, from
  srp-public), plus the accepted event list.
- **Branching:** each new candidate branches into three: accept as top card, accept as second card if
  p₂ ≥ 0.15, or reject as a false positive. If a hypothesis becomes impossible (a card not playable under the
  cycle, or elixir below cost at t_e within σ), it can insert one latent missed play, with its card drawn from the
  cycle-consistent set.
- **Log weight:**
  Σ log q (accepted) + Σ log(1−q) (rejected) + log P(card | dist) + n_missed·log λ_miss + timing log-likelihood.
  λ_miss and the q calibration are fitted on validation only.
- **Beam:** M=128 hypotheses, merging hypotheses with identical derived state.
- **Outputs:**
  - hypothesis weights and a concentration flag (top-mass ≥ 0.9);
  - elixir quantiles and hand/cycle marginals;
  - a stratified sampler for search roots.
- **Exactness:** with q=1 and no misses, ELT must equal srp-public exactly. The regression test reuses srp-public's
  24 full-game replays (0/23,058 elixir errors).

**Own state:**
- **Exact cycle:** the own deck is known before the match, and the cycle advances exactly from own confirmed plays.
  This replaces `own_model`'s random shuffle of unseen cards in `pixel_player.py`.
- **Phase-locked elixir:** each observed integer increment of the HUD digit anchors the fraction at that frame.
  Between anchors, elixir extrapolates by the phase regen rate, taken from gamedata. Spends apply at verified play
  times. Expected error is about the frame-time uncertainty: ±50 ms is ±0.02 elixir at 1x.
- **Pending commands:** a submitted command spends its cost and cycles its slot at once in the belief. It is
  reconciled on verification, or rolled back after 800 ms without one. This removes the R2 double spend.

**Board:** P1 tracks with HP. Missing HP falls back to the last seen value, and full HP only on a fresh birth.

### 2.6 Decision (P3)

- **Engine:** srp-pub-mix (search-tuning/RESULTS.md) in Rust: horizon 160, interval 10, balanced/pressure/defense
  mixture.
- **Roots:** K=4, drawn by stratified sampling from ELT hypotheses. If the belief is concentrated, all four roots
  share the MAP hypothesis and differ only in unrevealed cards and RNG. Score is the mean over roots. The robust
  variant (S1 arm E4R) adds a fifth root at opponent elixir q90.
- **Parallelism:** 4 threads, one root each, so wall time stays near today's K=1 (srp-public measured K=4 at
  0.271 s single-threaded, which is why it parallelizes).
- **Deadline:** 200 ms. Overruns fall back to the best completed candidate, as now.
- **Triggers:** besides the 10-tick cadence, a search starts immediately when a new opponent event arrives with
  q ≥ 0.5, rate-limited to one per 200 ms. Defense reacts to the event, not to the next cadence slot.
- **Proposals:** the human-prior proposal network (amendment 2026-10-01) plugs in through srp-pub-pol's top-8
  candidates. P2 also exports the public observation tensor for it.

### 2.7 Actuation with verification (P4)

1. **Channel:** persistent, either emulator gRPC touch injection or a long-lived `adb shell` session. T2 picks the
   one with at least 98% acceptance and two-tap p95 of 80 ms or less.
2. **Pre-tap check:** on the latest frame, at most 60 ms old, find the slot that currently shows the chosen card.
   Slots keep their card until it is played, so this remaps by identity and aborts if the card is gone. Abort if
   own elixir with pending spends is below cost.
3. **Tap:** card, then tile, with the inter-tap delay T2 selects. One outstanding command at a time.
4. **Verify:** within 600 ms (T2 sets the exact window), the slot card must change and the elixir digit must drop
   by cost ±1. A deploy marker or new same-side tracks near the tile corroborate.
5. **On failure:** classify it as no selection, insufficient elixir, illegal tile or unknown. Retry once after
   150 ms if the card is still present and affordable. Otherwise report back to P2/P3 and hold that card for 1 s.
6. **Never:** no randomized or "humanized" timing, and no detection-evasion feature
   (live-play-authorization rule). Inputs are plain taps.

### 2.8 Placement and budgets

| Stage | Runs on | Budget p50 / p95 |
|---|---|---|
| Capture (production → receipt) | Mac, emulator gRPC | 3 / 10 ms, at 20 FPS or more |
| Decode + sanitize + resize | Mac CPU, 1 core | 4 / 8 ms |
| Backbone + body/HUD heads | ANE (MPS fallback) | 15 / 25 ms |
| Temporal event head + fusion | ANE/MPS + CPU | 5 / 10 ms |
| Belief update (ELT M=128, own state) | Mac CPU, 1 core | 3 / 10 ms |
| Search (K=4, 4 threads) | Mac CPU, 4 cores | 110 / 200 ms (deadline) |
| Two taps | persistent channel | 45 / 80 ms |
| **Frame production → tap submission** | end to end | **≤200 / p99 ≤400 ms** (SURVEY.md target) |
| Verification | following frames | ≤400 / 600 ms |

- **Cores:** emulator 2-3, capture/decode 1, perception driver 1, belief 1, search 4, actuation and OS 2.
- **RAM:** emulator 3 GB, models under 0.5 GB, search under 2 GB.
- **Quiet host:** no other heavy job may run on the Mac during L2-v4. The preflight checks load average, and fleet
  migration makes this practical.

**Training on the fleet:**
- **GPUs:** five A6000s on 127x01, 02, 04, 07 and 08 (127x03 and 127x05 have no GPU, and 127x06 is down). The
  driver is 470 with CUDA 11.4, so use PyTorch cu118 wheels, which run on driver 470 or newer under CUDA 11 minor
  version compatibility. T0 verifies this.
- **Model:** backbone ≤12M parameters, event head ≤4M, HUD ≤0.5M, at about 10 GFLOPs per frame.
- **Training time:** a full train is roughly 6-10 A6000-hours for the backbone and 4-8 for the event head. Run
  sweeps across 4 GPUs in parallel. Export CoreML on the Mac.
- **Inference:** none on the fleet during play.

### 2.9 Interfaces

- **PublicVisionFrame:** extend `clasher.rl.live_inference_contract` additively. Add event candidates that carry a
  card distribution, existence q and execution-time interval. The privileged-key rejection stays.
- **BeliefSnapshot:** a new contract that P3 and the policy consume.
- **Fair-information boundary:** unchanged. Only pixels and the player's own deck and commands enter P1-P4.

## 3. Data plan

### 3.1 Label schema (per match, written by the v4 collector)

- **`frames.jsonl`:** one row per captured frame.
  - `seq`, `produced_at`, `received_at`, `media_pts`;
  - native tick bracket `[tick_lo, tick_hi]`, from started/completed step counters as in v3;
  - `render_backend`, `capture_fps_nominal`.
- **`objects.jsonl.gz`:** native `observe` at every tick bracket, kept for evaluation and training labels only.
  - `native_id`, `card_id`, `body_name`, `owner`, `x`, `y` (milli-tiles), `hp`, `max_hp`, `deploying`,
    `visible_hint`;
  - towers and King HP.
- **`hud.jsonl`:** per frame.
  - Own hand by slot, next card, exact fractional elixir, displayed integer elixir, clock and phase.
  - Both players' hands and elixir go to an evaluation-only file.
- **`events.jsonl`:** one row per play by either side.
  - `event_id`, `side`, `card`, `tile` (x, y), `command_tick`, `exec_tick` (exact, from the `replay-schedule-status`
    receipt), `cost`, `spawned_native_ids`;
  - `kind`: troop, building, spell, flight, underground, champion ability.
  - Rejected commands are recorded as negatives (`accepted=false`).
- **`video.mp4`:** sanitized 540x1140 H.264 (CRF 23) with PTS from production time. Sidecar hashes.
- **`receipt.json`:**
  - seeds, decks, styles, render backend, emulator ownership and attestation, IPv4/IPv6 UID egress rejection;
  - frame/tick audit and file hashes.
  - Written atomically last. A match without a receipt is incomplete and never trained on.

A converter emits the v3 dataset layout from these files, for the v3 control in §3.6.

### 3.2 Volume and throughput

- **v3 reference:** 88 matches, 3,070 deployments and 72k frames from two emulators in about 1.7 hours of
  collection, about 900 deployments per emulator-hour at 1x (l1/PROGRESS.md 17:48-19:30 stream lines). Real-time
  rendering is the bound. Raising the frame rate adds frames, not events.
- **Phase A:** 24 emulator-hours, 12 h wall on two emulators.
  - About 21k deployments, roughly 190 per card-side, 7x v3. About 1.7M frames at 20 FPS. About 8-10 GB of H.264 at
    about 5 KB per frame; v3 was 5.7 KB at 10 FPS.
  - Split by seed and deck multiset, before collection: 80% train, 10% validation, 10% heldout. Heldout must have
    at least 20 matches and at least 1,500 opponent events.
- **Phase B:** 40 more emulator-hours, run only if Phase A's learning curve (train on 25/50/100% of Phase A) still
  improves heldout event F1 by at least 2 pp per doubling. It targets at least 500 events per card-side, about 57k
  in total.
- **Scripted play mix:**
  - C56 scripts for both seats, with 30% random legal placements.
  - Forced near-simultaneous double plays (within 0.5 s) in 10% of turns.
  - Plays next to spawners, spells into crowds, champion abilities.
  - Phase starts spread across 1x, 2x and 3x (as in v3's 340-5200 tick starts).
  - Rare-card upweighting so that every card-side reaches the minimum.
- **Emulators:** at most two at once on the Mac (the L1 boundary), each 3 GB RAM. Collection pauses while T2 or the
  L2 runs need an emulator.

### 3.3 Storage and streaming (Mac disk: 27 GiB free)

- **Rolling buffer:** at most 6 GB on the Mac. The collector writes per-match folders, and the receipt finalizes
  each one.
- **Transfer:** a shipper rsyncs completed matches to `127x02:/mpac/sdicks02/repos/clasher/data/live-v4/` every
  5 minutes, through `pilot/transfer_to_fleet.sh` or the same rsync flags. The hub recomputes sha256 and writes a
  verification receipt. Only then does the Mac delete the media, keeping labels and receipts, about 2% of the size.
- **Bandwidth:** two emulators need about 0.2-0.4 MB/s against the 10-30 MB/s Tailscale link.
- **Fan-out:** the hub copies to GPU nodes over the LAN.
- **Guards:** collection stops when Mac free space drops below 15 GiB, or when the shipper backlog passes 6 GB.
- **Restart safety:** every job runs through `pilot/detach.sh` and resumes per match (session-restart memory).
- **Fleet footprint:** at most 40 GB in /mpac.

### 3.4 Synthetic rendering and official footage

- **No simulator-side synthetic rendering for v4.** The simulator has no sprite renderer. Building one, then
  closing its domain gap, costs more than renderer time, and the renderer produces real sprites with exact labels at
  about 900 events per emulator-hour.
- **Optional cheap augmentation (T7):** copy-paste of rendered sprite crops, cut with the native boxes, onto real
  rendered backgrounds. Use it only if any card-side stays below 80% recall after Phase A.
- **Official-client footage is not available from our own emulator now.**
  - Version 160402017 crashes at native-library load (`frrh.aC: 02`) on both Google APIs and Google Play API 35
    images, and BlueStacks Air failed first boot (l3/README.md).
  - Use recorded official footage (spectator or TV Royale video, via `perspective_sanitizer.py`) only as a
    *transfer canary*: 20 matches hand-labelled for events only (card, side, time ±0.5 s), about 15 minutes per
    match. Not for training in v4.0.
  - A canary recall gap above 15 pp relative to the renderer heldout triggers a domain-adaptation task, with
    pseudo-labels from ELT-consistent detections, before L3.

### 3.5 Augmentation (training)

- Frame drop and Δt jitter (§2.4).
- Render-backend mix, if both backends exist.
- Colour, gamma and JPEG/H.264 re-encode at CRF 18-35.
- ±2% scale and ±4 px translation, to absorb a different display size in official clients.
- Horizontal flips of the arena crop only, with labels mirrored (x → 18 − x). Never flip the HUD crop.

### 3.6 Regenerating the v3 baseline as a control

The v1 body detector and HUD that v3 depended on still exist locally (`live-loop/l1/v1/detector`, `hud.npz`). The v3
code and scripts are intact (`scripts/train_l1_stream_v3.py`, `infer_l1_stream_v3.py`, `evaluate_l1_stream_v3.py`).

- **Procedure:**
  1. Convert Phase A to the v3 layout at about 10 FPS by subsampling the 20 FPS streams on their timestamps.
  2. Train v3 unchanged on the v4 train split. That took 11 minutes on MPS for v3, or about 1 A6000-hour.
  3. Score it on the v4 heldout with the unchanged v3 evaluator.
- **Comparability check:** the result should land within the bootstrap CI of the published 180/280 recall and
  90 false positives. If not, record the collection shift, and v3-on-v4-data remains the control.
- **Extra cell, gap fragility:** score the same model under the L2 gap distribution. This demonstrates R1
  offline, and v4 must not show it.
- No extra emulator time is needed.

## 4. Noise-robust search (decision side, simulator only, fleet CPU)

### 4.1 Changes under test

1. **ELT belief** (§2.5) instead of the frozen v3 `OpponentPosterior`.
2. **K-root search:** K=4 stratified hypothesis roots, mean score. The robust variant adds a q90-elixir root.
3. **Event-triggered search** and **pending-action state:** in the simulator, the controller re-plans on event
   arrival, and its own command is applied to its belief at submission.
4. **Action failure model:** command rejection with probability p and a retry delay, to price R2 in the simulator.
5. **Extended noise model:** search-noise `noise-model.json`, plus a body-identity confusion sensitivity cell (10%
   within type) and latency distributions: 150 ms (old), the v4 target (p50 200, p99 400), and the L2-measured
   empirical distribution from `l2/native/*/decisions.jsonl`.

### 4.2 S1 preregistration draft (`search-noise-v2/`, frozen before any confirmation game)

- **Question:** do ELT and K-root search recover strength under the measured event noise, and which event quality
  keeps strength within 5 pp of clean?
- **Controller:** Stage 5b-compatible srp-pub-mix from search-noise. Native Rust backend on Linux, and only after
  the fleet Linux parity gate passes.
- **Fixed per-decision rollout budget:** fleet wall-clock deadlines don't transfer to the Mac. The budget equals
  the median candidates × styles completed in 200 ms on the M4 Pro (measured once, frozen). Latency is simulated
  explicitly.
- **Arms:** B (frozen v3 posterior, 1 draw; replicates search-noise B), E1 (ELT, 1 draw), E4 (ELT, K=4), E4R
  (E4 + q90 root), A (clean).
- **Primary matrix:** {B, E1, E4, E4R} × event noise {N64: 64.3/66.7, i.e. v3 standalone; N90: 90/90; N97: 97/97},
  with every other channel at v3-measured noise and the v4-target latency. 256 games per cell against C56 scripts
  (128 matchups × 2 seats; seven families as in search-noise), plus A at 256.
- **Secondary cells:**
  - E4 at N90 under each latency level (3 × 256);
  - E4 at N90 with first-attempt failure p ∈ {0.10, 0.60} (2 × 256);
  - E4 at N90 with identity noise (256);
  - head-to-head against A for B, E4 and E4R at N64 (3 × 128).
- **Primary endpoints:**
  1. E4 − B at N64 (paired matchup bootstrap). Success: the 95% lower bound is above 0.
  2. The lowest noise level L in {N90, N97} where E4's script score lower bound of E4 − A is above −0.10, with the
     point estimate within 5 pp. That L sets the v4 event gate (§5.1). If neither passes, the gate stays at 95/95
     and decision-side work continues before L2-v4.
- **Analysis:** 10,000 paired-matchup bootstrap resamples, both seats kept together (as search-noise). Families,
  and especially Hog 2.6, are descriptive.
- **Size:** about 5,100 games in total. At roughly 4 core-minutes per game, that is about 700 core-hours, about
  2 hours of wall time on four CPU nodes at 96 nice-10 threads.
- **Rules:**
  - Seeds disjoint from all search-noise seeds, with an audit.
  - No retuning after the first confirmation game.
  - Every receipt is retained.

## 5. Gates

### 5.1 L1-v4 offline gates (heldout matches, replayed through the pipelined runtime at true timestamps with the emulator idle-running)

| Gate | Target |
|---|---|
| Opponent events: correct card and side, one-to-one, available within 500 ms of `exec_tick` | recall ≥95% and precision ≥95%, each with a bootstrap lower bound of 92% or more. The level is provisional; S1 may lower it to 90/90, never below. |
| Same events under the L2 gap distribution (gap p95 610 ms) | recall of 90% or more (no reset failure) |
| Per card-side with ≥10 heldout events | recall ≥80%, precision ≥70% |
| Backdated execution-time error | p95 ≤150 ms |
| Placement within 1 tile (troops, buildings), within 1.5 tiles (spells) | ≥90% / ≥85% |
| Own hand slot accuracy; own elixir MAE (tracker) | ≥99.5%; ≤0.15 |
| Derived opponent elixir: MAE; 90% coverage; mean width | ≤0.5; 85-95%; ≤2.0 |
| Opponent hand when concentrated; share of query times concentrated after 60 s | ≥95%; ≥60% |
| Perception per frame on the Mac (emulator running) | p95 ≤40 ms |

The frame-tick certification gate from v3 is dropped as a blocker. What matters to the player is when an event
becomes available relative to the native execution tick, and that is measured directly. The empirical frame
residual (p95 27 ms) is far below the 500 ms tolerance.

### 5.2 L2-v4 loop gates (integrated loop on the renderer; all matches of §5.3)

| Gate | Target |
|---|---|
| Capture rate; share of captured frames processed | ≥18 FPS; ≥95% |
| Frame gap p99 | ≤150 ms |
| Frame production → tap submission | p50 ≤200 ms, p99 ≤400 ms |
| Search deadline overruns | ≤1% |
| First-attempt acceptance; attempts per confirmed play; unknown windows | ≥90%; ≤1.15; ≤5% |
| In-loop opponent events at 500 ms | within 2 pp of the offline L1-v4 result, and at or above the event gate |
| Pixel lifecycle: end detected; result read correctly | 100%; ≥98% (needs a result-screen reader) |

### 5.3 L2-v4 strength gate (controlled)

- **Arms**, on the same 96 seed pairs (32 per family × Hog 2.6, Royal Hogs spawners and X-Bow cycle, styles
  rotated, decks and openings paired as in L2):
  - **O (native truth oracle):** the player gets a PublicVisionFrame projected from native `observe`, the same
    projection the L2 opponent already uses, plus opponent events from native public play records. It acts through
    the same P4 verified actuation. This is an evaluation control, not a player.
  - **P (native pixels v4):** the full v4 pipeline.
  - **S (simulator, clean):** as in L2.
- **Primary:** P − O paired score, family-stratified paired bootstrap. Pass if the 95% lower bound is above −0.10.
  With 96 pairs and about 30% discordance the standard error is about 0.056, so a true difference of 0 passes with
  high probability. 48 pairs would not.
- **Secondary, descriptive:** O − S (engine plus actuation gap) and P compared with L2's 27/48.
- **Optional arm O-probe:** O submitting through probe commands instead of taps. Run it only if O − S is below
  −10 pp, to separate actuation from engine differences.
- **Cost:** 2 native arms × 96 games × about 5 minutes is about 16 emulator-hours, 8 h wall on two emulators.
  Arm S runs on the fleet in minutes.
- L3 readiness requires all of §5.1, §5.2 and §5.3, plus an official-footage canary event recall within 15 pp of
  the renderer heldout.

## 6. Preregistration skeleton (copy per experiment: L1-v4, S1, L2-v4)

```
# <experiment> preregistration
Frozen: <UTC time>; content manifest sha256 <...> (code, configs, model weights, thresholds, noise model)
Git HEAD (informational): <sha>; uncommitted content manifest is the identity.
Question and hypotheses: <H1..Hn, directional>
Population: decks/families/styles; seeds (list + audit receipt, disjoint from <prior experiments>)
Arms: <exact definitions; what differs; what is held fixed>
Primary endpoint(s): <metric>, <estimator>, <CI method, resamples, RNG seed>, <decision rule incl. margin>
Secondary/descriptive: <list; cannot change the verdict>
Sample size and justification: <n, expected SE>
Exclusions and technical reruns: <only infrastructure failures before outcome; same seed; logged in INCIDENT-*.md>
Stopping: no outcome-based early stopping; no retuning after first confirmation game
Timing/compute: hosts, nice level, max workers, render backend, Mac quiet-host check
Boundaries: fair-information checks (denied reads, invariance), emulator ownership + UID egress rejection, storage caps
Outputs: receipts layout, RESULTS.md template (all gates, pass/fail), metrics.json schema
Amendments: dated, before first confirmation game only; later amendments are reported as deviations
```

## 7. Work plan

Each task is sized for one implementation agent. Agents run at high effort, using `delegate_task` per the global
routing, and every long job runs through `pilot/detach.sh` and resumes from disk.

The lanes, which run in parallel:
- **Mac emulator:** T2, then T1 Phase A, then T9, then T10.
- **Mac CPU:** T4 and T5, alongside the emulator lane.
- **Fleet CPU:** T0, then T3 and T8-sim.
- **Fleet GPU:** T6, then T7, starting when 50% of Phase A has landed.

| # | Task | Where | Depends | Inputs | Outputs | Compute | Acceptance |
|---|---|---|---|---|---|---|---|
| T0 | Fleet GPU and training env check | 127x02 (+01/04/07/08) | in-flight fleet parity gate | `fleet/` env | `fleet/GPU-CHECK.md`: torch cu118 on driver 470, CoreML export path on the Mac | 1 h | A6000 trains a YOLOv8s epoch on dummy data; NCCL across 2 nodes not required |
| **T1** | v4 collector + streaming | Mac (2 emulators) → 127x02 | — (start right after T2's emulator slot) | v3 collector (`scripts/collect_l1_stream_v3.py`, `l1_native_capture_v3.py`), schema §3.1 | `scripts/collect_l1_stream_v4.py`, shipper, `live-loop/v4/data/` receipts; data on the hub | 1 agent-day + 12 h wall for Phase A | 20 FPS (or the documented backend maximum) on ≥95% of matches; every event has `exec_tick` from receipts; hub sha256 verification for 100% of matches; Mac buffer never above 6 GB; split frozen before training; v3-layout converter round-trips a sample |
| **T2** | Actuation bench and verified actuator | Mac, 1 emulator | — | `l2/offline_loop.py` tap path, `l3/official_loop.py` persistent input | `live-loop/v4/actuation/RESULTS.md`, `actuator.py` | 2-3 emulator-hours | Factorial over tap method × inter-tap delay × time since own last play × elixir margin, ≥40 trials per cell, truth-legal and affordable. The chosen method reaches ≥98% acceptance with two-tap p95 ≤80 ms. Pixel verification detects acceptance within 600 ms at ≥99% sensitivity and specificity. The bench reproduces the L2 failure mode (stale re-tap) and shows the pending-action fix removes it. Render backend and capture FPS measured. |
| **T3** | S1 noise-robust search | fleet CPU (127x01-08) | T0 parity | search-noise code and noise model, srp-public derived state, L2 latency logs | `search-noise-v2/` with PREREG, ELT module (`elt.py` + tests), RESULTS | 2 agent-days + ~2 h wall (700 core-h) | ELT equals srp-public exactly on 24 replays at q=1; prereg frozen before confirmation; all cells complete; verdict per §4.2 |
| T4 | L2 forensics | Mac CPU | — | `l2/native/*`, action-audit, perception-audit | `live-loop/v4/forensics/REPORT.md` | 4 CPU-h | Every rejection classified (stale own state, slot refill, unaffordable at tap time using the next native observation, wrong card, unexplained); unexplained ≤25%; event miss classes (gap-reset, never-seen, late) per opponent play |
| T5 | Pipelined runtime | Mac CPU | T2 (actuator API) | `l1_stream.py`, `pixel_player.py`, v1 detector as placeholder | `src/clasher/live/` (P0-P4, shm rings, replay harness) + tests | 3 agent-days | Replay harness at 20 FPS with emulator idle and search active: ≥95% of frames processed, 0 resets, production→submission p99 ≤400 ms with placeholder perception; fair-information denied-read tests pass |
| T6 | v3 control on v4 data | fleet GPU (1×A6000) or MPS | T1 (Phase A ≥50%) | converter, v3 scripts, v1 detector | `live-loop/v4/v3-control/RESULTS.md` | 1-2 GPU-h | Numbers reported at 10 FPS and under the L2 gap distribution; comparability to the published v3 recorded |
| T7 | v4 perception model | fleet GPU (4×A6000) + Mac export | T1, T6 | Phase A (B if triggered), §2.3-2.4 | weights, CoreML packages, `live-loop/v4/l1/RESULTS.md` | ~4 GPU × 24 h sweep; 1 h Mac benchmark | §5.1 gates on heldout (selection on validation only) |
| T8 | Belief and own-state integration | Mac CPU | T3 (ELT), T7 | ELT, own tracker spec §2.5 | P2 process, calibration on validation | 1 agent-day | §5.1 derived-state and own-state rows |
| T9 | Integration smoke | Mac, 1 emulator | T5, T7, T8 | all | `live-loop/v4/l2-smoke/` | 6-10 matches, ~1 h | §5.2 loop gates on smoke matches (not scored for strength) |
| T10 | L2-v4 paired evaluation | Mac (2 emulators) + fleet (arm S) | T9, S1 verdict | prereg §5.3 | `live-loop/v4/l2/` RESULTS + metrics | ~8 h wall | §5.2 + §5.3 verdict |
| T11 | Official-footage transfer canary | Mac CPU (+ human or agent labels) | T7 | recorded official footage | `live-loop/v4/canary/` | ~5 h labelling + 1 h inference | event recall gap vs renderer heldout reported; >15 pp triggers a domain-adaptation task |

**Parallel start:**
- Today, T2 and T3 can start; T4 can start at any time.
- Once T2 frees the emulator, T1 begins Phase A, while T5 builds on T2's actuator API.
- T6 and T7 start on the fleet GPUs at 50% of Phase A.
- Expected critical path: T1 (Phase A), then T7, then T9 and T10, about 7-9 days.

## 8. Risks

1. **Renderer-to-official domain gap.** Null's Royale 15.535 content and art against official 160402017. The L3
   client cannot run yet: it crashes at native load on both AVD images, and BlueStacks failed first boot. The v4
   gates are renderer gates only. Mitigations: the canary (T11), augmentation, and a planned adaptation step before
   L3.
2. **An event ceiling for intrinsically ambiguous plays.** Miner, Goblin Barrel, overlapping simultaneous plays,
   and spawner-adjacent plays. ELT's missed-play hypotheses and K-root search are the fallback; S1 prices the
   residual.
3. **Ceiling effects in the strength gates.** The simulator arm won 48/48. The P − O comparison is what avoids
   penalizing perception for engine differences.
4. **Fleet stack.** Driver 470 limits CUDA to 11.x wheels. The C56 Rust planner had an open Fisherman parity
   defect (COORDINATOR.md), and S1 needs native parity on Linux. The fallback is the Python engine on 128 threads
   with smaller cells.
5. **Mac contention and disk.** 24 GB RAM, 27 GiB free, and L2-v4 needs a quiet host. Collection, the L2 runs and
   T2 compete for the two emulator slots.
6. **Session restarts kill detached jobs** (memory note). Every task must resume per match or per game from disk.
7. **Timing without a compositor fence** remains empirical. v4 measures event availability end to end instead of
   certifying frames.
8. **ToS and IP.** The native renderer is a modified private-server client, used offline (SURVEY.md flags this,
   and the owner kept it). v4 adds no new use of it beyond offline collection and evaluation.

## 9. Sources

- `live-loop/SURVEY.md`; `live-loop/l1/RESULTS-v3.md`, `RESULTS-v2.md`, `README.md`, `PROGRESS.md` (lines 87, 283,
  515, the v3 stream, train and infer lines); `live-loop/l1/v3/DESIGN.md`.
- `live-loop/l2/RESULTS.md`, `metrics.json`, `perception-audit.json`, `action-audit.json`, `failure-examples.json`,
  `offline_loop.py`, `pixel_player.py`, `emulator/launch.json`, `native/pair-*/decisions.jsonl`.
- `live-loop/l3/README.md`, `PROGRESS.md`, `transport-benchmark.json`.
- `search-noise/RESULTS.md`, `PREREG.md`, `result.json`, `noise-model.json`, `player.py`.
- `search-tuning/RESULTS.md`; `srp-public/DESIGN.md`, `REPORT.txt`, `derived_public_state.py`.
- `amendments/2026-10-01-search-and-human-prior.md`; `COORDINATOR.md` (2026-10-05 to 10-07 entries).
- `src/clasher/vision/l1_events_v3.py` (gap reset, lines 142-184), `l1_stream.py` (latest-frame buffer).

## Appendix A. Reanalysis method (L2 action audit)

The input joins `l2/action-audit.json` (9,460 rows, keyed by pair and frame) with `l2/native/pair-*/decisions.jsonl`
(slot, tile, `tap_ms`, `action_submit_mono`), in submission order per game. For each deployment attempt it
conditions on the previous attempt's audited result and on whether the slot was the same.

| Previous attempt | Next confirmed / rejected (known windows only) | Acceptance |
|---|---|---:|
| confirmed | 88 / 1,339 | 6.2% |
| rejected | 1,237 / 3,141 | 28.3% |
| unknown | 301 / 1,047 | 22.3% |

- **Acceptance by tile row band of 4 tiles:** 17-24%. **By column band of 3 tiles:** 21-23%.
- **By tap duration bucket:** 21-28%.
- **By card, among attempts flagged neither wrong-card nor unaffordable:** from Electro Spirit 46%, Skeletons 41%
  and Ice Spirit 37% down to Hog Rider 14%, Musketeer 13% and Fireball 9%.
- **Rejection reason counts:**
  - 3,570 neither flag;
  - 1,159 both flags;
  - 414 unaffordable only;
  - 388 wrong card only.

These are temporal associations, not causal estimates. T4 redoes the analysis with the next native observation
after each tap.
