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
