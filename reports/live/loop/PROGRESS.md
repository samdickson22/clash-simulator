# LIVE loop: progress (exploration tier)

Owner: `live-loop-owner-r1` (parent: LIVE LEAD), working on 127x05 in `/mpac/sdicks02/repos/clasher-live` (worktree `live/lead`).
Nothing is committed here; the parent commits. Mac writes go only to `~/clasher-live/loop/`. Images and video are never committed;
the 05 copies are in `/mpac/sdicks02/scratch/live-loop/`.

## Resume here

1. Read the log below (newest last).
2. Review gate: `live/loop/mac/{bswin,bsgrab,bsclick}.swift`, `live/loop/mac/mac.sh`, `live/loop/{frames,record}.py` are
   **waiting for the parent's GO** (Sol review). Nothing new has been pushed to or run on the Mac.
3. After GO, in order: `live/loop/mac/mac.sh push`; `mac.sh build --check` (typecheck), then `mac.sh build`;
   `bsgrab info`; `bsclick where` probes (no events); a 10 s `record.py` FPS/latency run; the first single tap.

## Files

| path | runs on | what |
|---|---|---|
| `live/loop/mac/bswin.swift` | Mac | shared: find the BlueStacks window (largest on-screen layer-0 window owned by "BlueStacks"), front-most window under a point |
| `live/loop/mac/bsgrab.swift` | Mac | ScreenCaptureKit capture of the BlueStacks window only: `info`, `stream --crop --size --fps --seconds --frames` → BSF1 frames on stdout. Self-terminating (≤ 900 s) |
| `live/loop/mac/bsclick.swift` | Mac | CGEvent tap/drag in viewport-fraction coordinates; re-reads the window each command; refuses unless the front-most window under every touched point is BlueStacks'. `where` = no event. `serve` = stdin line protocol. Fixed timings |
| `live/loop/mac/mac.sh` | 05 | push (sha256-verified) / build / rexec / shot / fetch, `__RC`-token checked |
| `live/loop/frames.py` | Mac | BSF1 reader + `Grabber` (child process, TERM→KILL close) |
| `live/loop/record.py` | Mac | recorder: JPEG + frames.jsonl + summary.json under `~/clasher-live/loop/recordings/<name>/`; stops at --seconds ≤ 900, free < 6 GiB, > 3 GB, or stream end |
| `live/loop/tests/` | 05 | `run_tests.sh` (16 checks) with `fake_bsgrab.py` |

## Log

- 2026-10-15T21:57Z Read PLAN/PROGRESS/MAC-BENCH/BlueStacks README and the canvas layout (`clasher.vision.l1`: 540×1140 canvas,
  arena (0,200,540,1000), HUD boxes). Read-only Mac probes: BlueStacks PID 65579 (sam), free 15 GiB, swiftc 6.4 / SDK 27.0,
  screencapture OK. Home screen: "You", No Clan, Training Progress 1/3, gold 113, gems 100. BlueStacks window ≈ 360×610 pt at
  (163,30) pt, game viewport 16:9.
- Wrote the review set above. 05 dry run of record.py vs the fake: **16/16 pass** (rate, latency, JPEG, bad header,
  truncated frame, seq gap, existing dir, path escape, disk guard, byte cap). The Swift files are not typechecked yet (needs the Mac).
- Parent pre-approval: BlueStacks Settings → Display 19:9 via the click helper (account-persistence check before/after).
- Reference (read-only, later): CRBot @ a01f654 and Jaso1024 RTS-RL @ aec65d7 slot maps / menu flows.
- 2026-10-15T22:02Z **Fast tier / cutoff default → RL r5 v10** (parent). Copied 04 `live-rl5-perc-ours/ckpt/policy-00010.pt` (+ `.calibration.json`,
  threshold 0.5375) via 05 `scratch/live-loop/rl5/` to Mac `~/clasher-live/students-live/rl5-v10/`; sha256 on the Mac
  **e188e2aeb9a6828ffbef237aa327e495eb39ca5f8322ae18aa70c63cb81bba19** (= pin), calibration 4a07033d….
  - Live spec: `CLASHER_LIVE_FAST=student:/Users/sam/clasher-live/students-live/rl5-v10/policy-00010.pt@0.5375`; the tier name stays
    `LIVE-K4L-R-gs-rw-fc-w200-t4-p4`.
  - Rollback (one line): `CLASHER_LIVE_FAST=student:/Users/sam/clasher-live/clasher-live-macbench/students/it5s2-step001200.pt@0.5375`.
  - TODO before the first bot battle: smoke 1 decision on the Mac with the new spec (in the loop driver's preflight).
- 22:32Z **GO (Sam/coordinator): live test on the Mac.** Built bsgrab/bsclick (swiftc 6.4).
  - **CG window list + CGEvents from ssh reach the CONSOLE session (simonfarshid, locked), not sam's Screen Sharing session.** Three
    mouse-moves (no clicks) went there; sam's cursor did not move. bsclick's guard refused (no BlueStacks in that list). ScreenCaptureKit
    from ssh DOES see sam's session (display 1920x1080 pt, BlueStacks window 6728 at 244,50 542x940, scale 2) -> bsgrab uses SCK lookup.
  - **Input = option A, BlueStacks' own ADB** (LIVE LEAD OK): our adb server :5047 → 127.0.0.1:5555, guest 1080x1920 @320, touch
    device "BlueStacks Virtual Touch". `input tap` 19 ms in guest, 69 ms host round trip (new adb process); persistent shell
    two-tap ack 12-16 ms. Guest-only, so no stray clicks into Mac apps by construction.
  - **Capture:** full window 1084x1880 @10: 9.9 FPS, display→python p50/p95 2.7/4.3 ms; @30: 28.8 FPS, 2.5/3.6 ms; 0 seq gaps.
    Viewport at 16:9 = (0,32,510,908) pt in the window. SCK error -3805 (connection interrupted) once after 84 s → driver restarts bsgrab.
  - **Smoke RL r5 v10** on the Mac (mac_bench, 6 decisions/tier, 0 errors): fast p50/p95 4.1/21 ms; K4L 43/71 ms, 0 defaults.
  - Recordings (Mac `~/clasher-live/loop/recordings/`, 05 `scratch/live-loop/rec/`): `tc2-r1` (TC battle 2 + 3, Sam played the
    tutorial; won 3 crowns), `ladder1-r1` (first ladder match, bot idle, lost 0-3, 84 s until the SCK error).
  - Account after tutorial: **bigdiddle**, 0 trophies, Goblin Stadium. Deck: Knight, Archers, Minions, Arrows, Fireball, Giant, MiniPekka,
    Musketeer (all C56; levels 1-4).
  - **Domain gap (r1 export, 16:9 remap `live/loop/canvas.py`, ladder1 598 battle frames):** hand **98.3%** per slot (584-590/598),
    next **99.7%**; HUD elixir head WRONG (5.3 vs truth 10) → bar-fill reader (`(x_max-290)/74.8`, exact vs digit on spot checks);
    clock/phase heads wrong → from the anchored tick; **units ≈ 0 recall** (a Giant attacking our tower never detected; grass arena vs
    the renderer's arena); towers: opponent's right, our right-princess loss right, our damaged king flickers to "dead".
  - Arena remap: official540 = 0.9030*canvas + (25.74,-137.74) (5 tower template matches, resid < 0.5 px).
  - Driver `live/loop/drive.py` (+ Mac `~/clasher-live/loop/run.sh`, code tree `loop/code/15117b86b-w1` = this worktree + the
    bundle's audited reports/ subset): 05 replay dry run OK; Mac replay dry run OK (perception 114 ms p50, step p95 7 ms, 8 FPS).
  - **live1 = FIRST BOT-PLAYED LADDER BATTLE** started (match_start detected, K4L search plays, ADB acks 12-16 ms).
- 22:54Z **Live ladder results (K4L + RL r5 v10 fallback, ADB taps, Goblin Stadium, starter deck L1-4):**
  live1 W 3-0 (+31), live2 W 3-0 (+32), live3 W 3-0 (+30), live4 W 3-0 (+31); trophies 0 → 124. Opponents 21-113 trophies.
  - Per run (report_run.py): ~8 processed FPS; perception 114-117 ms p50; step p95 13-18 ms; frame→tap p50 154-158 ms; tap ack
    12-31 ms; 7/10/17/7 plays, all from search; all plays confirmed by the HUD except one in live4 (6/7).
  - Fixes on the way: elixir floor at pending reservations (live1 crash 'reservations exceed physical elixir' broke the fast-tier
    250 ms gate); **tower HP from the drawn numbers** (`live/loop/towers.py`, digit centroids `digits.npz`, max HP from the
    tower level via the tower_scaling formula) — Sam: the bot never spelled a 24-HP king because perception read it ~0.8-1.0;
    confirmation rule (3 equal reads, 8 for rises/halvings) after a latched misread in live3.
  - **Overlay** (`live/loop/overlay.py`): MJPEG at http://localhost:8765 on the Mac (units/towers/hand/elixir/plays).
  - SCK: a second SCK client (arena-bg grab, screenshots) can interrupt the main stream (-3805); the driver restarts in < 1 s.
  - Round 3 answers: canvas round trip of renderer frames reproduces units exactly → the zero-unit problem is domain, not pipeline.
    Arena bgs: 05 `scratch/live-loop/arena-bgs/goblin-stadium/` (4 at 720x1280 + 3 per battle at 1020x1816 from live4 on).
- 23:13Z live5 W 3-0 (154), live6 W 3-0 (184), **live7 L 2-3 (176), live8 L 0-1 (168)**. Overlay now shows the raw model view
  (unit heatmap + best sub-threshold candidate per spot; Sam: "no quick fixes, I want to see what the model sees").
  Tower OCR fix after Sam's screenshot (840 shown, 1232 read while undamaged): touching digits split at 0.72 h; confirmation
  on the previous non-empty reading. RESULTS.md written. Between battles: scratch `next.sh` (waits for the driver's
  "loaded" before tapping Battle; live8 anchored ~6 s late because Battle was tapped during the 7.6 s load).
- 2026-10-16T00:34Z **State for the successor: see HANDOFF.md** (per-battle routine, model swaps, rules).
  - s1-m01 W (Bone Pit; tower OCR read bright tower stones as king HP '3'/'31' → spells at a full-HP king; fixed:
    template-distance gate). s2-m01 W. s2-m02 L + s4-m01 L: BlueStacks output dimmed (~01:00Z, white ~180) → readers
    failed → fixed (normalize, frame-health pause, 60-frame tower death). Perception swapped to r5e3 (ft-r5 final,
    frame 81697f5b…) at s4/s5; replay on s2-m01 units/frame 1.53 → 2.30. s5-m01 W, s5-m02 W, s6-m01 W, s7-m01/m02 W → 451.
  - New: session driver (--matches), --autonav (result/road/home only; nav_stuck event on unknown screens), per-battle
    perception.jsonl + session-config.json (s6+), overlay model view (heatmap + candidates, body names), battlelog.py
    inventory (18 battles back-filled; non-C56 seen: SpearGoblins, GoblinCage, Tombstone, Bomber), pocket.py
    (r1 29/100 pocket plays, r5e3 7/29), reconstruct.py (perception for pre-s6 battles, running on 05).
