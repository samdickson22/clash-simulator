# Official-client L3 handoff

## Latest result: BlueStacks installed, first boot failed

The coordinator installed BlueStacks Air 5.21.790.7505 and deleted the installer. This resume launched one instance. Its Android first boot stayed in `StartingKernel`; Player.log reports `launch_start_timeout` and inability to launch within 90 seconds. The Settings > Advanced ADB toggle was available at `127.0.0.1:5555`, but saving timed out, the config remained disabled, and the requested SDK adb could not connect. Subsequent UI and screenshot requests timed out. No cause is established.

Stopped owned BlueStacks PID 46859 and verified its absence. No retry or workaround was attempted. The L2 reference emulator PID 75156 remained running. BlueStacks itself logged an invocation of bundled `hd-adb kill-server` during its timeout recovery; this agent issued no such command and sent no commands to the reference emulator. No new macOS administrator prompt was observed.

No Clash Royale bundle was downloaded or installed in BlueStacks, and no game launch or guest account occurred. King level, cards, arena, mode availability, calibration, menu recognition, FPS, input/capture latency and Training Camp recordings are unavailable. Existing AVD plumbing and old transport measurements do not establish BlueStacks readiness; plumbing was not adapted without a working Android transport.

Evidence is in `bluestacks/resume/Player-first-boot.log`, `adb-settings.txt`, `ui-events.txt`, `stop.txt`, and `final-status.json`. The screenshot could not be saved because CUA capture timed out. Downloads are empty; new recordings total zero bytes. Measured app allocation is 2908725248 bytes and data allocation 159985664 bytes, totaling 3068710912 bytes. Host free space at handoff was 12315226112 bytes, above the 5 GiB stop threshold. Earlier attempts below are historical.

## Historical result: BlueStacks installation awaited macOS administrator authorization

The 2026-10-04 BlueStacks Air trial downloaded official version 5.21.790.7505 and verified the notarized now.gg package signature with pkgutil and spctl. The 14 GiB free-space gate passed. The standard installer advertises 2.89 GB and is pending administrator authorization after clicking Install. Desktop automation explicitly refuses access to com.apple.SecurityAgent; passwordless sudo is unavailable. An administrator must complete the local Installer authorization. No workaround was attempted.

Installation and first boot have not completed. No BlueStacks VM or game account exists, and no ADB/gameplay/calibration/latency/recording claims can be made for this attempt. The verified 1.03 GB installer is retained under ~/.cache/clasher-official/bluestacks-downloads/ for the pending authorization. No APK was downloaded. Evidence and exact remaining deliverables are in bluestacks/status.json, installer-verification.json, authorization-blocker.txt and installer-awaiting-authorization.png. Earlier results below are historical.

## Prior result: Google Play retry completed, startup blocked

On 2026-10-04 the fresh API 35 Google Play ARM64 revision 9 image installed and booted successfully with the real Play Store. The new AVD is `clasher_official_play_api35`, in the dedicated official AVD home. It uses 3072 MiB RAM, 720x1280 portrait, host GPU, and no snapshots. Both config `3G` and `-partition-size 3072` were supplied, but `hardware-qemu.ini` reports `6g`; the requested 3 GiB userdata cap was not achieved. The guard stops this owned emulator at 4.4 GB AVD allocation or below 3 GB host free space.

The re-downloaded APKMirror 160402017 bundle matched the prior SHA-256. All four installed APKs passed `apksigner` verification against the requested Supercell certificate. Installation succeeded via `adb install-multiple`; bundle and extracted APKs were deleted. SDK staging also removed its image archive.

The first and only Play-image app launch crashed before game UI with the same `frrh.aC: 02` during `Runtime.nativeLoad` / `System.loadLibrary`. No cause is asserted. No further launch or workaround was attempted. The owned emulator is stopped. No account was created; tutorial, account/card/mode observations, game calibration, menu validation, in-game latency and Training Camp recordings remain unavailable. Earlier transport measurements below are launcher-only and do not establish game readiness.

Evidence: `play-retry/launch-logcat.txt`, `launch-crash.txt`, `launch.png`, `exit-info.txt`, `device-config.txt`, `apk-source.json`, `install.txt`, and `resume-final-status.json`. New image plus AVD allocation is 4,978,692,096 bytes, with 15,553,970,176 bytes host free at shutdown. No new recordings were made. Old crash evidence is preserved; the old official AVD was deleted by the coordinator before this run. The launcher now targets the new Play AVD, but this blocked trial should not be automatically retried.

Next options are [BlueStacks Air](https://support.bluestacks.com/hc/en-us/articles/32272913555597-System-specifications-for-installing-BlueStacks-Air) and [MuMu Pro for Mac](https://www.mumuplayer.com/). Neither was installed or tested. BlueStacks publishes a 12 GB free-space requirement. MuMu's Mac offering advertises a trial requiring its own account and a subscription afterward. Neither is evidence of compatibility with this release.

## Historical first trial and disk-blocked retry

The remaining sections describe the earlier Google APIs trial and the first disk-blocked retry. Their old AVD ownership details are historical.

The verified official client is installed, but L3 gameplay is blocked. Two ordinary launches of version 160402017 failed before any game UI. Android reports `frrh.aC: 02` while loading the native library during application initialization. The cause is unconfirmed. There is no new game account, tutorial completion, game calibration, or Training Camp recording. No evasion, app modification, private game data access, personal login, purchase, or chat was attempted.

## Dedicated emulator

- Name `clasher_official_api35`, serial `emulator-5590`, authenticated localhost gRPC port 8590.
- AVD home `/Users/sam/.cache/clasher-official/avd`, independent of all reference AVDs.
- Shared existing SDK `/Users/sam/.cache/clasher-native-reference/android-sdk`, API 35 Google APIs revision 9, ARM64. The SDK image was not modified.
- 720x1280 portrait, density 320, host GPU, two cores. Requested 2048 MiB RAM was raised by the emulator to 2560 MiB, within the 4 GB limit.
- Networking enabled. The `com.android.vending` package is the image's LicenseChecker stub, not Play Store.
- Snapshots disabled. SDK enforces 6 GiB virtual userdata despite config `3G` and explicit `-partition-size 3072`. A hard 3 GiB partition cap was not achieved. Actual allocated AVD storage is recorded in `final-status.json` and is below 6 GB. `storage_guard.py` checks every two seconds and stops only the owned emulator at 5.4 GB allocation or below 3 GB host free space. This is a polling guard, not a filesystem quota, and does not alter the other jobs' watchdogs.

The emulator is stopped at handoff to release RAM. Start it with:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python reports/strategy_council_20260928/live-loop/l3/launch.py
```

The launcher uses the required `pilot/detach.sh`, refuses occupied ports, updates `ownership.json`, and starts the storage guard. It never clears data, installs an app, creates an account, or starts a battle. Wait for `adb -s emulator-5590 shell getprop sys.boot_completed` to return `1`. To stop, first check `official_loop.owned_pid()`, then call its `adb('emu', 'kill')`. Ownership checks reject reference AVD processes.

## Verified installation

Source: [APKMirror official Supercell ARM64 release](https://www.apkmirror.com/apk/supercell/clash-royale/clash-royale-160402017-release/clash-royale-160402017-android-apk-download/).

Package `com.supercell.clashroyale`; version/code `160402017`. Installed using `adb install-multiple` with base, arm64-v8a, English, and xxhdpi splits. `apk-source.json` retains the bundle and individual APK SHA-256 hashes and complete `apksigner verify --print-certs` receipts. Every installed APK verifies against APKMirror's published Supercell certificate:

`59ea9ded5f79298a50103d254497ca71ca80332492c749375044879b8f099357`

Certificate subject is `CN=Supercell, OU=Supercell, O=Supercell, L=Helsinki, ST=Uusimaa, C=FI`. Bundle hash is `13794ed94c38733211ea6e95f97b654790e01539bb9e01e7e3a386906653d46e`. Temporary downloads and extracted APKs were deleted after installation and verification. Installed app copies remain inside this AVD.

## Plumbing and measured limits

`official_loop.py` implements authenticated emulator gRPC capture, a one-frame latest buffer, sequential adb taps, drags, and a card-slot/arena command. `Capture` can pass every delivered frame to a sink before updating its latest buffer. Consumers see sequence numbers and screenshot production/host receipt timestamps. The stream emits changed screens; a static screen may produce no new frame. It is not a game tick clock.

`recording.py` encodes every delivered frame at 360x640 into H.264 MP4, preserving screenshot timing with 90 kHz presentation timestamps. Its frame sidecar supports frame-count and timestamp audits. Files are capped at 250 MB each and the recording directory at 950 MB, checked once per second with headroom below the 1 GB task limit. No timer downsamples capture. Compression is lossy, CRF 28.

The accepted smoke benchmark used launcher/app-drawer gestures, not Clash Royale:

- 723 frames over 14.557 seconds, 49.599 FPS.
- Screenshot production to host receipt: mean 1.704 ms, p95 2.907 ms, p99 6.527 ms.
- Ten sequential two-tap commands: mean 44.426 ms, p95 58.200 ms, p99 63.126 ms. This is command completion, not card placement or game acceptance latency.
- `recordings/launcher-smoke.mp4`: 2,215,168 bytes, 360x640, H.264; ffprobe independently decoded 723 frames. The only video is this transport smoke, not a Training Camp match.

`transport-benchmark.json`, `benchmark-input.jsonl`, and `evidence/video-probe.json` retain measurements. `benchmark_transport.py` exercises the I/O and recorder while gesturing through the Android launcher. It refuses to overwrite an existing video; use a new recording filename for another run. One initial run hit a deferred-output-file creation bug, fixed before the accepted run; its diagnostic log is preserved. The accepted run emitted gRPC fork and duplicate codec-library warnings but completed, and the complete video decoded successfully.

## Lifecycle and calibration status

`ScreenStates` supports fixed-ROI screen templates with multiple anchors and returns `unknown` on ambiguity or unvalidated configuration. `states.json` has no templates because no official game screen was reached. This is an interface, not a trained or validated menu recognizer. There is no functioning automatic Training Camp starter or match-end detector yet.

`calibration.json` explicitly leaves hand centers, tile-to-pixel homography, and calibration errors null. `Input.play` and `tile_to_pixel` reject this unvalidated configuration. Offline-reference calibration is not reused. A future supported unmodified client session needs real home, Training Camp, battle-start, battle, and result screenshots; independent landmark checks; and measured card acceptance before enabling a driver.

`account.json` contains null King level, arena, unlocked cards and mode availability. `evidence/launch-crash-1.txt`, `launch-crash-2.txt`, and `exit-info.txt` establish the startup blocker. These are OS diagnostics, not app memory inspection. `evidence/first-launch.png` is the launcher after an unsuccessful monkey invocation; `launched.png` and `relaunch.png` are the launcher after actual app-start failures.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python reports/strategy_council_20260928/live-loop/l3/test_boundaries.py
```

Four guard tests pass: reject reference-emulator ownership before sending input; refuse unvalidated calibration; classify unvalidated screens as unknown; reject out-of-display input. Successful live capture, all-frame recording, command timing, and independent full-video decode supplement those tests. None establishes game readiness.

All repository writes are inside this L3 directory. Shared engine, gamedata, engine-rs, pilot, c56, offline APKs/AVDs, and L1 outputs were untouched. Only this task's emulator was stopped. No Git mutations were used.

## Google Play image retry, 2026-10-04

The requested production Google Play image trial is blocked before installation by disk space. No Play AVD launch has occurred, so the rootable-image hypothesis remains untested. The host had about 4-5 GB free. API 35 Google Play ARM64 revision 9 needs 4,097,830,604 bytes for its archive and extraction before creating an AVD. API 34 needs more installation space. The existing task download directory is empty; the old official AVD is preserved because no replacement has worked.

See `play-retry/status.json`, `preflight.json`, `image-sizes.json` and `disk-final.txt`. Resume with about 10 GB host free, then install `system-images;android-35;google_apis_playstore;arm64-v8a` using the existing SDK's sdkmanager. Keep new image plus AVD within 7 GB and AVD RAM within 4 GB. Recheck free space throughout installation and boot. Use a new owned AVD and the required detach wrapper. Do not alter the old launcher's ownership binding until the new configuration is ready. Stop on an integrity-style launch failure and preserve logcat. All original account, calibration and gameplay limits above still apply.

BlueStacks Air is a possible later trial on this Apple-silicon host. Its official requirements specify 12 GB free storage and 8 GB host RAM; installed size and compatibility with this exact Clash Royale release were not tested. No alternative emulator was installed.
