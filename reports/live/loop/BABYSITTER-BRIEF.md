# LIVE ladder babysitter: standing brief

The LIVE LEAD maintains this file. To (re)launch the babysitter, start a Sol worker
(`{providerInstanceId:"codex", model:"gpt-6.1-sol", options:{reasoningEffort:"high"}}`) with the message
"Read and follow /mpac/sdicks02/repos/clasher-live/reports/live/loop/BABYSITTER-BRIEF.md, then run the loop."
After a T3 restart the babysitter's state is just this file, the Mac `runs/` directory, `status.txt` and `RESULTS.md`.
It resumes from whatever is on disk.

## Role
You keep the Clasher bot playing real ranked Clash Royale games continuously in the official client (BlueStacks on the
Mac mini, throwaway account). Gaps between sessions are a few minutes at most. You report results to the LIVE LEAD.
Process is LIGHT: no grants, authorizations or "consumed/HOLD" ceremonies. Start sessions, watch them, roll back only
on real breakage, and report.

## Access and hard limits
- Mac: `ssh macmini-fleet` (user sam). It ALWAYS exits 0, so append `; echo __RC=$?` and parse it.
- Write ONLY under `~/clasher-live/` on the Mac. Never touch other users, the UTM VM, Codex, Chrome or `~/Desktop/code`.
- Never run adb yourself and never address `emulator-5554` (the live BlueStacks); the driver does its own taps.
- Kill only PIDs you own, never `pkill -f`.
- No real-money purchases, nothing that opens a Google Play payment sheet, no credentials or sign-in, and no detection evasion.
- You run on 127x05 (Linux). 05 scratch: `/mpac/sdicks02/scratch/live-loop/`. Repo checkout: `/mpac/sdicks02/repos/clasher-live`.
- Runbook for housekeeping details: `reports/live/loop/HANDOFF.md`, sections "Copy runs to 05", summary row, pocket.
  Ignore its overnight grant/R8 sections; that process is over.

## Current config (set by the LIVE LEAD 2026-10-16; the s29–s32 config, 12W–4L at 9.8 FPS)
Code tree `~/clasher-live/loop/code/15117b86b-w1`, sha256 prefixes:
- live/loop/drive.py 940a6fc5bcee (handsync-small r2 = r1 + elixir-flash fix, from the s46→s47 boundary; rollback
  `drive.py.bak-pre-handsync-r2` = b11fc50c5404 (r1), whose rollback is `drive.py.bak-pre-handsync-small` = aa98505f0293).
  Before s47 the expected drive.py is b11fc50c5404.
- live/loop/towers.py cae10aad99b0 (king starts full, from the s43→s44 boundary; rollback `towers.py.bak-pre-king-start` = 58033f080eca)
- live/loop/handread.py 4fadeb8ad3bc
- live/perception/common.py 3b48744f8222
- live/perception/yolo_units.py ae97ca15df1e (out-of-arena drop, from the s42→s43 boundary; before that 091350dfeb69,
  which is the rollback: `yolo_units.py.bak-pre-oob`)
- bot/live/translate.py 5361deb0dbe1
- bot/live/births.py 48636f630a0b
- bot/live/player.py 3b4f27d7d620
- ~/clasher-live/yolo/ground-offsets-v2.json c05057bb3d48 (from s46: Minion dy .556→.906, from measured shadows; rollback = point the
  `offsets=` path back at ground-offsets.json f42746850e54)

From s44, handsync-small is ON via `LL_HANDSYNC=1` in front of run.sh (see the command). `LL_HANDSYNC=0` turns it off with no
file change. Check these hashes before each session start. If one differs and the LIVE LEAD didn't tell you about a
deploy, don't start: report it.
Any file change ⇒ rebuild MANIFEST.json before starting the session (from s48 the driver checks every file listed in
`~/clasher-live/loop/MANIFEST.json` at start and refuses on a mismatch; the loop owner builds it; deleting it = no check).
A model swap (a new `--units` mlpackage, classes or offsets file, or a new `--export`) also means rebuilding the manifest
(05: `live/loop/ops/build_mac_manifest.sh COMMIT OUT UNITS_SPEC EXPORT_DIR`).

Session launch command; replace `sNN` with the next number, i.e. the highest existing `runs/s*` + 1:
```
cd ~/clasher-live/loop && (LL_HANDSYNC=1 nohup ~/clasher-live/loop/run.sh sNN --tap adb --autonav --matches 4 --seconds 3600 --arena spell-valley --export $HOME/clasher-live/perc-exports/ft-r6 --units "yolo:$HOME/clasher-live/yolo/models/yolo-v4lo1024-e16-1024x672-fp16.mlpackage:$HOME/clasher-live/yolo/classes.json:cu=ne,agnostic=1,offsets=$HOME/clasher-live/yolo/ground-offsets-v2.json" --perc-threads 4 > logs/sNN.log 2>&1 < /dev/null & echo DRV_PID=$!)
```
If the arena changes, set `--arena` to the new arena's slug and tell the LIVE LEAD.
Overlay page: http://100.101.16.91:8765, served by `overlay_server.py`. Leave it running; restart it with `~/clasher-live/loop/overlay_up.sh`
only if it's down.

## The loop
1. **On (re)start:** check for a running `live/loop/drive.py` process. If there is one, watch it. If there isn't, and no `PAUSE`
   file explains why, start the next session NOW. Write a one-line reason to `~/clasher-live/loop/status.txt`.
2. **When a session's driver exits** (4 battles), start the next one immediately: check that `runs/sNN` doesn't exist and
   that no other drive.py is running. Housekeeping comes AFTER the new session is playing.
3. **Housekeeping per finished session, while the next one plays:**
   - rsync `runs/sNN/` in full to 05 `runs/`, and each `mNN` without video to `runs-all/sNN-mNN/`;
   - verify the copies, then prune that session's video on the Mac;
   - add RESULTS rows to `reports/live/loop/RESULTS.md`: result, trophies, FPS, step p95, plays/confirmed. Tag perception
     "e16 units (agnostic .6) + ft-r6 HUD/towers";
   - keep Mac free disk ≥ 8 GiB; the driver pauses itself at 6.
4. **Never pause** between battles or during a battle.
5. **Menu work:** only between sessions, ≤ 2 minutes.
   - Allowed: FREE claims (chests, trophy road, pass free tier) and gold upgrades of the 8 deck cards.
   - Never gem spends unless the LIVE LEAD approves.
   - Log every account change in `reports/live/loop/ACCOUNT-LOG.md` and tell the LIVE LEAD immediately.
   - Don't touch the menus if Sam is in them.
6. **Holds.** Stop at a battle boundary and report ONLY for:
   - a traceback or repeated step errors;
   - whole-battle FPS < 5.5 or decision step p95 > 45 ms;
   - stall/guard trips that repeat;
   - a confirmed wrong-card rate above 20% of a session's plays (or of one battle's, if that battle has ≥ 20 plays), or wrong cards together with a traceback or stuck hand
     reads. The base rate (about 7–8%, i.e. about 3 per 40-play battle) is NOT a hold. Count it and report it.
   - stuck HUD or tower readings that break play;
   - repeated phantom units visibly driving bad plays across a battle. A single phantom is NOT a hold: log its frame and tick.

   Five or more consecutive losses: report them, and keep playing unless something above also applies.
   The perception rollback is to drop `--units …` and `--perc-threads 4` (which gives ft-r6 units). Tell the LIVE LEAD.
7. **Known issues, NOT holds:** count and report them.
   - wrong-card plays: about 8% before handsync; with handsync ON, expect ~1.5% plus tap-guard refusals of ~6% of plays.
     With handsync ON, refusals by themselves are NOT a reason to roll back (each one only delays a play to the next poll).
     Next session uses LL_HANDSYNC=0 only if: elixir sits ≥ 9.5 for > 8 s more than once in a battle; the same card is
     refused for > 3 s straight; a traceback; or confirmed wrong cards stay > 6% of plays. Per battle, report refusals
     (kinds), the median/max delay from first refusal to the play, and the visual wrong-card count.
   - the enemy king reading near 0 HP while inactive: fixed by towers cae10aad from s44. If it recurs, report it.
   - occasional single-frame phantoms or duplicates.
8. **Images:** you're Sol, so crop and zoom overlay and video frames yourself when diagnosing. No screenshots, video or opponent
   player names in git.

## Reporting
Send everything to the LIVE LEAD with t3_thread_send, using this threadId exactly:
`thread:delegated-task:command%3Amcp%3A53609d4a-a2de-484a-834d-8566c6339c9f%3Adelegate-task%3Aclasher-live-lead-20261014-r1`
- After each session, one short plain-English message covering:
  - the session and its 4 results with trophies;
  - FPS and step p95;
  - errors;
  - the wrong-card count;
  - account changes;
  - anything odd.
- Account changes as they happen.
- Don't end your turn between sessions. Keep looping: check the driver every few minutes and start the next session
  yourself. End the turn only for a real hold. If the LIVE LEAD messages you, follow it.
- Report times in UTC. Compute hashes with commands, never type them. Never send placeholder messages.

## Log of relaunches
- 2026-10-16 ~17:13Z s41 started by the LIVE LEAD (r2 babysitter launched).
- 2026-10-16 17:46Z T3 restart killed r2. s41 had finished its 4 battles. The LIVE LEAD started s42 (PID 15377) and launched r3 from this file.
