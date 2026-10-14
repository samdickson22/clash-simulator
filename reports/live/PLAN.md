# LIVE track plan: first real games in the official client (exploration tier)

The LIVE LEAD wrote this on 2026-10-14, about 22:50Z. The mandate is Sam's (COORDINATOR 2026-10-14 22:43Z): get the best bot playing real
games in the official client on a throwaway account, inside an emulator on the Mac mini. Training Camp comes first,
then ladder. No detection evasion. Screen state only.

## TL;DR

- **The critical blocker is the client, not the bot.** The official Clash Royale client has **never reached its first screen**
  on the Mac.
  - On both stock Android Studio images (Google APIs and Google Play, API 35 arm64) it aborts at startup with
    `frrh.aC: 02`, thrown during its first `System.loadLibrary`.
  - The logcat shows it reading `ro.debuggable`, `ro.secure`, `qemu.hw.mainkeys`, `qemu.sf.lcd_density`, the SELinux
    `enforce` node and `/proc/net/unix` just before it aborts. This is the client's anti-emulator check.
  - Masking those properties or patching the APK would be detection evasion, which is **excluded**. Stock AVDs are a dead end.
- **Shortest legal path:**
  - **Step 0:** get the unmodified client to run on a commercial Apple-silicon emulator with default settings. BlueStacks
    Air is already installed but failed its first boot on 10-04. MuMu Pro is the second option.
  - **Then:** a guest account, Training Camp, and ladder.
  - **Fallback:** if neither emulator runs it, the honest fallback is a physical Android phone on USB to the Mac.
    That needs Sam to widen the authorization, which today says emulator only.
- **The Mac is resource-starved today:**
  - **Disk:** 9.7 GB free. BlueStacks publishes 12 GB.
  - **RAM:** a UTM Windows 11 VM ("Canvasdoc", another project) holds **16 GB of the 24 GB** and has been up for 3 days.
  - Both need Sam (list below).
- **Perception has no accepted accuracy number.** It was trained only on frames from the private-server renderer.
  - v4 legacy T6 validation, not accepted: unit-event recall 2003/2826 = **70.9%**, precision 2003/2523 = **79.4%**.
  - Hand, elixir and tower-HP gates: never measured.
  - Step 2 trains and measures v4 on train/val in parallel with step 0, on one A6000 borrowed from the bot track.
- **The bot needs modest glue, not research:**
  - K4C-r16 takes 0.43 s of CPU per decision on one fleet core and is unbounded. It needs a deadline or thread
    hook, a `Snapshot → PublicView` adapter and Mac native pins.
  - Both engines support only the 56 C56 cards at level 11. Live games with a new account's starter cards are
    out of distribution (section 1.5).

## 1. Inventory

### 1.1 Mac mini, read-only check 2026-10-14 22:45Z

| item | state |
|---|---|
| Hardware | Apple M4 Pro: 12 cores (8 P + 4 E), 24 GB RAM, macOS 27.0, up 29 days |
| Free disk | **9.7 GiB** of 460 (Data volume 98% used). `~/Desktop/code` holds 134 GB, `~/Library/Caches` 5.2 GB, `~/.cache/clasher-native-reference` 13 GB |
| RAM in use | UTM `Canvasdoc Win11` VM (QEMULauncher) **16 GB**, colima/Virtualization 3.5 GB, WindowServer 1.6 GB. memory_pressure reports 38% free; 1.58 M pageouts |
| Android SDK | Only the offline-reference SDK at `~/.cache/clasher-native-reference/android-sdk` (emulator 37.1.11, API 35 `google_apis` arm64). **Off limits for live:** the reference AVD stays separate and never networked |
| AVDs | `clasher_reference_api35` (reference, off limits). `~/.android/avd/medium_phone` is a stub from Aug 5 whose API 36 Play image isn't installed. Official AVDs `clasher_official_api35` and `clasher_official_play_api35` were deleted 10-04 after the crash |
| BlueStacks Air | 5.21.790 installed in /Applications. One instance, `Tiramisu64` (Android 13, arm64). `bst.enable_adb_access="0"`. The 10-04 first boot hung in `StartingKernel` (`launch_start_timeout`) |
| Official APK | None present. The last copy (16.402, versionCode 160402017, Supercell cert `59ea9ded…9357` verified) was installed in the deleted AVDs; the bundle was deleted |
| Account | **None ever created.** No guest, no Supercell ID |
| Running emulators | None. Three idle `adb` fork-servers from the reference SDK (ports 5042–5044); leave them alone |
| Prior clasher trees (do not touch) | `~/Desktop/code/clasher`, `clasher-runtime-v4`, `clasher-mac-e4-tiers-20261011`, `clasher-cleanup`, `~/.cache/clasher-native-reference`, `~/.cache/clasher-live-v4`, `~/.cache/clasher-official` (L3 history) |
| **Live track dir** | **`~/clasher-live/`** (new; doesn't exist yet). Everything live goes there: venv, emulator downloads, recordings, logs |

### 1.2 Perception

Sources: `live-loop/v4/PROGRESS-T6T7.md`, `v4/l1/RESULTS.md`, `src/clasher/vision/l1_v4.py`.

- **Model:** `PerceptionV4`.
  - Inputs: an 832×448 arena crop plus a 64×448 HUD atlas.
  - Body head: identity×owner heatmaps, boxes, HP and HP visibility on a 64×36 grid.
  - HUD head: 5 card distributions, elixir digit and fraction, clock, phase.
  - Temporal head: play events over a 16-frame cache.
  - TorchScript export has parity (0 max-abs difference, shakedown). No CoreML.
  - Speed: A6000 frame+event p50 7.03 ms. No Mac number. v0 on MPS ran at 25 ms/frame.
- **Checkpoints:**
  - T6 epoch 24 `a3860deb…`; T7 final `e5d1acd1…`;
  - a shakedown copy at 127x01 `clasher-v4-training/t6-shake-1`;
  - the formal B chain on 08 stopped at epoch 3/24 (package bug, fix proposed in
    `l1/receipts/b08-r5-epoch04-root-cause-r1/`). **Not needed for live play.**
- **Measured on validation:**
  - v4 legacy T6 validation (64 matches, 53,392 frames): event recall **70.9%**, precision **79.4%**. This is not
    accepted.
  - Own-hand accuracy (gate ≥99.5%), elixir MAE (≤0.15) and tower HP: **never measured**.
  - Older models: v0 detector mAP50 0.532; v2 event recall 88.4%, precision 95.0%, placement 69.8%.
- **Data:** 513 train, 64 val and 64 heldout matches, all from the offline renderer (private-server APK 15.535 content
  at 1080×2280). Caches are on 127x01. **Heldout stays sealed.**
- **Domain gap:** the official client is now ≥16.402, with art, UI and HUD changes, and it will run at whatever
  resolution the emulator gives it. That gap has never been measured, because no official frame has ever been captured.

### 1.3 Capture and input

| path | measured | where |
|---|---|---|
| Emulator gRPC `streamScreenshot`, 360×640 | 49.6 FPS, receipt p95 2.9 ms (launcher only, AVD) | `live-loop/l3/official_loop.py`, `l3/README.md` |
| Reference renderer screenshots | 59.1 FPS median | `v4/T2-RESULTS.md` |
| `adb exec-out screencap` | 0.52 FPS PNG / 1.6 FPS raw. **Unusable** | `l1/RESULTS.md` |
| adb `input tap` (two-tap shell) | mean 44 ms, p95 58 ms (launcher) | `l3/README.md` |
| gRPC `sendTouch` (reference) | two-tap p95 26.9 ms | `v4/T2-RESULTS.md` |
| Mac planner, frame → submit (replay, mock actuator) | p50 186 ms, p95 285 ms, p99 334 ms (n=228) | `v4/mac-native-build48/` |
| Command delay | 26 ± 1 ticks renderer; official 26–27 ± 2 ticks, p95 ≈ 44 (ClashAI-derived, **not ours**) | `reports/research/command-delay-20261008.md` |

On BlueStacks there is no emulator gRPC. Capture options there are `scrcpy` (H.264 mirror, about 30–60 FPS, around
35–70 ms per community numbers) or macOS ScreenCaptureKit on the BlueStacks window. Input goes through adb (`input
tap` / `input swipe`, or `scrcpy` control). Step 0 measures all of this.

Reusable code: `l3/official_loop.py` (adb tap, drag and play, ownership guard), `l3/recording.py` (H.264 + frame
sidecar), `l3/storage_guard.py`, `v4/actuator.py` (pending ledger, verify, one retry), and the `ScreenStates` template
recognizer, which is an interface only with no templates yet.

### 1.4 Bot and decision-latency budget on the Mac

- **K4C-r16 (best; RoyaleSim P1 0.921):**
  - Built by `bot/search/candidates.py:make_candidate_player` (r3a=16, roots=1, samples=16).
  - Needs one checkpoint, R3a `37509a43…`.
  - Plans and rolls out in **our native Rust core** (5 µs clone), even when the game itself is RoyaleSim.
  - **Unbounded and single-threaded:** 41.0 rollouts and **0.429 s CPU per decision** on one fleet core
    (`reports/bot/candidates/RESULTS.md`). There is no deadline or budget hook, so live play needs a small code change
    (a deadline, or rollouts parallelised across threads).
- **it5s2 (fast tier):**
  - ExIt student, one forward pass per decision. Its sibling student D scores RoyaleSim P1 0.820.
  - Checkpoint and sha aren't in git yet; to get from the bot lead.
  - The K4S prereg bar is forward p99 ≤ 20 ms.
- **Reference curve (X4S, fleet, loss vs v1 at a 200 ms deadline):** K4 at 4 threads 18.5%, K4S-200 20.7%, S-200
  (1 core + R3a) 28.2%.
- **Mac timings so far are not evidence.** 67% of the old Mac scored searches had every candidate at −2.0
  (`COORDINATOR.md` ~917), so the 186 ms Mac p50 is void. Search on the Mac has to be re-measured with the fix on.
- **Mac native build:**
  - `engine-rs/build.sh` builds `clasher_core.abi3.so` for aarch64-darwin (build48, 41 s).
  - `bot/players/runtime.py` asserts the **Linux** native sha `44874fd6…`, so the Mac needs its own runtime pins.
  - The runtime root `e4v3-20261010-r1` (592 MB) has to be copied.
- **Adapter gap:** `src/clasher/live/` (Snapshot contract, its own 4-root planner) has **no link** to `bot/players`.
  We need a `Snapshot → Information/PublicView` adapter. The action is `slot*576 + row*18 + col`, with WAIT = 2304.
- **Budget per decision.** The bot polls every 5 ticks from tick 90 and searches on 10-tick multiples (10 ticks ≈
  0.33 s at 30 ticks/s). Commands are lagged 27 ticks, with one outstanding command.

| stage | target | basis |
|---|---|---|
| capture → frame | ≤ 40 ms | scrcpy or ScreenCaptureKit, to measure |
| perception (frame + event) | ≤ 30 ms | v4 takes 7 ms on an A6000; MPS is maybe 3–5× slower |
| state build + elixir/cycle tracking | ≤ 5 ms | |
| decision, K4C-r16 | ≤ 250 ms | 0.43 s on one fleet core. An M4 Pro P-core is faster (to measure, r ≥ 1 expected), and 4 threads give headroom |
| decision, it5s2 | ≤ 20 ms | single forward pass |
| input (adb tap/drag) | ≤ 60 ms | 44/58 ms measured on the launcher |
| **total, K4C-r16** | **≈ 385 ms ≈ 12 ticks** | |

- **Lag recalibration.** The stack adds about 12 ticks to the client's command delay, which is about 26–27 ticks
  (ClashAI-derived). So the planner's lag constant moves from 27 to about 38 ticks, and gets recalibrated from
  measured tap-to-render times.
- **Fallback.** If the search misses its deadline, it5s2 acts.
- **Core plan on 8 P-cores:** the emulator gets 3–4 cores, the search 1–4 threads, and perception runs on the GPU
  (MPS). This fits only **with the Win11 VM stopped** during sessions.

### 1.5 Decks and levels: the second big gap

- **Built for one setting.** The bot was built and measured only on the 5 X4S human decks at **card level 11**:
  - bridge (Hog / IceGolem / Musketeer / Cannon);
  - siege (Xbow / Tesla);
  - beatdown (Giant / Hog / Wizard);
  - bait (GoblinBarrel / Princess);
  - chip (Miner / Rocket / RoyalDelivery).
- **Hard limits in both engines:**
  - Our engine and the native search accept only the **56 C56 cards at level 11**
    (`src/clasher/rl/c56_rollout_planner.py:94`).
  - Ours hard-codes the level-11 king and princess towers, 4824 and 3052 HP (`src/clasher/player.py:31`).
  - RoyaleSim also hard-codes level 11.
  - The opponent belief samples from the human-deck prior; off-catalog decks are untested.
- **A fresh account** has only starter cards at low level, and Training Camp trainers use their own decks.
- **Plan:**
  - First check that every starter card and every trainer card is in C56.
  - Then plan **at level 11 for both sides**. Card stats scale almost uniformly with level, so when both sides are
    at equal level the dynamics are roughly level-invariant. Tower-vs-troop ratios are the main risk.
  - Map each card to C56, and refuse to play a card that isn't in C56.
  - Every live number will be labelled **"K4C-r16, starter deck at account level, out of distribution"** until the
    account can field cards close to an X-deck.
  - Proper level support is a bot-lead item if live results show it matters.

## 2. Shortest path to the first Training Camp game

Each step reports to the coordinator. Steps A and B run in parallel.

**A. Platform (critical path; Mac, light CPU).**
1. **Precondition from Sam:** free disk (≥ 20 GB) and stop or suspend the Win11 VM during live sessions. See the Sam list.
2. **BlueStacks Air retry**, default device profile:
   - Enable its own ADB setting (`bst.enable_adb_access`), a normal user setting.
   - Install the **unmodified** signed client: Play Store if a Google account is available, otherwise the APKMirror
     bundle verified against Supercell cert `59ea9ded…9357`, as on 10-04.
   - Launch it once.
   - **Stop rule:** if the client refuses to start, or shows an emulator or integrity block, stop. Never toggle
     root-hiding, device spoofing or property masking, in BlueStacks or anywhere else.
3. If BlueStacks fails: **MuMu Pro for Mac**. It needs a vendor account and a subscription after the trial, which is a
   Sam item. Same stop rule.
4. If both fail: report that **the official client cannot run legally in an emulator on this Mac**, and propose the
   phone-on-USB alternative to Sam.
5. **Once it runs:**
   - guest account (expected to need no login);
   - play the tutorial by hand-scripted adb taps;
   - capture home, Training Camp, battle and result screens;
   - calibrate the card slots and the 18×32 tile homography;
   - measure capture FPS and tap-to-render latency.

**B. Perception (127x01/04/08 GPU, about 6–10 h).**
1. Exploration-tier fine-tune of v4 from the T6 checkpoint on the **train** split, measured on **val** only:
   own-hand accuracy, elixir MAE, tower-HP MAE, unit detection P/R (identity × owner, within ¼ tile).
2. A deterministic HUD reader on official-client frames as a cross-check: template match for the hand cards and
   elixir bar, digit OCR for tower HP. The HUD is fixed-layout, so this is cheap and robust to the renderer gap.
3. Once official frames exist: label about 200 official Training Camp frames (hand, elixir, towers, units), measure the
   domain gap, and fine-tune if needed. These are our own captures; per the repo rule they stay off git if they show
   account names.

**C. Integration (Mac, replay).**
1. Build the `~/clasher-live` runtime on the Mac: Python 3.12, torch with MPS, the native Rust core build for
   aarch64-darwin (the build48 recipe in `v4/MAC-NATIVE-BUILD48.md`), and the K4C-r16 and it5s2 weights from the bot
   lead.
2. A replay harness feeds recorded **train/val** renderer matches through capture → perception → public state →
   decision → mock input. It reports perception error against ground truth, decision agreement with the offline bot on
   the same states, and the latency of every stage at p50/p95/p99.
3. One Sol review of the Mac-touching scripts before their first run.

**D. Training Camp.** Several games, each with video, decision log, perception log and input log. Measure perception
errors against manual labels, latency, misclicks (tap → card accepted), result and crowns.

**E. Ladder.** Once Training Camp is clean. Report trophies and W/L per game. No automatic match-queueing beyond the
normal button flow, and no randomized timing.

## 3. Blockers

| # | blocker | owner | impact |
|---|---|---|---|
| B1 | The official client aborts on stock AVDs (anti-emulator check); bypassing it is excluded | LIVE (A2–A4) | Critical path. May end in "no legal emulator", which means asking Sam about a phone |
| B2 | 9.7 GB free disk on the Mac | **Sam** | Can't install BlueStacks data and the client (about 12 GB published) |
| B3 | Win11 UTM VM using 16 GB of 24 GB RAM | **Sam** | Emulator plus search plus perception won't fit; possibly why BlueStacks hung |
| B4 | The 10-04 BlueStacks first boot hung in `StartingKernel` | LIVE | Retry after B2/B3; if it hangs again, try MuMu |
| B5 | Perception has no accepted accuracy, and the official-client domain gap is unmeasured | LIVE (B) | Needs GPU time (coordinator) and official frames (after A) |
| B6 | Engines only support the 56 C56 cards at level 11; the live account has low-level starter cards | LIVE + bot lead | Plan at level 11, refuse non-C56 cards, label results out of distribution |
| B8 | K4C-r16 is unbounded and single-threaded, Mac native pins are missing, and there is no live → bot adapter | LIVE (C) | About a day of glue code; it5s2 is the fallback tier |
| B9 | No valid Mac search timing (the old E4 numbers are void) | LIVE (C) | Measured in the step C replay |
| B7 | Account creation may need a Google sign-in or a Supercell ID email code | **Sam**, if it comes up | Guest play is expected not to need it |

## 4. For Sam (via the coordinator)

1. **Disk:** free about 20 GB on the Mac mini. The Data volume has 9.7 GB free. I won't delete anything outside my own
   dirs: `~/Desktop/code` (134 GB) holds sealed study trees, and the rest is yours.
2. **RAM:** may I stop the UTM "Canvasdoc Win11" VM during live sessions? It holds 16 GB and has been up 3 days. Or
   tell me the hours it must stay up.
3. **Emulator fallback:** if BlueStacks needs a Google sign-in to install from the Play Store, please create or log in
   a throwaway Google account on it (Screen Sharing), or tell me to keep sideloading the signed APK. If BlueStacks
   fails, MuMu Pro for Mac needs a vendor account and, after its trial, a subscription. OK to buy one month?
4. **Heads-up, no action yet:** if no commercial emulator runs the unmodified client, the remaining legal route is a
   physical Android phone on USB to the Mac. That needs your OK, because the authorization says emulator only. Spoofing
   the emulator to get past the client's check would be detection evasion, and I won't do it.

## 5. Resources requested

- **GPU:** one A6000 for about 10 h, for step B (v4 fine-tune plus val measurement). Requested from the coordinator
  out of the bot track's 01/04/08. 01 holds the v4 caches, so 01 is preferred.
- **CPU:** none heavy. 05 only orchestrates.
