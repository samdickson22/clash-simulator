# LIVE LEAD progress (exploration tier)

- **Mandate:** Sam, 2026-10-14. Official client, throwaway account, emulator on the Mac mini only. Training Camp, then
  ladder. No detection evasion.
- **Coordinator:** thread 0523ae6f.
- **Task:** clasher-live-lead-20261014-r1.
- **Plan:** `reports/live/PLAN.md`.

## Layout

- **Worktree:** `/mpac/sdicks02/repos/clasher-live` on 05, branch `live/lead`. Commit to main via a temp index.
- **Mac live dir:** `~/clasher-live/`, created 2026-10-14 22:52Z and empty. Until Sam answers, no Mac changes other
  than this dir and read-only checks.
  - Never touch: `~/Desktop/code/clasher*`, `~/.cache/clasher-native-reference` (reference AVD, never networked),
    `~/.cache/clasher-official` (L3 history), `~/.cache/clasher-live-v4`, the t1-* paths, or the E4 trees.
- **Mac ssh:** `ssh macmini-fleet` always exits 0, so wrap every command with `printf '__RC=%s' $?` and treat a
  missing token as failure.
- **Hosts:** 05 orchestrates only. GPU comes from the bot track on request.

## Done

- **2026-10-14T22:51Z, step 1 (PLAN) written.** Main findings:
  - The official client aborts at startup on stock AVDs: `frrh.aC: 02` from its anti-emulator check. That route is
    closed (no evasion).
  - The Mac has 9.7 GB free disk, and a Win11 VM holds 16 of its 24 GB RAM.
  - Perception has no accepted accuracy.
  - The bot needs glue: a deadline, an adapter, Mac pins.
  - Both engines support only C56 cards at level 11.

## Running

- **Coordinator ruling 2026-10-14 ~22:55Z:**
  - 127x01's A6000 is ours for about 10 h once the bot lead frees it.
  - On 01: `jobs/clasher/live-*` and `repos/clasher-live*`, ≤16 loader cores.
  - Read `clasher-v4-cache` and `clasher-v4-data`, train/val only.
  - Sam items have been relayed.
- **Step B perception owner:** Opus, delegated task `live-percB-owner-r1`. Its progress file is
  `reports/live/perception/PROGRESS.md`.
- **Step C bot glue owner:** Opus, delegated task `live-glueC-owner-r1`. Its work is in `bot/live/` and
  `reports/live/bot/PROGRESS.md`.
- **Bot lead answers (~23:05Z):**
  - **it5s2:** `student:/mpac/sdicks02/repos/clasher-bot-runtime/students/it5s2-step001200.pt@0.5375`, sha 08bdaf32….
  - **K4C-r16:** needs the runtime root `clasher-bot-runtime/r1`, with R3a 37509a43…, main02 d77005d5… and native 44874fd6….
  - **Deadline:** subclass `MultiSearchPlayer`, using the wall-mode cutoff from `SearchPlayer`. Any variant must be
    validated paired against K4C-r16 with `bot.eval.headline`.
  - **Live state:** follow the `royalesim_translate` pattern.
  - **Starter cards:** Spear Goblins and Goblin Cage are not in C56. Plan with real levels.
- **GPU:** 127x01 A6000 handed to the perception owner at 23:01Z for about 10 h. Return it to the bot lead (message their thread) when done, by about 2026-10-15T09:00Z.

## Next

1. **Coordinator:** ask for an A6000 (prefer 01, where the v4 caches are) and send Sam the list in PLAN section 4.
2. **Step B (in parallel):** v4 exploration fine-tune on train, measured on val.
3. **Step A:** after Sam frees disk and RAM, retry BlueStacks Air with default settings. Sol review before any Mac
   script runs.

## Log

- **23:16Z, glueC report 1:** `bot/live/player.py` and `translate.py` pass 15/15 tests on 05.
  - Tiers: `LIVE-K4CW-r16-w<ms>-t<threads>` (it5s2 cutoff default and fallback), and `LIVE-fast-it5s2` at ~13 ms.
  - w200-t4: max decision 192 ms. w120-t4: median under 120 ms.
  - The translator reproduces the v5 packet exactly from a perfect record. Gaps: unit facing (estimated by
    tracking) and spells/projectiles.
  - Next: oracle replay numbers, and the 03 wall-eval command.
- **23:22Z, wall eval:** the spec is accepted by the bot lead.
  - **Host:** 127x03 from ~01:30Z, after their K4L-R-gs fresh-bank run finishes.
  - **Cores:** logical 0–59 as 12×5 groups, with SMT siblings 64–123 idle.
  - **Out dir:** `/mpac/sdicks02/jobs/clasher/live-wall-rsim15535`.
  - **I own the run:** I stage `clasher-live-eval/`, run the 2-game smoke, launch with setsid, and tell the bot lead
    when it ends.
  - The command is in `reports/live/bot/RESULTS.md` §4, with 4 arms: w200, w150, w120 and `LIVE-K4CW-r16-w150-t4`.
  - If K4L-R-gs confirms, the best bot's rollout opponent becomes a learned policy driven from Python. That will cost
    more per decision, so re-time it for live.
- **23:30Z, perception baseline:** T7 final e5d1acd1 on the full val split (64 matches, 53,388 frames).
  - **Hand:** 97.9% per slot; all 4 slots right in 94.2% of frames.
  - **Elixir:** MAE 0.25.
  - **Tower HP:** MAE 0.15.
  - **Units:** essentially undetected (recall 0.3% at 0.5). The labels trusted only ~0.07 units per frame.
  - **Correction:** "legacy T6" a3860deb is the v3 stream model, and its 70.9/79.4% were play-event metrics.
  - **Fine-tune ft-r1** on the 01 A6000 since 23:13Z: dense card-level labels, 58 classes. Val subset at epoch 3:
    units F1 0.58 (P 0.95, R 0.42), tower MAE 0.024, elixir MAE 0.075. GPU done ~05:30Z.
  - The schema is in `live/perception/common.py:frame_record`. No play events, so the translator derives them from
    unit births.
- **23:51Z, glueC report 3 (interim):** 20/20 tests pass.
  - Plays are now derived from unit births (`bot/live/births.py`), with a ClockTracker.
  - **Replay agreement with the bot on the true state, it5s2, exact:** events 0.998; births 0.94; p70 0.81; p42 0.71.
  - **K4C-r16, exact:** events 0.90; its own reseed floor 0.78; births 0.68; p42 0.54.
  - The biggest cost is missing play events, i.e. spells. The perception owner has been asked to put play/spell
    events (temporal head) next, after ft-r1.
- **00:31Z, glueC FINAL:** all 5 deliverables done (`reports/live/bot/RESULTS.md`).
  - **Latency on 05, T1 real states:** it5s2 p50 13.7 / p99 18.6 ms. K4C unbounded p95 712 ms, so not usable live.
    w200-t4 p95 192 ms; w150-t4 142 ms; w120-t4 112 ms.
  - **Agreement with K4C on the true state, exact:** events 0.94; births 0.72; p42 0.57; reseed floor 0.79.
    Only ~48% of opponent plays reach the bot without spell detection.
  - **Mac:** build the native from the runtime root's own `engine-rs`, check it with `bot.live.native_parity`
    against `05:/mpac/sdicks02/jobs/clasher/live-glueC/parity.json`, then pin it via `bot/live/mac_pins.py`.
    Footprint: ~120 MB of files, 1 GB RSS.
  - **Open:** rollout spawns stay at level 11.
- **00:51Z, wall eval launched on 127x03.**
  - **Process:** PGID 2207770; script `/mpac/sdicks02/jobs/clasher/live-wall-rsim15535/run.sh` (resumable, re-run
    to continue). Code staged at `03:/mpac/sdicks02/repos/clasher-live-eval` (bot/ + reports/explore/x4s).
  - **ETA:** ~03:30Z. Tell the bot lead when it ends.
  - **Pairing:** `bot/eval/pair_by_name.py` against `bot-headline-r16-rsim15535` (RESULTS §4).
  - **K4L-R-gs** beat K4C-r16 by +0.055 [+0.041, +0.068] on the fresh bank. But it needs 120–140 ms of serial Python
    per decision, so it doesn't fit live yet.
- **00:57Z, perception events (interim, val only):**
  - **Baseline T7 temporal head:** R 9% / P 5%, so unusable.
  - **ft-r2** (01 A6000 since 00:04Z, ends ~05:34Z): TemporalHead joint with body/HUD, plus a location-level tracker
    (`live/perception/events.py`).
  - **At epoch 5 (8 val matches):** all events P 0.80 / R 0.72; opponent troops P 0.87 / R 0.75; opponent spells
    **P 0.83 / R 0.47**; median placement error 0 tiles.
  - **frame_record events:** `tick` is in **ms** on the caller clock, so the translator must convert it (TODO in
    integration).
  - The entry point is `live/perception/infer.py:LivePerception`. RESULTS ~06:30Z.
- **02:58Z, wall eval: 2,400 games done, 0 errors.** Paired B−A vs K4C-r16 on RoyaleSim 15.535, HEADLINE bank:
  - w200: R3a −0.087 [−0.143, −0.030], v1 −0.033 [−0.073, +0.007]
  - w150: R3a −0.142, v1 −0.050
  - w120: R3a −0.233, v1 −0.170
  - **LIVE w150 (it5s2 default):** R3a −0.095 [−0.153, −0.037], v1 −0.013 [−0.060, +0.033]
  - Reading: the deadline costs real strength (honest lateness included). The it5s2 cutoff default is better than
    R3a's. The Mac per-core speed decides the tier.
- **02:58Z:** added the arm `LIVE-K4CW-r16-w200-t4` (600 games, PGID 2574073 on 03, ETA ~03:40Z), then hand 03 back
  to the bot lead.
- **~02:50Z, GPU check (coordinator flagged it low):** 30 one-second samples averaged 90.8%. ft-r2 is healthy; the
  dips come from the val passes.
- **03:37Z, wall eval complete:** 3,000 games, 0 errors (`reports/live/WALL-EVAL.md`).
  - LIVE-w200: R3a −0.070 [−0.127, −0.013], v1 −0.020 [−0.067, +0.027].
  - Pending the Mac timing, the deployed tier is `LIVE-K4CW-r16-w200-t4`.
  - 03 handed back to the bot lead.
- **03:38Z, Mac CPU bench (coordinator-proposed, no emulator):** delegated to an Opus owner
  (`live-macbench-owner-r1`), with progress in `reports/live/mac-bench/PROGRESS.md`.
  - The owner stops before the first Mac run, for a Sol review.
  - Mac writes go only to `~/clasher-live/`, with a total footprint ≤ 2 GB (9.3 GiB free).
- **04:18Z, Mac bench at the gate:** scripts written; the end-to-end dry run on 05 is clean.
  - **Native recipe corrected:** e1 staged source plus `--features extension-module,gil-release`. Bit-exact
    parity holds on a 05 rebuild.
  - **Clean fleet baseline:** w200-t4 p95 185 ms, default 2.0%; w150-t4 p95 142 ms, default 13.1%; it5s2
    p50 13.3 ms. The old numbers came from a contended core.
  - **Sol review:** running (`live-macbench-sol-review-r1`).
  - **Kept:** rustc on 05 under `/mpac/sdicks02/tools-live` (613 MB).
- **04:21Z, Sol review of the Mac bench** (`live-macbench-sol-review-r1`): **not OK as is.**
  - 7 blockers: PID reuse in stop; `__RC` ignored when polling and on transfers; stale parity/audit approvals;
    no disk watch during steps; xcrun fallback; `-I` without `-B`.
  - 8 should-fixes and 1 nit.
  - All were sent back to the owner. After fixes: a dry run on 05, my spot-check, then GO.
- **04:24Z, ft-r2 final (val subset, 952 frames):**
  - hand 99.05%; elixir MAE 0.057; units F1 0.846 (P 0.95, R 0.76); tower MAE 0.006;
  - events P/R 0.91/0.74; spells 0.80/0.49.
  - The 01 GPU was **released to the bot lead 4.5 h early**. The full-val eval (PID 1117790, CPU-bound) is finishing
    alongside.
  - No more fitting on renderer data. The next perception step needs official-client frames.
- **04:36Z, step B DONE.** Final ft-r2 (sha cba64d2a…) on the FULL val split (64 matches); see
  `reports/live/perception/RESULTS.md`.
  - hand 98.85% per slot (97.0% all 4 right); elixir MAE 0.064; tower MAE 0.0089;
  - units P/R/F1 0.907/0.774/0.835 within 1 tile;
  - events P/R 0.872/0.750; opponent spells 0.745/0.490;
  - latency on 01 CPU: 107 ms per frame end to end, so the Mac needs MPS/CoreML or the event head on every other frame.
  - Files on 01 and 05: `/mpac/sdicks02/jobs/clasher/live-perception-20261014/` (export-final, sample-records).
  - Cheap next fix, no GPU: fuse the newborn unit's body identity into the event card.
- **04:37Z, coordinator accepted step B** (eafb2277) and approved (a), (b) and (c) in that order.
  - **(a) event-card fusion and (b) real-perception end-to-end replay:** delegated to an Opus owner,
    `live-integ-ab-owner-r1`. Output goes to `reports/live/integration/`.
  - **(c) Mac bench add-on:** a mixed contention case. The perception loop (MPS, then CoreML, then CPU with the
    event head on every other frame) runs concurrently with each tier, and the recommended live tier comes from the
    mixed numbers. This was added to the bench owner's fix round, so the same STOP gate applies.
- **04:53Z, glueC real-record fixes done (23 tests pass); glueC stopped.**
  - The ClockTracker is anchored on elixir-phase transitions. **The live loop must call `anchor(0, ts)` at match
    start.**
  - Opponent plays come from births grouped into clusters with a vote: P/R ~0.71/0.83 on real output, provisional.
  - Event ms times are converted to ticks.
- **06:16Z, (a) event-card fusion, full val:**
  - all-events F1 .807 → .855 (odd half, held out from config choice: .802 → .851);
  - opponent troops P/R .917/.919; opponent spells .646/.577 (thr .5) or .773/.507 (thr .6, hold 500);
  - median latency 150 → 225 ms.
  - **(b) early findings:**
    - only 59% of true opponent plays reach the bot, because the stream guard drops true plays after an earlier
      miss; the resync cycle tracker is approved and assigned to the integ owner;
    - a LiveSession bug is fixed: a single skipped poll used to kill the fast tier for the rest of the match.
  - Royal Ghost is a perception blind spot.
- **06:45Z, K4L adopted as the default live candidate:** `LIVE-K4L-R-gs-rw-fc-w200-t4-p4` (coordinator
  row 2376f007).
  - The `make_live_player` hook is on main (6543c103); 23 tests pass.
  - Fleet: p50/p95 79/126 ms, +0.058 vs K4CW at 200 ms.
  - Added to the Mac bench (mixed and alone) with the i10 fallback, K4CW w200/w150 and it5s2.
  - The opponent models (`bot-lopp-models/*.npz`) are never committed.
- **08:50Z, (a)+(b) DONE** (`reports/live/integration/RESULTS.md`).
  - **Fusion:** deployed config thr .6 / hold 500 (`events.LIVE_DEFAULT`). Full-val all-events P/R .909/.794.
  - **Resync cycle tracker** (`bot/live/resync.py`): opponent plays reaching the bot .594 → **.775**, precision .949.
  - **Real-perception replay vs the true state:** it5s2 .856 exact on 64 val matches (dense-truth record .948).
    K4CW-w200 .741 on 28 matches (its reseed floor .857).
  - 0 translator or decision errors in every arm.
  - The 01 K4CW runs are invalid (load ~85), so wall tiers need a quiet host.
  - **Live loop must call `anchor(0, ts)`.**
  - **Empirical-noise arms:** PERC-emp, PERC-emp-births, PERC-emp-both. The headline commands are in RESULTS (b),
    not yet run.
- **09:25Z, perception win-rate block launched on 127x03.**
  - fast: cores 0–19, PGID 3789271. K4L: cores 20–59 in 4-core groups, PGID 3789273.
  - Arms: `LIVE-*` vs `PERC-emp:LIVE-*`; 2,400 games in our engine.
  - Out dir: `03:/mpac/sdicks02/jobs/clasher/live-perc-winrate-ours/{fast,k4l}`. Scripts `run-{fast,k4l}.sh` are
    resumable.
  - Hand back to the bot lead by about 11:15Z.
- **09:27Z, Mac bench round 3 at the gate:** suite 65/65; bundle 631bd087.
  - K4L fleet-05 timing: p50/p95 59.8/138.3 ms, default 0.8%; i10 54.9/133.7.
  - **Sol round 2 launched** (`live-macbench-sol-review-r2`). It covers the fix round plus the new mac_perc,
    audit_site, frames_from_01 and K4L pool code.
  - Accepted, if Sol finds the per-step listing complete: OS-level Metal/CoreML caches outside `~/clasher-live`.
  - `frames_from_01` runs after the review.
- **09:27Z, bot lead:**
  - The GIL disagreement is likely in their Python/numpy rollout loop; they're fixing the docs and testing a
    thread-only K4L variant (would replace the spawn pool on macOS).
  - **If the Mac p99 is higher, i10 is the safer Mac default.** Keep the default share at ≤1% on 4 cores.
- **09:35Z, Sol round 2: OK after fixes.**
  - Blockers: process-group cleanup; push outside the lock and without a footprint check; MPS/CoreML OS caches;
    frame cache authentication; ctypes temp-file path.
  - **Ruling: OS-managed Metal/CoreML caches outside `~/clasher-live` are accepted**, with redirects for
    everything we control and before/after snapshots.
  - All findings were sent back. **GO on a clean suite and dry run, with no third Sol round:** frames_from_01, then
    `drive.sh all`, then MAC-BENCH.md.
- **10:27Z, perception win-rate block:**
  - **Fast half done:** 1,200 games, 0 errors. PERC-emp:it5s2 vs perfect sight: R3a **−0.137** [−0.197, −0.077],
    v1 **−0.113** [−0.163, −0.063]. Absolute 0.660 → 0.523 vs R3a, 0.883 → 0.770 vs v1.
  - **K4L half crashed:** native panic at `c56.rs:265` (electro_land config lookup). All 6 worker deaths were in
    the PERC-emp arm.
    - Cause: K4L `fc` trims the card config to hands+cycles, and misperceived off-deck units have no entry.
      PanicException is a BaseException, so the fallbacks missed it.
    - Stopped it (PGID 3789273) and handed 03 back.
    - Fixes: the bot lead's `bot-lead-k4l-fix-r1` (config, pool recovery, native lookup), plus ours,
      `live-panic-fix-owner-r1` (BaseException guard, card-consistency sanitiser).
    - Relaunch the K4L half after both land: `03:/mpac/sdicks02/jobs/clasher/live-perc-winrate-ours/run-k4l.sh`
      resumes, but delete the k4l dir first, because its partial rows predate the fix.
- **10:28Z, perception round 2 authorized** by the coordinator (perception costs −11 to −14 pp).
  - Targets: spell recall .57, swarm/unit recall .81, Royal Ghost.
  - Metric: Δ win rate of PERC-emp vs perfect sight.
  - GPU: **127x01's A6000** from ~11:30Z, for up to ~10 h, once the bot lead posts "01 GPU free". Forward that to
    the round-2 owner.
  - Owner: Opus, `live-perc-r2-owner-r1`, doing CPU diagnosis first.
- **10:38Z:** 127x01 A6000 free for perception round 2 (bot lead). Forwarded; window until ~20:30Z.
- **10:44Z, PERC-R2 diagnosis** (`05:/mpac/sdicks02/jobs/clasher/live-perc-r2-20261015/diag/`):
  - **Spells:** 32% of opponent spells sit below the 0.6 threshold (a discrimination problem), 9% have no peak.
    Zap, EQ and RoyalDelivery are the worst.
  - **Units:** 51% of misses are merged peaks. SkeletonArmy alone is 21% of misses; crowd recall is .54.
  - **Royal Ghost:** now labelled with a stationary-visible rule. The Δ metric can't see it, because the sim's
    truth shows Ghost.
  - **ft-r3** on 01 (PID 3037297) since 10:41Z, ends ~14:55Z; GPU back ~16:30Z. Changes: effect identities for
    spells, a count head for swarms, Ghost labels, event loss reaching the backbone.
  - Asked the bot lead for ~60 cores for 45 min for the PERC-emp-x* ablation (7 arms, 4,200 games).
- **10:46Z, perception-noise ablation launched on 127x03.**
  - PGID 4060013; 36 workers on logical 0–35; 7 PERC-emp-x* arms; 4,200 games; ETA ~12:00Z.
  - Out dir `03:/mpac/sdicks02/jobs/clasher/live-perc-ablate-ours`. Staged from HEAD plus the round-2 `perc.py`
    and `empirical.py` only.
  - Pairs against `live-perc-winrate-ours/fast`.
  - Tell the bot lead when it ends.
- **10:48Z, panic-fix (defence in depth) DONE** (`reports/live/integration/PANIC-FIX.md`).
  - **Cause:** an own-side ElectroSpirit misread (not in our deck) under the K4L `fc` trimmed config.
  - **Fixes:** a deck-rule board sanitizer in `translate.py`, and BaseException guards in `player.py`.
  - **Tests:** 8 new pass, 39 existing pass. 10 PERC-emp:K4L games: 0 crashes.
  - **Regression roots** for the bot lead are in `05:/mpac/sdicks02/jobs/clasher/live-panic-fix/`.
- **10:52Z, bot lead's K4L fix on main (654b18bb):** the fc cut keeps every referenced card;
  panic/EOF/BrokenPipe fall back to the cutoff default; the pool is replaced.
  - The K4L rerun is staged in a separate dir, `03:/mpac/sdicks02/repos/clasher-live-eval2` (origin/main 654b18bb,
    which includes our sanitizer 45658350), so the running ablation's tree isn't touched.
  - Script: `03:/mpac/sdicks02/jobs/clasher/live-perc-winrate-k4l-r2/run.sh` (cores 0–59, group 4).
  - Launch after the ablation ends and the bot lead posts "03 clear". Report the default share (this run is also the
    re-timing).
- **10:58Z:** ft-r3 relaunched (PID 3133892, GPU 92%), ending ~14:00–14:30Z. Loader stall fixed with NUMPY_MADVISE_HUGEPAGE=0 (THP compaction on 01); tip passed to the bot lead.
- **11:00Z:** the K4L rerun run.sh sets NUMPY_MADVISE_HUGEPAGE=0 for both arms (recorded; it changes timing compared with earlier 03 runs).
- **11:33Z, coordinator: live runs use pin set r1-total** (main 5cb79878, native 681b5f2c, panic-free,
  output-identical to r1). The fleet bot track stays on r1.
  - The K4L rerun is re-staged in `clasher-live-eval2` with r1-total and THP off; it loads 681b5f2c (checked).
  - The Mac bench owner is told to build from 44874fd6 source + NATIVE-TOTAL.diff and pin `mac-r1-total`.
  - **Bot-lead findings:** `native_failure` stat dropped in `_done`; duplicate hand card / 5-card cycle.
    Assigned to `live-hand-sanitize-owner-r1`.
- **11:41Z, K4L PERC rerun launched on 03:** PGID 90747, `run.sh --cores 36-59` (6 groups), r1-total, THP off.
  The 2-game smoke was OK.
  - When the ablation (PGID 4060013) ends, ~12:55Z: TERM -90747, then `setsid -f run.sh` (defaults to 0-59; it
    resumes).
  - The default share in the first part was measured beside the ablation; flag that in the results.
- **12:01Z, hand/cycle fix DONE** (`reports/live/integration/HAND-FIX.md`).
  - Own hand is now TRACKED from the opening order and our own plays; the HUD only breaks ties.
  - Corrections in 5.1% of PERC-emp polls, 0 invariant breaks.
  - The `native_failure` and `search_failures` stats are now logged.
  - Tests: 61 pass, 1 skip (the panic repro, now a no-op on r1-total).
  - **Note:** the running K4L rerun (code from 5cb79878) predates this fix, but it's consistent within its own run.
    Later PERC numbers will include it.
- **12:27Z, ablation DONE** (`reports/live/perception/ABLATION.md`).
  - The floor arm is level with perfect sight, so the method is valid.
  - **Unit noise is the lever:** +0.06–0.07 (misses +0.04–0.05, phantoms +0.02–0.08).
  - **Spells don't matter much:** about 0; all events only +0.02–0.03. HUD +0.01–0.02.
  - The perc-r2 owner was told to put units first.
- **12:27Z, K4L rerun restarted on 0–59** (new PGID 228307, resumed from 290 rows).
- **13:23Z, K4L PERC rerun DONE:** 1,200 games, 0 errors, **0 panics**, on r1-total with code from 5cb79878.
  - Perfect-sight K4L: 0.807 vs R3a, 0.947 vs v1. PERC-emp:K4L: 0.607 / 0.877.
  - **Δ R3a −0.200 [−0.263, −0.137], v1 −0.070 [−0.113, −0.023].**
  - Under noise K4L still beats it5s2 (0.607 vs 0.523 R3a; 0.877 vs 0.770 v1; different code versions).
  - The default share isn't available: headline rows carry no per-decision stats. TODO: add it to the runner.
- **13:23Z, unit-threshold test launched on 03 0–59:** PGID 386848; arms fresh PERC-emp, -sr1u50, -sr1u55; 1,800
  games. Out dir `live-perc-thr-ours`; code in `clasher-live-eval3`.
- **13:53Z, unit-threshold test DONE:** u50 +0.020/+0.020 (n.s.); u55 +0.017/−0.037.
  - **Decision: deployed unit threshold 0.4 → 0.5**, provisional; round 2 picks its own.
  - 03 handed back to the bot lead.
- **13:56Z, bot lead started `bot-lead-noise-robust-r1`** (decisions given a noisy view; target K4L
  under PERC-emp vs R3a, now −0.200).
  - Boundary: LIVE owns everything up to the perceived view; they send hook diffs to us.
  - **Tell them whenever the noise statistics change:** u50 now, r2 at ~15–16Z.
- **14:42Z, round-2 training done: no unit gain.**
  - ft-r3b (ea104903…) lands on r1's precision/recall curve. Phantom proxy, best point: r1 .161 vs r2 .1585, a tie.
  - Count extras hurt at every threshold.
  - What r2 does add: Royal Ghost, spell-effect detections, a switchable count head.
  - **01 GPU released to the bot lead at 14:42Z.**
  - Next, CPU only: decode-side phantom filters (cross-identity NMS, persistence and hysteresis), one sim command,
    RESULTS-R2.
  - Default deploy stays r1 at 0.5.
- **14:43Z, Mac bench on the Mac.**
  - Parity is **bit-exact 600/600** (Mac native 617bfef4, from native-source-v2 + NATIVE-TOTAL.diff; the same tree
    gives 681b5f2c on 05).
  - The audit failed on a macOS pipe-path artefact; the owner stopped, fixed it (TA7) and re-ran the suite 98/98.
  - **GO given** to resume, with `retire-bundle` approved.
  - Fleet v4 baseline on r1-total: K4L p50/p95/p99 61.0/141.2/191.8 ms, default 0.8%; i10 56.5/134.7/185.5, 0.5%.
- **14:55Z, PERC-R2 unit filter** (hysteresis .5/.25 plus owner NMS .6):
  - r1: recall .760 → .801, phantoms .110 → .083/frame, proxy .161 → .174 (odd half .172);
  - r2 with the filter: .819 / .094, proxy .176.
  - Round-2 code committed as **ba4e560e**.
  - CPU requested from the bot lead for the 4-arm sim (sr1u50, sr1f, sr2u55, r2; 2,400 games) →
    `live-perc-r2-ours`.
- **14:56Z, r2 sim HELD** at the perception owner's request: the Ghost truth-label bias (Royal Ghost is half of r2's phantoms). The 4 JSONs are being refit on common all-Ghost truth. Then the sim runs on 127x04, 36 workers, via the bot lead's `cpu_job.sh 36` lease wrapper.
- **15:02Z, r2 sim launched on 127x04** via `cpu_job.sh 36` (PGID 3133738; it waits for room, then runs).
  - Code: main **f0eabd1d**, the all-Ghost refit (r2 JSON sha c753b9bf).
  - Out dir `04:/mpac/sdicks02/jobs/clasher/live-perc-r2-ours`; perfect-sight reference copied to
    `04:…/live-perc-r2-ours-ref/fast` (600 rows).
  - Filter re-selected at hi .45 / lo .25 / nms .6. Proxy: r1u50 .161, r1f .178, r2u55 .162, r2 .183.
- **16:39Z, r2 sim DONE:** 2,400 games, 0 errors. The filter and r2 show **no measurable gain** vs r1u50; all
  within ±0.06, and the filter leans −0.05 vs R3a.
  - **Deployed perception stays r1 at threshold 0.5, no filter.**
  - Renderer-side decode tuning is saturated at sim resolution. The next lever is the official-client domain gap
    (blocked on Sam).
- **17:02Z, coordinator approved the Mac disk cleanup:** android-sdk 10.2 GB, npm, pnpm prune, Chrome
  cache, brew, and 4 cache dirs.
  - Excluded: Codex caches, cargo registry, and everything in list C.
  - Script `reports/live/mac-ops/disk_cleanup.zsh` is in Sol review (`live-mac-disk-cleanup-sol-r1`).
  - The script skips the Chrome cache if Chrome is running.
- **BlueStacks trial owner** `live-bluestacks-trial-owner-r1`: item 2 (RAM with the VM up) and item 3 (guest
  account without Google, Supercell-signed sideload).
  - Phase 1 (APK on 05 plus the scripts) ends at the Sol gate. Stop rule: no evasion.
- **17:04Z, Mac disk cleanup DONE:** `reports/live/mac-ops/disk_cleanup.zsh`, Sol r1 fixes applied, dry run first.
  - Free space **7.9 → 19.96 GiB** (21.4 GB), 12 GiB freed, `__RC=0`.
  - Removed: android-sdk 10.2 GiB, npm 0.5 GiB, pnpm prune, the Homebrew download cache, colima, t3code-updater,
    electron and node-gyp caches.
  - The Chrome cache was skipped because Chrome was running.
  - `brew cleanup` was narrowed to the download cache only, per Sol: it would otherwise remove kegs.
- **17:33Z, BlueStacks trial phase 1 done** (`reports/live/mac-ops/bluestacks/`).
  - APK: CR versionCode 160402020, 5 splits, Supercell cert 59ea9ded verified (arm64 variant).
  - Own adb r37.0.1 on port 5047. Offline harness 41/41.
  - Notes: the console user is `simonfarshid` (Sam's session runs in the background); RAM is tight with the VM up
    (swap 8.1/9.2 GB).
  - **Rulings:** the conf ADB-key edit is accepted; guard = pressure critical for 30 s or disk < 6 GiB; on a stale
    lock, stop; scrcpy decided later.
  - **Sol review** `live-bluestacks-sol-review-r1` is running. After the fixes, GO for phase 2 without another stop.
- **17:38Z, Sol review of the BlueStacks scripts: OK after fixes** (6 blockers: RC masking, unverified fetch, whole-conf restore, PID adoption, orphan VM processes, unowned adb kill-server; plus 3 should-fixes). Sent to the owner; GO for phase 2 once the offline suite is green with a mutation-checked test per finding.
- **20:34Z, RL r5 v10 student check under deployed noise launched on 04** via `cpu_job.sh 36` (PGID 605836).
  - Checkpoint `policy-00010.pt`, sha e188e2ae verified.
  - Arms: PERC-emp-sr1u50 with it5s2 vs rl5 (paired), plus rl5 perfect sight. 1,800 games.
  - Out dir `04:/mpac/sdicks02/jobs/clasher/live-rl5-perc-ours`.
  - Bot lead, fresh bank F9 vs it5s2: +0.059 [+0.031, +0.087]. K2-D multi-root is NOT confirmed.
- **~18:3xZ, BlueStacks phase 2:** the stop rule triggered.
  - BlueStacks boots in 23.6 s with the VM up: pressure warn, swap 9.2 → 11.3 GB, **RAM item answered**.
  - The client (sideloaded, ADB on) dies 115 ms after start in nativeLoad ("Report: Exiting", `lskumcyej.e: 02`),
    the same signature as the AVDs.
- **20:39Z, coordinator ruling:** reproduce a stock player setup (that's not evasion).
  - Ladder: **A** = ADB off (restore) plus a non-adb launch; **B** = Play install, prepared for Sam.
  - Relayed to the trial owner.
  - New possible Sam item: the console session is `simonfarshid`'s, and macOS input/capture likely needs Sam's
    session on the console.
- **20:44Z, native iPad-on-Mac route CLOSED:** Clash Royale has isIOSBinaryMacOSCompatible=false (Among Us control: true; all Supercell games false). Play Games on Win-on-Arm is not viable. BlueStacks stays primary.
- **20:45Z, PRIORITY (Sam): bring up BlueStacks with the Google Play sign-in screen in sam's session.**
  - Trial owner steered to: launch, then `open_play` (am start only), then a screenshot. No credentials, no CR
    launch.
  - **Sam access verified read-only:** Screen Sharing on, ARD all local users with full privileges,
    `mac-mini` 100.101.16.91:5900 answers `RFB 003.889` over the tailnet, and sam's GUI session exists in the
    background (the console is simonfarshid's).
  - Sam instructions sent to the coordinator: `vnc://mac-mini`, user sam, **"Log in as yourself"**.
- **20:50Z, Google Play Sign-in screen UP** in sam's session (BlueStacks PID 7218, guard until ~00:46Z; screenshot verified). Waiting for Sam to sign in. Next: uninstall the sideload, Play install, ADB off, stock launch.
- **20:57Z, bot lead heads-up:** a perceived opponent revealed-set contamination (a wrong card in 29/34 games; the cap of 8 locks out a real card, and the sanitizer drops its units) may explain much of K4L's −0.20. Their r3 worker is prototyping an evidence-ranked set and will send a diff for bot/live/*. Our review checks: fairness, one rule for plays and board, resync, and a paired Δ.
- **21:36Z, SAM: "its running on bluestacks".**
  - Read-only checks: Sam restarted BlueStacks (new PID 65579; our 7218 is gone; our guard is inert); conf still has
    ADB=1; our adb went offline at his restart.
  - macOS screencapture from ssh fails (no Screen Recording permission, background session).
  - Asked Sam via the coordinator: how it was installed and launched, the current screen, the ADB toggle state.
    That decides adb I/O vs macOS I/O (which needs TCC permissions and an active session).
  - Holding Mac actions.
- **21:40Z, MILESTONE: the official CR is running on BlueStacks** (Sam installed it from the Play Store, so the
  sideload was the crash cause).
  - Sam granted Screen Recording to tailscaled; **macOS screencapture over ssh works** (3840×2160).
  - The client is on its home screen, Training Progress 1/3, Battle highlighted.
  - Next: an Accessibility grant for clicks (Sam), a fast ScreenCaptureKit helper (Sol look), recording Training
    battle 2, the perception domain-gap check, calibration, then the first bot battle.
  - Not using ADB.
- **21:46Z, Mac mailbox created** at `~/clasher-live/mailbox/` (requests.jsonl, responses.jsonl, shots/). The Mac-side T3 thread (Sam's session, computer use) handles slow GUI work only. Waiting for its status.json heartbeat before sending r0001 (look only).
- **21:51Z, macOS I/O verified from ssh:** screencapture OK; CGEvent mouse-move accepted
  (AXIsProcessTrusted=true).
  - Codex computer use is still denied, so it's fallback only. The mailbox is dropped (STOP file written).
- **Mac bench DONE** (`reports/live/MAC-BENCH.md`):
  - live tier LIVE-K4L-R-gs-rw-fc-w200-t4-p4: p50/p95/p99 22.7/48.9/79.8 ms with perception at 10 FPS, 0% defaults;
  - Mac about 2.8× fleet per core;
  - perception cpu-ev2 50.8 ms/frame.
- **LIVE loop owner launched** (`live-loop-owner-r1`): capture helper, click helper, 16:9-vs-19:9 calibration,
  record TC battle 2, domain-gap check, first bot TC battle. Sol review before each new Mac script.
- **22:01Z, RL r5 v10 under deployed noise:** rl5 vs it5s2 (both sr1u50) R3a +0.032 [−0.032, +0.097], v1 +0.040
  [−0.013, +0.093]; 1,800 games, 0 errors.
  - **Adopted as the live fast tier and cutoff default:** CLASHER_LIVE_FAST=student:.../policy-00010.pt@0.5375,
    sha e188e2ae. it5s2 is kept as the rollback.
  - 04 handed back.
- **22:02Z, Sam: "you can live test on the Mac".** The coordinator sent the loop owner a direct GO (FPS test, one harmless tap, rl5 smoke, TC battle 2, domain gap). The Sol review of the live/loop helpers runs in parallel and doesn't block (`live-loop-helpers-sol-r1`). From now on live testing beats pre-review, within the limits: TC only, no purchases, no credentials, no evasion.
- **22:03Z, Sam: full in-game authority on the throwaway account.** Ladder, gems, gold, decks, chests and menus are all allowed; bans are accepted. Still off-limits: real-money payments, credentials/sign-ins, other Mac apps/users/files outside ~/clasher-live, and client or emulator modification to hide the bot. TC is the first loop check only; go to ladder once one full battle runs cleanly. Report W/L per battle with video. The coordinator told the loop owner.
- **22:06Z, Sol review of live/loop (parallel):** 2 blockers (per-event target validation; mouse-up on interrupt) and 8 should-fixes. Sent to the loop owner: fix #1–#2 before any battle; single test taps allowed meanwhile.
- **~22:20Z, loop owner on official frames:** account "bigdiddle", 0 trophies, Goblin Stadium.
  - Deck: Knight, Archers, Minions, Arrows, Fireball, Giant, MiniPekka, Musketeer (all C56).
  - Recorded 2 TC battles plus 1 ladder match with the bot idle (0–3).
  - Mapping: arena scale 0.903; HUD remapped.
  - **Perception on official frames:** hand ~98–99%, towers OK, elixir/clock/phase broken (being replaced),
    **units ZERO** (sand vs grass arena skin).
  - The first bot battle will be near-blind to units.
- **22:46Z, perception r3 launched** (`live-perc-r3-owner-r1`): official-arena compositing fine-tune
  of the unit head, evaluated on a hand-labelled official set. GPU (01 preferred) requested from the bot lead.
- **22:47Z, bot lead:** 01 A6000 for perception r3, ~6–8 h, free around 23:05Z (they'll post "01 GPU free"). Forward that to the r3 owner.
- **22:48Z, coordinator/Sam on r3:** (1) diagnose "zero units" first (pipeline: crop/scale/colour/normalization; raw max scores; sprite appearance; paste test) and report before the long fit; (2) make it background-invariant (many backgrounds including random textures and jitter; validate on labelled official frames plus a held-out arena). Relayed to the r3 owner. The loop owner now saves empty-arena frames for every new arena.
- **22:49Z: 01 A6000 free** for perception r3 (bot lead); forwarded to the r3 owner. Window until ~06:00Z at the latest; the diagnosis report comes before the long fit.
- **22:51Z, r3 "zero units" diagnosis: no pipeline bug** (BGR, scale and normalization correct; the
  grid aligns).
  - Official unit scores are 0.28–0.72 (renderer 0.89–0.95), with wrong cards at the peaks.
  - Arena decorations give steady FPs at 0.3–0.4.
  - Paste test: renderer units in a Goblin Stadium frame drop from ~0.9 to ~0.4. **The model keys on the arena.**
  - **GO for the background-invariant fit:** compositing onto many backgrounds plus hard negatives; Training Camp
    held out; ~80-frame hand-labelled official set; event head preserved; interim export as soon as it beats r1.
- **22:53Z, MILESTONE: the bot plays live ladder in the official client. 3 battles, 3 W (3–0 each),
  trophies 0 → 93**; live4 in progress.
  - Input: ADB taps (Sam's choice, "nah A"; the client is fine with ADB on).
  - Tower HP from the on-tower numbers; overlay at Mac localhost:8765.
  - Still nearly blind to units (median 0 per frame). Low-trophy opponents are weak, so not strength evidence.
  - The loop owner confirms no pipeline bug. Arena backgrounds at `05:scratch/live-loop/arena-bgs/goblin-stadium/`;
    native capture 1020×1816 available. Forwarded to r3.
- **~23:05Z, live ladder:** live1–5 all W 3–0, **0 → 154 trophies** (low-trophy opponents).
  - Sam asked that the overlay show the raw model view (heatmap plus sub-threshold candidates), and that we not patch
    around perception gaps without asking.
- **~23:05Z, perception r3 fit `ft-r4` running on the 01 A6000** (PID 2307911, 5 h budget, ends ~04:05Z).
  - Data: ~70% composited (8 Goblin Stadium floors, recoloured renderer floors, procedural textures, 6% empty-floor
    negatives); Training Camp held out; blur matching the 720×1280 capture.
  - Labelled official set: 81 frames (51 Goblin Stadium, 30 Training Camp), labelled by 5 Opus helpers with
    confidence ratings.
  - Round-1 baselines: renderer units P/R .952/.762; event .915/.742; decoration FP 1.0/frame on empty Training
    Camp, 0 on Goblin Stadium.
  - Checkpoints mirrored to 05 every 5 minutes.
- **23:22Z, perception r3 INTERIM export (epoch 1) delivered to the loop owner:**
  `/mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-e1/` (05 and 01); rollback `export-final`.
  - Official unit P/R at 0.5, 74 labelled frames: Goblin Stadium .83/.06 → **.975/.245**; Training Camp (held out)
    .18/.03 → **.93/.26**.
  - Empty-frame false positives: Goblin Stadium 0 → 0, Training Camp 1.0 → 0.
  - Still misses most Minions and Archers. Renderer val dip: unit F1 .846 → .816.
  - Trainer PID 2322178, GPU 62–83%.
- **23:22Z, live ladder: 10 battles, 8 W / 2 L, 228 trophies** (live10 W 3–0). Next arena unlock at 300; the loop owner will capture empty-arena frames for r3.
- **23:24Z, r3 epoch 2:** Goblin Stadium units P/R .898/.277; Training Camp .969/.320; 0 empty-frame FPs; renderer val recovering (unit F1 .821). Swap record sent to the loop owner (frame.pt 9b06f968, event.pt cc75886f, vocab d39b06bb). Asked for a threshold sweep (0.30–0.50) on the official set, plus a check of small units vs native-res capture.
- **23:32Z, r3 recall checks:**
  - **Threshold:** 0.5 kept (the proxy is flat over 0.40–0.50, and only 0.5 has 0 empty-frame FPs; at 0.30, R .48
    but P .68).
  - **Resolution:** not the cause (simulated degradation leaves recall flat).
  - **Root cause: level badge plus HP bar.** The renderer draws them over every unit; the official client draws them
    only on damaged units, and the detector keyed on them. Per-card recall at 0.4: Archers 13/37, Minions 14/51,
    Knight 12/21.
  - **ft-r5** drops the badge/HP strip for 60% of units (PID 2425017, from the r4 epoch-4 checkpoint, ends ~04:20Z).
- **23:36Z, live ladder: 11 battles, 9W–2L, 258 trophies.**
  - The driver now runs a session (up to 3 battles per driver; the overlay stays up).
  - **Elixir reader fix:** it now counts the partial (light-blue) segment. Before, the bot saw only whole elixir in
    all 11 battles.
  - Overlay is at ~7.5 FPS. Archers are back in the deck (Sam's upgrades).
  - Each run logs the perception export sha.
  - Committed as a93a24c6.
- **23:42Z, live: 12 battles, 10W–2L, 291 trophies; new arena Bone Pit (sand).**
  - **Tower-HP OCR bug:** bright stone on the full-HP king read as "3"/"31", so the bot spent 7 elixir (Fireball +
    Arrows) on a "nearly dead" king (won anyway, 3–0).
  - Fixed: digit-match distance gate, rows with non-digit shapes discarded; verified on 5 recordings. The bad session
    was stopped before its next battle.
  - Bone Pit backgrounds saved; told r3 to use Bone Pit as a second unseen-arena test.
- **00:00Z, live: 13 battles, 11W–2L, 321 trophies** (all played with r1 perception so far).
- **r3 ft-r5 (badge strip) works.** Epoch 3 at 0.5:
  - Goblin Stadium .959/.440 (e1 .975/.245);
  - Training Camp .1.000/.485;
  - **Bone Pit (unseen)** .857/.400 (r1 .750/.200);
  - 0 empty-frame FPs; renderer unit F1 .828.
  - **Interim 2** (`export-interim-r5e3`, frame.pt 81697f5b) sent to the loop owner.
- **00:01Z, interim 2 (r5e3) is LIVE** (session s5).
  - **Sam's observations, diagnosed:**
    - (1) Few past-bridge plays after a tower falls: a real weakness from near-blind unit perception (the search
      guards its own towers). It will be measured r1 vs r5e3.
    - (2) Past-bridge attempts with no tower down: a **bug**. Dimmed screens hid the tower digits, and the reader
      declared towers dead after 2 s. Fixed with brightness normalization, a 6 s dead rule on healthy frames, and the
      driver pausing on dim/black frames. Verified live.
- **00:02Z, r5e3 swap done** (sha OK; Bone Pit replay: units per frame 1.53 → 2.30, frames with ≥1 unit
  86% → 94%; own Archers 23 → 113, Minions 0 → 28).
  - **Record: 15 battles, 11W–4L, now 300 trophies.**
  - Two of the losses were broken by the driver (dim screen mid-battle with the bot paused; driver stopped for the
    reader fixes) and are marked as such.
  - r5e3 is playing session s5; the comparison vs r1 comes after 3+ battles.
- **00:04Z, coordinator rulings on Sam's observations, assigned:**
  - **Pocket play** (r1 vs r5e3 measurement; decision states go to the bot lead if unchanged) and **overlay naming**
    ("Skeleton (Skeleton Army)"): loop owner.
  - **Multi-body play-counting correctness** (Skeleton Army, Goblin Gang, Minion Horde, Barbarians, Bats, Guards,
    etc.; spawns must count 0) and **OOV placeholders** in the translator: new owner `live-translator-oov-owner-r1`.
  - **OOV inventory:** loop owner, from the in-game Battle Log (both decks per battle, back-filled ~25), into
    `reports/live/loop/opponent-decks.jsonl`, with no opponent names.
  - Per-arena card lists: Haiku → `ARENA-CARDS.md`.
  - **UNKNOWN_UNIT/BUILDING perception class**, then specific identities: r3 owner, after ft-r5.
  - Engine additions for the most frequent missing cards: bot lead (coordinator-assigned).
- **00:06Z, CARD LEAD** (thread `…clasher-card-lead-20261016-r1`) now owns adding all non-C56 cards to the
  engine (Sam's request). LIVE keeps perception identities, the unknown class, `bot/live/` and the live native pin.
  - Intro sent to the card lead; the inventory goes to them when the first versions land (Battle Log jsonl plus
    ARENA-CARDS.md).
  - The translator owner now coordinates the engine representation with the card lead.
- **Shared-sprite ambiguity** (Skeletons vs Skeleton Army, Goblins vs Goblin Gang, Minions vs Horde): the card has to
  be inferred at spawn from the burst. Sent to the translator owner (check plus fix) and the r3 owner (body classes
  later).
- **00:07Z, bot lead #2/#3:** the proxy-card plan fits (true id in the revealed set/cycle, proxy only as the board entity; must carry true cost; class-only unknowns can't fill the 8-card set; sanitizer keyed by true id). Pocket replay: the logs lack perception records, so the loop owner was asked to log perception.jsonl + session-config.json per battle (offline LiveSession replay), reconstruct past battles, and write pocket-moments.jsonl.
- **00:11Z, routing change (Sam): Claude low, so new workers are GPT-6.1-Sol (high), Haiku OK, Opus only if Sol fails.** The loop, r3 and translator Opus owners were asked for self-contained HANDOFF.md files at their next checkpoint; Sol successors follow. The live Mac processes keep running.
- **00:11Z, routing final (Sam): code workers stay Opus; Sol for evals, research, analysis, reviews and loop babysitting; Haiku narrow.** Handoffs cancelled for r3 and the translator. The loop owner finishes its code items, then hands the per-battle babysitting to a Sol worker.
- **00:12Z, r3 plan approved:** ft-r5 plateaued, so stop after epoch 8; export the best epoch (3–8) as ft-r5 final to the loop owner; then ft-r6 with the AnyTroop/AnyBuilding head (~04:30Z); evals and export; release the 01 GPU by ~06:00Z. Routing: no recently started worker suits Sol right now (the translator owner is code-heavy and stays Opus).
- **00:15Z, bot lead revealed-set fix** (patch sha 90835df8, commit 67a26536): strength NOT CONFIRMED (+0.013 [−0.003, +0.028] pooled; K4L vs R3a +0.017 [−0.008, +0.042]). Correctness: real opponent units dropped per game fall 24→1 (R3a) and 36→2 (v1); bit-identical on clean channels; my checks (a)–(d) met; `_admit` time-backwards bug fixed. **Decision:** adopt on correctness, gated on the Sol review. The translator owner applies it first, then layers OOV on revealed.py; the loop owner deploys between battles.
- **00:20Z, revealed-set patch on HOLD:** Sol says merge after fixes. Three should-fix items: board-only admits skip belief/cycle; sanitize runs before evict within a frame; catch-up polls duplicate evidence (live-specific). A bot-lead Opus worker is fixing them, then a Sol re-review, then the final sha comes to me. The translator owner is told not to apply 67a26536.
- **00:29Z, Battle Log inventory v1** committed (9b93d324) and forwarded to the CARD LEAD. 18 battles. Non-C56 cards faced: SpearGoblins 8, GoblinCage 6, Tombstone 4, Bomber 1. Auto-navigation is live and s7, a 4-battle unattended session, is running. 391 trophies. Logging perception.jsonl + session-config.json per battle from s6. The r5e3 battles s5-m01, s5-m02 and s6-m01 were all 3-0 wins.
- **00:30Z, pocket-moments v1** committed (77b0899f) and forwarded to the bot lead. Pocket-play share of bot plays after taking a tower: r1 29% (13 stretches, 100 plays) vs r5e3 24% (5 stretches, 29 plays); small n, s7 adding. Exact LiveSession inputs exist for s6+ only (one stretch); reconstruction of earlier runs is next.
- **00:42Z, live client version is 16.402** (versionCode 160402020; Play install at 2026-10-15 21:31Z), which matches RoyaleSim 16.402 data. Forwarded to the CARD LEAD and the bot lead. The CARD LEAD builds a `live16402` stats pin; it gets switched in after the bot lead's sim check. The driver logs the client version per battle from s8.
- **00:43Z, live16402 swap gate (bot lead):**
  - 0-error runs of K4L-live plus the fast tier on mixed decks;
  - a sim check of K4L vs R3a/v1 on 200 cases under both pins;
  - then a joint swap decision.
  - Note: RoyaleSim's data is build 160402017; live is 160402020 (a patch-level difference).
- **00:43Z, C56 stats diff (CARD LEAD):** 13/56 C56 cards differ materially from RoyaleSim 16.402.19.
  - Largest: Wizard +8% damage; Xbow; Goblinstein doctor +47%; Wallbreakers −14%; Ghost/IceGolem/Spirits HP −5–7%; Spear Goblin hit speed 1.7→1.6 s (Goblin Gang/Hut).
  - 22/66 non-C56 cards also differ.
  - Details: reports/cards/stats/BALANCE-SIZE.md (cards/lead).
  - Next: the live16402 pin → the bot lead's swap gate.
- **00:46Z, loop handover.**
  - Loop files are committed (38648cee).
  - A Sol babysitter (`live-ladder-babysitter-sol-r1`, codex gpt-6.1-sol high) now runs the ladder from loop/HANDOFF.md, and the loop owner is going idle.
  - Per-frame perception records exist for all 21 runs (live-logged from s6, reconstructed before that) and are forwarded to the bot lead.
  - Results: 20 battles, 16-4, 451 trophies; r5e3 5-0 plus the s4 incident.
  - **Multi-body counting fix** (translator, births.py): a real opponent elixir/cycle bug, with extras on r1 pred down 161→21 and SkeletonArmy 52→19 (17 true). Gate: a frozen patch, then a Sol review plus the bot lead's PERC-emp no-regression A/B, then commit and deploy at a session boundary.
- **00:48Z, s8-m04 lost 0–1 in overtime** (−14 trophies). Perception r5e3, 0 step errors. No sign of a driver incident yet; reconciliation is pending. s9 (Mac PID 81424) was started by the Sol babysitter.
- **00:50Z, s9 driver incident.**
  - Crashed at session start, before any battle: the client-version block shadowed `out`.
  - Fixed in b152532e and deployed to the Mac (drive.py 9665bb3e…; backup .bak-7c1a5e63). The babysitter restarts as s9b after the Battle Log.
  - Losses reconciled from video and the Battle Log: s7-m03 L 0–1, s8-m02 L 0–3, s8-m04 L 0–1 (512→498).
  - s8-m04 was a real bot loss, with no reader faults. Its opponent ran Bomber/SpearGoblins/Tombstone (non-C56).
- **00:57Z, ladder results:** 27 battles, 19W–8L, 484 trophies.
  - Recent results: 3W–4L since about 450 trophies, with clean losses (no reader faults), against opponents with Bomber/SpearGoblins/Tombstone.
  - Reports committed as 55c6df14.
  - Sam asked the loop owner directly for pause/resume and deck-from-screen buttons on the overlay; that's in progress. I told it to keep my b152532e fix, test the live startup path, and deploy at a session boundary via the babysitter, refusing non-C56 decks until proxies land.
  - The babysitter's loss-report rule is relaxed (anomalies only).
- **00:58Z, multi-body patch frozen** (sha 9ea9e745…; 97 passed, 1 skipped). The Sol review `live-multibody-review-sol-r1` is running, and the bot lead runs the PERC-emp no-regression A/B.
- **00:59Z, births A/B running** (bot-lead-multibody-ab-sol-r1 on 03).
  - Arms, paired on HEADLINE 0–299 vs R3a/v1:
    - K4L PERC-emp, 600 games per tree;
    - fast tier, 600 per tree;
    - clean-channel arm, 60 games.
  - Gate: pooled K4L CI lower bound ≥ −0.03 and 0 errors.
- **01:00Z, revealed-set r2** (sha b1d81add…, commit 7d873ca8): all 3 Sol findings fixed (+6 tests).
  - It now tags LiveSession records with _frame/_synthetic.
  - Clean channel: 30/30 identical. Noisy smoke: 40 games, 0 errors.
  - Sol re-review running, including composition with multibody.patch. HOLD the merge until its verdict.
  - Planned merge order: multibody, then revealed-set, then OOV item 2.
- **01:03Z, Sam's overlay controls:** Pause/Resume + PAUSE file + read deck from screen, with an out-of-scope block. Committed as 58fb7d5b (control_test 18/18 on the live path, with tap gating checked). The babysitter deploys at the s9b→s10 boundary with hash checks and a rollback path.
- **01:05Z, possible DECK MISMATCH:** the Battle Deck screenshot taken around 00:55Z shows Goblin Cage replacing Archers (average 3.8), while the driver still assumes Archers. s9b-m01 logged 5 Archers plays. The babysitter will stop s9b at the battle end, verify the deck read-only, then deploy 58fb7d5b and hold battles BLOCKED/paused. We don't change Sam's deck. Sam to be told.
- **01:05Z, deck mismatch = FALSE ALARM.** deckpage.png was an old crop (23:27:39Z, before the loop owner swapped Goblin Cage→Archers at 23:28:19Z). The live deck is the standard C56 deck. The babysitter continues with the deploy at the s9b→s10 boundary.
- **01:06Z, Sol review r1 of multibody (9ea9e745): MERGE AFTER FIXES.**
  - Findings: 5 must-fix (suppression eating genuine plays: Goblins by a live hut, cross-lane leftovers, Cannon replacement revival, FireSpirits by a hut, Knight absorbed into a Miner burst) and 1 should-fix (FirespiritHut memory).
  - Performance: 2.1 ms p95 at 40 bodies.
  - Next: the translator does a class audit (checklist table, a test per path, mutation checks), then re-freezes, then Sol r2.
  - The bot lead's A/B continues; a smaller K4L confirmation follows on the final patch.
- **01:07Z, controls live.**
  - The loop owner hash-deployed 58fb7d5b and started s10 (PID 36003) after s9b ended, because Sam couldn't see the controls.
  - s10 started paused (PAUSE file, now gone). It's now paused from the page, presumably Sam.
  - The babysitter is the sole Mac operator; the loop owner is idle.
- **01:08Z, revealed-set r2 Sol review: MERGE AFTER FIXES**, with composition issues against multibody.
  - Blocker: `_body` signature changed. Also: duplicate plays and an elixir ledger at 0; composition loss; tick dedup; Skeletons evicting Army; evicted tracks leaking.
  - The translator re-freeze adds a public births API (resolved identities, bodies_of/family_of, forget_card). The bot lead rebases onto the final multibody.
  - Babysitter: s10-m01 was a 4.8 s false match while Sam was in the menus. Planned fix: ignore matches shorter than 30 s (Opus, later). The bot lead's duplicate launch (PID 37460) failed safely at mkdir, and s10.log was truncated.
- **01:09Z, births API spec** from the bot lead, relayed to the translator. Required: snapshot/restore, last_tracks, resolve. Refinements: identity, forget_card, bodies_of/family_of. It goes into the multibody re-freeze.
- **01:10Z, s9b done:** L 1–3, W 3–0, W 1–0, L 0–3; 30 battles total, 21W–9L, 530 trophies. All r5e3, 0 faults. Committed as fa2e637b.
  - s10 is page-paused with Sam in the menus. Sam read a new deck (Valkyrie, Archers, Minions, Skeletons, Fireball, Giant, MiniPekka, Musketeer; all C56), not applied yet.
  - Second false match (s10-m02, 4.5 s) sent to the loop owner's fix.
- **01:11Z, Sam applied a new deck and resumed (s10-m03):** Valkyrie, Archers, Minions, Skeletons, Fireball, Giant, MiniPekka, Musketeer (all C56). paused=false, no out-of-scope cards. Laddering resumed.
- **01:17Z, false-match fix committed** (6c720d67; s10 m01/m02 replay gives 0 starts, 1658 battle frames unchanged, tests 9/9 + 18/18). The babysitter deploys it at the s10→s11 boundary.
- **Sam: 'we need spear gobs, tombstone and bomber detection'.**
  - Perception: the r3 owner adds these 4 cards (plus GoblinCage) as the next fine-tune after ft-r6, from labelled official crops.
  - The loop owner writes newcard-manifest.jsonl (battles × cards × video paths).
  - The CARD LEAD supplies names, bodies and ETAs (engine cards vs proxies).
- **01:17Z, CARD LEAD bodies:** SpearGoblins = 3× SpearGoblin (shared with the GoblinGang/Hut sprite); Tombstone = building + Skeleton spawns (shared sprite); GoblinCage = building + GoblinBrawler (distinct); Bomber (distinct).
  - ETA: proxies on main in ~1–2 h. r1-cards1 (full scope, C56 bit-identical) ready for the bot lead's review in ~2–3 h; live16402 later.
  - Implication: the SpearGoblin and Skeleton bodies are already perceivable (as GoblinGang/Skeletons labels), so translator OOV item 2 can infer SpearGoblins/Tombstone from shared bodies plus the battle log, while perception adds the Tombstone/GoblinCage/Bomber/Brawler identities.
- **01:18Z, new-card manifest** committed (ce82d4d2): 17 battles with target cards, all with video on 05. Sent to the r3 owner by the loop owner. The babysitter re-runs it after each inventory.
- **01:23Z, PYTHONHASHSEED live bug** (bot lead's question): the live process was unseeded, and R.meta card tokens differ by seed for BarbLog (24 vs 20), Ghost (289 vs 114) and BlowdartGoblin.
  - Live impact so far: very likely none (none of these cards in our or opponent decks yet).
  - Fixed: run.sh exports PYTHONHASHSEED=0, verified on the Mac. Plus drive.py --out collision hardening. Committed as 3d346510; deploys at s11→s12.
  - s10 restart stall: name reuse gave FileExistsError, so the babysitter started s11 (PID 73430) with Sam's new deck.
  - Coordinator: new perception plan (fresh pretrain, 122 cards, official assets) — plan due.
- **01:29Z, perception path → YOLO** (Sam and coordinator). Launched:
  - `live-katacr-baseline-sol-r1`: KataCR v0.7.13 baseline on the r3 official set, ETA 1–2 h.
  - `live-yolo-integration-opus-r1`: CoreML/MPS speed during live play plus a YoloUnits adapter (--units yolo:).
  - `live-nulls-generator-opus-r1`: Null's Royale labelled frames from the reference AVD (T1 seal lifted); plan in ~45 min. It also provides native-fixture slots for the CARD LEAD.
  - r3 owner: finish ft-r6 (fallback); ft-r7 cancelled; labelling redirected to YOLO-format live labels plus the held-out split.
  - YOLO fine-tune: after the Null's data exists (~T+6–12 h) on 01 plus 04/08 (6–10 GPU-h; bot lead needs 1 h notice).
  - Sam: stop sealing; speed is not a blocker. Plan reported to the coordinator. arena-card-freq.json (70b27ec7) sent to the bot lead.
- **Ladder:** s11 m01 W 1–0 (620), m02 W 2–1 (654). 33 battles, 24W–9L. Barbarian Bowl reached; --arena barbarian-bowl from s12.
- **01:30Z, r3 owner:** ft-r6 epoch 3 beats ft-r5 final (GS .975/.497, TC 1.0/.557, BP .849/.397; 0 empty-frame FPs).
  - ft-r6 done ~04:10Z, export ~04:50Z → babysitter swap.
  - EVAL-SPLIT.md written (held-out battles: 134 frames, 472 units).
  - Labelling redirected to full YOLO-format labels (208 training frames, 7 helpers). ft-r7 cancelled.
  - The r3 owner now owns the YOLO fine-tune.
- **01:32Z, s11 went 4–0** (W 1–0, 2–1, 1–0, 2–1; 590→714). 35 battles, 26W–9L. step p95 31–35 ms at 6.8–6.9 FPS. 3d346510 deployed (hashes match); s12 starting with --arena barbarian-bowl and a PYTHONHASHSEED check pending.
- **01:35Z, compute compression (Sam: 'hella compute').**
  - All 3 A6000s go to YOLO; 04/08 freed at 01:35Z.
  - YOLO v1 starts now under the r3 owner (KataCR init + KataCR MIT dataset + r3 labels; parallel variants).
  - `live-yolo-synth-compositor-opus-r1` launched: millions of composited frames on 03/04/08 CPU leases.
  - Null's refocused to per-card cut-outs.
  - Revised ETAs sent to the coordinator: KataCR numbers ~02:30Z, YOLO v1 candidate ~05–06Z, CoreML adapter ~04–05Z, go-live ~05–06:30Z, v2 ~10–14Z.
  - s12 live with PYTHONHASHSEED=0 confirmed. Mac disk 9.8 GiB.
- **01:36Z, s12-m01 L 1–2** (714→685), a clean loss with PYTHONHASHSEED=0 and no faults. 37 battles, 27W–10L. Mac disk 11.4 GiB.
- **01:37Z, coordinator: Null's starts capturing NOW** with no plan-review step. Priority: cards KataCR doesn't cover (coverage list from the baseline worker → katacr-coverage.json), then current-art C56 refreshes, then CARD LEAD fixtures. Pre-run script review waived; hard limits kept.
- **01:38Z, KataCR fast-track** (Sam/coordinator): if the baseline clearly beats r5e3, ship the simplest form (MPS/CPU, every 2nd–3rd frame with carry; step p95 ~33 ms kept) at the next boundary. The YOLO integration worker is retasked; the babysitter is warned.
- **Pocket verdict (bot lead, dfde913a):** not perception, not costly. The live 27% pocket rate matches sim; forced pocket pushes Δ 0.000. pw2 is an optional harmless +5–7 pp of visible pocket play. Tower-missing guard and king_spell metric → loop owner.
- **01:39Z, HAND/SLOT DESYNC bug** (s12-m02 n864): the bot submitted Musketeer from slot 3 while perception's hand showed MiniPekka there, and the game deployed Mini P.E.K.K.A. The previous play (n844, MiniPekka slot 3) likely never deployed, but the tracked hand cycled on submit. Sent to the loop owner (root cause, rate across runs, fix + test; priority over the tower guard). The babysitter keeps laddering.
- **01:40Z, s12-m02 W 2–1** (685→715). 38 battles, 28W–10L.
- **01:41Z, YOLO v1 plan (r3 owner).**
  - Input: KataCR's 568×896 crop at (42.2,31.3)–(674.2,1019.3) of the 720×1280 capture. Classes: KataCR's 155 names + team.
  - Variants: V1a on 04 (KataCR det1 YOLOv8-L init); V1b on 08 (COCO v8-M); V1c on 01 after ft-r6 (best + synthetic).
  - Data: KataCR synthetic generator + 6.6k real + our labels ×3; EVAL-SPLIT excluded.
  - Training by ~02:15Z, first scored ~02:45–03:00Z, usable candidate ~04:00–04:30Z.
  - Crop and class format forwarded to the integration worker.
- **01:43Z, Mac contention:** live FPS 6.9→5.8 and step p95 (last 60 s) 44.5 ms in s12-m03. Load 14–18: the Null's qemu at 65%, a broad find at 97% plus mds_stores. Both Mac workers told to kill broad find, limit qemu to 2 cores at background QoS, run one instance only, and verify live latency. s12-m03 W 1–0 (715→745); 39 battles, 29W–10L.
- **01:49Z, Claude usage limit at ~01:45Z:** every Opus worker failed. After Sam's reset I resumed in place: loop owner (hand desync, tower guard), translator (multibody re-freeze + API), YOLO integration (KataCR fast-track), Null's (cut-outs), compositor, and the r3 owner (YOLO v1; yb1–7 relaunched on Sol/Haiku). The Sol interim lead spawned no duplicates. Orphaned Null's emulator stopped (load 20; disk 7.2 GiB). Barbarians (non-C56) seen in s12-m04. s12 2W–2L; 40 battles, 29W–11L, 716 trophies. Sam: stretch Claude, non-coding → Sol.
- **01:50Z, KataCR preliminary** (results.json, conf .7, our EVAL set): GS .79/.31, TC .81/.27, BP .49/.20 vs r5e3 .96/.44, 1.0/.49, .82/.34. Worse as-is, pending the threshold sweep and mapping checks. If confirmed: no KataCR-as-is go-live, and KataCR becomes init + data for the YOLO fine-tune.
- **01:54Z, s13 DOWN:** the driver stopped on its 6 GiB disk guard after m01 started.
  - Cause: macOS swap growth (6.8/8 GiB, new swapfiles 01:40–01:46Z during the Null's emulator run). Free is now 8.3 GiB.
  - The babysitter restarts as s14, syncing Sam's new in-game deck via /deck (Valkyrie, Archers, Minions, **Cannon**, Fireball, Giant, MiniPekka, Musketeer).
  - The Null's emulator is held until Mac free ≥ 10 GiB and swap < 5 GiB.
  - Loop owner: make the disk guard pause and resume instead of stopping.
- **01:55Z, s14 running** (PID 81391, started by the loop owner at Sam's request). deck_pending = Sam's Cannon deck (from m02). Free 8.6 GiB, single driver verified.
  - Risk: the deployed 3fede983 auto-suffix would allow a second concurrent driver. The babysitter must check ps before any start. The loop owner builds a single-instance lock next.
- **01:58Z, compositor done** (cc6ecdaa).
  - 10k pilot checked by eye (16 boxes/frame, 139 classes; HP bars only on damaged units).
  - ~1M bulk on 03/04/08, ETA ~02:15–02:25Z, ~110 GB at scratch/yolo-synth/v1. Sol monitor `yolo-synth-sol-monitor-r1` took over.
  - Gap: ~110 classes have opponent-only cut-outs (red↔blue swap, 16% of boxes), and the newest cards have none, so v2 needs Null's per-team cut-outs.
  - New non-C56 cards from Battle Log bl4: Barbarians, MegaMinion, BattleRam.
- **01:59Z, Sam → loop owner: 'vision gets confused when cards are grayed out'.** Unaffordable cards are drawn grey, and the hand head misreads them at low confidence (in s14-m01 Cannon was read as FirespiritHut/Skeletons). Likely linked to the hand/slot desync; the loop owner folds it into the hand fix after the single-instance lock (flock on ~/clasher-live/loop/driver.lock, in progress).
- **02:01Z, bl4 inventory committed** (e7beb00f): 41 rows. New non-C56 cards: Barbarians 3, MegaMinion 2, BattleRam 1. Arena freq refreshed (GS 12, BP 21, Barbarian Bowl 8). Manifest has 31 rows. The Battle Log corrects s9b-m04 to L 2–3.
  - Mac disk 9.56 GiB. s14 m02 is unpaused with the Cannon deck active.
  - New cards forwarded to the CARD LEAD and the bot lead.
- **02:02Z, YOLO V1a epoch 4** (04, KataCR det1 init), thr .5:
  - Scores: GS .882/.610, TC .788/.536, BP .705/.466, empty-frame FPs 0.17/frame. ft-r5 final: GS .959/.440, TC 1.0/.485, BP .853/.388, 0 FPs.
  - Recall is up everywhere, precision lower.
  - V2 on 08: V1b weights + compositor synth .55 / our official .30 / KataCR real .15.
  - V1c on 01 after ft-r6 (~04:50Z).
  - Fixes: per-class ground offsets, 60 empty-arena hard negatives (GS river bushes firing as spear goblins), tower pseudo-labels.
  - Labels: 114/208 frames done; Sol helpers on the remaining 94.
  - Live-trial bar: P ≥ .9 at .5 and recall > ft-r5, ETA 1–2 h.
- **02:03Z, multibody round 2 frozen** (sha a5667ac9…; 138 passed + 1 skip).
  - R1–R14 class audit, 34/34 mutants killed, full births API for the bot lead.
  - Dump: matched 871/1325, extras 116 (round 1: 825/83; old: 834/221).
  - Sol r2 review `live-multibody-review-sol-r2` launched; the bot lead runs the confirmation A/B and rebases revealed-set onto it.
  - CARD LEAD: Barbarians/MegaMinion/BattleRam already proxied (a382530c9). The Batch A C56 gate runs on 04, ETA 02:45–03:15Z.
- **02:04Z, Null's capture GO** with a disk-first watchdog: start at ≥9 GiB free; stop at <8 GiB free, swap +1.5 GiB, or live p95 ≥45 ms for 2 min. 1.5 GB RAM, 2 cores, background QoS. The worker disclosed that its adb (5049) auto-connected to BlueStacks 01:52–01:59Z with no commands sent; fixed with ADB_LOCAL_TRANSPORT_MAX_PORT=5553. The bot lead queued the multibody r2 confirmation A/B; revealed-set Phase B is rebasing onto the final API.
- **02:04Z, incidents:** s13-m01 was lost after the disk-guard stop (−29, 716→687); s14-m01 L 0–3 under Sam's page pause from 101 s (−30, →657). Both classed as incidents, not clean losses. Total 42 battles: 29W–13L (2 losses are these incidents, plus 2 earlier driver incidents). 657 trophies. s14-m02 is running with the Cannon deck active.
- **02:08Z, s14-m02 W 2–1** (657→687, Cannon deck, clean). s14 done (m03/m04 results pending). s15 starts behind the empty-driver gate. Mac 9.0 GiB. The Null's worker launched its capture in the background and is waiting.
- **02:09Z, OPENING-HAND STALL:** s14-m04 L 0–3 (717→688) with 0 decisions. LiveSession needs 4 deck cards, and perception reads Cannon as GoblinBarrel, so any battle with Cannon in the opening hand is AFK.
  - s14: m02 W 2–1 and m03 W 3–1 (→717); m04 is an incident.
  - Ladder HELD after s15-m01. The loop owner is building a deck-constrained hand read, packaged with the lock, tower guard, own-play dedupe and low-disk pause.
  - Sam also reports the 'Play Again' end screen trips the driver.
- **02:11Z, KataCR baseline FINAL** (7302ad89): worse than r5e3 as-is at all thresholds. Strong on Giant/Musketeer/SpearGoblin/Brawler/Tombstone; Archers R .08, Minions .05, MiniPekka .12. Weights and Ultralytics are AGPL-3.0 (internal use OK). Decision: no KataCR-as-is go-live; the integration worker is retargeted to the YOLO fine-tune (V1a/V2). Synth v1 on 08: 200k frames, 3.26M boxes.
- **02:12Z, ladder HELD.** s15-m01 L 0–3 (688→659), clean (586 decisions, no stall). s15 stopped at match_end; no driver running. Mac 9.44 GiB. Waiting for the loop owner's consolidated package. Total 44 battles: 30W–14L (incl. 5 incident losses), 659 trophies.
- **02:12Z, correction to the line above:** the total is **46 battles, 31W–15L**. Five of the losses are incidents: s2-m02, s4-m01, s13-m01, s14-m01, s14-m04. Clean record: 31W–10L. 659 trophies.
- **02:14Z, Sam's deck-change lesson** (coordinator) propagated:
  - Loop owner: authoritative deck read at session start and after edits; a deck-constrained hand; refuse with BLOCKED rather than going AFK; hand templates captured from the deck screen for any card; a stall guard that falls back to the fast tier after 6 s at full elixir.
  - Babysitter: a manual pre-session deck check until that's automated, plus stall reporting.
  - Resume after the bundle deploys; report the first post-fix battle.
- **02:17Z, routing (Sam):** 'Claude burning, use Sol where possible', then 'Opus should still own stuff, don't switch EVERYTHING to Sol'. Final: Opus owners keep ownership (loop, translator, r3/YOLO, integration, Null's) and delegate non-coding slices to Sol helpers. The handoff orders were revoked. Synth v1 on 04 done (200k); 03 at ~200/600 shards.
- **02:18Z, Sol r2 multibody: MERGE AFTER FIXES** (7 must, 3 should; the class is not closed).
  - The translator does round 3, with a Sol-written randomized scenario fuzzer (Sam: Sol can take tedious coding).
  - The revealed-set rebase holds on forget_card/state semantics.
  - Interim option: ship a5667ac9 live if the bot lead's A/B shows no regression (old tracker 221 extras vs 116).
- **02:22Z, revealed-set Phase B committed** by the bot lead on multibody r2: 8040430e, patch sha 890bfe58…. All 6 r2 findings addressed; test_revealed 29/29 plus test_multibody 77. Needs multibody on main first, and a re-run after multibody round 3 (forget_card/state). Clean-channel and smoke checks still running.
- **02:23Z, Null's capture RUNNING** (Mac emulator PID 14886, watchdog, capture PID 65718; ship loop on 05; Sol monitor nulls-sol-monitor-r1).
  - SpearGoblins smoke: 138 cut-outs. Batch 1 (10 cards, both teams) ETA 1.5–2 h.
  - Client is 15.535 (not 16.402).
  - Level badge/dial visible on cut-outs: asked for them to be flagged or masked, so the compositor adds them only to damaged units.
  - CARD LEAD fixture slots offered (1–2 h, via me).
- **02:24Z, bot lead: future pin switch = ONE bundle.** It is r1-cards1/live16402 pin + extended K4L rollout-opponent net + open-world belief + extended student rows. A pin alone would break: non-C56 cards become empty pad slots, and the closed-world belief raises 'no train deck'. Current live (r1-total + proxies) is fine. The bundle comes with a sim gate. Never deploy the CARD LEAD's pin by itself.
- **02:25Z, r3 owner stays owner** (HANDOFF section in PROGRESS-R3.md).
  - V2l (v8-L) on 04, restarted after a stale-code launch bug; V2m (v8-M) on 08. Both use the 134k real-format + 200k synth lists.
  - Eval loops fixed. ft-r6 at step 12k, done ~04:10Z.
  - Sol helper yolo-monitor-sol scores every 15 min (scratch/live-perc-r3/yolo-evals/MONITOR.md) and alerts when a candidate clears the bar.
- **02:25Z, multibody round 3 in the working tree** (not frozen).
  - All 10 Sol r2 findings fixed; test_multibody 110; r1+r2 reproducers pass; mutants 34/34 + 11/11.
  - Sol fuzzer (translator-births-fuzzer-r1) being written; then pass rates a5667ac9 vs r3, then re-freeze.
  - a5667ac9 stays reproducible for the interim ship.
  - OOV item 2 code-complete (oov.patch 9f4dfbb4, pre-r3).
- **02:25Z, CARD LEAD Null's fixture slot** penciled in (~90 min after cut-out batch 1; Sol worker cards-nulls-fixtures-sol-r1, probe only, mechanics only since the client is 15.535). Starts on my GO once its scripts are ready.
- **02:26Z, translator:** round 3 is waiting on the Sol fuzzer.
  - OOV item 2 code-complete (oov.py, 23 tests, 9/9 mutants; unknown_card default 'standin'). Its patch gets rebuilt after the r3 re-freeze and the revealed-set merge.
  - NOTE: bot/live/births.py and translate.py in the shared worktree hold uncommitted WIP. Commit and deploy only explicitly listed files from the loop owner's package.
- **02:27Z, overlay request (Sam via the coordinator):** the babysitter starts a PAUSED driver (PAUSE file, zero taps) so :8765 serves while the ladder is held. The loop owner makes the overlay always-on after the package.
- **02:29Z, overlay serving** at http://mac-mini:8765 (100.101.16.91), verified from the Mac (HTTP 200, bound on *:8765).
  - Paused overlay-only driver s16 PID 85141 (PAUSE file, zero taps).
  - /state paused:false display bug → loop owner.
  - The babysitter received a YOLO v2m-e2 candidate record; no unit swap until the adapter, deploy and latency checks are done.
- **02:30Z, YOLO candidate yolo-v2m-e2** (v8-M, KataCR init; sha ee76ad2c… stripped). Held-out P/R at .5: GS .950/.843, TC .976/.835, BP .851/.718; 0 empty FPs (ft-r5: .959/.440, 1.0/.485, .853/.388).
  - The integration worker builds yolo_units.py matching eval_yolo predict(), plus the Mac bench.
  - Deploys with the hand-fix package. Reported to the coordinator.
- **02:31Z, Null's overlays separated** (live/nulls/overlay.py).
  - Badge, HP bar and deploy dial are cut out as their own RGBA rows with offsets; body rows carry flags. Format spec: scratch/nulls/cutouts/FORMAT.md.
  - Batch 1 restarted 02:30Z (capture PID 86406); two old SpearGoblins runs discarded.
  - Mac 9.8 GiB, swap −0.03. CARD LEAD slot ~04:10Z on my GO.
- **02:32Z, Barbarian Bowl coverage** (Sam via the coordinator).
  - r3 owner: BB held-out set (30–50 frames from held-out battles, Sol labelling), score yolo-v2m-e2 vs r5e3 as a 4th row. Gate the go-live only if BB recall is clearly worse.
  - Compositor monitor: BB floors into the next shards.
  - Babysitter: standing new-arena rule (bgs + first battles kept, notify).
- **02:33Z, coordinator: decouple the resume from YOLO.** Resume on r5e3 once the hand package passes tests. ETA ~03:00–03:10Z.
  - Loop owner status: s14-m04 replay gives its first decision at frame 28; s14-m02 parity 777 identical decisions, off-deck hand reads 34%→0%. Lock, dedupe, tower guard and low-disk pause done; stall-guard test in progress.
  - Babysitter: BB first 3 battles kept on 05; 42 BB background files.
- **02:35Z, BB eval set in labelling.**
  - Held out: s14-m02 (22 frames) + s15-m01 (20), labelled from scratch by 2 Sol helpers (no model pre-labels).
  - Training: 110 frames from 11 BB battles, YOLO pre-labels verified by 3 Sol helpers.
  - Compositor asked for BB floors (training-eligible only). EVAL-SPLIT.md updated.
  - Next: score v2m-e2 vs ft-r5 on BB.
- **02:42Z, hand-fix package committed** (937aae60).
  - Contents: deck-constrained hand, own-play dedupe, stall guard, flock, tower guard, low-disk pause, /state fix.
  - Tests: s14-m04 replay gives its first decision at +28 frames; s14-m02 parity 777 decisions; all suites pass.
  - The babysitter deploys and resumes as s17 (units r5e3).
  - Deferred: deck-read automation, hand templates, Play Again, always-on overlay.
- **02:43Z, YOLO adapter ready + committed** (yolo_units.py 1a0f599d).
  - Runs CoreML fp16 on the ANE (worker thread): 896×576 p50/p95 18.7/31.5 ms, no frame skip.
  - Parity 444/445 vs eval_yolo predict(). Replay: 4.29 vs 2.51 units/frame, 0 errors.
  - The committed drive.py (937aae60, deploying as s17) already contains --units. Mac model/classes/offsets are in place (mlpackage 5731cc79).
  - Plan: add yolo_units.py + --units at the s17→s18 boundary, after s17's first battles confirm the hand fix. Watch step_ms p95 and yolo_wait_ms.
- **02:44Z, synthetic BB supplement done.** +100k frames each on 04/08 (now 300k/~4.9M boxes per host). Floors BB .40 / BP .25 / KataCR .25 / GS .10; BB held-outs excluded. 03's bulk is still running. Null's cut-outs not yet ingested.
- **02:44Z, LADDER RESUMED:** 937aae60 deployed (all 5 Mac hashes match); deck check OK (Cannon). s17 PID 33809 on r5e3. m01's first decision came 4.57 s after match_start (MiniPekka, search). Full first-battle report pending.
- **02:46Z, s17-m01 interim:** 343 decisions by 96 s; no stalls or errors.
  - Cannon fix proven: hand=[Giant,Fireball,Cannon,Minions] while hand.raw had GoblinBarrel.
  - Towers match. Mac 8.45 GiB.
- **02:47Z, YOLO candidate 2: yolo-v2l-e11** (v8-L, sha 46b5752a…) supersedes v2m-e2.
  - Held-out P/R at .5: GS .946/.887, TC .988/.856, BP .860/.752, BB .940/.793 (ft-r5 BB .922/.472). 0 empty FPs. BB gate passed.
  - Mac ANE 27/39 ms.
  - The integration worker exports CoreML and checks parity; deploy at the s17→s18 boundary with the v2m-e2 package as fallback.
- **02:48Z, FIRST POST-FIX BATTLE s17-m01: W 1–0** (659→689).
  - 685 decisions; first decision 4.6 s after start; 29/31 plays.
  - Cannon corrected from raw GoblinBarrel on 171 frames. No stalls or errors. step p95 21.6 ms.
  - Record: 47 battles, 32W–15L (5 losses are incidents; clean 32–10). Mac 9.46 GiB.
- **02:48Z, synth v1 COMPLETE:** 1.21M frames, 19.7M boxes, 139 classes (03: 610k/67G; 04: 300k/33G; 08: 300k/33G). All QA checks pass. Missing: mirror, tesla-evolution-shock, zap-evolution. v2 waits for ≥5 Null's cut-out runs (none usable yet).
- **02:49Z, BB rescore** on final labels, thr .5: v2l-e11 .954/.809, v2m-e2 .907/.770, ft-r5 .922/.476. Replaces the earlier figures; other arenas unchanged.
- **02:53Z, bot lead sim check on Sam's Cannon deck:** 80 games, 0 errors. Every card is played by both K4L and the student.
  - K4L wins 95% vs R3a and 100% vs v1; the student 90%/100%.
  - The student almost never plays Giant (2/40 games); that's policy, not perception.
  - Report: 127x03:/mpac/sdicks02/jobs/clasher/bot-deckcheck/REPORT.md.
- **02:54Z, revealed-set 890bfe58 validated:** clean channel 30/30 identical; 40-game noisy smoke 0 errors, 37 evictions. Queued behind multibody round 3, then a re-run and a fresh Sol review.
- **02:59Z, s17 done** (m04 W 1–0; account 661, so m02/m03 were losses; details in the 2-session report). s18 PID 75456 started on r5e3/937aae60 (YOLO export not ready at the boundary). Deck check OK.
- **03:13Z, status.**
  - Ladder: s17 2W–2L, s18 4–0 (781 trophies). 54 battles, 37W–17L (5 incident losses; clean 37–12).
  - YOLO v2l-e11 exported to the Mac (mlpackage f69a2aac, parity 613/613, ANE p95 34.5 ms). The babysitter deploys it at s19 with rollback criteria.
  - 08 GPU idle → r3 owner to queue the next run plus a keep-alive. 03 CPU → reclaimed by the bot lead (synth v1 done; v2 waits for Null's cut-outs).
  - Multibody r3 frozen (8e04b255; OOV 4eeb623b on top): Sol r3 review launched; the bot lead A/B and revealed-set re-run on 8e04b255.
- **03:13Z, bot lead:** 03 reclaimed (it11). Confirmation A/B switched to multibody r3 8e04b255. A Sol worker re-validates revealed-set on r3 (tests, clean channel, 40-game smoke).
- **03:14Z, Sam: viewer down, bot idle (the s18→s19 gap).**
  - Babysitter: start s19 with YOLO NOW. New rule: housekeeping (Battle Log, copies, prune) runs after the session starts; inter-session gaps of a few minutes max; Battle Log pass every ~3–4 sessions.
  - Loop owner: always-on standalone overlay, now priority.
- **03:15Z, s19 PLAYING with YOLO v2l-e11 units** (PID 22246). First decision 4.58 s after match_start; yolo 26.6 ms, wait 0.005 ms; no errors. Battle Log bl5 captured before launch, processed offline. Reported to the coordinator.
- **03:16Z, Sam: between-session menu work** (upgrade cards, claim trophy road / Pass Royale / chests, build the best valid deck).
  - Babysitter: ≤5 min per boundary of free claims plus gold upgrades (deck cards first: Giant, MiniPekka, Musketeer, Fireball); never real money or Google Play sheets; a one-time collection.json inventory; deck changes only from my list (all C56) with read/apply/verify.
  - Bot lead: sim-rank candidate C56 decks from the collection.
- **03:17Z, YOLO queues:** V2m on 08 had finished (not a candidate), so 08 idled; keep-alive queues are now on both hosts.
  - V3l on 08 from V2l e24 (e24 already GS .960/.912, BP .872/.782, BB .939/.871 at .5).
  - 04 finishes V2l, then V3l1024. 01 gets V1c after ft-r6. A Sol monitor alerts on >10 min idle.
  - Bot lead deck search (bot-lead-deckopt-sol-r1, 04/08 CPU ≤40): 8–10 C56 decks, stage 1 at 100 games, stage 2 at 300; waiting for collection.json.
- **03:18Z, Sam: YOLO owner confusion** (enemy Skeletons/Minions boxed as ours; ghost labels).
  - Integration worker: live owner fix in yolo_units.py (badge colour, sticky owner, spawn side, own-deploy evidence), with before/after owner accuracy and a crowded-scene subset.
  - r3 owner: per-arena owner accuracy plus a confusion matrix; training fix (owner-balanced, crowded scenes; the red↔blue swap is a suspected cause).
  - Loop owner: faint/hide candidates under 0.3 on the overlay.
- s19-m01 last-60 s FPS 5.97. Rollback rule refined to whole-battle FPS < 5.5, or step p95 > 45 ms, or errors; the first lever is Null's contention.
- **03:18Z, contention under YOLO:** live frame perception 116→139 ms, FPS ~6.0. Null's qemu at 37% CPU, load ~11. Asked the Null's owner to STOP qemu during live battles (CONT between), or throttle to keep live FPS ≥6.5.
- **03:19Z, FIRST YOLO BATTLE s19-m01: W 1–0** (781→811).
  - 687 decisions, 27/27 plays. Whole-battle FPS 5.91; step p50/p95 6.3/23.3 ms; yolo 28/34 ms, wait ~0.
  - Units/frame mean 3.05 vs 1.98 (old model). No errors; no massive phantoms seen.
  - Record: 55 battles, 38W–17L (clean 38–12). bl5 inventory: no new non-C56 cards; manifest 44 rows.
- **03:20Z, owner accuracy (r3 owner):** live v2l-e11 is 0.984 overall, but enemy→ours is **4.8%** (8/167); ours→enemy 1/410. It worsens with more synthetic training (V2l latest 9.4%), consistent with the red↔blue swap.
  - Fixes: 3× team loss weight; V3lo on 08 from V2l e24 (synth .35 / official .40 / KataCR real .25); V3lo1024 queued on 04.
  - Compositor asked for no-swap, ≥50% crowded mixed-team shards. New candidate gate: enemy→ours ≤3%.
  - Asked the bot lead for a partial 03 lease for those shards.
- **03:21Z, 03 lease granted** (~64 workers, 1–2 h) for no-swap crowded mixed-team shards (~150k). Sent to the compositor and its monitor. Release back to the bot lead when done.
- **03:23Z, Mac disk dip** to 7.73 GiB during s19-m02, recovered to 9.03 after the video prune. Cause unattributed; swap stable 6.68. The Null's capture restarted with no qemu. Asked the Null's owner about AVD growth and to enforce the 8/9 GiB lines. The babysitter continues; s20 with YOLO at the boundary.
- **03:23Z, Null's:** AVD unchanged (read-only, no snapshots); its watchdog correctly stopped the emulator at 7.77 GiB. A/B: freezing qemu doesn't change live FPS (5.91 vs 5.93), so the FPS cost is YOLO pre/post on the live side.
  - Null's GO at ≥9 GiB with the battle gate off and a live-FPS trigger (<5.6 or step p95 >40 → stop until battle end).
  - Integration worker: reduce YOLO GIL/CPU cost after the owner fix (target ≥6.5 FPS).
- **03:25Z, always-on page committed** (9c1b6098). overlay_server on :8765 proxies the driver on :8766, shows 'between sessions: <reason>' from status.txt, and pause works without a driver; owner-coloured used-units view with toggles. The babysitter deploys it at the s19→s20 boundary.
- **03:26Z, Sam: enemy Cannons tagged as ours.**
  - Integration worker: a hard building rule in the owner fix (enemy half = enemy unless our deploy log says otherwise; our half = ours only with a deploy-log entry, otherwise flagged; owner fixed at first sighting), plus per-building owner rows and replay flip counts. Ships with the owner fix at the next boundary.
  - r3 owner: per-class building owner eval; balance Cannon team data.
- **03:27Z, Sol r3 multibody: MERGE AFTER FIXES** ('not closed enough to ship'; 6 must, 4 should).
  - Fresh seeds: clean 19.3% exact / 2.50% missed / 1.40% extra; noisy 2.91% / 6.62%.
  - DECISION: if the bot lead's A/B on 8e04b255 shows no regression, merge + deploy 8e04b255 as an interim (old tracker much worse: extras 221 vs 118). Round 4 follows (translator fixes 1–8; its Sol helper fixes the fuzzer, 9–10).
- **03:29Z, deploy-hash catch (babysitter):** 9c1b6098 had accidentally swept in the integration worker's uncommitted owner-fix hooks in drive.py (they would crash against the deployed yolo_units). Fixed on main with 9f75ab5f (drive.py = 937aae60 + port default only, f93a7a06…) via a temp index, leaving the worker's WIP intact. Lesson: stage-check commits for files others are editing (git diff --cached for unexpected hunks).
- **03:30Z, s19 (YOLO v2l-e11): 1W–3L** (W 1–0 →811, L 0–1, L 0–2, L 0–1 →720). 3 clean losses in a row, so the hold fired.
  - DECISION: s20 rolls back to r5e3 units (no --units). YOLO returns after the model-based owner fix passes the gate (enemy→ours ≤3% overall and per building).
  - Before YOLO: s17–s18 6–2.
  - Totals: 58 battles, 39W–19L (clean 39–14).
- **Sam: 'We shouldn't hard code cases in.'** Hand-coded owner rules cancelled.
  - Owner gets fixed via owner-balanced data, hard-example mining from s19 and an optional learned temporal head.
  - Translator: round 4 = correctness fixes only, no new special-case rules; design a learned play detector trained on sim truth + noise to replace the rule stack.
  - Principle passed to all workers.
- **03:31Z, Sam: owner via badge/bar colour + facing/motion, as LEARNED cues.**
  - r3 owner: make badge/bar visible to the team prediction (context crop); a learned owner classifier on crop + 2–4 frame track history, balanced (team, damaged/undamaged, buildings both sides, crowded); blend with the YOLO team flag; report with and without.
  - Opus code (sub-worker OK), Sol training/evals.
  - v1team shards (no swap, 70% crowded mixed-team) on 03: 64k done.
- **03:32Z, Cannon owner bias cause found** (r3 owner): KataCR real data has Cannon 1,533 ours vs 118 enemy. Rebalanced (85% of 'ours'-Cannon frames dropped → 237/105) for all current and queued runs. Per-class owner eval added. s19-m01 (enemy Cannon) to be held out. The babysitter flags enemy-building battles and keeps their video.
- **03:32Z, learned owner classifier underway.**
  - Confirmed: YOLO boxes exclude the badge/HP bar.
  - Sub-worker owner-net-opus (live/perception/owner/, OWNER-NET.md): a context crop incl. badge/bar, no vertical flips (facing cue); balanced team/class/damaged; buildings for both teams.
  - Hard examples from s19-m02+ (Sol-verified) also feed the YOLO V4 runs (share .10). s19-m01 becomes a held-out owner-eval battle.
  - YOLO: V3lo (3× team weight) on 08 → V4lo (v1team); V3lo1024/V4lo1024 on 04. 01 is shared with the owner net after ft-r6.
- **03:33Z, s19-m01 and m02 held out** for owner/enemy-building eval (~20 frames each, labelled from scratch by Sol). Hard-example mining uses s19-m03+. Compositor excludes them. Baseline = plain v2l-e11.
- **03:34Z, Sam: no separate owner classifier; fix owner inside YOLO's team output.** owner-net-opus cancelled (keep the mining/labels/eval). YOLO gets owner-balanced data, s19 hard examples, the 3× team weight, and boxes/context covering the badge+bar (the r3 owner decides how). Report retrained vs v2l-e11 per arena/building/crowded.
- **03:36Z, s20 PLAYING** (PID 81335) on r5e3 units (YOLO rollback). First decision 4.48 s after start.
  - Always-on page deployed (server PID 67178; drive f93a7a06).
  - Menu: free Pass gold claimed (+842 → 5571 gold). Deck cards can't be upgraded yet (not enough copies). Collection inventory at the next boundary.
- **03:37Z, s20 verified.**
  - Proxy page OK; FPS **7.85** / step p95 17.7 ms on r5e3 (vs ~5.9 FPS with YOLO), confirming YOLO's in-process CPU cost.
  - RESULTS (authoritative, from the babysitter): 58 battles, 38W–20L incl. 5 incidents; 720 trophies before s20. Correction to my running tally of 39–19.
  - Building flags on 43 battles; videos retained.
- **03:38Z, revealed-set 890bfe58 re-validated on multibody r3 8e04b255:** applies cleanly; test_revealed 29/29, test_multibody 115/115; clean channel 30/30; smoke 40/40.
  - Plan once the A/B passes: merge 8e04b255 (interim), then a Sol review of revealed-set against the r3 contract, then merge. OOV last.
- **03:38Z, CARD LEAD:** all 7 priority non-C56 cards landed as real engine cards on main (0ee42633e): SpearGoblins, GoblinCage(+Brawler), Tombstone, Bomber, Barbarians, BattleRam, MegaMinion. r1-cards1 pin (full scope) smoke OK; live16402b (16.402 stats) in ~1 h.
  - Live switch = ONE bundle: pin (live16402b) + bot-lead extended nets + open-world belief + translator OOV/driver C56-gate widening + Mac parity build.
  - Until then the driver's C56 block on our deck stays, and opponent new cards go via the proxy table.
- **03:40Z, v1team COMPLETE** (03: 150k frames, 2.75M boxes, no swap, 66% crowded); 03 released to the bot lead.
  - Gap: only 34 classes have both-team cut-outs; our deck's archer/minion/mini-pekka are opponent-only in synthetic.
  - r3 owner: upweight official frames for these. Null's: capture both teams of our deck cards first after batch 1.
- **03:40Z, s20-m01 W 1–0** (720→750) on r5e3: 882 decisions, 35/34 plays, FPS 7.8, step p95 19.7 ms, 0 errors. Clean-loss streak reset.
- **03:41Z, coordinator:** owner-net-opus told directly to stop classifier work and hand its labels (s19 hard examples and eval, hrd1/2, own1/2) to the r3 owner for YOLO retraining/eval. Process rule passed down: helpers ask via t3_thread_send, never UI input requests. Pending-request check: babysitter, Null's, compositor and integration all clear.
- **03:42Z, translator round 4** (Sol r3 #1–6 fixed generally; #7 deferred to the learned detector; test_multibody 141 + 2 xfail; mutants all killed). Freeze waits on the fuzzer helper.
  - Learned play-detector design approved (PLAY-DETECTOR-DESIGN.md): deterministic association + LightGBM decision; sim truth labels; ~3 days.
  - Dataset helper starts now; heavy sim on a 03 lease via the bot lead.
- **Account log:** the babysitter keeps ACCOUNT-LOG.md and reports each action; state sent to the coordinator (gold 5571, gems 300; Sam's upgrades inferred: Fireball +1, Giant +3; Cannon possibly upgradable). Collection inventory at s20→s21.
- **03:43Z, ACCOUNT-LOG backfilled** and relayed to the coordinator. Observed: Sam upgraded Cannon L3→L6.
  - Translator: dataset helper translator-playdet-dataset-r1 (Sol) started (bot/live/playdet/; heldout guard; bulk on 03, ~4–8 cores × 3–6 h, ask pending).
- **06:48Z, RESUME after the Claude usage stop.**
  - The LADDER WAS IDLE ~04:03–06:45Z (s21 ended; babysitter turn complete, not woken). Babysitter woken: start s22 now, with a standing rule to auto-continue sessions.
  - Deck change authorized (bot lead deck search: Cannon→Skeletons, +8.0 pp [+3.7, +12.3]); logged in ACCOUNT-LOG.
  - Multibody r3 interim: the bot lead A/B births arm +0.027 (events arm −0.017 [−0.047, +0.012], doesn't exercise births) → ship. But r3 on current main fails 3 champion tests → translator rebase.
  - CARD LEAD Null's slot GO (120 min, the Null's owner pauses capture and pings the CARD LEAD directly). live16402b final.
  - r3 owner running again (resumed at 06:41).
- **06:49Z, Mac disk:** removed ~/clasher-live/apk (1.0 GB of sideload APKs, verified identical to 05 bst-trial/verified-160402020 via SHA256SUMS) to get above the 9 GiB Null's start line.
- **06:53Z, s22 PLAYING** (PID 42105, r5e3) with the NEW DECK applied before m01: Valkyrie, Archers, Minions, Skeletons, Fireball, Giant, MiniPekka, Musketeer. Account log updated. First decision 4.5 s after start. Mac 9.63 GiB.
- **06:57Z, s21 final 2W–2L** (W 1–0, L 0–3, L 0–3, W 3–1; 780). s22 (new Skeletons deck): m01 L 1–3, m02 L 0–3 (clean; 7.3–7.8 FPS). m03 running; a 3-loss hold is possible. Mac cleanup freed ~1.7 GiB → 11.1 GiB free. Record: 68 battles, 43W–25L (5 incidents).
- **06:58Z, Sam: r5e3 barely sees friendly troops until damaged; rarely sees friendly swarms (1 of 3 Minions).**
  - Asked the r3 owner for a baseline table (own-units recall undamaged/damaged, per-body swarm recall) for r5e3 / v2l-e11 / best epoch.
  - New gates for the next live YOLO: owner ≤3%, friendly undamaged recall, swarm per-body recall.
  - Training adds own-deploy hard examples from s20–s22 (labels pre-placed from taps/decisions).
- **07:00Z, Sam: recurring dense-frame weakness audit.** Owner: the r3 perception owner (Opus), with Sol helpers reviewing frames. Every session or ~3 h; random dense frames from live + held-out candidate replays; misses/merges/owner/class/phantoms → WEAKNESSES.md; each item gets a data fix, and recurring items become eval slices. Added to the r3 standing instructions. First audit: s20–s22 + candidate replays.
- **07:01Z, s22-m03 W 1–0** (721→751), the first win on the new Skeletons deck; streak reset. Correction: s21-m02/m03 were L 1–3 (not 0–3). Record 69 battles, 44W–25L.
- **07:02Z, Sam screenshot (s22, tick 2022):** r5e3 boxes 1 of 2 enemy Archers and 1 of ≥2–3 own Minions, so swarm undercount on both teams. Sent to the r3 owner as the first WEAKNESSES.md item (pull the raw frame, label, hard example, diagnose model vs NMS/peak setting; run the best YOLO candidate on it).
- **07:03Z, friendly/swarm baseline** (r3 owner, held-out 227 frames): ours undamaged recall r5e3 .17 / ft-r6 .32 / v2l-e11 .70 / V4lo-e14 .81; swarm bodies ours .28 / .40 / .88 / .86.
  - Gates accepted: friendly undamaged ≥ .75, swarm ≥ .80, owner ≤ 3%. V4lo-e14 fails only owner (3.9%).
  - Interim: ft-r6 replaces r5e3 at the s22→s23 boundary (babysitter).
  - First WEAKNESSES entry ~10:30Z. Null's status relayed to the Sol monitor via the compositor.
- **07:04Z, coordinator condition:** the ft-r6 swap goes ahead only if its enemy→ours rate on the 227 frames ≤ r5e3's. The swap is held (s23 on r5e3); the r3 owner runs owner_eval on both.
- **07:05Z, ft-r6 swap GO:** enemy→ours 0/168 vs r5e3 0/158; ours→enemy 3/261 vs 3/218; ft-r6 matches 429 units vs 376. Swap at the next boundary.
  - Possible card/slot mismatch s21-m03 (Minions logged, Valkyrie deployed) → loop owner (root cause + rate over s17–s22).
- **07:13Z, merges and deploys.**
  - Multibody r3 merged on main (bbdc651e; births sha 48636f63…); my earlier scratch failure was a namespace-package import artifact. The babysitter deploys births.py at the s23→s24 boundary with rollback criteria.
  - Sol r4 review (e90541ed) launched.
  - playdet dataset package committed (318699f4); 03 lease requested from the bot lead.
  - **YOLO yolo-v4lo1024-e16 passes ALL gates** (enemy→ours 1.7%, buildings 0; ours undamaged .82; swarm .85/.85; id P/R all .931/.845). The integration worker exports at 1024×672 (parity, ANE latency, FPS) before deploy.
  - s23 on ft-r6 (m01 L 1–3). s21–s22 4W–4L. 70 battles, 45W–25L.
- **07:13Z, playdet:** 03 lease approved by the bot lead (8 cores × 2–3 h); translator told to proceed.
  - s23-m02 W 1–0 (751→781).
  - Daily free chest screen caused nav_stuck (the babysitter cleared it and logs the account items). Loop owner: reward-screen autonav (UI, safe buttons only).
- **07:16Z, CARD MISMATCH:** logged ≠ played card in 6/38 s22 deploys (Skeletons deck) vs 0/47 (s20) and 1/50 (s21) on the Cannon deck.
  - DECISION: revert the deck to Cannon at the s23→s24 boundary (account change, logged).
  - Loop owner: root cause + general fix + post-tap resync, measured on replays.
  - Reported to the coordinator.
- **07:17Z, account claim:** daily bonus 2-star chest gave gold ×400, plus an emote snippet ('Night, Night…' 1/9). Balance verified at the boundary. s23-m03 underway.
- **07:19Z, synth v1team3 on 04 done:** 50k frames; balanced official art for both teams; our deck's archer, minion and mini-pekka now have real both-team cut-outs. 08's 50k is queued.
- **07:23Z, s23-m03 W 3–1 → 811.** Second daily chest: +400 gold + emote snippet (logged).
  - Pushed the r3 owner's perception tools + WEAKNESSES audit 1 (0f6daaf1).
  - playdet dataset running on 03 (8 workers, PGID 3924413).
  - Asked the translator for an offline derived-play audit command (no derived-play log in the driver).
- **07:25Z, Sol r4: not a safe improvement over r3** (5 must, incl. a phantom Golem on a dropout death, staggered swarms eaten by the 3-tick spawn rule, resolve not read-only).
  - DECISION: stop rule iteration. r3 stays the live tracker. Fix only API purity if r3 shares it (r3.1).
  - The translator's effort moves to the learned play detector, using Sol's r3/r4 reproducers + fuzzer (independent champion truth) as its test set. OOV rebases on r3.
- **07:27Z, s23→s24 boundary.**
  - births r3 deployed (Mac sha 48636f63 PASS).
  - Trophy-road 750: claimed Mega Minion ×25 (choice was Battle Ram/Mega Minion; not MiniPekka); new 18th card, NOT in the deck.
  - Deck reverting to Cannon.
  - s23 final 2W–2L at 781. 74 battles, 47W–27L. s24 starting (ft-r6, Cannon deck, births r3).
- **07:32Z, playdet-r1:** the T1 part ran (7m45s); all 16 sim shards hit an ability/reservation bug (28 matches, superseded). r2 patch verified; sim-only r2 launches after T1 validation (lease freed meanwhile).
- **07:33Z, s24 playing** (PID 52100; r3 births live, 8 raw opponent events, 0 errors).
  - Gold settled 6,971 (+1,400 from chests + win bonuses); Mega Minion L3, 18 cards.
  - Babysitter woken (auto-continue).
  - r3 resolve is pure (61k calls), so no r3.1. playdet sim fix committed (fdf3dd50).
  - Translator found the synthetic FP channel unrealistic (5.0 vs 1.2 FP plays/match; persistence 0.45% vs 31.6%), so it re-noises before training. Audit tool coming.
- **07:34Z, synth v1team3 complete on 04+08** (100k frames, balanced official art for both teams; no team-gap classes).
  - playdet r2 sim (2000 matches) running on 03 under an 8-core lease. T1 shards on 03 lacked registered inputs; the translator finishes T1 (reminded: 05 is light-only).
  - Null's still at 2 runs; v2 gate unchanged.

### 07:36Z revealed-set r3-base review: MERGE AFTER FIXES
- The Sol review of 890bfe58 on 0f6daaf1d passed (218 passed, 5 skipped), but found 3 defects:
  - (1) spawn/child/leftover identities are treated as raw-label evidence, giving phantom admission and eviction;
  - (2) synthetic catch-up polls still feed tracker.update(), so one capture turns into a play plus an eviction;
  - (3) a board-only troop admission can never be evicted.
- Repros are in /mpac/sdicks02/scratch/live-review/revset-r3. The fixes went to the bot lead; r3 alone stays live. Round-2 Sol review follows once the bot lead posts the new patch sha.
- s24m01 L 0–1 (−30, 781→751), a clean loss; clean losses in a row: 2 (s23m04 + s24m01). The babysitter is watching the 3-clean-loss rule.

### 07:38Z r3 owner correction on the YOLO e16 record (gate unchanged)
- Training uses fixed 576×896 images in every run; `--imgsz 1024` affects only inference and eval. All of e16's gate numbers were measured at (1024,672), the size the Mac adapter runs (CoreML parity 756/756), so its pass stands.
- Control: the 896-trained V4lo-e14 run at 1024 gets enemy→ours 2.5% but recall .80/.81, so it fails; e16 is still the only checkpoint passing every gate.
- The deploy plan is unchanged; it waits on integration's export, FPS and step-time numbers.

### 07:41Z audit_plays committed (390d6779b)
- bot/live/audit_plays.py (aee42034…) and its test file (a4f5f97a…, 9 passed) are now on main. The command replays recorded runs through the real translator and compares trackers side by side.
- Sample (r3 vs old, accepted plays / off-deck): s12-m04 9/2 vs 12/7; s12-m03 13/3 vs 14/2.
- Finding: s23-m04 has 2011 unmapped AnyTroop units. Class-only perception units are dropped today; the OOV class-only path (rebased on r3) is the fix.

### 07:43Z Sam: "it sometimes double counts troops" (s24, ft-r6)
- Overlay screenshot (~07:42Z): two nested boxes on one own MiniPekka (0.71 + ~0.70), and overlapping labels on our Archers/Skeletons.
- Routed to the r3 perception owner as a WEAKNESSES item:
  - classify same-class double peak / cross-class / overlay artifact;
  - check translator and births impact via audit_plays;
  - run the frames through e16;
  - fix through the model or tuned suppression on held-out data, no per-card rules;
  - new standing "duplicate on one body" audit column per model.

### 07:47Z double-count diagnosis: stale decode on the Mac
- ft-r6's AnyTroop/AnyBuilding objectness channels fire on every body. The Mac common.py (blob 5949aad10, ba4e560e5) emits them as units, giving a second box on each body; they are 54–58% of logged s24 units.
- Card-level effect is none: the translator drops Any*, and audit_plays found 0 births on one body in s24-m01/m02.
- Fix: deploy main common.py (blob e0b013900, sha256 3b48744f…) at a boundary, after offline parity on 05 and a Mac import check; rollback is .bak-pre-anyunit. Sent to the loop owner.
- Translator told: OOV must use record['unknown_units'], not raw AnyTroop.
- e16 itself has 13 duplicates on held-out (minion ×8, valkyrie ×3 cross); the r3 owner is tuning NMS, results in ~30 min.

### 07:49Z double-count follow-ups (coordinator approved the fix)
- Board state: in card_level mode assign() leaves Any* as None and _rows() skips them, so board rows, HP and births never saw them. The loop owner's parity check now also compares board rows per frame.
- Affected sessions: ft-r6 + stale decode = s23 onward until the swap. The loop owner tags them in RESULTS.md.
- Closing the class: the loop owner is building a session-start manifest guard: sha256 of every imported/opened code-tree file vs a manifest from the intended commit, plus an imported-module coverage check and a PYTHONHASHSEED check; it refuses to start on mismatch and logs the manifest sha in the header. Sol review before it goes live.
- e16: the corrected duplicate metric (same body, IoU ≥.3) gives class-wise .6 = 2, agnostic .6 = 0, all gates pass. Integration told to default to agnostic NMS .6. Sam's frame n=2821 under e16: one MiniPekka, both Archers (ft-r6 saw one), no duplicates. WEAKNESSES item 9 is 826758992.

### 07:51Z revealed-set round-3 fixes in; Sol review round 2 started
- Bot lead committed 39d8d7068; patch sha256 88fc13ee… verified by command on origin/main. Base is 501702884 (with r3 births).
- The fixes cover source-card evidence for all births states, read-only catch-up tracker lookups, and provisional board-only admissions. test_revealed 39/39; LIVE suite 214/13/6 vs 175/13/6.
- Sol round 2 task: live-revealed-set-review-sol-r3base-round2 (repros, class closure, thrash, suite vs unpatched, timing). The bot lead's 03 smoke and pinned-runtime suite are pending.

### 07:56Z OOV r3 (class-only path) received
- Patch oov-r3.patch sha256 67941b1d… verified; base 390d6779b; suite 217 passed / 1 skipped. It reads only record['unknown_units']; Any* arriving as units is skipped.
- Measurement: 12,984 Any* detections, only in s23+, 71% overlapping a named unit (89% within ±2 frames). At most 80 genuine unknown tracks ≥3 frames over 7 battles (53 opponent).
- Merge order: revealed-set first, then rebase OOV. A Sol review is running (live-oov-r3-review-sol-r1). Leaning toward keeping the default 'drop' and switching live via config.
- The babysitter is asked to backfill s23/s24 opponent decks for the off-vocab correlation.

### 08:03Z revealed-set Sol round 2: MERGE AFTER FIXES (again)
- Suite 223/13/6 vs 184/13/6 (same missing-checkpoint failures); fair information clean.
- Still open: source attribution depends on membership (MUST); provisional admissions thrash (MUST); gap ≠ empty frames (SHOULD); replay protection expires after 64 captures (SHOULD). 80-body p95 25.8 vs 15.9 ms.
- Sent to the bot lead with an invariant table I1–I4, each with a property/fuzz test and a mutation check. Option to park revealed-set behind the learned detector if one more round can't close the classes. r3 alone stays live.
- Ladder: s25m01 W (811), m02 L (781), m03 W (811); record 81 battles, 51W–30L. m04 active.

### 08:04Z revealed-set PARKED (bot lead's decision, agreed)
- Gain +0.013 [−0.003, +0.028] unconfirmed; r3 already cut off-deck drops 17→4 per game; class gaps found two rounds running; adds busy-board latency.
- I1–I4 become the v2 contract on top of the learned detector. Patch 88fc13ee / 39d8d706 is kept in reports/bot/noise-robust/. r3 stays live alone.
- OOV now rebases on main directly (no revealed-set dependency). The detector should output source card, confidence, capture id and tick for v2.

### 08:12Z s25 3W–1L (841, record 82 / 52W–30L); Pass Royale wild cards; level gap
- Account: free Pass Royale tier-25 chest, Common Wild Card ×67 (stock 112). Relayed. Wild-card upgrades (Archers L7, then Minions) moved to the s27 boundary.
- The s25→s26 gap was 5m34 (over the cap) because the Pass claim UI ran long. The babysitter now hard-cuts optional menus at ~2 min, and s26's boundary is inventory only.
- Finding: the live bot plans with every card at L11. drive.py never passes LivePlayer(levels=), and session-config has no level keys. LevelRoot exists (d9fc2843d). Sent to the bot lead as a possible lever: sim A/B, fair-information opponent levels, own levels from collection.json.

### 08:13Z decode fix GO (pending Sol review of mac_decode_check.py)
- Loop owner parity on all of s24 (6118 frames): perception identical except Any* (5769 frames → 0); board rows 3082/3082 identical; observation identical; accepted plays 4/4 identical; driver dry run 0 tracebacks.
- The babysitter swaps common.py to 3b48744f… at a boundary (.bak-pre-anyunit, rollback criteria as planned). RESULTS s23-m01..s25-m04 are tagged "ft-r6 + stale decode¹".
- Loop owner's flag (b) refuted: the deployed translate.py 5361deb0 defaults to unknown_card='drop' (line 293); 'standin' was in the 05 oov WIP. Flag (a): oov WIP in standin mode gave phantoms (rows 14/64); passed to the translator for its real-input evaluation.
- Levels: the bot lead's Sol scoping (bot-lead-levels-scope-sol-r1) is checking sim capability first. Hold --levels until the A/B; wild cards are fine to spend.
- Manifest guard built (15/15 tests); Sol review running.

### 08:15Z Null's woken for the CARD LEAD slot; unknown_units mostly noise
- The Null's generator thread had been idle since 06:54Z and never saw the slot GO. Woken via thread_send to pause capture, leave the AVD probe-ready and send the CARD LEAD the window. CARD LEAD informed.
- Translator pointed to the re-decoded s24 records (05 scratch/live-loop/parity/cache-s24/*-new.jsonl).
- Measured: unknown_units has 3.26 per frame, median score .064, p99 .169; only 27 ≥ .3 and 5 ≥ .5; card_max is absent from records. Effectively unthresholded noise. Flagged to the translator, who passes it to the r3 owner; needs a decode threshold chosen on held-out data. Harmless to the deployed translator, which ignores the key.

### 08:16Z OOV class-only path PARKED (Sol: MERGE AFTER FIXES, 4 musts)
- Musts: standin default vs config 'drop'; unknown building sites suppress named plays (Giant, Cannon); placeholder overflow of max_entities 128; EvictTranslator crash. Drop-mode audit identical. Report: scratch/live-review/oov-r3-review-20261016/REVIEW.txt.
- Parked because ft-r6 unknown_units is noise (median .064, 27 ≥ .3 / 6118 frames) and e16 has no any-unit channel. v2 contract: Sol's findings + explicit opt-in + bounded placeholder budget + sites never relabel named births.
- Translator now works full time on the learned play detector.

### 08:16Z CARD LEAD Null's window 08:15:18Z–10:15:18Z
- Delivered to the CARD LEAD's active turn. The 06:54Z ready message had only been queued and never reached them, so the probe sat idle.
- Null's capture so far: 2 runs (SpearGoblins, both teams), no deck-card runs yet. The deck-first queue resumes at 10:15Z or when the CARD LEAD releases the slot. The emulator stays up; watchdog on, 11.2 GiB free.
- yolo_synth v2 needs ≥5 Null's runs, so it's late; re-check after 10:15Z.

### 08:17Z unknown_units thresholded (15d80e820); v1team4 CPU-starved
- r3 owner: frame_record unknown_threshold=.5 and card_max added (about 5 in 6118 frames). On held-out, ft-r6 objectness peaks at P/R .19/.29, so parking OOV is right. e16 detects 93% of the 80 off-vocab units with team correct and names 89% of them (Tombstone 24/25, GoblinCage 18/20).
- The decode swap stays pinned to 3b48744f…; 15d80e820's version goes into the manifest-guard bundle after a parity rerun.
- yolo_synth v1team4 has been queued since start on 04/08 by cpu_room (136–137 procs vs a 105 ceiling). Asked the bot lead: 01 (load 4, GPU 96%), free slots, or keep queued. 02 and 07 have no route.
- 08:18Z The bot lead granted 01 for v1team4 (~32 cores, leaving ~8 for the YOLO trainer). cpu_room.sh is fixed to ignore train_cr.py loaders. The synth owner is told to launch on 01 with no overlapping shards versus the queued x04a/x08a.

### 08:21Z s26m02 L (782); record 84 / 52W–32L; 3-clean-loss rule changed
- No more holding on 3 clean losses: continue and send a loss report. Hold only for real anomalies (errors/guards, FPS < 7.0, step p95 > 45 ms, decisions < 50% of normal, card mismatch, stuck HUD, ≥5 straight losses).
- My error: a placeholder "noop" send to a spliced thread ID (clasher-live-lead under the 99d49b81 prefix). It failed harmlessly as thread_not_found. Rule reaffirmed: no placeholder sends.

### 08:24Z yolo_synth v1team4 complete on 01 (x01a)
- 50k frames, 889k boxes, 139 names, 5.8 GB at 01:/mpac/sdicks02/scratch/yolo-synth/v1team4/. Team swap 0; QA passed; held-outs excluded.
- Gaps: Musketeer/Giant/Fireball have no official art (KataCR only); official opp MiniPekka pool 5 and Minion 7 are reused.
- Handed to the r3 owner for V6lo/V7lo1024. x04a/x08a still queued, adding up to 100k frames if admitted. 01's CPU lease is released.

### 08:30Z loop owner status: card-mismatch root cause found
- Wrong card sent on 42/542 plays (7.75%) by video truth. Causes, mostly in the hand tracker:
  - opening order taken from the first HUD frame while cards are still being dealt;
  - whole-hand re-anchor fires on greyed-card noise;
  - greyed cards misread confidently (Archers right only 18% when greyed);
  - correct coloured reads never used to fix the tracked hand.
- handsync gives 0/517 in replay against the deployed bot code. Package pending, with a stall-test re-run (test-tree issue).
- Autonav reward-screen package pending as well.
- Manifest guard: Sol r1 NO-GO with 7 gaps (incl. stale .pyc, opponent models uncovered); rebuilt, re-review next.
- mac_decode_check.py is in Sol round 3. 15d80e820's common.py has parity with 3b48744f; sha256 8b755403….
- After handsync, the Skeletons deck (the bot lead's top deck search result) can come back.

### 08:33Z packages ready; decode swap GO sent; levels pilot funded
- Decode swap: mac_decode_check.py got a clean Sol GO after 4 rounds (sha256 31fd83b3…). The loop owner sent steps 1–4 to the babysitter with my GO.
- handsync-r1 (drive.py cbdf0d70…): base 42/542 wrong cards; handsync 0/517 wrong deploys, guard refused 11. LL_HANDSYNC=0 rolls back. autonav-r1 (drive.py 38cee9c8…) handles reward screens.
- Sol review running (live-handsync-autonav-review-sol-r1): guard livelock, tracker invariants, autonav never-tap list.
- Deploy order: decode swap at the next boundary, then handsync(+autonav) at the boundary after if the review is clean. Skeletons deck after one clean handsync session.
- Manifest guard r2 (7 Sol findings addressed) is in its bundle E2E, then Sol r2. 15d80e820 common.py (8b755403…) parity identical, unknowns 19,944 → 5.
- Bot lead: levels pilot funded (bot-lead-levels-pilot-r1). An L4 Musketeer dies to an L6–8 Fireball, which uniform L11 gets wrong. RoyaleSim A/B, 200 paired games. --levels held until then.
- playdet r2 sims at 764/2000, ETA ~10:10–10:25Z.
- Committed 5b55e3aa8: RESULTS s23–s26, ACCOUNT-LOG, opponent decks, PROGRESS.

### 08:39Z s27-m02 real 45 s loss; s27-m04 wrong-card case; rule refined
- s27-m02 was verified on video as a real battle: our Giant+Archers took the enemy left tower while an enemy MiniPekka/Musketeer/Goblins push killed our right tower and king; no Cannon defence. Sent to the bot lead as a levels diagnostic; the 05 mirror is verified by sha.
- s27-m04 n212 (opening play): the bot logged MiniPekka slot 2, but Archers was deployed (HUD, video and elixir agree). This is the known handsync mode (a). GO to resume, s28 unpaused.
- Rule: until handsync is live, wrong-card plays are counted and reported, with a hold only at ≥3 in a battle or a session rate clearly above ~8%. After handsync, any wrong-card deploy means hold.
- Loop owner asked to run sync_replay/slot_audit on s23–s27 as an out-of-sample check, including this case.

### 08:43Z decode swap DONE at s27→s28 (boundary 67 s)
- Mac check rc 0: 3/3 record_equal; Any* 3/4/2 → 0/0/0. Installed common.py 3b48744f…, .bak-pre-anyunit 153c8c61…; export hashes pinned.
- s27 3W–1L (m04 W); record 90 battles, 56W–34L. 1 confirmed wrong card (n212) out of 85 plays. No account changes.
- s28 runs on the fixed decode; rows untagged from s28-m01. First-battle FPS/step check at match_end.

### 08:55Z e16 DEPLOY GO at the s28-m03 → s29 boundary (Sam's top priority)
- Blocker was only the unrun live FPS replay. Integration finished at 08:12Z (ANE 1024 p50/p95 36/49 ms; parity 753/753 agnostic), but the report wasn't actioned. Skipping the replay; measuring live.
- I staged on the Mac ~/clasher-live/tmp/e16-stage: drive.py fbf34ebe… (main f93a7a06 + --perc-threads), yolo_units.py 091350df…. Model, classes and offsets hashes verified on the Mac. The babysitter swaps with .bak-pre-e16 and launches s29 with --units yolo e16 agnostic=1 --perc-threads 4.
- Rollback: FPS < 5.5 / step p95 > 45 / errors / stalls / phantoms. Drop --perc-threads first, then --units.
- Enemy king false-low HP (hp_frac < 0.2 while alive): 21 runs s1–s28. Pre-existing; sent to the r3 owner.
- New standing rule (Sam): all image inspection goes to Sol helpers. Memory: sol-for-image-inspection.


### 2026-10-16T09:08:08Z Sol resume in place — current status and audit
- Sam's 2026-10-16 freeze governs: routine fixes/tests/evidence and existing jobs continue; no new strategy/runtime/model promotion. Current worktree is `/mpac/sdicks02/repos/clasher-live` (`live/lead`); the command-center checkout had stale PLAN-only progress and was read only. Existing owners' dirty files preserved; no merge/rebase/commit.
- e16 s28→s29 verified via sole Sol babysitter at 09:05:26Z: exactly one driver PID6545, page67178, no observer/chain watchers, s29/m03 unpaused. Exact code/model/config hashes and local evidence digests are in `reports/live/audit/sol-resume-20261016.json`; s28/m04 was a wait directory, not a fourth battle. No new driver or host command by LIVE LEAD.
- s29m01 L1–2 (813→782),684 decisions,26/26 submitted/HUD confirmed,FPS9.834,decision-step p95 37.972ms. s29m02 W1–0 (782→812),881 decisions,36/35,FPS9.818,p95 35.273ms. Both zero step/yolo errors/guards/stalls; existing FPS<5.5 / decision p95>45ms / errors / stalls / obvious phantoms gates not triggered. Local `report_run.py` rechecks rc0 and rollback_flags empty. Distinguish report's all-frame p95(19.9/19.4) from decision-only gate metric. Capture restarts1/2 and m02 between-battle nav_stuck1 remain logged; babysitter asked to reconcile manual clearance.
- Exact enemy→ours evidence: s29m01 n1865 tick3506.211, redL5 Musketeer/Goblin right bridge; preserved05 video001865.jpg + frames/perc + overlay. Routed to r3 WEAKNESSES/data audit, no per-card workaround. These are real units with wrong ownership; prior GO continues.
- King false5 is towers.py OCR of a troop badge, not ft-r6 HP head. Loop owner retains tower candidate/tests; r3 does not edit loop files. Candidate NOT deployed: corrected normalization test found81 changes/796 prior readings (1917→117,1468→168 examples). Loop owner fixes offline and owns already-started SMALL Astra numeric diagnostic; no duplicate diagnostic.
- Recovered review: handsync GO AFTER FIXES/autonav NO-GO;103 existing checks pass each overlay,24 package handsync (28 optional replay),29 classifier/6 autonav checks,12000 structural checks. Reproduced reserved-slot race/livelock/opening timeout/exceptions/capture reuse/unsafe synthetic reward tap prohibit old bundles. Prior0/517 claim means residual measure-mode: raw4/517 wrong,all4guardflagged,25baselineactionsomitted. Guard r2 NO-GO; enforcement redesign parked for Opus.
- Remaining translator owner was idle with pending approved work: configured/resumed same thread on Sol high, ordinal27/task recorded in audit. Existing gen03 helper active;03 driver3965663 alive1191/2000,8/16 rc0 zero failures at09:06:47Z. r3/loop/synth/yb3/level pilot and babysitter already active; completed reviewers stay completed.
- GPU04 V7 and08 V6 finished cleanly rc0 at08:39:34Z/08:53:40Z;01 V8PID1967844 e9/20 active. Reported completion to BOT LEAD/coordinator; no replacement trainers. Synth owner preserves QA bank and queued jobs; no duplicate compute.
- Parent notified immediately of deployed hashes, metrics, defects, account ledger and job states. No new account actions; last prior changes Archers6→7(40wild/1000gold),Minions4→5(13wild/150gold),balances6421gold/300gems/59wild. No deployment/rollback/commit in this resume; no new host-touching scripts. Next: babysitter finishes current gates, loop owner corrects tower/handsync offline, r3 audits ownership and completed evals.

- 2026-10-16T09:08:35Z Follow-up: s29m03 W1–0(+30→842),786decisions,32submitted/33HUDconfirmations,FPS9.8,decisionp95=36.362ms; no step/yolo errors/guards/stalls/manual taps. s29 now2W–1L throughm03; m04 playing same PID6545/priorGO. m02 nav_stuck was raw n0/ts0, automatically cleared by result/home taps at4.6543385/8.688903249s;matchstart14.250389917s, no manual clearance/filepause. m03 nav_stuck1/capturecounter3 logged separately. No account change/new promotion. Audit JSON updated; these are exploratory live outcomes, no strength claim.

- 2026-10-16T09:10:09Z Material capture correction: s29 restarts1/2/3 throughm03 are REAL SCK stream interruptions; currently4×SCStreamErrorDomain Code−3805/application connection interrupted and5starts duringm04. Babysitter read deployed LiveFrames._run and stderr; counter increments after stream end. Cause unknown; no attribution without evidence. Zero step/yolo/stall errors does NOT mean zero overall incidents. FPS~9.8/current prior gates pass; no new rollback rule/driver. Sole babysitter copies bsgrab.stderr05 after session; parent+loop owner notified for existing-evidence diagnosis.
- 2026-10-16T09:10:09Z Synth NC rev2 sync complete09:07Z,verified09:09Z:443reviewed official masks+310unchanged preview negatives;5962sprite rows/281floors/16heldouts to03/04/08 (images before8metadata files), all host hashes match.04/08 CPU-room queued throughout,no bank loaded during sync; admission5962load-log confirmation pending. Completed01x01a50k and04pilot1k used457;01bank untouched. Hash-verified rollback457 bank/indexes/classes preserved. Receipt monitor-sol/official-rev2-sync-receipt.json; exact metadata hashes in audit JSON. No restart/extra launch/signals/account/runtime/strategy change. Nulls2runs fails>=5 gate. Parent+r3 notified; source balance and all prior gates retained.

- 2026-10-16T09:12:14Z Sol exact-frame review supersedes earlier definite Goblin wording: s29m01n1865 two redL5 bridge bodies are enemies(owner1), final records incorrectlyowner0. Stored Musketeer(score.5845,x13.609,y15.704) and Goblins(.5063,x14.190,y17.192) are predicted classes; visible class/instance association remains uncertain (Musketeer favored for leading body, second Musketeer/Goblin unresolved). No explicit producer/source/owner-confidence or raw detector boxes in row, so raw YOLO/fusion cause NOT proven. Nearby units_model owner1.7659 corroborates team only. Review/source verification read locally, unchanged-source checks pass; exact hashes in audit JSON. No label/patch applied. Parent+r3+babysitter notified.
- 2026-10-16T09:12:14Z Translator resume audit09:10Z in integration/PROGRESS + jobdir JSON:10CLI/testset tests pass,diff clean,full/veto fit runner check-only handles complete32-shard ledger/rejects partial input; waits for gen03 checksummed delivery before approved sequential2thread nice19 fits. Internal split205/513 T1 physical matches straddle train/report via noise arms: internalP/R diagnostic only; independent A→syntheticbank/fuzz→singleB gates unchanged. Split redesign deferred for Opus. No birth/rule/runtime change; provisional sims10:10–10:25Z/extraction10:45–11:15Z.

- 2026-10-16T09:14:32Z s29 FINAL3W–1L→872;m04W1–0,708dec26submitted/23HUDconfirmations,FPS9.797823,decisionp50/p95=7.234/35.862ms,0step/yolo/stall/guards;nav_stuck1autocleared,capturetotal4. Sole babysitter started s30PID52026 same approved e16/perc4/Cannon8,unpaused,18sboundary;no accountaction/promotion. All s29videos/logs05verified,Mac-onlypruned. stderr preserved05/runs/s29/bsgrab.stderr sha13959199ab92605ab0228893438f81e7e4d8d1444e0d6f453ac3f70ca572d2a8;4×−3805/5starts. Resetgaps730.410/879.813/878.669/819.112ms at1.541/1.691/1.681/1.629s afterstart;stderr noUTCtimestamps,orderedcorrelation only.
- 2026-10-16T09:14:32Z OFFLINE concrete capture suspect: verified saved deployed drivefbf34ebe exacthash;grab_arena_bg lines261–274 starts second bsgrab/SCK subprocess(3nativeframes,fps4,seconds5), unconditionally called live matchstart lines547–551. Each s29battle logged arena_bg frames3. Driver itself creates duplicate SCKclient, while babysitter no-screenshot statement remains true. Strong mechanism/timing candidate,not controlled causalproof. Parent/loop/r3/babysitter notified;loop owner retains driver ownership and prepares bounded routine offlinefix/review using primary stream/existingdata. No live edit/newhold/hostscript/newdriver;priorGO/gates unchanged. Exact commands/source+receipt hashes in audit JSON.

### 2026-10-16T09:23:59Z Updated Sam authority; capture-only shipping in progress
- Current rule supersedes blanket hold: make obvious routine confident reversible decisions now; passing meaningfulchecks+requiredreview+concreterollback allow shipment. Only consequential hard-to-undo sufficiently uncertain decisions defer. Failedtests/unmetreview remainblockers. Propagated recursively to loop/babysitter/r3/synth/translator/reviewer;noClaude retries.
- Coordination: direct t3_thread_send(modeauto) to exact parent0523ae6f-baa3-4d4e-b233-b392671670db orappropriateexistingowner;question/evidence/recommendation/dependency stated;independentworkcontinues. No user-inputtools/pendingoldrequests. Added to futurebriefs and ownerHANDOFFs.
- Capture-only fix finalaa98505 against exactdeployedfbf34ebe removessecondSCKhelper/call;event candidates reusemainJPEGs,explicitpending/unverified/framesnull,relativevideo+path_baseevent_directory preventfalsematchrenamealias. Superseded6b2e37/358269 MUSTNOTdeploy. IndependentSolr3review active;priorroundscanceledonbytechanges,allfindingscarriedforward. FinalE2E+renameprobePASS session6173exit0/tmp/tmp.Qbxo2oh9zy:1primary/no secondstream/restarts0,3JPEG+metadatahashesretainfalsematchidentityafterrename+reopen. PackageSTEPSexactfinaldriveraa98505/testd49e44a5/rollbackfbf. Requiredscanner/tempindexcommit+solebabysitter normalboundarydeploy followGO;noOpuswait.
- s30m01W3–1→902,569dec19/19,FPS9.8,decisionp9533.146ms,0runtimeguards/navstuck,capturerestart1;reset1.510safterstart701.621msgapmatchesbaselinepattern. m02W2–0→932,685dec26submitted/28rawHUDconfirmations,FPS9.8,decisionp9535.194ms,navstuck1autocleared,capture2,noaccountactions. Latestparentreceipt m03W→962,m04activePID52026. Arena4threshold1000:routefirstnewarenaframefromexistingrecordingtoexistingr3Sol audit;noextraSCK/helper.
- Final6 deployedconfigevals allrc0(1024x672/conf.5/agnostictrue/iou.6,227frames833units18empties,emptyFP0);nonepassallstandinggates. ExactV6TCP.957/.957/.957,V7.968/.947/.926<.970floor. e16retained;V8existing. Finaltable/receiptpinsownedr3;do notroundfailtopass.

### 2026-10-16T09:33:06Z Capture and tower fixes committed; deployment released
- Capture independentSolr3GO finalaa98505/testd49e44a5;allpriorfalsematch/provenancefindingsfixed. Scoped3-filetempindexonorigin/main,isolatedGIT_DIRHEAD avoids upstream/staleworktree comparison;requiredscanner+diffcheckrc0. Initialplain-tempindexdiffcheckincludedunrelatedupstreamwhitespace;correctedisolatedHEAD/scopedcheckpassed,nootherownersfileschanged. Pushedbd3eec30d9412876436610a59defd73e4717771c at09:27Z(driver,test,CAPTURE-SINGLE-STREAM.md). SharedHEAD/index/WIPpreserved.
- Tower freshindependentSolGO exact58033f;13/13hardenedbadge+10/10guardchecks,796baselineunchanged,127kingreadings/3007rejectionsprobed,TowerReaderASTidentical. Scoped3-filetempindex/scanner+diff0 pushed0dfea3172f57c68082e22795e3ce9d2096afe9b9 at09:29:58Z(towers,test,TOWER-BADGE-FIX.md). Nootherdriver/model/hand/autonav/manifestchanges.
- BothDEPLOYGOs sentsolebabysitter:stageNOW,normal31→32boundary,verifyexactbase+independentbackups+deployedhashes+__RC;sameexistingargs/e16/deck. Capturebase/rollbackfbf34ebe; towerbase/rollback82097878. No livechangebyLEAD,receiptsPENDING. Firstbattlecapturegap/restartdelta/relativecandidatechecks+kingHP/realHP/FPS/decisionp95/errors required underexistinggates.
- s31PID93716started09:25Z afters30ended;capturefixnotyetlive. New2screens matching s30m04n1168–1290/likely1287 routedsolebabysitterforpreservation;existingSolreviewconfirmsMusketeermiss/wrongteam,butlowerbodyKnightconsistent. DoNOTlabelthosebodiesBarbarians.
- Mappingcontractaudit:coordinatorR3overallowner,existingintegrationworkerresumedSolforwholecontract/capability/proxyisolatedpackage;no duplicateedit/imagehelper. Generalbarbarian/evolution cardBarbarians/identityKnight aliasrealcanonicalobservationissue;legacyproxyintentfromKataCRbaselineconsidered,specificrawknightoutputsnotproofofbarbariancause. R3rawheadsteamtraceindependent;freshreviewbeforeanymappingdeploy.
- TranslatorgroupedsplitcorrectionfreshSolGO b7372226/test718dae19,9tests+real54136rows205→0crosssplitmatches,413train/100report;requiredscanner0/rollbackfaea95ce. Full/vetofitswaitcompleteverifiedgen03delivery.09:32Zsims1530/2000,8/16rc0,zero failures,8NI19workers,existinglease/no duplicatejob.
- R3reviewed9labelrepairapplied09:24Z05/01/04/08:39→38unitbodies,51towerrowspreserved,noimages/raw/exclusionschanged;perhostbackups/rollbackandposthashPASS. ExistingV8samePIDreadsupdatedlabelsper-sampleafter09:24;OLD457synthlineageexplicit.

### 2026-10-16T09:35Z Integration mapping audit (Sol high, local only)
- Exact deployed adapter `091350dfeb69a97735160a647dac3749a70cc3ba862790ef5c10720a5714b515` and mapping `f033bf1b787d6594bde9296ba7350932a449d367f9635969b354fa8269f95bec` copied from existing05 evidence `scratch/live-loop/evidence/s30-m04-phone222/source/` into isolated `jobs/clasher/katacr-yolo-live-20261016/mapping-audit-20261016T0931Z/base/`. Jobs deploy/yolo_units.py has different SHAec53d9f9 and was excluded; shared dirty adapter/drive preserved. No own commit.
- First scope/fix/test plan sent DIRECT to LIVE LEAD, loop owner and r3 before edits. r3 owns overall canonical-observation/backend-proxy contract; integration retains isolated implementation. Legacy proxies are intentional baseline data (KATACR-BASELINE + frozen proxy table); blindly preferring card over identity is unsafe for unsupported/descendant bodies. Coordinator requires truthful primary observations with backend standins separate; additive metadata alone is insufficient. Precise contract awaits existing r3 code-only diagnostic; no duplicate helper/image/model work.
- Model-free exact-adapter checks at09:32:54Z PASS:156names×2owners=312 paths,312 plain class IDs,11 proxy/descendant inventory checks,3 unsupported/unknown/unitFalse cases. Classifications:60 intentional legacy aliases,52 equal source/identity,43 null identity,1 class-only unknown. All output owner/coordinate/score/schema/source-name behavior pinned. Four rows differ from CURRENT legacy job mapping:royal-recruit-evolution,elixir-golem-mid,elixir-golem-small,hog. No automatic correction applied. Source labels/parent cards are not treated as actual backend capability.
- Exact recovered translator5361deb0 (git e1b468ecc), common3b48744f (git9e954c5b4), l1_v4ced093d match local evidence; sole babysitter asked for actual deployed runtime/config/template pins. Archived runtime public-template reconstruction only is running nice19/CPUs2-3/single-threadBLAS, no detector/policy load. Exact commands/base hashes/transient missing-git-object recovery/tests/deferred issues in scope-receipt.json/base-sha256.json/mapping-audit.json and scripts in isolated audit dir. Final justified frozen package→LEAD independent Sol prehost review→sole babysitter normal boundary; no Mac/SSH/input/capture/training/host09–18 commands or deployment by integration.

- 2026-10-16T09:34:57Z Capturestage Macaa98505verified__STAGE_RC0 at09:30Z;notyetdeployedmid31. Reaffirmedsolebabysitterprioritystagebothreviewedfixes/normal31→32boundarybeforeoptionalfirstanchorsearch/inventory;independentbaseguards/rollback. No newdriver/clientfromLEAD.
- 2026-10-16T09:34:57Z Screenshotprovenance correction retained:5rawsampleframes1188/1208/1228/1248/1288 hadnoexactjoin. Laterseparate1280/1287check HIGHconfidenceIMG2↔1287;IMG1↔1280VISUALLYREJECTED/exactnunknown. No contradiction(1287notinthe5). LowerbodyKnightcorrect;genericBarbarianaliasseparate. EnemyMuskowner1→0acrosssampledframeswithredL6badge;parallelunits_modelenemycorroborativeonly,notpipelinecause. Existingr3Solhelper/reports/sourcehashespreserved,noduplicatecapture/helper.

- 2026-10-16T09:40:23Z Currentaudit authorization/deferredfieldsupdatedtocorrectedSamrule(noautomaticOpus/promotion/designhold);actualfailedreviews/testsremaingates. Hand/navr2reviewactive:knownbaselineauthorizedmanualfree rewardflowskeptUNKNOWN/manualandloggednav_stuck/manual/account;notnewregressionalone,neverunsafeauto-tap,unsafe/unclassifiable/cannotclear/newerrorholdunchanged. Decisionexplicitlysentowner+parent,notsilentrulechange.
- 2026-10-16T09:40:23Z Mappingcapabilityaudit confirmsactual56cfg/70templates;ALLaliasedcanonicalcardsunsupportedincfg,Barbariantoken23notcapability. R3overall/integrationsoleadapterimplementation+existingtranslatorconsumerownercoordinatecanonicalobservedbody/detectorfamilycard/rawname/index/p_team,separateexplicitbackendexact/proxy/unplaced projection;bodyconstraintsforwardedthroughdefaultassign/tracker,authoritativeregistry/unresolvedexplicit. No blindcardpriority/newOOVpolicy/adapter-onlyfix/duplicatehelper. RawMusketeerteamtraceindependent.
- 2026-10-16T09:40:23Z Referenceslotoriginal4070exit0/118tick600complete;reviewedcontrols36861ACTIVE09:32:46,NOTidle,hardstop10:10Z/sendcap10:09:55. Synthowner→existingmonitorinformed;Nullsresumewaitsfixtureownerexplicitidlehandoff,>=5gateunchanged;no extrajob/client.

- 2026-10-16T09:42:01Z DEPLOYED at normal31→32boundary09:38:09Z:onlydriveraa98505+towers58033f;stage/base/independentbackup/deployedhashesPASS,__DEPLOY_OK/__RC0. s31PID93716natural4/4exit;new32PID33448started09:38:25ZRC0,samee16/perc4/ft-r6HUD/Cannon8/r3birthsargs. Rollbacks remainexactfbfdriver/820978tower,independent/safeboundary. Exactcommands05scratch/live-loop/s31-s32-twofix-commands-sol.json. Parentnotifiedimmediately;firstcompletedbattlevalidationpending. Noaccountaction/model/deck/otherbundlechange.
- 2026-10-16T09:42:01Z Sam message policy nowcurrent:messageparent/owneronlyneededaction/input,realnext-step-changingblocker/failure,ormaterialresult/deploy/accountaction;default<=3shortlines/80words,currentresult+neededaction+onereceiptpath,batchrelatedupdates. Noack/healthypoll/unchangedgate-queue/logged-pushedonlymessages. Coordinatorbroadcastsactivechildren—NOrebroadcastbyLEAD. Includeinfuture/resumedbriefs;detailsstayPROGRESS/audit;clarificationsdirectt3_thread_sendmodeauto,notinputtools.
- 2026-10-16T09:42:01Z Arenaargmetadata:soleexistingSolbabysitteraskedreadactualclientnamefromexistingrecordedhome/TrophyRoad,setnextsessionarglocallyevidenced,noextraSCK/capture/noparentconfirmation. Batchfirstpost-fixcapture+tower+perfvalidationinoneshortmaterialreport.

- 2026-10-16T09:44:09Z Added standalone current LEAD HANDOFF.md with correctedauthority/quietDMcoordination/roles/deploybackups/gates/pendingvalidation. Latestresultsfromsoleoperator: s30fourwins→992,s31twoeach→1000;Arena4entryobservedafter31m03,actualnameevidencependinglocally. Existingrecording/overlay/statearound32m01tick2289preservationrequestedforgrayviewer/bannerissue;vieweronlyowner+existingSolhelper,nocapture/inference/newclientchange. SLOT-IDLEexplicitreceipt permitsreservationrelease/existingapprovedNullspipelineresumeafterliveness;actionroutedexistingowner,126fixturesNOTautomatically>=5gatecredit.

### 2026-10-16T09:45:09.147273+00:00 Canonical observation contract agreed; isolated adapter draft
- Message discipline: parent/owner updates only for action/input, changed blockers/failures or material results; ≤3shortlines/80words default. Details stay in this existing PROGRESS and audit artifacts; no acknowledgments/healthy polls/rebroadcast/new helpers.
- R3 owns overall schema/data review; integration sole adapter+mapping implementation; existing translator/OOV owner sole isolated5361/4863 consumer patch. No shared adapter/drive/common/translator/births writes. Reviewed contract: perunit observation_contract=canonical-body-v1; cls=reviewed observed body,card=detector family (not deployment provenance),kind,rawdetector{name,class_idx,p_team,variant},body_resolution,optionallegacy_backend_proxy{body,card,origin}. Never common.body_card to reconstruct canonical family; unresolved bodies remain named observations with explicitunresolved and unplaced consumer disposition. spawn_card not synthesized.
- Explicit consumer legacy_mapping_compat v1 optin approved by r3+OOV owner: preserve verified legacy backend board/plays/elixir/cycle, with true observed family and legacyprojection audit. Defaultunknown_card=drop unchanged; invalid/noentity/samekind mismatch=>unplaced+reason/counter. Consumer constructor/env wiring owned translator, no drive change. No adapter-only ship.
- Mechanical data draft156names:91 existing registry/BODY_ALIASES candidates,27unresolved,60unique cfg+samekind legacyproxy rows; originalindices/card/identity/classes list preserved. Sources registry15.535.86 and existing proxy BODY_ALIASES, no CamelCase guess/parent-main fallback. mapping-draft.jsondf1aeb21 awaits r3 reviewed data manifest; all candidates labeledDRAFT.
- Isolated adapter 1b05090de88885d0fcc19461e008a981e62174ed1bd3e62d73400a69a50298e6: canonical mode only when explicitmapping marker; oldmapping yields exactold outputs. Rawhead class_idx added without decode/NMS/head/team/box changes; canonicalstep uses explicitbody/card/variant/proxydata and never helper/provenance. Metadata copies protectregistry; validation rejects unknowncontracts/invalidresolution.
- Bounded checks PASS at2026-10-16T09:45:09.147273+00:00: 8canonicaladapter tests (156×2owner geometry/dropmask/raw paths, all156 exactlegacyrollback outputs, Barbarian/evolution negativecontrols, unresolvednamed, syntheticKataCR+plainYOLO decode/NMS parity, forbiddenlegacyhelper, malformedcontract failbeforeload) and7exactdeployedtranslatorboundary tests (Golemite/RascalBoy/SpearGoblin loss, unsupportedBarbarians/drop, template-notconfig, emptyRoyalDelivery/BarbLog, Knightstable). Exact argv/UTC/stdout/stderr/hashes/CPU2-3/nice19/env in verification.json; all4 scripts rc0, no model/policyload. Earlier AST-helper nesting error and incorrect initial Rascal expectation corrected to actualmajorityGirl behavior; initialcapability reader used olderbirths then recovered exact4863.
- Solebabysitter provided runtime-capability-s32 read-only snapshot:18 reconstruction inputs match actualMac bytes (15engine/gamedata/2translators),0mismatches; pinsmac2d4e0db8/nativeMac617bfef4. More builder/token/carddefinition source checks requested as needed for exactcapability review; no host action by integration. runtime-pin-equivalence.json pins receipts.
- Deferred blockers: reviewedcanonicaldata; bodyawareconsumer+fullcompat semantics/tests; final exactruntime/template pins; requiredscanner on finalbundle; LEAD freshindependentSolprehostreview; reviewedboundaryGO/solebabysitter only. Rollbackrestore all4 originaladapter/mapping/consumer files+unsetexplicitcompat env, no drive/capturechange. No deployment/commit.

### 2026-10-16T09:49:11.903475+00:00 Integration adapter/data frozen, awaiting consumer bundle
- STRICT SILENCE now applies: no routine status/test/review/queue/receipt/commit/manualcompletion messages; logfiles only. Messages only blockedparentaction/urgentlivefailure/explicitrequest/essentialdependencyhandoff, ≤2sentences+1receiptpath. No reply/rebroadcast; no active helpers.
- Frozen ownfiles in `jobs/clasher/katacr-yolo-live-20261016/mapping-audit-20261016T0931Z/package/`: yolo_units.pySHA1b05090de88885d0fcc19461e008a981e62174ed1bd3e62d73400a69a50298e6; classes.jsonSHAee8adecb240b14b2193bf34f01dd53f6a4fa1e36e1c55fdc882692c05cd7bc62; reviewedbodydataSHA65581fa6239b5716b6fe3a54d04b67b2764006408d01a0dc7db394bdafa687b9. 91resolved/27explicitunresolved;60explicitlegacyproxydata rows, indices/families/legacyidentity/classlist unchanged. Unresolved stays rawnamedcls with unresolved marker; never unknownvisual substitution/parentmainfallback. Rawclass_idx/p_team/variant retained; canonicalfamily bypasses commonhelper. Adapter mode gated mappingmarker; sameoldmapping yields exactoldrecord output for156names. No shared file mutations.
- Final ownchecks:11adaptertests+7deployedboundarydiagnostic tests PASS,312allname/owner geometry/dropmask paths,312classIDs,2syntheticrawheadformats preserve NMS/team/boxes. from_spec/config records canonicalcontract+mappinghash; invalidcontract/resolution fails beforemodelload. Child specificity tests include orphanBrawler/PhoenixEgg/Golemite/RascalGirl/SpearGoblin; no synthesizedspawn_card. Exactargv/UTC/stdout/stderr in verification.json, nice19/CPUs2-3/singlethreadBLAS. gitdiff--noindex--check yieldedrc1/emptyoutput (changedfiles, no whitespace findings). Requiredscanner command `/mpac/sdicks02/cc/tools/bin/clasher-secret-scan` rc0,29scopedfiles via temporaryrepo/index; sharedindexbyteunchanged; no commit.
- Solebabysitter read-onlyruntime-capability-s32 snapshot now22matching publicreconstructioninput hashes,0mismatch; deployedroyalesimvocab tokenhash exactly matches reconstructed token_names. Macnative617bfef4/Linuxnative681b5f2c are distinctplatformbinaries; no Macruntime execution or fullmechanicsclaim. runtime-pin-equivalence.json holds exactsource/hash receipt.
- Detailed frozenmanifest `adapter-release.json` includes ownfiles/base091+f033/consumer5361+4863/runtimepins/tests/scanner/deferredissues/concreterollback. Essential dependency handoff sent only to existingconsumerowner. Parent/r3 readfiles; no routine manualcompletion. Need consumerbodyconstraints+policy env+play/elixir/cycle integration tests, then combinedfreeze and LEAD independentSolprehostreview/GO before solebabysitter normalboundary. No adapter-alone ship. Rollback complete4originalfiles+unsetCLASHER_LIVE_LEGACY_MAPPING_COMPAT, preserve driver/model/capture/HUD; originalhashes included.

- 2026-10-16T09:49:12Z Firstpost-fix s32m01 capture/HP/performancePASS:W2–0+30→1030,684decisions27submitted/26HUDconfirmation,FPS9.8,decisionp50/p95=7.225/35.068ms;0step/yolo/stall/guards/navstuck/writerdrops. Oneprimarybsgrabline,zero−3805/restartdelta/seqreset;startupmaxgap508.649ms,all3relativecandidateJPEGs+metadataresolveafterclose. Ownking3312allbattle,enemy2400→3312startupthenreal3199→3086preserved,no5. Existingreceipt05s32-m01-twofix-receipt-sol.json;localreport_run.py rc0reproducedcapture_restarts0/rollback_flags[]. Batchedparentreport sentBEFOREnewstrictsilencerule. Thisvalidatesfixes,notperfectperception.
- 2026-10-16T09:49:12Z SamSTRICTSILENCE nowdominates:messageONLYblockedneedingparentaction/urgentlivefailure/explicitrequest/essentialdependencyhandoff,max2sentences+1receiptpath. No routine status/tests/gates/reviews/queues/receipts/commits/acks/manualcompletion—evenmaterial.Automatictaskcompletionnotduplicated. PersistedinHANDOFF/audit/futurebriefs;NOrebroadcasttoactivechildren(coordinatorcovers).
- 2026-10-16T09:49:12Z R3PyTorchJPEGheadtrace reproducesMusketeerwrongteamBEFOREmapping(.962class/.003enemyat1228;.821/.103at1287);notCoreMLoriginaltensor/parityclaim. StaticbannerfalseArcher s32m01n1219/tick2289.737finalowner0Archersscore.5825,x4.572/y32.697. Essentialconsumer/gatedependency sentexistingtranslatorowner:executeexactdeployedassign/tracker/boardimpactbeforedecidingexistingobvious-phantomrollback,notinferimpactfromoverlayalone. No model/geometryrulechange.

- 2026-10-16T09:51:01Z Whole-assignment reporting clarification persisted:oneowning-parentfinalonlywhenwholeassignmentactuallydone,result/artifact/remainingblocker;automaticdeliverycounts,noDMduplicate. Essentialcross-ownerhandoffsdirectowner,notcoordinator;substantialendtoendownership,nottinypertestagents;independentreviewsseparate. No policyrebroadcast/ack. Scopedownauditdocspushedc42a85c20084796029be34c6d27e8a5c92dc44f1,scanner+diff0,sharedHEAD/index/WIPpreserved;no forbiddenpushed-onlymessage.
- 2026-10-16T09:51:01Z Adaptertaskterminalread/acknowledged:canonical-body-v1adapter/mappingfrozen1b05090d/ee8adecb;bodyresolution65581fa6(91resolved/27unresolved),18checks,explicitlegacy_mapping_compat-v1consumer. Releaseartifact jobs/clasher/katacr-yolo-live-20261016/mapping-audit-20261016T0931Z/adapter-release.json routedessentialdependencydirectlyexistingtranslatorconsumerowner+r3overallowner;matching5361/4863consumer/fullintegration/freshreviewremainshipblockers,noparentmilestonemessage/noadapter-onlydeploy. Staticbannerexactboardimpactdependencyremainswithtranslatorownerbeforephantomgateadjudication.

### 2026-10-16T09:53:51Z Urgent confirmed static-banner phantom — existing rollback gate
- ConsumerownerexecutedEXACTtranslate5361/births4863atloggedpoll2290,n1219,tick2289.737:bannerArchersassignsownArcher(token4/kind0)andenterspacketx4.572/y32.0;inputy32.697CLAMPED,notrejected. Precedinglogged-pollreplaycorroborates;automaticclock+10tickdiagnosticexplicitlysuperseded. No policy/CoreMLtensor/choiceclaim. Receipt /mpac/sdicks02/jobs/clasher/live-multibody-20261015/consumer-mapping-compat-20261016/s32-m01-n1219-deployed-board.json,SHA2b82d972181f19e32e2cb59cbc9c95e9303af87ec15ebf2925533284b83f183a.
- Decision:existingobvious-phantomrollbackgateFIRED. DirectedSOLEbabysitterearliestsafebetween-battleboundaryomit--units→ft-r6modelunits;retainreviewedcaptureaa98505/tower58033andotherargs. NOnewgeometry/modelrule/promotion;donotinterruptactive32m04/startduplicate. Urgentlivefailureparentnotificationandr3essentialdataacceptancehandoffsent(max2sentences+path). ExecutionreceiptPENDING. Existingcapture/HP/perfvalidationstillvalid,notperfectperception.

- 2026-10-16T09:56:42Z PhantomrollbackEXECUTEDsafe32→33boundary:32m04match_endts244155.989417,n2411;PID33448naturalexit/noSIGTERM/noactivebattleinterrupt. Emptygate/PAUSEabsent/driveraa98505+tower58033hashguardsPASS;new33PID77969at09:54:06Z__RC0OMITS--units,actualconfigunits_source=model/loadedunits=model/frame650bd5cf,unpaused. Capture/tower/perc4/export/deck/runtime/birthsunchanged;--arena spell-valleyactualclientmetadata. Receipt05s32-phantom-rollback-receipt-sol.json andexactcommand05s33-rollback-command-sol.json. Firstwholefallbackbattleperf/finalunitprovenancePENDING;no manualcompletionmessageuntilverifiedorblocked,parentexplicitonce-request. Nogeometrymask/gaterelaxation/modelpromotion.

- 2026-10-16T10:01:00Z RequestedphantomrollbackCOMPLETEverified:actual33units_source=model,1731finalmodelinputrecords/zeroYOLOoverridefields,driverlogrecordexactLiveSessioninput+same5361/4863consumer;packetboardnotserialized,nofreshpacketreplayclaimed. Firstfallback33m01cleanL0–1→1032,685dec25/24,FPS9.874441/decisionp9532.767500ms,0runtime/guards/restarts/writerdrop/navstuck. Localreport_run.py rc0reproduced. Requestedonce-onlyparentreport sent(nofutureautomatic/manualduplicate). Exactincidentretained2b82d972;captureaa/tower580preserved,nogeometrymask/gaterelaxation/newmodel.
- 2026-10-16T10:01:00Z Viewerexplicitrequestfulfilledthroughscopedcommit+RELEASEhandoff: freshindependentGO f16a0473/ef6f1dde/test2ae06121;8new/7existingplusoldbackend/restart/nonreaderprobespass. Onlyfrozen2implementationfiles+test+VIEWER-STREAM-FIX.mdtempindexoncurrentorigin,requiredscanner/diff0,pushed547a3b6521c51fc9180bec2a49759ce39fd20505. Essentialhandoffsolebabysitterstage/normalboundary/exactbaseguards+2backups/restartonlyverifiedownedproxy(existinglauncher/sameports/args),preserveallbot/capture/tower/controlstate. No driverrestartmidbattle/newSCK/client;nextnormaldriverreloadsOverlay. LiveviewerreceiptPENDING;nosuccessclaim. Exactsteps05viewer-r1/STEPS.md,commitreceipt05scratch/live-review/viewer-stream-commit-jll826do/receipt.json. ReviewerP3wronghosttimeprosecorrectedinourreport;sourcebytesunchanged.

### 2026-10-16T10:05:12.097609+00:00 Full canonical bundle ready for independent review coordination
- Existingconsumerowner delivered frozen release at jobs/clasher/live-multibody-20261015/consumer-mapping-compat-20261016/consumer-release.json; integration independently verified all24 release/rollback/evidence SHA256s and byte-identity of ownadapter1b05090d/mappingee8adecb/reviewdata65581fa6. No source bytes changed;152consumerchecks/42verifiedproxy board-play-cost-cycle equivalence/scanner0/exactbasepatch evidence frozen by consumerowner.
- Exact combinedreview handoff manifest jobs/clasher/katacr-yolo-live-20261016/mapping-audit-20261016T0931Z/full-bundle-review-handoff.json pins release+adaptermanifests/argvreceipts/base/runtime/capability evidence/rollback. Existing authority: LEAD launches fresh independent boundedSolprehostreview; integration requests directly, no duplicate review worker. Strictsilence retained except essential review dependencyhandoff.
- Critical scope: current PROGRESS confirms e16 rolled back32→33 after true staticbannerphantom reaches backendboard. This canonical contract package DOES NOT fix model phantom/team predictions, mask geometry or relax gates. ReviewGO is codecontract eligibility only; NOpermission to reenablestatusquodetector, no adapter-alone deployment or boundary ship while independent detector rollback gate unresolved. All four originalconsumer/adapter/mapping bytes preserved; no Mac/SSH/input/capture/training/commit by integration.

### 2026-10-16T10:09:38Z Independent full canonical contract review launched
- Fresh bounded Sol-high T3 task `node:delegated-task:command%3Amcp%3Aff24817d-3245-4789-ba9a-57d6d29f6e75%3Adelegate-task%3Alivelead-canonical-contract-full-sol-prehost-20261016-r1`; original brief, prior adapter/body-constraint defects, full canonical/explicit-proxy contract, all24 frozen release/rollback/evidence pins, claimed152checks/42proxy parity carried for independent verification. Local read-only tests max20min/nice19/2cores, no helpers/hosts/models. Pending report `/mpac/sdicks02/scratch/live-review/canonical-contract-full-r1/REVIEW.md`. GO is code/data contract only: e16 remains OFF after phantom; no adapter-alone deploy or gate clearance.
- Nulls ANR independent review GO exact c4ffb6f9; conditional LEAD release sent existing sole monitor for one verified SystemUI tap and unchanged queue seed2026101610. All fresh identity/modal/live/disk/watch/unused-namespace conditions remain mandatory; queue-first rollback, preserve old invalid artifacts, no retries/lifecycle escalation. `/mpac/sdicks02/scratch/nulls/qa/anr-recovery-independent-review-1003.md`. No host action by LEAD. Initial log command python rc127/no writes, corrected python3.

### 2026-10-16T10:12:07.963034+00:00 CARD vocab patch prepared; core dependency not landed
- Explicit user handoff reviewed patch532867a5; applies currentorigin eb4ba9378 and frozen canonical translator unchanged. Isolated candidate4d9c37a5; model-free exacthelper/loader241measuredentries preserved,inputimmutable,idempotent,tokenhashrejects,constructorcompletionAST PASS. Full realruntime/pin/parity not claimed. Receipt `/mpac/sdicks02/scratch/live-review/vocab-live-integration-1q85j1me/receipt.json`, checks `/mpac/sdicks02/scratch/live-review/vocab-live-integration-1q85j1me/completion-check.json`.
- Core1802e899c exists locally but ancestor rc1 and origin lacks complete_vocab: commit MUST wait for CARD landing. Initial translator DM incorrectly inferred landing from masked shellrc; explicit check corrected immediately to owner and dependency sentCARD. No sharedsource/index/host/pin changes.
- Latest user live steering: s34 reserved-slot handsync error; accepted LL_HANDSYNC=0 rollback at safe battle boundary, retaining viewer/capture/tower/modelunits. Existing loopowner resumed Sol for fullfieldreproducer/genericfix/review/package; no duplicate helper/operator and no premature r4 efficacy claim. Actual rollback completion still requires soleoperator receipt.

### 2026-10-16T10:17:13.671244+00:00 Integration final paired review and rollback handoff
- Fresh independent Sol-high review APPROVES the exact paired six-file code/data bundle with no MUST-FIX. Integration rechecked all 24 release/rollback/evidence hashes plus its frozen adapter/mapping/reviewed body data against both independent receipt and r3 final handoff. Product source and original frozen manifests are unchanged. Final record: `/mpac/sdicks02/jobs/clasher/katacr-yolo-live-20261016/mapping-audit-20261016T0931Z/final-review-rollback-handoff.json`; copied review report/receipt/r3 handoff are under `review-final/`. This supersedes only the pending-review status in earlier adapter/full-bundle coordination manifests.
- Independent task: `node:delegated-task:command%3Amcp%3A7bbda7ed-63fb-4178-b469-e7708aa40e0a%3Adelegate-task%3Ar3-full-mapping-consumer-prehost-sol-20261016-r1`. Report SHA256 `bc2705df1789d5a9284b043cc7fc0b2c7bbbbba4b1227a2be1177346acd4d7fe`, receipt SHA256 `b8530ab7a73fd13303f52c63e9dbf55b1fdc948c8189ec3c7bf9066d086dcaa3`. Review reproduced 152 consumer checks, 11 adapter checks and 7 old-boundary diagnostics; independent checks cover all56 archived cards,312 rollback owner paths,472 named policy projections,42 exact-original proxy board/play/cost/cycle equivalences,108 repeated unresolved no-play cases, snapshot/resolve body constraints, invalid-kind/template cases and record self-opt-in rejection. No tests or inference were rerun in this final recording step.
- Scope exception remains explicit: reviewer accidentally reran a supplied selected test that invokes play_match/make_live_player and policy inference, despite the no-inference restriction. No detector inference or host/deploy action occurred; further inference stopped. r3 accepted code/data approval backed by independently authored model-free boundary/provenance checks. This is a reviewer execution error, not product authorization; never call the whole review inference-free. Future constrained reviews must inspect selected tests and transitive calls first.
- Detector enablement stays BLOCKED. The new paired bundle still retains the s32-m01 banner phantom on the backend board; final V8 candidates fail standing gates. Code/data approval does not clear phantom/owner/accuracy/swarm gates, actual CoreML/runtime/performance validation, authorize model promotion or reenabling --units, or permit adapter-only deployment. Preserve current omission of --units and reviewed capture/tower/HUD/driver/runtime/model/offset pins. Only LIVE LEAD can commit/release; only the existing sole babysitter can apply any eventually authorized paired bundle at a normal session boundary.
- Concrete rollback remains all four frozen originals together: adapter091350df, mappingf033bf1b, translate5361deb0 and births48636f63 from the consumer rollback directory, with their full SHA256 values in the final handoff. Unset CLASHER_LIVE_LEGACY_MAPPING_COMPAT, verify originals and stop/reconcile unexpected current bytes before overwriting. Extra alias/body metadata are inert with the old sources; no destructive removal is needed. An eventual authorized new launch must explicitly opt into v1 and verify policy/counter activation.
- Exact final recording command: `env PYTHONDONTWRITEBYTECODE=1 nice -n 19 python3 -B /mpac/sdicks02/jobs/clasher/katacr-yolo-live-20261016/mapping-audit-20261016T0931Z/record_final_review.py` (rc0). The script records its own hash, UTC, immutable source/evidence hashes and actions. Required final documentation secret-scan receipt: `/mpac/sdicks02/jobs/clasher/katacr-yolo-live-20261016/mapping-audit-20261016T0931Z/final-handoff-secret-scan.json`, using a temporary git repository/index and copies only; original frozen scanner receipts/shared index remain untouched. No own commit, helper, source edit, Mac/SSH/input/capture/training/account/deploy action or routine/duplicate completion DM.

### 2026-10-16T10:19:54.477641+00:00 Canonical full-bundle independent R1 NO-GO
- Report `/mpac/sdicks02/scratch/live-review/canonical-contract-full-r1/REVIEW.md`: P2 verified barbarian→hunter proxy transition differs from exact original5361/4863 board and publicplay/cost/cycle timing;2original-source differential assertions fail despite152consumer+18adapter tests PASS and all frozenhashchecks PASS. Release remainsHELD, e16OFF/phantomgateunchanged,noadapter-alone.
- Essential fix/refreeze handoff to existingconsumerowner and contract recommendationtor3: retain immutabletruthfulcanonicalobservations/strict exact-body constraints; separately define explicit legacy-proxy backend relabel/effective-body audit to satisfy acceptedcompatibility. Add transition tests, N1malformedbodyhardening and N2fullenvreceipts. No duplicate implementation/reviewer; freshreviewroundonlyafterfrozenfix. Reviewer reports frozen/sharedsourcesunchanged but sharedindexhashchangedconcurrently(causeunknown); preserve currentindex, no restoration/sourceattribution.

- 2026-10-16T10:20:30.554146+00:00 Soleoperator receiptsread: viewer547a COMPLETED29default720x1280+9mobile360x640complete decodedJPEGs, uncheckedmobile/controlstatepreserved, noWAN/Safariclaim. Handr4FAILED;actuals35PID40053LL_HANDSYNC0baseLiveSession/LiveTranslator/modelunits verified; sourcefiles/capture/tower/viewer/deckpreserved, wholefallbackperfPENDING. SafeSTOP10:14:28Zafterm03: m01/m02boundariesMISSEDduringobservergaps, notdeliberateadditionaltrials; noactivebattleinterruption,m04waitonly. s34m03greyedholdalso logged. Existingloopownerownsfullfieldfix/review, no newhelper/operator. Receipts05viewer-r1-deploy-receipt-sol.json/handsync-autonav-r4-deploy-receipt-sol.json.

### 2026-10-16T10:32:41.189303+00:00 Integration dependency changed to consumer R2; R1 approval superseded
- Current consumer dependency is `/mpac/sdicks02/jobs/clasher/live-multibody-20261015/consumer-mapping-compat-r2-20261016/consumer-release.json`, SHA256 `71cdbde2c3ce9c39f4b2512900aaaed1455101ea921d3f775aa1e8fe59e69f85`. Integration verified all40 release/rollback/evidence hashes and exact byte identity of its frozen adapter1b05090d/mappingee8adecb/reviewedbody65581fa6. Original four rollback hashes remain unchanged. No product bytes were edited. Current authoritative integration pointer: `/mpac/sdicks02/jobs/clasher/katacr-yolo-live-20261016/mapping-audit-20261016T0931Z/CURRENT-RELEASE-STATUS.json`; detailed dependency/rollback/evidence pins: `/mpac/sdicks02/jobs/clasher/katacr-yolo-live-20261016/mapping-audit-20261016T0931Z/consumer-r2-dependency-handoff.json`.
- R1 is NO-GO: later independent transition finding supersedes its earlier APPROVE and the approval status in this log at10:17 and final-review-rollback-handoff.json. Preserve those immutable records as historical evidence, including the policy-inference scope exception; do not reuse their approval or rerun the historical R1 recorder to establish current status.
- R2 owner claims original family/relabel/composition semantics for explicit legacy_proxy projections, strict constraints for exact observations, separate requested/effective assigned-body audits, malformed cls rejection, and complete runtime/environment receipts. Owner claims214passing checks,48original-source transitions across both owners/directions/capture gaps/revival/body counts/before-after-close,42proxy parity cases,12malformed-cls cases,111runtime source pins, forward/reverse patch and scanner0. Integration did not rerun tests or inference; these remain claims for fresh independent full-bundle review.
- Existing LIVE LEAD/r3 coordinate the fresh full-bundle review; no duplicate review/helper/consumer implementation launched. R2 is REVIEW-PENDING, detector enablement BLOCKED, no adapter-alone release. Banner phantom/model gates remain unchanged. Independent vocab owner still owns its separate landed-core dependency; do not fold unseen changes into the frozen pair without combined checks/review. Eventual rollback remains all four originals together plus unset CLASHER_LIVE_LEGACY_MAPPING_COMPAT; verify targets and stop on unexpected bytes; preserve model/pins/driver/capture/towers/HUD.
- Exact recording command: `env PYTHONDONTWRITEBYTECODE=1 nice -n19 python3 -B /mpac/sdicks02/jobs/clasher/katacr-yolo-live-20261016/mapping-audit-20261016T0931Z/record_r2_dependency.py`, rc0. Required final dependency documentation scanner receipt: `/mpac/sdicks02/jobs/clasher/katacr-yolo-live-20261016/mapping-audit-20261016T0931Z/consumer-r2-dependency-secret-scan.json`; temporary copied documents/index only. No Mac/SSH/input/capture/training/model/pin/account/deploy/commit/shared-WIP mutation or routine/duplicate owner message.

### 2026-10-16T10:34:01.140497+00:00 R2 canonical review and single-battle handsync r5 release
- Fresh independent Sol-high fullbundle R2task `node:delegated-task:command%3Amcp%3Aff24817d-3245-4789-ba9a-57d6d29f6e75%3Adelegate-task%3Alivelead-canonical-contract-full-sol-prehost-20261016-r2`, originalbrief/R1/N1/N2/explicitproxy-backendsemantics/214claimedmodel-freechecks/currentpins carried. Reviewer MUSTpreinspecttests/transitivecalls,no policy/play_match/detector inference; max20minnice19CPUs2-3. OnlyLEADreviewowner confirmedconsumer(no duplicate). Pending `/mpac/sdicks02/scratch/live-review/canonical-contract-full-r2/REVIEW.md`; e16OFF/phantomgate/noadapter-alone/runtimepin action unchanged.
- User explicitly authorizes r5singlefile+clearreviewedfive-losshold ONLY forONEbattle. ReadindependentGO/exact13hashes; tempindexoncurrentorigin eb4/scanner0/diff0/push0 committedONLYhandsync.py7b1c0b5c as9fad2e273935272bdc023f4da6d1a09ac46398b2. Sharedindex/HEADunchanged. Receipt `/mpac/sdicks02/scratch/live-review/handsync-r5-commit-u29whq42/receipt.json`.
- EssentialreleasesentSOLEbabysitter: normalboundary/exactr4base2a/driverdf928/uniquebackup guards, LL_HANDSYNC1 existingONEmatchlimit/nochain-autostart, thenvalidationboundarybeforeanyfurtherplay. Preserveeveryloss/incident and viewer/capture/tower/MODELunits/e16OFF/runtimepins/deck/args. Allerror/greyed/refusal/otherholdgatesretained; failureLL0safe-boundaryrollback. NoMacoperationbyLEAD; actualdeploy/canaryreceiptPENDING.

### 2026-10-16T10:40:53.839243+00:00 Reviewed LIVE template-vocab integration COMPLETE (source only)
- CARD corea6a5401c1 landed/remoteverified; exacthelper38113873 matches approved1802source. Applied exactreviewed532867a5 patch to actual5361 source inisolatedstage, no sharedWIPoverwrite. Two callsites load_vocab and LiveTranslator explicitvocabconstructor complete measuredvocab from runtimepublictemplates. Focused8existingtranslator/fair-information testsPASS16.02s on archivedMacbench r1-total/native-total-r1, nice19CPUs2-3/oneBLASthread, excludespolicygame/detectorinference. Priorfixture241measuredentries preserved/immutable/idempotent/tokenhashrejects.
- ScopedONEfile tempindexonorigin a6/scanner0/diff0/push0: `ae3f6b0c579c5c817630b92a64089917c6623704`, candidate4d9c37a5. Sharedindex/HEAD/WIPpreserved. Receipt `/mpac/sdicks02/scratch/live-review/vocab-live-commit-zkroscqu/receipt.json`. Noactivepins/Mac/runtime/rootreleasechange. EssentialcompletiontoCARD; consumerfuturecombinedpackage mustmerge delta+exactcomplete_vocab helper hostdependency withbaseguards/combinedvalidation/review. CurrentR2frozenreviewunchanged; detectorOFF/noadapter-alonehold remains.

### 2026-10-16T10:41:49.951117+00:00 Independent canonical R2 GO — code contract only
- `/mpac/sdicks02/scratch/live-review/canonical-contract-full-r2/REVIEW.md` closesR1/N1/N2 for exactmanifest71cdbde2. Independent214frozen+36new+18integration(312subchecks)PASS; allpins/patch/reverse/scanner0. Model-freeguard0calls, in-memory3policyloadstatementsremovedonlyreviewharness; productunchanged. Narrowpreinspectionlimit2pureeventlisthelpersinspectedafterrun disclosed. E16OFF/phantom/model/field/performance/runtime/CoreMLgates remain, noadapteralone/pin/releaseaction.
- Existingconsumerownerassignedsingleisolatedcombinedcandidate: preserveR2frozen, mergeapprovedlandedae3f6b0c5twocalls+exacthelper38113873withactualhostbaseguards/pairedrollback/model-freecombinedregressions, thenfreshindependentcombinedreview. DoNOTcommitR2overnewvocabsource/unreviewedhostdependency, doNOTreenablemodel. No duplicateimplementation/reviewer/Macoperation.

### 2026-10-16T10:48:22.708356+00:00 ONE-battle r5 canary completed; unchanged refusal gate FAILED
- `/mpac/sdicks02/scratch/live-loop/handsync-r5-one-battle-receipt-sol.json`:19/19physicalHUDcompletions,0reservation/steperrors,4ownduplicatesdropped;9.8729FPS/decisionp9531.2141ms,0capture/drops/navstuck/HP5. First5physicaldeploystextmatch, nofull19/futureperfectclaim. L2–3, floor1000/0deltainferrednotsettledtext;ALLlosses/incidentsretained119total70W49L.
- GateFAILED3/22greyed=13.636%>10%, NOexemption/relaxation. Oneactualstart/end/naturalexit, NOchain/furtherplay. Afterexactguards restoredONLYhand2a frombackup, nextauthorizedlaunchMUSTLL0; currentlyNOdriver/proxy20393/validationPAUSE. All1573video/211552624bytes05verified, onlyMacpruned.
- Existingloopowneressentialhandoffownswholeofflinefield n597/948/1457diagnosis→genericjustifiedfix/tests/review/package. Actualrequestedsearchactions1994/221/2097; emitted2304ispost-refusalnull, notproofNULLguardbug. Distinguishtrueunaffordability/reservation fromreader/planner/guarddefect; coordinateexistingownersasneeded, noextraoperator/helper/liveaction/gaterelaxation.

### 2026-10-18T04:58:18Z display: memory-route black video fixed (gate = vision driver only); MuMu native size
- Memory-route battles (live/mem memloop, no vision driver, no video/ JPEGs) held the capture gate and forced 'frames' -> black placeholder + overlay (mem-l4 04:43-04:47Z, Sam saw black). Gate / frames / allowed now count a battle only while a vision driver process exists (pgrep '[d]rive\.py', fail closed: rc!=1 or error = present; signal/start/exit checks fresh, 10 Hz loop cached 1 s). Deployed via new feed-only deploy (no dispgrab rebuild), feed 67550->48361, sha256 5f7c185f1a13c036e26ae28b1a074694de8ddf74fb4eb1812d04a3239d181c4c; Sol review r1 GO. Interim: capture-gate opened by hand 04:53:13Z for mem-l5. Evidence mem-l5 (display mode, gate open): 65.10 s of RTSP samples over battle ticks 659..1996, 20.76-24.26% pixels changing between samples (live, not black/frozen); overlay tower labels matched the logged tick 3224 row (Sol report); same-time HP of the earlier battle not verified. Tests 58/58 PASS 04:59:21Z with the deployed dispgrab source.
- Registration: SCK window capture copies the sourceRect at native pixels (scalesToFit off) into the requested buffer, so size [1080,1920] padded 1034x1838 native -> guest scale 0.957489, 16.4% black right/bottom (a smaller crop only clips more). MuMu config now omits size (native = crop x backing scale). Native-size config applied after idle preflight at 05:00:28Z; decoded 1034x1838 result frame at 05:00:56Z normalized to 1080x1920 has scale 0.9993706 and offset (-0.214,+2.187) px (1451/1664 inliers), near-black 0.465%, versus original 0.95733 / (+0.03,+1.94) px / 8.8% near-black and tower-anchor drift up to 35 px right and 58 px down. Failed explicit crop was reverted before the native-size fix. Final native-size battle overlay check PASSED (mem-l6, 05:04:30-05:05:36Z): 65.000 s of decoded battle samples, ticks 851-2169, normalized guest-to-stream scale 0.99938968 and offset (-0.16294,+2.15008) px, max tower-anchor drift 0.66x1.95 px versus 35x58 px before; near-black pixels 0.433-0.479%, changed pixels 20.36-27.02%, no sustained freeze. All paired states were display/starts2/gate open and sole SCK PID 55315 stayed unchanged. Two SCK -3805 interruptions recovered in-process within about 1 s; zero subsecond stalls is not claimed. Evidence: /mpac/sdicks02/scratch/live-mem/stream-check/black-fix-20261018/final-mem-l6/.

### 2026-10-18T07:17Z display: frozen capture now self-heals; no SCK metadata probes beside capture
- Cause: feed's periodic `dispgrab info` was a second SCK client; replayd used executable-path identity and dropped the live stream when that helper exited. At 05:42:18Z in-process recovery failed, while the encoder watchdog accepted repeated old pixels at 30 fps. Window 1629 stayed on-screen; no sleep/lock evidence. Active window discovery now uses CoreGraphics only. Capture-age >=8 s or missing stats for 15 s triggers bounded teardown/reap before replacement; retries retain a visible card and back off to 60 s. State/feed log report capture PID, stale reason/recovery and window status.
- Fresh Sol R4 GO before host execution; 86/86 tests. Feed SHA256 1288459f95223dd2ace05e6bd2d7377324ac0e192a64ae82c07548069ac3bfea; only feed restarted (48361->31629), supervisor13848/media13850 unchanged. Exact-PID STOP test: 31677->33548 in15 s, fresh stats/state in26 s. Post-fault RTSP: 661 unique game frames, 660.067 PTS s/659.241 wall s, battles plus between-battle screens, zero sampled black frames, max PTS gap1.033 s; sole capture33548 in133 samples. No bot/memory/MuMu/adb input changes. Evidence and reviewed rollback: /mpac/sdicks02/scratch/live-mem/stream-check/freeze-20261018/ (FINAL.txt, verification/evidence-report.txt, ROLLBACK.txt); backup stamp20261018T070426Z-31344.
