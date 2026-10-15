# LIVE integration: (a) event card fusion, (b) end-to-end replay on REAL perception (exploration tier), PROGRESS

Owner: integration sub-agent (parent: LIVE LEAD). Started 2026-10-15T04:42Z. Worktree 127x05 /mpac/sdicks02/repos/clasher-live (live/lead,
= origin/main 2572188d incl. eafb2277). No commits (LEAD commits). Not touching bot/live/mac_bench.py, reports/live/mac-bench/.
Heldout never listed/opened: every loader goes through live/perception/common.HeldoutGuard (raises, not assert).

## Layout
- Job dir (01 and 05): /mpac/sdicks02/jobs/clasher/live-integration-20261015/ (code/ = synced copy of live/, src/, v4 l1 on 01; dump/; logs/).
- 01 python: /mpac/sdicks02/envs/clasher-gpu/bin/python. 05 bot python: /mpac/sdicks02/repos/clasher-bot/.venv/bin/python.

## Log
- 04:40Z infer.py: step() -> step_prepared(arena, hud, ts, unit_floor) (pixel-cache input; exposes peaks + low-score units in .last);
  verified on 01: cache pixels == prepare_pixels(raw) 16/16, step_prepared records == step records 8/8.
- events.py: body fusion via confirmation hold (hold_ms>0); hold_ms=0 == original tracker.
- 04:42Z DUMP RUNNING on 01: dump_records.py, 4 shards x 4 threads, nice 19, setsid. PIDs 1245446-1245449 (python main = PID printed).
  Out: JOB/dump/<ep>.jsonl.gz (64 val matches; resumable: rerun same command, finished files skipped). Logs JOB/logs/dump-K.log.
- 04:44Z dump restarted as 16 shards x 1 thread (4x4 ran 308 ms/frame/process): PIDs 1254332-1254347 on 01, logs JOB/logs/dump16-K.log.
- 04:52Z overlap with live-glueC-owner-r1 (bot/live). LEAD ruling: I own (b); glueC finished and committed 46a595b9
  (phase-anchored ClockTracker, cluster-voted births, ms event times). I build on their files from my own modules.
- New files: live/perception/eval_fusion.py (offline tracker grids on the dump), bot/live/real_replay.py (harness),
  bot/live/empirical.py (+ empirical-val.json), bot/live/test_integration.py (11 tests pass; test_live.py 23 pass).
- Edits to shared files: bot/live/translate.py LiveSession gap fill (catch-up polls, can_act=False; the frozen 5-tick
  D1 gate otherwise kills the fast tier for the rest of the match after ONE skipped poll; mutation-checked);
  bot/live/perc.py 'emp', 'emp-births', 'emp-both' arms; live/perception/eval_events.py lazy finetune2 import.
- Findings so far: (1) hold gives most of the fusion gain; body votes rarely flip (errors correlated with the event
  head: shared backbone). (2) Royal Ghost is never perceived (dense labels ignore it). (3) truth-record vs true
  state differ mainly by Ghost rows.
- 05:15Z provisional fusion cfg from 27 val matches: th .6, hold 500, vote .35, r 1.5, agree 2, early .6.
- 05:15Z K4CW-w200-t4 replay RUNNING on 05 (cores 2-5, nice 19, setsid) PID 4062792 (python; 4062789 = bash wrapper) -> JOB/replay-k4cw (resumable:
  rerun the same command; matches.jsonl lists finished episodes). Log JOB/logs/replay-k4cw.log.
- 05:13Z dump on 01: 27/64 done, ETA ~06:10Z (01 load ~94).
- 05:51Z dump DONE (64/64 val, no errors). 06:06Z it5s2 replay (provisional fusion) on 01, 16 shards -> JOB/replay-fast
  (64 matches, 0 crashes). Found + fixed a harness artifact for HUD-clock arms (now decided per frame like LiveSession).
- Stream-guard analysis (fused events, 64 matches): 330 drops, 302 are TRUE plays (D1 mirror un-rotated by earlier misses).
- 06:15Z final fusion grids (01): split-half selection -> th .5, hold 700, vote .35, r 2.5, agree 2, early .6;
  odd-half F1 .802 -> .851. (a) reported to LEAD 06:20Z. real_replay.FUSION = final; FUSION_PROVISIONAL kept.
- 06:16Z it5s2 rerun with the final config + fixed HUD arms on 01: PIDs in /tmp/fast2_pids.txt (1724368-1724383)
  -> JOB/replay-fast2. K4CW (provisional config) still running on 05.
- NEXT: refit bot/live/empirical-val.json on all 64 with the final config (on 01 when free); RESULTS.md; headline command.
- 06:25Z LEAD: (b) picks the fusion config (both run; tie-break thr .6/hold 500 = fewer false spells); resync-capable
  cycle tracker approved (mine); note Royal Ghost blind spot.
- 06:35Z bot/live/resync.py: ResyncTranslator (+ BothResync): contradicting opponent play -> infer the fewest missed
  plays of known hand cards that make the history consistent for a fresh DerivedD1, rewrite history, set `resynced`;
  caller restarts the player (hooks: LiveSession._poll 3 lines + ctx stored; PercPlayer.act; real_replay arms '-rs').
  Tests: 15 integration + 23 test_live = 38 pass (incl. fair-information invariance with resync).
- 06:38Z killed old K4CW run (PID 4062792, mine) after 22 matches (provisional cfg, no resync) -> kept as reference.
- 06:43Z it5s2 replay with all arms (resync, both configs) on 01 -> JOB/replay-fast3, PIDs in /tmp/fast3_pids.txt
  (1860929-1860944).
- 06:48Z K4CW-w200-t4 final run on 05 (cores 2-5) PID 1920866 -> JOB/replay-k4cw-rs; arms ref,reseed,truth,births-rs,
  fused-rs,fused-prov-rs,fused-hud-rs. Resumable (rerun same command).
- 07:00Z replay-fast3 (all arms) showed resync reach .648 -> .770 but ~1.5k decision errors in -rs arms: BUG, the
  rebuilt mirror lacked the resynced play, so a duplicate detection right after was accepted -> inconsistent history
  -> restarted pollers raised. Fixed (mirror.accept(X)) + test. Also harness: every arm now decides on the FIRST frame
  of the poll window (LiveSession / T1 reference semantics); before, non-HUD arms used the window's last frame.
  replay-fast3 and replay-k4cw-rs-bug are superseded (kept).
- 07:08Z FINAL runs: K4CW-w200-t4 on 05 PID 4153258 -> JOB/replay-k4cw-rs (7 arms); it5s2 on 01 -> JOB/replay-fast4
  (14 arms), PIDs /tmp/fast4_pids.txt (1976773-1976788). Both resumable.
- 07:26Z replay-fast4 DONE (64 matches, 0 crashes, 0 decision errors in every arm). Deployed config decided:
  thr .6 / hold 500 (tied agreement .856 vs .857; 58 vs 104 wrong plays reach the bot) -> events.LIVE_DEFAULT, used by
  LivePerception by default. Resync: reach .594 -> .775 (deployed cfg), .648 -> .807 (even-half cfg).
- 07:28Z K4CW also on 01: 3 shards x 4 threads, --reverse, PIDs 2069604-2069606 -> JOB/replay-k4cw-rs-01 (merge with
  05's dir via `real_replay report DIR1 DIR2`, duplicate episodes dropped).
- 07:29Z empirical-val.json refit on all 64 with LIVE_DEFAULT (bot/live/empirical-val.json, compact JSON);
  headline_wall smoke of PERC-emp / PERC-emp-both on 01: 2 full games, 0 errors (JOB/hw-emp-smoke).
- RESULTS.md written except the K4CW table (K4CW_TABLE placeholder). Unanchored HUD clock unusable in 32/64 windows.
- NEXT: at ~08:30Z stop the K4CW runs (kill only PIDs 4153258 on 05, 2069604-2069606 on 01), fill the table, rerun
  pytest (both suites), report to LEAD.
- 08:43Z K4CW coverage 64/64 across hosts; stopped my PIDs (05: 4153258; 01: 2069604-2069606). The 01 half is INVALID
  as a K4CW measurement (loaded 01: 80% of decisions fell back to it5s2, reseed 1.0); K4CW reported from 05 only
  (28 matches): reseed .857, truth .862, deployed fused-prov-rs .741, births-rs .725; reach .785 @ P .950.
- 08:50Z final pytest on 05: test_integration (15) + test_live (23) = 38 passed. LivePerception with LIVE_DEFAULT
  smoke on 01 (320 real val frames, 6 events, OK). RESULTS.md complete.

## State: DONE (exploration tier). Nothing of mine is running on 01 or 05. Nothing committed (LEAD commits;
run clasher-secret-scan on the staged diff - not on 05's PATH; my pattern grep was clean).
Open / next: HEADLINE win-rate runs (commands in RESULTS (b)); K4CW on the remaining 36 matches on a QUIET host if
wanted; Royal Ghost labels; spell-event recall (.57) is now the largest remaining opponent-play gap.
