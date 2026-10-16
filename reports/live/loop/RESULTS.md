# LIVE loop: first bot-played battles in the official client (exploration tier)

Owner `live-loop-owner-r1` (parent: LIVE LEAD). Mac mini, BlueStacks Air 5.21.790 (Play Store install, user `sam`'s
session), official Clash Royale, throwaway account **bigdiddle**. Code: `live/loop/`. Log: `PROGRESS.md`.
Recordings, video and screenshots stay out of git: Mac `~/clasher-live/loop/{runs,recordings}`, 05
`/mpac/sdicks02/scratch/live-loop/{runs,rec,shots}`.

## TL;DR

- **The bot plays ranked ladder battles end to end in the official client:** capture → perception → LiveSession(LivePlayer
  `LIVE-K4L-R-gs-rw-fc-w200-t4-p4`, RL r5 v10 fast tier/fallback) → ADB taps. **40 battles: 29 wins, 11 losses, 0 → 716 trophies (Arena 2 Bone Pit from 300). Two of the losses were driver
  incidents (s2-m02, s4-m01: dim screen broke the readers / driver stopped). r1: 11-3; r5e3 (perception r3 ft-r5): 18-7 +
  the s4 incident** (Goblin Stadium; opponents 21-164 trophies, tower levels 1-3). Low-trophy opposition: this shows the loop works,
  not strength.
- **Latency per decision (initial r1 battles):** capture 2 ms, canvas 1.6 ms, perception 113-117 ms (p50, CPU), LiveSession step p95 13-18 ms;
  **frame → tap p50 150-158 ms, p95 165-197 ms**; ADB two-tap ack 13-24 ms. ~8 processed FPS.
- **HUD confirmation is an aggregate diagnostic:** some battles have fewer confirmations than submissions; others have extra confirmations from reanchoring. See per-battle counts below.
- **Perception on official frames (r1 export, 16:9 remap):** own hand 98.3% per slot, next 99.7%; the HUD elixir/clock/
  phase heads fail (replaced by a bar reader and the anchored tick); tower HP head misreads (replaced by OCR of the drawn
  numbers); **units ≈ blind** (median 0-1 detections/frame; weak cross-identity responses at real units). Not a pipeline bug
  (renderer frames round-trip through the 16:9 mapping with identical detections) — a domain gap; perception r3 owns it.
- **Overlay** (MJPEG, Mac `http://localhost:8765`): the model's unit heatmap (red opponent / blue ours), its best
  sub-threshold guess per spot with score, accepted units, tower HP as read, hand/next/elixir/tick and each play.

## Battles

| run | result | trophies after | perception | battle s | proc FPS | perc p50 ms | step p95 ms | frame→tap p50 / p95 ms | tap ack p50 ms | plays | HUD-confirmed | step errors | capture restarts |
|---|---|---:|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| live1 | W 3-0 (+31) | 31 | r1 | 58.4 | 8.3 | 113.4 | 12.9 | 154.4 / 187.9 | 15.0 | 7 | 7 | 1 | 0 |
| live2 | W 3-0 (+32) | 63 | r1 | 79.1 | 8.1 | 115.5 | 17.0 | 157.8 / 195.4 | 13.5 | 10 | 11 | 0 | 0 |
| live3 | W 3-0 (+30) | 93 | r1 | 130.4 | 8.0 | 116.8 | 18.0 | 155.7 / 196.7 | 14.5 | 17 | 17 | 0 | 0 |
| live4 | W 3-0 (+31) | 124 | r1 | 43.7 | 8.0 | 114.4 | 16.9 | 156.2 / 185.4 | 23.9 | 7 | 6 | 0 | 1 |
| live5 | W 3-0 (+30) | 154 | r1 | 144.6 | 8.1 | 115.4 | 16.6 | 150.3 / 164.7 | 20.9 | 19 | 19 | 0 | 1 |
| live6 | W 3-0 (+30) | 184 | r1 | 55.2 | 7.4 | 115.3 | 18.1 | 153.0 / 191.2 | 21.9 | 7 | 8 | 0 | 1 |
| live7 | **L 2-3 (−8)** | 176 | r1 | 172.5 | 7.3 | 117.6 | 27.2 | 153.9 / 172.8 | 18.0 | 28 | 26 | 0 | 1 |
| live8 | **L 0-1 (−8)** | 168 | r1 | 175.0 | 7.5 | 114.7 | 18.3 | 152.5 / 196.4 | 25.9 | 27 | 27 | 0 | 1 |
| live9 | W 3-0 (+30) | 198 | r1 | 98.3 | 7.5 | 114.8 | 16.7 | 150.3 / 181.7 | 27.2 | 12 | 12 | 0 | 1 |
| live10 | W 3-0 (+30) | 228 | r1 | 141.8 | 7.5 | 114.9 | 17.2 | 149.9 / 162.7 | 25.7 | 20 | 19 | 0 | 1 |
| live11 | W 3-1 (+30) | 258 | r1 | 158.9 | 7.5 | 115.1 | 17.8 | 150.2 / 163.4 | 25.6 | 23 | 24 | 0 | 1 |
| s1-m01 | W 3-0 (+33) | 291 | r1 | 150.3 | 7.0 | 115.2 | 27.0 | 153.5 / 204.3 | 16.3 | 21 | 21 | 0 | 1 |
| s2-m01 | W 3-1 (+30) | 321 | r1 | 96.7 | 7.1 | 114.7 | 19.4 | 151.9 / 198.5 | 15.5 | 12 | 12 | 0 | 1 |
| s2-m02 | **L 2-3 (−14)** | 307 | r1 | — | — | — | — | — | — | — | — | — | — |
| s4-m01 | **L 1-3 (−7)** | 300 | r5e3 (driver stopped) | — | — | — | — | — | — | — | — | — | — |
| s5-m01 | W 3-0 (+30) | 330 | r5e3 | 164.1 | 7.0 | 114.9 | 24.1 | 163.1 / 194.8 | 14.6 | 27 | 28 | 0 | 1 |
| s5-m02 | W 3-0 (+31) | 361 | r5e3 | 149.2 | 7.0 | 114.8 | 19.8 | 153.9 / 195.9 | 15.7 | 23 | 24 | 0 | 2 |
| s6-m01 | W 3-0 (+30) | 391 | r5e3 | 58.1 | 6.9 | 115.2 | 31.6 | 154.4 / 195.5 | 16.7 | 8 | 9 | 0 | 1 |
| s7-m01 | W 3-0 (+30) | 421 | r5e3 | 136.0 | 6.9 | 115.4 | 22.7 | 160.4 / 209.0 | 16.3 | 18 | 17 | 0 | 1 |
| s7-m02 | W 2-0 (+30) | 451 | r5e3 | 175.5 | 6.9 | 115.8 | 25.0 | 160.4 / 217.2 | 15.9 | 26 | 27 | 0 | 2 |
| s7-m03 | **L 0-1 (−15)** | 436 | r5e3 | 175.2 | 6.9 | 115.9 | 26.5 | 161.5 / 182.5 | 15.2 | 28 | 29 | 0 | 3 |
| s7-m04 | W 3-0 (+30) | 466 | r5e3 | 87.8 | 6.9 | 115.2 | 18.3 | 159.0 / 191.6 | 15.5 | 10 | 12 | 0 | 4 |
| s8-m01 | W 3-1 (+30) | 496 | r5e3 | 131.5 | 6.9 | 116.0 | 19.2 | 157.7 / 203.4 | 15.3 | 19 | 18 | 0 | 1 |
| s8-m02 | **L 0-3 (−14)** | 482 | r5e3 | 47.2 | 6.9 | 115.2 | 34.6 | 160.1 / 213.1 | 14.3 | 8 | 7 | 0 | 2 |
| s8-m03 | W 3-0 (+30) | 512 | r5e3 | 135.7 | 6.9 | 115.6 | 19.8 | 155.2 / 162.7 | 14.8 | 20 | 20 | 0 | 3 |
| s8-m04 | **L 0-1 (−14)** | 498 | r5e3 | 197.1 | 6.8 | 115.8 | 32.7 | 158.3 / 168.8 | 14.8 | 30 | 29 | 0 | 4 |
| s9b-m01 | **L 1-3 (−14)** | 484 | r5e3 | 167.6 | 6.9 | 115.7 | 33.0 | 163.1 / 207.5 | 14.5 | 25 | 26 | 0 | 1 |
| s9b-m02 | W 3-0 (+30) | 514 | r5e3 | 115.2 | 6.9 | 115.3 | 21.6 | 157.5 / 162.8 | 15.0 | 13 | 13 | 0 | 2 |
| s9b-m03 | W 1-0 (+30) | 544 | r5e3 | 263.9 | 6.9 | 116.5 | 30.6 | 156.5 / 166.3 | 15.5 | 47 | 48 | 0 | 3 |
| s9b-m04 | **L 2-3 (−14)** | 530 | r5e3 | 189.5 | 6.8 | 116.8 | 26.3 | 163.9 / 187.8 | 14.7 | 29 | 31 | 0 | 4 |
| s10-m03 | W 1-0 (+30) | 560 | r5e3 | 175.5 | 6.9 | 116.3 | 22.0 | 161.0 / 200.3 | 14.2 | 30 | 32 | 0 | 3 |
| s10-m04 | W 2-1 (+30) | 590 | r5e3 | 196.2 | 6.8 | 116.6 | 32.2 | 159.5 / 181.2 | 13.6 | 37 | 43 | 0 | 4 |
| s11-m01 | W 1-0 (+30) | 620 | r5e3 | 175.4 | 6.9 | 115.9 | 34.3 | 160.5 / 204.8 | 15.5 | 32 | 40 | 0 | 1 |
| s11-m02 | W 2-1 (+34) | 654 | r5e3 | 175.1 | 6.9 | 115.5 | 31.0 | 156.3 / 162.9 | 14.7 | 30 | 36 | 0 | 2 |
| s11-m03 | W 1-0 (+30) | 684 | r5e3 | 175.5 | 6.8 | 116.1 | 35.4 | 166.4 / 187.2 | 14.7 | 32 | 37 | 0 | 3 |
| s11-m04 | W 2-1 (+30) | 714 | r5e3 | 175.1 | 6.8 | 115.6 | 33.3 | 170.3 / 216.0 | 15.6 | 32 | 39 | 0 | 4 |
| s12-m01 | **L 1-2 (−29)** | 685 | r5e3 | 175.3 | 6.8 | 115.7 | 33.0 | 165.1 / 221.0 | 16.1 | 34 | 37 | 0 | 1 |
| s12-m02 | W 2-1 (+30) | 715 | r5e3 | 175.5 | 6.8 | 116.4 | 33.0 | 159.2 / 167.1 | 15.2 | 33 | 38 | 0 | 2 |
| s12-m03 | W 1-0 (+30) | 745 | r5e3 | 175.7 | 6.3 | 121.0 | 33.4 | 167.6 / 220.6 | 17.5 | 30 | 34 | 0 | 3 |
| s12-m04 | **L 0-3 (−29)** | 716 | r5e3 | 158.6 | 6.7 | 116.4 | 22.9 | 160.6 / 169.8 | 16.7 | 26 | 24 | 0 | 4 |

s2-m02 / s4-m01: the BlueStacks output dimmed mid-battle (white level ~180, cause unknown); the elixir/tower readers
failed (elixir 0, princesses 'dead') and the bot tried past-bridge deploys; fixed by brightness normalization, a frame
health pause and slow tower death (60 healthy frames). s5+: interim/final r5e3 perception. s7+: --autonav (result OK,
trophy-road OK, home Battle; unknown screens never tapped). s7/s8 crowns and trophy counts verified from Battle Log bl3-sol; s7-m01 crowns from final video. s8-m04 was a real loss: no unhealthy frames, no elixir=0 or falsely dead princess reads, 30 plays / 29 HUD-confirmed, no step errors. Capture restarts in multi-match sessions are cumulative per driver. s1/s2 = session driver (`--matches 3`, one driver for consecutive battles; s1-m01+ Bone Pit sand arena, cards
upgraded by Sam: Archers L5, Knight L3, ... ). s1-m01: the tower OCR read bright Bone Pit tower stones as king HP
'3'/'31' and the bot threw Fireball + Arrows at a full-HP king (Sam); fixed before s2 (template-distance gate, a non-digit
in the number row voids the reading). Perception: r1 = `live-perception-20261014/export-final` (frame.pt sha256 20f77a71…, unit threshold 0.5); from
now on the driver logs the export path and frame.pt sha256 in each run's `events.jsonl`. Battle s = first to last processed battle frame (3-crown wins end early). Generated by `live/loop/report_run.py`.
Version notes: live1 had no elixir floor (its one step error disabled the fast tier for the last 11 s); live1-2 used
perception's tower-HP head (never spelled a 24-HP king — Sam); live3+ tower OCR; live4+ arena-bg grab (its second SCK
stream causes the one capture restart, < 1 s); live6+ model-view overlay. After live8: digit split for touching glyphs (Sam: an undamaged tower showed 840, the bot
kept 1232 — '84' merged into one component and only '0' was read) and confirmation on actual readings.

## Pipeline

| stage | how | file |
|---|---|---|
| capture | ScreenCaptureKit window stream (SCK sees sam's session from ssh; CG window list / CGEvents reach the console session instead), viewport (0,32,510,908) pt → 720×1280 BGRA, latest-frame reader thread, restart on SCK errors | `mac/bsgrab.swift`, `frames.py` |
| canvas | 16:9 official → 540×1140 renderer canvas: arena = uniform scale 0.903 + offset (5 tower template matches, residual < 0.5 px), HUD box by box | `canvas.py` |
| perception | `LivePerception` r1 export, unit threshold 0.5 | `live/perception/infer.py` |
| HUD overrides | elixir = pink bar extent `(x_max−290)/74.8`; clock/phase from tick anchored at battle-HUD appearance; elixir floored at pending reservations | `drive.py` |
| towers | digit OCR of the on-tower HP numbers (28 labelled glyph centroids), max HP from tower level (repo tower_scaling growth), 3/8-frame confirmation | `towers.py`, `digits.npz` |
| bot | `LiveSession` + `make_live_player('LIVE-K4L-R-gs-rw-fc-w200-t4-p4')`, `CLASHER_LIVE_FAST=student:…/rl5-v10/policy-00010.pt@0.5375` (sha e188e2ae…), pin set mac-r1-total | `drive.py`, Mac `loop/run.sh` |
| input | persistent `adb shell` (BlueStacks' own ADB, our server :5047): `input tap card; input tap target` (guest only, cannot reach Mac apps); targets validated (card row / arena box) | `drive.py` |
| start/end | battle HUD (elixir drop) on 3 frames → `ClockTracker.anchor(0, ts)`; HUD gone 3 s → end | `drive.py` |

## Open

1. **Units (perception r3).** The bot plays nearly blind to troops; the overlay shows it live.
2. Navigation between battles is manual (OK / chest / trophy road / Battle via ADB taps, screenshot-checked).
3. Sol should-fixes #4-#10 (record.py signals/deadlines, monotonic timestamps, mac.sh quoting/token) not yet applied;
   bsclick (#1/#2) unused (input is ADB).
4. Starter deck, card levels 1-4, tower levels 1-3: out of the engines' level-11 distribution (labelled OOD).

From s10-m03: Sam applied Valkyrie, Archers, Minions, Skeletons, Fireball, Giant, MiniPekka, Musketeer; own towers level 5 (3096 king / 1890 princess), replacing the earlier level-2 towers. Both real s10 session configs record the correct deck and no out-of-scope cards. s10 control events: 1 paused_by_user (file, in excluded m01) and 1 resumed_by_user (before m03 real battle); page pause while Sam used menus was observed and untouched. s10-m01/m02 were false-match menu transitions (4.8/4.46 s), excluded from the table. s10-m04 overlay showed one Not enough Elixir rejection after a claimed Skeletons play; submitted/HUD-confirmed are aggregate counts and can include reanchoring.

s11 played on the grassy Barbarian Bowl arena (automatic background folder still named bone-pit); s12+ uses --arena barbarian-bowl. From s12, launcher3d346510 pins PYTHONHASHSEED=0 to match training token IDs; earlier live processes did not have this launcher pin.

s12-m02 has a confirmed card/slot desync: n864/tick2111.5 submitted Musketeer in slot3 while the same-frame HUD read MiniPekka in slot3 (.774) and Musketeer next (.963); game deployed MiniPekka. Opus loop owner investigating; keep laddering per LIVE LEAD. s12-m03 had transient performance drift: last60s FPS5.76/perception p95~170ms; s12-m04 recovered to6.89FPS/perception p95~120ms. No step errors or unhealthy battle frames during these sessions.

Battle Log bl4-sol corrects s9b-m04 crowns to 2–3 (trophies unchanged); the earlier final video frame showed the red three-crown animation before the full result. s13-m01 is a driver incident pending Battle Log result: disk guard stopped below6GiB after a file pause; no completed result row yet.
