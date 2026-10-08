# L2-v4 preregistration (DRAFT, not frozen)

Draft 2026-10-08 (~18:45 UTC), design sub-agent on 127x05, research only: no games, emulator actions or training.
The coordinator reviews, amends, freezes and commits it. Paths are relative to `reports/strategy_council_20260928/`
unless stated. "Frozen" below means: listed in the L2-v4 content manifest (sha256) sealed before the first
confirmatory game, after all entry criteria (§5) hold.

## 0. Recommendation

- **Run L2-v4 as a four-arm paired test on the 3 L2 families:** P (pixels v4), O (fair truth oracle, same renderer
  and same P4), S-d (simulator, 27-tick total delay, delay-aware), S (simulator, no delay, descriptive). Only P and O
  use the renderer; S and S-d are fleet CPU and cost minutes.
- **Primary:** P − O paired score, family-stratified paired bootstrap. **PASS iff the 95% lower bound > −0.10.**
  Keep DESIGN's margin (§4.2) but **not** its sample size. DESIGN §5.3 says 96 pairs pass a true difference of 0
  "with high probability". At its own 30% discordance assumption, the power is 0.43; at a realistic 18% it is 0.64.
- **Sample size: 144 pairs planned** (80% power at a true difference of 0 if E[D²] ≤ 0.18), with a **blinded
  re-estimation at 54 pairs** to a final n in {108, 144, 180, 216}. **Wall time:** about 6.0 min per renderer game,
  so 144 pairs = 288 games ≈ **29 h on one renderer**, or ≈ 14.5 h if two renderers run P and O of the same pair at
  the same time. Two concurrent renderers are allowed only if a two-instance loop qualification passes first.
  Over the whole n range: 22–43 h on one renderer, 11–22 h on two.
- **Entry (all required, §5):** formal v4 perception gates, with the event row at ≥90/90 (S5 decision); the P4
  verifier re-test with the v4 HUD head (≥324 + 324 trials, ≥99% / ≥99%, Clopper-Pearson reported); the Mac
  build48 identity; an emulator-on latency/loop smoke with formal v4 weights; frozen tracker v3 parity on v4 inputs;
  quiet-host preflight; O/S/S-d harness tests; a seed audit. I also recommend a **binding simulator go/no-go**: run
  the v4-measured noise in the simulator; if it predicts P − O below −0.10, don't spend ~30 renderer-hours on a
  predictable FAIL (§5 E9, open decision 1).
- **Realistic expectation:** with v3-level board noise, S6 predicts P − O ≈ −26 pp: T3-N97-d22-aware 60.2% vs
  clean-d22-aware 86.7% (`search-noise-s6/RESULTS.md`). P can pass only if the v4 board, HP and event channels are
  much better than the v3 noise model. The go/no-go check measures exactly that, before any renderer time is spent.

## 1. Question and hypotheses

**Question.** On the offline renderer, with everything except the player's sensor held fixed, how much playing
strength does the full v4 pixel pipeline lose relative to fair, perfect perception? The pipeline is P0 capture,
v4 perception, frozen tracker v3, the S6 delay-aware 4-root search, and P4 verified actuation. Secondary
questions: how large is the renderer-vs-simulator gap, and how much does the command delay cost?

- **H1 (primary, non-inferiority):** score(P) − score(O) > −0.10.
- **H2 (descriptive):** score(O) − score(S-d) ≈ 0. A large negative value means the renderer engine, the opponent
  plumbing or P4 cost strength that the simulator does not see.
- **H3 (descriptive):** score(S) − score(S-d) ≈ +2.7 pp, the S6 latency cost, CI [−2.0, +7.4].
- **Pre-registered prediction:** P − O ≈ S-v4N − S-d (§5 E9). Section 10 uses a mismatch between the two to choose
  the next diagnostic.

## 2. Arms

| Arm | Where | Sensor / belief | Planner | Actuation | Role |
|---|---|---|---|---|---|
| **P** | renderer, Mac | v4 perception on pixels (P1); **frozen tracker v3** opponent belief; pixel own-state ledger | S6 delay-aware, K=4 roots, horizon 160, interval 10, 200 ms deadline, **d = 27 ticks** | P4: gRPC, 20 ms inter-tap, v4-HUD pre-tap remap and verifier, ≤1 retry | treatment |
| **O** | renderer, Mac, same AVD, seed and opening as P | **Fair truth projection** replaces P1's *output* (P1 still runs in shadow on every frame); belief = **exact public deduction** (S6 clean-cell `derived_d1.py`) on truth public events | identical to P | **identical P4**, incl. its pixel-HUD verifier | control |
| **S-d** | simulator, fleet CPU, Linux build48 | clean exact public deduction (as S6 clean cells) | identical P3 scorer, K=4, **command delay 27, delay-aware** | engine command channel, single pending command, no retries (S6) | engine-gap anchor |
| **S** | simulator, fleet CPU | as S-d | identical, **d = 0** | as S-d | descriptive |

**O precisely.**
- **Truth source.** At each captured frame, the projection takes the latest coherent native observation with tick
  ≤ that frame's `tick_hi` (the T1 collector's tick bracket). It fills the same `PublicVisionFrame` contract that
  P1 publishes. It is published when P1 finishes that frame, so O's queue timing, CPU/MPS load and frame drops
  match P's.
- **Public fields only:** own hand, next card and fractional elixir; visible bodies with identity, owner, position
  and HP; tower and King HP; clock and phase.
- **Opponent events:** card, side, tile and `exec_tick`, taken from the opponent controller's succeeded schedule
  receipts. Each is delivered at the first frame with `tick_hi ≥ exec_tick`, with q=1 and σ=0.
- **Never passed to the player:** opponent hand, deck order, opponent elixir, RNG or unrevealed cards. The player
  derives opponent elixir and cycle itself (fair-information rule). O is a *fair* player with perfect perception,
  not a cheating oracle.
- **Shared P4.** P4 is the shared actuation layer, so O uses the same v4 pixel HUD for its pre-tap check and
  verification. P − O then contains no actuation difference.

**Held fixed across P and O** (frozen hashes):
- **Renderer stack:** APK, hook (22-tick nominal command age), attestation `864227bf…`, read-only AVD
  `clasher_reference_api35`, `-gpu host`, 2 cores, 3,072 MiB, 20 FPS capture.
- **Timing and native code:** `actuation/backend-timing.json` (D_b p50/p99 1,151.7/1,187.3 ms; verify deadline
  1,787.3 ms; rollback 1,987.3 ms; `planner_total_delay_ticks` 27), and the Mac build48 native `9263a8f7…`.
- **Player code and models:** runtime `src/clasher/live/` hashes, the frozen train prior catalog, and the v4
  checkpoint and calibration.
- **Opponent:** the C56 script, its style, an 8-tick command lead and a 500 ms decision cadence (as in L2).
- **Game setup:** seed, decks, seat 1 for the player, and a no-action warm-up to tick 220.
- **Planner seed:** world seed + 100000 in both arms.

**Known differences, declared and not removed** (they enter the secondaries, not the primary):
- **O/P vs S-d:**
  - the renderer engine vs the simulator engine and RNG;
  - the opponent's probe cadence, 8-tick lead and read timeouts;
  - P4 verification and retry;
  - runtime triggers on a ~4-tick-stale frame vs the simulator's 2-tick poll;
  - a 200 ms wall deadline vs full scoring. On the Mac the deadline rarely binds: active search p99 was 144 ms with
    0 overruns (`runtime-mac-latency.json`). The truncation share is logged.
- **Simulator arms:** they reuse the P3 scorer with K=4 roots from the clean deduction state. S6 itself used a
  single public root; this departure keeps S-d's planner identical to O's.

## 3. Population, schedule and seeds

- **Decks:** the L2 decks, unchanged (`live-loop/l2/register.py`):
  - Hog 2.6: HogRider, Musketeer, Cannon, Fireball, Log, IceGolem, IceSpirit, Skeletons;
  - X-Bow cycle: Xbow, Tesla, Knight, Archers, Fireball, Log, Skeletons, ElectroSpirit;
  - Royal Hogs spawners: RoyalHogs, FirespiritHut, GoblinHut, Berserker, Ghost, Fireball, Log, ElectroSpirit.

  That is 18 distinct cards. The decks are fixed now, before any L1-v4 heldout result exists, so they cannot be
  chosen for perception quality.
- **Rotation as L2,** with families interleaved so that host drift spreads across families. Pair i has family
  f = i mod 3 and index j = ⌊i/3⌋:
  - own deck = family deck;
  - opponent deck = Hog 2.6 if f = 0, else deck (j mod 3);
  - opponent style = (balanced, pressure, defense)[(j + f) mod 3];
  - both decks shuffled by `random.Random(seed)` as in L2;
  - player seat 1.
- **Arm order:** P first iff ⌊j/3⌋ is even. Over every 6 values of j, each style/opponent cell gets both orders.
  n must be a multiple of 18, which 54/108/144/180/216 all are. As in L2, style and opponent deck are aligned
  within the non-Hog families, so style and deck splits are descriptive only.
- **Seeds:** all fresh, registered now, and audited before use.

  | Use | Formula | Range |
  |---|---|---|
  | Confirmatory worlds | 1976300001 + 1009·i | i = 0..215 (maximum n) |
  | P4 re-test trials | 1976100001 + 101·k | k = 0..703 (640 scored + 64 development) |
  | Integration smoke and two-instance qualification | 1976200001 + 101·k | k = 0..31 |
  | Simulator prediction worlds | 9783000001 + 1009·i | i = 0..215 |
  | Simulator prediction sensors | 9883000001 + 1009·i | i = 0..215 |

  - **Audit:** as S6, scanning retained text, NPZ seed fields and receipts on 127x01, 127x04, 127x05 and the Mac
    repo plus runtime root. It covers L2 (1967150031+1009i), T2 (1974…), Phase A (1975…, split
    `3edbd25b…`), S1–S6 and Stage 5/6. Any collision blocks registration. Unavailable historical paths are
    reported as a limitation.
- **Pairing check:** before a pair counts, the two renderer games must show exactly equal opening state at tick
  220: both hands and queues, and elixir. S and S-d copy that opening into the simulator (L2 rule); the evaluator
  copies it, never the player.

## 4. Primary endpoint, decision rule, power and wall time

### 4.1 Estimator and rule

- **Score:** per game, s = 1 for a win, 0.5 for a draw and 0 for a loss, from the native terminal receipt's
  winner. D_i = s_P,i − s_O,i, and D̄ is the mean over all n pairs. Families have equal n, so this equals the
  stratum-weighted mean.
- **CI:** family-stratified paired bootstrap. Each of 10,000 resamples draws n/3 pairs with replacement within
  each family. Percentile 95% interval, `numpy.default_rng(1976390001)`.
- **PASS iff all hold:**
  1. the lower bound is strictly greater than −0.10;
  2. all n pairs are complete, with native terminal receipts in both renderer arms;
  3. there are zero fair-information violations;
  4. the frozen manifest is intact on every game, by per-game provenance hash check.

  Otherwise FAIL. An incomplete run is reported as INCOMPLETE, never as PASS.
- **Also reported:** the two-sided CI, W/D/L per arm, and the exact McNemar test on win/non-win discordant pairs as
  a sensitivity check. It can't change the verdict.

### 4.2 Why keep the −0.10 margin

1. **Continuity:** L2, DESIGN §5.3 and the S1 gate (E4 − A > −0.10) all use it. Changing it now would break the
   comparison with L2's −43.8 pp result.
2. **Scale of known defects:** the margin is smaller than any single known large defect, so a pipeline carrying
   one of them at full size should fail. Those defects are the derived opponent state (+15.2 pp to repair, S2),
   delay-unaware planning (+14.5 pp, S6) and the T3 tracker gain (+8.2 pp, S5). The margin is larger than the
   small channels (HP +3.1, own state 0, latency when delay-aware +2.7), which are not worth blocking L3 on.
3. **A tighter margin is infeasible:** at −0.05 the required n is 4× larger, about 570 pairs at E[D²] = 0.18, or
   about 115 renderer-hours on one renderer.
4. **A looser margin is meaningless:** −0.15 would pass a pipeline that had lost the entire derived-state benefit.

### 4.3 Power

The normal approximation gives power ≈ Φ(0.10/√(E[D²]/n) − 1.96). A 300-replicate Monte Carlo of the stratified
bootstrap matched it: 0.84 vs 0.81 at n = 144 and E[D²] = 0.18; 0.73 vs 0.71 at E[D²] = 0.226. With win
probability p in both arms and independent outcomes within a pair, E[D²] = 2p(1−p): 0.18 at p = 0.90, 0.226 at
p = 0.87. For O's likely level: S6 clean-d22-aware scored 86.7% across 9 families; L2's simulator arm won 48/48 on
these 3 families. Correlation through world difficulty lowers E[D²].

| E[D²] | n=96 | n=108 | n=144 | n=180 | n=216 | n for 80% / 90% |
|---:|---:|---:|---:|---:|---:|---:|
| 0.10 | .87 | .91 | .97 | .99 | 1.00 | 78 / 105 |
| 0.15 | .72 | .77 | .87 | .93 | .97 | 118 / 158 |
| **0.18** | .64 | .69 | **.81** | .89 | .93 | 141 / 189 |
| 0.20 | .59 | .64 | .77 | .85 | .91 | 157 / 210 |
| 0.25 | .50 | .55 | .67 | .77 | .84 | 196 / 263 |
| 0.30 | .43 | .48 | .59 | .69 | .77 | 235 / 315 |

Power is at a true difference of 0. At a true −0.03, n = 144 gives 0.51 at E[D²] = 0.18. The margin assumes P is
genuinely near O; this design cannot certify a small real loss.

**Blinded sample-size re-estimation (the only interim look).**
- **When and what:** once 54 pairs are complete, a script reads the terminal receipts and computes m̂₂ = mean(D_i²).
  D² is symmetric in sign, so this reveals nothing about direction.
- **Output:** it prints only n_final = clamp(18·⌈785·m̂₂/18⌉, 108, 216), where 785 = (1.96 + 0.8416)²/0.01. Nobody
  reads arm-level scores or m̂₂.
- **Validity:** n_final is fixed in a dated receipt before pair 55 starts. There is no efficacy or futility
  stopping. Re-estimating a nuisance parameter blind does not materially inflate the type-I error for paired
  designs.
- **Default:** if the script cannot run, n = 144.

### 4.4 Wall time

- **Per renderer game:**
  - L2 native games averaged 5,103 ticks (`l2/metrics.json`: 244,928 / 48) at 19.82 ticks/s, i.e. 4.3 min of play.
  - Overhead is about 80 s: preflight, configure, opening check, runtime warm-up, receipts and flush.
  - Technical reruns add about 5%.
  - **Planning value: 6.0 min.** The bound is about 6.5 min, for a 6,001-tick overtime game.
  - This agrees with L2's actual cadence: 4.1 min per native game for pairs 30–47, 7.7 min for the overtime-heavy
    Hog pairs 5–15.

| n | Renderer games | 1 renderer (sequential P, O) | 2 renderers (P ∥ O, same pair) |
|---:|---:|---:|---:|
| 108 | 216 | 21.6 h | 10.8 h |
| **144** | **288** | **28.8 h** | **14.4 h** |
| 180 | 360 | 36.0 h | 18.0 h |
| 216 | 432 | 43.2 h | 21.6 h |

- **Additional time:**
  - Before the run:
    - P4 re-test, about 3 emulator-hours (T2's 640 trials took 2–3 h);
    - the T9 integration smoke, about 1 h;
    - the optional two-instance qualification, about 1.5 h;
    - the S-v4N prediction, about 20 min of fleet CPU.
  - During the run: S and S-d, 2n simulator games, about 15 min of fleet CPU (S6 ran 1,280 games in 15 min on two
    hosts).
- **Concurrency rule:**
  - **Default: one renderer**, with P then O (or O then P) back-to-back per pair.
  - **Two renderers** are allowed only if a pre-registered two-instance qualification on smoke seeds passes every
    §5.2 loop gate on **both** instances at once. In that mode, P and O of the same pair run simultaneously, so
    contention is shared equally. Renderer assignment alternates by pair.
  - The mode is fixed before the first confirmatory game. A downgrade from 2 to 1 is allowed only between pairs,
    after a technical failure, and is logged.
  - **Why concurrency isn't simply assumed:** two runtimes need about 2 × (2 emulator + 4 search + 3 pipeline)
    cores against 12, and they share the GPU between `-gpu host` rendering and MPS perception. Phase A also hit
    critical memory pressure at 3 renderers (COORDINATOR 06:41Z).

## 5. Entry criteria: all must hold before the first confirmatory game

An unmeasured criterion counts as BLOCKED, never as PASS.

| # | Criterion | Requirement | Evidence / source |
|---|---|---|---|
| E1 | **v4 perception (§5.1)** | Sealed formal T7 selection, scored once on heldout through the pipelined runtime on the Mac with the emulator idle-running (`l1/PREREG.md`). **Event row as decided by S5:** opponent recall **and** precision ≥90% at 500 ms, each with a bootstrap lower bound ≥87% (the DESIGN 95/92 pattern shifted to the 90 minimum). 97/97 is the target, reported. The L1 report's own frozen 95/95 verdict is reported unchanged; it is not re-scored. All other §5.1 rows apply, with three amendments for the adopted tracker (open decision 3): (a) derived opponent elixir: coverage 85–95%, MAE ≤0.80 and width ≤3.0, which is tracker v3's simulated N90 level (S5: 0.892 / 0.769 / 2.79); the ≤0.5 / ≤2.0 targets were set for ELT; (b) hand claims: accuracy ≥90% when the hand reaches ≥90% mass, with the count reported; the "≥60% of queries concentrated" row becomes descriptive, since tracker v3 resolves 24% of samples even at N97; (c) the perception-stage p95 ≤40 ms becomes descriptive, because end-to-end latency is gated in E4. **Per card-side:** every opponent-side card among the 18 L2-v4 cards with ≥10 heldout events must meet recall ≥80% and precision ≥70%. Cards with <10 events are listed as unqualified, and their in-loop results are descriptive. Decks are not changed in response. | `l1/RESULTS.md`, `selection-freeze.json` |
| E2 | **P4 verifier re-test** with the v4 HUD head | Protocol below. Sensitivity ≥99% **and** specificity ≥99%, with Clopper-Pearson 95% bounds reported. | new `actuation/v4hud-retest/` |
| E3 | **Mac build48 identity** | `MAC-NATIVE-BUILD48.json`: native `9263a8f7…`, 66/66 source pins, P16 12/12, C56 7/7, random 24/24, recorded 8/8, Stage 5 200/200, Stage 6 69/69, tests 36/36. Every game's provenance must show the same loaded native SHA. Fleet arms use the Linux build48 `78bd9950…` (Stage 6 qualified). | `MAC-NATIVE-BUILD48.md`, COORDINATOR 18:24Z |
| E4 | **Runtime latency and loop, with formal v4 weights and the emulator running** | The receipt `runtime-mac-latency.json` (p50 186 / p99 334 ms vs ≤260/≤400) used v3 fallback perception, mock input and the emulator off, so it doesn't qualify P. Required: a **T9 integration smoke**, 8 matches on smoke seeds, real gRPC taps, unscored, passing all §5.2 loop gates with the revised budget: ≥18 FPS; ≥95% processed; gap p99 ≤150 ms; frame→submission p50 ≤260 / p99 ≤400 ms; overruns ≤1%; first-attempt acceptance ≥90%; ≤1.15 attempts per confirmed play; unknown windows ≤5%. `planner_total_delay_ticks` is recomputed as round((smoke median frame→submission + 1,151.7)/50). If it differs from 27, the new value is frozen for P, O and S-d before the first game. The ANE vs MPS device choice is frozen the same way. | `RUNTIME.md` "Remaining prerequisites" 1–2 |
| E5 | **Frozen tracker v3** | Frozen S4 `tracker_v3.py` `0e6a7c36…` and dependencies (`RUNTIME-FROZEN-INTEGRITY.json`); runtime adapter `tracker.py` `e2690e28…`. Bit-exact parity was shown on 32,837 fleet and 2,200 Mac updates; add **≥5,000 Mac updates driven by the L1-v4 heldout replay outputs**, since the inputs are new. **Calibration level, by rule:** frozen S4 N97 (radius 0.0682) if the E1 heldout opponent recall and precision are both ≥97%, otherwise N90 (0.1104). No other tracker setting changes. | `RUNTIME.md` latency revision |
| E6 | **Quiet host**, checked before every game | No other clasher jobs on the Mac: T1 pool stopped, 0 collector processes; no non-L2-v4 emulator. Memory-pressure level 1; free memory ≥40%; 1-minute load ≤6.0 (the latency run's preflights saw 3.5–4.5); free disk ≥20 GiB; shipper backlog ≤4 GB. Record console users, the UTM VM state and swap. On failure, wait and recheck every 5 min for up to 60 min. The game never starts on a failed check. | DESIGN §2.8; `runtime-mac-latency.json` preflights |
| E7 | **Renderer receipts**, per session and after any restart | `emulator-host/.../complete.json` ownership (PID, serial, ports, read-only AVD, attestation `864227bf…`, backend host); IPv4/IPv6 app-UID REJECT rules; backend-timing SHA as frozen. **20-trial D_b check** on development seeds: p50 within 1,151.7 ± 100 ms. T1 completion receipt and pool stopped. | `T2-RESULTS.md`, `t1-completion-mirror/` |
| E8 | **Harness and fairness tests** | O truth adapter: an allow-list of public fields, and a test that injecting any privileged key raises. Exact-deduction belief equals S6 clean-cell outputs on recorded traces. S/S-d harness: K=4 P3 scorer, d ∈ {0, 27}, at d=0 equal to the native scorer, as S6. Opening-copy and opening-equality checks. Shadow P1 in O. L2's four boundary checks carried over: masked-HUD invariance, confidence preservation, denied file/socket reads during P decisions, seed balance and disjointness. Pixel end/result reader in shadow, logged for §5.2; if it doesn't exist, that §5.2 row is BLOCKED, which doesn't affect the strength verdict. | new tests |
| E9 | **Simulator go/no-go (recommended binding)** | Cells S-v4N and S-d-pred, 216 fresh simulator worlds each, with the L2-v4 schedule structure, paired. **S-v4N** = the S6 noisy harness with d=27 aware, tracker v3 at the E5 level, and each noise channel set from the sealed L1-v4 heldout report: event recall and precision (per card where ≥10 events), exec-time error, placement, board phantom/drop, HP missing/error, own-HUD error. Where the v4 report has no measurement, the v3 noise-model value is used and listed; board labels are masked, see `l1/RESULTS.md`. **Go iff the point estimate of (S-v4N − S-d) ≥ −0.10.** The value is also recorded as the prediction for P − O. | new `search-noise-l2v4pred/` |
| E10 | **Registration** | Seed audit passed; schedule and this PREREG frozen with a content manifest; `status.py` prints counts only. | — |

**E2 protocol: P4 verifier re-test**, written and frozen before any trial (coordinator decision 00:35Z (a)–(c)).

- **System under test:** P4 exactly as it will run in L2-v4. gRPC transport, 20 ms inter-tap, 20 FPS capture,
  `backend-timing.json` windows, and the frozen v4 HUD checkpoint and thresholds from E1. Freeze the code and
  weights by hash before trial 1. Up to 64 development trials on separate seeds are allowed before the freeze and
  are excluded.
- **Spend predicate, ledger-relative:**
  - **The two predictions:** P2's phase-locked own-elixir ledger gives Ê_spend(t), which includes the command's
    cost from its acceptance, and Ê_no(t), which doesn't.
  - **Detection:** a play counts as detected at the first frame t in the window where both hold:
    1. The slot at the remapped slot index no longer shows the submitted card (it shows the cycle's next card or
       is refilling).
    2. Of the ≥3 most recent frames since the slot change, a majority have a HUD integer-elixir reading with
       |HUD − Ê_spend| ≤ 1, and closer to Ê_spend than to Ê_no.
  - **Effect:** a single baseline digit read can no longer veto a play, which was the T2 Cannon failure. Ties at
    the 10-elixir cap are scored by the slot-change condition alone.
- **Positives: 324**, i.e. 18 L2-v4 cards × 18 trials. Each card covers 3 elixir margins at submission (cost +0.1,
  +1, +3) × 3 recencies since the player's last acceptance (≤1.5 s, 3 s, ≥8 s; the ≤1.5 s level is the R2 regime)
  × 2 phases (1x vs 2x/3x elixir, by start tick as in Phase A). Plays are truth-legal and affordable at execution
  by construction.
- **Negatives: 324**, i.e. 6 types × 54. Each window is the backend window (submission + 1,787 ms), checked for no
  native own acceptance through 1,987 ms:
  1. no input;
  2. card selection only;
  3. tile tap only;
  4. a tap that is unaffordable at execution;
  5. an opponent play within 2 tiles during the window;
  6. no input while own elixir crosses an integer or sits at the 10 cap.
- **Truth:** native first-observed own acceptance (as T2), evaluator-only.
- **Endpoints:**
  - **Sensitivity:** share of positives detected within 600 ms of native acceptance, inside the window.
  - **Specificity:** share of negatives with no detection in the window.
  - **Pass bar:** each ≥99%, i.e. at most 3 misses and at most 3 false detections out of 324. The Clopper-Pearson
    95% interval for 321/324 is [97.3, 99.8]%, and for 324/324 it is [98.9, 100]%.
  - **Also reported:** detection latency after native acceptance (p50/p95), pre-tap slot-identity accuracy
    (target ≥99.5%), and retries issued on positives (must be 0 duplicate plays).
- **Evidence and failure handling:** retain the H.264 frames for every trial (about 3 s each, a few hundred MB),
  not only for the misses. On FAIL, the misses are analysed and any fix gets a new prospective re-test on fresh
  seeds. The failed trials are never re-scored.

## 6. Secondary and descriptive endpoints

None of these can change the primary verdict.

1. **O − S-d** (renderer engine + opponent plumbing + P4 gap): paired by world, family-stratified bootstrap, with
   CI. If the point estimate is < −0.10, register and run the DESIGN **O-probe** follow-up: O submitting through
   probe commands instead of taps, same seeds, to separate actuation from engine.
2. **S − S-d** (delay cost; S6 found +2.7 [−2.0, +7.4]) and **P − S-d** (total gap).
3. **P vs L2's 27/48 (0.5625):** P's score minus 0.5625 with a family-stratified two-sample bootstrap. Also O vs
   L2's simulator arm (48/48). The decks and rotation are L2's; the seeds and player differ.
4. **Per family:** P, O, S-d and S scores and P − O, each with a stratum bootstrap CI. No per-family pass/fail.
   Style and opponent-deck splits likewise.
5. **Calibration of the simulator:** observed P − O vs the E9 prediction, with the difference and a CI from the
   two bootstraps (independent samples).
6. **§5.2 loop gates,** over all P games (perception rows), and over P and O games (actuation and latency rows):
   - capture FPS and processed share; gap p99; frame→submission p50/p99;
   - overruns; first-attempt acceptance; attempts per confirmed play; unknown windows;
   - **in-loop opponent events at 500 ms vs the offline L1-v4 result (within 2 pp) and vs the event gate**; the
     shadow P1 in O games adds a second, decision-independent sample of this;
   - pixel end and result reading.

   These decide loop readiness and L3 readiness (DESIGN §5.3: L3 needs §5.1 + §5.2 + §5.3 + the canary), not
   strength.
7. **Mechanism diagnostics** (P vs O vs S-d; associations only):
   - tracker coverage, width, MAE and hand-claim accuracy;
   - board phantom and drop rates and HP missing rate;
   - own-hand and elixir error;
   - P4 in-loop verification (vs native) and retry/rollback counts;
   - pending-blocked decision demand;
   - search truncation share;
   - opponent coherent-read skips (L2 had 19 timeouts in 5 matches);
   - native ticks per wall-second; game length.

## 7. Run procedure, technical reruns and interruptions

- **Order:** pairs run in index order. Within a pair, both renderer games run back-to-back on the same renderer
  session (or concurrently, §4.4) before the next pair starts. Simulator arms for a pair run once its opening is
  recorded; their receipts stay unread.
- **Integrity checkpoint after pair 6 (loop metrics only; win/loss never read):** stop, as a failed qualification
  and not a strength result, if any of these hold:
  - processed FPS <15 in either arm;
  - first-attempt acceptance <70%;
  - in-loop opponent-event recall at 500 ms <80% in P;
  - any duplicate or unreserved tap.

  On a stop, all games are retained; a fix needs fresh seeds and a re-frozen PREREG.
- **Blinded re-estimation at 54 pairs** (§4.3).
- **Technical rerun rule** (as in L2 and S1–S6):
  - **What may be rerun:** only an *incomplete* game whose cause is infrastructure. That means:
    - a renderer or emulator crash or restart;
    - a lost probe or gRPC forward;
    - a runtime worker death or heartbeat timeout (the runtime has no auto-restart: `RUNTIME.md`);
    - a coherent-observation gap >10 s;
    - a wall guard of 900 s (a 6,001-tick game takes about 303 s at 19.8 ticks/s);
    - a Mac sleep, reboot or session restart.
  - **How:** partial logs are preserved under `recovery-<label>/` with an `INCIDENT-*.md`. The same seed is
    replayed after the opening-equality check against the pair's other arm. The completed other arm is kept.
  - **What is never rerun:** a game that reached a native terminal is never rerun or replaced, whatever its loop
    metrics. Poor FPS, rejects or misreads are data.
  - **Player absent:** if the runtime is absent for >2 s for a technical reason, the harness pauses the renderer
    through the probe. The game is then incomplete. It is never counted as terminal; this is L2's SIGSTOP lesson.
- **Rerun limits:** if one seed fails 3 times, or technical reruns exceed 10% of games, stop and write an incident.
  A resume needs a dated infrastructure-only amendment, with no player, perception, analysis or gate changes.
- **After any emulator restart:** repeat E7, including the 20-trial D_b check. If D_b drifts by more than 100 ms,
  stop: the 27-tick planner delay would no longer match the hook.
- **Host events:** every long process runs under `pilot/detach.sh` with per-game resume from receipts (memory note:
  session restarts kill jobs). The status script prints counts and health only.
- **Amendments:** dated, and only before the first confirmatory game. Later changes are reported as deviations.

## 8. Fair-information and live-play rules

- **P:** inputs are sanitized pixels, the player's own deck and commands, public card metadata and the frozen train
  prior. `PublicVisionFrame` keeps its privileged-key rejection, and denied-read tests run during decisions.
- **O:** the public-field allow-list in §2. Opponent elixir, hand and cycle are *derived* from public events, which
  the fair-information rule permits. Unrevealed cards and RNG are never read.
- **S and S-d:** clean exact public deduction, as in S6.
- **Opponent scripts and evaluator:** they may read native state, as in L2; that never reaches the player.
- **Live play:** offline renderer only, read-only AVD, game-UID network rejected (IPv4 and IPv6). No official
  client, no ladder, no account. Plain taps only: no randomized or "humanized" timing and no detection-evasion
  feature (live-play authorization; DESIGN §2.7.6). Nothing beyond offline evaluation is added to the
  modified-client use.

## 9. Logging and outputs

- **Per renderer game:**
  - `config.json`, `provenance.json` and `pids.json`;
  - per-frame latency and queue logs, public perception outputs and event candidates;
  - belief summaries, roots, decisions with candidate scores, and the command/ledger/P4 verification log with raw
    HUD reads;
  - evaluator native observations per frame bracket, opponent commands and receipts, read skips, the opening state
    and the terminal receipt;
  - per-second host health (load, pressure, swap, FPS);
  - sanitized 540×1140 H.264 of every game, about 30 MB per game and ~13 GB at n=216, shipped to 127x01 like T1.
    The Mac buffer stays ≤6 GB.
- **Provenance** covers: runtime, tracker, S6 and actuator hashes; v4 checkpoint and calibration; timing profile;
  native SHA; split; seeds.
- **Simulator arms:** S6-style immutable receipts.
- **Outputs:** `live-loop/v4/l2/` with this PREREG (frozen), `schedule.json`, `seed-audit.json`,
  `manifest.json`, the E1–E10 entry receipts, `sample-size.json` (n_final), `RESULTS.md` (every gate PASS/FAIL,
  primary first) and `metrics.json`. The coordinator recomputes the primary independently from raw receipts before
  reporting, as with S5 and S6.

## 10. What happens if P fails

There is no tuning, threshold fitting, calibration or selection on L2-v4 games or recordings, ever. They may be
used only for forensics. Any fix is tested on fresh seeds under a new PREREG. L2-v4 is not rerun until it passes.

1. **First, compare P − O with the E9 prediction (S-v4N − S-d).**
   - **Prediction inside the observed CI:** the simulator models the loss. The next diagnostic is a pre-registered,
     simulator-only **v4 channel decomposition** in the style of S2: from S-v4N, repair one channel at a time to
     truth (events, derived state, board, HP, own HUD, latency), and from S-d, add one at a time. It uses fresh
     seeds and takes minutes of fleet CPU. Its largest lever picks the next investment: event head, board/HP head
     or tracker.
   - **Observed loss clearly larger than predicted** (the prediction above the upper CI): an unmodelled
     renderer-side loss. The next diagnostic is a **deterministic replay forensic** on the recorded L2-v4 videos.
     The replay harness runs P1+P2 on the P and O game recordings at true timestamps. Measured against native
     truth, it reports in-loop event recall vs offline, timing, board and HUD errors. Measured against O's truth
     decisions, it reports decision agreement on the same states. That localises the gap to the channel
     (perception content, latency/backlog, or actuation). Next, a renderer **hybrid-arm** study under a new PREREG:
     P with truth events, and P with truth board.
2. **If O − S-d < −0.10 as well:** run the O-probe follow-up (§6.1) before any perception work. The renderer or
   actuation itself is then costing strength, and P − O cannot carry the blame.
3. **If P passes but a §5.2 loop gate fails:** strength is non-inferior but the loop isn't ready. Fix the failing
   gate and requalify it with a smoke. Strength is not rerun unless the fix touches P1–P4 decision behaviour.

## 11. Deviations from DESIGN §5.3 and earlier decisions (all deliberate)

| Item | DESIGN / earlier | Here | Why |
|---|---|---|---|
| Pairs | 96 (32 per family) | 144 planned, 108–216 after blinded re-estimation | DESIGN's power claim is wrong (0.43 at its 30% discordance) |
| Simulator arms | S clean | S-d (d=27, aware) plus S (d=0) | T2 amendment items 4–5; S6; latency revision (total delay 27, not 22) |
| Simulator planner | S6 single root | P3 scorer, K=4, as the runtime | Keeps O − S-d free of planner differences |
| O belief | not specified | exact public deduction (S6 clean) on truth events; shadow P1 | O = perfect, fair perception; matches S-d belief; equal compute load |
| Event gate | 95/95, LB 92 (provisional; L1 PREREG frozen at 95/95) | ≥90/90, LB ≥87; 97/97 target | S5 decision 07:11Z |
| Derived-state rows | MAE ≤0.5, width ≤2.0, ≥60% concentrated | MAE ≤0.80, width ≤3.0, hand-claim accuracy ≥90%; concentration descriptive | Tracker v3 adopted (S5); old rows were ELT targets that v3 misses even in the simulator |
| Wall time | 2 emulators × 96 × 5 min ≈ 8 h | 1 renderer by default; 2 only after qualification | The quiet-host latency receipt is single-instance |

## 12. Open decisions (the repo can't answer these)

1. **Is E9 binding?** Recommendation: yes. If it predicts FAIL, run the §10.1 simulator decomposition instead of
   ~30 renderer-hours. Alternative: run a small descriptive calibration batch (18 pairs) to validate the simulator,
   with no verdict.
2. **Two renderers?** It depends on whether the Mac (12 cores, 24 GB, shared GPU, the non-clasher UTM VM) sustains
   two runtimes within the §5.2 gates. Only the qualification can tell. Recommendation: attempt it after E4; it
   halves the wall time.
3. **Sign-off on the §5.1 row amendments in E1 (a)–(c)** for the L2-v4 entry. They replace frozen-L1 targets that
   the adopted tracker cannot meet by design; the L1 report itself stays unchanged.

## Sources

- `live-loop/v4/DESIGN.md` §2.5–2.8, §5.1–5.3, §6.
- `live-loop/l2/PREREG.md`, `RESULTS.md`, `metrics.json`, `register.py`, `PROGRESS.md`.
- `COORDINATOR.md`, entries 2026-10-07 23:55Z to 2026-10-08 18:24Z: T2 option B; S1–S6; latency revision 09:19Z;
  Phase A 15:45Z; Mac latency 17:45Z; build48 18:24Z.
- `amendments/2026-10-07-t2-actuation-timing.md`; `live-loop/v4/T2-RESULTS.md`; `actuation/backend-timing.json`.
- `live-loop/v4/RUNTIME.md`; `runtime-mac-latency.json`; `MAC-NATIVE-BUILD48.md`.
- `live-loop/v4/l1/PREREG.md` and `RESULTS.md` (formal fits complete; selection pending; heldout unopened at 17:34Z).
- `search-noise-s5/RESULTS.md`; `search-noise-s6/RESULTS.md` and `PREREG.md`.
- Power computations: normal approximation plus a 300-replicate stratified-bootstrap Monte Carlo (this draft).
