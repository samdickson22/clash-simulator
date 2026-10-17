# LIVE DISPLAY owner: PROGRESS (display-r1)

Owner: LIVE DISPLAY (Opus), reporting to LIVE LEAD. Display only; never drive.py, perception, timing, or emulator input.
Scratch on 05: /mpac/sdicks02/scratch/display-r1/ (src/, mac-snap/ = Mac originals, mac-new/ = staged edits, test/, measure/).

## Design (r1, CURRENT = r1b clean video + browser overlay; LIVE LEAD decision 03:1xZ)
- display/bin/dispgrab (own copy of bsgrab.swift: NV12 from SCK, no 900 s cap, constant-rate re-emit of newest frame,
  10 s stats with last_capture_age) | ffmpeg h264_videotoolbox CBR -> rtsp desktop (native 1044x1856, 8 Mbit/s) +
  phone (540x960, 1.5 Mbit/s) -> MediaMTX (WHEP default, LL-HLS fallback). No Python in the pixel path.
- display/display_feed.py (supervised by video_supervisor.py instead of the old ffmpeg-from-:8766): follows driver logs
  -> display/state.json 10 Hz; owns the pipeline; (re)starts it ONLY when the driver is not in a battle (-3805 risk:
  drive.py notes a 2nd SCK client correlated with capture interruptions). Labels: units_bot (translator) preferred,
  else raw detector class (units_yolo), 'class->card' when they differ.
- overlay_server.py (patched; both code trees): /tv (display/tv.html), /display/overlay.js, /display.json, SSE
  /display/events, POST /display/clientstats -> display/client-stats.jsonl (real-viewer WebRTC stats); main page gets
  the canvas overlay + Overlay toggle + Fullscreen (native rendition).
- /tv: auto layout (portrait screen = edge-to-edge video; landscape = video + side panel), ?rotate=90|270, ?overlay=0,
  Fullscreen button, controls auto-hide, double-buffered reconnect (last frame held), JPEG fallback when HD is down.
- Babysitter restart command: ssh macmini-fleet '~/clasher-live/loop/video_up.sh start; echo __RC=$?' (idempotent).

## Old design notes (r1a, superseded)
- display_compose.py (Mac: ~/clasher-live/loop/display/) runs its own read-only bsgrab stream at native pixels
  (game rect from `bsgrab info`: 0,32,522,928 pt x2 = 1044x1856), 30 FPS, constant-rate ticker.
- Overlay comes from the driver's line-buffered logs (newest runs/<s>/mNN/ perception/frames/decisions.jsonl); the
  driver's :8766 is never used. No session: live picture + "NO SESSION RUNNING: <status.txt>"; not in battle:
  "BETWEEN BATTLES"; capture child down > 6 s: placeholder card.
- I420 -> ffmpeg h264_videotoolbox -> rtsp 127.0.0.1:8554/{desktop 1044x1856 ~8 Mbit/s, phone 540x960 ~1.2 Mbit/s}
  -> MediaMTX (unchanged paths, so the :8767/:8765 pages keep working).
- video_supervisor.py runs mediamtx + compose (instead of ffmpeg-from-:8766). Extra compose args: display/args.json.
- state.json (2 Hz) in display/ for the TV panel (deliverable 3).

## Baseline bot perf (old pipeline; measure/botperf.py on copied logs)
| battle | fps | decision p95 ms | cap_ms p50/p95 |
|---|---|---|---|
| s61/m01 | 9.861 | 47.35 | 2.37/4.13 |
| s61/m02 | 9.894 | 48.52 | 2.38/7.17 |
| s61/m03 | 9.725 | 41.56 | 2.21/6.89 |
| s61/m04 | 9.739 | 44.99 | 2.26/11.08 |
| s62/m01 | 9.883 | 49.52 | 1.70/3.26 |

## SHA256 (computed)
- staged display_compose.py: 505ab6c758a0b8586739dcf273d530830ca333a264cb8896b11f9689db15b414
- Mac video_supervisor.py original: 395acd8de284a950e383c1435a678362f466b9dbe3f12bca5f6e41d44710dad9  -> staged: 6ec7ceae033ad712aa2eecb4e1429b885ecafe19034f81a403cb666cce8666cb
- Mac video/mediamtx.yml original: da8014476f4c265b0db67f6f3039856c511c07fea7b3ff09f21fb2bdbcd1ef01  -> staged: ff64788f14e58a104ab76af8c23e0e356a810b9d547dca49ff3d1bccf4b3370d

## Log (UTC)
- 2026-10-17T03:05:13Z started; read stack; local replay test 30.0 FPS 1044x1856 OK; Sol code review + Sol image check launched.
- 2026-10-17T03:33:50Z r1b built; e2e on 05 (fake capture -> real ffmpeg/libx264 -> mediamtx -> patched overlay_server -> Chrome for
  Testing 155): WebRTC native 1044x1856 30 fps, 0-13 dropped/2000, jb ~8-15 ms; all layouts checked by Sol (r2 image).
  Sol code review r1 (compose) + r2 (r1b) fixed; r3 delta pending. dispgrab compiled on Mac (no warnings):
  bin/dispgrab.new 495a00da1bba8b7b692e38cc092391afddaec08510fecb3a489ec03f056acfe3. Staged in display/ (not running).
- Before-baseline (old pipeline) s63/m01-07 + s64/m01-02: fps 9.72-9.92, p95 41.5-47.7 ms, cap_ms p50 1.6-1.8.
  Mac 03:3xZ (no driver): swap 0, memory free 72%, PhysMem 21G used / 2.1G unused.
- Tailscale: macbook-air-914 DIRECT (IPv6, Spectrum) vs mini (AT&T): no LAN URL; tailscale ping 32 ms.
- Deploy plan (ladder paused 03:35Z-<=05:45Z): backups *.bak-pre-display-r1 (video_supervisor.py 395acd8d...,
  video/mediamtx.yml da801447..., overlay_server.py 420f2f89... both trees); install; video_up.sh stop/start;
  video_page_restart.py. Rollback: restore the three .bak-pre-display-r1 files, video_up.sh stop/start, page restart.
- 2026-10-17T03:57:10Z DEPLOYED (LIVE LEAD authorised during the ladder pause; no driver). Mac sha256 (computed now):
    98aa74a46fa581637d2fc4b2cae1eba62312bc00885c862483a8e33dd96759e5  video_supervisor.py
    ff64788f14e58a104ab76af8c23e0e356a810b9d547dca49ff3d1bccf4b3370d  video/mediamtx.yml
    30989c5ae9638d21b3f64032344ee108c5d96c4479b9e114deb9849402983d48  code/15117b86b-w1/live/loop/overlay_server.py
    30989c5ae9638d21b3f64032344ee108c5d96c4479b9e114deb9849402983d48  code/fullpool-r1/live/loop/overlay_server.py
    81bf753651aa558783e1f4a366559351f46dabe82893901319659aea1800f6a7  display/bin/dispgrab
    a140cb92bc5a198c8c517482f914a7321905648b24784d23abd603746f43fc7e  display/src/dispgrab-v2.swift
    142aabed4e60c4310bbdda64f8dccae7ebacf2693d24709c6e15d6b3eee5ae7f  display/display_feed.py
    159c1a9afeb36040cc77e376c1bac3f78bc8f7fd17f4dae79d5f082f3304d6e4  display/tv.html
    c1fa89ab4e93dd2ffbe5e4fdd38815e4981c6805c4481932a1a3a8257fb47124  display/overlay.js
    395acd8de284a950e383c1435a678362f466b9dbe3f12bca5f6e41d44710dad9  video_supervisor.py.bak-pre-display-r1
    da8014476f4c265b0db67f6f3039856c511c07fea7b3ff09f21fb2bdbcd1ef01  video/mediamtx.yml.bak-pre-display-r1
    420f2f893463a661125911728daade60cbd0e93b70dbdaab9be0d3775e55a5c8  code/15117b86b-w1/live/loop/overlay_server.py.bak-pre-display-r1
    420f2f893463a661125911728daade60cbd0e93b70dbdaab9be0d3775e55a5c8  code/fullpool-r1/live/loop/overlay_server.py.bak-pre-display-r1
  First frames 03:40:17Z (dispgrab native 1044x1856 @30.06 fps emitted). -3805 hit my own stream 4x 03:40-03:42Z
  with no driver -> dispgrab restarts SCK in-process now. BlueStacks quit 03:42Z -> status card (30 fps both paths,
  ffprobe 181 pkts/6 s). Sam's Air on /tv 03:47Z: WebRTC 1044x1856 27-30 fps, RTT 31 ms direct, jb ~119 ms,
  0 lost, 1.8% dropped (client-stats.jsonl).
  Modes: display/mode.txt yield (default; legacy :8766 publisher while a driver session is active) | display.
  Gate file display/capture-gate (hold in battle). Sources: grid (stream-source.json nulls) > BlueStacks > card.
  Null's: no emulator process/window visible on the Mac at 03:57Z -> asked LIVE LEAD (visible window or adb screencap OK).
  Sol reviews: r1 compose, r2, r3 (NO-GO, fixed), r4 (NO-GO, fixed), r5 pending.
  ROLLBACK: cd ~/clasher-live/loop; ./video_up.sh stop; cp -p video_supervisor.py.bak-pre-display-r1 video_supervisor.py;
    cp -p video/mediamtx.yml.bak-pre-display-r1 video/mediamtx.yml; for t in 15117b86b-w1 fullpool-r1; do
    f=code/$t/live/loop/overlay_server.py; chmod 644 $f; cp code/$t/live/loop/overlay_server.py.bak-pre-display-r1 $f;
    chmod 444 $f; done; ./video_up.sh start; ~/clasher-live/venv/bin/python -B video_page_restart.py
