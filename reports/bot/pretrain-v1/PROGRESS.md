# pretrain-v1 progress log

**Current scope, including Sam's 2026-10-22 amendments:** S100 versus M, 25/50/100% data scaling for both
sizes, the 41,328-match retrains, and outcome RL for both sizes after qualification.
L is cancelled by decision. Earlier L plans and smoke results below are retained as history.

New single-model Clash Royale policy. Input: the live memory record plus causal history. Output: gate / slot /
tile / value, with the gate sampled. There is no decision-time search. Design:
`/mpac/sdicks02/scratch/new-pretrain-20261020/{DESIGN,PREREG-DRAFT,INVENTORY,FIDELITY}.md`. Engineering choices:
[DECISIONS.md](DECISIONS.md). Code: `bot/pretrain_v1/`. Data: `/mpac/sdicks02/datasets/pretrain-v1/` on 127x05
(snapshot inputs are hash-verified on their assigned training hosts).

Constraints in force:
- Owned GPUs 01/02/08 are authorized; current retrains are M on 01 and S100 on 02. 08 finished the scaling runs.
- HP1 processes on 04/08 are untouched. 07 is CPU-only, at most 32 processes and nice >=10.
- Leased hosts are only 09/12/17, through 2026-10-25T07:53Z or reclaim. R37 watcher GO is complete;
  dedicated watchers are live on all three hosts, with no workload admitted. Their process/PSS/GPU/nice limits and allowed write roots apply.
  Hosts 13-16 belong to the search/defense/spell eval owner; 11/18 are excluded.
- Hosts keep MemAvailable above 28 GiB and load at or below 90.
- Mac access is limited to the approved benchmarks under `~/clasher-pretrain-bench/`. No live changes or deployment.
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
- **Sol R11 = NO-GO** (telemetry failed open; ownership by command text; no single-driver lock; compare_arms not
  re-hashing the bank or external identity) → fixed in 12ff883aa. **Sol R12 = GO-WITH-FIXES**: the sweep may
  proceed; harden malformed telemetry before merging the driver. Done:
  - pure parsers reject negative, non-finite, non-numeric or duplicate rows and an implausible device total, turning
    them into fail-closed `Telemetry`;
  - focused checks in `sweep/check_sweep_telemetry.py`.

  The driver on 08 was swapped for the hardened version while it was still waiting for the S seeds.

### 16:45 recovery on Sol high

- The three registered S seeds remain on 08, at pass 5 and about 36,000 steps. The selection finalizer,
  single locked sweep driver, and both 05 evaluation waiters are alive. No compute was restarted. At recovery,
  08 had 47 GiB MemAvailable and load 76. The driver hash matches the reviewed version on origin/main.
- The frozen sweep still uses the 19,410-match v3 snapshot with 3,902,495 rows and 811,369 admitted plays.
  The source collection has since reached 25,000 sealed attempts. That growth will enter a later retrain.
- The exact serving benchmark previously supported CPU only. The pending R13 change moves Session tensors to
  the model's device and copies sampled probabilities to CPU before NumPy decoding. This permits the same
  Session.step, value head, survival gate, masks and accepted-command history on MPS. CPU arithmetic is unchanged.
- Selected-checkpoint benchmarks will use 20,000 timed polls after 200 warmup, rather than the earlier 3,000-poll
  random-weight measurements. They record checkpoint SHA256, shared load and latency for the densest decile
  within the sampled records. A short input corpus fails instead of producing a qualification result.
- Training and game-evaluation code directories remain pinned while these measurements are prepared in a new
  worktree. No size recommendation, RL launch or deployment has been made.
- R13 review found a stale-result reuse bug, lexical path containment and raw-row counting before duplicate-tick
  filtering. These are fixed for R14 review. The selected runner now refuses every existing output directory,
  validates each fresh result against the requested checkpoint and measurement settings, resolves symlinks and
  traversal before writing, and counts monotonic polls consistently. Session results publish by atomic rename.
  Checkpoint identity hashes the exact bytes loaded. CPU parity passed on 1,000 real polls; the short MPS smoke
  completed, but its latency is not a qualification result.
- **Sol R14 = GO.** The reviewed Session/measurement fixes pass 30 tests with one MPS skip. Full selected-model
  Mac qualification is still pending. A dedicated `sweep/bench_wait_05.py` is being reviewed separately. It will
  own only Mac measurements, distinct from the registered selection/evaluation waiters. Admission requires an
  explicit GO receipt for its exact code commit and matching staged-record hashes, then each local
  `sweep/anchors/{S100,M,L}/selection.json` and its checkpoint SHA256. The owner holds a global 05 lock, checks
  existing Mac benchmark processes without changing them, and runs CPU1/CPU4/MPS sequentially. The Mac runner
  also holds a global file lock. No measurement owner has been launched at this entry.
- **Sol R15 = NO-GO** for the dedicated owner at b7fdd2116. Fixes for fresh R16 review require a nonempty review
  with explicit exact-revision GO metadata, bind every consumed record file and byte to a frozen manifest, and
  retain corpus and runtime hashes in each result and completed attempt. Missing, added or changed records are
  refused before each measurement. Existing staging trees, archive members and checkpoint destinations receive
  physical-path checks before writes. The read-only process guard now also covers the `bench_cpu` module form.
  No Mac measurement owner has been launched while these changes await review.
- **Sol R16 = NO-GO** solely for a symlinked shared Mac lock. All R15 fixes passed the independent probes.
  The lock now opens with `O_NOFOLLOW`, uses nonblocking open for safe file-type validation, and must be a regular
  file before flock. Regression checks reject both a dangling outside symlink without creating its target and
  a FIFO without blocking. Fresh R17 review gates landing and owner launch.


### 17:09 dedicated Mac qualification owner admitted

- **Sol R17 = GO** for exact commit `75a3be7d2818b7ae90cf9513b8a164888fecdfd9`, now on origin/main.
  The final suite passed 34 tests with one MPS skip. R17 also passed seven independent lock checks.
- Exactly one dedicated measurement waiter is running on 05: Python PID **1902088**, supervised by timeout PID
  **1902079**, detached through LAN SSH with the fleet key. It runs independently of the agent turn, with a
  48-hour outer bound. The two existing 05 selection/evaluation waiters and the locked 08 sweep remain unchanged.
- Immediately before launch, the local process audit found no benchmark waiter and the Mac process audit found
  no benchmark job. The owner's own Mac process guard passed too. It has completed staging and verified the
  exact runtime and all 36 record files. Its current state is **waiting for S100 selection**, with no selected
  checkpoint measurement started yet.
- The immutable code checkout is `/mpac/sdicks02/repos/clasher-pv1-sol-bench-20261021` at the reviewed commit.
  Admission uses `sweep/mac-qualification/go.json`, containing the hashed R17 report, exact revision, source
  runtime identity and frozen corpus identity. Corpus SHA256 is
  `0c1b52af43c431e18d30416fcf6bd988c57e97351c11838fc1bfbd36ee65c028`.
- Gates for each size are `sweep/anchors/{S100,M,L}/selection.json`, a matching selected checkpoint SHA256,
  unchanged runtime/corpus identities and no existing Mac benchmark job. The Python waiter holds a global 05
  lock; each Mac selected runner holds a global Mac lock. Existing incomplete attempts fail closed. Completed
  attempts are reused only after full identity and count validation.
- All local paths above beginning `sweep/` resolve under `/mpac/sdicks02/scratch/pretrain-v1-dev/`.
  Owner metadata, logs, receipt and returned results are under `sweep/mac-qualification/`:
  `owner.json`, `owner.out`, `waiter.log`, `go.json`, then `{S100,M,L}/{attempt.json,cpu-t1.json,cpu-t4.json,mps-t1.json}`.
  Mac files are confined to
  `~/clasher-pretrain-bench/qualification-75a3be7d2818b7ae90cf9513b8a164888fecdfd9/`, with archived `code/`,
  `records.json`, selected checkpoints and one result directory per size/checkpoint SHA. Real input records remain
  under `~/clasher-pretrain-bench/records-session/`.
- Each size runs CPU1, CPU4 and MPS1 sequentially, with 20,000 timed decisions after 200 warmup through the same
  production Session. Results retain checkpoint, corpus, source runtime and feature hashes, dense-scene latency,
  cold start and shared host load. No model choice, outcome-RL launch or deployment is authorized by a result.
- The three registered S seeds have finished naturally. The original 08 finalizer is running full-DEV selection;
  the original sweep driver is waiting. All selected-model latency results remain pending.

To resume the dedicated waiter after inspecting any failure, use the same command. The lock refuses duplicate
owners, validated completed attempts are recovered, and incomplete attempts require inspection:

```sh
python3 -B -u /mpac/sdicks02/repos/clasher-pv1-sol-bench-20261021/reports/bot/pretrain-v1/sweep/bench_wait_05.py \
  --code /mpac/sdicks02/repos/clasher-pv1-sol-bench-20261021 \
  --revision 75a3be7d2818b7ae90cf9513b8a164888fecdfd9 \
  --go /mpac/sdicks02/scratch/pretrain-v1-dev/sweep/mac-qualification/go.json \
  --out /mpac/sdicks02/scratch/pretrain-v1-dev/sweep/mac-qualification
```

### 19:14 Canvasdoc shared-load amendment

Sam reports the `canvasdoc` Colima VM is running tests alongside replay emulators. It must remain untouched.
Every further Mac qualification records the VM's host CPU/RSS and is labeled shared-load. Passing the unchanged
30 ms p95 and 50 ms p99 limits under this load is a conservative pass. A cleaner rerun is preferred when its
work is idle; the replay emulators remain part of the host load.

- S100 completed at 17:54, before the currently observed Canvasdoc VM and hostagent started at 18:55:39. Its
  selected checkpoint is `e9366c55503f3d826fa6add0beb9880883be9274158e728f03f932dcd19acbc7`. Over 20,000 timed
  Session decisions, p95/p99 were CPU1 1.77/2.05 ms, CPU4 3.81/12.17 ms and MPS1 22.74/46.22 ms. These results
  retain their original shared-host-load record and lack Canvasdoc telemetry. They are historical measurements
  and do not establish a clean-host number or CPU/RSS for an earlier Canvasdoc instance.
- The old measurement owner PID 1902088 was idle waiting for M, and no Mac benchmark was running. Only that owned
  idle waiter was stopped to prevent another uninstrumented measurement. Training, selection, game evaluation,
  replay, the VM and Docker were not changed. No replacement owner is running pending review.
- New `bench_load.py` reads host `ps` CPU/RSS at roughly two-second intervals outside timed decisions, including
  initial/final snapshots. It attributes the generic Apple VM process by its open `colima-canvasdoc` disk/EFI
  files using read-only `lsof`, and includes Colima services and descendants. Guest Docker work is inside the VM
  host process accounting. It retains per-PID CPU/RSS, totals, UTC samples, peaks and attribution completeness.
- A live read-only probe observed hostagent PID 86994 and VM PID 87024 with 1.7–7.8% aggregate CPU and peak
  1,456,656 KiB RSS. Telemetry was complete. No workload or VM control command was issued.
- Missing attribution or failed telemetry cannot qualify a result. Every measurement is labeled `shared-load`;
  its budget status explicitly says pass/fail under shared load. Source identity includes the telemetry module,
  and completed-result reuse requires the new complete telemetry. Older measurements are preserved separately.
- `bench_wait_05 --idle-rerun` adds a second set of S/M/L measurements after the shared-load set. Before each idle
  rerun, Canvasdoc CPU must remain at or below 5% of one logical core for 60 seconds of read-only observations.
  The result reports whether that low CPU condition also held in the sampled measurement window. This is an
  observed idle condition, not a claim about the guest test scheduler or a fully quiet host. Both phases retain
  the shared-load label and are stored separately. No VM process is signaled, paused or reconfigured.
- Fresh R18 review gates landing and the replacement owner. The suite passes 41 tests with one MPS skip.

### 19:27 Canvasdoc-aware owner admitted

- **Sol R18 = GO** for exact revision `56e25ded1c0bf7b2e85aa2036feb7fde66775760`, landed on origin/main through a
  fresh worktree. Independent validation passed 41 tests with one MPS skip and the mocked timing, telemetry,
  phase/recovery and lock probes. The immutable runtime checkout is
  `/mpac/sdicks02/repos/clasher-pv1-canvasdoc-bench-20261021`.
- Exactly one replacement measurement owner is running: Python PID **635370**, timeout parent **635361**, detached
  through LAN SSH with a 48-hour bound. The old owner and its timeout parent have exited. Fresh local and Mac
  duplicate checks passed before launch, and the owner's own revision, source/corpus and process gates passed.
  At 19:27:33 it started the selected S100 checkpoint's shared-load rerun. No result is asserted until returned
  artifacts validate.
- The owner uses `--idle-rerun`. It completes S100/M/L shared-load measurements first, then a separately stored
  Canvasdoc-idle phase with the documented 60-second low-CPU gate. Every result retains its actual VM CPU/RSS
  samples and shared-load label. Budget failure is recorded as failure under that load; incomplete attribution
  cannot qualify. An idle condition that changes during a run is visible in its sampled `idle_observed` field.
- Local receipt, metadata, logs and results are in
  `/mpac/sdicks02/scratch/pretrain-v1-dev/sweep/mac-qualification-canvasdoc/`, with `go.json`, `owner.json`,
  `owner.out`, `waiter.log` and `{shared-load,canvasdoc-idle}/{S100,M,L}/` result directories. The previous
  `mac-qualification/S100/` artifacts remain unchanged.
- Mac artifacts are confined to
  `~/clasher-pretrain-bench/qualification-56e25ded1c0bf7b2e85aa2036feb7fde66775760/`.
  Result directories include phase, size and checkpoint SHA; their `cpu-t1.json`, `cpu-t4.json` and `mps-t1.json`
  contain complete Canvasdoc samples, latency percentiles, source/corpus/checkpoint hashes and budget status.
- Source training, selection/evaluation waiters, the 08 sweep driver, Canvasdoc, guest Docker and replay services
  continue unchanged. The only replaced process was our idle measurement waiter. No model choice or deployment
  was made.

The replacement command, to use only after inspecting failures and confirming its owner has exited, is:

```sh
python3 -B -u /mpac/sdicks02/repos/clasher-pv1-canvasdoc-bench-20261021/reports/bot/pretrain-v1/sweep/bench_wait_05.py \\
  --code /mpac/sdicks02/repos/clasher-pv1-canvasdoc-bench-20261021 \\
  --revision 56e25ded1c0bf7b2e85aa2036feb7fde66775760 \\
  --go /mpac/sdicks02/scratch/pretrain-v1-dev/sweep/mac-qualification-canvasdoc/go.json \\
  --out /mpac/sdicks02/scratch/pretrain-v1-dev/sweep/mac-qualification-canvasdoc --idle-rerun
```
- **First instrumented result, S100 CPU1:** 20,000 decisions passed the budget under shared load: p95 2.101 ms,
  p99 2.417 ms. Canvasdoc telemetry was complete across 18 snapshots, the VM was present, and aggregate peak
  Canvasdoc CPU/RSS was 4.7% of one logical core / 1,439,392 KiB. This run met the observed low-CPU condition but
  retains `pass-under-shared-load` and `clean_result=false`. The CPU1 artifact is preserved locally as
  `mac-qualification-canvasdoc/partial-S100-cpu-t1.json`; completion of CPU4/MPS and the full S100 result set is
  still pending. This does not select a model size.

### 23:18 Canvasdoc workload closed; ready idle measurements

- Sam reports Canvasdoc's workload closed at 06:18Z on Oct 22, with its hostagent at 0% CPU and 64% free memory.
  Replay emulators remain running and are part of realistic serving load. The qualification condition is now
  **Canvasdoc workload idle with replay emulators active**. Host VM background CPU/RSS continues to be recorded;
  a brief VM housekeeping spike is not evidence that guest tests restarted.
- S100 and M are selected. Their previous instrumented shared-load CPU1 p95/p99 were 2.10/2.42 ms and 8.70/19.70 ms.
  M's CPU4 p95/p99 was 16.53/46.68 ms. All passed the CPU budget while Canvasdoc was busy. MPS for M failed under
  that load at 36.41/80.75 ms. The per-run Canvasdoc CPU/RSS samples remain with each artifact.
- The automatic measurement owner was idle awaiting L, so its phase order held the ready S/M idle reruns behind L.
  Only that idle owner was stopped. A bounded ready-measurement launcher, shell PID **2085528** with timeout parent
  **2085519**, now holds the same global 05 lock and runs S100 then M through the unchanged R18-reviewed
  `bench_selected` runner. No model/decoder/training setting changed. Fresh Mac duplicate checks found no benchmark
  before launch. CPU1/CPU4/MPS remain sequential, each with 20,000 decisions plus 200 warmup.
- Sam's workload-idle confirmation is stored at `mac-qualification-canvasdoc/canvasdoc-idle-user-context.json` and
  copied alongside each returned idle attempt. Results preserve the actual sampled `idle_observed` value and
  shared-load classification because emulators remain active. A clean Canvasdoc-workload comparison is not a
  claim that all host background CPU disappeared.
- The temporary launcher is `mac-qualification-canvasdoc/run_ready_idle.sh`, detached over LAN SSH with a five-hour
  outer bound. Its state/logs are `ready-idle-owner.json`, `ready-idle-owner.out` and `ready-idle-{S100,M}.log`.
  Results use the already registered `canvasdoc-idle/{S100,M}/` locations and checkpoint/corpus/runtime validation.
  It then restores the unchanged R18 waiter, which will validate/reuse completed idle attempts without rerunning
  them. The temporary outer bound also limits that restored waiter's remaining lifetime; inspect/relaunch after
  expiry if L remains pending. Training, game evaluation and Mac services were not interrupted.
- **L admission blocker discovered during this check:** L has never launched. Its solo smoke reserved
  33.0605 GiB. The reviewed 1.5× allocator cap is 49.5908 GiB, before the 0.7 GiB context allowance, while an empty
  GPU's admission budget is only 43.5 GiB. Consequently the locked driver waits forever even with an idle GPU.
  S/M/scaling jobs have completed, and 08 currently has no GPU process. The protection rule has been preserved.
  L needs a reviewed execution-memory adjustment before its run can proceed; no capacity choice, protection
  relaxation or training-configuration change was made in this turn.
- First ready idle-run results for S100 passed: CPU1 p95/p99 3.053/6.220 ms and CPU4 6.069/12.809 ms, each over
  20,000 decisions. Canvasdoc telemetry was complete. Actual VM background peaks were 8.2% and 23.6% of one core,
  respectively, so the strict sampled `idle_observed` flag is false; Sam's workload-closed confirmation remains
  separately attached. These remain valid passes under replay/shared load, not a fabricated low-CPU telemetry
  pass. MPS for S100 and all M idle-profile runs are pending at this update.


### 23:28 L cancelled by Sam decision

This supersedes the instruction to make L fit. M, at 8,756,421 parameters, is the upper size. The capacity
comparison is S100 versus M, with the same registered game evaluation and bigger-model decision rule. The
S25/S50/S100 data-scaling read remains part of the sweep.

- L is **cancelled by decision, not failed**. No full L training, fitting-code change, gradient-accumulation review
  or L checkpoint selection was launched. The historical L smoke and initial random-weight latency artifacts
  remain preserved and do not constitute a trained L result. An unused clean worktree was created while the
  fitting instruction was active; no fitting implementation was written there.
- Verified and stopped exactly the idle 08 sweep driver PID **2198244** and the idle 05 game-evaluation waiter
  PID **1514991**, both waiting for L. S/M game evaluations were already complete. No training or evaluation
  worker was interrupted. Cancellation receipts are `bc-sweep/cancelled-L.json` on 08 and
  `/mpac/sdicks02/scratch/pretrain-v1-dev/sweep/cancelled-L.json` on 05.
- Active driver, game-comparison and benchmark templates now contain only S/M and the existing scaling runs.
  The S/M Mac idle-profile measurements continue through the reviewed R18 runner. Any automatic restoration
  of the old L-waiting owner will be retired cleanly after those measurements finish. The updated S/M owner
  will validate/reuse completed artifacts, with no duplicate benchmarking.
- Fresh Sol R19 review covers only this scope reduction. Model/trainer settings, data/split, optimizer schedule,
  memory guards, decoder, checkpoint selection, game estimand and latency budgets are unchanged.

### 23:38 R19 GO landed; S/M evidence and cancellation ownership

- Sol R19 is GO for exact revision `0252406dbe59b2aed9a8ce5945e5760231bdc873`.
  It landed on main unchanged through a fresh worktree. Review: `/mpac/sdicks02/scratch/pretrain-v1-dev/review/SOL-R19.md`.
- Rechecked 08: no full L run directory, training process or GPU process. Both cancelled idle PIDs are absent.
  The cancellation receipts preserve the historical smoke as history and mark L `cancelled-by-decision`.
- The 400-case paired game comparison completed. M minus S100 is +3.009 percentage points over 399 complete
  pairs, 95% CI [-2.999, +9.023]. The all-assigned conservative estimate is +2.75 points, CI [-3.25, +8.75].
  `a_wins_by_registered_rule=false`: the complete-pair lower confidence limit is not above zero.
  This evidence does not support preferring M under the registered rule. No model choice or deployment was made.
  Artifact: `/mpac/sdicks02/scratch/pretrain-v1-dev/sweep/compare-M-vs-S100.json`.
- Against the sealed current search control, S100 is -45.60 points, CI [-50.87, -40.57], and M is -42.60 points,
  CI [-47.86, -37.57]. Each arm ran all 400 assigned cases, with one candidate failure and 399 complete pairs.
  No invalid actions or provenance violations were reported. Both BC-only policies remain well below search.

The fixed v3 snapshot contains 19,410 matches, 3,902,495 rows and 811,369 admitted plays. All rows below use
seed 2026102001 and the same held-out match split. These are selected DEV metrics, not a new independent test.

| Run | Broad NLL | Hog NLL | Card top-1 | Tile within one | Gate ECE | Value Brier |
|---|---:|---:|---:|---:|---:|---:|
| S25 | 0.3842 | 0.5146 | 51.51% | 31.88% | 0.0028 | 0.5977 |
| S50 | 0.3710 | 0.5076 | 55.65% | 36.00% | 0.0058 | 0.6085 |
| S100 | 0.3582 | 0.5096 | 57.99% | 40.08% | 0.0063 | 0.5610 |
| M | 0.3478 | 0.5239 | 60.14% | 43.94% | 0.0064 | 0.5883 |

Broad imitation improves with each data fraction, so more data still helps that objective. Hog NLL does not
improve monotonically. M improves broad NLL and action accuracy but worsens Hog NLL and value Brier versus S100.
The data-scaling read therefore supports continued corpus growth without establishing a larger-model game win.

- Mac owner shell PID **2085528**, timeout parent **2085519**, remains on the S100 idle-profile MPS measurement.
  M follows sequentially; no benchmark was duplicated. The R18 production Session and telemetry code are unchanged.
  Shared-load results already complete: S100 p95 CPU1/CPU4/MPS = 2.10/3.44/18.85 ms; M = 8.70/16.53/36.41 ms.
  M passes CPU and fails MPS under that shared load. Idle-profile S100 CPU1/CPU4 passed at 3.053/6.069 ms;
  its MPS and the M idle-profile measurements are pending. Actual Canvasdoc CPU/RSS remains recorded.
- Exact cancellation guard PID **3494057** replaces guard PID 3133684, which was stopped after checking its argv.
  Its five-hour bound now matches the measurement launcher. It waits for validated S/M idle results and retires
  only the exact restored old R18 waiter, identified by revision, argv and parent PID. It cannot signal a Mac
  benchmark or training process. State: `mac-qualification-canvasdoc/retirement-guard.json`; completion receipt:
  `mac-qualification-canvasdoc/retired-L-waiter.json`. No old benchmark waiter is currently running.
- The earlier Threadripper RL-cost extrapolation remains provisional: S about 5 seconds of policy work per game
  versus M about 16 seconds under the stated seat/poll assumption. No outcome-RL launch or new cost experiment
  was performed. L cost estimates above are historical only.


## 2026-10-22

### 00:04 registered BC follow-ups running; both-size RL added

- Sam clarified that M's +3.01-point interval [-3.00, +9.02] is inconclusive. **S100 remains the default**, not an
  assertion that M lost. The registered game rule is unchanged. L stays cancelled by decision.
- [FOLLOWUP-PREREG.md](FOLLOWUP-PREREG.md) was committed as `802cba9ad` before generating follow-up banks or
  starting M fraction training. Fresh-bank code received Sol R21 GO at `36c60c43562b22e2642787d376048221254914db`.
  R20 found an inherited opponent-mix override; the generator now pins the original mixture before import.
- Two banks were frozen before follow-up training. Each has 1,600 cases, 800 per controller, 400 per seat/controller,
  drawn with the original mix, levels, exclusions and deck shuffling. Both are mutually disjoint and disjoint from
  all 1,200 original cases. Fixed horizon, no interim decision, no pooling the original 400 into the new decision.
  Bank directory: `/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022/`.
  - `power-v3-bank.json`, SHA `f8a21c0e9a92b8f5fffffaf4b76d517092ee3f123a4eb9eac06604cc79a0b552`.
  - `next-snapshot-bank.json`, SHA `10c24cd429416344d6ee69342bc6317a2c90387bb73a97eb38c9dbf4cf30a276`.
- Sol R22 found orphan-phase relaunch and partial READY publication hazards. Both were fixed and independently
  verified. Sol R23 GO covers exact `93baf3a5bcff9670a0b8ddbcf437638172e84fbd`, landed on main. Six targeted tests
  passed. Intent files precede GPU spawn and refuse unreceipted restarts; READY gates publish atomically after
  complete transfer/hash verification. No failed owner was restarted into a surviving workload.
- **08 GPU owner PID 1327095**, code `/mpac/sdicks02/repos/pretrain-v1-followup-93baf3a5b`, launched at 06:59:07Z.
  First phase M50 is running, guard PID 1327129 / trainer PID 1327130. Its effective batch, optimizer, AMP,
  nested donor subset and 6,102-step warmup match the registration. At step 1,000 it used 9.67 GiB reserved and
  processed about 3,466 rows/s. Queue: M50/select, M25/select, then the larger-snapshot S100/select and M100/select.
  Every GPU phase uses the unchanged measured-peak admission and host guard. Outputs and `owner.json`, `active.json`,
  `intent-*.json`, `completed-*.json`, logs are under `/mpac/sdicks02/jobs/clasher/pretrain-v1/followup-20261022/`.
- **05 game owner PID 2013400**, external guard PID 2013392, runs 24 one-thread workers on the v3 S100 bank first,
  then M; it will compare the arms after all assignments. The same owner waits for next-snapshot selections and
  runs their second fresh bank. Output root is the bank directory above; `games-owner.json`, `launch-05.json`,
  `games-owner.log`, `power-v3/`, `next-snapshot/`, and `comparison-{power-v3,next-snapshot}.json` retain ownership,
  all rows and readouts. At this update 49 S100 rows were sealed; no interim strength claim is made.
- **05 snapshot owner PID 2013395**, external guard PID 2013388, freezes the first 83 acknowledged batches under
  `/mpac/sdicks02/datasets/pretrain-v1/snapshot-20261022-b083/`. It reuses 39 immutable v3 shards, copies the manifest
  separately, and builds 44 new shards with eight workers. `input.json` pins receipt hashes. The 08 consumer cannot
  start next-snapshot training until the transferred store passes all file hashes and an atomic `STORE-READY.json`.
- Initial guards are healthy: 05 MemAvailable about 101 GiB / load 34; 08 about 55 GiB / load 72. No 04 process or
  HP1 allocation was touched. The direct self-SSH launch on 05 failed authentication before execution; the actual
  05 launch used the established 08-to-05 LAN hop. There was no duplicate launch.
- Available S data-scaling sample sizes are 784,048 / 1,565,207 / 3,124,681 train rows and 7,752 / 15,504 / 31,008
  train donors for 25% / 50% / 100%; all use the same 379,752 DEV rows. Their broad NLL is 0.3842 / 0.3710 / 0.3582.
  M100 uses the same 3,124,681 train rows and 31,008 donors; M50 is on the matching 1,565,207 rows / 15,504 donors.
  M25/M50 selected metrics are pending. The background reporter exposed a legacy S100 run receipt without the
  explicit `train_donors` field. A standalone reader fix uses its existing sampler donor count; Sol R25 review is
  pending. This reporting error did not interrupt training, building or games. Target artifact is `scaling-read.json`.
- Mac qualification is complete. Idle-profile p95/p99 milliseconds, each over 20,000 timed Session decisions:
  S100 CPU1 3.053/6.220, CPU4 6.069/12.809, MPS 52.639/81.536; M CPU1 15.955/26.395,
  CPU4 9.764/26.039, MPS 34.368/42.270. Both sizes pass CPU and fail MPS against the 30 ms p95 budget.
  The artifacts preserve actual Canvasdoc CPU/RSS, Sam's workload-idle confirmation and replay/shared-load labels;
  the host is not claimed to have no background load. All attempts passed identity/count/completion validation.
  Guard 3494057 retired exactly the restored obsolete L waiter PID 659970 at 06:47:35Z. No benchmark waiter remains.
- Sam now authorizes outcome RL for **both S100 and M**, independently of the BC size selection.
  [RL-DUAL-PREREG.md](RL-DUAL-PREREG.md) records matched seeds, 32 updates x 262,144 environment poll steps per seed,
  terminal-only PPO, each size's human BC anchor, real levels, the calibrated 3bf68f929 actor-amendment lineage,
  fresh final banks, own-BC and cross-size comparisons, snapshots, KL and defense/spell diagnostics, and collapse
  rules. Learners remain on 08 only after BC/eval release. Actor throughput is measured on free 05/08 capacity
  before reporting any requested HP1 CPU share; HP1's allocation cannot be taken without Sam's decision.
- Sol R24 gave **component-only GO**, exact `9ade4b3643c97e1b6aa2cb124f423ac2176e734c`, for the RL registration and
  exact joint-policy PPO/KL/GAE math. Four CPU tests and independent probes passed, including full-distribution
  enumeration, forced no-op, nonterminal chunk bootstrap, and microbatch gradient equivalence. Landed component
  commits are `83195356e` and `6673ae8c9`. This is not a launch GO: the calibrated-engine record producer, rollout
  harness, parity/mutation/level/soak checks, actual actor throughput and final launch-config review remain required.
  No RL actor, learner, resource handoff or deployment has started.


### 00:39 snapshot ready; scaling reader fixed; engine producer in review

- Sol R25 GO covers reader revision `b3e99412d61b2a37fa0e72a138b58b2744c4d499`, landed as `c5512b84f`.
  Standalone 05 scaling reader PID **2614081**, guard **2614076**, runs from its immutable reviewed worktree.
  It publishes `followup-20261022/scaling-read.json` every 120 seconds while M25/M50 are pending, then exits once
  all six selections are available. Four existing runs are now published with metrics and sample sizes.
  The old CODE93 embedded reader still fails on the immutable legacy S100 receipt and cannot overwrite the report.
  Its game owner is untouched; after both game comparisons complete, inspect/retire its final idle reader join.
- The 83-batch larger snapshot is fully built, transferred and hash-verified: **41,328 usable matches and
  8,143,577 rows**, versus v3's 19,410 matches and 3,902,495 rows. Both hosts have atomic `STORE-READY.json`.
  Manifest SHA `f52562891584db3dffef6c45ced1106a41b712456e67a1cd87ccc084b23dc59a`.
  It is frozen and will not follow later re-drive syncs. The existing 08 owner consumes it after M fraction
  training/selection. No new GPU owner or duplicate training job was launched.
- Both-size RL producer draft is committed at `e2c877b3cdef7415eb1c6c4a6ee9e10fb1b29fe3`, pending Sol R26 review.
  It projects our calibrated engine's own HUD and public entities through the unchanged live FrameBuilder,
  featurizer and production Session. Read-only logits capture records the actual sampled probability without
  another forward pass or a serving-code change. Forced/no-op and stale/cadence handling are explicit.
- Copied the exact approved joint actor/runtime lineage into independent 05 directories
  `/mpac/sdicks02/repos/pretrain-v1-rl-{runtime,actors}-0dcab45f7-joint/`. Verified all **9,409 runtime and 17,010
  actor-source** file hashes. Original HP1 files/processes remain untouched. The checker bootstraps Runtime before
  any engine classes and verifies imported module origins, preventing a mixture with the active editable checkout.
- Initial local inspection used engine imports before Runtime, producing an incompatible-class exporter error.
  Bootstrap order and explicit root selection were corrected. Producer qualification attempt 01 then caught
  ordinary tower attack projectiles carrying tower stats and being treated as crown towers; classification now
  requires an actual building entity. The failed attempt and traceback remain preserved.
- Qualification attempt 02 passed **496/496 byte-parity and 496/496 private-state mutation checks**, covering all
  eight Hog cards at real levels and King9 in both perspectives. Attempt 03 repeated those checks and added one
  full S100 readiness game against R3a on the exact real-level Hog deck. It reached a true terminal state at tick
  6001: **1,182 traced decisions, 78 submitted/executed commands, zero rejections**, all shadow features equal and
  sampled log probabilities finite. It took 35.93 wall / 35.52 CPU seconds after runtime construction. This one
  game is a readiness smoke, not an estimate of strength or the registered league's games/hour.
- Six local component tests passed, including prevention of enemy-player-object reads, dead-tower handling,
  unknown identity refusal, tower projectile regression, unchanged Session actions/features, and learner-versus-
  captured action log probabilities within 2e-6. Proofs are under `scratch/pretrain-v1-dev/rl-readiness/`.
  R26 is a component review only. Streaming rollouts, step/version accounting, PPO learner, complete opponent
  pool, matched actor-throughput measurement, audits/soak and final launch review remain open. RL is not launched.

### 01:00 compute expansion authorized; M games remain the critical path

- Sam authorizes full use of 01 and 02, light CPU work on 07, and leased 09/12/17 through
  2026-10-25T07:53Z. Hosts 13–16 belong to the separate frozen search/defense/spell evaluation owner;
  pretrain will not use them. No 11/18 use. HP1 on 04/08 remains untouched.
- Planned GPU allocation is 01 M25 then next-snapshot M, 02 next-snapshot S100, with the already running
  M50 on 08 preserved. A reviewed handoff must prevent the old 08 owner from launching reallocated pending
  phases before either new owner starts them. Training seeds, data splits, effective batches, optimizer
  settings and selection remain the registered experiment. Inputs on each local NVMe require hash verification.
- The M power-bank evaluator has 358/1,600 sealed cases at 07:55:49Z, plus 24 active attempts. Median sealed
  game time is 58.26 seconds. Existing workers use static assignments and cannot safely overlap another launcher.
  Expansion source `8ca6f6d7d980062950fbb5b9c36fcfb3bc767054` passed four local tests and is in fresh Sol R27 review.
  It drains each active game before retiring its exact worker PID, keeps the legacy parent waiting, and shares
  unchanged cases among 64 workers on 05 with exclusive per-case locks. No case or started attempt is retried.
  Conditional ETA after reviewed handoff is 25–40 minutes; the original 24 workers continue during review.
- 01/02 staging and pending-phase ownership implementation are delegated to Sol high. Leased-host staging and
  reclaim/resource supervision are a separate Sol high implementation. Neither has launched unreviewed compute.
  Reclaim watchers are not yet live. Before leased-host jobs launch they must poll their lease at most every
  60 seconds, respect process/PSS caps, nice >=10, leave 8 GB GPU free, and checkpoint/exit within 30 minutes
  of reclaim before marking the lease ended. Only approved clasher repo/job paths may receive their files.
- Leased CPU allocation will prioritize game evaluations, then both-size RL actors. 09/17 allow 96 total clasher
  processes each, 12 allows 64, all with 64 GB summed PSS caps; host load remains <=90 and MemAvailable >28 GiB.
  07 permits at most 32 processes at nice >=10, no GPU. RL learners will use 01/02 and, as needed, the leased
  GPUs after the final launch GO. The two BC sizes remain mandatory; S100 remains the default size selection.
- Sol R26 gave component-only GO for `e2c877b3cdef7415eb1c6c4a6ee9e10fb1b29fe3`, landed as `3f57c213e`.
  Six tests and all frozen runtime/source hashes passed. Its documented dormant fallback root-tag limitation
  fails closed and must be covered or excluded before admitting a reachable new path. No PPO launch GO exists.

### 01:06 M worker expansion live

- R27 rejected `8ca6f6d7d` for a marker disappearing while another worker seals. The scan now ignores only
  FileNotFoundError, with a targeted concurrent-disappearance regression; malformed markers still fail closed.
  Fresh Sol R28 GO is exact `56ef1c94bd0cb370f414bed7c3dfd3a0e96db137`, five tests passed.
  Landed commits `d4f296e42` and `faf05d3b1`. No live processes were touched before that GO.
- Expansion guard PID **66600**, owner **66607**, launched 08:02:06Z from the exact reviewed worktree.
  All 24 old workers completed their active attempts before retiring. Drain sealed count was 538 with no
  attempt markers left. The replacement 64-worker pool started 08:03:44Z; at 08:05:22Z it had 64 active games,
  load 56 and 87 GiB available memory. Exact legacy parent **1946894** remains stopped until all assigned
  rows validate, then resumes the existing game owner for the registered paired comparison. Its waiting state
  is deliberate. No case or started game was discarded or rerun.
- Owner/claim/drain/completion receipts live in `followup-20261022/power-v3/eval-M/expansion-*`;
  logs and launch receipt are `followup-20261022/power-v3-M-expansion*`. An incomplete pool intent blocks
  automatic restart. Existing source/runtime/bank/checkpoint and manifest remain immutable.
- M calibrated-engine readiness attempt `rl-readiness/producer-M-04.json` passed 496 feature-parity checks,
  496 private-state mutation checks, eight real-level deployments and one true terminal game: 702 polls,
  37 submitted/executed commands, zero rejections, finite captured log probabilities, 27.57 seconds.
  This is 25.46 polls/s versus the earlier S100 smoke's 32.90 polls/s. Different game lengths prevent treating
  this as matched league games/hour or strength evidence; full league throughput is still required before RL.

### 01:21 larger-snapshot trainers live; leased-host guard rejected

- R29 GO covers exact allocation revision `962244600d0d3b025901d05dc81e7d2fc1bc39d8`, landed `de4afd681`.
  Eleven tests passed. The resource-only split is now **01 next-M100, 02 next-S100, unchanged 08 M50 then M25**.
  This starts the slower larger model immediately while all three owned GPUs work. Exclusive next-phase intents
  on 08 were reserved at 08:11:03Z; durable central claims arbitrate launches. M50/M25 intents were not reserved.
- The first 01/02 owners failed preflight before any claim or training because copied builder-provenance files
  were outside the consumed-data inventory. Preserved those 88 files per host under
  `followup-20261022/allocation-0102/builder-provenance/`, with original paths and SHA256 receipts. No consumed
  array, manifest, READY receipt, source or controller changed. Reverification passed all 3,176 / 2,160 data
  inventory entries and 68 source entries. The failed owner logs and launch receipts remain preserved.
- Second owners **889015 on 01** and **1271721 on 02** launched 08:13:12Z. Both trainers are running.
  Next-M reports 4,414 rows/s, next-S100 5,309 rows/s; GPU use about 80% / 77%, with roughly 35 GiB free on each.
  The snapshot has 6,498,432 train rows, 65,840 train donors and 803,577 DEV rows; training's fixed DEV cap is
  400,000, while selection uses its registered full DEV population. Same seed, batch, warmup and size-specific
  optimizer settings are recorded in each run.json. 01/02 use matching torch 2.7.1+cu118 environments.
- Provisional ETAs from these first intervals: next selections around 12–14Z; the complete M25/M50 scaling
  read around 11:30–12:30Z. Early stopping and full-DEV selection can shift those estimates. Existing 05 readers
  still consume the atomically published selection bundles at their original 08 paths. No duplicate phase starts.
- 07 now runs the existing frozen `probe_roots.py` for the selected S100 and M checkpoints. Guards **1259137**
  and **1259138**, children **1259139** and **1259141**, started 08:09:22Z, nice >=10, CPU only, four torch threads
  each. All 472 staged source/checkpoint/audit/recording files were SHA256 checked. Paths and receipts are under
  `/mpac/sdicks02/repos/clasher-pretrain-audit-20261022/`. These are recorded-state diagnostics, not new game
  outcomes or counterfactual defense claims. They stay well below the 32-process limit and use the usual guard.
- M power eval at 08:20:39Z: **1,207/1,600 sealed**, 64 active, load 69. Six frozen-opponent own-cycle exceptions
  remain sealed failures; no retries or bank/code changes. They will enter the registered conservative accounting.
- R30 is **NO-GO** for leased supervisor `dcb19e0023b0081028875e44bb87d291e1281476` due live-process ownership,
  boot identity, tightened deadlines, actual polling cadence, path containment and lease-lock protocol defects.
  No watcher or job has launched on 09/12/17. Fresh runtime/actor/R2 archives are SHA256 verified there, but not
  extracted into runnable mirrors. A dedicated fix task is active; fresh independent GO precedes watcher startup.
- Approved PPO learner and bounded streaming actor components are being implemented in separate Sol high tasks.
  Both require independent review and full integration/throughput/soak checks. There is no RL launch GO or firm
  launch ETA. No HP1 process, host 13–16 allocation, model selection, strategy or deployment was changed.

### 01:30 power comparison complete; M meets the registered rule

- All 1,600 cases per arm are sealed. There are 1,592 valid pairs and eight retained failures on identical R3a
  case IDs in both arms. No retry or exclusion from assigned-case bounds. The 64-worker expansion finished
  08:27:42Z and resumed the legacy parent; its unchanged owner produced `comparison-power-v3.json`.
- M minus S100 is **+3.2506 percentage points**, paired 95% CI **[+0.1590, +6.2677]**. The conservative
  all-assigned lower point is **+2.75 points**, CI [-0.3141, +5.8125]. This passes the registered rule, which
  requires positive complete-pair lower CI and positive conservative point. The conservative CI itself need not
  exclude zero under that rule. The earlier 400-case result is not pooled or relabeled a loss.
- Against LIVE-K4CW-r16-fp, M wins 373/800 (46.625%) versus S100 322/800 (40.25%). Against R3a, M wins
  392/792 versus S100 391/792. There are no draws among valid games. Recommendation: M under the registered
  rule, with both sizes meeting the Mac CPU budget. Sam's size decision is still pending; no default or deployment
  was changed. [POWER-READOUT.md](POWER-READOUT.md) records full sample sizes, failures, latency and hashes.
- A direct coordinator-thread steer was refused because that thread had no running turn. No message was queued.
  The result is recorded here and in this implementation thread for the coordinator to collect.
- M50 training on 08 finished early with best epoch 5 and is now in full-DEV selection. M25 remains next in its
  original queue. 01 next-M100 and 02 next-S100 continue. The larger snapshot's game bank is already frozen.
- Lease fixes are committed at `873ca1f6a37b0abc251d5b69e10860feeea2bfc1`, passing 32 tests plus 14 subtests,
  three repeated suite runs and 175 race checks. Fresh independent R31 review is pending. Watchers remain
  unlaunched until GO. RL learner and streaming actor implementation tasks continue without workload launches.

### 02:06 lease protocol amendment and streaming integration checks

- Sam superseded R33's cooperative-editor assumption. RoadForge may atomically replace, truncate or
  rewrite its lease file without locks. The watcher amendment reopens the path on every poll, latches any
  parsed `reclaim: true` or `refused: true` before schema checks, and retries missing/unreadable/partial files
  until more than five continuous minutes have elapsed. Known expiry bounds still apply during retries.
  Clasher records its own drained receipt without modifying RoadForge's file. Fresh independent review is
  required for this amendment. No watcher or workload has launched on 09/12/17.
- Learner component `fca861bcf7b9ce1d46eb02ccbecf02d7c9a31090` and streaming actor component
  `5a39be5fc3fca1fe7745a4b3af0c6e5ce9950de3` each received independent Sol high component GO.
  They landed through `d677ed716`. Component review does not authorize a PPO training launch.
- CPU integration checks using immutable `d677ed716` and the hash-verified calibrated runtime passed for
  both selected v3 checkpoints. Actor chunks were written to the atomic NPY queue, reopened as read-only
  mmap arrays, converted to the learner's Chunk type and structurally validated. S100 published 1,183 rows;
  M published 703. Each counted one value-only deadline row, discarded zero rows, rejected zero commands,
  and reproduced its earlier production command SHA exactly. Same-weight version changes at quota
  boundaries preserved the game trajectory. Artifacts are `rl-readiness/stream-{S100,M}-01.json` under
  `/mpac/sdicks02/scratch/pretrain-v1-dev/`. These are one-game integration checks, not league throughput,
  GPU likelihood parity, an RL improvement result, or a launch qualification.
- M50 selection is complete and admitted; M25 is running on 08 in the original owner queue. Next-M100 on
  01 and next-S100 on 02 have reached epoch 2. Measured training rates remain about 4,374 and 5,214 rows/s.
  Next selections remain provisionally 12–14Z, with final time depending on early stopping and full-DEV
  selection. The scaling read has five of six points; M25 is the only pending point.
- Both frozen recorded-state audits on 07 are complete and copied with SHA256 receipts to
  `/mpac/sdicks02/scratch/pretrain-v1-dev/audit-20261022/`. Each covers 108 recordings and 442 observed
  defense roots. S100/M play probability at the root is 0.15194/0.17050 and within the recorded window
  0.52035/0.53228; spell probability at the root is 0.01682/0.02540. These conditional recorded-state
  diagnostics do not establish counterfactual defense success or game strength.

### 02:23 R34 rejected; scaling read published with five points

- R34 is NO-GO for `b822690aa1e52001ef2016d0591a97cf96994702`. Independent probes reproduced
  a stale emergency record overwriting a concurrent new admission, an overflowing JSON integer blocking
  even latched reclaim enforcement, and deeply nested partial JSON causing early emergency draining.
  A dedicated fix task owns these reproductions and their regressions. Fresh R35 review will precede
  landing or operational actions. No leased watcher, extraction or workload is running on 09/12/17.
- [DATA-SCALING-READOUT.md](DATA-SCALING-READOUT.md) publishes all five admitted points and exact sample
  sizes now. M25 remains the only missing point; its original 08 trainer reached epoch 11. Next-M100 on
  01 reached epoch 2, next-S100 on 02 epoch 3. No queue, effective batch, schedule or split was changed.
- A new isolated implementation task is integrating the reviewed actor/queue and learner contracts into
  an exact-quota coordinator component. It may add code and local tests only. Full engine continuation,
  transport, GPU numerical parity, resource admission, league throughput, soak and integrated launch
  review remain required. No RL training has started.

### 02:39 R34 fixes ready for R35

- Lease fixes are committed at `d1b566e8ecae89e3f10fc98bd36c52fa41a1d77e`. Local validation passed
  74 tests plus 107 subtests on Python 3.12, all 74 tests on Python 3.8, and the R34 reproductions,
  adapted R33 recovery cases and added admission/parser regressions. Fresh independent Sol high R35
  review is running. The no-launch gate remains: no watcher or workload on 09/12/17 until explicit GO.
- Existing training continues unchanged: M25 reached epoch 15 on 08, next-M100 epoch 3 on 01 and
  next-S100 epoch 3 on 02. Original owners, claims and runtime remain in place.

### 02:52 R35 rejected; cached recovery fixes and numerical qualification in progress

- R35 is NO-GO at `d1b566e8ecae89e3f10fc98bd36c52fa41a1d77e`. New combined-failure probes show
  token-only recovery can still be delayed by external lease reads, recovery deadlines can be lost across
  simultaneous own-lock contention and restart, and repeated truncating stop-file writes can corrupt a
  checkpointer's notification. A dedicated fix task is addressing all three. R36 remains the next independent
  review gate. No watcher, extraction or workload has launched on 09/12/17.
- M25 training finished with best training-DEV epoch 7 and is in full-DEV checkpoint selection. Next-M100
  on 01 and next-S100 on 02 continue unchanged. Final M25 admission and the six-point scaling read are pending.
- Retained a second CPU integration pass's real actor chunks for S100 and M, including Session old likelihoods
  and values, unchanged quota boundaries, runtime manifests and per-array SHA256 receipts. Both games passed
  their original command hashes, exact row counts and terminal checks. A CPU numerical measurement is running
  against the reviewed learner baseline at batches 1/128/256. Exact inputs and minimal source were SHA256
  verified and staged under `repos/clasher-pv1-rl-numerics-d677ed716` and
  `jobs/clasher/pretrain-v1/rl-numerics-v3` on 08. No GPU numerical job has started; M25 selection has priority.
  The registered `2e-6` absolute likelihood/value gate is unchanged. No optimizer update is performed.

### 02:55 all six data-scaling points complete; strict numerical gate fails

- M25 selected epoch 7, admitted checkpoint `8e78eae361b849645c2954a35257a4f9c600f8360b532796008dfd3b51dc0516`.
  The standalone reader has atomically published all six points and finished. M25/M50/M100 broad NLL
  is 0.377329/0.364624/0.347816 and Hog NLL 0.574733/0.564444/0.523859. M's value Brier is
  0.645109/0.614383/0.588279. [DATA-SCALING-READOUT.md](DATA-SCALING-READOUT.md) now contains the
  full read and sample sizes. Fractions use 784,048 / 1,565,207 / 3,124,681 train rows and the same
  379,752 DEV rows across 1,887 physical matches, including 78 Hog matches. More data improves both
  sizes' broad imitation metrics; this one-seed result does not establish data as the sole limit.
- 08 has released BC/selection compute. Numerical measurement against retained production Session chunks
  fails the unchanged `2e-6` limit on 05 CPU already. At microbatch 128, S100 has max log-probability/value
  errors 5.653e-6/7.838e-6 across 1,183 rows; M has 3.985e-6/4.202e-6 across 703 rows. Batch 1 and 256
  also fail. Evidence: `rl-readiness/numerics-cpu05.json`. No PPO optimizer update occurred.
- Ranked diagnosis checks are padding changes during chunk collation, fused attention kernels, and the
  05/08 PyTorch version difference. Identical retained inputs and selected anchors are SHA-verified on 08.
  CPU and GPU baseline measurements are running there under the existing guard after selection released
  the GPU. The first GPU measurement attempt failed before inference due to a supplied anchor directory;
  its log is preserved, paths were corrected, and the second attempt has a distinct output/log. No threshold,
  model, optimizer semantics or deployment changed. Numerical qualification is an explicit RL launch block.

### 03:01 coordinator component landed; numerical blocker isolated further

- Fresh independent Sol high review gives component GO at coordinator source
  `7a1ade83957753d13a3db73552fcbf5fe003b935`. Reviewer passed 149 tests and extra finalization probes.
  The five reviewed source commits landed through `5f73b819a`; all three resulting files match the reviewed
  blobs exactly. Actor/learner source remains unchanged. This is not an integrated harness or RL launch GO.
- [NUMERICAL-QUALIFICATION.md](NUMERICAL-QUALIFICATION.md) records the failed strict CPU/GPU measurements,
  source/input identities and minimized one-row padding reproduction. The direct coordinator steer was
  refused because that thread had no running turn; nothing was queued. No threshold or strategy was changed.
- Matching-version actor recapture is running on 05 in an isolated SHA-verified PyTorch 2.7.1 environment.
  Existing environments and running trainers remain unchanged. R35 lease fixes continue separately;
  no watcher, extraction or workload is running on 09/12/17.

### 03:06 matching-version numerical control still fails

- Actual CPU Session recapture under SHA-verified PyTorch 2.7.1+cu118 reproduces identical public feature
  arrays and command hashes for both sizes. CPU05 and GPU08 baselines still exceed `2e-6` at microbatch 128.
  GPU max log-probability/value errors are 4.977e-6/1.073e-5 for S100 and 8.802e-6/7.212e-6 for M.
  Framework version alone is not the cause. Detailed measurements and input hashes are in
  [NUMERICAL-QUALIFICATION.md](NUMERICAL-QUALIFICATION.md). No numerical setting was adopted or gate relaxed.
- A measurement-only explicit attention math-backend probe is in progress; it uses retained states and
  recomputed reference likelihoods, so it cannot by itself qualify production actor sampling. R35 lease
  fixes continue. No leased watchers, extra BC runs, PPO training or deployments have started.

### 10:12Z R36 review and completed attention-kernel probe

- R35 fixes are committed at `86d3f20cda886a0516edc05326a845399eba1345`. Both Python versions passed
  79 tests, the 48-case R33 matrix, ten R34 positive groups and eleven R35 validation cases. Fresh independent
  Sol high R36 review is running. No watcher, extraction or workload has launched on 09/12/17.
- The explicit attention math-backend probe also exceeds the strict `2e-6` gate for both sizes on CPU and GPU.
  At microbatch 128, GPU max log-probability/value errors are 5.566e-6/9.775e-6 for S100 and
  9.500e-6/4.888e-6 for M. It compares retained-state unpadded one-row CPU reference distributions with
  batched learner outputs under the same explicit settings. This is a numerical probe, not actual actor
  sampling under a new runtime. No kernel setting or threshold was adopted; qualification remains blocked.
- Next-snapshot trainers remain healthy, M epoch 4 on 01 and S100 epoch 5 on 02. Provisional selection ETA
  remains 11:30-13Z from measured rates and full-DEV selection overhead. A separate isolated task is preparing
  a reviewed 05 CPU expansion owner for their already-frozen 1,600-case bank, reusing the successful R28
  per-case claims/drain procedure for both arms. It will preserve the original 05 owner and scientific cases;
  no additional game pool has launched. No lease watcher is needed for this owned-host work.
- Corrected seven recent local-time entry headings from their actual git author timestamps. These headings
  use PDT; explicit Z timestamps use UTC. Artifact, process and result timestamps were unchanged.

### 10:22Z R36 rejected; recovery integrity fixes required

- R36 is NO-GO for `86d3f20cda886a0516edc05326a845399eba1345`. Its real-child probes show a redundant
  stop-notification rewrite failure can block overdue KILL, one damaged journal entry can block all valid
  cached recovery, and changed journal contents can introduce an unrelated PID because their content-derived
  filename is not verified on read. The prior R35 cases and both 79-test suites still pass.
- A dedicated fix task is addressing immutable or validated notification reuse, per-entry journal error
  isolation with admission/ended uncertainty gates, and canonical journal digest verification before any
  ownership restoration. Fresh R37 review will follow. Nothing has landed or launched on 09/12/17.

### 10:37Z next-bank waiter live; R37 watcher review pending

- Reviewed next-bank expansion component `ef8b9395e3ba5faf4d340f754adee3f627e2d982` landed through
  `366c7d542`, with runtime source blobs verified identical. It runs from its clean immutable reviewed
  worktree. Fresh prelaunch process scanning found no waiter/controller/pool duplicate. Guard **4017232**
  and owner **4017239** launched at **10:32:52Z** on 05. Actual log state is
  `WAIT ready/selection/run/scaling publication`; no extra evaluator or expansion pool has started.
- Original CODE93 game owner remains untouched. The waiter preserves the frozen 1,600 cases and existing
  checkpoint selection/accounting, and will expand its original S100 then M pools from 24 to 64 workers.
  [NEXT-EVAL-EXPANSION.md](NEXT-EVAL-EXPANSION.md) records launch receipts, gates and output paths.
- Closed-source receipt publication on 08 does not itself copy run/summary receipts to 05. A separate
  receipt-only copier implementation/review task is closing that autonomous handoff; it is not launched.
  The expansion waiter's gate stays closed until both admitted anchors and completed local receipts exist.
- R36 fixes are committed at `7851936824d5255172d3409bfa0e0dffba25c5b3`, passing 89 tests on each
  interpreter and 146 Python 3.12 subtests, prior matrices and real-child fault regressions. Fresh independent
  R37 is running. No leased watcher or workload has launched. The strict numerical gate remains unchanged;
  an isolated higher-precision forward probe is measuring whether that engineering option meets it.

### 10:54Z R37 GO and live watchers; next-run receipt handoff closed

- Fresh independent Sol high R37 gives GO at exact source `7851936824d5255172d3409bfa0e0dffba25c5b3`
  for watchers and individually qualified staging/CPU contracts only. Both 89-test interpreter suites,
  146 Python 3.12 subtests, prior recovery matrices and independent active-fault probes passed.
  Review: `/mpac/sdicks02/scratch/pretrain-v1-dev/review/SOL-R37.md`. Main's supervisor, runbook and
  tests match the reviewed blobs. GPU, BC-resume and full RL launch remain outside this GO.
- Live watcher owners started at 10:45:58-59Z: 09 PID **3363731**, 12 PID **2219277**,
  17 PID **2622636**, each nice 10. Subsequent 10:46:28-29Z polls show `watching`, no jobs,
  no journal uncertainty, no reclaim/refused flag, and hard expiry `2026-10-25T07:53:00Z`.
  Reopening the owner lease by path is independent of inode/locks. Its bytes stayed unchanged.
  Immutable source: `/mpac/sdicks02/repos/clasher-pv1-lease-r37-7851936824/` on each host.
  State and launch receipts: `/mpac/sdicks02/jobs/clasher/lease-20261022/<host>/`.
  Local launch/live evidence: `scratch/pretrain-v1-dev/lease-r37-{launches,live}.json`.
  Existing archive staging remains unextracted; no scientific workload has been admitted.
- Receipt-only owner has fresh independent Sol high GO at `aa10b891e1154f931382339312837aed2f53b9ba`;
  17 focused tests pass. No existing copier was found immediately before launch. On 05, guard **2197122**
  and owner **2197130** started at **10:53:49Z**, nice >=10, from its clean immutable reviewed worktree.
  It atomically published the byte-exact S100 run/summary receipts and is `waiting` for M's atomic
  publication, without a transport failure. S100 selected anchor SHA256 is
  `74c7640776fd2c00fdd20c8c732dc07f4ed94c98964b5f816de4a60ae7cc332f`.
  State: `followup-20261022/next-run-receipts-owner.json`; outputs: `next-run-receipts/{S100,M}/`.
  The existing expansion waiter remains gated on both sizes and has started no extra game pool.
  [NEXT-RECEIPTS-OWNER.md](NEXT-RECEIPTS-OWNER.md) records gates and recovery behavior.
- 01 M is healthy at epoch 6, step 80,500, about 4,376 rows/s, reserved GPU memory 20.79 GiB.
  S100's selected completed run is already published through 08 and mirrored to 05. Both-arm game
  evaluation still waits for M. The prior 11:30-13Z admitted-bundle estimate is retained pending completion.

### 10:54Z higher-precision numerical probe passes, production qualification still open

- A measurement-only FP64 model forward with dtype-aware input casts and explicit math attention
  passes the unchanged absolute `2e-6` bound on retained real states for both sizes, CPU/GPU and
  microbatches 128/256. All 1,183 S100 and 703 M rows pass. GPU max log-probability/value errors
  are 7.7525e-7/4.5519e-14 for S100 and 5.4056e-7/9.5479e-15 for M at microbatch 128.
  Evidence and prototype hashes: [NUMERICAL-QUALIFICATION.md](NUMERICAL-QUALIFICATION.md).
- This recomputes one-row CPU reference distributions; it does not sample actual actor trajectories
  under FP64 or run an optimizer update. The production learner remains FP32 and fails its strict gate.
  No precision setting is adopted, numerical threshold relaxed, or RL launch authorized.
  Actual Session capture, exact next-snapshot starts, learner dtype/update correctness, full throughput
  and memory, and target latency remain to qualify before any runtime decision.
- A five-pass M CPU1 network-only timing on 05 measures mean 16.963 ms FP32 versus 26.444 ms FP64,
  about 1.56x. It excludes featurization and game work; it is neither a Mac latency result nor actor games/h.
  Probe GPU job finished cleanly, with no PPO updates and no remaining job.

### 10:56Z S100 next-snapshot selection admitted; FP64 candidate isolated

- S100's 41,328-match snapshot checkpoint is admitted at epoch 3, five eligible of six candidates.
  Full DEV covers 4,080 physical matches, 515,173 actor rows and 163,009 plays, including 153 Hog matches.
  Selected broad/Hog NLL is 0.336666/0.469532; card top-1 0.601224, tile within-one 0.440264,
  ECE 0.005477 and value Brier 0.561125. This is the selected full-DEV receipt, separate from
  the training summary's capped DEV metrics. Both-arm game evaluation awaits M's selection.
- Dedicated receipt owner has completed several 60-second polls, remains nice 19, and waits only for
  M's atomic publication with no network failure. It will continue independently of this agent turn.
- A separate Sol high implementation task is preparing a test-only FP64 numerical qualification
  candidate in an isolated worktree, followed by fresh independent Sol high review. The task preserves
  production FP32 defaults and the unchanged 2e-6 threshold, makes no remote/GPU/Mac calls and authorizes
  no precision adoption or training launch. It will supply actual Session/learner/checkpoint/update
  evidence and commands for later parent qualification. Task: `pv1-sol-fp64-qualification-candidate-20261022`.

### 11:22Z actual FP64 candidate passes CPU/GPU; qualification continues

- Offline candidate code `bf96bd145f381367c667f639cc262326f58c87e1`, evidence commit
  `1ebd0b0a3939761ae2d33eadeed27422eee042f8`, has fresh independent Sol high offline-only GO.
  Its 162 focused tests pass, with default FP32 output/digest parity to main. Candidate code stays
  isolated, with no production precision adoption. [NUMERICAL-QUALIFICATION.md](NUMERICAL-QUALIFICATION.md)
  records source/input identities, actual Session captures and remaining gates.
- Actual old-v3 S100/M captures pass CPU1/CPU4 and GPU strict 2e-6 at batches 128/256 on all
  1,183/703 rows. GPU max logp errors are 7.7525e-7/5.4056e-7; value errors below 4.6e-14.
  Fresh 256-row warmup fixtures and roundtrips pass. GPU test peak reserved memory is 1.012/1.762 GiB,
  not a full PPO memory qualification. Guard 3163159 on 08 exited cleanly at 11:17:43Z.
- Exact next-snapshot S100 CPU capture/check also passes: 886 genuine Session rows, max logp 1.0419e-6,
  max value 2.0151e-14, zero discarded/rejected rows. Its GPU check started at 11:21:57Z on 02, guard
  **1795299**, under `jobs/clasher/pretrain-v1/fp64-qualification-staging-20261022/`.
- Own 02 now has fresh verified calibrated-runtime and actor copies at
  `/mpac/sdicks02/repos/clasher-pv1-qual-runtime-0dcab45f7` and
  `/mpac/sdicks02/repos/clasher-pv1-qual-actors-0dcab45f7`. All 9,409/17,010 pinned file hashes match.
  Extraction receipt is `fp64-qualification-staging-20261022/verified-extraction.json`.
- Separate isolated Sol high tasks prepare the inherited AdamW resume-completeness fix, a real-size
  effective-batch-2048 PPO/post-update qualification fixture, and a target Mac FP64 benchmark option.
  Each requires fresh independent Sol high review. They authorize no production runtime/experiment
  changes, remotes, training launch or deployment. Parent owns reviewed measurement launches.
- M retraining finished with training-summary best epoch 4 and is in full-DEV selection on 01.
  Both-arm next-bank eval remains gated on the selected M publication. Existing receipt and expansion
  owners continue independently; no duplicate pool or training run was started.

### 11:24Z next-S100 GPU check complete; current autonomous owners

- Exact admitted next-S100 passes GPU parity on 02, 886 rows at batches 128/256, max logp
  1.0419e-6 and value 3.4750e-14. The 256-row warmup fixture/roundtrip passes, peak reserved
  0.869 GiB. Guard exited zero at 11:22:17Z. Evidence copied to `rl-readiness/fp64-next-S100-cuda1.json`.
- Fresh 11:22:58-59Z watcher states on 09/12/17 are `watching`, empty jobs and journal issues,
  `owner_lease_updated=false`. No leased workload or registered PPO run has started.
- Three isolated implementation/review handoffs remain active: `pv1-sol-adam-resume-completeness-20261022`,
  `pv1-sol-real-shape-ppo-qualification-20261022`, and `pv1-sol-fp64-mac-benchmark-candidate-20261022`.
  Production precision and model default remain unchanged. Next-bank receipt/expansion owners wait for M.
- A coordinator steer carrying these results returned `thread_not_sendable` because it had no running
  turn. Nothing was queued; all evidence and current gates are recorded here.

### 11:27Z reviewed test-only precision code and AdamW integrity fix integrated

- Independent Sol high gives scoped GO at `0f72b1eaadaa6b8ea7384edbb7f8d842a41df4f4` for
  AdamW resume-state integrity. Its 51 new tests plus 162 focused regressions pass; the reviewer
  passed eight additional cases. Bitwise continuation passes after updates 0/1/3/4 in FP32 and
  test-only FP64, including sparse, all-forced and boundary-declined actor masks.
- Main now includes the reviewed test-only FP64 candidate and this integrity fix. Every file under
  `bot/pretrain_v1/` matches the combined reviewed source exactly. Existing immutable qualification
  checkouts and jobs were untouched. Production FP32 remains the default; FP64 requires explicit
  `test_only=True` and production loading rejects its candidate checkpoints. This lands code, not
  production precision adoption, full runtime resume qualification or an RL launch.
- Resume derives the exact initialized parameter set and per-parameter counters from completed
  updates and replayed seeded shuffles, with packed actor eligibility evidence. Value steps on every
  update, trunk after the three critic warmups, and policy heads only in eligible PPO minibatches.
  Missing states, incorrect counters or canonical parameter IDs, missing legacy evidence and
  unprovable partial-update checkpoints fail closed.
  [ADAMW-RESUME-CANDIDATE.md](ADAMW-RESUME-CANDIDATE.md) and
  [RL-LEARNER-CONTRACT.md](RL-LEARNER-CONTRACT.md#adamw-resume-invariant) record the proof and limits.
- Full-batch PPO/post-update and Mac measurement helpers remain under separate implementation/review.
  M full-DEV selection has published eligible epoch 0 and epoch 1 candidate rows, with no final selected
  bundle yet. The existing receipt/next-bank expansion owners remain gated on that final publication.

### 11:44Z reviewed target benchmark and real-size fixture running

- Mac benchmark source `48795b3c7e343ca038d23abea9f6c69eea219d60` has fresh independent
  Sol high offline-only GO, 46 tests passed and one legacy MPS skip. Reviewed source and
  staged corpus/checkpoints were verified before launch; no prior benchmark job or waiter existed.
  Immutable package SHA256 is `6d8b3ca1d41089362f1a64760dc065912d416a27858c724133abb8625ff83291`.
- Mac owner **9723**, nice 10, started at **11:36:39Z** under
  `~/clasher-pretrain-bench/offline-fp64-48795b3c7/`. It runs selected v3 S100 then M, each
  CPU1/CPU4 for 20,000 actual Session decisions after 200 warmups. Every subprocess is bounded;
  all created files stay inside the benchmark directory. Existing replay/VM/server workloads
  remain untouched. FP64 MPS is explicitly unsupported, with no fabricated timing or fallback.
- Corpus canonical SHA256 is `0c1b52af43c431e18d30416fcf6bd988c57e97351c11838fc1bfbd36ee65c028`,
  36 physical real-record files, verified against the source corpus. Prelaunch Canvasdoc accounting
  was complete/idle, peak CPU 2.6% and RSS **757,952 KiB**. S100 CPU1 completed 20,000 decisions
  at p95 **18.207 ms**, p99 **27.593 ms**, passing the unchanged budget. Canvasdoc became active
  during this phase, peak CPU **18.2%**, RSS **795,536 KiB**, so it is shared-load evidence.
  CPU4 and M remain in progress. [FP64-TARGET-BENCH-HANDOFF.md](FP64-TARGET-BENCH-HANDOFF.md).
- New-only real-size fixture source `20a2d82b486d0349f00257b7c4621bdaa1efb3c3` has independent
  source GO. The integrated snapshot with the AdamW fix and benchmark helpers is
  `dc27b50708805d57a2daf127b80540b314126df1`, package SHA256
  `678058e4cc6670df7e165c083984b1a7a1ec5ad99da88b46a470dcb61517fe2c`.
  Parent's eight focused integrated tests pass. Fresh independent Sol high integration review
  gives GO for this bounded offline fixture only, with no actionable findings. Reviewed component
  source blobs match main exactly; running measurements retain immutable copies.
- On own 02, guard **1846079** and fixture owner **1846080** started at **11:41:18Z**, after fresh
  duplicate/resource/anchor checks. It uses exact admitted next-S100 SHA `74c7640776fd2c00fdd20c8c732dc07f4ed94c98964b5f816de4a60ae7cc332f`.
  It collects **8,192 genuine training polls**, three critic warmups plus one PPO update, effective
  batch **2,048**, microbatch **128**, then **256 fresh version-4 Session polls** for strict CPU/GPU
  parity. This is explicitly test-only, not the registered 262,144 x 32 experiment.
  Output is beneath `jobs/clasher/pretrain-v1/fp64-qualification-staging-20261022/integrated-dc27b5070/qualification-artifacts/`.
  [PPO-SESSION-QUALIFICATION.md](../../../bot/pretrain_v1/checks/PPO-SESSION-QUALIFICATION.md) records
  budgets, input gates, unfinished-game accounting and remaining qualification limits.
- Production FP32/default model, registered experiment and deployment remain unchanged.

### 11:49Z both next anchors admitted; expanded game eval live; fixture stopped

- M full-DEV selection completed at epoch 4, five eligible of seven candidates. Anchor SHA256
  `947af5cb5ac2b47fe666b329f21326e180b4b0d742bd97b1867603446cad79f4`. Broad/Hog NLL
  **0.328198/0.515936**, card top-1 **0.624880**, tile within-one **0.475606**, ECE **0.005127**,
  value Brier **0.572595** on the shared expanded DEV set.
  [NEXT-SNAPSHOT-READOUT.md](NEXT-SNAPSHOT-READOUT.md) records both sizes and sample counts.
- The receipt-only owner is `done` for S100 and M. The reviewed next-bank waiter admitted both
  anchors and launched S100 expansion controller **3741363**, preserving original parent
  **3709397** at case boundaries and running the 64-worker pool on 05. Sealed rows are arriving.
  It preserves the same frozen 1,600 cases, accounting and scientific runtime, then expands M.
  No duplicate jobs or replacement cases were launched.
- The next-S100 offline PPO fixture stopped at a failed gate after two critic warmups: actor
  generated/published **4,334**, discarded **0**; learner trained **4,096**, version **2**, optimizer
  steps **4**. A sampled command was rejected in the fifth completed game, seed
  `2026102208000004`. No PPO update or post-update parity phase occurred. Both completed warmup
  updates passed strict 2e-6 parity, effective batch 2,048, finite gradients and frozen-anchor checks.
- Failed attempt artifacts are retained unchanged. Evidence archive on 05:
  `rl-readiness/failed-S100-attempt1-evidence.tar`, SHA256
  `d5c1696ee2df1f564f05ceed8e0eac377b8bee06346d6b9d185ad70b765dc84e`.
  It contains all 4,334 published NPY rows, receipts and final counters. The completed-game gate
  fires before appending the rejected game's play log, so a focused deterministic replay task is
  tracing that exact game/command. No retry, seed replacement, rejection waiver, mask change or
  registered RL launch occurred. M's fixture is held pending this diagnosis.
- Mac FP64 S100 CPU4 also passes: p95 **23.744 ms**, p99 **47.565 ms**, 20,000 decisions.
  Both S100 thread settings observed active Canvasdoc and remain shared-load evidence. M CPU1
  fails the budget at p95 **45.302 ms**, p99 **59.454 ms**; its CPU4 measurement is still running.
  The owner continues collecting the approved matrix. No precision or model decision is made.

### 11:52Z FP64 Mac matrix complete; M misses observed-load budget

- Mac owner 9723 completed and exited at **11:49:48Z**. Both selected v3 sizes completed
  20,000 exact Session decisions on each of CPU1/CPU4. S100 p95/p99 are **18.207/27.593 ms**
  and **23.744/47.565 ms**, both passing. M is **45.302/59.454 ms** and **40.351/59.143 ms**,
  both failing the unchanged budget. FP64 MPS is explicitly unsupported and unmeasured.
- Canvasdoc was active in all four measured phases. Peak CPU S100 CPU1/CPU4 was 18.2%/59.9%,
  M 113.2%/20.4%; full RSS telemetry is retained. These are shared-load results. An idle rerun
  is pending actual idle workload conditions; no VM/emulator/server was changed or stopped.
  [FP64-TARGET-BENCH-READOUT.md](FP64-TARGET-BENCH-READOUT.md) contains the complete matrix,
  source/corpus/checkpoint bindings, units and artifact locations. No precision or size choice follows.
- The bounded PPO fixture remains stopped at its rejection gate. The focused diagnostic task is
  reproducing the fifth game from retained commands/features; no failed fixture data is replaced.
  Fresh-bank game eval continues independently under the reviewed 64-worker owner.


### Operational-rejection contract amended before code changes and relaunch

- Sam resolved the Cannon occupancy case: preserve DECISIONS.md item 8 and the engine, remove only the
  fixture's extra zero-rejection gate, and retain every sampled action/log probability/poll transition.
  Rejected taps leave hand and elixir unchanged and play continues. No resampling, WAIT substitution,
  transition removal, extra reward penalty or replacement budget is allowed.
- RL-DUAL-PREREG.md now registers per-snapshot and per-card executed-rejection rates and separate other
  execution failures. A rate strictly above twice that size's frozen BC-start rate is an alert, never a kill.
  Pending terminal/budget commands are separate. Missing baseline exposure is unavailable, not zero.
- Engine errors, invalid state and unknown identity still fail closed. Public history inference remains
  unchanged. Occupancy-aware masking is recorded only as a later follow-up. The first failed fixture and
  its evidence remain immutable. Corrected code, focused live-consequence tests and fresh independent
  Sol high review are required before a new bounded qualification attempt. No relaunch has occurred.


### Rejection amendment evidence and input staging

- The original minimized occupancy repro still fails only at the superseded zero-rejection assertion.
  A separate observational probe of the same frozen native apply/command queue confirms the hand and
  elixir remain unchanged, game_over stays false and the channel becomes available. No engine or mask
  source changed. Evidence is under `rl-readiness/rejection-amendment-20261022/`.
- Independent read-only receipt/array hash checks locate the original rejected tap at tick 5265, action
  **1933**, version **2**, log probability **-5.7638250995640075**, actor=true, reward=0, terminated=false.
  Its original queue row was retained. `retained-rejected-action-proof.json` binds its receipt and policy.
- Own 01 now contains fresh verified runtime/actor mirrors, **9,409/17,010 files**, from the same pinned
  joint manifest. Own 01 and 02 have the exact selected next-M checkpoint and selection receipt staged;
  its FP64 converted policy SHA is `a97cb49e7f9795a61753b445ab5059781bcb37cdc1f3fafaa6ad7f33978f3be0`.
  These are input copies only. Revised fixture implementation and independent review remain pending;
  no new fixture, registered training, precision adoption or deployment has launched.
- At 12:22Z, lease watchers on 09/12/17 were live, watching, with empty admitted-job sets and no journal
  issues. The owner leases remained valid with reclaim=false. They remain unused for RL launch.


### 12:40Z R38 GO landed; revised S100 and M offline fixtures launched

- Fresh independent Sol high R38 gives GO at exact revision
  `8fe59e7d2246baefb908d793122086f790e9cc33`, package Python SHA256
  `a77548c1c0bd63fa072290b91b3ddecfd72767a10f896f3b953c77c6f0c8d69c`.
  Forty-two focused tests and independent reviewer probes pass. The parent independently reproduces the
  S100 sidecar's exact counts and nine separate failures. Reviewed changes landed on main. Actor, learner,
  model, featurizer, mask, history and frozen engine/evaluator bytes remain unchanged.
- Both bounded offline fixtures started **2026-10-22T12:40:32Z** after fresh source, input, duplicate and
  resource checks. S100 on **02**: guard **2000869**, timeout owner **2000870**, Python **2000873**.
  M on **01**: guard **1583700**, timeout owner **1583701**, Python **1583704**. At launch both GPUs
  were idle with 48,575 MiB free, host load below 0.2 and more than 122 GiB MemAvailable.
- Each uses its exact selected next anchor, 8,192 training polls plus 256 post-update polls, three critic
  warmups and one PPO update, effective batch 2,048, microbatch 128, one CPU actor thread and a CUDA learner.
  Both have a one-hour outer timeout, the same game-seed range and at most 64 games. These are qualification
  fixtures, not the registered 262,144 x 32 experiment. Ordinary rejected taps are retained and reported;
  all other failures, strict 2e-6 parity and existing collapse/accounting gates remain.
- On each host, source/output root is
  `/mpac/sdicks02/jobs/clasher/pretrain-v1/fp64-qualification-staging-20261022/fixture-8fe59e7d2/`.
  Results are under `qualification-artifacts/<source SHA>/<anchor SHA>/ppo-session-cuda-b128-attempt2`
  for S100, and `...-attempt1` for M. Logs beside the source root are
  `ppo-next-S100-8fe59e7d2-attempt2.log` and `ppo-next-M-8fe59e7d2-attempt1.log`, with guard and launch
  receipts. Local 05 launch receipts and plans remain in `rl-readiness/rejection-amendment-20261022/`.
  Original failed S100 attempt remains immutable. No production RL, precision adoption or deployment GO.


### 12:52Z both revised fixtures pass; next 1,600-case comparison final

- S100 and M both finish the R38-approved offline fixture: **8,448 retained polls each, zero discards**,
  8,192 trained, three critic warmups, one PPO update and 256 fresh post-update rows. Strict CPU/GPU post-PPO
  likelihood errors are **3.292e-7 / 6.414e-7**, below 2e-6. All finite-gradient, policy-head-change, frozen-anchor,
  AdamW, cadence, budget and padding proofs pass. Other execution failures are zero. Owners have exited.
- Operational rejections remain data: S100 **2/417** executed taps, M **1/442**, all Cannon. Terminal/budget
  pending taps are separately **1/5**. Per-card and sampled-version counters are saved. Original failed S100
  prefix **4,334 rows / 722 arrays** matches the revised successful run bit for bit. The fixture readiness
  exposure has no matched frozen BC reference, so comparisons are explicitly unavailable. The implemented
  >2x alert comparator is tested; it never stops a run. Full RL snapshot comparison is still a launch gate.
- [PPO-FIXTURE-READOUT.md](PPO-FIXTURE-READOUT.md) records exact source/anchors, per-stage error bounds, KL,
  observed memory and actor/learner costs. M capture wall time per poll is about **1.62x** S100; same-batch
  PPO update is **4.06x**. This is one-R3a readiness evidence, not full league throughput or production memory.
- The fresh next-bank comparison also finishes: all **1,600 attempts** per size, **1,591 complete pairs**,
  nine common R3a failures retained. M minus S100 paired score is **+16.2107 pp**, 95% CI
  **[+13.3666, +19.1365]**. Conservative all-assigned lower estimate is **+15.5625 pp**. The registered preference
  rule passes for M. LIVE wins are **486/800 M versus 348/800 S100**, with 0 versus 1 draws. No default/model
  or deployment decision is made here. Both sizes retain their approved RL stages.
- [NEXT-SNAPSHOT-READOUT.md](NEXT-SNAPSHOT-READOUT.md) and [OPERATIONAL-REJECTIONS.md](OPERATIONAL-REJECTIONS.md)
  report results separately from the prior banks. Both frozen BC sidecars retain nine other failures, with no
  contract failures. Executed-rejection rates are **22/53,094 S100** and **19/60,104 M**.
- An idle Mac FP64 rerun was prepared using exact next anchors and the existing reviewed benchmark source.
  Fresh idle admission failed, peak Canvasdoc CPU **10.2%**, RSS **851,424 KiB** at 12:55Z. **No new benchmark
  owner/worker launched**; checkpoints are staged only under `~/clasher-pretrain-bench/`. Existing replay,
  Canvasdoc, UTM and server workloads remain untouched. Prior M FP64 shared-load over-budget results remain.
- Full registered RL, production precision adoption, model/default change and deployment remain unlaunched.
  The coordinator thread had no steerable turn when the result update was sent; nothing was queued.


### 20:08Z M promoted by Sam; RL and interim corpus work resumed in parallel

- Sam makes M primary and S100 secondary. Accepted serving target is M FP32 CPU1, p95 about16ms;
  another idle Mac run is removed from the critical path. No deployment or live/Mac configuration change.
- Allocation reserved:01 M learner/local actors;02 S100 learner/local actors;08 two interim M-BC seeds;
  05 sealed-snapshot build, integration tests and eval/audits.09/12/17 later actors only after lifecycle/reclaim
  qualification under the existing caps.04HP1 and13–16 remain untouched.
- Three isolated Sol-high implementation owners are active: interim120k sealed-only freeze and M retrains,
  full registered rollout/league driver, and terminal-boundary actor recycling/lease adapter. No duplicate
  existing compute was restarted. The raw status reports128,970 sealed matches; the exact included receipts
  and row count will be frozen and reported by the snapshot owner.
- R37 watcher source7851936824 remains approved and unchanged. All three existing watcher PIDs are live,
  nice10, empty and without lease breaches at20:08Z. No new watcher review/restart is needed. Full leased
  actor continuation is still a separate gate, so it does not delay the own01/02 path.
- Missing RL gates are concrete: integrated full262,144 rollout/league transport, terminal-boundary recycling,
  production memory admission and the registered6h32-actor soak, then fresh exact-source/config launch GO.
  The completed8k PPO fixtures do not satisfy these by themselves. RL launch time is not yet claimed.

### 20:29Z own-host handoff review and interim build

- R39 returns **NO-GO** for actor lifecycle `5d09f7a0b91d3a21fa143f25fbeb472561103212`.
  Two independently reproduced races can mutate a verified checkpoint's budget and roll back already
  acknowledged counters during object replacement. The candidate is unlanded. A separate fix owner is working
  from [SOL-R39.md](/mpac/sdicks02/scratch/pretrain-v1-dev/review/SOL-R39.md); another independent review is required.
  R37 watchers remain unchanged. Own-host monitors must independently enforce worker RSS and host limits while
  engine calls or learner acknowledgements block. Lifecycle hooks alone do not provide that enforcement.
- The reviewed interim builder is running on 05, owner **1254644**, with 24 workers. The frozen prefix contains
  **119,970 source matches in 240 sealed batches**, input SHA256
  `2422eb7321982a60b14f5152d3a4338f456294d1cd249b6cbb973de834c765c2`.
  It reuses 83 verified shards and builds 157. At 543 seconds, 131 shards contain 65,143 usable matches and
  12,704,697 rows; measured remaining build time is about 20 minutes. This excludes mirror verification and training.
  Build receipts and logs are in `/mpac/sdicks02/jobs/clasher/pretrain-v1/interim-20261022-b240/`.
- Two M seeds are reserved serially on GPU08. Concurrent seeds would exceed the 43.5 GiB admission budget.
  Before training, the parent corrected its brief's confusion between inference dropout 0 and prior M training
  dropout 0.1. Training retains **0.1** and receives a fresh config review. The running snapshot build is unaffected.
- At 20:24Z, own01/02 GPUs are empty with 48,575 MiB free and about 122 GiB host memory available each.
  They remain reserved for M/S100 respectively. GPU08 is empty, host load 59.7 and about 53.1 GiB available;
  its existing HP1 actors remain untouched. Leased 09/12/17 remain watcher-only pending actor qualification.
- A CPU-only constructor probe on 01 verifies the full pinned runtime and selected M anchor, then converts the
  local model to FP64 for measurement. It exits after 47.48 seconds, with **616,439,808 bytes RSS** and
  **612,308,992 bytes PSS**, CUDA uninitialized. It generates no games or polls. This excludes engine-game,
  opponent-cache and queue growth and does not admit a 32-worker pool. A separate maximum-shape allocation
  probe is in R40 review; it has not used a GPU.
- Frozen HP1 recovery04 v330 was found on 04 and copied read-only to 05. SHA256 remains
  `73bbbd860625a24e4e61f15dd30596c78542d04c4eedfcf2ab1346183de2c70e`.
  The existing `StudentPlayer` factory uses threshold `0.019753086419753086`. The raw seven-file royal-arena
  deck/level source also matches every hash in `opp-levels-dist.json`; the driver can freeze actual joint
  historical profiles rather than treat planning medians as observed training levels.
- No registered RL launch time is claimed. Integrated transport/pool review, precision registration,
  production admission and the registered six-hour actor soak remain outstanding. Mac measurement and
  deployment are not on this path.

### 20:33Z maximum-shape allocation passes; reviewed interim source landed

- R40 gives bounded offline GO for `4e8f740beab33557f1f5ceb0bd2c5b4678d8e3bb`.
  Both selected anchors pass the synthetic FP64 probe at microbatch 128, all **324 token positions present**,
  including entity/event/reveal widths **256/32/16**. Two optimizer steps include resident AdamW moments.
  M peaks at **20,870,856,704 bytes reserved, 19,665,971,200 allocated**; S100 at
  **9,609,150,464 reserved, 8,669,340,672 allocated**. Reserved peaks are **19.44 / 8.95 GiB**,
  inside the unchanged 43.5 GiB allocator budget. Loss and gradient norms are finite.
- Both probes start at **20:30:20Z**, M on 01 and S100 on 02. Guard/timeout PIDs are
  **2725255/2725257** and **3227833/3227835**. Both exit zero, at 20:31:00Z and 20:30:40Z;
  all four exact PIDs are gone. GPU use returns to idle. No games, environment polls or policy checkpoints
  are generated. The probe clears gradients before each step, so it does not itself measure a subsequent
  microbatch with accumulated gradients, full-rollout host memory or actor pools.
- SHA-verified results and guard logs are copied to
  `/mpac/sdicks02/scratch/pretrain-v1-dev/rl-readiness/maxshape-20261022/{M,S100}/`.
  Result SHA256s are `ead578501467015735a1baa19c16a21be9c80b85f66ec497b7afae79a0b82fb9` and
  `fe60b2f3bc200456230bab47d324ae0f036a0ea3cda134388548423603ac4cd4`.
  Probe archive SHA256 is `73527481b5010e9a19a1090eee49710f45ae77d3f97a8dc9d1bcb61d40eaae13`.
  This adds allocation evidence only; production precision and registered RL remain unlaunched.
- Reviewed interim preparation/training changes `b53b95763` and dropout correction `40ea0b503` are landed.
  Fresh nested Sol high R2/R3 approve the source pins. The corrected training pin is
  `e34e88921c36f87febeda11857af5e49fdd1fe8698a250da0e0ec674c5fe7125`; all **73** pinned input files match
  the landed files. Parent featurizer/dataset regression checks pass **25/25**. Training retains dropout 0.1,
  batch 512, BF16, the same LR/decay/schedule and R7 release behavior. Existing builder PID 1254644 continues.

### 20:39Z explicit training precision component reviewed

- Fresh independent Sol high R42 gives **component GO** for `f9c83babb9f3fa01b22ddff84ac312c07f9710da`.
  All **147 CPU tests** and independent record, precision and resume probes pass on pinned Torch 2.7.1.
  The explicit dual-size FP64 registration is landed. Default FP32 and test-only record schemas remain unchanged;
  an FP64 registered run needs the exact amendment identifier and the original full-budget guards.
  Checkpoints bind the identifier; missing or mismatched configuration fails resume.
- [TRAINING-PRECISION-20261022.md](TRAINING-PRECISION-20261022.md) records the amendment before launch.
  Both arms use the same precision, LR, objective, effective batch and step budget. Strict 2e-6 parity remains.
  This does not qualify the full runtime or change serving/deployment. The driver still needs its final review.
- R39 fixes are frozen at `f756460c9f95a7b83f26211eca0420ab15a6f525`, with **217 CPU tests passed**.
  They snapshot verified record/cursor bytes and deny unsafe in-process object transfer. Detached process handoff
  remains terminal-only with exact dead-source and durable one-use claims. Fresh R41 review is pending;
  the original NO-GO candidate is not landed or used for real engine qualification.

### 20:45Z R41 GO and three parallel BC seeds supersede reservations

- R41 gives **component GO** for `f756460c9f95a7b83f26211eca0420ab15a6f525` after 217 CPU checks and
  independent race probes. The combined terminal-handoff component and fixes are landed. Parent composition
  checks on pinned Torch2.7.1 pass **114/114**, covering handoff, lease adapter, precision and coordinator.
  This still requires integrated driver/resource review before real-engine qualification.
- Sam supersedes the idle01/02 reservation and serial-two-seed plan. The new BC allocation is
  **08 seed2026102001, 01 seed2026102002, 02 seed2026102003**, all on the same frozen snapshot and unchanged
  M training settings. All three are intended to run in parallel. No seed launch time is claimed yet.
- The six-hour soak uses01/02 actors **and learners** as soon as R41 and integrated review permit.
  Sharing requires measured aggregate GPU use with at least8GiB free. Otherwise BC checkpoints and yields
  before soak admission. A dedicated owner is implementing complete optimizer/scheduler/RNG/batch-cursor
  checkpointing with deterministic continuation tests; existing model-only epoch saves cannot provide it.
  One earlier duplicate checkpoint owner was stopped before overlapping trainer edits. Three-host staging
  and controller review proceed independently. The existing08 source is immutable and can start its first
  reviewed seed without waiting for the01/02 handoff component.
- Historical next41k M throughput is **4,374 train rows/sec median**, about25.3minutes per6,498,432-row epoch
  including capped DEV. The preliminary interim estimate is **about1.2hours per epoch, up to9.6hours per seed**,
  plus full-DEV selection and any explicit soak pause. These are historical extrapolations, not measured
  interim training rates. The parallel allocation replaces the earlier19–20hour serial estimate.

### 20:49Z snapshot ready on all three hosts; first parallel BC arm launched

- The frozen snapshot is complete and independently SHA-verified on **08,01,02**: 240 batches,
  **119,970 source matches, 119,475 usable matches, 23,498,034 rows**, 6,241 store files.
  Manifest SHA256 is `1aa01c37fdd18ac7c23a5e9cf7b875b674d5021309ab4b4b79603fd29661b264`.
  Source input SHA and safety counters remain as registered. Builder PID1254644 exited naturally.
- **08 seed2026102001 launched 2026-10-22T20:48:23Z**, exact PID **2985510**, Linux start **250150843**,
  boot **8965a752-e095-4700-b4fd-c6b90daddfca**. It uses immutable reviewed source `40ea0b503`, corrected
  pin `e34e88921c36f87febeda11857af5e49fdd1fe8698a250da0e0ec674c5fe7125`, dropout0.1 and the original
  batch512/BF16/LR/schedule. Allocator cap is39.035GiB. Inherited legacy locks prevent duplicate owners.
  This is one direct seed command, with **no automatic second seed on08**. The parent rechecks the receipt,
  exact live PID and command, host memory/load and empty preceding compute state.
- The 08 receipt is `jobs/clasher/pretrain-v1/interim-20261022-b240/independent-08-launch.json` on08;
  a copy is retained on05 under `scratch/pretrain-v1-dev/interim-20261022-b240/`.
  At52seconds, the process has about9.6GiB RSS, host memory available about43.9GiB and load78.3.
  It is initializing the store/baseline; no interim training throughput is claimed yet.
- **01 seed2026102002 and02 seed2026102003 are staged**, with completed input-hash verification.
  Their launch waits for the reviewed complete-checkpoint/yield component and revised host controller,
  so they can return GPUs to the01/02 actor/learner soak safely. They have not launched.
  Preliminary upper training time remains about9.6hours per seed plus full-DEV selection and any soak pause;
  first measured interim throughput will replace that extrapolation.


### 21:05Z three interim seeds active; latest allocation supersedes yield plan

- All three reviewed immutable40ea M-BC seeds are active.08 seed2026102001 launched20:48:23Z, PID2985510;
  01 seed2026102002 and02 seed2026102003 launched20:54:57Z, PIDs2786949/3293704. The same240 sealed batches,
  119,475 usable matches and23,498,034 rows are SHA-verified on all three hosts. Full source/runtime pins,
  process-start/boot identities and receipts are in INTERIM-120K-STATUS.md. No jobs were restarted or signalled.
- Sam explicitly cancels checkpoint/yield/controller development and review. Candidate05ed0f89 remains unlanded
  and unused, cancelled by decision. This supersedes the20:45/20:49Z yield and waiting notes above. All seeds
  run to completion with the original trainer invocation. No automatic second seed runs on08.
- Early measured training rates are about3,096/4,371/4,354 rows/sec on08/01/02. Training-only physical GPU use
  is about16.26/13.21/15.81GiB. Conditional eight-pass training estimates are about13.5–14.5/9.6/9.6 hours,
  plus DEV/calibration/full-DEV selection. Final holdout remains unused. No120k anchor is admitted yet.
- Soak sharing needs full-process GPU peaks and8GiB free throughout. R40's19.44GiB M allocator peak is not a
  physical-process peak. Prior complete M BC workflow reserved32.10GiB at DEV/calibration; early training
  measurements do not prove whole-workflow sharing. The driver prepares a separately gated M09/S12 fallback.
- Sam's standing compute-max rule authorizes leased13–16 again, each process cap32/PSS32GiB/affinity0–31/nice10.
  A dedicated owner extends the watcher with fresh review, preserving current09/12/17 watchers. The same owner
  stages pinned runtime/environment dependencies on09/12 first. No new leased engine/GPU job is admitted yet.
- The integrated driver includes R41/R42 and independent host/child/GPU monitors. Final review and real
  six-hour qualification remain pending. The frozen LIVE serial identity is the deployed K4L pt5 interruptible
  search with f1a2 step001200 at threshold0.6444047689437866, fullpool belief11433651/freqb53b02a1fde4,
  native1/pool0/chunks4/no wall. This differs from the historical BC strong-opponent K4CW surrogate.
- An unresolved preregistration gate is explicit: continuing games can start under different current/reservoir
  versions across sizes. Sam has been asked whether to permit and record per-arm versions or require a paired
  scheduling redesign. Registered RL cannot launch under an implicit amendment. Separate qualification rows
  remain qualification-only. No registered RL launch time is claimed.
- The active live-integration owner received M anchor947af5cb5ac2b47fe666b329f21326e180b4b0d742bd97b1867603446cad79f4,
  selection receipt,486/800 LIVE wins and paired M–S+16.21pp CI[13.37,19.14]. That owner controls live integration;
  this task performs no deployment or Mac changes.


### 21:16Z integrated driver frozen for independent review

- Driver candidate50f83891b4411abfd54f17122a5556ade16129f0 is clean and frozen in
  /mpac/sdicks02/repos/clasher-rl-registered-driver-20261022. It adds persistent process transport, terminal
  recycling, coordinator/learner integration, frozen league/evaluation factories, independent resource monitors
  and a separate bounded qualification soak entry. Implementation reports332 CPU tests passed. It has not
  landed or launched engine/GPU/soak work.
- Fresh independent Sol-high R43 reviews transport, quota accounting, resources, lease composition and
  qualification gates. R44 independently reviews populations, exclusions, paired evaluation and rejection
  reporting. Both review the exact frozen commit. Registered snapshot-version scheduling remains unresolved;
  qualification rows and checkpoints cannot become registered training.
- Source archive SHA256 is d7f47f3a73b9e7788c742ae5726bed957843fdfef8ff099a773e64cb47a1d03e.
  The draft input bundle and explicit gate audit are under
  scratch/pretrain-v1-dev/rl-readiness/registered-driver-inputs-r1/. Missing full-process CUDA memory evidence,
  source-bound precision receipt, full queue exposure and six-hour soak remain real gates.
- Fresh read-only21:15:28–29Z checks confirm all three exact BC PID/start identities.08 is atstep8000,
  2946 rows/sec, physical GPU20,933MiB, host available34.16GiB/load82.61.01 and02 are atstep10000,
  about4359/4355 rows/sec, physical GPU15,533/18,643MiB, host available103.35/103.39GiB/load1.19.
  These are continuing training peaks, not complete DEV/calibration peaks. No existing job was changed.


### 21:23Z per-arm game-start versions authorized; R44 production findings

- Sam explicitly chooses per-arm current/reservoir versions at game start, with actual version recorded and
  deterministic opponent families/decks/levels/seeds still paired. RL-DUAL-PREREG.md now registers
  paired-case-draws-game-start-version-v1 before any registered launch. Continuing games and budgets remain
  unchanged. The final registration receipt must bind this amendment; no implicit receipt is substituted.
- R44 reviews exact driver50f83891b and gives production NO-GO. The final summary accepts insufficiently
  authenticated evaluation provenance, and the exclusion inventory omits PF1's300 seeds plus10 physical
  source-run identities retained in training profiles. Both require fixes, newly frozen production inputs
  and fresh review. Existing candidate and qualification inputs remain preserved.
- R44 gives population-only GO for bounded six-hour qualification with its frozen draft workload, since its
  rows/checkpoints cannot become registered training. This is not an integrated launch GO. R43 transport and
  resource review remains running; full physical GPU evidence, precision/queue/soak gates remain outstanding.


### 21:28Z R43 qualification NO-GO; separate fixes and physical probe preparation

- R43 independently reviews50f83891b after236 passing CPU checks and reproduces four qualification blockers:
  canonical claims directory never created; six-hour shutdown not bounded; IPC deadline excludes frame-body
  transfer and sending; supervisor setup exceptions escape failure handling. The adopted per-arm-version
  amendment also needs actual opponent policy SHA in every game record. SOL-R43.md retains exact probes.
- A separate Sol-high implementation owner fixes lifecycle/IPC/resource paths and opponent metadata in a fresh
  worktree at the reviewed base. R44 fixes reporting/provenance/population inputs independently in disjoint
  files. Original candidate and staged inputs stay immutable. Both need fresh review before composition.
- No integrated or six-hour launch is authorized by these reviews. No registered RL has launched. R37 remains
  approved for its existing watchers; this driver NO-GO is distinct from watcher source review.
- R43 finds unchanged R40 suitable for a separate bounded synthetic CUDA full-process-memory measurement on
  idle09/12, conditional on exact remote source/anchor/runtime verification, fresh R37 whole-process admission,
  free43.5GiB at entry, independent one-second physical process/device traces, GPU free at least8GiB, finite
  timeout and exact exit/reap. The staging owner prepares M09/S10012 attempts under those conditions. No probe
  launch time or measured physical peak is claimed yet. BC jobs remain untouched on01/02/08.
- A one-second sampled synthetic peak has sampling uncertainty and omits accumulated-gradient/full-update,
  engine actor, queue and long-run growth. It cannot alone satisfy integrated memory admission or soak GO.


### 21:36Z supplemental M allocation; new-host watchers landed

- Independent995579193 GO for new13–16 watchers is landed as c9c341d19/1bb37afd3. Supervisor and runbook
  hashes exactly match the review. Watchers are live at13=1366383/14=1490887/15=2654636/16=3599992,
  nice10/CPU0–31. Existing09/12/17 watchers remain unchanged. No workload GO is inferred from watcher GO.
- Sam orders useful GPU work while RL is blocked. Supplemental M seeds2004–2010 are registered for
  09/12/17/13/14/15/16 respectively, preserving the119,970 source snapshot and M hyperparameters.
  LEASED-M-BC-PLAN-20261022.md records per-host staging/review targets. No extra seed launch is claimed.
- A dedicated Sol-high owner starts staging and the required minimal lease-only stop checkpoint adaptation.
  Original01/02/08 jobs/source remain unchanged. Cancelled full yield/resume/controller work stays cancelled.
  R40's new operational monitor remains in fresh independent review; no09/12 GPU attempt has begun.
- Future M handoffs target live integration r2 at a07d278b, never the failed r1. It already has947af5cb.
  Claude main and sjeother limits are known, so any necessary Claude child uses assistant_ui. Sol-high owns
  current reviews/fixes. The failed old lease Claude patch was completed and reviewed by Sol, not duplicated.


### 21:41Z R44 fix frozen for fresh R45 review

- R44 implementation is clean31c1035ad56dd5099d885473bd78b731d12021f2 atop50f83891b. It authenticates
  registered scope/admission/source/config/runtime and complete checkpoint ledgers, validates successful-row
  origins and explicit invalidity, and derives exclusion unions from pinned historical sources.
- Fresh production candidate is rl-readiness/registered-driver-inputs-r44-v2/bundle.json with configs-complete/.
  It records4700 historical seeds,53 physical IDs and3335 deck identities, including all300 PF1 seeds and the
  demonstrated10 physical overlaps. Training retains11/87 royal and10/23 adjacent profiles after exclusions;
  level/family mixtures stay fixed. Old qualification inputs and5400 evaluation cases remain preserved.
- Implementation reports90 focused tests and10 existing regressions passed. Two old fixtures fabricate
  unaudited exclusions or omit now-required origins/config; they are not a combined-suite pass. The R43 owner
  will compose the fixes and migrate those shared fixtures without weakening validation. R45 independently
  reviews exact31c1035ad now, including original attack reproductions. No source/config/launch GO is inferred.


### 21:51Z R45 exclusions pass; reporting remains NO-GO

- R45 gives NO-GO at31c1035ad. New origin validation rejects the actual approved runtime/src/clasher package
  layout, and intermediate checkpoint files can bypass serialized runtime/Adam-counter verification when their
  update is not an evaluation snapshot. Completion also needs reconciliation of existing actor/quota/receipt
  progress, beyond hash linkage. Independent probes retain all attacks and exact scope in SOL-R45.md.
- R45 independently verifies the complete declared historical inventory and all5400 preserved cases. There
  are4700 historical seeds/53 physical IDs/3335 opponent-deck identities, with all300 PF1 seeds and the ten
  demonstrated source overlaps excluded. Those corrected exclusions do not need a new scientific decision.
- A fresh narrow implementation owner fixes real-layout origins, every-boundary serialized checkpoint/progress
  verification and the two legacy fixtures. Original31 and old qualification inputs stay preserved. R43 freezes
  its lifecycle-only fix first so bounded qualification review can proceed independently of production reporting.
- No integrated, registered or operational launch approval follows from the112 passing R45 tests. Both disclosed
  legacy fixtures still fail until migrated; no full-suite pass is claimed. Existing BC jobs are untouched.


### 21:56Z pure R43 fix in fresh R46 review

- Pure R43 fix9db1beeec023b25b2bccf31a5a3c23bfb55e9bc6 is frozen directly atop50f83891b, source digest
  6ad3e1e2775c4ce712cc90ea5a7a09f41e7ecf304b99da3b6b33ef427d78be78. It contains no R44/R45 changes.
  Implementation reports42 focused CPU checks passed, including genuine first recycle, framed IPC deadlines,
  finite startup/shutdown, exact-session cleanup and opponent policy-SHA metadata. Earlier R43 SHAs are superseded.
- Fresh R46 independently reviews the bounded qualification path and, separately, the unchanged standalone
  full262144-row synthetic CPU queue qualifier. No queue or six-hour launch is claimed before exact GO and
  fresh resource/staging admission. Production reporting fixes remain a separate gate.
- Parent prepares an explicitly PENDING source-bound precision composition artifact under
  jobs/clasher/rl-qualification-r46-20261022/precision-composition-pending.json, SHA
  ff5f29b827b542239b250fa02451863991571a80e58b36610c3787eb0136ad49. Model, RL math, streaming actor,
  production policy and featurizer bytes equal R38; learner bytes equal R42. The only learner difference from
  R38 is the explicit precision-registration/config guard, not forward/loss/optimizer computation.
- Actual retained R38 result hashes are Mba336f8f3fbb28a039dfed899727a05b79206c1917a608c03dc5b24232a13014
  and S100c4a8aced92ee22e10ca2520d23ee14ec0fe2129a6e13359ba2d6df97e2517a1a. Both exact anchors passed
  fresh256-row version4 CPU/GPU parity at batch128/256, max logp errors6.414e-7/3.292e-7, below2e-6.
  This is composition evidence, not a new numerical run, full-memory proof, precision receipt GO or launch GO.


### 22:06Z full CPU queue launched; R46 fixes and R47 review proceed separately

- R45 correction a81a24ef0d45cd15f31c7f2ebbdd0b1c14e86d6e is frozen atop31c1035ad. It fixes real runtime/src
  origins and verifies all33 serialized boundaries, retained actor/receipt/progress evidence and final totals.
  Implementation reports171 tests passed with no skips, including the two migrated legacy fixtures. Fresh R47
  independently reviews that exact clean source; no operational GO is inferred.
- R46 gives integrated qualification NO-GO at9db1beee. An unrelated learner exception after cutoff can be
  hidden behind the first cooperative stop reason, and select.select fails on control descriptors>=1024.
  A fresh owner fixes the independent failure outcome and high-FD readiness, with stable contention regressions.
  The original source remains pinned and unchanged; this is not production reporting work.
- R46 explicitly gives GO to the separate synthetic full CPU queue method. Parent launches exactly one
  262144-row/2048-chunk attempt on05 at2026-10-22T22:05:14Z, timeout owner PID571379/start249648650/session571379.
  Admission has114.51GiB available/load4.01 and more than8GiB free disk; Torch271, CUDA hidden, nice10/math1,
  hard nofile unchanged1048576 and900-second timeout with10-second TERM/KILL followup. Source digest is
  6ad3e1e2775c4ce712cc90ea5a7a09f41e7ecf304b99da3b6b33ef427d78be78; script SHA7a99592277bcf11bac53c88ec894c9355afcabec337a18adc4d3005fd4ec4fc6.
  Launch/result/exit evidence is under jobs/clasher/rl-qualification-r46-20261022/queue-full-attempt1*.
  It generates no engine games, experiment polls or optimizer steps. Full result is pending.
- R46 independently accepts the unchanged R38/R42 FP64 composition evidence for a narrow precision component
  receipt once exact corrected code/config GO is obtained. No new numerical run is needed solely for those
  unchanged components. This does not replace physical GPU, staged-input, memory, six-hour or launch gates.


### 22:08Z supplemental host qualification and original seed telemetry

- Supplemental full-store CPU qualification has completed on13–15 at conservative memory bounds about16.30GiB,
  within each30.5GiB job reservation plus the required margin. Those hosts await exact combined code/config GO
  and fresh per-host admission. Parent explicitly permits their launch independently of16/17 if review finds no
  shared source blocker. No supplemental GPU training launch is claimed yet.
- Host16's loader completed but its wrapper rejected a resource sample, so no memory qualification receipt was
  issued. The owner retains the failed attempt and runs bounded diagnostics.17 is held on repeated post-write
  input integrity checks. Neither is represented as ready; their earlier target ETAs are conditional and at risk.
- Fresh22:07:24–25Z checks confirm original PID/start identities on01/02/08.01 is atstep36500,4397rows/sec,
  physical GPU19,409MiB and103.35GiB available;02 atstep36000,4336rows/sec,18,643MiB and103.39GiB available;
  08 atstep26500,3073rows/sec,23,215MiB and33.92GiB available/load83.04. None has a completed epoch file at
  that sample. No120k checkpoint is selected or admitted, and best-M handoff remains the evaluated41k anchor.


### 22:11Z R47 original fixes pass; two safety invariants remain open

- R47 gives scoped reporting NO-GO ata81a24ef. It confirms normal pinned runtime/src origins, all33 serialized
  boundaries and prior actor/receipt/final reconciliation fixes, with171 supplied tests and independent real
  producer-positive checks passing. It additionally accepts contradictory saved KL-stop/safety progress and
  finite negative Adam second moments, both impossible under the registered learner/optimizer.
- A fresh narrow owner fixes required real metric fields, finite/count/parity bounds, warmup-zero and exact
  high-KL-streak recurrence, plus nonnegative exp_avg_sq at every boundary. It preserves full real-learner
  positives and rehashed intermediate attacks. No optimizer, sampler, schedule or transport change is authorized
  by this reporting fix. Original source/inputs remain preserved for fresh review.
- The R46 full CPU queue attempt remains within its900-second timeout and has written1769 of2048 chunks at
  22:11:10Z. No completion receipt is claimed yet. R46 high-FD/independent-error-channel fixes continue
  separately; no integrated, registered or six-hour launch has occurred.


### 22:14Z full262144-row CPU queue exposure passes

- The R46-approved standalone attempt passes under the900-second timeout in509.21seconds, exit0. It maps all
  2048 maximum-axis chunks simultaneously, writes2,099,716,096 bytes, peaks at2.47GiB RSS and38,917 descriptors,
  then closes mappings, acknowledges receipts and returns to5 descriptors with an empty queue. Exact owned
  timeout/Python identities are gone and no process survives. No engine, CUDA, experiment poll or optimizer ran.
- FULL-QUEUE-READOUT-20261022.md records source/script/runtime pins, host admission, result/receipt hashes,
  timeout/cleanup and scope. Evidence index SHAdb321ed8372a556beef1a387b865606191fe82e83d863ec1773c5a7ce37ffbda
  is under jobs/clasher/rl-qualification-r46-20261022/. This is an actual full-row storage proof, not an extrapolation.
- The method proof is separate from integrated full-rollout/32-actor/GPU/soak admission. Corrective source
  changes need unchanged-method rebinding. Independent learner-failure/high-FD and reporting-safety fixes
  continue; no six-hour or registered launch GO is inferred. Original BC jobs remain untouched.

### 22:34Z six BC seeds active; R48 clears qualification control code

- Supplemental seeds2026102007/8/9 launched on13/14/15 at22:19:24/31/34Z after independentR5 GO and fresh
  host admission. Exact trainer PIDs are1628486/1772655/2902801. All passedstep500 with finite losses,
  4128.5–4224rows/sec and14.33–14.45GiB allocator peaks; startup PSS was27.084/26.028/25.315GiB.
  Reviewed implementationd341d6f954b126a5ca2ad4a9dcfa7bffc6063c77 and receipt commit18674ef1f remain separate
  from the immutable40ea primary jobs on01/02/08. No watcher, owner lease or primary trainer changed.
  Launch evidence is in jobs/clasher/supplemental-bc-20261022/ and the supplemental checkout's LAUNCH-STATUS.md.
-16 remains held without a causal explanation for its failed resource sample. The exact frozen sampler/native
  zombie-leader stress ran120 cases with zero failures, maximum0.2468seconds. That diagnostic result does not
  replace the missing successful parent qualification.17 remains held pending causal/integrity evidence covering
  bytes actually consumed. A fresh isolated owner and independentR7 review investigate both; no training retry.
- R48 gives narrow qualification code/config eligibility GO at5accde42847e27c610b5e72a442ee5786fa375df,
  closing R46 learner-failure masking and high-FD control defects.197 checks pass. Existing full CPU queue and
  unchanged R38/R42 FP64 evidence are eligible for exact-source rebinding. This is no staging, GPU, lease,
  operational launch, six-hour completion or production reporting GO.
- Parent prepares input-root candidatefe6d64214200679372f337bb37b33606f5c9997d directly atopR48. Explicit audit
  roots retain exact manifest coverage; a fresh local closure copies402 pinned inputs under jobs/clasher and
  rewrites only five reachable JSON reference containers. Both configs pass full local9409runtime/17010actor
  input checks with05 roots substituted in memory. Cases/decks/levels/settings and raw payload bytes compare
  unchanged.43 focused checks pass; fresh independentR49 reviews source and concrete metadata. No remote
  staging is claimed. Prepared artifacts live under jobs/clasher/rl-input-roots-20261022/prepared-attempt2/.
- Reporting correctionee30d45192a9197607ee2fc720245577ddf90482 fixes R47 metric/KL-stop and negative Adam
  second-moment authentication. Owner reports103 new and171 legacy tests, no skips; fresh independentR50
  reviews the exact clean source. It remains separate from qualification control until composition is reviewed.
- R40 operationalR4 remains NO-GO because observation can end before owned process exit/reap. Its owner
  prepares the coherent absolute-deadline repair and fresh review.09/12 remain exclusively R40-owned; no SSH
  or GPU measurement attempt or host release has occurred. Physical process evidence and six-hour launch
  remain pending. Best evaluated M handoff remains947af5cb; no120k checkpoint has been selected/promoted.

### 22:36Z reviewed supplemental code landed; held-host diagnosis remains separate

- ExactR5-reviewed supplemental source and launch receipts landed on main as a38944584 through0576ad857.
  The adapter, trainer, launcher and registration bytes matchd341d6f95;21 local lease/admission checks pass.
  This landing neither updates nor restarts the immutable running trainers.13/14/15 are the only hosts covered
  by that operational review;09/12 retain R40 ownership,16/17 remain held.
-17's preserved rejected environment archive exhibits concrete same-file buffered/direct read discrepancies,
  including112 wrong bytes over sampled3MiB blocks and a targeted range with42 buffered wrong bytes versus
  zero direct, then another with41 buffered versus one direct. Inode,mtime,ctime and length remain unchanged.
  This establishes read-path instability, not a specific hardware cause. No payload writes/cache advice/GPU
  work or admission change occurred. A full240-second diagnostic timeout is retained as failure.
-16's128 native exit cases, including eight16GiB cases, pass. Original sampler stderr was discarded, so those
  diagnostics do not retroactively establish its cause. IndependentR7 permits a diagnostic-loss-only patch;
  freshR8 review remains required before deployment or any new qualification. No training retry is admitted.
- Fresh22:35:41Z exactPID/start/boot checks confirm01 has ep00.pt/best.pt and is in epoch1 atstep50500,
  4364rows/sec and21,653MiB physical GPU,103.33GiB available/load1.50.08 remains epoch0 atstep36500,
  3019rows/sec,26,235MiB GPU,33.95GiB available/load82.25. These partial checkpoints are not selected anchors.
  FullDEV selection and frozen-bank evaluation remain mandatory before replacement live-M handoff.

### 22:45Z R49 input closure GO; exact component receipts issued

- R49 gives narrow separate-qualification metadata/config eligibility GO atfe6d64214200679372f337bb37b33606f5c9997d.
  It independently verifies all402 inputs,397 unchanged payloads and five reference-container rewrites; both
  complete input manifests pass with9409runtime/17010actor files,326audit files/108games and1600primary/200DEV
  cases per arm.19 focused checks and independent attack probes pass. It accepts unchanged queue/FP64 proof
  rebinding. Remote contents, physical GPU, fresh leases, launch and actual exposure remain unestablished.
- R49 finds a separateP2: post-training evaluation still checks audit pins against default paths. Parent reproduces
  both relocated DEV/final failures, preserves the failed log, and fixes only that precondition to use configured
  roots.50 checks pass; clean candidate65672fb593231cd3f382f2ed63b1eb334011cab9 receives freshR51 review.
  This evaluator path is absent from the separate soak; the qualification source remains pinnedfe6, unchanged.
- Parent issues the R49-authorized exact-fe6 FP64 component receipt, SHa0d85120715f2df663f3e38eb41be25d7d3626c9843d367ca41348f3bd448d67a,
  plus retained synthetic queue-method composition SHac46dfc02ebd422dc9f4d2c57c21f2ac39ebdf8316a73e45b37c15d62d6fd3d8a,
  under jobs/clasher/rl-qualification-receipts-20261022/fe6d64214/. Both bind source aggregate
  ff71c87aa81d069f2574dcb30aff0df988a56a7a20d7b925a96f1441c669dd0e, retained raw evidence andR48/R49 reviews.
  No new numerical run, whole-runtime precision adoption, physical process proof or operational GO is claimed.
  Final config identities and launch receipts remain pending physical measurement and staging/admission.
- A separate Sol-high owner prepares a minimal exact-source/input staging and bounded persistent launch package
  locally, with independent review required before any use. It accepts parent-pinned final configs/receipts and
  explicit R40 host releases; it cannot invent them. No SSH or new remote job is authorized at preparation time.
  Six BC seeds remain running;16/17 holds and R40 exclusive09/12 access remain unchanged.

### 22:51Z R50 and R51 scoped GO; integrated source awaits R52

- R50 gives narrow registered-result authentication/provenance GO atee30d45192a9197607ee2fc720245577ddf90482.
  Both R47P1 guards close;274 tests pass with independent rehashed attacks, mandatoryKL-stop recurrence and
  actual learner/coordinator producer positives. This does not approve an integrated or operational launch.
- R51 closes R49's relocated evaluation precondition at65672fb593231cd3f382f2ed63b1eb334011cab9.16 tests and
  52 independent boundary cases pass; all402 prepared inputs/configs remain unchanged, with numerical/queue
  evidence eligible for rebinding. The separately selected qualification source remainsfe6; no run pin changes.
- Parent composes all reviewed driver, relocation and reporting patches on current main in a fresh checkout,
  clasher-pv1-rl-composed-20261022, exact7823423a39f3bdcf85f9f3afac4dced7842b9db5. Source aggregate is
  9621646fe51f3d9fce549d1540dc2d0d6c1f8c7ee891aeca7cf5151b08deb187.26 component/document byte comparisons
  match their reviewed revisions, including unchanged numerical/storage code, primary/supplemental BC,
  lease watcher and current scientific documents. Fresh independentR52 reviews the combined interfaces before landing.
- Initial combined CPU run has227 passes and142 setup errors: the synthetic reporting fixture constructs a
  coordinator with __new__ and omitted the independently reviewed failure-channel fields. A direct leaf call
  reproduces missing_failure_lock before checkpoint00. Only that fixture now initializes the real constructor's
  Event/Lock/null failure/null typed cancellation. Runtime guards are unchanged. The targeted all33-checkpoint
  positive passes; the complete369-check combined rerun is in progress. Failed and mistyped-target logs are
  retained under jobs/clasher/rl-composition-20261022/; none is counted as a passing run.
-16 diagnostic-only patch still awaits freshR9 after R8's trailing-stderr/invalid-JSON-shape findings. Its logging
  regressions and17 read-path evidence do not establish successful operational qualification. Both remain held.
  Exact staging/launch preparation and R40 physical-control repair continue independently. No integrated,
  physical-admission, six-hour or registered launch GO is asserted; all existing jobs remain untouched.

### 22:53Z held-host diagnosis closes without admission

- Held-host owner finishes clean at110e58072ee8fa593bb028f8c32b9a79e4db9ec3. R9 accepts diagnostic-only source
  8cce3825b71545739ae8603669f5cf4930d9c3cb, wrapper SHAf5c93b4082a0700280b90d2ed7fae591808403839579775b25b71474ec1dbb73.
  It fixes retained trailing output after timeout and classifies unusable parsed JSON.24 owner-admitted CPU
  checks pass. The operational wrapper, trainer, configs and watchers remain unchanged; the patch is not installed.
-16's original discarded sampler stderr/return code/timing remain irrecoverable, with128 native exit fixtures
  unable to reproduce it.17 retains buffered/direct read disagreement, including a direct-read difference.
  Neither hardware cause nor trusted mitigation is established. Both remain HOLD. R9 authorizes no operational
  qualification retry, training, replacement or resume; no such action occurred. Every new fixture job is gone.
- Exact source/config pins and evidence are in jobs/clasher/supplemental-bc-20261022/held1617-causal-r1/
  implementation-handoff-r1.json and review-r9/REPORT.md. Future operational use requires distinct reviewed
  source/config pins, causal host qualification or accepted integrity mitigation, and fresh admission. No diagnostic
  result or subsequent clean hash scan is represented as clearing a hold.

### 22:55Z R40 local test cleanup wait removed

- Parent finds the R40R5 implementation child waiting on approval for a command-substitution rm of test
  directories. Parent withdraws that unexecuted step by interrupting only the local child, preserves all partial
  source/evidence, and steers the reactivated R40 owner to a fresh test-attempt directory. No deletion approval
  is requested or bypassed, no candidate is treated as frozen/passing, and no operational process is signalled.
- R40 retains sole09/12 ownership and must finish the narrow repair, refreeze exact artifacts and obtain fresh
  independentSol-high review before any SSH/GPU attempt. Its math, workload/observer deadlines, lease and
  exit/reap/GPU-free requirements remain unchanged. Any Claude child uses assistant_ui directly; Sol-high
  coding is already authorized. Existing BC jobs and watchers remain untouched.

### 22:57Z combined369-check CPU suite passes

- Corrected exact7823423a39f3bdcf85f9f3afac4dced7842b9db5 composition passes all369 checks in489.82seconds,
  exit0, with no skips/deselections. Source remains clean. Log CPU-SHA is
  6b5a4ba4a21400f4d65381d839535e88ca4abf8855156c9a63a47011bc7d5390 at
  jobs/clasher/rl-composition-20261022/cpu-tests-fixed.out. Component-map SHA is
  f678cecb4ee4135c91e63f147af492ffd2dc5c4f7bf17d20e8ceadf19a0ea1ee. R52 receives the retained result.
- Passing CPU composition does not replace independent integrated review, physical/staging/lease admission,
  actual six-hour exposure or launch receipts. No source landing, run-pin replacement or remote job follows
  automatically. Qualification remains pinnedfe6; six BC seeds and all holds remain unchanged.

### 22:59Z R52 integrated GO; exact reviewed stack landed

- R52 gives narrow integrated source/code/config eligibility and landing GO at7823423a39f3bdcf85f9f3afac4dced7842b9db5,
  with no blocking findings. It verifies the retained369-pass suite and fresh producer/provenance/attack/audit
  and input-closure probes, preserving all scoped evidence limitations. Existing queue/FP64 proof is eligible
  for rebinding, with no new numerical run justified solely by this composition.
- Parent lands the exact nine-commit stack on current main asf7b93f6d8 throughf512eeb47. Comparison against
  the reviewed tree differs only in accumulatedPROGRESS.md notes. The complete pretrain Python aggregate
  matches9621646fe51f3d9fce549d1540dc2d0d6c1f8c7ee891aeca7cf5151b08deb187. Source is clean; no runtime
  alteration or redundant suite rerun is required for this byte-identical landing.
- R52 explicitly does not approve staging, physical/lease admission, operational or registered launch, promotion,
  deployment or completed exposure. Current qualification source/component/run pins remainfe6 and are not
  silently replaced by this main landing. Operational-package preparation and R40 physical-control repair
  continue under their existing owners; actual physical measurements and the separate six-hour run remain open.
- Registered production inputs remain the separate frozenR44-v2 candidate with all5400 paired assignments and
  historical exclusions; its GO/precision/league placeholders remain absent. Six BC jobs, all watchers and the
  16/17 holds are unchanged. The evaluated41kM947af5cb anchor remains the best live handoff.

### 23:02Z qualification package frozen for operational review

- Sol-high owner freezes implementation249a74549e652172be463511ea5d3779245e798b in a clean worktree.
  Package jobs/clasher/rl-qualification-launch-20261022/freeze.json SHA is
  82e2a7bcbc02b504cba25150b9961078ff374d2d6836a425669f5f24900bb471.29 CPU/mock checks pass underPython3.12.12;
  no SSH/GPU/engine, current-job scan, admission, lease mutation, watcher restart or BC change occurred.
- The package retains exactfe6 source,96 files including83Python files, and all402 prepared inputs. It reserves
  three processes/4GiB PSS for CPU source/input stages with300/1800-second bounds, then40 processes/48GiB PSS
  and a25200-second total wrapper bound for the separate soak. Driver readiness-based six hours and128-update
  ceiling remain unchanged. R37 retains complete ownership/resource/reclaim enforcement and exact cleanup.
- Fresh independentR53 reviews the operational code and authority schemas. Actual R40 release/physical evidence,
  final configs and launch receipts are still absent. Code/contract eligibility cannot substitute for those concrete
  bindings, transport/staging, fresh lease/resource admission or real exposure. Parent will request the concrete
  authority check when real inputs exist. No GO JSON or operational activity is inferred from implementation tests.
- R40R5 repair is frozen atb13f0a864fadd8088b83900ffa1738027804c4f658b0345d4de165aa1eb5b744 after38 checks,
  including final-query start after independently observed reap. Its fresh independent audit is active; no SSH/GPU
  attempt or per-host release has yet occurred.09/12 stay with that owner.16/17 remain held; six BC seeds continue.

### 23:23Z actual R40 outcomes, seed2008 failure and operational blockers

- Actual unchangedR40 probes ran after exactR5 operational GO: M09 started23:04:41Z, S10012 at23:05:20Z.
  S100 passes with10,405MiB sampled physical process peak and38,013MiB sampled minimum free. M math passes
  with probe exit0, but monitoring fails on process-environ EACCES plus an unbound GPU row; monitor/attempt
  exits1/14. Valid attributed21143MiB, raw21145MiB and sampled device-used21164MiB are retained facts, not a
  passed M process-peak proof. No retry occurs. Both exact trees are reaped and GPUs restored;09/12 ownership
  is explicitly released at23:05:04/23:05:33Z. Raw evidence is r40-physical-0912/results-and-release.json.
- Read-only M forensics reproduces environ EACCES during ordinary exit in64/64 local CPU children, and in an
  alive nondumpable control. The exact remote permission cause remains unproved. Original attribution throws
  before returning all six identity fields, permanently latching failure. Missing remote partial stat/dumpability
  records cannot be reconstructed. A CPU-only lifetime-identity proposal is being prepared for fresh review
  and explicit authorization before any acceptance change or another GPU measurement. Original M stays FAILED.
- Host14 seed2026102008 is no longer running: fresh23:12:10Z exact-process/GPU check finds no trainer and no
  GPU process. Its retained log ends after finite step6500 at a one-second sample_resources communicate timeout.
  No successful summary/exit exists. The run is resource-failed and excluded in full from selection, with no resume,
  replacement or retry. Earlier six-running reports relied on the last startup/progress check and are superseded.
- Fresh23:22:59–23:23:02Z checks verify exact PID/start/boot on01/02/08/13/15.01 is epoch2/step74500,02 has
  finished epoch1 and entered epoch2,08 is epoch1/step53000; none has completed training.13/15 remain alive.
  A bounded read-only monitor PID970317/start250115076/boot5f666b17-9407-450e-a537-8a4b0838a8c2 checks
  those five hosts once per minute, uses one bounded SSH per host, never retries a failed connection, never
  signals/restarts workload processes, and exits on unexpected stop. State/logs are in
  jobs/clasher/pretrain-status-owner-20261022/. Its completion notices do not authorize selection or promotion.
- R53 operational package review is NO-GO for twoP2 defects: exact-reaping success can omit an adopted zombie,
  and failure before attempt persistence can allow readmission. A fresh isolated Sol-high owner fixes both with
  real owned-child and durable-intent regressions; no staging or S100 authority is issued. Another new-only fixture
  prepares actual-engine terminal recycle hash comparison for review before any real engine execution. Existing
  fixture/component evidence is not silently upgraded to real recycle or six-hour proof.
- A future-only persistent BC sampler candidate reduces per-poll interpreter setup while retaining strict one-second
  cadence/deadlines, all R37 resource thresholds and fatal stale/failed-sample handling. It is not a claimed cause
  of14/16 failures or permission to clear holds. No candidate is installed in running jobs.16/17 remain held;
  the 394-path input blocker in the old lease-owner handoff was already closed locally by R49, not reinstated.

### 23:28Z concrete S100 physical draft and independent follow-ups

- Parent freezes a non-launchable S100 configuration draft using its actual passing monitor and two-step workload
  records. Physical process bytes are10,910,433,280 and allocator peak9,609,150,464. Raw source/result/identity,
  trace, drain, release and R5-review copies are retained under
  jobs/clasher/rl-qualification-receipts-20261022/S100-physical-draft1/. Draft config SHA is
  377216270a30102b9f6b84e26994a453c65dafb60fe9e6fa26bff105d7511a8b. Only precision evidence and GPU-admission
  fields differ from the frozen prepared config. Missing launch gates remain missing; no release/review GO is issued.
- Fresh isolated work prepares: the two R53 package corrections; a new-only actual-engine terminal recycle parity
  fixture for review before execution; the explicit CPU-only M lifetime-identity protocol proposal; and a future-only
  persistent BC sampler that preserves one-second freshness/deadlines and all resource thresholds. None is installed
  or run against operational workloads. No cause, host clearance, retry or passed gate is inferred from proposals.
- To put useful reviewed measurement work on idle14, a separate owner prepares an unselected full-DEV preview
  job for finalized primary epoch files. It must reuse pinned metric code, exclude FINAL, write no selection/anchor
  output, and leave primary training/selection rules unchanged. No transport/GPU/admission occurs before fresh
  review and exact checkpoint/input/resource pins. This does not replace or resume failed seed2008 or clear16/17.

### 23:35Z operational fixes enter independent R54 review

- R53 fixes are committed at 301248e771bb093928b683aa8cb9ff38eb42c1da, directly atop the reviewed package base.
  The new freeze SHA is 3f4194c104fe060945f6fe2c012e2ab27dfb48d796fb34b3587e8181ee80cf0e. All 47 CPU checks
  pass, both new regressions fail on the base, and all 11 authority attacks reject. R54 independently reviews
  adopted-child reaping and durable intent before admission. The original package, source and inputs stay unchanged.
- At 23:34Z the read-only monitor verifies exact PID/start/boot for all five remaining BC trainers. Primary 01/02
  are in epoch 2 at steps 80000/79500; 08 is in epoch 1 at step 57000. No training summary has completed.
  Seed 2008 remains failed and excluded. R54 is code/interface review, with no staging or launch authority implied.
- Finalized primary epoch-1 files from 01/02 are copied read-only to
  jobs/clasher/interim-dev-preview-inputs-20261022/ep01-parent-collection/. Both source hashes, sizes, inodes and
  modification times match before/after transfer and the local copies. The receipt pins source and snapshot.
  These are unselected preview inputs only; no host14 transfer, admission, GPU work or selection occurred.

### 23:37Z M lifetime-identity proposal enters R55 review

- The CPU-only proposal freezes at dcb5add59857c2a46fe7a69ea68108437642cf522a76c6d0c33df8144eecc27d.
  It passes 75 behavioral checks and preserves all 2420 original files. R55 independently reviews its exact
  identity and drain semantics. A hard operational stop remains enabled; no remote or GPU attempt occurred.
- The proposed gate would allow prior token provenance only for a continuously held, previously bound pidfd
  with matching fresh identity and an unreaped PID, when current environ reads return EACCES or EPERM.
  This cannot prove inaccessible current tokens or executable contents. That explicit policy expansion needs
  coordinator authorization after review, followed by review of a fresh operational package before one new
  bounded M measurement. The original M attempt stays FAILED; S100 PASS and all running jobs are unchanged.

### 23:41Z R54 durability blocker and installed-path correction

- R54 remains NO-GO for 301248e: a concurrent winning claimant can hand off before another creator syncs an
  intent ancestor's parent. The original missed-zombie defect is closed, including 20 independent nested-orphan
  drains. A fresh isolated owner fixes ancestor durability and retains the exact reaping and single-attempt rules.
- Read-only checks at 23:40:01Z on 12 and 23:40:20Z on 09 establish that the package's expected R37 path is absent.
  The deployed path on both is repos/clasher-pv1-lease-r37-7851936824/lease_supervisor.py, with exact reviewed
  SHA 0613d6db62371eb197bb5d41cbf342b57f1998ddeb91e04c7c5ab2be36ac0ffc. The sole package owner will pin that
  canonical path, retaining mandatory hash validation and no fallback. Watcher 12 remains live at its exact identity;
  its lease is active with reclaim false. These observations grant no admission or authority.
- R56 independently reviews the frozen unselected DEV preview at 487304d190366e7953b5ed8443c77f39349d77ee.
  R58 reviews the future-only persistent BC sampler at 6f7e9d4f5def382bae89b074c6c3077904954fa4 after 113 CPU
  checks and eight subtests. Neither candidate is installed or operationally launched. Seed2008 remains failed and
  excluded, hosts16/17 remain held, and no existing training source or selection rule changes.

### 23:56Z reviewed package landed; concrete DEV operation in review

- R57 gives narrow code/interface GO at 4b9c3892c0211db87859b91d1ab2bbcc1afe2b56, freeze
  b93c403020a4e6e45d8656ac00e441f196e274a5bb02e4092f30260fe4e513c2. The ancestor durability race and
  installed R37 path mismatch are closed; 49 tests, fresh race/handshake/authority and orphan-drain probes pass.
  Parent lands the exact reviewed package as 442d44ea6, 30d70fd69 and 8e6090c97. R56's exact reviewed DEV helper
  lands as 0fc86eb12. Both landed directories are byte-identical to their reviewed trees. No source/run pin is
  silently replaced, no redundant suite rerun is needed, and landing grants no operating authority.
- R56 gives code and finite-plan GO for the two unselected ep01 previews after 16 independent CPU checks.
  A concrete local transfer package contains 83 files in 79237120 bytes, SHA
  60f1945483293ea7b48d0012dee573557057ea46e0d5a2177ccfc9a000153890. R61 independently reviews staging,
  transport and the exact launch protocol. Review freeze SHA is
  2d887222fdfa549c5fe6779f7eca6b6da4b7d795fabf96d90870ddbed52e9376. No remote staging or GPU admission yet.
- Fresh 14 preflight at 23:48:46Z proves the original failed training tree drained, all historical jobs gone,
  exact watcher live, active unreclaimed lease, no HALT/release or journal issues, one counted process, 8.71 MiB
  PSS, 118.82 GiB available, load1.54 and 47.5254 GiB GPU free. A first read-only inspection stub omitted its
  logs attribute and falsely classified records uncertain; corrected v2 preserves that failure and changes no
  remote state. Actual admission will independently repeat all checks. Local preparation ops-r1 also retains
  its overly strict archive-membership assertion failure; ops-r2 extracts only the reviewed 73 mapped files.
- R55's lifetime checks pass but the frozen CPU candidate is NO-GO because some entrypoints precede its stop
  and Python optimization removes its assertion. A separate corrected freeze
  b4bf9e4304d3c09fd95538b4f9015c7a7c0c532318c4ec5932dd5f3bad776649 enters R60 review with 75 behavioral,
  30 adapted and 198 full-file containment checks. No identity-policy change or new M attempt is authorized.
- R59 rejects the terminal fixture for tower-level mapping, unavailable pidfd APIs, post-done monitoring and
  whole-frame deadline defects. A new isolated owner fixes these before review or real games. R58 rejects the
  future persistent sampler for late child death accepted as success and cached bytecode bypassing source pins;
  a separate isolated owner repairs both. Neither rejected candidate is installed in existing jobs. Seed2008
  remains failed/excluded and 16/17 remain held. Actual terminal parity and six-hour exposure remain unrun.

### 2026-10-23 00:04Z actual DEV preview admitted on 14

- R61 gives conditional GO for the exact ops-r2 staging-plus-one-preview protocol after eight supplied CPU
  checks and 13 independent verification groups. Parent rehashes every frozen constituent and performs fresh
  lease/watcher/ownership/resource/no-prior-attempt checks before each admission. Exclusive intents are fsynced
  before SSH using the reviewed directory-walk/file-publication functions. No ambiguous admission is retried.
- CPU stage admitted 00:00:45Z on 14, PID2241140/start18362200, token26cabf0a43784f44a9b8f7a4e1e63c24.
  All 83 transfer files and all73 source/6241 store/20303 environment entries verify. Stage completes00:01:04Z;
  R37 records exact tree gone00:01:06Z. Parent independently verifies the receipt/token and no survivors before GPU.
- One finite DEV preview admitted 00:02:13Z, rootPID2249000/start18371001,
  bootbfd7788a-d4d1-4687-9761-c462114e8849, token3987ec1332d846009e732f452c65bcfc. EvaluatorPID2249004 is
  observed on the GPU at00:02:52Z with869MiB while initializing/loading. No completed metrics exist yet.
  The fixed two ep01 files, full2332353 DEV rows, noFINAL/noexport/noselection scope and all reviewed limits hold.
- Receipts/intents/fresh preflights are in jobs/clasher/dev-preview-20261022/ops-r2/. Output is
  jobs/clasher/dev-preview-20261022/outputs/primary-ep01-r1/unselected-dev-preview.json on14. R37 and the
  original guard own resource/reclaim handling; the six-hour timeout is not an extension of earlier lease bounds.
- A distinct read-only observer on05, PID1433370/start250360244/boot5f666b17-9407-450e-a537-8a4b0838a8c2,
  checks once per minute and exits on completion/failure, bounded23400seconds. It never signals, restarts or
  resubmits jobs. Evidence is ops-r2/observer/; a usable readout still needs parent validation of guard exit0,
  no timeout/reclaim/resource breach, exact drained job, complete finite metrics and unchanged input hashes.
  All five BC training jobs and both held hosts are unchanged. This action selects or promotes no model.

### 00:10Z coordinator authorizes one new M measurement; BC readiness proceeds

- R60 gives GO solely for the frozen CPU proposal's suitability for the policy decision. All startup containment
  barriers hold in ordinary/optimized entry probes; the lifetime identity algorithm and coupled drain controls
  remain unchanged. It supplies no operational package approval or production RL authority.
- Coordinator explicitly approves the R60 lifetime rule plus exactly ONE new bounded M memory measurement,
  under existing lease caps and reclaim watchers, with exact new operational-package review still required.
  Original M stays FAILED. Parent durably records the verbatim decision in jobs/clasher/r60-parent-authorization-20261023.json,
  SHA32269e4e1519451f2300ac5e53cb2bf03c6b0faf246066f39c75ad53b57d5cf1. No further approval is needed
  for this same scope. A sole owner prepares a fresh package for independent R64 review; it has no host reservation.
- Parent forwards both actual old R40 SSH releases into the already-reviewed 09/12 CPU-stage release gates,
  using the pinned original results-and-release artifact. A separate owner advances reviewed CPU staging and
  extra BC launch readiness for seeds2004/2005 now, without waiting for the new M measurement package.
  Training on 09/12 still requires its own exact config/launch review and fresh completed CPU qualification;
  the prior R5 GPU approval covers only13/14/15. No failed or held job is retried or silently cleared.
- Host14's distinct reviewed DEV preview remains independently observed. The five BC runs on01/02/08/13/15,
  failed/excluded seed2008, held16/17, scientific settings and live M947 handoff are unchanged.

### 00:13Z 09/12 CPU extension enters independent review

- Already-reviewed 09 CPU source stage was admitted exactly once at00:09:49Z, PID1746979/start250392925,
  token4e8bcae4ef114db3a2dba689f56a8dff. Fresh source, watcher, lease and aggregate checks passed, supervisor
  cache was absent, and six-process/4GiB/CPU0-31/nice15/GPU0 limits hold. Environment extraction is underway;
  12 follows after09 under the reviewed one-host-at-a-time staging procedure. No GPU is reserved.
- The sole BC owner freezes a separate byte-pinned install/probe extension under readiness-0912-r1, with
  isolated source capsule repos/clasher-bc-0912-r65-20261023. Launcher SHA is
  d5924216f04bd3c5f915129981ba794b3df1d5859fd21be351c53d38c6da5e6b. Config09 SHA is
  c413390c3fcab807847e782491cdb4bbad1c0c2473c4b800f3fd121629732401; config12 SHA is
  2d06b67ecad57172d8ad639941c688a00b0301ef14e91a87d490d43834eb5b96. OriginalR5/shared gates and all
  running artifacts stay unchanged; the source capsule is hash-bound rather than represented as a Git worktree.
- Fresh independent R65 reviews exact CPU install/probe eligibility, including release/watch/cap/no-cache pins,
  isolated review-gate and no-retry intent. No new install/probe is authorized until that review returns GO.
  GPU training requires a separate exact review after fresh completed CPU qualification. No R58 candidate code
  or scientific/optimization change is introduced, and held16/17 are not cleared.

### 2026-10-23 00:34Z completed CPU staging and fresh review gates

- Both 09/12 source stages completed exactly once: 09 admitted00:09:49Z, completed00:14:07Z,
  gone00:14:28Z; 12 admitted00:15:12Z, completed00:19:28Z, gone00:19:29Z. Each verified all73 source,
  6241 store and20303 runtime files plus CPU imports. No CPU memory qualification or GPU training ran.
- R65 rejects the separate install/probe extension for missing directory durability before transport and a cache
  guard that missed Python3.12 bytecode. The original frozen package remains preserved. R2 changes only its
  launcher: SHA53322bbf1d3a6d474022a18d8c79fe37d2fe5f8e67bdc1d8e435eef2a04fe079. Exact R57 directory
  publication and all canonical supervisor cache tags/legacy paths now enter fresh independent R67 CPU-only
  review. Frozen extension-pins SHA4d7a62bd9fd069151807a0aca7d531c6e34927da04e53b630b00d4038da9fa06.
  All741 prior protected files and the original one-shot sampler remain unchanged. Training still requires
  actual completed CPU qualification and separate R66 review. No measurement reservation delays this route.
- Coordinator-authorized ONE new M measurement package enters independent R64 operational review at freeze
  cdb29d507bf69809333ae43f3ef71841c92737c96c3e5c956963dba5a7f79fd5. Parent verifier passes all52 manifest
  entries and73 sources; no new remote attempt, authority receipt, intent or exposure exists yet. The original
  M measurement remains FAILED. Historical-token lifetime policy approval is confined to this new measurement;
  it grants no production RL authority and cannot displace a ready BC admission.
- R62 rejects terminal parity execution because a detached adopted child can escape ownership and falsely
  yield a reaped-success receipt. A fresh isolated owner repairs that gap before any calibrated game. R63
  rejects the future sampler because delayed duplicate/partial shutdown stdout can still produce success.
  Parent reproduces all four train/probe cases and prepares a separate repair, preserving the current BC code.
  Actual terminal game count remains zero; six-hour exposure and registered RL remain unrun.
- The 00:29Z read-only checks show all five BC jobs01/02/08/13/15 active with matching PID/start/boot and no
  failure receipts. Host14's unselected DEV preview remains running without a complete report. Held16's new
  CPU qualification plan is frozen for future R68 review only; 16/17 remain HOLD and seed2008 stays excluded.

### 00:38Z R64 refuses exposure; R63 repair frozen

- R64 exact operational review is NO-GO. A transient readable foreign GPU row can evade the monitor's failure
  branch, and missing/negative/NaN GPU reservation fields can evade competing-GPU refusal before exposure.
  No remote dispatch, intent, authority receipt or measurement ran. A separate owner repairs both under fresh
  R71 review. Parent narrows the earlier monitor-byte-identity requirement only to correct the foreign-row
  refusal promised by the existing contract; all lifetime, measurement, cleanup and timing controls remain pinned.
  Canonical R37 is unchanged. One new M measurement remains authorized but unconsumed, without host reservation.
- The future sampler repair is frozen at9cfed645b5164913283f285090fd1898bedc2b96 in a separate worktree.
  Its terminal acceptance requires stdout EOF and no observed bytes beyond the single bound ACK, even after
  the retained prefix fills. Four original coupled failures become passes; nine added checks pass. The retained
  four suites pass152 tests plus8 subtests, and all41 original independent R63 probes pass. Evidence and exact
  hashes are scratch/pretrain-v1-dev/r63-root-fix-20261023/HANDOFF.json. No operational eligibility is claimed;
  fresh independent R70 review and future caller/config/qualification gates remain required.
- R67 exact CPU install/probe review is still running. Terminal cleanup repair remains isolated and unqualified.
  R68 review of held16's frozen CPU plan is pending; no held-host retry or GPU clearance follows preparation.

### 2026-10-23 00:49Z actual 09/12 CPU qualification and completed DEV readout

- R67 CPU eligibility GO closes both R65 blockers at launcher53322bbf1... . Parent pins the actual report and
  authorizes only one install then one probe per host, retaining all fresh remote guards and no-retry intents.
  09 install admitted00:39:58Z PID1845236/start250573871 and gone00:40:28Z; probe admitted00:40:57Z
  PID1848486/start250579782 and gone00:42:28Z. Its completed child1849904/start250582232 matches boot,
  seed2004 and configc413390... . Conservative bound16.2984619140625GiB plus2GiB fits30.5GiB.
- 12 install admitted00:40:59Z PID953472/start908926776 and gone00:41:29Z; probe admitted00:42:14Z
  PID957902/start908934330 and gone00:43:59Z. Completed child959335/start908936643 matches boot,
  seed2005 and config2d06b67... . Bound16.298431396484375GiB plus2GiB fits30.5GiB. Both full-store
  probes cover23498034 rows/TRAIN18811143/DEV2332353, report no stop/failure and have drained identities.
  Parent retains raw observations/receipts and validation in supplemental-bc-20261022/r67-actual-20261023/;
  R66-CPU-PROOFS.json SHA6fd97f77d390e9da6e14e4544d2139e11e83360e6c6e1dc672ea7f1b618f443e.
  Fresh independent R66 training review is active; neither GPU training command has run yet.
- The separate14 ep01 DEV preview completes guard exit0 at00:36:53Z and R37gone00:37:06Z. Parent freshly
  verifies no surviving identities/stop file/stop reason and the exact report and checkpoint hashes. Full2332353
  DEV rows give raw jointNLL .320051/.320066, conditional card accuracy .630403/.629961, tile accuracy
  .247037/.245537, ECE .003413/.001602 and valueBrier .467180/.455122 for primary seeds2002/2003.
  These are unselected ep01 diagnostics; FINAL remains unused, no calibrated checkpoint was exported, and
  current evaluated M947 remains the live handoff. Report SHA299dfa337d07e81762f053e003813c28ba52d20308051e5f1a4bc04f5cda5341.
- Parent collects finalized ep02 checkpoints from01/02 without changing their trainers, retaining matching
  source stats and SHA before/after transfer:2d3156f601bdffe36238de810fd06eb5420f3cf7a98a9d300b8993bd853b77b9 /
  4ab2ec987ddf0a66469616682f70573d2ea3059e16ab866d4965bc6c1af8b660. A new unselected14 preview package
  is prepared under jobs/clasher/dev-preview-ep02-20261023/ops-r1, using unchanged reviewed helper and full
  sameDEV split; exact operational R73 review remains pending. No second preview admission has run.
- R68 held16 review is explicitly deferred to prioritize ready09/12 training. Its partial report confirms a local
  startup-cache gap and leaves broader review incomplete. It supplies no GO or HOLD release. The frozen plan
  and all failed evidence are retained; any fix and later review must use a new revision/round.

### 2026-10-23 00:59Z both reviewed 09/12 M seeds launched

- R66 gives GO only for09seed2004/12seed2005 at exact R67 source/config pins, after58 focused virtual cases.
  Final report SHAa3066e895a99b9206af6dffdf1d82827442567bd61b7ed8215c97ceb7670a970 is copied byte-for-byte
  into the isolated r2 approval and combined-review gate. Parent freshly rehashes all73 source/20303 runtime/
  6241 store entries and75 installed adapter-tree files on each host; both audits pass00:56:53Z. CPU receipts
  remain fresh. Actual launch then repeats lease/watch/ownership/cache/GPU/resource/unused-output checks.
- 09 training admission00:57:28Z, wrapperPID1902003/start250678820, tokenprefixe8af472d;
  actual seed2026102004 trainer starts00:57:46Z PID1903019/start250680614,
  boot28e4a86a-da6a-4604-8ff0-2f90af977c0e. 12 admission00:57:29Z, wrapper1010689/start909025763,
  tokenprefixde08c7aa; seed2026102005 trainer starts00:57:46Z PID1011736/start909027536,
  boot491bec58-ab4e-4390-b54a-7c8f60e85340. Both run the exact reviewed M/drop.1/bf16 invocation to completion.
  No retry/yield/resume path is used. Allocation is39GiB GPU/30.5GiB PSS/eight slots per host under R37.
- Exact launch, parent gate and preflight observations are retained in supplemental-bc-20261022/r67-actual-20261023/;
  R66-ACTUAL-LAUNCHES.json binds both admissions. Seven BC jobs are now active on01/02/08/09/12/13/15.
  Historical4300rows/s implies about9.7h for eight TRAIN passes plus DEV/calibration, subject to early stopping;
  first measured blocks for09/12 remain pending. Source/data/scientific rules and primary three-seed selection
  remain unchanged. Failedseed2008 and held16/17 stay excluded. No new live checkpoint is selected.
- A distinct read-only observer covers only these two new jobs, avoiding overlap with the original five-host
  observer. Owner05 PID3537817/start250692897/boot5f666b17-9407-450e-a537-8a4b0838a8c2, singleton lock,
  54000-second bound, once-minute sequential SSH checks, no signals/restarts/admissions. Output is
  jobs/clasher/bc-0912-readonly-owner-20261023/{owner,status,samples}.json; completion is advisory and requires
  parent review of summary/exit0, generation-bound drain and unchanged source before supplemental selection.
- The authorized new M memory measurement has no dispatch or exposure and cannot displace these jobs. R71
  reviews its corrected package, but its fixed09 GPU target is occupied. R69 terminal fixture and R73 fresh
  ep02 DEV preview reviews are also active. Actual RL and six-hour qualification remain unlaunched.

### 2026-10-23 01:06Z finite new-seed losses; ep02 compatibility correction enters R74

- At01:04:17Z both new trainers reach step2500 with finite losses. 09 reports4385rows/s and9.98GiB reserved;
  12 reports4313rows/s and11.73GiB reserved. These are partial training peaks, not complete-workflow memory
  evidence and not permission to co-locate a learner across later DEV/calibration phases.
- R73 rejects the first unselected ep02 packet before operation: its unchanged helper requires the original root,
  permits only ep00/ep01 and expects a different parent-receipt schema. Parent missed those explicit bindings
  during packaging. No second preview ran; all98 frozen files and the original collection evidence remain intact.
- Separate ops-r2 corrects only the helper's private JOB root and explicit finalized-ep02 allowlist, while preserving
  every scientific/source/checkpoint/DEV/metric function AST except that epoch predicate. The raw collection
  receipt remains byte-identical; an explicit parent normalization derives path/size/hash/inode/mtime fields from
  captured pre/post evidence and recomputed local hashes. Scope flags attest read-only collection/DEV-only
  diagnostics, not absence of the running source trainers. Raw and normalized receipts are both transport-pinned.
- Both actual ep02 checkpoints pass complete CPU metadata, finite FP32 weights, configuration, feature and
 8756421-parameter validation. Twenty binding/format checks and eight stage CPU/mock checks pass, including
  the original three R73 negatives and genuine new-inventory/receipt/output positives. Scientific metric math is
  unchanged. Fresh R74 reviews freeze1bb57a5b0ace1cd744b9045307c1d7a6566e36fe9a908a3eacdff53b70b2c12b
  under jobs/clasher/dev-preview-ep02-20261023/ops-r2. No staging, admission or GPU action is authorized yet.
- R69 terminal cleanup and R71 M measurement re-reviews continue. The R70 future sampler review and held16
  fixes remain queued behind launch-critical work; their candidates supply no operational approval. Seven BC
  trainers, failedseed2008 exclusion, 16/17 HOLD and evaluated M947 live handoff remain unchanged.

### 2026-10-23 01:25Z R74 preview admitted; R69 engine fixture underway; R70 component PASS

- R74 gives exact code and operational-package eligibility for ep02 ops-r2, freeze
  1bb57a5b0ace1cd744b9045307c1d7a6566e36fe9a908a3eacdff53b70b2c12b. Both R73 binding failures and receipt
  mismatch are closed. Parent freshly rehashed all103 files and checked arbitrary-writer lease, exact watcher,
  all-owner accounting, old logical-phase records, source/runtime/cache and physical headroom before each admission.
  Directory-safe exclusive intents fsync every ancestor and final file/parent before transport; no retry budget.
- 14 CPU stage admitted01:23:10Z, wrapper2705863/start18856798, token4b2163be79d149538676082034b4f3c7.
  Stage child2705864 verifies73source/6241store/20303runtime files and publishes bound receipt01:23:33Z,
  then R37 records gone01:23:36Z. Fresh full-owned scan finds neither wrapper nor child; no stop marker.
- Fresh GPU preflight01:24:00Z finds47.5254GiB free and no active clasher allocation. GPU preview
  dev-preview-primary-ep02-r1 admitted01:24:17Z, PID2712380/start18863409, bootbfd7788a-d4d1-4687-9761-c462114e8849,
  token974d94d7f9cd4fcead0542b7f2a20d88. R37 charges8processes/30.5GiB PSS/39GiB GPU onCPU0–31/nice10.
  It evaluates both exact ep02 checkpoints over2332353DEV rows at unchanged batch512, with no FINAL or export.
  Historical ep01 duration suggests roughly35minutes, conditional on resource/lease guards; six-hour hard bound.
- Separate finite read-only observer05 PID2248190/start250846131/boot5f666b17-9407-450e-a537-8a4b0838a8c2
  samples once/minute for at most23400seconds. It never admits/restarts/signals. Ownership and observations live
  under jobs/clasher/dev-preview-ep02-20261023/parent-actual/{gpu-identity.json,observer/}; exact completion still
  requires guard0, finite both-candidate report, no stop/reclaim/breach, R37gone and full-owned drain.
- R69 one bounded real-engine terminal fixture started01:14:31Z on05 PID1080074/start250784327. It is
  currently executing S100 after both M-seat persistent/source/successor groups exit0. No full result or parity
  acceptance yet. Output is scratch/pretrain-v1-dev/rl-readiness/terminal-recycle-reviewed-attempt1; admission
  and log are jobs/clasher/terminal-recycle-parent-r69-20261023/. Fresh R75 post-execution review remains required.
- R70 gives component PASS for future persistent sampler9cfed645b5164913283f285090fd1898bedc2b96, with78fresh
  independent checks and no remaining blocker. It supplies no caller/runtime/config/seed or operational approval.
  All seven BC trainers keep their original sampler. At01:22Z new09/12 seeds reach12000finite steps, about4300rows/s.
- The single approved new M physical measurement is unconsumed. Its fixed09 package defers to BC. A separate
  fixed14 binding is being prepared for fresh R77 review after the preview, sharing the same global one-attempt
  budget and requiring fresh arbitration. No GPU reservation or displacement. Held16 fixes are preparation only;
  16/17 remain HOLD, failed2008 excluded, M947 anchor unchanged. Six-hour soak and registered RL remain unlaunched.

### 2026-10-23 01:31Z actual terminal parity fixture completes; R75 post-review active

- The single admitted R69 CPU fixture exits0 after16 actual calibrated-engine games across M/S100 and both
  seats, comparing persistent two-game play against terminal-only source/successor handoff. Its result is
  completed-parity-pending-independent-postreview; no further engine attempt was launched. All12 worker
  exits are0 with no cleanup error, unresolved child, retained pidfd or survivor, and all4 canonical one-use
  claims exist. Fresh parent checks exact captured PID/start identities and the standalone parent are gone.
- Retained result SHA3fa1495efd32aef22aa85efa55d207fce2f0a25e4c6929d89c1ba42644fd8982. The completed
  artifact index binds2739 files/61502666 bytes, SHAedfd7d1b658107d93e993ace328b1fbfab67da5aaa34de63a24c4b8840351167.
  Parent evidence is jobs/clasher/terminal-recycle-parent-r69-20261023/{parent-completion-check.json,
  completed-artifacts-index.json}; original outputs remain unchanged at the reviewed-attempt1 path.
- Fresh independent Sol-high R75 reviews actual source/input/receipt provenance, emitted arrays and journals,
  bitwise comparisons, counters and cleanup. No additional engine execution is authorized by that review.
  The result retains engine_resume_qualified=false/process_resume_qualified=false, zero optimizer/science
  steps and promotable=false. Even a terminal-parity PASS would not establish midgame engine continuation,
  six-hour/32-actor memory stability, physical GPU admission, production precision/RL or deployment.
- The ep02 preview on14 continues under its finite read-only observer. Seven BC jobs continue independently;
  no selected120k anchor or replacement live handoff exists. R77 fixed14 measurement package preparation
  and held16 CPU-package repairs are separate, unactivated work.

### 2026-10-23 01:44Z R75 bounded terminal-only parity PASS; R76 full held16 review requested

- Fresh independent R75 recomputes all128 publication manifests/2432NPY arrays and every binary journal,
  features/masks via production collation, rewards/bootstrap/time charges, command hashes and transfer ledgers.
  All8 paired games are bit-identical across16 actual games/11248 sampled rows and4 terminal handoffs.
  The naturally rejected Cannon tap preserves action1916, original FP64logp, actor mask, reward0 anddt5,
  matching persistent/source row593 without resampling. All12worker exits0; parent-supplied fresh exact
  identity-gone evidence is explicitly distinguished from independent sample reconstruction. No transient
  parentRSS/cadence proof is invented. See TERMINAL-PARITY-20261023.md and immutable SOL-R75.md.
- The three fixture files land byte-identical to reviewed9fa from a fresh worktree. Actual execution stays bound
  to9fa/source69402fe3; landing on main does not qualify a different composed package or permit a retry.
  Terminal-only frozenweights samehost/boot scope only, no midgame/6h/GPU/precision/productionRL approval.
- Fixed14 M memory package freezes3edf8c879aa4f86e16c8247d3f6dd5b40058049d62652abc9ee6623cd3a3c4d9 and
  enters fresh R77 review. Its required pinned Python environment is absent on14; separate bounded CPU
  staging needs exact review and later parent gates. Central05 global intent is still absent/unconsumed.
  All valid old/new host dispatches must serialize through that same durable exclusive central intent; old09
  exposure paths are host-local historical bytes, not distributed storage. Parent will not activate old09
  while BC owns it. New14 adds central exposure under both remote locks before spawn. No reservation.
- Held16 repair package is frozen and enters NEW independent R76 FULL review, not resumed partialR68.
  Startup uses verified source buffers, and earliest total initialization/cleanup alarm covers the old gap.
  Author42tests on each interpreter/60 cache cases pass with219protected paths unchanged; an early
  fixture's missing terminal-status evidence is retained and excluded. No actualCPU operation or HOLD
  release exists. Host17 remains out of scope. Seven BC and14ep02 preview continue unchanged.

### 2026-10-23 01:56Z R77 NO-GO before operation; stage repairs and actor-cost read

- R77 rejects fixed14 package3edf8c... before any operation: CPU-stage admission abandons identities its
  child still charges as live wrappers; source-side transfer lifetime/interruption cleanup is not proved;
  common.load_r37 hashes one read and executes another. All408 supplied tests pass but miss these paths.
  Separate M-physical-host14-r77-fix-20261023 preparation addresses all3, preserving every old package
  byte/mode and the unconsumed global M opportunity. Fresh R78 remains required; no authority issued.
- R77 accepts centralized one-dispatch intent under the explicit only05-to14 authority rule. Legacy09
  dormant entrypoints do not themselves enforce that universal invariant. They receive no authority,
  permit or transported review context; no physical distributed-storage claim is made.
- A read-only timing extraction from four persistent frozen-FP64/scripted-pressure games per size on05
  gives M mean27.4463CPU seconds/game versus S10015.6262, ratio1.7564. Our player decision CPU means
  15.4662 versus6.4829seconds/game, ratio2.3857. Whole two-game-worker wall throughput including startup,
  artifact publication and fixture instrumentation is67.88games/hour M versus87.62 S100 per worker.
  These are small scripted-pool fixture measurements, not registered mixed-pool or32-worker estimates.
  Exact raw hashes and arithmetic live in terminal-recycle-parent-r69-20261023/actor-cost-read.json.
  No HP1 CPU is requested or taken. R76 remains active; 16/17 HOLD and all running jobs stay unchanged.

### 2026-10-23 02:05Z primary ep02 DEV preview complete and drained; next useful GPU work prepared

- R74 one-shot preview ends guard0 at01:59:37Z; R37 records gone02:00:06Z. Fresh parent02:02:28Z verifies
  exact job identity, no stop marker/reason, full-owned drain, exact finite report hash and74 active-period
  events with no ending/breach. Physical free47.5254GiB and no active clasher jobs are observations at that
  time, not a reservation or future admission. The finite read-only observer exits0 and will not restart.
- Full2332353DEV raw metrics, seed2002 then2003: jointNLL0.31620049/0.31651589; cardtop1
  0.63742696/0.63747581; tiletop1 0.25511606/0.25354222; ECE0.00379290/0.00259758;
  valueBrier0.50994407/0.50664162. Same-DEV ep01 jointNLL0.32005101/0.32006629 and Brier
  0.46717979/0.45512249. Action NLL/accuracy improve while raw ECE and value Brier worsen. Neither seed
  is selected or exported. ReportSHA281f55fec476608532bb808e493ed840a126fc1c504a7f99b54462333160d58c;
  exact comparisons, final guard and provenance in dev-preview-ep02-20261023/parent-actual/.
- R76 full held16 CPU review rejects observer-descendant cleanup, first-fork identity bookkeeping and
  failure-path terminal-status draining. Separate host16-cpu-qualification-r76-fix-20261023 work preserves
  old bytes/R9 wrapper/scientific configuration; fresh R80 review precedes any actualCPU authority.
  No host16 attempt consumed;16/17 remain HOLD. M stage fixes remain separate with R78 required.
- To keep14 useful while those gates finish, a separate supplemental-seed2007/2009 finalized-ep02 DEV
  preview packet is being prepared, with bounded read-only checkpoint collection and unchanged R74
  scientific metric code. No GPU/stage/admission is authorized yet; fresh R79 review and parent gates
  are required. Whichever approved use is ready first may use14; no measurement reservation/displacement.
  Primary all-three completion/selection/game gates and evaluated M947 live handoff stay unchanged.

### 2026-10-23 02:28Z supplemental inputs complete; exact existing environment identified

- Supplemental preview ops-r1 seals blocked because its13 collection wrapper caps address space256MiB
  while its first child requests512MiB; failure precedes lease/input access. Seed2009 collection on15
  succeeds with the corrected256MiB child. This is a collector failure, not a BC training failure.
- Parent explicitly permits one additional bounded read-only13 retrieval after diagnosing that local limit.
  It uses the exact corrected15 scripts, new collection-recovery13-20261023 prefix, fresh lease/watcher/
  all-owner/source/trainer/finalized-epoch gates, and no remote writes or operational admission. It finishes
  in1.071s at02:24:35Z with wrapper2914830/start251156973 and child2914831/start251156975 on the
  original13boot; child0 and exact identity gone. Seed2007 ep02SHA111c001e5c9362f6137f37ae5297a88d39e5f885286e6eda792626dc949b80bb.
  Seed2009SHAe57cc47c6e987b33e43dd3bc9c050c64379a1c46e1fdb9c040eee4ccb1082e42. Each35061136bytes.
  Both inputs now exist for complete ops-r2 preparation and fresh R79; old blocked packet remains intact.
  No CPU-stage/GPU logical opportunity is consumed by read-only input retrieval.
- The M inventory and already-used14 BC environment map match all20303 files by exact size andSHA,
  including20302Python files and env-source-manifest. Local identity proof is retained in
  M-physical-host14-parent-20261023/existing-BC-env-map-identity.json. Historical R74 stage verified that
  complete environment on14. New M correction may reuse it read-only after fresh full-file/cache/path
  checks, avoiding a redundant5.7GB copy; R78 must review any revised binding. No runtime equivalence
  is inferred from version labels, no current remote readiness is claimed and no shared environment is changed.
- R76 fix owner1 fails capacity after partial preparation; fallback owner2 fails expired authentication.
  Both are terminal with no pending child runs. Sole owner3 uses primarySol-high/priority, inventories and
  preserves existing partials before continuing. No superseded owner is revived, no missing old fixture
  terminal status is invented. New independent R80 remains required before any16 CPU authority.

### 2026-10-23 03:01Z R78/R80 remain NO-GO; supplemental command repaired for R82

- R78 rejects M CPU-stage cleanup when retained direct Popen identity reads fail and confirms the
  source05 global nice/affinity applicability defect. Separate r78-fix preparation keeps held direct-child
  wait authority independent of discovery and restricts placement checks to source wrappers while keeping
  all-owner accounting. New exact R81 review remains required. No M opportunity or CPU stage consumed.
- R78 qualifies the earlier111-child implementation claim:111 spawn entries,110 explicit per-child reap
  entries, one failed publication fixture lacks its exact terminal receipt. Cleanup-return inference and a
  consolidated absence assertion do not supply that missing status. No survivor is asserted or old PID
  queried/controlled. The original failed evidence stays intact; fresh R78 review accounts for56/56 own
  fixture processes separately. Earlier all111 language must be read with this later evidence correction.
- R80 rejects the held16 correction: registration-first identity failure can strand a producer child, and
  malformed registration can steal an unrelated Popen's exit37 before native fork-return proof. Separate
  r80-fix preparation preserves native-return provenance and distinguishes pending registration from
  returned-PID coverage. R83 full review remains required;16/17 HOLD and zero actual16 CPU attempts remain.
- R79 verifies supplemental inputs/helper/science/archive but rejects CPU shell generation: quoting&&
  makes builtin cd receive36 arguments. Parent's separate ops-r3 fixes both build/refresh generators,
  preserving all final argument tokens while emitting cd/&&/exec as shell syntax. Eight inert real Bash
  handles reproduce old failure and verify exact args, spaced paths and literal metacharacters, all waited.
  No SSH/R37/stage/operational executable is reached. All underlying runtime files and data remain byte-identical.
- Fresh independent R82 reviews ops-r3 freeze d195f7e0ad758a300bd37df4ce839c583969852ae3f4a6722078371508cc1d0b.
  The unchanged stage explicitly fetches its immutable payload from ops-r2, not ops-r3; all provenance
  and constituent pins disclose this binding. CPU/GPU logical attempt budgets and fresh parent gates
  remain unchanged; no failed package is launched. Seven BC jobs continue independently.

### 2026-10-23 03:15Z R82 supplemental DEV preview running on 14

Fresh independent R82 gave exact code/package eligibility GO for ops-r3 freeze
`d195f7e0ad758a300bd37df4ce839c583969852ae3f4a6722078371508cc1d0b`.
The parent read the full report, rehashed the package, verified all actual
73 source, 6,241 store and 20,303 environment files on 14, and passed fresh
lease, watcher, resource, cache, ownership and duplicate gates. The reviewed
helper landed byte-identically on main `7309292d2` before operation. Immutable
payload transport still uses ops-r2 as explicitly reviewed.

The one CPU stage was admitted 03:06:40Z, wrapper PID/start
3233593/19477748, token aa86a2509bc446759140d5f14f5e9081. Its receipt completed
03:07:00Z and R37 recorded gone 03:07:06Z; parent verified complete owned drain.
No child start was captured before its exit. After another fresh admission
check, the one GPU preview was admitted **03:08:42Z**, PID/start
**3243125/19489981**, boot bfd7788a-d4d1-4687-9761-c462114e8849, token
**10bf259cd7384352aa4012e9afe6e388**. Both global phase intents were exclusively
written and file/ancestor/directory-fsynced before their SSH commands. No retry.

The GPU phase is `dev-preview-supplemental-ep02-r1`, with 8 slots, 30.5 GiB PSS,
39 GiB GPU reservation, CPU0-31/nice10 and a six-hour wrapper bound. It measures
full DEV for the retained seed2007/2009 ep02 checkpoints. Output is
`/mpac/sdicks02/jobs/clasher/dev-preview-supplemental-ep02-20261023/outputs/preview-r1/unselected-dev-preview.json`
on 14. This is an unselected preview, with no FINAL, export, or game-strength claim.
Historical duration suggests about 03:44Z completion, conditional on current load.

A distinct finite read-only observer is live on 05, PID/start
**2211640/251508328**, boot 5f666b17-9407-450e-a537-8a4b0838a8c2,
exec session 64204. Its singleton lock, exact job/input pins, 60-second cadence
and 23,400-second bound are under
`/mpac/sdicks02/jobs/clasher/dev-preview-supplemental-ep02-20261023/parent-actual/observer/`.
It cannot admit, restart, signal, or query GPU state. Its first sample at
03:15:11Z found the exact job running without a report. Completion requires
original guard0, finite unselected report with exact input provenance, no stop,
R37gone and complete owned-tree drain, followed by parent readout.

Existing finite BC observers report all seven seeds still alive on
01/02/08/09/12/13/15. At 03:15Z, primary01/02 reached epoch index5,
08 index3; 09/12 reached index1 with finite losses. No completion summaries yet.
The two sole fix owners remain active for R78 M-measurement cleanup/policy and
R80 held16 registration/fork provenance. Fresh R81/R83 review follows their
frozen handoffs. The approved single M measurement is unconsumed; original M
measurement remains failed. No six-hour soak or registered RL has launched.

### 2026-10-23 03:20Z both corrections sealed; R81 and R83 independent reviews active

The sole M correction owner sealed freeze
`6654fd353ad604e4a108a9f17a63613b36358a0249c778a493827b2b334021d5`
under `M-physical-host14-r78-fix-20261023`. It reports direct-handle cleanup
independent of discovery and placement checks restricted to exact source05
wrappers. Fresh Sol-high R81 is reviewing the full package and evidence.
The inherited raw disk paths still bind the old package root, so relocated
operational execution is not established. R81 must distinguish code closure
from concrete operational eligibility. No authority or measurement consumed.
Historical 111-spawn/110-explicit-reap evidence and the new development receipt
gaps remain disclosed, separate from the final 51 explicit primary waits.

The held16 owner sealed freeze
`be951347a5c0928d62137ae5868b530fff4c6c37c6d5fd50a2fde90d052faf39`
under `host16-cpu-qualification-r80-fix-20261023`. Registration now stages
without ownership until independent native returned-fork provenance arrives.
Fresh Sol-high R83 is performing the full CPU package review, including both
frame orders, identity failures and unrelated status protection. The supplied
232-case matrix per interpreter includes expected refusals, not successful
operational qualifications. Host16 remains HOLD; no CPU setup/probe consumed.
Both implementation owners are complete, with no overlapping edits.

The finite supplemental preview observer still records the exact 14 job running
at 03:18:11Z. Its original six-hour bound, output pins and no-retry contract
remain unchanged. Seven BC seeds continue under their existing owners.

### 2026-10-23 03:30Z R83 NO-GO; ancillary descendant/drain correction assigned

The parent read full SOL-R83. The exact R80 registration findings close, but
held16 CPU eligibility remains NO-GO. The actual R9 sampling subprocess execs a
fresh interpreter, whose unchanged headroom helper can outlive the one-second
sampler timeout. The guard misses that native descendant and falsely reports
complete reaping. A second finding shows repeated recvmsg errors can exit the
finally block before known children are drained. Both were reproduced in local
owned CPU fixtures; neither establishes the original host16 incident's cause.

A sole Sol-high implementation owner is correcting both in a new separate
`host16-cpu-qualification-r83-fix-20261023` capsule. The reviewed predecessor
remains immutable. R9/SAMPLE_CODE, cadence/deadlines, sampler choice, trainer,
scientific payload, ownership boundaries and no-retry budget must remain intact.
Fresh independent R84 follows the frozen handoff. Host16 remains HOLD; no CPU
setup/probe consumed. The M package remains in separate R81 review. The finite
14 observer still reports the original supplemental preview running at 03:29:11Z.

### 2026-10-23 03:34Z R81 NO-GO; exact wait provenance and concrete package binding assigned

The parent read full SOL-R81. The source05 placement predicate is closed and
persistent proc-read errors now permit direct-handle cleanup. However, ECHILD
followed by ordinary Popen.poll/wait can synthesize returncode0 after the actual
status has been consumed elsewhere. The candidate accepts that bare value,
allowing a false CPU-owner pass and false local SourceFetch acceptance. Four
owned CPU cases reproduced the failure; no operational attempt occurred.

A sole Sol-high owner is preparing separate
`M-physical-host14-r81-fix-20261023`, retaining real exact-wait provenance or
refusing unknown status. The same correction explicitly binds all raw gate,
runtime and source-SSH paths to the new concrete root and updates the inherited
review schema to R85. Existing frozen roots cannot be aliased or overwritten.
Fresh independent R85 will review the complete concrete freeze after sealing.
The stable CPU phase, ready/source roots and central single-measurement intent
remain unchanged. No new opportunity, retry, reservation, displacement or
production authority follows. The approved measurement is still unconsumed.

### 2026-10-23 03:45Z supplemental ep02 DEV preview complete; bounded host16 bootstrap approved

The supplemental preview completed with guard exit0 at 03:43:03Z and exact
R37gone at 03:43:06Z. The finite observer completed; it must not be restarted.
Fresh parent read-only inspection at 03:45:34Z verified full owned-tree drain,
no active Clasher jobs, no stop/breach across 71 active-period events, the exact
live watcher/R37 and 47.525 GiB GPU free on14. This observation is not future
admission clearance. Report SHA:
`d5484b44166e5a8c58bcdb78f0fc303c804fda487c268ecc44f984fffc6c6572`.
Evidence and reduced readout are under
`/mpac/sdicks02/jobs/clasher/dev-preview-supplemental-ep02-20261023/parent-actual/`.

Both candidates used all 2,332,353 DEV rows, without FINAL or selection/export.

| Seed / ep | Raw joint NLL | Card top1 | Tile top1 | ECE | Value Brier |
|---|---:|---:|---:|---:|---:|
| 2007 / 2 | 0.316337 | 0.638517 | 0.255345 | 0.006802 | 0.526663 |
| 2009 / 2 | 0.315969 | 0.637790 | 0.254201 | 0.002991 | 0.514631 |

These are unselected diagnostics, not game-strength evidence. M947 remains the
best selected/evaluated live handoff. Seven BC seeds remain active with no
completion summaries as of the existing observers' 03:44Z samples.

R83's receive-error fix is sealed as partial freeze
`b1b6c0cc9ccc68a03f9a1fd3690754c424dce030e41c63548efb3e18a06f519b`.
It explicitly refuses complete exec-descendant coverage and remains ineligible.
Sam approved one source-only verified bootstrap/authenticated channel across
exec at 03:43:34Z, with review AND actual CPU qualification required by the
hard stop **05:43:34Z**. The exact decision is in
`/mpac/sdicks02/jobs/clasher/host16-bootstrap-decision-20261023.json`.
R9/SAMPLE_CODE and training must stay unchanged. RL-critical and useful work
on14/17 have priority. If the time box is missed, stop; only an already valid
exact13/15 launcher may be used on16, otherwise16 remains held. No further
architecture rounds for this extra seed. A separate bounded implementation
owner is preparing the bootstrap; parent R84 review and actual qualification
remain mandatory. Host17 remains held for the established read-path discrepancy.

To use free14, a separate owner is preparing one unselected primary ep04 full-DEV
packet from finalized 2002/2003 checkpoints, reusing the reviewed metric workflow.
It has only bounded read-only source capture/CPU preparation authority. Parent
R86 review and fresh admission must precede operation. The M-critical exact-wait
and concrete-binding correction continues in parallel. Whichever legitimate
reviewed work is ready first may use14; there is no reservation or displacement.

### 2026-10-23 03:57Z R85 M package and R86 ep04 preview reviews active

The M owner sealed the exact-status and concrete-binding correction at
`M-physical-host14-r81-fix-20261023`, freeze
`9d745d8809217071acb7580afb9ed568ab18f2f459b44ac6e026c7be3742a272`.
Fresh Sol-high R85 reviews both engineering and concrete operational eligibility.
Retained kernel status now governs native-owner and SourceFetch acceptance;
new-root paths and R85 receipt schema are explicitly bound. Actual staged r
startup is not yet demonstrated and remains an explicit staging gate. Maximum
serialized argument measured 124,608 bytes, close to the retained 126,000 bound.
No operation or approved M opportunity has been consumed.

The primary ep04 packet sealed at `dev-preview-primary-ep04-20261023/ops-r1`,
freeze `911e6e814d2bcbf1da2707f6cf5ed6957e7b6d857f9a53eccece7e5e697b6a25`.
Fresh Sol-high R86 reviews the exact minimal helper epoch/root changes and
complete operational binding. Both bounded sequential captures succeeded once,
with source pre/post SHA/stat and exact helper waits. Strict CPU validation
passed for actual finite FP32 M checkpoints, without forward/CUDA initialization:

- 2002 ep04: `4677723173573ad8353ee9710e59b8fc530cb94946200f56beb982450e80dc0a`.
- 2003 ep04: `d06a2175e3ab4b2e1d78bf2e2125d7e27be59a0b204b4d473e6a12275fe6f773`.

This packet has no stage/GPU authority, intent or reservation. The parent read
both full handoffs. Host14 remains available to whichever reviewed eligible work
is ready first under fresh gates. The approved host16 bootstrap occupies a
separate implementation slot and retains its 05:43:34Z review-and-qualification
hard stop; it must not delay these critical reviews or useful work on14/17.

### 2026-10-23 04:11Z R86 primary ep04 preview running on 14

The parent read full R86 GO and rehashed all189 frozen constituents. Reviewed
helper `16aad1e1e13501d0a7f8c778f412d9b38c85d9a287f979a8c89380c5b625e408`
landed byte-identically via a fresh worktree on main `5167fb8b7` before operation.
A new full target-file audit completed04:08:22Z, validating73 source,6241 store
and20303 environment files with hashes and no caches. Fresh04:08:39Z lease,
watcher, all-generation ownership, no-prior-phase and resource checks passed.

The one CPU phase was admitted **04:08:58Z**, wrapper3506954/start19851554,
bootbfd7788a-d4d1-4687-9761-c462114e8849, tokenb04641a78ba14a4db2be67ef459b1d65.
The live parent captured child3506955/start19851554 before exit. Its complete
verified receipt was written04:09:17Z; R37gone04:09:36Z. Fresh04:10:14Z GPU gates
verified exact native disappearance, full owned drain, no stage stop/breach,
receipt/log equality, pins, fresh lease/watch/cache/all-owner resources and
47.525GiB physical GPU free. Global R57 intents were exclusively written and
file/all-ancestor/EEXIST/immediate-parent fsynced before each phase SSH. No retry.

The GPU phase `dev-preview-primary-ep04-r1` was admitted **04:10:33Z**,
PID/start **3513569/19861060**, same boot, token
**ce2d8dc5137046a29798253565337db0**. It runs the original8-slot/30.5GiB PSS/
39GiB GPU reservation,CPU0-31/nice10, batch512/math3/inter-op1 andsix-hour bound.
Output on14 is
`/mpac/sdicks02/jobs/clasher/dev-preview-primary-ep04-20261023/outputs/primary-ep04-r1/unselected-dev-preview.json`.
Conditional historical completion estimate is around04:45Z. This is unselected
fullDEV diagnostic work, with noFINAL, export, selection or game-strength claim.

A distinct finite read-only observer runs on05, PID/start **190980/251843625**,
boot5f666b17-9407-450e-a537-8a4b0838a8c2, execsession71942. Its singleton lock,
exact epoch4/input pins, 60-second cadence and23400-second limit are under
`/mpac/sdicks02/jobs/clasher/dev-preview-primary-ep04-20261023/parent-actual/observer/`.
The first04:11:04Z sample finds the exact job running. It cannot launch, restart,
signal or query GPU state. Completion requires guard0, exact finite unselected
report, no stop/breach and R37gone/fullowneddrain, then parent readout. The prior
supplemental observer is complete and must not be restarted. R85 M review and
bounded host16 bootstrap continue separately; no M measurement consumed.

### 2026-10-23 04:12Z R85 concurrency NO-GO; single race correction assigned

The parent read full SOL-R85. The prior false-success defect and concrete
root/R85 binding defects close, with actual staged-r readiness still pending.
One P2 remains: a genuine cooperating wait can retain exact exit0 and reap between
child enumeration and proc inspection. Discovery then wrongly fails the owner;
a second interval can leave a permanent false cleanup error despite exact reaping.
The review reproduced both on3.8/3.12. No false successful exit or survivor was
shown by this finding, but it can strand the single logical CPU phase.

A separate sole Sol-high owner is preparing `M-physical-host14-r85-fix-20261023`,
reconciling only retained exact wait evidence before declaring identity failure.
Unknown status, actual proc denial, initial capture failures and foreign ownership
must still refuse. Fresh R87 reviews the final concrete package. The approved M
opportunity remains unconsumed. The active14 ep04 preview and bounded host16
bootstrap continue separately; no operations, phase retry or reservation follow
from this correction.

### 2026-10-23 04:16Z host16 bootstrap stopped early; host16 remains held

The bounded bootstrap owner sealed partial freeze
`7d27ec2d9f00aca99a0bfa75564f75b1cec3c6400ba4185d4992d5dbc3ce9441`
at04:15:55Z. Python cross-exec/helper controls and both42-test suites pass,
but unchanged nvidia-smi is an ELF invocation refused by the approved source-only
boundary. Actual qualification cannot pass. One original3.12 delayed-WAIT case
also remains failed. The parent read the full handoff and stopped this work
early, without spending further architecture/review rounds or consuming a real
CPU opportunity. R84 is not requested on this known ineligible partial.

The exact approved13/15 launcher was inspected as the fallback. Both launcher
and wrapper require completed, same-host/seed/config/current-boot CPU memory
qualification, no older than3600s. Host16 has no successful parent qualification
receipt after its failed original probe. That prerequisite cannot be bypassed.
**Host16 remains HOLD.** No training, resume, replacement, retry or host-health
clearance follows. Remaining engineering capacity returns to the M/RL path and
useful14 work;17 remains independently held for read-path instability.

Preparation violated the preservation contract: chmod followed six copied
symlinks into old R80/R83 fixture targets, changing four directory modes and two
19-byte fixture-intent modes. The implementation restored the exact modes with
nofollow descriptors and fsynced them. Parent independently checked all six
restored modes and both file hashes. Bytes/names/types are unchanged and the
40734-path final inventory matches, but ctime changed and the old paths were
not untouched throughout. This violation is retained, not certified away by
the final inventory. No operational source, actual intent, watcher or job was
changed. Full mismatch/repair evidence stays in the frozen partial; the parent
stop and checks are `host16-bootstrap-parent-stop-20261023.json` under jobs/clasher.

### 2026-10-23 04:27Z R87 concrete M correction review active

The parent read the full sealed cooperating-reap correction handoff and bindings.
Fresh independent Sol-high R87 reviews exact freeze
`51cbf3b514e6137306a2d18555a81bed29b2cbb53ef4209cad2606a18bf940d4`
at `M-physical-host14-r85-fix-20261023`. Missing discovery/live observations now
reconcile only retained exact wait transactions; a busy pinned waiter defers an
observation, not proof of exit. Descriptor closure remains required before
cleanup success. Unknown status, real denial, failed initial capture and foreign
ownership must still refuse. Both original R85 schedules have retained actual
3.8/3.12 RED/GREEN evidence; the implementation inventories220 distinct primary
children and14 separate driver waits without merging historical counts.

The new concrete root and R87 receipt schema are bound throughout. Actual r and
remote readiness remain unstaged. The measured final serialized maximum is
125238 bytes, only762 below the126000 limit; actual authority serialization and
cap refusal remain mandatory before first effects. The single approved M
measurement and logical CPU stage remain unconsumed. The ep04 finite observer
still found the exact14 job running04:26:04Z. No host16 work is resumed.

### 2026-10-23 04:47Z R87 passes; fresh source05 arbitration blocks staging; ep04 complete

R87 engineering PASS and exact conditional operational GO were read in full.
All179 manifest pins were freshly rechecked. Nineteen reviewed flat source/config
files landed byte-identically on main `3b4ecc084`; the repository copy is source
publication, with runtime binding still fixed to the jobs package. No accepted
receipt, CPU staging or measurement opportunity was created.

Fresh read-only source05 arbitration found an actual valid-path blocker before
any phase. The initial self-SSH alias resolves loopback and refused the LAN-only
fleet key; explicit LAN129.65.221.15 corrected that diagnostic transport without
configuration changes. The exact source_accounting function then consistently
refused cwd/environ reads for a same-UID nondumpable SSH session. Its stat/status/
cmdline are readable, but cwd/environ/smaps_rollup return EACCES. It is outside
the new helper's exact wrapper chain. Diagnostics are under
`M-physical-host14-parent-r87-20261023`. No session was changed or controlled.

A sole narrow correction owner is preparing `M-physical-host14-r87-fix-20261023`.
Unclassifiable same-UID processes must remain conservatively charged with safe
identity and RSS/PSS evidence, never skipped or assigned zero. Existing source
caps, wrapper placement and all lifetime/measurement algorithms remain. Fresh
R88 reviews the final concrete correction. R87's conditional GO cannot override
this failed fresh gate; the M measurement remains unconsumed.

The ep04 preview finished with guard0 **04:44:54Z**, R37gone **04:45:06Z**.
The finite observer completed without restart. Parent fresh04:47:29Z inspection
verified exact full owned drain, no active Clasher jobs,72 clean active-period
events, no stop, exact watcher/R37 and47.525GiB GPU free. Report SHA:
`f09a81d5e16898fdd450ae4b60e17031fa020ad89af2ed718bdd0896b5e7d308`.
Both candidates used all2332353 DEV rows, without FINAL, selection or export.

| Seed / ep | Raw joint NLL | Card top1 | Tile top1 | ECE | Value Brier |
|---|---:|---:|---:|---:|---:|
| 2002 / 4 | 0.312700 | 0.647441 | 0.264464 | 0.005454 | 0.559174 |
| 2003 / 4 | 0.312789 | 0.646819 | 0.261390 | 0.004711 | 0.549710 |

Action metrics improve versus the corresponding ep02 previews, while raw ECE
and value Brier worsen. These unselected diagnostics do not establish games
strength or change the selected M947 handoff. Seven BC runs remain active.
A separate owner is preparing primary ep06 DEV inputs/packet for useful14 work,
with R89 review and fresh gates before any operation. No GPU is reserved for
that packet or the pending M measurement. Host16 work stays stopped;17 stays held.

### 2026-10-23 04:49Z ep06 source guard correctly refuses unfinished checkpoint

The sole ep06 host01 capture refused `ep06 not completed` at04:47:56Z before
transferring any checkpoint bytes. The remote helper and local SSH were exactly
waited/reaped with exit1; host02 was never contacted. The zero-byte partial,
raw stderr and source identities remain under sealed partial freeze
`4deea242d0fc8f917d8a534335c00ffccf24ef1f3bc143754991453136eed681`.
No inventory, helper variant, operational packet, stage/GPU budget or approval
was created. No ep06 retry is authorized or running.

The existing BC observer at04:49:01Z independently records01/02 training epoch
index6, steps239000/237000. Their ep05 is the prior completed epoch. The parent
explicitly authorized a new distinct bounded read-only ep05 capture per host,
with the same strict completed-publication guard and no retries, for a useful
unselected full-DEV packet. A separate narrow owner prepares that packet under
`dev-preview-primary-ep05-20261023/ops-r1`; future R89 reviews complete code and
operational bindings. The ep06 partial remains immutable. M source-accounting
correction and R88 remain critical and separate. Host14 is unreserved and awaits
whichever reviewed work is legitimately ready first.

### 2026-10-23 04:58Z exact R88 source-accounting and R89 ep05 reviews active

The parent read the source-accounting correction handoff and evidence summary.
Fresh Sol-high R88 reviews freeze
`54bf84e35d9c8550ea0263b0090ee7fa4eb134aa5b4af4a81c3703394f71ef9c`
at `M-physical-host14-r87-fix-20261023`. Denied classification fields now retain
raw error provenance and conservatively charge possible Clasher processes,
with bracketed UID/start and positive RSS/PSS evidence. Such charges give no
cleanup authority. Lifetime/source-flow/monitor/controller algorithms retain
R87 identity after mechanical bindings. The final measured argv maximum is
125932/126000, only68 bytes margin. Actual compact authority serialization and
strict oversize refusal remain mandatory before first effects. No activation,
CPU phase or M measurement has been consumed.

Both completed ep05 source captures succeeded once, sequentially, and passed
strict actual FP32 CPU validation without forward or CUDA initialization. The
parent read the full packet handoff/request. Fresh Sol-high R89 reviews freeze
`a770c27ba87d7343b5cd25f13714696002a80fb26c3a304ab7b1e0c6d5883b90`
at `dev-preview-primary-ep05-20261023/ops-r1` and helper
`7ad6232ec815c25d87d5b8625c1f34fda60b99214cedd40aa56d9da80b3826a6`.
This distinct completed-ep05 packet does not retry or relabel the preserved
unfinished-ep06 refusal. No14 stage/GPU operation or reservation exists for it.
M-critical R88 and useful14 R89 review run in separate slots; whichever eligible
work is ready first must pass fresh parent gates before using14. Host16 stays
stopped and held,17 stays held, and all seven BC runs are untouched.

### 2026-10-23 05:14Z ep05 preview admitted; R88 conditional GO accepted for preparation

The parent read full R89 and landed its byte-identical helper in main `2da33e74f`.
All 230 frozen files and fresh 14 source/store/runtime inventories passed. CPU
staging admitted once at05:05:57Z, PID3752537/start20193414, completed05:06:16Z
and R37gone05:06:36Z with exact owned drain. Separate fresh GPU gates passed
at05:07:02Z. The ep05 preview admitted at05:07:18Z, PID3758372/start20201508,
boot `bfd7788a-d4d1-4687-9761-c462114e8849`, token
`a883ea93f2b440469eee660c54f242b9`. Permanent per-phase global intents were
exclusively created and fsynced before transport; no retries are authorized.

The independent finite read-only owner is05 PID2441574/start252183408,
boot `5f666b17-9407-450e-a537-8a4b0838a8c2`, under
`/mpac/sdicks02/jobs/clasher/dev-preview-primary-ep05-20261023/parent-actual/observer`.
It observes job `dev-preview-primary-ep05-r1` for at most23400s and cannot
launch, restart, signal or query GPU. Output is
`/mpac/sdicks02/jobs/clasher/dev-preview-primary-ep05-20261023/outputs/primary-ep05-r1/unselected-dev-preview.json`.
Conditional completion estimate05:42Z; actual complete/guard0/full-owned-drain
and R37gone still need parent readout. Inputs are completed zero-indexed ep05,
not the preserved refused ep06 capture. No selection, FINAL or live handoff.

R88 engineering PASS and conditional operational eligibility were read in full.
The parent source05 read-only test at05:08:42Z passed the exact reviewed
conservative accounting:18 charged processes/22 reserved, PSS5804765184 bytes
plus7939565568 reserved, MemAvailable119332016128 bytes, load3.53. This is
preparation evidence, not current admission. R88-O1 still requires an explicit
runtime publication plan, writable dispatch/permit destinations and remote r
parent, plus actual compact-context serialization checks before any intent.
The M CPU phase and approved ONE new M measurement remain unconsumed. Original
M remains FAILED; S remains PASS. The preview owns14 until complete drainage;
no reservation or BC displacement. Seven BC seeds remain under existing owners;
16/17 remain held and no further16 architecture/review work is authorized.

### 2026-10-23 05:17Z R88 source landed and local runtime preparation recorded

Exact R88 sources landed in main `748cc5171`. Original sealed-package and all
predecessor preservation verification passed before activation. The complete
review report SHA is `b248b2825fec8ff9ff3a75e43c1ac8df2fdfc0566a49e69ebce1d9c9894cd7dc`.
The parent accepted engineering PASS and conditional eligibility, with R88-O1
runtime preparation explicitly recorded under
`/mpac/sdicks02/jobs/clasher/M-physical-host14-parent-r88-20261023`.

A compact accepted R88 receipt and empty writable dispatch parent are now
published in the new accepted root. Root mode2500 was restored after temporary
owner-write publication; all186 frozen manifest operands remain byte-identical.
The first preparation check failed because mkdir inherited setgid, producing
mode2700 rather than0700. That failure is retained. Only the new empty dispatch
directory was corrected with an exact directory descriptor. No predecessor
mode changed, and no CPU phase or measurement attempt occurred.

Actual selected compact receipt plus a prospective integer CPU permit serializes
at125649/126000 bytes, leaving351 bytes. A fresh actual permit and all complete,
nested-stage and source-SSH arguments must be checked again before effects.
No CPU or measurement permit, global intent, exposure or host14 transfer has
been created. The explicit future permit-publication plan uses temporary write
on this new root only, exact R57 exclusive durable publication, then restoration.
Remote writable-parent/absence/readiness checks remain required before any
intent. The ep05 preview still owns14; its existing finite read-only owner will
wake the parent for completion readout. No M reservation or BC displacement.

### 2026-10-23 05:46Z ep05 passed; single M CPU phase failed and drained

The ep05 read-only observer failed at05:42:42Z because its final report path
still named ep04. Its source and failure are preserved unchanged. A distinct
one-shot corrected parent readout at05:43:03Z verified the actual ep05 report,
exact input hashes/epoch, finite metrics and complete2332353 DEV rows. The
preview was not restarted. Guard terminal: `2026-10-23T05:41:38Z exit 0`. R37gone
05:42:06Z, full owned drain and no active allocation;47.525GiB GPU free.
Report SHA `dc1e030f703a3f61ca31f5497126a622936f157ccea21ee35efdc2c329cc0ee3`.

| Seed / ep | Raw joint NLL | Card top1 | Tile top1 | ECE | Value Brier |
|---|---:|---:|---:|---:|---:|
| 2002 / 5 | 0.311734 | 0.650748 | 0.266547 | 0.004191 | 0.561581 |
| 2003 / 5 | 0.312204 | 0.649967 | 0.265177 | 0.005151 | 0.556386 |

Action NLL improves versus ep04; raw value Brier worsens for both. These remain
unselected diagnostics, with no FINAL, game-strength claim or replacement
checkpoint handoff. The selected M947 anchor is unchanged.

Fresh source05/14 checks passed at05:44:05Z, including remote runtime-parent
writability, exact watcher, no prior phase, no active jobs, all-owner/resource
caps and47.525GiB GPU free. Actual complete transport arguments fit125955 bytes
under126000. An earlier parent-shell argument126062-byte refusal occurred
before intent or SSH; it is retained. Redundant parent thread-environment text
was removed, preserving hidden CUDA, placement, reviewed helpers and child
environment. The stable global CPU-phase intent was exclusively published with
R57 directory/file durability before the sole SSH dispatch at05:44:05Z.

R37 admitted `M-host14-ready-stage-20261023` at05:44:06Z, native
PID3922628/start20422357, token `5a0efd6d9eac4c71af3b3751be0a6734`,
boot `bfd7788a-d4d1-4687-9761-c462114e8849`. Inventory fetch0 passed9001947
bytes and its exact hash. Fetch1 failed with source terminal
`FileNotFoundError(2, 'No such file or directory')`; no traceback or filename was
retained. All four pinned source paths remain present with expected sizes.
The failing path and remote cause are not established. Parent transport exited1
at05:44:14Z, owner/stage receipts are failed. No retry or partial reuse follows.

Retained owner and source/local receipts show exact direct-child raw waits,
known source disappearance and no cleanup signals/errors. Fresh parent05:45:32Z
confirms full owned absence, root absent, no active jobs, R37gone05:44:36Z and
47.525GiB GPU free. All evidence and partial destinations remain preserved under
`M-physical-host14-parent-r88-20261023` and the stable R77 phase roots. Original
M09 remains FAILED; the ONE new M GPU measurement was not dispatched and remains
unconsumed. Its CPU prerequisite is failed and closed, so no M GPU or soak
launch is eligible. R90 performs bounded independent CPU-only forensics without
a source fix, retry or operating authority.

The existing finite owners still record seven BC trainers alive with matching
identities at05:45Z. Primary01/02 are in final epoch index7,08 in index5; none
has a completion summary. A separate owner prepares a distinct seed2001
completed ep03/ep04 full-DEV packet from08 for useful14 work, with one bounded
source capture per input, no GPU reservation, and R91 review before operation.
The refused ep06 and failed CPU phase are not retried.16/17 remain held.

### 2026-10-23 05:51Z R90 independent failure forensics complete

The parent read the complete R90 FORENSICS.md and INDEX.md. All186 manifest
operands and79 captured originals remain unchanged. The original stream call
failed; the current catch retains only repr and raises a replacement RuntimeError,
losing the initiating traceback and filename. Eight accounting and five stream
mocks show that archive-open and in-stream procfs failures can collapse to the
same retained error. They do not prove the actual initiating cause. Source
archive absence, procfs ENOENT and a specific failing PID remain unproven.

R90 did not refresh R37 or operational PIDs. Its cached running-state qualification
is correctly separate from the parent later05:45:32Z full-drain observation and
R37gone05:44:36Z. Actual admission is05:44:06Z from the R37 record;05:44:05Z
is the parent transport dispatch time. No historical result or source receipt
has been rewritten.

A bounded owner now prepares only a small CPU diagnostics proposal, retaining
original traceback without locals and exception filenames while preserving all
source/accounting/failure semantics. It cannot modify or activate the accepted
package. Current actual argv margin is45 bytes, so any proposal must disclose
transport-size limits rather than increase the cap. Fresh R92 review is required.
The logical CPU phase remains FAILED and closed with no retry; the approved
new M GPU opportunity remains unconsumed. Seed2001 ep03/ep04 DEV packet
preparation continues separately for14; no reservation or operational authority.

### 2026-10-23 05:54Z seed2001 ep03/ep04 packet sealed; R91 active

The parent read the complete handoff, R91 request and phase protocol. Both
original08 seed2001 checkpoints were captured once each, sequentially, with
strict publication guards and finite FP32 CPU validation. No forward or CUDA
initialization occurred. The complete packet is
`/mpac/sdicks02/jobs/clasher/dev-preview-seed2001-ep03-ep04-20261023/ops-r1`,
freeze `a869529467cec932f1bd57b224a18582c1afcf75f14296d5d8ce3833fbe2a8fb`.
The helper's seven mechanical substitutions support one seed at distinct epochs
using seed/epoch identity keys; scientific evaluation/calibration stays unchanged.

Fresh independent Sol-high R91 reviews exact code and operational eligibility.
No helper landing,14 operation, permit, intent, reservation or observer exists
for this packet. R89 and earlier shell/schema/receipt fixes remain review
requirements. Conditional future limits are unchanged4slot/4GiB CPU staging
and8slot/30.5GiB/GPU39 full-DEV preview, with separate fresh gates and permanent
R57 per-phase intents. This is distinct from the failed M CPU readiness and
uses the existing verified BC environment. That failed phase is not retried.
R90 is complete; a separate diagnostics-only proposal is still in preparation.

### 2026-10-23 05:57Z diagnostics proposal frozen; R92 CPU-only review active

The parent read the full diagnostics runbook and patch. Candidate freeze
`75db9f8786098d27d4b94d37ef8d3097967e9aaefbf230aea532d2054896aa22`
is under `M-source-diagnostics-proposal-20261023`. Ten bounded original/candidate
mocks pass. The added failure-only object retains at most eight traceback frame
locations without locals, bounded exception names/filenames and integer errno.
Existing success, error, status, stream, accounting and lifecycle behavior stays
unchanged. Original source remains byte-identical.

Fresh Sol-high R92 reviews this small CPU-only proposal, not operational
eligibility or another attempt. The source-only encoding estimate adds440
compressed/588base64 bytes; the same envelope would be about543 bytes over
the126000 cap. Full repinning is unmeasured. It cannot be adopted as-is, and no
cap increase, omitted pin, new transport architecture or operational edit is
authorized by the proposal. R91 independently reviews the useful14 DEV packet.

Proposed next M path, requiring a coordinator budget amendment: one new bounded
CPU-only readiness phase after exact diagnostics/package review, with unchanged
scientific payload and the same unconsumed ONE M GPU opportunity. Nonsemantic
compaction of operational source text may address transport size, but needs exact
byte/AST/pin review and actual argument measurements. No such package is built
or adopted yet. The failed CPU phase, partial roots and permanent intent remain
closed/preserved. There is no automatic retry, no14 reservation and noBC
displacement. The documented no-second-phase rule prevents execution without
that separate decision.

### 2026-10-23 06:02Z R92 source PASS with sizing qualification

The parent read the full independent R92 report. Exact diagnostics-only source
`6458cfd9cce46dc102156a28cb83f4bb32a35ff29559f736bbfe5853a70fa529`
passes engineering/source review with no blocker. Existing source, freeze and
original evidence remain unchanged. The result grants no operational adoption,
staging, retry, measurement or production authority.

R92-N1 corrects the implementation's below40KB sizing statement: non-BMP JSON
escapes with maximum retained fields produced76027 bytes; under80KB describes
these added fields with the current writer. The original error repr and other
terminal fields are outside that bound. Traceback traversal remains linear in
existing depth, while retained frames stay at eight and no locals are captured.
The separate argv estimate remains about543 bytes beyond the cap. Full
repinning/transport is unmeasured and the proposal is ineligible for adoption.

The parent requested a coordinator amendment for ONE new CPU-only readiness
phase after exact package review, preserving the failed phase and unchanged
single unconsumed GPU budget. No answer has arrived, so dependent execution
stays closed. No new package, intent or phase is started. Independent R91
continues on the distinct useful14 DEV packet.

### 2026-10-23 06:09Z R91 passed and seed2001 ep03/ep04 preview running

The parent read full R91 engineering PASS and conditional exact package GO.
All254 frozen files/37 directories reverified, and the byte-identical helper
landed main `6995879a9`. Fresh06:05:21Z source73/store6241/env20303 full hashes
and exact inventories/no-cache checks passed. Canonical watcher, arbitrary-writer
lease/retained deadlines, no controls/journal/ending, all owner and gone-record
remnants, no duplicate phases and actual+reserved resources passed. Physical
GPU free47.525GiB. Separate global CPU/GPU R57 intents were exclusively created
with file/all-ancestor/EEXIST/immediate-parent fsync before each SSH.

CPU `dev-preview-seed2001-ep03-ep04-cpu-stage-r1` admitted06:05:56Z,
PID4003942/start20553393, token `353f089f828449e2829aa5870aac5a8f`.
Exact receipt completed06:06:14Z from child4003943. Parent verified original
log/receipt/token/pins/counts, child/root disappearance, no stop/breach/ending,
full owned drain and R37gone06:06:36Z. Post-stage full asset hashes passed again
at06:07:05Z. Entirely fresh GPU gates passed06:07:15Z.

GPU `dev-preview-seed2001-ep03-ep04-r1` admitted06:07:39Z,
PID4011480/start20563704, boot `bfd7788a-d4d1-4687-9761-c462114e8849`,
token `8b7627a3abef411598f6bb8d94e676a4`. Limits remain8slots/PSS30.5GiB/
GPU39/CPU0-31/nice10/6h guard. Conditional finish06:42Z. Output is
`/mpac/sdicks02/jobs/clasher/dev-preview-seed2001-ep03-ep04-20261023/outputs/seed2001-ep03-ep04-r1/unselected-dev-preview.json`.

A new independent finite read-only observer is05 PID990371/start252549701,
boot `5f666b17-9407-450e-a537-8a4b0838a8c2`, under parent-actual/observer.
It runs at most23400s and only inspects once/minute with25s per-SSH bound; no
launch/restart/signal/GPU query. Its report path is derived from exact reviewed
OPERATIONS output, and same-seed candidate hashes are keyed by seed/epoch.
No old observer was copied. The first06:08:45Z sample confirms running. Actual
completion/guard0/report/full drain/R37gone still need parent readout. No FINAL,
selection, export or947 handoff. Failed M CPU phase and pending budget amendment
are separate; no retry/measurement follows.16/17 remain held.

### 2026-10-23 06:58Z seed2001 preview quarantined by final event audit

The finite read-only observer completed normally at06:42:45Z: report complete,
finite, both input hashes correct, original guard0 at06:41:40Z, R37gone06:42:06Z.
Report SHA `6d5e1f984676492c4d21730e338436af89ca7ffce7ac6e32a1145866bd37b82c`.
The parent initially described that observer result as passed. The mandatory
full event audit then refused qualification: one poll at06:41:36Z records
`unobservable: OSError: live group PSS unobservable` with zero placeholder
resource fields. Those zeros are not valid measured usage or proof of headroom.
The parent corrected the assessment immediately; guard0 cannot override this
no-breach requirement. No rerun, promotion or acceptance occurred.

Descriptive raw joint NLL was0.313670/0.312422 at ep03/04 and raw Brier
0.544127/0.565162. These values are quarantined, not qualified results or a
selection/game-strength claim. Scientific eligibility remains false. Fresh
parent06:46:20Z evidence confirms full known-owned drain, no active jobs, healthy
watcher and47.525GiB GPU free. Strict failed-readout code/stderr and separate
postfailure-drain JSON both remain under parent-actual; no failure was erased.
Fresh independent R93 performs focused CPU-only interpretation of the exact
observability event and R37 source. It may not soften the rule or issue a retry.

The original BC observer stopped at06:56:00Z after15 seed2009 disappeared with
a summary but no exit receipt at its expected path. This is an observer failure,
not yet a proven training failure. R95 solely inspects exact launcher/receipt
paths and bounded read-only completion evidence on01/02/15, then prepares a
distinct finite read-only owner only for unfinished08/13 after duplicate checks.
Original observer/failure bytes stay intact;09/12's separate owner is untouched.
01/02 are reported finished with summaries, pending detailed process/artifact
qualification;08 keeps full three-primary-run selection on the critical path.

R94 statically prepares light full-DEV work for freed own01 using distinct
completed seed2002 ep06/ep07 inputs and existing qualified guard components.
No01 connection is allowed until R95 releases its completion collection. There
is no new guard architecture, GPU reservation, long BC run or launch authority.
Exact future R96 review and fresh admission must precede any execution. This
keeps later RL sharing possible.16/17 remain held;04HP1 untouched. The M CPU
phase stays failed/closed and its budget amendment remains unanswered.


### 2026-10-23 07:23Z completion evidence, failed captures, and next gates

R93 independently confirms the seed2001 ep03/04 preview remains failed and
quarantined. Its zero resource fields are error placeholders, not measured
usage; the retained event does not identify the failing PID or path. No resource
excess or hardware cause can be inferred. No rerun or promotion is authorized.

R95 confirms supplemental seed2009 on15 is FAILED/excluded: the pinned wrapper
raised the original resource-sampler error after calibration, and no
training-exit receipt exists. The finite summary cannot override that failure.
Trainer/wrapper and all retained native identities are gone; raw exit status and
sampler stderr were not retained. No restart or hardware clearance follows.
Primary01/02 have finite completed artifacts and exact original trainer absence
on matching boots; their direct-launch native exit status is unavailable.

The corrected finite read-only observer covers only unfinished08/13:
05 PID2969502/start252876735, session2969502, boot5f666b17-9407-450e-a537-8a4b0838a8c2,
nice15/CPUs0-31, sequential60s checks with25s SSH bound, deadline13:03:15Z.
Receipt and script live under jobs/clasher/bc-readonly-owner-recovery-20261023.
The old failed observer is preserved;09/12's separate observer is untouched.

The proposed own01 DEV route has no reviewed standalone ResourceMonitor.
The parent previously named a nonexistent component; this is corrected. No new
guard architecture is introduced. The next packet instead targets the existing
reviewed14 route;01/02 remain unreserved. R94's ep06 capture attempt1 failed on a
collector syntax error, zero checkpoint bytes. The local compile failure should
have stopped dispatch but did not; the mistake and native wait1 are retained.
After an explicit parent correction for this reversible read-only capture only,
R96's attempt2 compiled and failed closed at a calibration metadata check, again
before checkpoint access. Ep07 remains unattempted. No eligible packet, CPU
checkpoint validation,14 admission or GPU budget exists for these inputs.

Static diagnosis establishes the second failure is a collector contract error:
40ea writes only epoch DEV rows to log.jsonl and prints final gate calibration to
stdout. The retained stdout calibration matches the hash-pinned summary.json;
the collector incorrectly required calibration keys in the last epoch row.
A corrected read-only contract needs actual retained-metadata regression tests
and independent review before another capture. Both failed roots remain intact.

R97 prepares a distinct extra M seed2026102010 on idle15 using the reviewed R70
persistent sampler. It is not a retry/replacement of failed2009, and primary
three-seed selection is unchanged. Exact CPU caller/package review, actual CPU
qualification and GPU launch review remain required; no operations yet.
R98's nonoperational diagnostics compaction proposal reports maximum121458 bytes
against126000, with all186 manifest operands and18 bundle entries retained.
Fresh R102 reviews only that CPU proposal. It supplies no operating authority.
The R88 M CPU phase remains failed/closed; its budget amendment has no answer,
and the single approved new M GPU measurement remains unconsumed. A coordinator
steer failed because its thread was idle; no message was queued or delivered.
