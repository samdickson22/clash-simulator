# pretrain-v1 progress log

New single-model Clash Royale policy. Input: the live memory record plus causal history. Output: gate / slot /
tile / value, with the gate sampled. There is no decision-time search. Design:
`/mpac/sdicks02/scratch/new-pretrain-20261020/{DESIGN,PREREG-DRAFT,INVENTORY,FIDELITY}.md`. Engineering choices:
[DECISIONS.md](DECISIONS.md). Code: `bot/pretrain_v1/`. Data: `/mpac/sdicks02/datasets/pretrain-v1/` on 127x05
(copied to 127x08).

Constraints in force:
- Only 08's GPU is used.
- RL training on 04/08 keeps running.
- Hosts keep MemAvailable above 28 GiB and load at or below 90.
- No Mac or live changes, and no deployment.
- Code lands on main through fresh worktrees after GPT-6.1 Sol (high) review.

## 2026-10-21

- **12:00 PDT: inputs pinned.**
  - Deployed memory package, read-only from the Mac MEM-MANIFEST: `state.py` 9085e337, `rfextras.py` 513088f2,
    cards-122 289d240f. Local byte-identical copies are vendored.
  - Live runs use `spell_events=False`, so record `events` is always empty live.
  - Re-drive corpus at the time: 15.5k / 252k matches, 34 acked batches. Jobs with source coordinates are at
    `scratch/native-redrive-full-20261021/jobs/`.
- **Label-timing measurement** (300 matches, 19,394 executed plays). At E−27 the card is in hand 99.0% of the
  time and affordable 88.3%. Under DESIGN's strict mask, 12.6% of plays therefore cannot be lag-aligned (see
  DECISIONS item 12).
- **Piece 1, featurizer**, and **piece 2, dataset builder**, written.
  - 13 unit tests pass.
  - Smoke parity audit (6 matches): 9,638 polls where the serving path (`policy.Session`) equals builder bytes,
    and 0 violations in 9,638 private-mutation and 4,369 future-suffix cases.
  - Builder speed: 0.4 s per match per core, about 106k stored rows per 500-match batch.
  - Commit e001cf230 on branch `pretrain-v1/featurizer`; Sol review R1 requested.
- **Model**: 2,102,213 parameters. Untrained, single thread on 05 over a real live game: featurize + network +
  decode p50 4.9 ms, p95 6.1 ms.
- **12:15: v0 store and shakedown.** v0 store (pre-review, f0540f3e): 16,916 matches, 3.60M rows, 847,827 admitted
  plays (79.7% of 1,063,202 executed plays). BC v0 epoch 0 on 08 (4.5k rows/s, 12.5 GB VRAM), DEV:
  - joint NLL 0.350 against the frequency baseline's 0.408; Hog 0.477 against 0.553;
  - card top-1 51%, tile top-1 17%, tile within-one 34%;
  - gate ECE 0.003, plays ratio 1.07;
  - **Hog value NLL 3.05**: a few hundred oversampled Hog games' outcomes were memorised. The value loss is now
    importance-corrected (DECISIONS 23).

  v0 is superseded and was stopped.
- **12:20: Sol R1 = NO-GO** (`scratch/pretrain-v1-dev/review/SOL-R1.md`).
  - Blockers: opening-hand ambiguity, uncertain continuations, Mirror legality, split fingerprint ignoring the
    rotation.
  - Should-fix: live eligibility (tick-90 start, deciding record, stale tower, expiry), opponent cast counts.

  Fixed in f3f11f807 (`RESPONSE-R1.md`). #2 is handled per the coordinator's data rule plus an `unc` flag, recorded
  as a disagreement in DECISIONS 14.

  The stronger suffix mutation (it rewrites future source commands too) exposed a second-order leak: admission
  criteria had been gating `History.submit`. The channel is now emulated only from facts observable at d*. The audit
  is back to 0 violations, and 21 unit tests pass.
- **CPU latency** (05 Threadripper, untrained, batch 1, 20,000 polls of real live records):
  - 1 thread: p50 4.9 ms, p95 6.0 ms, p99 6.8 ms; dense p95 5.9 ms; cold 8.3 ms;
  - 4 threads: p95 4.8 ms, p99 5.2 ms.

  The featurizer is 0.17 ms of that. The Mac measurement is pending (no Mac access in this task).
- **Eval hooks built.**
  - (a) `sim_rsim.py` + `eval_rsim.py`: a RoyaleSim producer through the same FrameBuilder; the policy arm on the
    r2 paired bank (HOG26-acct, account levels) is paired against r2's sealed live-search (f1a2) rows. Smoke with an
    untrained model: 2 games, 42 commands, 0 rejections.
  - (b) `probe_roots.py`: the 453 defense groups and 957 spell opportunities, replayed through `observe` on the frozen
    c17/c18 recordings.
- **RL design** written ([RL-DESIGN.md](RL-DESIGN.md)); not launched.
- **12:35:** Sol R2 (re-review of pieces 1+2) and R3 (model / trainer / eval / RL design) requested in parallel.
  The v1 store `f-e2869e6dbb77-b-dafd672b` is being built (36 acked batches).
- **12:40: Sol R2 = NO-GO** (illegal fallback submissions; producer-specific rejection timing) and **Sol R3 = NO-GO**
  for pieces 3–5 (RoyaleSim carrier id collision; eval dropping failed pairs; row- vs game-sampling; value metrics
  and G1 evidence; resume mixing; probe id reuse and gate cadence; RL KL cadence; stale benchmark). All accepted and
  fixed in 579bd1fe9 (`RESPONSE-R2.md`, `RESPONSE-R3.md`).
  - There is now **one record-derived channel rule** for every producer: a submitted card still in hand 45 ticks
    later means rejected.
  - Carrier instances are matched by flight-age continuity.
  - BC sampling is game-balanced with a water-filled exposure cap of 5 draws per row per pass. The realised Hog
    share is 12% against the requested 50%. This is set by the cap and the ~2% Hog row fraction, not by corpus size
    (DECISIONS 25).
  - New `admit_bc.py` (G1 report with physical-game cluster bootstrap).
  - `eval_rsim` keeps all cases, with ITT bounds and a PCG64 bootstrap.
  - RoyaleSim shadow check: logged-frame replay == serving features, 1,581/1,581 polls.

  24 unit tests pass. Sol R4 (combined re-review) requested.
- **12:52: v2 store** `f-93bc7eae8dd9-b-1005dbb4` (37 batches):
  - 18,415 usable matches (18,500 attempted), 36,828 perspectives, **3,717,470 rows**;
  - **776,321 admitted plays** (67.5% of 1,149,419 executed). Rejections: hand-ambiguous 12.2%, unaffordable 12.0%,
    channel busy 7.2%;
  - 796 Hog 2.6 perspectives (650 train / 74 dev / 72 final), exact-Zap 0, vanilla 68;
  - value labels on 17,968 perspectives;
  - per target card: all eight Hog 2.6 cards have ≥ 9,000 admitted plays (PREREG floor 1,000).

  The Hog-cycle perspective floor (1,000) is **not yet met** (796); it grows with the corpus.
- **12:55:** BC v2 started: 3 registered seeds in parallel on the 08 A6000 (about 36 GB VRAM). The 210-match parity
  audit plus all live records is re-running on 05.
- **CPU latency, current bytes** (`bench-cpu-05-untrained-93bc7eae.json`, 2,102,597 parameters, batch 1, 20,000 live
  polls on 05):
  - 1 thread: p50 5.2 ms, p95 6.3 ms, p99 6.8 ms; dense p95 6.2 ms; cold 7.1 ms;
  - 4 threads: p95 4.6 ms, p99 5.0 ms.

  The older f0540f3e result is kept as HISTORICAL.
- **13:00: Sol R4: pieces 1+2 GO-WITH-FIXES, pieces 3–5 NO-GO.**
  - Blocker: eval accounting (unrun cases dropped from ITT; mixed point/bootstrap weights).
  - Should-fix: provenance enforcement; revealed-card recency (a feature bug); probe denominators; duplicate-donor
    balancing; G1 must drive selection; current parity evidence.

  Fixed in 946b15b31:
  - `select_bc.py` for registered anchor selection;
  - donor-level sampler;
  - frozen-assignment eval accounting (fixture check passes);
  - probe coverage.

  The feature fix forced a third store rebuild (`f-ce6e509ee43a-b-1005dbb4`) and a BC restart; the v2 seeds ran for
  10 minutes only. Sol R5 requested.
- **13:08: v3 store** `f-ce6e509ee43a-b-1005dbb4` (39 batches):
  - 19,410 matches, 38,820 perspectives, **3,902,495 rows**;
  - **811,369 admitted plays** (67.5% of 1,202,829);
  - 842 Hog 2.6 perspectives (687 train / 81 dev / 74 final), value labels on 18,896 perspectives.
- **13:10–13:22, incident on 08:** the first BC v3 launch command appeared to fail, but it had started; a relaunch
  doubled it to 6 processes writing the same run directories (GPU 47.6/48.7 GB, MemAvailable down to 30.8 GB, above
  the 28 GiB floor). All 6 were killed; the GPU went back to 104 MiB and 63.5 GB available. The seeds were relaunched
  once from `jobs/clasher/pretrain-v1/launch_bc_v3.sh`, which refuses to start if any pretrain-v1 BC is already
  running. Exactly 3 seeds are now running (about 7.6 GB RSS each). RL processes were not touched.
- **13:25: Sol R5: pieces 1+2 GO-WITH-FIXES, pieces 3–5 NO-GO** (blocker: `select_bc` crashed on a duplicate
  `gate_bias` argument; should-fix: external eval provenance, partial probe windows). Fixed in 42000b149:
  - the selector smoke run completes;
  - eval freezes external identities and the controls' runtime pins;
  - a fixture plus a negative check pass;
  - an end-to-end 2-case eval smoke is complete and valid, with 810/810 shadow-equal polls.

  Sol R6 requested.
- **BC v3 sampler** (seed 1 `run.json`): 31,008 donors (76 duplicate copies merged), 676 Hog donors, realised Hog
  share 12.7%, max row exposure 5.0. 6,102 steps per pass, about 28 min per pass at 1.86k rows/s per seed with
  three seeds sharing the A6000.

## Retrain plan as the corpus completes

The re-drive runs at about 2.2k matches/h, with an ETA of about Oct 25 23:00 PDT for all 252,238. The store grows
in place: `python -m bot.pretrain_v1.dataset build` appends newly acked batches to the same
`f-<feature>-b-<builder>` store, taking about 5 min per 40 batches with 32 workers on 05. It refuses a store with
another feature hash, and `rsync` then copies the store to 08.

| Retrain | Trigger | Corpus | Purpose |
|---|---|---|---|
| R-a | about Oct 22 evening | about 60k matches, about 2.7k Hog perspectives (≥ 1,000 floor) | First run past the Hog-perspective floor; 3 seeds, unchanged hyperparameters, then `select_bc` and the G1 report |
| R-b | corpus complete (about Oct 26) | 252k matches, about 50M rows | Registered BC anchor for RL; same contract |

Notes:
- Each retrain starts from random initialisation (DESIGN). Selection always runs through `select_bc`.
- **Cost:** about 50M rows per pass at about 1.9k rows/s per seed with 3 parallel seeds is about 7.5 h per pass, and
  up to 60 GPU-h per seed for 8 passes, inside the 64 GPU-h per-seed cap. Two measured speed-ups are worth
  registering first: bf16 autocast and a vectorised ragged gather.
- **Hog share** stays about 12% under the exposure cap of 5 (DECISIONS 25). Reaching 50/50 needs a coordinator
  decision.
- If the featurizer or builder changes, the store is rebuilt from scratch (new hash). The rebuild costs about 1.5 h
  of 05 CPU for the full corpus.
- **Prerequisite for R-b (Sol R7):** `train_bc.Store` loads fixed arrays eagerly, at about 383 B per row: about
  19 GB per process at 50M rows, and over 35 GB during construction. Before the full-corpus run:
  - map fixed columns and offsets per shard and gather only batch rows;
  - use cumulative shard boundaries instead of row maps;
  - stream pass index and weight preparation, with RNG-equivalence checked;
  - chunk the calibration reductions.

  The R-a corpus (about 60k matches, about 13M rows) fits the current design (about 5 GB of arrays per process).
- **13:30: Sol R6 = GO-WITH-FIXES for both scopes.**
  - Pieces 3–5: eval provenance must follow the actual imports. Fixed in 52d38caea: the RoyaleSim module actually
    imported (`scratch/barrelgoblin-fix-20261020-stageA3/test-deps/royalesim`) plus r2 code-tree and runtime-joint
    Python, 3,836 files, rechecked in every worker.
  - Pieces 1+2: current-byte parity evidence. Delivered in `parity.json` (ce6e509ee43a / 1005dbb4):
    - **209 matches / 418 perspectives:** 335,385 polls serving == builder; 335,385 private-mutation and 162,213
      decision-time suffix-mutation cases; **0 violations**;
    - **all 556,523 live records** (867 files) pass the allow-list with 0 errors;
    - live vs re-drive feature means: units per poll 4.39 / 4.18; unknown body or card 0 / 0; motion matched 96% /
      97%; elixir held 4.16 / 5.77 (our bot holds less than the pros); towers down 0.78 / 0.22.
- **13:35: landed on main.** Fresh worktree `clasher-pv1-land`, `--no-ff` merge of `pretrain-v1/featurizer`, 25/25
  tests, pushed as **83e02341a** (`28de76513..83e02341a`). The change is purely additive: 32 files under
  `bot/pretrain_v1/` and `reports/bot/pretrain-v1/`. The BC code running on 08 is byte-identical to main.
- **13:45, incident: BC memory growth on 08.** The trainer's prefetch list kept every consumed batch future until
  the end of the pass, about 1.2 MB per step per seed. By step 5,000 each seed held 12.2 GB RSS and 08 MemAvailable
  was 31 GB, approaching the 28 GiB floor; RL actors were not yet affected. All three seeds were stopped
  deliberately before the guard fired. The fix drops each future once consumed (commit on the branch, pending a
  Sol check before main). The three seeds restarted at 13:47 from scratch.
- **13:55: Sol R7 GO-WITH-FIXES on the memory fix.** Batch order and numerics are unchanged, and it is approved for
  the current store. The full-corpus memory changes are listed as the R-b prerequisite. The fix lands on main.
- **14:16: BC v3, pass 0 complete on all three seeds** (capped-DEV logs, uncalibrated): joint NLL 0.376 on every
  seed (baseline 0.444); Hog 0.495–0.498 (baseline 0.594); card top-1 53–54%; tile within-one 33–34%; ECE
  0.003–0.007; value accuracy about 70%.
- **14:35: interim anchor** (`select_bc` over the pass-0 checkpoints, full DEV, gate intercept fitted): all three
  seeds eligible; selected seed 2026102003 (tie on broad NLL broken by Hog NLL), sha 425fdb33…, gate bias +0.147.
  Full-DEV G1 (1,887 physical games, 244,125 actor rows, 79,072 plays; PCG64 10,000-draw physical-game bootstrap):

  | Metric | Model | Baseline | Δ (95% CI) |
  |---|---|---|---|
  | Joint NLL, broad | 0.3753 | 0.4442 | −0.0689 [−0.0701, −0.0677] |
  | Joint NLL, Hog-cycle (78 games) | 0.4942 | 0.5939 | −0.0997 [−0.1081, −0.0915] |
  | Gate ECE | 0.0037 | | |
  | Gate Brier | 0.0409 | 0.0436 | |
  | Plays ratio | 1.00 (Hog 0.99) | | |

  Card top-1 is 53.9% (Hog 57.4%). Tile top-1 is 16.7% and tile within-one 33.4% (Hog 36.2%).

  Per target card, DEV plays / card top-1 / tile within-one:

  | Card | Plays | Card top-1 | Tile within-one |
  |---|---:|---:|---:|
  | Skeletons | 5,010 | 0.60 | 0.23 |
  | Musketeer | 927 | 0.61 | 0.29 |
  | IceGolem | 1,164 | 0.82 | 0.27 |
  | Cannon | 1,672 | 0.33 | 0.62 |
  | Fireball | 1,265 | 0.16 | 0.31 |
  | Zap | 1,581 | 0.43 | 0.29 |
  | IceSpirit | 1,820 | 0.73 | 0.24 |
  | HogRider | 1,554 | 0.74 | 0.58 |

  G1 items 1 and 2 (ECE / Brier / ratio) pass. The hazard-inversion part of item 2 is not testable on this store, so
  admission is **partial**.

  Interim evaluation started on 05: eval (a) on all 400 HOG26-acct r2 cases, and the probe roots.
- **14:30–14:55: interim probe roots** (interim anchor; diagnostics on the search's recorded trajectories,
  `scratch/pretrain-v1-dev/probe-interim-ep00.json`).
  - **Defense**, 442 of 453 groups observed (9 partial, 2 without a root): P(play at the root poll) 0.10;
    P(any play within 60 ticks) 0.47.
    - "Awake/affordable unresolved" (169 groups, where the live search played nothing): window play probability
      0.45.
    - Goblin Barrel (127 groups): window 0.30, and P(Zap/Fireball at root) only 0.009. The BC policy barely spells
      Barrels.
  - **Spell opportunities**, 954 of 957 observed: P(that spell at root) 0.02; tile mass within 1.5 tiles of the
    audit's best target 0.13.
- **14:55, eval (a) interim run 1 INVALID.** `eval_rsim.main()` imported `bot.pretrain_v1` before forking, so the
  workers' whole `bot` package (R3a/K4CW opponents and harness modules) came from origin/main, not r2's frozen code
  tree. A case-218 traceback exposed it. The run (Δ about −0.77) is kept under `INVALID-…` and is not reported as a
  result.
  - Fix (5848502a5): the feature hash comes from a standalone `featurize.py` load; `bot` must be unimported at fork;
    workers assert that every harness/opponent module resolves inside r2 and record the origins.
  - The 400-case rerun is in progress. Sol R8 has been requested.
- **14:40: Sol R8 = NO-GO.** Appending this repo's `bot` directory to `bot.__path__` let r2's K4CW start path lazily
  import `bot.cyclemodel` from this repo. The `wrap` it imported is a no-op with `BOT_CYCLE_MODEL` unset, but it is
  still a provenance violation. Run v2 was stopped at 75/400 and kept as `INVALID-…`.
  - Fix (c3a81b261): only `bot.pretrain_v1` is registered, by an explicit package spec, and every loaded
    `bot.*` module is scanned before and after every game.
  - **Sol R9 = GO-WITH-FIXES:** persist complete origins and validate them at resume and summary. Done in f90b5fd0a,
    with fixture negatives for tampered and incomplete origins.
- **14:45: interim eval v3 interrupted** at 97/400 when the agent session was interrupted (its processes were
  children of the tool shell); it is superseded. v4 was relaunched under `setsid`. BC on 08 was unaffected.
- **BC pass 1** (capped DEV): joint NLL 0.363–0.366 (pass 0: 0.376), Hog 0.482–0.484, card top-1 56%, tile
  within-one 37–38%.
- **15:00: interim eval (a), valid run v4** (interim pass-0 anchor 425fdb33; r2 HOG26-acct row, account levels,
  RoyaleSim 16.402; `scratch/pretrain-v1-dev/eval-interim-ep00-v4/summary-pv1.json`).
  - 400/400 cases assigned and run. 0 invalid, 0 provenance-invalid, 265,028/265,028 polls shadow-equal, 32.4 plays
    per game.
  - Candidate failures: 14. Thirteen are games interrupted by a T3 server restart and retained as infrastructure
    failures per PREREG; one is case 218, an R3a opponent cycle-tracker error that r2's control also hit.
  - Complete pairs (386): policy 0.111 vs K4CW (search 0.920) and 0.171 vs R3a (search 0.904). **Δ = −0.771,
    95% [−0.813, −0.727]**, 97.5% [−0.818, −0.721]. ITT bounds [−0.780, −0.743].
  - In short, the pass-0 BC policy alone is far below the live search at account levels, in line with r1's direct
    HP1 swap (−0.63 to −0.80). Pure imitation is not expected to beat search; RL is the stage meant to close this.
  - Jobs on 05 now start via `ssh` to 05's LAN IP. That keeps them outside the T3 process tree, so a T3 restart (it
    killed the first v4 launch and a `setsid` job) cannot take them down.
- **Value-head overfitting (BC v3, pass 1).** DEV value NLL rose from 0.60–0.65 to 1.15–1.30, and Hog from 0.56–0.57
  to 1.07–1.31. Value accuracy held near 0.68, so the head has become overconfident: it memorises per-game outcomes,
  because every row of a game shares one W/D/L label and rows recur every pass.
  - The actor objective, which drives selection, keeps improving: joint NLL 0.376 → 0.364.
  - The value head is not used at decision time. DESIGN re-warms it for 3 updates before PPO, so it does not block BC.
  - **Fix for the next retrain:** value loss on a per-game subsample (a fixed number of rows per perspective per
    pass), plus value-head selection by DEV value NLL (or early stopping), reported separately from the actor
    anchor.

- **BC v3 passes 0–3** (capped DEV, per seed). Broad joint NLL 0.376 → 0.366 → 0.360 → 0.355–0.359 (still falling).
  **Hog-cycle NLL bottoms at pass 1–2** (0.482–0.484) and rises to 0.506–0.518 by pass 3. Value NLL climbs every pass
  (0.6 → 1.8–2.2).
  - The 687 Hog training donors are seen up to 5× per pass under the exposure cap and are being memorised. The broad
    corpus is not yet.
  - The registered rule (lowest broad NLL, Hog only as a tie-break) will therefore pick a late pass with worse Hog
    NLL. `select_bc` reports both, and the G1 Hog interval still has to exclude 0.
  - This is a direct data-limit signal for the target deck. The scaling read and the growing corpus address it, and
    a coordinator-registered Hog-aware early stop could too.

## Model-size sweep (coordinator request, 15:30)

The request came via the coordinator from Sam. The question is whether a bigger model plays better within the M4
Pro latency budget. The sweep must not disrupt the running BC seeds or the v4 eval; the v4 eval had already
finished.

### Design

All runs use the same v3 store and split, seed 2026102001 for the new runs, and the R7 memory fix.

| Name | d / layers / heads / FFN | Parameters | LR | Weight decay | Dropout | Precision |
|---|---|---:|---|---|---|---|
| S (registered) | 192 / 4 / 6 / 576 | 2,102,597 | 3e-4 | 1e-4 | 0 | fp32 |
| M | 320 / 6 / 8 / 1280 | 8,756,421 | 2e-4 | 0.01 | 0.1 | bf16 autocast |
| L | 512 / 8 / 8 / 2048 | 28,179,013 | 1.5e-4 | 0.01 | 0.1 | bf16 autocast |

Every size uses one warm-up pass then cosine decay, at most 8 passes, and patience 2.
- **Data-scaling read:** S on 25%, 50% and 100% of the train donors. The subsets are nested and come from a fixed
  permutation of donors, with DEV fixed. Each run gets the same total step budget, so 25% runs 32 short passes and is
  evaluated every 4.
- **Selection per run:** `select_bc` (gate intercept fitted on DEV, full-DEV G1 admission: joint NLL vs the baseline
  with a physical-game cluster CI, card and tile accuracy, gate ECE and Brier, plays ratio, and now value NLL, Brier
  and accuracy).
- **Game evaluation per size:** the same 400-case r2 HOG26-acct eval vs the live search, and paired size-vs-size
  comparisons (`compare_arms.py`).
- **Rule:** prefer a bigger size only if it wins on games, not just on loss.
- **Scheduling:** 08's GPU only (04 stays RL). The three S seeds hold 44 of 48.7 GB, and an M smoke inside the
  remaining headroom OOM'd its own capped process, harmlessly. So the sweep waits for the S seeds and their
  selection, measures each size's peak with a solo smoke, and launches whenever peak × 1.5 fits (each process is
  capped with `PV1_GPU_FRACTION`, MemAvailable ≥ 40 GiB, load < 85). Drivers:
  - `sweep/sweep_08.py` on 08, detached;
  - `sweep/sweep_05.sh` on 05, started via LAN ssh so a T3 restart cannot kill it.

### Latency on the real target (random weights: network cost per size; checkpoint qualification pending)

Measured with `bench_device.py`: batch 1, one decision end to end (featurize, collate, device transfer, network,
masks, sampled gate/slot/tile), 3,000 timed polls of real live records after 200 warmup.

**Caveat (Sol R10 #6):** the weights were random. That isolates each size's network cost, but random weights change
how often the tile branch runs. The selected checkpoints will be re-measured through the exact serving path
(`bench_device --session`: `policy.Session.step` with the value head, survival gate and accepted-command history)
under recorded load. The runs were sequential under changing load, so cross-size differences are approximate.

Mac mini M4 Pro (8P + 4E cores, 24 GB), torch 2.10 in the existing `~/clasher-live/venv`, files only under
`~/clasher-pretrain-bench/`. The Mac was **under shared load**: the re-drive, Sam's UTM VM and a dev server were
running, load average 13 → 33 across the runs, memory pressure high (358 MB free, 10 GB compressed). The live bot
was paused, and nothing else was touched.

| Size | CPU 1 thread p50 / p95 / p99 | CPU 4 threads p50 / p95 | MPS p50 / p95 | Cold (CPU 1) |
|---|---|---|---|---|
| S | 1.9 / 7.3 / 13.2 ms | 2.5 / 9.6 ms | 21.8 / 54.1 ms | 4 ms |
| M | 4.0 / 11.5 / 21.3 ms | 5.1 / 18.6 ms | 20.6 / 54.8 ms | 8 ms |
| L | 9.2 / 17.6 / 40.4 ms | 13.9 / 44.7 ms | 28.2 / 64.2 ms | 11 ms |

- **All three sizes meet p95 ≤ 30 ms on one CPU thread.** L's p99 (40 ms) is within PREREG's 50 ms.
- Four threads are slower under this shared load, and MPS is dominated by per-call dispatch overhead at batch 1.
  Serving should use CPU with 1 thread.
- CoreML/ANE was not tried.
- The featurizer is 0.12–0.17 ms of every decision.

### RL actor cost (provisional extrapolation; 127x05 Threadripper 3990X, the same CPU as RL hosts 04/08; 1 thread per actor)

| Size | 1 thread p50 / p95 | 4 threads p50 / p95 | Policy CPU per game* |
|---|---|---|---|
| S | 4.7 / 5.5 ms | 3.7 / 4.1 ms | ~5 s |
| M | 14.2 / 17.1 ms | 8.0 / 9.2 ms | ~16 s |
| L | 39.3 / 47.6 ms | 17.8 / 21.1 ms | ~45 s |

\* About 700 polls per seat-game × 1.65 expected policy seats per game. The 30% self-play, 20% reservoir and 15% BC
anchor league slots all use our own model, giving 1 + 0.65 = 1.65 seats.

For scale:
- engine stepping is about 7 s per game;
- HP1's actors averaged about 58 CPU-s per game;
- the RL CPU envelope (14,000 h for 3 × 200k games) is about 84 CPU-s per game.

These are wall-time extrapolations from batch-1 latency, not measured actor CPU-seconds or throughput. Provisionally:
L alone would take over half the per-game envelope and roughly halve games per hour, M adds about 20–30%, and S is
negligible. Actor and learner soak measurements are needed before RL budgeting. The learner GPU also scales: an L PPO update over about 0.5M polls × 2 epochs is roughly 10× an S update,
to be measured from the sweep's bf16 training throughput.

### Sol R10 (sweep review) = NO-GO; fixes

- **GPU protection (blockers 1–2).** Every sweep GPU phase (smoke training, smoke selection, training, selection)
  now has a per-process allocator cap and is admitted only when

  device total − external usage − Σ (cap + context) of our running phases − 4 GiB headroom ≥ cap + context.

  External usage is every non-sweep GPU process, measured per PID. Caps are 1.5 × peaks from solo smokes of the
  *complete* workflow (training, DEV evaluation at batch 1024, calibration at 2048, `select_bc` at 2048), which must
  exit cleanly. The smokes start only once the GPU has no other process. `select_bc` honours the cap and records its
  peak. The first driver was stopped before it launched anything (it was still waiting for the S seeds).
- **Arm comparison (blocker 4).** `compare_arms.py` now:
  - reuses `eval_rsim`'s validators (manifests must agree on bank, assignment, runtime pins and external identity;
    every row is checked against its case, and its origins if it claims validity);
  - takes strata from the assignment and reports each arm's failures plus all-assigned bounds.

  Self-comparison of v4: Δ 0.000 over 386 complete pairs, all-assigned bounds ±0.035. A mixed-provenance comparison
  is refused.
- **Pre-declared game rule.** A bigger size wins iff (1) the complete-pair 95% lower bound of Δ(big − small) is > 0
  and (2) the all-assigned lower-bound point estimate is > 0. Otherwise the smaller size stays.
- **Scaling schedule.** S50 and S25 use the same 6,102 warm-up steps as S100. Evaluations come about every 6.1k steps
  and step budgets match within 0.4%.
- **Other fixes:**
  - the admission value NLL now uses exact log-softmax;
  - `bench_device --session` times the serving path;
  - the RL cost is marked provisional.
