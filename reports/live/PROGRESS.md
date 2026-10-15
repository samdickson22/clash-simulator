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
