# LIVE step C: bot-side glue (owner: live-glueC-owner-r1, exploration tier)

Started 2026-10-14T22:57Z on 127x05, worktree /mpac/sdicks02/repos/clasher-live (branch live/lead). No commits (LIVE LEAD commits).

## Layout
- Code: bot/live/ (player.py, translate.py, replay.py, tests). Reports: reports/live/bot/{PROGRESS,RESULTS}.md.
- Python: /mpac/sdicks02/repos/clasher-bot/.venv/bin/python (bot lead's 05 venv, torch 2.10; read-only use), run from the clasher-live root.
- Runtime: CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1 (05's copy of clasher-bot-runtime/r1).
- it5s2: copied read-only from 03 to /mpac/sdicks02/repos/clasher-live-runtime/students/ (sha 08bdaf32… verified, + calibration json).
- Data: /mpac/sdicks02/repos/clasher-bot-data/t1-trainval (local on 05, 577 dirs) + t1-split.json. Heldout never read.
- 05 rules: <=4 cores, nice 19, taskset.

## Log
- 23:21Z D1+D2 done: bot/live/{player,translate,levels,synth}.py, 16 tests pass (bot/live/test_live.py). Reported to LIVE LEAD (report 1).
- D4: bot/live/headline_wall.py + exact command in RESULTS.md §4; 2-game smoke on 05 OK (jobs/clasher/live-glueC/hw-smoke). Reported (report 2).
- D3 running (05, cores 2-5, nice 19, setsid): jobs/clasher/live-glueC/agree-fast (it5s2, 12 games, 10 noise arms) and agree-search-{0,1,2} (K4C unbounded, 3 games each, 10 noise arms). Resume: rerun same command with --start at the next game (games.jsonl lists finished games).
- D5: native_parity.py written (dump on Linux, check on Mac); needs a Linux self-check run.
- 23:25Z BUG found by the replay: a missed perception event desynced the frozen DerivedD1/OwnCycle trackers ('public play inconsistent with ordinary cycle'), breaking pollers for the rest of the match. Fixed: LiveTranslator stream guard (mirrors of DerivedD1 both seats + OwnCycle) drops impossible plays (counted cycle_conflict_dropped:<seat>); LiveSession takes the opening order from the first HUD; LivePlayer survives a failing fast poll. 17 tests pass. Stale results moved to jobs/.../live-glueC/stale-r0; runs relaunched 23:25Z.
- Added bot/live/{mac_pins.py,mac_pins.json,native_parity.py,runtime_manifest.py,summarize.py}.
- NEXT: when agree-fast ends -> core 2: runtime_manifest, native_parity dump+self-check, T1 fast agreement (8 matches). When agree-search-* end -> T1 latency: search unbounded t1, w200 t1, w200/150/120 t4 (cores 2-5).
- 23:30-23:44Z LIVE LEAD: perception schema final (live/perception/common.py:frame_record): card-level identity (spawning card), no play events, no spells, clock_s/phase/timestamp_ms. Done:
  - bot/live/births.py: CardBodies (card -> bodies from engine config: units + production/death children), UnitTracker (tracks, body assignment, opponent plays from CONFIRMED births: 2 sightings within 20 ticks, zone check), ClockTracker (HUD clock+phase+timestamp -> tick; collector.py:379 convention).
  - translate.py: card-level path (default), plays_from='births' (default) | 'events'; frame_record keys (cls/card, towers side 'center', hand dict, exec_ms events); LiveSession emits own plays from completed commands; tick via ClockTracker.
  - synth.py rewritten: SynthPerception (truth-side spawning-card labeller, schema v1) + noisy(); replay arms: events, births, p70, p42, r42-only, hud-only, reseed (LEAD numbers: P .95, R .42/.70, hand 2%, elixir sd .1, tower sd .03).
  - tests: 20 pass (incl. real frame_record() code path, births, clock). Asked perception owner (live-percB) for real validation records.
  - legacy-schema (body-level, events) runs kept in jobs/.../live-glueC/legacy-schema (5 fast + 3 search games).
- 23:44Z schema-v1 runs: v1-fast (core 2, 12 games), v1-search-{0,1,2} (cores 3-5, 3 games each); PIDs 2933852/54/55/60; .rc files on exit.
- 00:16Z schema-v1 engine results final (it5s2 12 games, K4C 9 games) and T1 it5s2 (8 train matches) -> RESULTS §2. Parity fixture (40 roots, Linux self-check PASS) + runtime manifest (80.7 MB runtime subset + 37.8 MB it5s2, RSS 1.0 GB) -> RESULTS §5.
- Added bot/live/perc.py: PERC-<arm>:<player> = play through synthetic perception at a noise arm (win-rate cost via HEADLINE; command in RESULTS §4). 21 tests pass.
- Phase 3 running (phases.sh; started 00:11Z): lat-t1-unb (core 3), lat-t1-w200t1 (core 4), t1-search (core 5); then lat-t1-w{200,150,120}t4 on cores 2-5 sequentially. Log: jobs/.../live-glueC/phases.log.
- 00:30Z DONE (all 5 deliverables). Phase 3 results in RESULTS §2 (T1 K4C) and §3 (latency). 21 tests pass + 1 skipped until real perception records exist (asked live-percB to drop them at jobs/clasher/live-perception-20261014/sample-records/; test picks them up automatically).
  Nothing running. Nothing committed (LIVE LEAD commits; run clasher-secret-scan on the staged diff - not on 05's PATH; a pattern grep of bot/live + reports/live/bot was clean).
  Not done / open: D4 paired HEADLINE (bot lead's 03 slot), optional PERC headline, real-record test, Mac build+parity (needs Mac authorization).
- 04:52Z Real-record fixes (scope set by LIVE LEAD; task (b) real-perception replay belongs to live-integ-ab-owner-r1 - I stop here):
  births.py: ClockTracker anchored on confirmed elixir-phase transitions (+ anchor() for match start; robust clock-reading fallback) - real clock regression MAE 3-6 s had pushed ticks +1200 off; now <=12 ticks once anchored. UnitTracker play detection by spatial cluster vote (vote 10 ticks / 2.5 tiles / 2 hits / score>=.6, relabels absorbed 40 ticks): real-output opponent-play P/R .33-.42/.93-1.0 -> ~.71/.83 on the 2 sample val matches (truth units ~.91/.86).
  translate.py: perception event 'tick' in ms (with 'score') -> exec_ms -> ticks; unit score passed to the tracker.
  test_live.py: real-record test (sample-records), ms-event test, clock/births/frame_record expectations updated. 23 tests pass.
  real_records.py: written (eval script), NOT run - the study is the integ owner's.
