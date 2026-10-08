# T1 progress

Current status: Phase A RUNNING in its one-time two-renderer retry (2026-10-07 23:46 PDT). Wrapper PID 22770; scheduler PID 22771; label pool-phase-a-20261007-retry2-once. retry_used=true; any per-match endpoint failure or critical memory pressure permanently reduces Phase A to one renderer. The retry snapshot at the end supersedes prior operating snapshots.

The retained L2 launcher's historical base config had been removed with old artifacts. Launch reached the verified attestation, then failed reading that missing file. Recovered the same owned emulator using L2 pair 00's retained setup config, rechecked both UID firewall rules and the exact attestation, and wrote `base-config.json` and `emulator-host/complete.json`. No APK or hook changes were made. `launch.py` makes this repair repeatable without changing old L2 files.

Current owner is emulator-5584, adb 5042, gRPC 8558 and probe 26794. Backend is host GPU, with two emulator cores and 3 GiB. The other project's UTM VM, Stage 6 workers, old adb 5041 and transfer jobs are untouched. One emulator keeps Phase A at about 24 hours of active collection wall time, plus setup and transfer.

The split is prepared in `split.json`. The pipeline freezes the final content manifest before smoke or Phase A. Smoke uses three separate seeds at normal, double and triple-elixir starts. No training is launched. Data buffer is `~/.cache/clasher-live-v4/buffer`; finalized data goes only to `127x02:/mpac/sdicks02/repos/clasher-v4-data/matches/`. Local `data/` holds compact checksummed receipts. The hub's first real two-file checksum rehearsal passed. Negative checksum and local-mutation tests preserve all local media.

The collector checks a 400 MiB new-match reserve against the 6 GB buffer cap and 15 GiB free-disk floor. It checks a 32 MiB reserve every second while encoding. Transfer failures pause new matches. Partial matches retain their files and rerun the same frozen seed. Matches are complete only after atomic `receipt.json`; local media deletion follows a hub recomputation of every SHA256 and a matching acknowledgement.

## Resume

The current detached driver is `pipeline.py --phase-a-only`: wrapper PID **63607**,
pipeline PID **63610** (both started 2026-10-07, wrapper reparented to launchd).
It holds `pipeline.lock` and waits for a readable
`127x01:/mpac/sdicks02/jobs/clasher/hub-ready.json`, then rechecks smoke admission
and the frozen source hashes before collecting. No Phase A match may precede that
marker or the verified smoke receipt. Read `pipeline-state.json` and
`pipeline-phase-a-20261007.log` first. Do not launch a duplicate driver.

Owned renderer PID **28907**, dedicated adb server PID **28905** on **5042**,
serial **emulator-5584**, gRPC **8558**, probe **26794**. Receipt:
`emulator-host/relaunch-20261007/complete.json` (mirrored at `emulator-host/complete.json`).
The AVD is read-only, host GPU, 2 cores / 3 GiB, app UID 10208; both UID REJECT
rules and attestation SHA256 `864227bf7208aa9c06cd976db3fa0734a32277b0552f92e496ad283a917b4a93`
passed. Verify receipt PID, process start and command before acting on any PID;
never kill shared adb or other projects' VMs.

If the driver has exited, inspect its exit file and stage log, preserve the failed
match, and resume on the Mac with a fresh log name:

```sh
cd /Users/sam/Desktop/code/clasher
resume_stamp=$(date -u +%Y%m%dT%H%M%SZ)
reports/strategy_council_20260928/pilot/detach.sh \
  reports/strategy_council_20260928/live-loop/v4/resume-phase-a-$resume_stamp.log \
  reports/strategy_council_20260928/live-loop/v4/run.sh phase-a-resume-$resume_stamp \
  .venv/bin/python -u reports/strategy_council_20260928/live-loop/v4/pipeline.py --phase-a-only
```

Read-only counts: `.venv/bin/python scripts/collect_l1_stream_v4.py --status`.
The collector resumes from hub-verified receipts, ships complete buffered matches
before starting another, and reruns incomplete matches with the same frozen seed.
Never rerun the historical T2 bench from the old resume instructions.

If the owned emulator died, use the same detach/run wrapper with
`launch.py NEW_RECEIPT_DIRECTORY`; if stopped during adbd root restart, add
`--resume-owned PREVIOUS_LAUNCH_DIRECTORY`. It refuses to adopt a foreign serial.
Do not refreeze or modify source after Phase A starts without a dated deviation.

Current source manifest SHA256:
`460aabbd70b894da0750b0ef573ff06a8b7423ac77ada300254494819daab475` (407 hashes).
Current registration: `127x01:/mpac/sdicks02/repos/clasher-v4-data/registration/v4-registration-460aabbd70b894da/`.
Split SHA256 remains `3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258`.
Runtime `collection-config.json` overrides the old split metadata's hub and duration:
stop at heldout >=1,500 opponent events AND >=20 matches, or the 36 active-hour cap
with the preregistered 380-second complete-match reserve. No outcomes or model
outputs enter the rule. Buffer cap 6,000,000,000 bytes; free floor 15 GiB.


2026-10-07 15:32:11 -0700: Frozen 404 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 15:37:08 -0700: T1 freeze remains intact. T2 restarted with public-mask legal placements; prior fixed-tile trials are diagnostic only. New bench worker 8559. The serial driver waits before smoke and Phase A. No collection match has started.

2026-10-07 15:45:49 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

The converter accepts either one finalized match or the hub's `matches/` directory. It excludes smoke and metadata receipts from a bulk conversion. Its output contains `manifest.json`, `videos/`, and `audit/`, ready for the unchanged v3 trainer's dataset and audit arguments. A two-match test decoded real H.264 outputs and checked frame/event label round trips. Source-only amendments occurred before any collector smoke; prior registration bundles remain on the hub.

2026-10-07 15:51:47 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 16:05:16 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 16:08:01 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 16:11:33 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 16:20:38 -0700: Frozen 405 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

Coverage note for the coordinator: 21,000 total deployments with roughly symmetric seats and a 10% heldout split implies about 1,050 heldout opponent events, below DESIGN's 1,500 minimum. Actual counts may be higher, so the runner measures and reports that gate. It preserves the frozen 80/10/10 split and stops at 24 active emulator-hours; it does not silently extend Phase A or alter heldout sampling. If coverage falls short, additional acquisition needs a prospective coordinator decision.


## Pre-smoke amendment, 2026-10-07: hub recovery, timing and coverage

Before any smoke or Phase A match, adopt the coordinator decision in
`../../amendments/2026-10-07-t2-actuation-timing.md` (including its addendum).
The destination is now `127x01:/mpac/sdicks02/repos/clasher-v4-data/matches/`.
This is an operational destination change; acquisition labels and match schema are unchanged.
Old registration bundles on 127x02 are unreachable. Re-register the preserved producer
sources and the new content manifest under the new hub's `registration/` directory.
Do not write to the hub's recovered source checkout.

Phase A now stops when the frozen heldout split contains at least 1,500 accepted
opponent events AND at least 20 matches, or at the 36 active emulator-hour cap.
Only receipt counts are inspected; no label content, model output, or outcome enters
the stopping rule. The frozen seed/deck memberships and 80/10/10 split are unchanged
(split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258).
The collector reserves its existing 380-second maximum match duration before starting
another complete match, so it may stop at the cap up to 380 seconds early rather than
exceed 36 hours. Coverage shortfall is reported; it does not authorize more collection.
Historical split metadata still says 24 hours and 127x02; `collection-config.json`
is the prospective operational override, avoiding a change to split identity.

Phase A requires a readable JSON `127x01:/mpac/sdicks02/jobs/clasher/hub-ready.json`
and at least one checksum-verified smoke match on 127x01, in addition to all existing
three-smoke admission gates. The 15 GiB disk floor and 6 GB buffer cap are unchanged.

Source deviation before smoke: the prior collector hard-coded its hub and duration,
so minimal source edits were necessary to load the operational config, enforce the
count/cap stop, and check hub readiness. The backend-relative actuator timing change
also changes a hashed source file. Therefore archive the prior freeze locally and
refreeze before smoke. No APK, hook, command age, attestation, collector label schema,
threshold or frozen population is changed. T2 failure does not block T1's independent
scheduled-receipt collector; it continues to block production actuator qualification.

2026-10-07 pre-smoke validation incident: the existing 1-second synthetic codec test measured 18.80 and 18.73 FPS, including startup cost. Its synthetic capture fixture is extended to 6 seconds to assess steady timestamp sampling without lowering the 19.5 test assertion. Real smoke remains three frozen matches at >=19.8 FPS each; no acquisition endpoint was changed. The first failure occurred during T2; the second with the renderer paused. Both results are retained in the validation logs.

2026-10-07 pre-smoke diagnostic outcome: the 6-second synthetic extension also failed (15.71 FPS, frame-gap p99 206 ms). Profiling showed time in paced sleeps/reads rather than codec encoding; the evidence does not support the initial startup-cost hypothesis. Restored the original 1-second fixture and original assertions. No production sampling code or endpoint was changed. Seven actuator tests and eight coverage/storage/converter checks passed; the existing synthetic lifecycle FPS assertion remains failing on this host. Real preregistered smoke is the next acquisition measurement and remains mandatory for Phase A. All diagnostic logs/profile are retained.

2026-10-07 16:44:50 -0700: Frozen 407 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 16:46:17 -0700: v4-smoke-0: 1215 frames, 19.994 FPS, 21 plays, all exact ticks; hub verified 7860383 bytes.


## Pre-Phase-A infrastructure amendment, 2026-10-07 23:51Z

The first smoke attempt shipped `v4-smoke-0` (19.994 FPS, 21 exact-tick plays)
to 127x01, then smoke seed 1975100001 failed at tick 2630 with `unsupported visible
body identity`. Ordinary native objects keep the parent spell card ID: the spawned
Barbarian was projected as BarbLog. This is an adapter failure, not a match outcome.
The collector-only repair maps a spell with exactly one hitpoint-bearing payload
to that payload's existing C56 body stats (BarbLog→Barbarian, GoblinBarrel→Goblin,
RoyalDelivery→DeliveryRecruit). Unknown/ambiguous payloads still fail. No common
engine, APK, hook, player, label schema, data thresholds or split membership changes.

Preserve the successful old match on the hub and archive its local receipt and
converter check under `data/smoke-attempts/pre-body-repair-20261007/`. Preserve the
incomplete second match in the capped buffer. Archive the old source manifest and
refreeze before rerunning all three original smoke seeds with `-bodyrepair1`
attempt IDs. This ensures admission uses one producer freeze and overwrites no
completed receipt. Phase A has collected no matches and remains gated on all three
new smoke passes plus hub-ready.json. The coordinator's 23:50:59Z whole-repo
checksum window has ended; this source repair is later than that hub source snapshot.
Only the new producer registration bundle is sent to v4-data, never a hub source resync.

Raw T2 truth preservation audit: the completion bench initially appended 17 gzip members to its evaluator-only truth file. Split those members into `~/.cache/clasher-live-v4/buffer/actuation/truth-before-completion-20261007.jsonl.gz`; the original 623-member compressed prefix is restored byte-for-byte (SHA256 d4a41a942cf10e7792b3ce322e9d6aa786b68bfb84418c6e172ea95dfbf16117). Both sets remain retained, and the completion bench now targets its separate truth file. Original factorial trial SHA256 remains b17fa82b5463be4be2c7727c809c502dd925ae4b1ac5939bd531b4dcade77cae.

2026-10-07 16:53:08 -0700: Frozen 407 source/config hashes; split SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.

2026-10-07 16:54:38 -0700: v4-smoke-0-bodyrepair1: 1218 frames, 19.999 FPS, 20 plays, all exact ticks; hub verified 8143379 bytes.

2026-10-07 16:56:14 -0700: v4-smoke-1-bodyrepair1: 1214 frames, 19.995 FPS, 29 plays, all exact ticks; hub verified 8971873 bytes.

2026-10-07 16:58:21 -0700: v4-smoke-2-bodyrepair1: 1195 frames, 19.999 FPS, 49 plays, all exact ticks; hub verified 11381698 bytes.

2026-10-08T00:00:00.880269+00:00: Bodyrepair1 smoke admission PASS. Normal/double/triple: 1218/1214/1195 frames, 19.999/19.995/19.999 FPS, 20/29/49 accepted events; 98/98 exact ticks; all three hub checksums verified (28,496,950 bytes total). Converter passed with 609 selected frames and all 20 deployment labels from smoke 0. No champion ability event occurred in smoke; report Phase A coverage separately. Focused validation-bodyrepair1.log: 16/16 tests pass (including all seven actuator tests, body-alias regression, count/cap admission, storage negatives and real-codec converter). The earlier synthetic lifecycle FPS assertion remains an unresolved test limitation; its assertion and fixture are unchanged. Real smoke endpoints were not relaxed. Buffer 62,709,459 bytes and free disk 20,760,186,880 bytes at smoke admission. Driver is detached and waiting for hub readiness; no first Phase A match yet.

2026-10-07 18:00:17 -0700: v4-phase-a-1975100700: 5655 frames, 20.000 FPS, 135 plays, all exact ticks; hub verified 41410220 bytes.

2026-10-07 18:02:41 -0700: v4-phase-a-1975100701: 2416 frames, 19.955 FPS, 45 plays, all exact ticks; hub verified 15960789 bytes.

2026-10-07 18:05:09 -0700: v4-phase-a-1975100702: 2170 frames, 19.830 FPS, 65 plays, all exact ticks; hub verified 16936102 bytes.

2026-10-07 18:07:39 -0700: v4-phase-a-1975100703: 1935 frames, 19.999 FPS, 62 plays, all exact ticks; hub verified 16411513 bytes.

2026-10-07 18:09:11 -0700: v4-phase-a-1975100704: 686 frames, 20.000 FPS, 31 plays, all exact ticks; hub verified 5836778 bytes.

2026-10-07 18:10:44 -0700: v4-phase-a-1975100705: 561 frames, 20.000 FPS, 33 plays, all exact ticks; hub verified 5372810 bytes.

2026-10-07 18:12:33 -0700: v4-phase-a-1975100706: 797 frames, 19.993 FPS, 28 plays, all exact ticks; hub verified 6515048 bytes.

2026-10-07 18:15:18 -0700: v4-phase-a-1975100707: 3018 frames, 20.000 FPS, 52 plays, all exact ticks; hub verified 20386693 bytes.

2026-10-07 18:17:41 -0700: v4-phase-a-1975100708: 2416 frames, 20.000 FPS, 56 plays, all exact ticks; hub verified 15594954 bytes.

2026-10-07 18:19:18 -0700: v4-phase-a-1975100709: 1216 frames, 19.998 FPS, 28 plays, all exact ticks; hub verified 8974701 bytes.

2026-10-07 18:20:22 -0700: v4-phase-a-1975100710: 305 frames, 19.980 FPS, 11 plays, all exact ticks; hub verified 2498631 bytes.

2026-10-07 18:22:52 -0700: v4-phase-a-1975100711: 1796 frames, 19.999 FPS, 62 plays, all exact ticks; hub verified 15751326 bytes.

2026-10-07 18:24:58 -0700: v4-phase-a-1975100712: 1195 frames, 20.000 FPS, 38 plays, all exact ticks; hub verified 9921135 bytes.

2026-10-07 18:26:48 -0700: v4-phase-a-1975100713: 794 frames, 19.994 FPS, 26 plays, all exact ticks; hub verified 7408258 bytes.

2026-10-07 18:30:16 -0700: v4-phase-a-1975100714: 3846 frames, 20.000 FPS, 82 plays, all exact ticks; hub verified 27367539 bytes.

2026-10-07 18:34:45 -0700: v4-phase-a-1975100715: 4797 frames, 20.000 FPS, 156 plays, all exact ticks; hub verified 36754950 bytes.

2026-10-07 18:36:22 -0700: v4-phase-a-1975100716: 1217 frames, 20.000 FPS, 47 plays, all exact ticks; hub verified 9405915 bytes.

2026-10-07 18:38:48 -0700: v4-phase-a-1975100717: 1872 frames, 19.999 FPS, 50 plays, all exact ticks; hub verified 14866600 bytes.

2026-10-07 18:41:15 -0700: v4-phase-a-1975100718: 1733 frames, 19.992 FPS, 50 plays, all exact ticks; hub verified 14321889 bytes.

2026-10-07 18:43:21 -0700: v4-phase-a-1975100719: 1196 frames, 19.994 FPS, 45 plays, all exact ticks; hub verified 10065339 bytes.

2026-10-07 18:45:11 -0700: v4-phase-a-1975100720: 796 frames, 19.988 FPS, 29 plays, all exact ticks; hub verified 7103249 bytes.

2026-10-07 18:48:08 -0700: v4-phase-a-1975100721: 3277 frames, 20.000 FPS, 66 plays, all exact ticks; hub verified 20806151 bytes.

2026-10-07 18:50:33 -0700: v4-phase-a-1975100722: 2416 frames, 20.000 FPS, 39 plays, all exact ticks; hub verified 17570545 bytes.

2026-10-07 18:52:09 -0700: v4-phase-a-1975100723: 1218 frames, 19.994 FPS, 32 plays, all exact ticks; hub verified 9026411 bytes.

2026-10-07 18:55:04 -0700: v4-phase-a-1975100724: 2396 frames, 20.000 FPS, 92 plays, all exact ticks; hub verified 20903921 bytes.

2026-10-07 18:57:25 -0700: v4-phase-a-1975100725: 1624 frames, 19.991 FPS, 71 plays, all exact ticks; hub verified 15729941 bytes.

2026-10-07 18:59:15 -0700: v4-phase-a-1975100726: 877 frames, 19.999 FPS, 29 plays, all exact ticks; hub verified 7803579 bytes.

2026-10-07 19:01:04 -0700: v4-phase-a-1975100727: 795 frames, 19.997 FPS, 36 plays, all exact ticks; hub verified 6748317 bytes.

2026-10-07 19:04:02 -0700: v4-phase-a-1975100728: 3275 frames, 19.998 FPS, 71 plays, all exact ticks; hub verified 20675279 bytes.

2026-10-07 19:06:18 -0700: v4-phase-a-1975100729: 2258 frames, 20.000 FPS, 51 plays, all exact ticks; hub verified 17798346 bytes.

2026-10-07 19:07:55 -0700: v4-phase-a-1975100730: 1217 frames, 19.995 FPS, 32 plays, all exact ticks; hub verified 9417584 bytes.

2026-10-07 19:10:16 -0700: v4-phase-a-1975100731: 1768 frames, 19.997 FPS, 45 plays, all exact ticks; hub verified 14567031 bytes.

2026-10-07 19:12:24 -0700: v4-phase-a-1975100732: 1385 frames, 19.996 FPS, 48 plays, all exact ticks; hub verified 12638618 bytes.

2026-10-07 19:13:45 -0700: v4-phase-a-1975100733: 344 frames, 19.985 FPS, 11 plays, all exact ticks; hub verified 2948646 bytes.

2026-10-07 19:15:26 -0700: v4-phase-a-1975100734: 631 frames, 19.969 FPS, 30 plays, all exact ticks; hub verified 5805545 bytes.

2026-10-07 19:18:32 -0700: v4-phase-a-1975100735: 3472 frames, 19.996 FPS, 57 plays, all exact ticks; hub verified 20826628 bytes.

2026-10-07 19:20:16 -0700: v4-phase-a-1975100736: 1677 frames, 19.992 FPS, 30 plays, all exact ticks; hub verified 11640334 bytes.

2026-10-07 19:23:22 -0700: v4-phase-a-1975100737: 2933 frames, 19.999 FPS, 110 plays, all exact ticks; hub verified 24855929 bytes.

2026-10-07 19:24:32 -0700: v4-phase-a-1975100738: 444 frames, 19.985 FPS, 14 plays, all exact ticks; hub verified 3608458 bytes.

2026-10-07 19:26:12 -0700: v4-phase-a-1975100739: 865 frames, 19.999 FPS, 23 plays, all exact ticks; hub verified 6857526 bytes.

2026-10-07 19:28:18 -0700: v4-phase-a-1975100740: 1196 frames, 19.998 FPS, 50 plays, all exact ticks; hub verified 12212862 bytes.

2026-10-07 19:30:01 -0700: v4-phase-a-1975100741: 676 frames, 19.997 FPS, 26 plays, all exact ticks; hub verified 6508000 bytes.

2026-10-07 19:32:36 -0700: v4-phase-a-1975100742: 2853 frames, 19.997 FPS, 52 plays, all exact ticks; hub verified 19874175 bytes.

2026-10-07 19:34:59 -0700: v4-phase-a-1975100743: 2417 frames, 19.999 FPS, 49 plays, all exact ticks; hub verified 16626570 bytes.

2026-10-07 19:36:35 -0700: v4-phase-a-1975100744: 1219 frames, 19.996 FPS, 36 plays, all exact ticks; hub verified 9643518 bytes.

2026-10-07 19:39:27 -0700: v4-phase-a-1975100745: 2395 frames, 19.999 FPS, 78 plays, all exact ticks; hub verified 20938831 bytes.

2026-10-07 19:40:41 -0700: v4-phase-a-1975100746: 356 frames, 19.974 FPS, 11 plays, all exact ticks; hub verified 2929314 bytes.

2026-10-07 19:42:44 -0700: v4-phase-a-1975100747: 1148 frames, 19.996 FPS, 45 plays, all exact ticks; hub verified 10254569 bytes.

2026-10-07 19:44:33 -0700: v4-phase-a-1975100748: 796 frames, 19.998 FPS, 31 plays, all exact ticks; hub verified 7254117 bytes.

2026-10-07 19:49:22 -0700: v4-phase-a-1975100749: 5414 frames, 19.999 FPS, 120 plays, all exact ticks; hub verified 42324096 bytes.

2026-10-07 19:51:44 -0700: v4-phase-a-1975100750: 2417 frames, 19.997 FPS, 51 plays, all exact ticks; hub verified 16563067 bytes.

2026-10-07 19:53:20 -0700: v4-phase-a-1975100751: 1215 frames, 19.994 FPS, 31 plays, all exact ticks; hub verified 10008154 bytes.

2026-10-07 19:56:12 -0700: v4-phase-a-1975100752: 2395 frames, 20.000 FPS, 84 plays, all exact ticks; hub verified 20084590 bytes.

2026-10-07 19:58:42 -0700: v4-phase-a-1975100753: 1796 frames, 19.991 FPS, 59 plays, all exact ticks; hub verified 16297593 bytes.

2026-10-07 20:00:39 -0700: v4-phase-a-1975100754: 1053 frames, 19.990 FPS, 38 plays, all exact ticks; hub verified 9390512 bytes.

2026-10-07 20:02:28 -0700: v4-phase-a-1975100755: 796 frames, 19.995 FPS, 29 plays, all exact ticks; hub verified 7784332 bytes.

2026-10-07 20:05:19 -0700: v4-phase-a-1975100756: 3160 frames, 19.998 FPS, 56 plays, all exact ticks; hub verified 20945069 bytes.

2026-10-07 20:07:42 -0700: v4-phase-a-1975100757: 2418 frames, 19.998 FPS, 47 plays, all exact ticks; hub verified 16674877 bytes.

2026-10-07 20:10:43 -0700: v4-phase-a-1975100758: 2853 frames, 19.999 FPS, 94 plays, all exact ticks; hub verified 23974929 bytes.

2026-10-07 20:12:53 -0700: v4-phase-a-1975100759: 1599 frames, 20.000 FPS, 44 plays, all exact ticks; hub verified 12236279 bytes.

2026-10-07 20:15:22 -0700: v4-phase-a-1975100760: 1797 frames, 20.000 FPS, 63 plays, all exact ticks; hub verified 14997200 bytes.

2026-10-07 20:17:27 -0700: v4-phase-a-1975100761: 1196 frames, 19.995 FPS, 47 plays, all exact ticks; hub verified 10862805 bytes.

2026-10-07 20:19:13 -0700: v4-phase-a-1975100762: 746 frames, 19.984 FPS, 31 plays, all exact ticks; hub verified 7374593 bytes.

2026-10-07 20:22:35 -0700: v4-phase-a-1975100763: 3765 frames, 20.000 FPS, 70 plays, all exact ticks; hub verified 24967328 bytes.

2026-10-07 20:24:58 -0700: v4-phase-a-1975100764: 2416 frames, 20.000 FPS, 59 plays, all exact ticks; hub verified 16744641 bytes.

2026-10-07 20:26:34 -0700: v4-phase-a-1975100765: 1216 frames, 20.000 FPS, 27 plays, all exact ticks; hub verified 9821565 bytes.

2026-10-07 20:29:27 -0700: v4-phase-a-1975100766: 2397 frames, 19.997 FPS, 74 plays, all exact ticks; hub verified 22088703 bytes.

2026-10-07 20:31:56 -0700: v4-phase-a-1975100767: 1796 frames, 20.000 FPS, 65 plays, all exact ticks; hub verified 15269293 bytes.

2026-10-07 20:34:01 -0700: v4-phase-a-1975100768: 1195 frames, 20.000 FPS, 49 plays, all exact ticks; hub verified 11513471 bytes.

2026-10-07 20:35:51 -0700: v4-phase-a-1975100769: 795 frames, 19.994 FPS, 30 plays, all exact ticks; hub verified 6518787 bytes.

2026-10-07 20:38:47 -0700: v4-phase-a-1975100770: 3276 frames, 20.000 FPS, 59 plays, all exact ticks; hub verified 21849072 bytes.

2026-10-07 20:41:10 -0700: v4-phase-a-1975100771: 2417 frames, 19.997 FPS, 54 plays, all exact ticks; hub verified 16693841 bytes.

2026-10-07 20:42:46 -0700: v4-phase-a-1975100772: 1217 frames, 19.999 FPS, 36 plays, all exact ticks; hub verified 9118570 bytes.

2026-10-07 20:45:35 -0700: v4-phase-a-1975100773: 2324 frames, 19.998 FPS, 85 plays, all exact ticks; hub verified 20652185 bytes.

2026-10-07 20:47:14 -0700: v4-phase-a-1975100774: 837 frames, 19.992 FPS, 24 plays, all exact ticks; hub verified 7277267 bytes.

2026-10-07 20:48:39 -0700: v4-phase-a-1975100775: 439 frames, 19.994 FPS, 18 plays, all exact ticks; hub verified 3744633 bytes.

2026-10-07 20:50:28 -0700: v4-phase-a-1975100776: 796 frames, 19.995 FPS, 31 plays, all exact ticks; hub verified 7060055 bytes.

2026-10-07 20:53:24 -0700: v4-phase-a-1975100777: 3276 frames, 19.998 FPS, 62 plays, all exact ticks; hub verified 20768928 bytes.

2026-10-07 20:57:06 -0700: v4-phase-a-1975100778: 3939 frames, 19.999 FPS, 82 plays, all exact ticks; hub verified 28362424 bytes.

2026-10-07 20:59:17 -0700: v4-phase-a-1975100779: 1891 frames, 19.992 FPS, 47 plays, all exact ticks; hub verified 14695101 bytes.

2026-10-07 21:00:55 -0700: v4-phase-a-1975100780: 798 frames, 17.074 FPS, 20 plays, all exact ticks; hub verified 6195928 bytes.

2026-10-07 21:03:25 -0700: v4-phase-a-1975100781: 1795 frames, 19.997 FPS, 61 plays, all exact ticks; hub verified 16366519 bytes.

2026-10-07 21:05:04 -0700: v4-phase-a-1975100782: 695 frames, 19.707 FPS, 27 plays, all exact ticks; hub verified 6204285 bytes.

2026-10-07 21:06:54 -0700: v4-phase-a-1975100783: 795 frames, 19.989 FPS, 31 plays, all exact ticks; hub verified 6580196 bytes.

2026-10-07 21:09:35 -0700: v4-phase-a-1975100784: 3007 frames, 20.000 FPS, 56 plays, all exact ticks; hub verified 21403386 bytes.

2026-10-07 21:13:07 -0700: v4-phase-a-1975100785: 3789 frames, 20.000 FPS, 87 plays, all exact ticks; hub verified 25082287 bytes.

2026-10-07 21:14:42 -0700: v4-phase-a-1975100786: 1216 frames, 19.997 FPS, 37 plays, all exact ticks; hub verified 9287163 bytes.

2026-10-07 21:16:20 -0700: v4-phase-a-1975100787: 964 frames, 19.994 FPS, 35 plays, all exact ticks; hub verified 9986700 bytes.

2026-10-07 21:17:42 -0700: v4-phase-a-1975100788: 512 frames, 19.999 FPS, 16 plays, all exact ticks; hub verified 4571021 bytes.

2026-10-07 21:19:07 -0700: v4-phase-a-1975100789: 415 frames, 19.984 FPS, 20 plays, all exact ticks; hub verified 4221343 bytes.

2026-10-07 21:20:56 -0700: v4-phase-a-1975100790: 795 frames, 20.000 FPS, 38 plays, all exact ticks; hub verified 6990417 bytes.

2026-10-07 21:23:51 -0700: v4-phase-a-1975100791: 3272 frames, 19.982 FPS, 74 plays, all exact ticks; hub verified 21922209 bytes.

2026-10-07 21:26:50 -0700: v4-phase-a-1975100792: 3141 frames, 19.998 FPS, 71 plays, all exact ticks; hub verified 22443428 bytes.

2026-10-07 21:28:26 -0700: v4-phase-a-1975100793: 1216 frames, 20.000 FPS, 37 plays, all exact ticks; hub verified 9364184 bytes.

2026-10-07 21:30:26 -0700: v4-phase-a-1975100794: 1404 frames, 19.995 FPS, 42 plays, all exact ticks; hub verified 10640106 bytes.

2026-10-07 21:31:55 -0700: v4-phase-a-1975100795: 631 frames, 19.986 FPS, 17 plays, all exact ticks; hub verified 5019304 bytes.

2026-10-07 21:33:59 -0700: v4-phase-a-1975100796: 1196 frames, 19.992 FPS, 47 plays, all exact ticks; hub verified 10743379 bytes.

2026-10-07 21:35:49 -0700: v4-phase-a-1975100797: 795 frames, 19.997 FPS, 33 plays, all exact ticks; hub verified 7475549 bytes.

2026-10-07 21:39:34 -0700: v4-phase-a-1975100798: 4228 frames, 19.998 FPS, 100 plays, all exact ticks; hub verified 29492414 bytes.

2026-10-07 21:42:57 -0700: v4-phase-a-1975100799: 3571 frames, 19.998 FPS, 75 plays, all exact ticks; hub verified 28526807 bytes.

2026-10-07 21:44:36 -0700: v4-phase-a-1975100800: 1216 frames, 19.995 FPS, 34 plays, all exact ticks; hub verified 8533441 bytes.

2026-10-07 21:46:46 -0700: v4-phase-a-1975100801: 1540 frames, 19.996 FPS, 43 plays, all exact ticks; hub verified 12520410 bytes.

2026-10-07 21:48:07 -0700: v4-phase-a-1975100802: 485 frames, 19.994 FPS, 13 plays, all exact ticks; hub verified 4256572 bytes.


## Operational throughput amendment, 2026-10-07 PDT (recorded 2026-10-08T05:16:34.976089+00:00)

Before starting a second renderer, authorize up to three concurrent owned offline
renderer instances from the same read-only AVD, with the existing pinned attestation
and hook. No APK/hook change or re-attestation is authorized. Each instance has its
own adb server, console, gRPC and probe ports and a fresh launch receipt. Every new
match receipt records its instance ID; historical immutable receipts remain unchanged.
IPv4/IPv6 app-UID egress REJECT rules and the pinned attestation, PID/start identity,
read-only AVD and host GPU are checked before and after each match.

This is an operational throughput change, decided before inspecting any labels'
content, outcomes or model outputs. Frozen seed/deck schedule and split membership
(SHA256 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258)
remain unchanged. Claims use a file-locked shared queue, taking the earliest unclaimed,
unverified seed, without duplicate or skipped scheduled seeds. Incomplete infrastructure
attempts are preserved and rerun with the same seed; completed receipts are never rerun
or overwritten. Receipt metadata/counts alone drive admission and the stopping rule.

All endpoints remain unchanged, including >=19.8 measured FPS per match, exact-tick
accepted plays and hub checksum verification. Aggregate technical success remains
>=95%. Counts and active emulator seconds sum across instances. Stop at heldout
>=1,500 accepted opponent events AND >=20 matches, or 36 active emulator-hours.
Reserve 380 active seconds for EACH outstanding match before claiming another.
The 6,000,000,000-byte buffer cap and 15 GiB free-disk floor remain GLOBAL; reserve
400 MiB per outstanding match plus any larger finalization bound under the same lock.
Ship only through the existing verified shipper to 127x01 v4-data.

Ramp to instance 2 only after instance 1 resumes; admit instance 2 only after its
first full match passes FPS, exact-tick and hub checksum endpoints; then trial
instance 3 the same way. On any new FPS failure or critical Mac memory pressure,
stop new work above the last good count, drain current matches, pause and terminate
only the extra owned renderers after PID/start/command verification, and record the
scale-back. Partial matches never enter the coverage counts.

Preserve the original source manifest and smoke admission. A separate checksum-verified
operational source registration records only the launch/pool plumbing and instance-ID
receipt addition; validate queue/restart/global-reserve behavior before collection.
The three original smoke passes remain prerequisite and the added-instance first-match
gates measure concurrency without changing renderer, sampling, scripts or labels.

Transition observation: PID 63610 had already exited with code 1 at epoch
1791434995.354052 (storage guard); no signal was sent to an absent/reused PID.
Last verified old-driver match: v4-phase-a-1975100802 (19.994 FPS); incomplete
v4-phase-a-1975100803 is retained for same-seed rerun. The original pipeline/stage
logs and exits are preserved. At transition there are 103 verified Phase A matches,
10 heldout matches/258 accepted opponent events, 2.573823 active emulator-hours,
and 101/103 FPS passes (historical failures 1975100780 and 1975100782 retained).

2026-10-07 22:20:52 -0700: Technical rerun of v4-phase-a-1975100803; incomplete attempt retained.

Pool ramp: renderer-2 launch verified before first match; PID 21497, adb 5043 / console 5586 / gRPC 8559 / probe 26795. Original renderer-1 is rerunning partial seed 1975100803. No labels inspected.

Prospective pool implementation review: SIGTERM sent to verified scheduler PID 21299 to drain the two first matches. Remove the scheduler queue lock around network shipping before continuing: a long acknowledgement must not block another worker's once-per-second storage check. No collector timing, labels or endpoints change; current matches and exits are preserved. Re-register the corrected pool source before restart.

2026-10-07 22:22:57 -0700: Pool renderer-1 v4-phase-a-1975100803: 19.999 FPS, 42/42 exact plays; hub verified 9648859 bytes; pass=True.

2026-10-07 22:24:10 -0700: Pool renderer-2 v4-phase-a-1975100804: 19.980 FPS, 32/32 exact plays; hub verified 7554974 bytes; pass=True.

2026-10-07 22:24:10 -0700: Pool stopped: SIGTERM drain

Renderer-3 infrastructure startup incident: original launch exited 1 before attestation/seed assignment; Android app Mainloop SIGSEGV after 8 seconds (crash log retained at emulator-host/pool-renderer-3-20261007/startup-crash.txt). Host renderer PID 24095 remains owned/read-only; retry through launch.py --resume-owned into a fresh receipt directory. APK/hook/AVD unchanged; no match or coverage receipt exists for this attempt.

2026-10-07 22:27:27 -0700: Pool renderer-1 v4-phase-a-1975100805: 20.000 FPS, 62/62 exact plays; hub verified 22515954 bytes; pass=True.

2026-10-07 22:27:31 -0700: Pool renderer-2 v4-phase-a-1975100806: 19.998 FPS, 70/70 exact plays; hub verified 21644707 bytes; pass=True.

Renderer-3 owned resume PASS: same PID 24095, pinned attestation and both UID REJECT rules verified; adb 5044 / console 5588 / gRPC 8560 / probe 26796. First match trial requested at epoch 1791437311.775219. Instance 2 has passed two full matches (19.980/19.998 FPS, 32/70 exact plays, both hub verified).

2026-10-07 22:29:09 -0700: Pool renderer-1 v4-phase-a-1975100807: 19.996 FPS, 35/35 exact plays; hub verified 9325458 bytes; pass=True.

2026-10-07 22:30:08 -0700: Pool renderer-2 v4-phase-a-1975100808: 19.998 FPS, 67/67 exact plays; hub verified 15974082 bytes; pass=True.

2026-10-07 22:30:45 -0700: Pool renderer-3 v4-phase-a-1975100809: 19.999 FPS, 74/74 exact plays; hub verified 12061142 bytes; pass=True.

2026-10-07 22:31:17 -0700: Pool renderer-1 v4-phase-a-1975100810: 19.997 FPS, 40/40 exact plays; hub verified 10277959 bytes; pass=True.

2026-10-07 22:32:00 -0700: Pool renderer-2 v4-phase-a-1975100811: 19.994 FPS, 35/35 exact plays; hub verified 7075610 bytes; pass=True.

2026-10-07 22:33:39 -0700: Pool renderer-2 v4-phase-a-1975100814: 19.995 FPS, 41/41 exact plays; hub verified 8947421 bytes; pass=True.

2026-10-07 22:33:45 -0700: Pool renderer-3 v4-phase-a-1975100812: 20.000 FPS, 70/70 exact plays; hub verified 21334230 bytes; pass=True.

2026-10-07 22:33:49 -0700: Pool renderer-1 v4-phase-a-1975100813: 19.967 FPS, 45/45 exact plays; hub verified 16751987 bytes; pass=True.

2026-10-07 22:35:42 -0700: Pool renderer-1 v4-phase-a-1975100816: 19.998 FPS, 39/39 exact plays; hub verified 8714441 bytes; pass=True.

2026-10-07 22:35:57 -0700: Pool renderer-3 v4-phase-a-1975100817: 19.991 FPS, 51/51 exact plays; hub verified 11651793 bytes; pass=True.

2026-10-07 22:36:02 -0700: Pool renderer-2 v4-phase-a-1975100815: 19.997 FPS, 62/62 exact plays; hub verified 15454952 bytes; pass=True.

2026-10-07 22:37:19 -0700: Pool renderer-1 v4-phase-a-1975100818: 19.977 FPS, 21/21 exact plays; hub verified 4549901 bytes; pass=True.

2026-10-07 22:38:42 -0700: Pool renderer-2 v4-phase-a-1975100820: 20.000 FPS, 53/53 exact plays; hub verified 18833754 bytes; pass=True.


## Current pool operating snapshot — 2026-10-07T22:38:50.297910-07:00

This section supersedes the historical serial-driver status and Resume above.
Phase A is RUNNING on three admitted renderers. Scheduler PID 24088, detached
run.sh wrapper PID 24086, label/log pool-phase-a-20261007-r2. All processes inherit
nice 10 / one-thread encoder settings. No source commit, stash, clean, APK or hook
change, re-attestation, official client, timing randomization, or other-project
VM/adb intervention was performed.

The operational amendment is PREREG.md, heading "Operational throughput amendment,
2026-10-07 PDT", timestamp 2026-10-08T05:16:34.976089+00:00. The same text is above.
Original source manifest remains 460aabbd70b894da0750b0ef573ff06a8b7423ac77ada300254494819daab475;
split remains 3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258.
Current operational manifest is 6a6cf2734128fa82b4742a71bb6da577d544af38df2e71c5bcc24ca62920a9f8,
hub registration v4-registration-6a6cf2734128fa82. Original smoke
admission remains intact. pool-transition-20261007/ preserves previous source/state.

Transition: old PID 63610 had already exited 1 on the storage guard at 21:49:55 PDT,
so no signal was sent to it. Last old match 1975100802; retained incomplete seed
1975100803 was the first pool match, successfully rerun with the same frozen seed.
Initial scheduler 21299 was deliberately SIGTERM-drained while correcting transfer
lock scope; both current matches finished, shipped and exited 0, and wrapper
pool-phase-a-20261007.exit is 0. Corrected pool resumed at seeds 1975100805/0806.
Network transfers do not hold the capture/queue lock. No completed match was rerun.
New instance 3 initially had an Android app startup SIGSEGV before attestation or
seed assignment. The failed log/exit/crash are preserved; launch.py --resume-owned
successfully restarted the same owned PID using a fresh receipt directory.

Instances and endpoint evidence:

- renderer-1: renderer PID 28907, adb PID 28905, serial emulator-5584, adb 5042, gRPC 8558, probe 26794; launch receipt emulator-host/relaunch-20261007/complete.json. First match v4-phase-a-1975100803: 19.999370 FPS, 42/42 exact accepted plays, hub verified. 7 pool matches pass, FPS range 19.966904–19.999722, 284 exact plays. Current worker PID 43485 / v4-phase-a-1975100821 (workers rotate).

- renderer-2: renderer PID 21497, adb PID 21492, serial emulator-5586, adb 5043, gRPC 8559, probe 26795; launch receipt emulator-host/pool-renderer-2-20261007/complete.json. First match v4-phase-a-1975100804: 19.979888 FPS, 32/32 exact accepted plays, hub verified. 7 pool matches pass, FPS range 19.979888–19.999764, 360 exact plays. Current worker PID 44361 / v4-phase-a-1975100822 (workers rotate).

- renderer-3: renderer PID 24095, adb PID 24091, serial emulator-5588, adb 5044, gRPC 8560, probe 26796; launch receipt emulator-host/pool-renderer-3-20261007-retry1/complete.json. First match v4-phase-a-1975100809: 19.999306 FPS, 74/74 exact accepted plays, hub verified. 3 pool matches pass, FPS range 19.990556–19.999928, 195 exact plays. Current worker PID 42613 / v4-phase-a-1975100819 (workers rotate).

All new matches have instance IDs, pre/post pinned-attestation and both UID REJECT
checks, exact ticks and hub acknowledgements. Independent hub rehashes of each
instance's first match match all 11 file hashes; evidence:
pool-first-match-hub-recheck.json. The completed+claimed seed union is a contiguous
unique prefix of the frozen schedule. No FPS scale-back or critical-pressure event
occurred during the pool ramp. Seven focused tests passed, including a three-process
file-lock contention test, incomplete same-seed retry, global disk/buffer reserves,
and global in-flight active-time cap. The real SIGTERM drain and partial recovery
also passed. Historical two FPS failures remain counted, not filtered.

Current counts: 120 Phase A matches, 120 hub verified,
118/120 FPS passes, 5915/5915
accepted plays exact, 11 heldout matches / 295
accepted opponent events, 2.975055 active emulator-hours.
Phase A is not complete. pool-scale-report.json records this timestamped snapshot.

Throughput: audited old driver 26.55 matches/hour (103 matches over
3.880 hours from first capture to final hub acknowledgement).
Three-renderer window: 13 verified completions over 10.29
minutes = 75.84 matches/hour (2.86x). This short window includes
in-flight work on the first two renderers at its start; match lengths vary.
At 26.82 accepted opponent events per heldout match, estimated coverage needs
about 560 total matches / 440 more, approximately 5.8
hours (ETA 2026-10-08T04:26:57.218973-07:00); use roughly 6–8 hours as an early
planning range. Counts only were used. Projected active time at that coverage is
13.9 hours, below the unchanged
36-hour cap. The scheduler enforces the actual count/cap rule, not this ETA.

Headroom: CPU idle samples 40.83%, 50.57%, 52.81%;
memory_pressure reports 30% free and kernel level 2 (warning,
not critical). Three renderers coexist with untouched UTM PID 76247.
Global buffer 234,252,365 bytes / 6,000,000,000; free disk
20.80 GiB / 15 GiB floor. Reservations total
1,200 MiB for three active matches, with larger finalization bounds reserved as
needed. Evidence: pool-headroom-20261007.txt and pool-processes-20261007.txt.

### Pool Resume (authoritative)

Read pool-state.json, pool-control.json, pool-phase-a-20261007-retry2-once.log and its exit
file first. Worker PIDs and active seeds change every match. Do not start the old
pipeline.py or standalone shipper while this pool is alive. The scheduler holds
pipeline.lock and collector.lock; workers additionally hold per-instance locks.
SIGTERM to the verified scheduler PID drains and ships all current matches before
exit. Verify PID, start time and command before signaling; never signal by pattern.
On failure, preserve buffered artifacts and inspect per-match *-exit.json/logs.
Resume automatically ships completed buffered matches and reclaims incomplete seeds;
check the FPS in any completed buffered receipt before resuming after a crash and
retain a prior scale-back count. Source/registration and original smoke gates are
checked on restart. Do not refreeze the frozen split or original source manifest.

Resume ONLY when the scheduler and every prior worker have exited:

~~~sh
ssh macmini-fleet
cd /Users/sam/Desktop/code/clasher
.venv/bin/python -B - <<'PY'
from pathlib import Path
import json, subprocess, time
v=Path("reports/strategy_council_20260928/live-loop/v4")
state=json.loads((v/"pool-state.json").read_text())
for pid in [state["pid"],*[x.get("pid") for x in state["claims"].values()]]:
    if pid:
        r=subprocess.run(["/bin/ps","-p",str(pid),"-o","command="],capture_output=True,text=True)
        if r.returncode==0 and "pool.py" in r.stdout:
            raise SystemExit(f"Pool process {pid} is still alive; do not duplicate it")
label="pool-resume-"+time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())
with (v/(label+".log")).open("a") as log:
    p=subprocess.Popen([str(v/"run.sh"),label,".venv/bin/python","-B","-u",str(v/"pool.py")],
        stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print("wrapper PID",p.pid,"log",v/(label+".log"))
PY
~~~

Read-only counts: .venv/bin/python -B scripts/collect_l1_stream_v4.py --status.
Current desired count and receipt paths are in pool-control.json. A persisted
scale_back_count in pool-state.json limits future restarts; do not silently clear
it or re-admit a failed concurrency level. If an owned renderer died, invoke
launch.py NEW_RECEIPT_DIRECTORY --instance N through run.sh at nice 10, update only
that instance's receipt path in pool-control.json, and apply the same first-match
admission gate. For an interrupted owned launch, use a fresh NEW directory and
--resume-owned PREVIOUS_LAUNCH_DIRECTORY. Never kill a shared adb server.

2026-10-07 22:38:56 -0700: Pool renderer-3 v4-phase-a-1975100819: 19.999 FPS, 56/56 exact plays; hub verified 21890854 bytes; pass=True.

2026-10-07 22:38:58 -0700: Pool renderer-1 v4-phase-a-1975100821: 19.997 FPS, 32/32 exact plays; hub verified 9433820 bytes; pass=True.

2026-10-07 22:41:01 -0700: Pool renderer-1 v4-phase-a-1975100823: 19.995 FPS, 38/38 exact plays; hub verified 11299656 bytes; pass=True.

2026-10-07 22:41:07 -0700: Pool renderer-3 v4-phase-a-1975100824: 19.998 FPS, 50/50 exact plays; hub verified 10788335 bytes; pass=True.

2026-10-07 22:41:12 -0700: Pool renderer-2 v4-phase-a-1975100822: 19.996 FPS, 60/60 exact plays; hub verified 15023277 bytes; pass=True.

2026-10-07 22:42:53 -0700: Pool renderer-1 v4-phase-a-1975100825: 19.991 FPS, 28/28 exact plays; hub verified 6784693 bytes; pass=True.

2026-10-07 22:43:37 -0700: Pool renderer-2 v4-phase-a-1975100827: 19.997 FPS, 58/58 exact plays; hub verified 17084602 bytes; pass=True.

2026-10-07 22:44:06 -0700: Pool renderer-3 v4-phase-a-1975100826: 19.996 FPS, 54/54 exact plays; hub verified 21714246 bytes; pass=True.

2026-10-07 22:44:33 -0700: Pool renderer-1 v4-phase-a-1975100828: 20.000 FPS, 42/42 exact plays; hub verified 9521084 bytes; pass=True.

2026-10-07 22:45:11 -0700: Pool renderer-2 v4-phase-a-1975100829: 19.993 FPS, 27/27 exact plays; hub verified 7229204 bytes; pass=True.

2026-10-07 22:46:18 -0700: Pool renderer-3 v4-phase-a-1975100830: 19.947 FPS, 46/46 exact plays; hub verified 11606940 bytes; pass=True.

2026-10-07 22:46:43 -0700: Pool renderer-1 v4-phase-a-1975100831: 19.924 FPS, 44/44 exact plays; hub verified 11362548 bytes; pass=True.

2026-10-07 22:46:44 -0700: Pool renderer-2 v4-phase-a-1975100832: 19.986 FPS, 15/15 exact plays; hub verified 3603970 bytes; pass=True.

2026-10-07 22:48:26 -0700: Pool renderer-2 v4-phase-a-1975100835: 19.967 FPS, 27/27 exact plays; hub verified 8886132 bytes; pass=True.

2026-10-07 22:49:11 -0700: Pool renderer-1 v4-phase-a-1975100834: 19.931 FPS, 62/62 exact plays; hub verified 17305630 bytes; pass=True.

2026-10-07 22:49:34 -0700: Pool renderer-3 v4-phase-a-1975100833: 19.969 FPS, 61/61 exact plays; hub verified 23851747 bytes; pass=True.

2026-10-07 22:50:02 -0700: Pool renderer-2 v4-phase-a-1975100836: 19.998 FPS, 22/22 exact plays; hub verified 7192674 bytes; pass=True.

2026-10-07 22:51:05 -0700: Pool renderer-1 v4-phase-a-1975100837: 19.992 FPS, 31/31 exact plays; hub verified 8786994 bytes; pass=True.

2026-10-07 22:51:43 -0700: Pool renderer-3 v4-phase-a-1975100838: 19.998 FPS, 42/42 exact plays; hub verified 10868059 bytes; pass=True.

2026-10-07 22:51:55 -0700: Pool renderer-2 v4-phase-a-1975100839: 19.931 FPS, 35/35 exact plays; hub verified 7584724 bytes; pass=True.

2026-10-07 22:53:35 -0700: Pool renderer-2 v4-phase-a-1975100842: 19.995 FPS, 37/37 exact plays; hub verified 9455846 bytes; pass=True.

2026-10-07 22:54:06 -0700: Pool renderer-3 v4-phase-a-1975100841: 19.955 FPS, 41/41 exact plays; hub verified 16941411 bytes; pass=True.

2026-10-07 22:54:44 -0700: Pool renderer-1 v4-phase-a-1975100840: 19.941 FPS, 72/72 exact plays; hub verified 26864193 bytes; pass=True.

2026-10-07 22:54:54 -0700: Pool scale-back: critical memory pressure; target 2.

2026-10-07 22:55:35 -0700: Pool renderer-2 v4-phase-a-1975100843: 19.107 FPS, 40/40 exact plays; hub verified 9936921 bytes; pass=False.

2026-10-07 22:55:35 -0700: Pool scale-back: per-match endpoint failed; target 1; completed evidence retained.

2026-10-07 22:55:45 -0700: Pool renderer-3 v4-phase-a-1975100844: 19.999 FPS, 19/19 exact plays; hub verified 6250973 bytes; pass=True.

2026-10-07 22:56:46 -0700: Pool renderer-1 v4-phase-a-1975100845: 19.837 FPS, 39/39 exact plays; hub verified 9337270 bytes; pass=True.

2026-10-07 22:58:39 -0700: Pool renderer-1 v4-phase-a-1975100846: 19.998 FPS, 28/28 exact plays; hub verified 6942702 bytes; pass=True.

2026-10-07 23:02:53 -0700: Pool renderer-1 v4-phase-a-1975100847: 19.999 FPS, 118/118 exact plays; hub verified 35419229 bytes; pass=True.

2026-10-07 23:05:20 -0700: Pool renderer-1 v4-phase-a-1975100848: 19.998 FPS, 56/56 exact plays; hub verified 16173076 bytes; pass=True.

2026-10-07 23:07:35 -0700: Pool renderer-1 v4-phase-a-1975100849: 19.999 FPS, 54/54 exact plays; hub verified 15472467 bytes; pass=True.

2026-10-07 23:08:44 -0700: Pool renderer-1 v4-phase-a-1975100850: 19.994 FPS, 11/11 exact plays; hub verified 2929874 bytes; pass=True.

2026-10-07 23:11:16 -0700: Pool renderer-1 v4-phase-a-1975100851: 20.000 FPS, 59/59 exact plays; hub verified 15321916 bytes; pass=True.

2026-10-07 23:13:25 -0700: Pool renderer-1 v4-phase-a-1975100852: 19.994 FPS, 46/46 exact plays; hub verified 11116243 bytes; pass=True.

2026-10-07 23:15:05 -0700: Pool renderer-1 v4-phase-a-1975100853: 19.998 FPS, 22/22 exact plays; hub verified 5649960 bytes; pass=True.

2026-10-07 23:18:06 -0700: Pool renderer-1 v4-phase-a-1975100854: 19.998 FPS, 63/63 exact plays; hub verified 21540624 bytes; pass=True.

2026-10-07 23:20:33 -0700: Pool renderer-1 v4-phase-a-1975100855: 19.997 FPS, 44/44 exact plays; hub verified 17124360 bytes; pass=True.

2026-10-07 23:22:16 -0700: Pool renderer-1 v4-phase-a-1975100856: 19.999 FPS, 39/39 exact plays; hub verified 10267607 bytes; pass=True.

2026-10-07 23:24:59 -0700: Pool renderer-1 v4-phase-a-1975100857: 19.998 FPS, 77/77 exact plays; hub verified 18670158 bytes; pass=True.

2026-10-07 23:26:49 -0700: Pool renderer-1 v4-phase-a-1975100858: 19.985 FPS, 30/30 exact plays; hub verified 8575431 bytes; pass=True.

2026-10-07 23:28:56 -0700: Pool renderer-1 v4-phase-a-1975100859: 19.999 FPS, 40/40 exact plays; hub verified 10529102 bytes; pass=True.

2026-10-07 23:30:50 -0700: Pool renderer-1 v4-phase-a-1975100860: 19.995 FPS, 30/30 exact plays; hub verified 8061490 bytes; pass=True.

2026-10-07 23:33:50 -0700: Pool renderer-1 v4-phase-a-1975100861: 19.996 FPS, 54/54 exact plays; hub verified 22260312 bytes; pass=True.

2026-10-07 23:36:15 -0700: Pool renderer-1 v4-phase-a-1975100862: 19.996 FPS, 52/52 exact plays; hub verified 15544805 bytes; pass=True.

2026-10-07 23:38:49 -0700: Pool renderer-1 v4-phase-a-1975100863: 19.998 FPS, 55/55 exact plays; hub verified 18181168 bytes; pass=True.

2026-10-07 23:41:28 -0700: Pool renderer-1 v4-phase-a-1975100864: 19.999 FPS, 91/91 exact plays; hub verified 17710102 bytes; pass=True.


## Operational one-time two-renderer retry, 2026-10-07T23:42:52.942136-07:00

Coordinator decision recorded before inspecting any labels' content, outcomes or
model outputs: retry two owned offline renderers ONCE after cleanly draining the
current scheduler. The prior critical-pressure transition at 22:54:54 PDT and
renderer-2 match 1975100843 at 19.107 FPS remain retained and counted.
Set max_count to 2, mark retry_used=true, and reset the previous one-renderer limit
only for this authorized retry. If any subsequent match fails a per-match endpoint,
or memory pressure becomes critical, return to ONE renderer for the remainder of
Phase A. Drain in-flight matches, preserve evidence, stop only verified excess
owned renderers, persist scale_back_count=1, and never ramp up again, including
after restart. Critical pressure is checked even when a limit already exists.
No second retry is authorized.

Only operational pool code/registration and controls change, with regression tests.
The frozen split, original source manifest/smoke admission, APK, hook, attestation,
offline UID isolation, collection endpoints, coverage rule and 36 active-hour cap
remain unchanged. No labels' content is inspected. Other projects' VMs/emulators
and shared adb servers remain untouched. Archive: pool-retry-2-20261007/.

2026-10-07 23:43:59 -0700: Pool renderer-1 v4-phase-a-1975100865: 19.998 FPS, 70/70 exact plays; hub verified 15194018 bytes; pass=True.

2026-10-07 23:43:59 -0700: Pool stopped: SIGTERM drain

2026-10-07 23:46:13 -0700: One-time retry launched: pool-phase-a-20261007-retry2-once, wrapper PID 22770; retry_used=true, max_count=2. Any endpoint failure/critical pressure permanently limits Phase A to one; no further retry.

### One-time retry operating snapshot (2026-10-07 23:46 PDT; monitoring)

Scheduler 24088 was verified by exact command/start and sent SIGTERM at 23:42:52.
It drained match 1975100865 (19.998 FPS, 70/70 exact plays, hub verified), then
scheduler/worker/wrapper exited; wrapper exit 0 and empty claims were checked.
All logs, exits, prior sources/control/state/manifest remain preserved in place or
under pool-retry-2-20261007/. No prior evidence was deleted.

Renderer-2's former PID 21497 was absent. launch.py --instance 2 completed under
fresh receipt emulator-host/pool-renderer-2-retry2-20261007/complete.json, PID 21614.
Renderer-1 PID 28907 remains owned. Both pass the unchanged attestation, read-only
AVD/host GPU and IPv4+IPv6 UID REJECT checks. No other VM/emulator/adb was signaled.

Detached launch uses the Pool Resume Python/Popen command above with fresh label
pool-phase-a-20261007-retry2-once: wrapper 22770, scheduler 22771.
Read this label's .log/.exit and pool-state.json before any resume. Do not reset
retry_used or scale_back_count again. max_count is 2; a fallback to 1 is permanent
through all restarts for the rest of Phase A. Never launch the old serial pipeline.
Eight pool tests passed; output is pool-retry-2-20261007/unit-tests.txt.
New operational manifest SHA256:
1674279ab234fa5c1f58e4a57271c35e428fbe826b80d4ba6eb1d78561548a72.
Its seven-file registration was checksum-verified on 127x01. Original freeze,
split, smoke admission, renderer code and thresholds remain unchanged.

2026-10-07 23:48:07 -0700: Pool renderer-2 v4-phase-a-1975100867: 20.000 FPS, 32/32 exact plays; hub verified 6828034 bytes; pass=True.

2026-10-07 23:48:22 -0700: Pool renderer-1 v4-phase-a-1975100866: 19.990 FPS, 44/44 exact plays; hub verified 11955889 bytes; pass=True.

First retry-match gates independently verified on 127x01: renderer-1 1975100866, 19.989692 FPS, 44/44 exact accepted plays, 11/11 file hashes, 11,955,889 bytes; renderer-2 1975100867, 19.999795 FPS, 32/32 exact accepted plays, 11/11 file hashes, 6,828,034 bytes. Both pass. Evidence: pool-retry-2-20261007/first-match-hub-recheck.json.

2026-10-07 23:50:47 -0700: Pool renderer-1 v4-phase-a-1975100869: 19.996 FPS, 52/52 exact plays; hub verified 17250932 bytes; pass=True.

2026-10-07 23:51:08 -0700: Pool renderer-2 v4-phase-a-1975100868: 20.000 FPS, 71/71 exact plays; hub verified 21940666 bytes; pass=True.

2026-10-07 23:52:54 -0700: Pool renderer-1 v4-phase-a-1975100870: 20.000 FPS, 50/50 exact plays; hub verified 14388308 bytes; pass=True.

2026-10-07 23:54:04 -0700: Pool renderer-2 v4-phase-a-1975100871: 19.998 FPS, 102/102 exact plays; hub verified 20104069 bytes; pass=True.

2026-10-07 23:54:22 -0700: Pool renderer-1 v4-phase-a-1975100872: 19.999 FPS, 17/17 exact plays; hub verified 5033572 bytes; pass=True.

2026-10-07 23:56:12 -0700: Pool renderer-2 v4-phase-a-1975100873: 20.000 FPS, 53/53 exact plays; hub verified 10891577 bytes; pass=True.

2026-10-07 23:56:14 -0700: Pool renderer-1 v4-phase-a-1975100874: 19.999 FPS, 32/32 exact plays; hub verified 7201751 bytes; pass=True.

2026-10-07 23:58:18 -0700: Pool renderer-1 v4-phase-a-1975100875: 19.997 FPS, 30/30 exact plays; hub verified 14676436 bytes; pass=True.

2026-10-07 23:58:40 -0700: Pool renderer-2 v4-phase-a-1975100876: 19.996 FPS, 47/47 exact plays; hub verified 16088869 bytes; pass=True.

### One-time retry 15-minute checkpoint (2026-10-08T00:01:13.671887-07:00)

Phase A remains RUNNING. Label pool-phase-a-20261007-retry2-once, wrapper PID 22770,
scheduler PID 22771; renderer PIDs 28907 and 21614.
Control max_count=2; retry_used=true, scale_back_count=None.
The current Pool Resume command above remains authoritative; preserve these fields
on every restart. Any endpoint failure or critical memory pressure permanently
reduces Phase A to one. No further retry is authorized.

The first 15 minutes produced 11 hub-verified matches, all
11/11 passing; FPS range
19.989692–19.999897.
Throughput 44.00 matches/hour, including fresh-match startup and shipping.
Both first-match independent 11-file hub rechecks passed (details above).
No critical-memory or endpoint scale-back occurred in this window.

Counts: 177 Phase A matches / 177 hub verified;
174/177 FPS passes (three historical failures retained);
8562/8562 accepted plays exact;
17 heldout matches / 426 accepted opponent events;
4.333626 active emulator-hours. Completed+claimed seed union is a
unique contiguous prefix of the frozen schedule; no duplicate/skipped seeds.

At 15 minutes: kernel pressure 2 (2=warning, 4=critical);
System-wide memory free percentage: 29%; vm.swapusage: total = 11264.00M  used = 10377.00M  free = 887.00M  (encrypted).
Global buffer 305,915,057 bytes / 6,000,000,000;
free disk 23.05 GiB / 15 GiB floor.
Other projects' VMs and shared adb servers were untouched.

Receipt-count-only projection: 25.06 accepted opponent events per heldout match,
approximately 423 further scheduled matches to reach heldout >=1500 events
AND >=20 matches; 9.61 hours at this window's 44.00 matches/hour,
ETA 2026-10-08T09:38:02.904162-07:00. Projected active total
14.69 hours, below the unchanged
36-hour cap. Short-window estimate only; actual count/cap rule controls stopping.
Evidence: pool-retry-2-20261007/report.json, monitor.jsonl, 15-minute-sample.json,
15-minute-status.json, first-match-hub-recheck.json, final-processes.txt and unit-tests.txt.
No APK/hook/attestation changes, labels-content inspection, or git commits.

2026-10-08 00:01:35 -0700: Pool renderer-2 v4-phase-a-1975100878: 19.998 FPS, 76/76 exact plays; hub verified 21981433 bytes; pass=True.

2026-10-08 00:02:00 -0700: Pool renderer-1 v4-phase-a-1975100877: 19.999 FPS, 127/127 exact plays; hub verified 30500836 bytes; pass=True.

2026-10-08 00:03:20 -0700: Pool renderer-2 v4-phase-a-1975100879: 19.999 FPS, 22/22 exact plays; hub verified 7887745 bytes; pass=True.

2026-10-08 00:03:25 -0700: Pool renderer-1 v4-phase-a-1975100880: 19.965 FPS, 14/14 exact plays; hub verified 3730373 bytes; pass=True.

2026-10-08 00:05:12 -0700: Pool renderer-2 v4-phase-a-1975100881: 19.943 FPS, 26/26 exact plays; hub verified 7595576 bytes; pass=True.

2026-10-08 00:06:24 -0700: Pool renderer-1 v4-phase-a-1975100882: 19.984 FPS, 61/61 exact plays; hub verified 23612873 bytes; pass=True.

2026-10-08 00:08:48 -0700: Pool renderer-2 v4-phase-a-1975100883: 20.000 FPS, 111/111 exact plays; hub verified 27703952 bytes; pass=True.

2026-10-08 00:08:51 -0700: Pool renderer-1 v4-phase-a-1975100884: 19.997 FPS, 64/64 exact plays; hub verified 15514321 bytes; pass=True.

2026-10-08 00:10:05 -0700: Pool renderer-1 v4-phase-a-1975100885: 19.988 FPS, 16/16 exact plays; hub verified 4053576 bytes; pass=True.

2026-10-08 00:11:22 -0700: Pool renderer-2 v4-phase-a-1975100886: 19.999 FPS, 75/75 exact plays; hub verified 15323543 bytes; pass=True.

2026-10-08 00:12:14 -0700: Pool renderer-1 v4-phase-a-1975100887: 20.000 FPS, 58/58 exact plays; hub verified 10503951 bytes; pass=True.

2026-10-08 00:13:02 -0700: Pool renderer-2 v4-phase-a-1975100888: 19.997 FPS, 21/21 exact plays; hub verified 5929779 bytes; pass=True.

2026-10-08 00:14:47 -0700: Pool renderer-1 v4-phase-a-1975100889: 19.998 FPS, 44/44 exact plays; hub verified 19648009 bytes; pass=True.

2026-10-08 00:15:26 -0700: Pool renderer-2 v4-phase-a-1975100890: 19.997 FPS, 53/53 exact plays; hub verified 16432549 bytes; pass=True.

2026-10-08 00:17:35 -0700: Pool renderer-1 v4-phase-a-1975100891: 19.995 FPS, 71/71 exact plays; hub verified 19442004 bytes; pass=True.

2026-10-08 00:18:22 -0700: Pool renderer-2 v4-phase-a-1975100892: 19.998 FPS, 80/80 exact plays; hub verified 20853157 bytes; pass=True.

2026-10-08 00:19:41 -0700: Pool renderer-1 v4-phase-a-1975100893: 19.994 FPS, 44/44 exact plays; hub verified 11214389 bytes; pass=True.

2026-10-08 00:20:09 -0700: Pool renderer-2 v4-phase-a-1975100894: 19.990 FPS, 35/35 exact plays; hub verified 7271875 bytes; pass=True.

2026-10-08 00:21:33 -0700: Pool renderer-1 v4-phase-a-1975100895: 19.990 FPS, 31/31 exact plays; hub verified 7170020 bytes; pass=True.

2026-10-08 00:23:46 -0700: Pool renderer-1 v4-phase-a-1975100897: 20.000 FPS, 45/45 exact plays; hub verified 15266260 bytes; pass=True.

2026-10-08 00:24:27 -0700: Pool renderer-2 v4-phase-a-1975100896: 19.998 FPS, 119/119 exact plays; hub verified 33716715 bytes; pass=True.

2026-10-08 00:25:25 -0700: Pool renderer-1 v4-phase-a-1975100898: 19.996 FPS, 34/34 exact plays; hub verified 9852816 bytes; pass=True.

2026-10-08 00:27:22 -0700: Pool renderer-2 v4-phase-a-1975100899: 20.000 FPS, 80/80 exact plays; hub verified 21844124 bytes; pass=True.

2026-10-08 00:27:56 -0700: Pool renderer-1 v4-phase-a-1975100900: 19.997 FPS, 62/62 exact plays; hub verified 14782245 bytes; pass=True.

2026-10-08 00:29:31 -0700: Pool renderer-2 v4-phase-a-1975100901: 20.000 FPS, 46/46 exact plays; hub verified 10745912 bytes; pass=True.

2026-10-08 00:29:49 -0700: Pool renderer-1 v4-phase-a-1975100902: 19.990 FPS, 37/37 exact plays; hub verified 7138150 bytes; pass=True.

2026-10-08 00:32:18 -0700: Pool renderer-1 v4-phase-a-1975100904: 19.999 FPS, 51/51 exact plays; hub verified 17430723 bytes; pass=True.

2026-10-08 00:32:29 -0700: Pool renderer-2 v4-phase-a-1975100903: 19.986 FPS, 70/70 exact plays; hub verified 22092662 bytes; pass=True.

2026-10-08 00:34:17 -0700: Pool renderer-1 v4-phase-a-1975100905: 19.959 FPS, 36/36 exact plays; hub verified 12820578 bytes; pass=True.

2026-10-08 00:35:14 -0700: Pool renderer-2 v4-phase-a-1975100906: 20.000 FPS, 85/85 exact plays; hub verified 19625900 bytes; pass=True.

2026-10-08 00:36:22 -0700: Pool renderer-1 v4-phase-a-1975100907: 19.999 FPS, 43/43 exact plays; hub verified 10268258 bytes; pass=True.

2026-10-08 00:37:22 -0700: Pool renderer-2 v4-phase-a-1975100908: 20.000 FPS, 55/55 exact plays; hub verified 11550818 bytes; pass=True.

2026-10-08 00:38:13 -0700: Pool renderer-1 v4-phase-a-1975100909: 19.993 FPS, 33/33 exact plays; hub verified 7642867 bytes; pass=True.

2026-10-08 00:40:40 -0700: Pool renderer-1 v4-phase-a-1975100911: 19.999 FPS, 54/54 exact plays; hub verified 16506399 bytes; pass=True.

2026-10-08 00:40:47 -0700: Pool renderer-2 v4-phase-a-1975100910: 20.000 FPS, 65/65 exact plays; hub verified 27083411 bytes; pass=True.

2026-10-08 00:42:18 -0700: Pool renderer-1 v4-phase-a-1975100912: 19.996 FPS, 29/29 exact plays; hub verified 8900730 bytes; pass=True.

2026-10-08 00:43:02 -0700: Pool renderer-2 v4-phase-a-1975100913: 19.998 FPS, 58/58 exact plays; hub verified 13928595 bytes; pass=True.

2026-10-08 00:44:38 -0700: Pool renderer-2 v4-phase-a-1975100915: 20.000 FPS, 23/23 exact plays; hub verified 4982690 bytes; pass=True.

2026-10-08 00:44:49 -0700: Pool renderer-1 v4-phase-a-1975100914: 19.997 FPS, 69/69 exact plays; hub verified 15515636 bytes; pass=True.

2026-10-08 00:46:30 -0700: Pool renderer-2 v4-phase-a-1975100916: 19.996 FPS, 26/26 exact plays; hub verified 7097740 bytes; pass=True.

2026-10-08 00:48:56 -0700: Pool renderer-2 v4-phase-a-1975100918: 19.997 FPS, 55/55 exact plays; hub verified 17575682 bytes; pass=True.

2026-10-08 00:49:14 -0700: Pool renderer-1 v4-phase-a-1975100917: 19.998 FPS, 104/104 exact plays; hub verified 33925714 bytes; pass=True.

2026-10-08 00:50:35 -0700: Pool renderer-2 v4-phase-a-1975100919: 19.996 FPS, 26/26 exact plays; hub verified 9094930 bytes; pass=True.

2026-10-08 00:50:40 -0700: Pool renderer-1 v4-phase-a-1975100920: 19.990 FPS, 17/17 exact plays; hub verified 5704512 bytes; pass=True.

2026-10-08 00:52:12 -0700: Pool renderer-2 v4-phase-a-1975100921: 20.000 FPS, 21/21 exact plays; hub verified 6156364 bytes; pass=True.

2026-10-08 00:52:23 -0700: Pool renderer-1 v4-phase-a-1975100922: 19.980 FPS, 30/30 exact plays; hub verified 6300496 bytes; pass=True.

2026-10-08 00:53:47 -0700: Pool renderer-2 v4-phase-a-1975100923: 19.995 FPS, 22/22 exact plays; hub verified 4507504 bytes; pass=True.

2026-10-08 00:55:20 -0700: Pool renderer-1 v4-phase-a-1975100924: 20.000 FPS, 55/55 exact plays; hub verified 21218242 bytes; pass=True.

2026-10-08 00:56:12 -0700: Pool renderer-2 v4-phase-a-1975100925: 19.999 FPS, 46/46 exact plays; hub verified 16323250 bytes; pass=True.

2026-10-08 00:58:05 -0700: Pool renderer-1 v4-phase-a-1975100926: 19.999 FPS, 79/79 exact plays; hub verified 18314299 bytes; pass=True.

2026-10-08 00:59:06 -0700: Pool renderer-2 v4-phase-a-1975100927: 20.000 FPS, 90/90 exact plays; hub verified 19048455 bytes; pass=True.

2026-10-08 01:00:36 -0700: Pool renderer-1 v4-phase-a-1975100928: 19.996 FPS, 78/78 exact plays; hub verified 15915320 bytes; pass=True.

2026-10-08 01:01:13 -0700: Pool renderer-2 v4-phase-a-1975100929: 19.994 FPS, 36/36 exact plays; hub verified 10282894 bytes; pass=True.

2026-10-08 01:02:14 -0700: Pool renderer-1 v4-phase-a-1975100930: 19.992 FPS, 20/20 exact plays; hub verified 4721292 bytes; pass=True.

2026-10-08 01:04:08 -0700: Pool renderer-2 v4-phase-a-1975100931: 19.996 FPS, 53/53 exact plays; hub verified 20438002 bytes; pass=True.

2026-10-08 01:04:40 -0700: Pool renderer-1 v4-phase-a-1975100932: 19.995 FPS, 64/64 exact plays; hub verified 16393246 bytes; pass=True.

2026-10-08 01:06:19 -0700: Pool renderer-1 v4-phase-a-1975100934: 19.994 FPS, 28/28 exact plays; hub verified 7494932 bytes; pass=True.

2026-10-08 01:07:49 -0700: Pool renderer-2 v4-phase-a-1975100933: 19.999 FPS, 115/115 exact plays; hub verified 30140374 bytes; pass=True.

2026-10-08 01:08:41 -0700: Pool renderer-1 v4-phase-a-1975100935: 20.000 FPS, 67/67 exact plays; hub verified 16169999 bytes; pass=True.

2026-10-08 01:09:45 -0700: Pool renderer-2 v4-phase-a-1975100936: 19.996 FPS, 43/43 exact plays; hub verified 8974688 bytes; pass=True.

2026-10-08 01:10:35 -0700: Pool renderer-1 v4-phase-a-1975100937: 20.000 FPS, 33/33 exact plays; hub verified 7521761 bytes; pass=True.

2026-10-08 01:12:44 -0700: Pool renderer-2 v4-phase-a-1975100938: 20.000 FPS, 71/71 exact plays; hub verified 21145311 bytes; pass=True.

2026-10-08 01:12:59 -0700: Pool renderer-1 v4-phase-a-1975100939: 19.998 FPS, 36/36 exact plays; hub verified 15963894 bytes; pass=True.

2026-10-08 01:14:17 -0700: Pool renderer-1 v4-phase-a-1975100941: 20.000 FPS, 16/16 exact plays; hub verified 4093255 bytes; pass=True.

2026-10-08 01:16:03 -0700: Pool renderer-1 v4-phase-a-1975100942: 19.999 FPS, 32/32 exact plays; hub verified 7776719 bytes; pass=True.

2026-10-08 01:16:26 -0700: Pool renderer-2 v4-phase-a-1975100940: 19.999 FPS, 102/102 exact plays; hub verified 28174598 bytes; pass=True.

2026-10-08 01:18:11 -0700: Pool renderer-1 v4-phase-a-1975100943: 19.992 FPS, 45/45 exact plays; hub verified 11544794 bytes; pass=True.

2026-10-08 01:18:19 -0700: Pool renderer-2 v4-phase-a-1975100944: 19.996 FPS, 40/40 exact plays; hub verified 6810113 bytes; pass=True.

2026-10-08 01:20:43 -0700: Pool renderer-2 v4-phase-a-1975100946: 19.995 FPS, 50/50 exact plays; hub verified 17216976 bytes; pass=True.

2026-10-08 01:21:11 -0700: Pool renderer-1 v4-phase-a-1975100945: 19.999 FPS, 98/98 exact plays; hub verified 22108401 bytes; pass=True.

2026-10-08 01:22:20 -0700: Pool renderer-1 v4-phase-a-1975100948: 19.997 FPS, 10/10 exact plays; hub verified 2489984 bytes; pass=True.

2026-10-08 01:22:28 -0700: Pool renderer-2 v4-phase-a-1975100947: 19.996 FPS, 37/37 exact plays; hub verified 10290131 bytes; pass=True.

2026-10-08 01:24:19 -0700: Pool renderer-1 v4-phase-a-1975100949: 20.000 FPS, 37/37 exact plays; hub verified 10709943 bytes; pass=True.

2026-10-08 01:24:35 -0700: Pool renderer-2 v4-phase-a-1975100950: 19.995 FPS, 44/44 exact plays; hub verified 11242079 bytes; pass=True.

2026-10-08 01:26:12 -0700: Pool renderer-1 v4-phase-a-1975100951: 19.985 FPS, 28/28 exact plays; hub verified 6995129 bytes; pass=True.

2026-10-08 01:27:33 -0700: Pool renderer-2 v4-phase-a-1975100952: 19.996 FPS, 56/56 exact plays; hub verified 22590504 bytes; pass=True.

2026-10-08 01:28:46 -0700: Pool renderer-1 v4-phase-a-1975100953: 19.999 FPS, 70/70 exact plays; hub verified 18643085 bytes; pass=True.

2026-10-08 01:29:11 -0700: Pool renderer-2 v4-phase-a-1975100954: 19.995 FPS, 29/29 exact plays; hub verified 9601932 bytes; pass=True.

2026-10-08 01:30:42 -0700: Pool renderer-2 v4-phase-a-1975100956: 19.998 FPS, 23/23 exact plays; hub verified 5116912 bytes; pass=True.

2026-10-08 01:31:41 -0700: Pool renderer-1 v4-phase-a-1975100955: 19.997 FPS, 82/82 exact plays; hub verified 20031359 bytes; pass=True.

2026-10-08 01:32:50 -0700: Pool renderer-2 v4-phase-a-1975100957: 19.995 FPS, 50/50 exact plays; hub verified 11626120 bytes; pass=True.

2026-10-08 01:33:25 -0700: Pool renderer-1 v4-phase-a-1975100958: 20.000 FPS, 31/31 exact plays; hub verified 5810795 bytes; pass=True.

2026-10-08 01:35:47 -0700: Pool renderer-2 v4-phase-a-1975100959: 19.994 FPS, 79/79 exact plays; hub verified 20268786 bytes; pass=True.

2026-10-08 01:36:29 -0700: Pool renderer-1 v4-phase-a-1975100960: 19.997 FPS, 62/62 exact plays; hub verified 22933642 bytes; pass=True.

2026-10-08 01:38:06 -0700: Pool renderer-1 v4-phase-a-1975100962: 19.991 FPS, 25/25 exact plays; hub verified 6937887 bytes; pass=True.

2026-10-08 01:38:18 -0700: Pool renderer-2 v4-phase-a-1975100961: 19.994 FPS, 64/64 exact plays; hub verified 17281490 bytes; pass=True.

2026-10-08 01:39:57 -0700: Pool renderer-2 v4-phase-a-1975100964: 19.985 FPS, 23/23 exact plays; hub verified 5797667 bytes; pass=True.

2026-10-08 01:40:37 -0700: Pool renderer-1 v4-phase-a-1975100963: 19.996 FPS, 57/57 exact plays; hub verified 16556000 bytes; pass=True.

2026-10-08 01:41:49 -0700: Pool renderer-2 v4-phase-a-1975100965: 19.993 FPS, 27/27 exact plays; hub verified 6945262 bytes; pass=True.

2026-10-08 01:43:30 -0700: Pool renderer-1 v4-phase-a-1975100966: 20.000 FPS, 48/48 exact plays; hub verified 19381320 bytes; pass=True.

2026-10-08 01:44:14 -0700: Pool renderer-2 v4-phase-a-1975100967: 19.998 FPS, 48/48 exact plays; hub verified 17165385 bytes; pass=True.

2026-10-08 01:46:01 -0700: Pool renderer-1 v4-phase-a-1975100968: 19.997 FPS, 60/60 exact plays; hub verified 18264679 bytes; pass=True.

2026-10-08 01:46:39 -0700: Pool renderer-2 v4-phase-a-1975100969: 19.999 FPS, 58/58 exact plays; hub verified 14191656 bytes; pass=True.

2026-10-08 01:47:27 -0700: Pool renderer-1 v4-phase-a-1975100970: 19.998 FPS, 15/15 exact plays; hub verified 4320873 bytes; pass=True.

2026-10-08 01:48:48 -0700: Pool renderer-2 v4-phase-a-1975100971: 19.998 FPS, 52/52 exact plays; hub verified 12394048 bytes; pass=True.

2026-10-08 01:49:19 -0700: Pool renderer-1 v4-phase-a-1975100972: 19.977 FPS, 31/31 exact plays; hub verified 7186245 bytes; pass=True.

2026-10-08 01:51:16 -0700: Pool renderer-2 v4-phase-a-1975100973: 20.000 FPS, 42/42 exact plays; hub verified 18597952 bytes; pass=True.

2026-10-08 01:53:45 -0700: Pool renderer-1 v4-phase-a-1975100974: 20.000 FPS, 130/130 exact plays; hub verified 34427674 bytes; pass=True.

2026-10-08 01:54:04 -0700: Pool renderer-2 v4-phase-a-1975100975: 20.000 FPS, 67/67 exact plays; hub verified 22027010 bytes; pass=True.

2026-10-08 01:56:28 -0700: Pool renderer-1 v4-phase-a-1975100976: 19.998 FPS, 71/71 exact plays; hub verified 18877850 bytes; pass=True.

2026-10-08 01:56:36 -0700: Pool renderer-2 v4-phase-a-1975100977: 19.997 FPS, 66/66 exact plays; hub verified 17161257 bytes; pass=True.

2026-10-08 01:57:56 -0700: Pool renderer-1 v4-phase-a-1975100978: 19.987 FPS, 20/20 exact plays; hub verified 3693527 bytes; pass=True.

2026-10-08 01:58:28 -0700: Pool renderer-2 v4-phase-a-1975100979: 19.999 FPS, 26/26 exact plays; hub verified 6623256 bytes; pass=True.

2026-10-08 01:59:11 -0700: Pool renderer-1 v4-phase-a-1975100980: 19.996 FPS, 22/22 exact plays; hub verified 8334932 bytes; pass=True.

2026-10-08 02:00:54 -0700: Pool renderer-2 v4-phase-a-1975100981: 19.998 FPS, 51/51 exact plays; hub verified 17723647 bytes; pass=True.

2026-10-08 02:02:53 -0700: Pool renderer-1 v4-phase-a-1975100982: 19.998 FPS, 170/170 exact plays; hub verified 31582904 bytes; pass=True.

2026-10-08 02:03:06 -0700: Pool renderer-2 v4-phase-a-1975100983: 19.999 FPS, 59/59 exact plays; hub verified 12792568 bytes; pass=True.

2026-10-08 02:04:30 -0700: Pool renderer-2 v4-phase-a-1975100985: 19.980 FPS, 13/13 exact plays; hub verified 3014376 bytes; pass=True.

2026-10-08 02:05:12 -0700: Pool renderer-1 v4-phase-a-1975100984: 20.000 FPS, 53/53 exact plays; hub verified 12767031 bytes; pass=True.

2026-10-08 02:06:23 -0700: Pool renderer-2 v4-phase-a-1975100986: 19.983 FPS, 34/34 exact plays; hub verified 6723224 bytes; pass=True.

2026-10-08 02:08:11 -0700: Pool renderer-1 v4-phase-a-1975100987: 20.000 FPS, 68/68 exact plays; hub verified 22294954 bytes; pass=True.

2026-10-08 02:09:12 -0700: Pool renderer-2 v4-phase-a-1975100988: 20.000 FPS, 56/56 exact plays; hub verified 20615975 bytes; pass=True.

2026-10-08 02:10:15 -0700: Pool renderer-1 v4-phase-a-1975100989: 20.000 FPS, 46/46 exact plays; hub verified 13607224 bytes; pass=True.

2026-10-08 02:10:39 -0700: Pool renderer-2 v4-phase-a-1975100990: 19.989 FPS, 22/22 exact plays; hub verified 5579815 bytes; pass=True.

2026-10-08 02:11:35 -0700: Pool renderer-1 v4-phase-a-1975100991: 19.982 FPS, 12/12 exact plays; hub verified 3150582 bytes; pass=True.

2026-10-08 02:12:47 -0700: Pool renderer-2 v4-phase-a-1975100992: 19.993 FPS, 43/43 exact plays; hub verified 10901694 bytes; pass=True.

2026-10-08 02:13:09 -0700: Pool renderer-1 v4-phase-a-1975100993: 19.988 FPS, 18/18 exact plays; hub verified 4378631 bytes; pass=True.

2026-10-08 02:15:34 -0700: Pool renderer-1 v4-phase-a-1975100995: 19.992 FPS, 48/48 exact plays; hub verified 17138835 bytes; pass=True.

2026-10-08 02:16:18 -0700: Pool renderer-2 v4-phase-a-1975100994: 19.998 FPS, 73/73 exact plays; hub verified 27955247 bytes; pass=True.

2026-10-08 02:17:12 -0700: Pool renderer-1 v4-phase-a-1975100996: 19.990 FPS, 34/34 exact plays; hub verified 8905168 bytes; pass=True.

2026-10-08 02:19:12 -0700: Pool renderer-2 v4-phase-a-1975100997: 19.998 FPS, 89/89 exact plays; hub verified 19659465 bytes; pass=True.

2026-10-08 02:19:31 -0700: Pool renderer-1 v4-phase-a-1975100998: 19.996 FPS, 40/40 exact plays; hub verified 13690899 bytes; pass=True.

2026-10-08 02:20:50 -0700: Pool renderer-2 v4-phase-a-1975100999: 19.989 FPS, 25/25 exact plays; hub verified 5707158 bytes; pass=True.

2026-10-08 02:21:10 -0700: Pool renderer-1 v4-phase-a-1975101000: 19.997 FPS, 23/23 exact plays; hub verified 4885750 bytes; pass=True.

2026-10-08 02:23:34 -0700: Pool renderer-1 v4-phase-a-1975101002: 19.997 FPS, 62/62 exact plays; hub verified 16971269 bytes; pass=True.

2026-10-08 02:23:48 -0700: Pool renderer-2 v4-phase-a-1975101001: 19.996 FPS, 68/68 exact plays; hub verified 22039575 bytes; pass=True.

2026-10-08 02:25:48 -0700: Pool renderer-1 v4-phase-a-1975101003: 19.997 FPS, 51/51 exact plays; hub verified 14914337 bytes; pass=True.

2026-10-08 02:26:44 -0700: Pool renderer-2 v4-phase-a-1975101004: 19.998 FPS, 100/100 exact plays; hub verified 22780605 bytes; pass=True.

2026-10-08 02:28:19 -0700: Pool renderer-1 v4-phase-a-1975101005: 19.999 FPS, 66/66 exact plays; hub verified 17606973 bytes; pass=True.

2026-10-08 02:28:52 -0700: Pool renderer-2 v4-phase-a-1975101006: 20.000 FPS, 46/46 exact plays; hub verified 10315501 bytes; pass=True.

2026-10-08 02:30:10 -0700: Pool renderer-1 v4-phase-a-1975101007: 19.992 FPS, 31/31 exact plays; hub verified 7041781 bytes; pass=True.

2026-10-08 02:31:49 -0700: Pool renderer-2 v4-phase-a-1975101008: 19.998 FPS, 59/59 exact plays; hub verified 22389526 bytes; pass=True.

2026-10-08 02:32:34 -0700: Pool renderer-1 v4-phase-a-1975101009: 19.997 FPS, 51/51 exact plays; hub verified 15763763 bytes; pass=True.

2026-10-08 02:34:34 -0700: Pool renderer-2 v4-phase-a-1975101010: 20.000 FPS, 77/77 exact plays; hub verified 21409541 bytes; pass=True.

2026-10-08 02:34:45 -0700: Pool renderer-1 v4-phase-a-1975101011: 19.995 FPS, 47/47 exact plays; hub verified 11838159 bytes; pass=True.

2026-10-08 02:36:17 -0700: Pool renderer-2 v4-phase-a-1975101012: 20.000 FPS, 28/28 exact plays; hub verified 7457934 bytes; pass=True.

2026-10-08 02:36:18 -0700: Pool renderer-1 v4-phase-a-1975101013: 20.000 FPS, 19/19 exact plays; hub verified 4360947 bytes; pass=True.

2026-10-08 02:37:55 -0700: Pool renderer-1 v4-phase-a-1975101014: 19.999 FPS, 17/17 exact plays; hub verified 4277475 bytes; pass=True.

2026-10-08 02:40:19 -0700: Pool renderer-2 v4-phase-a-1975101015: 19.982 FPS, 97/97 exact plays; hub verified 30344421 bytes; pass=True.

2026-10-08 02:41:51 -0700: Pool renderer-1 v4-phase-a-1975101016: 20.000 FPS, 102/102 exact plays; hub verified 31009373 bytes; pass=True.

2026-10-08 02:42:18 -0700: Pool renderer-2 v4-phase-a-1975101017: 19.994 FPS, 42/42 exact plays; hub verified 13465166 bytes; pass=True.

2026-10-08 02:43:16 -0700: Pool renderer-1 v4-phase-a-1975101018: 19.984 FPS, 19/19 exact plays; hub verified 5296688 bytes; pass=True.

2026-10-08 02:43:46 -0700: Pool renderer-2 v4-phase-a-1975101019: 19.984 FPS, 19/19 exact plays; hub verified 4173924 bytes; pass=True.

2026-10-08 02:45:24 -0700: Pool renderer-1 v4-phase-a-1975101020: 20.000 FPS, 45/45 exact plays; hub verified 11326728 bytes; pass=True.

2026-10-08 02:45:39 -0700: Pool renderer-2 v4-phase-a-1975101021: 19.978 FPS, 30/30 exact plays; hub verified 7637952 bytes; pass=True.

2026-10-08 02:48:05 -0700: Pool renderer-2 v4-phase-a-1975101023: 20.000 FPS, 52/52 exact plays; hub verified 16471941 bytes; pass=True.

2026-10-08 02:48:23 -0700: Pool renderer-1 v4-phase-a-1975101022: 20.000 FPS, 72/72 exact plays; hub verified 21935385 bytes; pass=True.

2026-10-08 02:49:53 -0700: Pool renderer-2 v4-phase-a-1975101024: 19.992 FPS, 49/49 exact plays; hub verified 10994477 bytes; pass=True.

2026-10-08 02:50:22 -0700: Pool renderer-1 v4-phase-a-1975101025: 20.000 FPS, 49/49 exact plays; hub verified 10556287 bytes; pass=True.

2026-10-08 02:52:22 -0700: Pool renderer-2 v4-phase-a-1975101026: 20.000 FPS, 55/55 exact plays; hub verified 14933586 bytes; pass=True.

2026-10-08 02:52:23 -0700: Pool renderer-1 v4-phase-a-1975101027: 19.993 FPS, 37/37 exact plays; hub verified 8394851 bytes; pass=True.

2026-10-08 02:54:00 -0700: Pool renderer-1 v4-phase-a-1975101028: 19.989 FPS, 24/24 exact plays; hub verified 4621106 bytes; pass=True.

2026-10-08 02:54:58 -0700: Pool renderer-2 v4-phase-a-1975101029: 19.995 FPS, 47/47 exact plays; hub verified 18806938 bytes; pass=True.

2026-10-08 02:56:26 -0700: Pool renderer-1 v4-phase-a-1975101030: 19.994 FPS, 53/53 exact plays; hub verified 16583518 bytes; pass=True.

2026-10-08 02:56:37 -0700: Pool renderer-2 v4-phase-a-1975101031: 19.997 FPS, 32/32 exact plays; hub verified 9346733 bytes; pass=True.

2026-10-08 02:58:51 -0700: Pool renderer-2 v4-phase-a-1975101033: 19.996 FPS, 62/62 exact plays; hub verified 14384114 bytes; pass=True.

2026-10-08 02:59:22 -0700: Pool renderer-1 v4-phase-a-1975101032: 19.994 FPS, 107/107 exact plays; hub verified 21141348 bytes; pass=True.

2026-10-08 03:01:00 -0700: Pool renderer-2 v4-phase-a-1975101034: 19.993 FPS, 44/44 exact plays; hub verified 10105388 bytes; pass=True.

2026-10-08 03:01:14 -0700: Pool renderer-1 v4-phase-a-1975101035: 19.999 FPS, 34/34 exact plays; hub verified 7076322 bytes; pass=True.

2026-10-08 03:03:39 -0700: Pool renderer-1 v4-phase-a-1975101037: 19.998 FPS, 52/52 exact plays; hub verified 17699981 bytes; pass=True.

2026-10-08 03:03:59 -0700: Pool renderer-2 v4-phase-a-1975101036: 19.998 FPS, 67/67 exact plays; hub verified 21746005 bytes; pass=True.

2026-10-08 03:05:47 -0700: Pool renderer-1 v4-phase-a-1975101038: 19.996 FPS, 51/51 exact plays; hub verified 13894319 bytes; pass=True.

2026-10-08 03:05:58 -0700: Pool renderer-2 v4-phase-a-1975101039: 19.999 FPS, 35/35 exact plays; hub verified 10837919 bytes; pass=True.

2026-10-08 03:07:42 -0700: Pool renderer-2 v4-phase-a-1975101041: 19.991 FPS, 29/29 exact plays; hub verified 6727979 bytes; pass=True.

2026-10-08 03:08:08 -0700: Pool renderer-1 v4-phase-a-1975101040: 19.999 FPS, 56/56 exact plays; hub verified 13217339 bytes; pass=True.

2026-10-08 03:09:34 -0700: Pool renderer-2 v4-phase-a-1975101042: 20.000 FPS, 29/29 exact plays; hub verified 7433372 bytes; pass=True.

2026-10-08 03:11:05 -0700: Pool renderer-1 v4-phase-a-1975101043: 20.000 FPS, 58/58 exact plays; hub verified 21287386 bytes; pass=True.

2026-10-08 03:11:59 -0700: Pool renderer-2 v4-phase-a-1975101044: 19.998 FPS, 57/57 exact plays; hub verified 16105786 bytes; pass=True.

2026-10-08 03:12:44 -0700: Pool renderer-1 v4-phase-a-1975101045: 19.998 FPS, 37/37 exact plays; hub verified 9703017 bytes; pass=True.

2026-10-08 03:14:16 -0700: Pool renderer-2 v4-phase-a-1975101046: 20.000 FPS, 54/54 exact plays; hub verified 14468861 bytes; pass=True.

2026-10-08 03:15:15 -0700: Pool renderer-1 v4-phase-a-1975101047: 20.000 FPS, 68/68 exact plays; hub verified 16076622 bytes; pass=True.

2026-10-08 03:16:24 -0700: Pool renderer-2 v4-phase-a-1975101048: 19.989 FPS, 56/56 exact plays; hub verified 10540783 bytes; pass=True.

2026-10-08 03:16:54 -0700: Pool renderer-1 v4-phase-a-1975101049: 19.988 FPS, 27/27 exact plays; hub verified 5045067 bytes; pass=True.

2026-10-08 03:19:15 -0700: Pool renderer-2 v4-phase-a-1975101050: 19.996 FPS, 62/62 exact plays; hub verified 21013901 bytes; pass=True.

2026-10-08 03:19:18 -0700: Pool renderer-1 v4-phase-a-1975101051: 19.997 FPS, 53/53 exact plays; hub verified 16115132 bytes; pass=True.

2026-10-08 03:20:57 -0700: Pool renderer-1 v4-phase-a-1975101052: 19.999 FPS, 33/33 exact plays; hub verified 9822081 bytes; pass=True.

2026-10-08 03:22:13 -0700: Pool renderer-2 v4-phase-a-1975101053: 19.997 FPS, 70/70 exact plays; hub verified 19188036 bytes; pass=True.

2026-10-08 03:23:29 -0700: Pool renderer-1 v4-phase-a-1975101054: 20.000 FPS, 68/68 exact plays; hub verified 17152313 bytes; pass=True.

2026-10-08 03:24:22 -0700: Pool renderer-2 v4-phase-a-1975101055: 20.000 FPS, 39/39 exact plays; hub verified 11011341 bytes; pass=True.

2026-10-08 03:25:22 -0700: Pool renderer-1 v4-phase-a-1975101056: 19.999 FPS, 37/37 exact plays; hub verified 7750285 bytes; pass=True.

2026-10-08 03:26:21 -0700: Pool renderer-2 v4-phase-a-1975101057: 19.996 FPS, 46/46 exact plays; hub verified 14034588 bytes; pass=True.

2026-10-08 03:27:07 -0700: Pool renderer-1 v4-phase-a-1975101058: 19.996 FPS, 30/30 exact plays; hub verified 10861276 bytes; pass=True.

2026-10-08 03:29:02 -0700: Pool renderer-2 v4-phase-a-1975101059: 19.999 FPS, 70/70 exact plays; hub verified 20456768 bytes; pass=True.

2026-10-08 03:30:01 -0700: Pool renderer-1 v4-phase-a-1975101060: 19.997 FPS, 89/89 exact plays; hub verified 21682641 bytes; pass=True.

2026-10-08 03:31:34 -0700: Pool renderer-2 v4-phase-a-1975101061: 19.999 FPS, 64/64 exact plays; hub verified 17951033 bytes; pass=True.

2026-10-08 03:32:10 -0700: Pool renderer-1 v4-phase-a-1975101062: 19.997 FPS, 47/47 exact plays; hub verified 11002571 bytes; pass=True.

2026-10-08 03:33:27 -0700: Pool renderer-2 v4-phase-a-1975101063: 19.993 FPS, 36/36 exact plays; hub verified 7278646 bytes; pass=True.

2026-10-08 03:35:52 -0700: Pool renderer-2 v4-phase-a-1975101065: 20.000 FPS, 52/52 exact plays; hub verified 15812950 bytes; pass=True.

2026-10-08 03:36:16 -0700: Pool renderer-1 v4-phase-a-1975101064: 19.988 FPS, 92/92 exact plays; hub verified 30499198 bytes; pass=True.

2026-10-08 03:37:42 -0700: Pool renderer-2 v4-phase-a-1975101066: 19.993 FPS, 46/46 exact plays; hub verified 11003517 bytes; pass=True.

2026-10-08 03:38:07 -0700: Pool renderer-1 v4-phase-a-1975101067: 19.999 FPS, 34/34 exact plays; hub verified 10044392 bytes; pass=True.

2026-10-08 03:39:14 -0700: Pool renderer-2 v4-phase-a-1975101068: 19.989 FPS, 19/19 exact plays; hub verified 5246158 bytes; pass=True.

2026-10-08 03:40:15 -0700: Pool renderer-1 v4-phase-a-1975101069: 19.998 FPS, 50/50 exact plays; hub verified 11153949 bytes; pass=True.

2026-10-08 03:41:06 -0700: Pool renderer-2 v4-phase-a-1975101070: 19.997 FPS, 35/35 exact plays; hub verified 7344703 bytes; pass=True.

2026-10-08 03:43:31 -0700: Pool renderer-2 v4-phase-a-1975101072: 19.996 FPS, 44/44 exact plays; hub verified 17030473 bytes; pass=True.

2026-10-08 03:44:50 -0700: Pool renderer-1 v4-phase-a-1975101071: 19.999 FPS, 99/99 exact plays; hub verified 34860667 bytes; pass=True.

2026-10-08 03:45:11 -0700: Pool renderer-2 v4-phase-a-1975101073: 19.995 FPS, 30/30 exact plays; hub verified 9325294 bytes; pass=True.

2026-10-08 03:46:22 -0700: Pool renderer-1 v4-phase-a-1975101074: 19.995 FPS, 21/21 exact plays; hub verified 7125543 bytes; pass=True.

2026-10-08 03:46:37 -0700: Pool renderer-2 v4-phase-a-1975101075: 19.987 FPS, 15/15 exact plays; hub verified 3893151 bytes; pass=True.

2026-10-08 03:48:07 -0700: Pool renderer-2 v4-phase-a-1975101077: 19.999 FPS, 16/16 exact plays; hub verified 3346192 bytes; pass=True.

2026-10-08 03:48:29 -0700: Pool renderer-1 v4-phase-a-1975101076: 19.990 FPS, 47/47 exact plays; hub verified 10737434 bytes; pass=True.

2026-10-08 03:50:54 -0700: Pool renderer-1 v4-phase-a-1975101079: 20.000 FPS, 43/43 exact plays; hub verified 15522043 bytes; pass=True.

2026-10-08 03:51:05 -0700: Pool renderer-2 v4-phase-a-1975101078: 19.999 FPS, 57/57 exact plays; hub verified 24165981 bytes; pass=True.

2026-10-08 03:52:56 -0700: Pool renderer-2 v4-phase-a-1975101081: 19.999 FPS, 32/32 exact plays; hub verified 9156548 bytes; pass=True.

2026-10-08 03:54:37 -0700: Pool renderer-1 v4-phase-a-1975101080: 19.998 FPS, 132/132 exact plays; hub verified 31359167 bytes; pass=True.

2026-10-08 03:55:28 -0700: Pool renderer-2 v4-phase-a-1975101082: 19.999 FPS, 72/72 exact plays; hub verified 16431102 bytes; pass=True.

2026-10-08 03:56:45 -0700: Pool renderer-1 v4-phase-a-1975101083: 20.000 FPS, 39/39 exact plays; hub verified 11290371 bytes; pass=True.

2026-10-08 03:57:20 -0700: Pool renderer-2 v4-phase-a-1975101084: 19.997 FPS, 34/34 exact plays; hub verified 7302685 bytes; pass=True.

2026-10-08 03:59:44 -0700: Pool renderer-1 v4-phase-a-1975101085: 20.000 FPS, 65/65 exact plays; hub verified 21105286 bytes; pass=True.

2026-10-08 03:59:47 -0700: Pool renderer-2 v4-phase-a-1975101086: 19.980 FPS, 54/54 exact plays; hub verified 15977700 bytes; pass=True.

2026-10-08 04:01:06 -0700: Pool renderer-2 v4-phase-a-1975101088: 19.998 FPS, 15/15 exact plays; hub verified 4276590 bytes; pass=True.

2026-10-08 04:01:26 -0700: Pool renderer-1 v4-phase-a-1975101087: 19.997 FPS, 36/36 exact plays; hub verified 9836256 bytes; pass=True.

2026-10-08 04:03:02 -0700: Pool renderer-1 v4-phase-a-1975101090: 19.988 FPS, 23/23 exact plays; hub verified 5688160 bytes; pass=True.

2026-10-08 04:03:38 -0700: Pool renderer-2 v4-phase-a-1975101089: 19.997 FPS, 60/60 exact plays; hub verified 17394919 bytes; pass=True.

2026-10-08 04:04:54 -0700: Pool renderer-1 v4-phase-a-1975101091: 19.999 FPS, 33/33 exact plays; hub verified 7791545 bytes; pass=True.

2026-10-08 04:06:36 -0700: Pool renderer-2 v4-phase-a-1975101092: 19.999 FPS, 64/64 exact plays; hub verified 21145512 bytes; pass=True.

2026-10-08 04:08:14 -0700: Pool renderer-2 v4-phase-a-1975101094: 19.993 FPS, 36/36 exact plays; hub verified 9091831 bytes; pass=True.

2026-10-08 04:08:55 -0700: Pool renderer-1 v4-phase-a-1975101093: 19.996 FPS, 118/118 exact plays; hub verified 33617574 bytes; pass=True.

2026-10-08 04:10:13 -0700: Pool renderer-2 v4-phase-a-1975101095: 19.995 FPS, 37/37 exact plays; hub verified 11573326 bytes; pass=True.

2026-10-08 04:10:48 -0700: Pool renderer-1 v4-phase-a-1975101096: 19.994 FPS, 32/32 exact plays; hub verified 9494605 bytes; pass=True.

2026-10-08 04:12:21 -0700: Pool renderer-2 v4-phase-a-1975101097: 19.999 FPS, 44/44 exact plays; hub verified 10716904 bytes; pass=True.

2026-10-08 04:12:41 -0700: Pool renderer-1 v4-phase-a-1975101098: 19.994 FPS, 32/32 exact plays; hub verified 7583602 bytes; pass=True.

2026-10-08 04:15:06 -0700: Pool renderer-1 v4-phase-a-1975101100: 19.980 FPS, 51/51 exact plays; hub verified 16326584 bytes; pass=True.

2026-10-08 04:16:44 -0700: Pool renderer-1 v4-phase-a-1975101101: 20.000 FPS, 28/28 exact plays; hub verified 9049866 bytes; pass=True.

2026-10-08 04:17:20 -0700: Pool renderer-2 v4-phase-a-1975101099: 19.989 FPS, 114/114 exact plays; hub verified 39561023 bytes; pass=True.

2026-10-08 04:18:35 -0700: Pool renderer-2 v4-phase-a-1975101103: 19.825 FPS, 12/12 exact plays; hub verified 2718431 bytes; pass=True.

2026-10-08 04:19:04 -0700: Pool renderer-1 v4-phase-a-1975101102: 19.996 FPS, 45/45 exact plays; hub verified 13616248 bytes; pass=True.

2026-10-08 04:20:19 -0700: Pool renderer-2 v4-phase-a-1975101104: 19.993 FPS, 27/27 exact plays; hub verified 6815973 bytes; pass=True.

2026-10-08 04:20:56 -0700: Pool renderer-1 v4-phase-a-1975101105: 19.993 FPS, 29/29 exact plays; hub verified 7642434 bytes; pass=True.

2026-10-08 04:23:18 -0700: Pool renderer-2 v4-phase-a-1975101106: 20.000 FPS, 60/60 exact plays; hub verified 20334168 bytes; pass=True.

2026-10-08 04:23:21 -0700: Pool renderer-1 v4-phase-a-1975101107: 19.998 FPS, 57/57 exact plays; hub verified 15672378 bytes; pass=True.

2026-10-08 04:24:42 -0700: Pool renderer-2 v4-phase-a-1975101109: 19.991 FPS, 16/16 exact plays; hub verified 5164967 bytes; pass=True.

2026-10-08 04:25:01 -0700: Pool renderer-1 v4-phase-a-1975101108: 19.999 FPS, 33/33 exact plays; hub verified 9739897 bytes; pass=True.

2026-10-08 04:26:01 -0700: Pool renderer-2 v4-phase-a-1975101110: 19.994 FPS, 15/15 exact plays; hub verified 3175532 bytes; pass=True.

2026-10-08 04:27:10 -0700: Pool renderer-1 v4-phase-a-1975101111: 19.998 FPS, 44/44 exact plays; hub verified 10782617 bytes; pass=True.

2026-10-08 04:27:47 -0700: Pool renderer-2 v4-phase-a-1975101112: 19.979 FPS, 30/30 exact plays; hub verified 7111653 bytes; pass=True.

2026-10-08 04:30:06 -0700: Pool renderer-1 v4-phase-a-1975101113: 20.000 FPS, 69/69 exact plays; hub verified 20438036 bytes; pass=True.

2026-10-08 04:30:11 -0700: Pool renderer-2 v4-phase-a-1975101114: 19.999 FPS, 39/39 exact plays; hub verified 14790052 bytes; pass=True.

2026-10-08 04:31:54 -0700: Pool renderer-1 v4-phase-a-1975101115: 19.962 FPS, 42/42 exact plays; hub verified 10741771 bytes; pass=True.

2026-10-08 04:32:54 -0700: Pool renderer-2 v4-phase-a-1975101116: 20.000 FPS, 80/80 exact plays; hub verified 18721900 bytes; pass=True.

2026-10-08 04:34:25 -0700: Pool renderer-1 v4-phase-a-1975101117: 19.999 FPS, 71/71 exact plays; hub verified 14843954 bytes; pass=True.

2026-10-08 04:34:39 -0700: Pool renderer-2 v4-phase-a-1975101118: 19.985 FPS, 29/29 exact plays; hub verified 6970938 bytes; pass=True.

2026-10-08 04:36:12 -0700: Pool renderer-1 v4-phase-a-1975101119: 19.989 FPS, 26/26 exact plays; hub verified 6844778 bytes; pass=True.

2026-10-08 04:37:35 -0700: Pool renderer-2 v4-phase-a-1975101120: 19.998 FPS, 62/62 exact plays; hub verified 21032991 bytes; pass=True.

2026-10-08 04:38:37 -0700: Pool renderer-1 v4-phase-a-1975101121: 19.998 FPS, 55/55 exact plays; hub verified 16402682 bytes; pass=True.

2026-10-08 04:39:34 -0700: Pool renderer-2 v4-phase-a-1975101122: 19.996 FPS, 43/43 exact plays; hub verified 12672089 bytes; pass=True.

2026-10-08 04:41:19 -0700: Pool renderer-1 v4-phase-a-1975101123: 20.000 FPS, 64/64 exact plays; hub verified 16642790 bytes; pass=True.

2026-10-08 04:41:49 -0700: Pool renderer-2 v4-phase-a-1975101124: 19.964 FPS, 49/49 exact plays; hub verified 14011382 bytes; pass=True.

2026-10-08 04:43:00 -0700: Pool renderer-1 v4-phase-a-1975101125: 19.999 FPS, 25/25 exact plays; hub verified 6313251 bytes; pass=True.

2026-10-08 04:43:42 -0700: Pool renderer-2 v4-phase-a-1975101126: 19.991 FPS, 37/37 exact plays; hub verified 6901940 bytes; pass=True.

2026-10-08 04:46:06 -0700: Pool renderer-1 v4-phase-a-1975101127: 19.982 FPS, 63/63 exact plays; hub verified 22417589 bytes; pass=True.

2026-10-08 04:46:09 -0700: Pool renderer-2 v4-phase-a-1975101128: 19.995 FPS, 39/39 exact plays; hub verified 16681134 bytes; pass=True.

2026-10-08 04:47:48 -0700: Pool renderer-1 v4-phase-a-1975101129: 19.999 FPS, 34/34 exact plays; hub verified 9864059 bytes; pass=True.

2026-10-08 04:47:54 -0700: Pool renderer-2 v4-phase-a-1975101130: 19.994 FPS, 29/29 exact plays; hub verified 8481708 bytes; pass=True.

2026-10-08 04:50:01 -0700: Pool renderer-2 v4-phase-a-1975101132: 19.999 FPS, 44/44 exact plays; hub verified 11098233 bytes; pass=True.

2026-10-08 04:50:21 -0700: Pool renderer-1 v4-phase-a-1975101131: 19.998 FPS, 59/59 exact plays; hub verified 16119473 bytes; pass=True.

2026-10-08 04:51:40 -0700: Pool renderer-2 v4-phase-a-1975101133: 19.998 FPS, 22/22 exact plays; hub verified 5522384 bytes; pass=True.

2026-10-08 04:53:20 -0700: Pool renderer-1 v4-phase-a-1975101134: 19.998 FPS, 58/58 exact plays; hub verified 21045664 bytes; pass=True.

2026-10-08 04:53:24 -0700: Pool renderer-2 v4-phase-a-1975101135: 19.995 FPS, 27/27 exact plays; hub verified 11279394 bytes; pass=True.

2026-10-08 04:55:00 -0700: Pool renderer-2 v4-phase-a-1975101137: 19.992 FPS, 24/24 exact plays; hub verified 7822447 bytes; pass=True.

2026-10-08 04:55:49 -0700: Pool renderer-1 v4-phase-a-1975101136: 19.997 FPS, 69/69 exact plays; hub verified 18177000 bytes; pass=True.

2026-10-08 04:57:30 -0700: Pool renderer-2 v4-phase-a-1975101138: 19.996 FPS, 53/53 exact plays; hub verified 15517697 bytes; pass=True.

2026-10-08 04:57:57 -0700: Pool renderer-1 v4-phase-a-1975101139: 19.994 FPS, 51/51 exact plays; hub verified 11919944 bytes; pass=True.

2026-10-08 04:59:08 -0700: Pool renderer-2 v4-phase-a-1975101140: 19.988 FPS, 24/24 exact plays; hub verified 4459970 bytes; pass=True.

2026-10-08 05:01:33 -0700: Pool renderer-2 v4-phase-a-1975101142: 19.999 FPS, 47/47 exact plays; hub verified 15664164 bytes; pass=True.

2026-10-08 05:02:25 -0700: Pool renderer-1 v4-phase-a-1975101141: 19.999 FPS, 118/118 exact plays; hub verified 34402426 bytes; pass=True.

2026-10-08 05:03:11 -0700: Pool renderer-2 v4-phase-a-1975101143: 19.995 FPS, 33/33 exact plays; hub verified 9371324 bytes; pass=True.

2026-10-08 05:04:10 -0700: Pool renderer-1 v4-phase-a-1975101144: 19.995 FPS, 30/30 exact plays; hub verified 8381151 bytes; pass=True.

2026-10-08 05:05:03 -0700: Pool renderer-2 v4-phase-a-1975101145: 20.000 FPS, 28/28 exact plays; hub verified 8793637 bytes; pass=True.

2026-10-08 05:05:51 -0700: Pool renderer-1 v4-phase-a-1975101146: 19.989 FPS, 33/33 exact plays; hub verified 6561513 bytes; pass=True.

2026-10-08 05:06:55 -0700: Pool renderer-2 v4-phase-a-1975101147: 20.000 FPS, 33/33 exact plays; hub verified 6968642 bytes; pass=True.

2026-10-08 05:08:49 -0700: Pool renderer-1 v4-phase-a-1975101148: 19.998 FPS, 58/58 exact plays; hub verified 21489255 bytes; pass=True.

2026-10-08 05:09:21 -0700: Pool renderer-2 v4-phase-a-1975101149: 19.997 FPS, 53/53 exact plays; hub verified 15461384 bytes; pass=True.

2026-10-08 05:11:21 -0700: Pool renderer-2 v4-phase-a-1975101151: 20.000 FPS, 41/41 exact plays; hub verified 11278163 bytes; pass=True.

2026-10-08 05:11:44 -0700: Pool renderer-1 v4-phase-a-1975101150: 19.998 FPS, 72/72 exact plays; hub verified 20372532 bytes; pass=True.

2026-10-08 05:13:18 -0700: Pool renderer-1 v4-phase-a-1975101153: 19.993 FPS, 20/20 exact plays; hub verified 4519568 bytes; pass=True.

2026-10-08 05:13:52 -0700: Pool renderer-2 v4-phase-a-1975101152: 19.999 FPS, 55/55 exact plays; hub verified 15652214 bytes; pass=True.

2026-10-08 05:15:10 -0700: Pool renderer-1 v4-phase-a-1975101154: 19.995 FPS, 32/32 exact plays; hub verified 6622318 bytes; pass=True.

2026-10-08 05:16:51 -0700: Pool renderer-2 v4-phase-a-1975101155: 20.000 FPS, 55/55 exact plays; hub verified 22926677 bytes; pass=True.

2026-10-08 05:17:36 -0700: Pool renderer-1 v4-phase-a-1975101156: 19.997 FPS, 46/46 exact plays; hub verified 15634231 bytes; pass=True.

2026-10-08 05:18:30 -0700: Pool renderer-2 v4-phase-a-1975101157: 19.997 FPS, 33/33 exact plays; hub verified 9253188 bytes; pass=True.

2026-10-08 05:19:46 -0700: Pool renderer-1 v4-phase-a-1975101158: 19.995 FPS, 50/50 exact plays; hub verified 12172418 bytes; pass=True.

2026-10-08 05:20:28 -0700: Pool renderer-2 v4-phase-a-1975101159: 19.995 FPS, 44/44 exact plays; hub verified 9467590 bytes; pass=True.

2026-10-08 05:21:42 -0700: Pool renderer-1 v4-phase-a-1975101160: 19.994 FPS, 34/34 exact plays; hub verified 8899343 bytes; pass=True.

2026-10-08 05:22:21 -0700: Pool renderer-2 v4-phase-a-1975101161: 19.942 FPS, 28/28 exact plays; hub verified 6861880 bytes; pass=True.

2026-10-08 05:24:40 -0700: Pool renderer-1 v4-phase-a-1975101162: 19.998 FPS, 54/54 exact plays; hub verified 22645927 bytes; pass=True.

2026-10-08 05:24:47 -0700: Pool renderer-2 v4-phase-a-1975101163: 19.976 FPS, 51/51 exact plays; hub verified 15954480 bytes; pass=True.

2026-10-08 05:27:07 -0700: Pool renderer-1 v4-phase-a-1975101164: 19.999 FPS, 55/55 exact plays; hub verified 14738723 bytes; pass=True.

2026-10-08 05:27:42 -0700: Pool renderer-2 v4-phase-a-1975101165: 19.998 FPS, 92/92 exact plays; hub verified 18732043 bytes; pass=True.

2026-10-08 05:29:09 -0700: Pool renderer-2 v4-phase-a-1975101167: 19.999 FPS, 16/16 exact plays; hub verified 3398097 bytes; pass=True.

2026-10-08 05:29:24 -0700: Pool renderer-1 v4-phase-a-1975101166: 19.999 FPS, 58/58 exact plays; hub verified 13073162 bytes; pass=True.

2026-10-08 05:31:03 -0700: Pool renderer-2 v4-phase-a-1975101168: 19.992 FPS, 28/28 exact plays; hub verified 7617611 bytes; pass=True.

2026-10-08 05:32:23 -0700: Pool renderer-1 v4-phase-a-1975101169: 19.996 FPS, 57/57 exact plays; hub verified 22441345 bytes; pass=True.

2026-10-08 05:33:28 -0700: Pool renderer-2 v4-phase-a-1975101170: 19.998 FPS, 53/53 exact plays; hub verified 16721780 bytes; pass=True.

2026-10-08 05:34:28 -0700: Pool renderer-1 v4-phase-a-1975101171: 19.993 FPS, 50/50 exact plays; hub verified 11951610 bytes; pass=True.

2026-10-08 05:34:39 -0700: Pool renderer-2 v4-phase-a-1975101172: 19.995 FPS, 14/14 exact plays; hub verified 3167382 bytes; pass=True.

2026-10-08 05:36:12 -0700: Pool renderer-1 v4-phase-a-1975101173: 19.999 FPS, 34/34 exact plays; hub verified 7525405 bytes; pass=True.

2026-10-08 05:36:46 -0700: Pool renderer-2 v4-phase-a-1975101174: 19.990 FPS, 39/39 exact plays; hub verified 11240413 bytes; pass=True.

2026-10-08 05:38:05 -0700: Pool renderer-1 v4-phase-a-1975101175: 19.998 FPS, 38/38 exact plays; hub verified 7758654 bytes; pass=True.

2026-10-08 05:39:43 -0700: Pool renderer-2 v4-phase-a-1975101176: 19.988 FPS, 65/65 exact plays; hub verified 21639624 bytes; pass=True.

2026-10-08 05:41:11 -0700: Pool renderer-1 v4-phase-a-1975101177: 19.999 FPS, 64/64 exact plays; hub verified 23210219 bytes; pass=True.

2026-10-08 05:41:21 -0700: Pool renderer-2 v4-phase-a-1975101178: 19.994 FPS, 41/41 exact plays; hub verified 8594769 bytes; pass=True.

2026-10-08 05:42:26 -0700: Pool renderer-1 v4-phase-a-1975101179: 19.985 FPS, 13/13 exact plays; hub verified 4061445 bytes; pass=True.

2026-10-08 05:43:07 -0700: Pool renderer-2 v4-phase-a-1975101180: 19.999 FPS, 38/38 exact plays; hub verified 8193461 bytes; pass=True.

2026-10-08 05:44:34 -0700: Pool renderer-1 v4-phase-a-1975101181: 19.994 FPS, 45/45 exact plays; hub verified 11585940 bytes; pass=True.

2026-10-08 05:44:59 -0700: Pool renderer-2 v4-phase-a-1975101182: 19.991 FPS, 35/35 exact plays; hub verified 7193736 bytes; pass=True.

2026-10-08 05:47:25 -0700: Pool renderer-2 v4-phase-a-1975101184: 20.000 FPS, 46/46 exact plays; hub verified 17547777 bytes; pass=True.

2026-10-08 05:47:33 -0700: Pool renderer-1 v4-phase-a-1975101183: 19.986 FPS, 57/57 exact plays; hub verified 21022746 bytes; pass=True.

2026-10-08 05:49:22 -0700: Pool renderer-1 v4-phase-a-1975101186: 19.995 FPS, 42/42 exact plays; hub verified 8759408 bytes; pass=True.

2026-10-08 05:50:21 -0700: Pool renderer-2 v4-phase-a-1975101185: 20.000 FPS, 105/105 exact plays; hub verified 21491406 bytes; pass=True.

2026-10-08 05:51:02 -0700: Pool renderer-1 v4-phase-a-1975101187: 19.999 FPS, 26/26 exact plays; hub verified 5857623 bytes; pass=True.

2026-10-08 05:52:02 -0700: Pool renderer-2 v4-phase-a-1975101188: 19.999 FPS, 27/27 exact plays; hub verified 5993874 bytes; pass=True.

2026-10-08 05:52:55 -0700: Pool renderer-1 v4-phase-a-1975101189: 19.936 FPS, 30/30 exact plays; hub verified 7765902 bytes; pass=True.

2026-10-08 05:55:01 -0700: Pool renderer-2 v4-phase-a-1975101190: 19.983 FPS, 67/67 exact plays; hub verified 21796112 bytes; pass=True.

2026-10-08 05:57:08 -0700: Pool renderer-2 v4-phase-a-1975101192: 19.974 FPS, 44/44 exact plays; hub verified 13512357 bytes; pass=True.

2026-10-08 05:57:22 -0700: Pool renderer-1 v4-phase-a-1975101191: 19.999 FPS, 121/121 exact plays; hub verified 35942781 bytes; pass=True.

2026-10-08 05:59:54 -0700: Pool renderer-1 v4-phase-a-1975101194: 20.000 FPS, 57/57 exact plays; hub verified 16213272 bytes; pass=True.

2026-10-08 06:00:04 -0700: Pool renderer-2 v4-phase-a-1975101193: 19.981 FPS, 78/78 exact plays; hub verified 20961658 bytes; pass=True.

2026-10-08 06:01:58 -0700: Pool renderer-2 v4-phase-a-1975101196: 20.000 FPS, 26/26 exact plays; hub verified 7153464 bytes; pass=True.

2026-10-08 06:02:02 -0700: Pool renderer-1 v4-phase-a-1975101195: 20.000 FPS, 39/39 exact plays; hub verified 10307496 bytes; pass=True.

2026-10-08 06:04:26 -0700: Pool renderer-1 v4-phase-a-1975101198: 19.999 FPS, 57/57 exact plays; hub verified 16378180 bytes; pass=True.

2026-10-08 06:04:55 -0700: Pool renderer-2 v4-phase-a-1975101197: 19.999 FPS, 53/53 exact plays; hub verified 20172347 bytes; pass=True.

2026-10-08 06:06:05 -0700: Pool renderer-1 v4-phase-a-1975101199: 20.000 FPS, 37/37 exact plays; hub verified 9253324 bytes; pass=True.

2026-10-08 06:06:38 -0700: Pool renderer-2 v4-phase-a-1975101200: 19.988 FPS, 27/27 exact plays; hub verified 7676461 bytes; pass=True.

2026-10-08 06:07:42 -0700: Pool renderer-1 v4-phase-a-1975101201: 19.990 FPS, 24/24 exact plays; hub verified 6691444 bytes; pass=True.

2026-10-08 06:08:46 -0700: Pool renderer-2 v4-phase-a-1975101202: 20.000 FPS, 46/46 exact plays; hub verified 10815240 bytes; pass=True.

2026-10-08 06:09:30 -0700: Pool renderer-1 v4-phase-a-1975101203: 20.000 FPS, 30/30 exact plays; hub verified 6499503 bytes; pass=True.

2026-10-08 06:10:46 -0700: Pool renderer-2 v4-phase-a-1975101204: 19.975 FPS, 28/28 exact plays; hub verified 12834117 bytes; pass=True.

2026-10-08 06:11:52 -0700: Pool renderer-1 v4-phase-a-1975101205: 19.996 FPS, 43/43 exact plays; hub verified 15116127 bytes; pass=True.

2026-10-08 06:12:25 -0700: Pool renderer-2 v4-phase-a-1975101206: 19.999 FPS, 35/35 exact plays; hub verified 9446846 bytes; pass=True.

2026-10-08 06:14:02 -0700: Pool renderer-2 v4-phase-a-1975101208: 19.992 FPS, 27/27 exact plays; hub verified 6304220 bytes; pass=True.

2026-10-08 06:14:17 -0700: Pool renderer-1 v4-phase-a-1975101207: 19.999 FPS, 66/66 exact plays; hub verified 16160735 bytes; pass=True.

2026-10-08 06:15:35 -0700: Pool renderer-2 v4-phase-a-1975101209: 19.991 FPS, 19/19 exact plays; hub verified 4566395 bytes; pass=True.

2026-10-08 06:16:11 -0700: Pool renderer-1 v4-phase-a-1975101210: 19.999 FPS, 28/28 exact plays; hub verified 7345263 bytes; pass=True.

2026-10-08 06:18:34 -0700: Pool renderer-2 v4-phase-a-1975101211: 20.000 FPS, 62/62 exact plays; hub verified 21070113 bytes; pass=True.

2026-10-08 06:18:47 -0700: Pool renderer-1 v4-phase-a-1975101212: 19.980 FPS, 53/53 exact plays; hub verified 17448549 bytes; pass=True.

2026-10-08 06:20:05 -0700: Pool renderer-1 v4-phase-a-1975101214: 19.999 FPS, 14/14 exact plays; hub verified 4144485 bytes; pass=True.

2026-10-08 06:20:13 -0700: Pool renderer-2 v4-phase-a-1975101213: 19.994 FPS, 30/30 exact plays; hub verified 9700099 bytes; pass=True.

2026-10-08 06:21:44 -0700: Pool renderer-1 v4-phase-a-1975101215: 19.993 FPS, 23/23 exact plays; hub verified 7669478 bytes; pass=True.

2026-10-08 06:22:07 -0700: Pool renderer-2 v4-phase-a-1975101216: 19.997 FPS, 33/33 exact plays; hub verified 9520978 bytes; pass=True.

2026-10-08 06:23:36 -0700: Pool renderer-1 v4-phase-a-1975101217: 19.989 FPS, 27/27 exact plays; hub verified 7102342 bytes; pass=True.

2026-10-08 06:25:06 -0700: Pool renderer-2 v4-phase-a-1975101218: 19.980 FPS, 61/61 exact plays; hub verified 21330167 bytes; pass=True.

2026-10-08 06:26:01 -0700: Pool renderer-1 v4-phase-a-1975101219: 19.997 FPS, 60/60 exact plays; hub verified 15672805 bytes; pass=True.

2026-10-08 06:27:15 -0700: Pool renderer-1 v4-phase-a-1975101221: 19.999 FPS, 17/17 exact plays; hub verified 3409130 bytes; pass=True.

2026-10-08 06:28:11 -0700: Pool renderer-2 v4-phase-a-1975101220: 19.999 FPS, 104/104 exact plays; hub verified 23501266 bytes; pass=True.

2026-10-08 06:29:38 -0700: Pool renderer-1 v4-phase-a-1975101222: 19.996 FPS, 60/60 exact plays; hub verified 13868553 bytes; pass=True.

2026-10-08 06:30:20 -0700: Pool renderer-2 v4-phase-a-1975101223: 19.992 FPS, 42/42 exact plays; hub verified 10652713 bytes; pass=True.

2026-10-08 06:31:31 -0700: Pool renderer-1 v4-phase-a-1975101224: 19.998 FPS, 35/35 exact plays; hub verified 6831774 bytes; pass=True.

2026-10-08 06:33:55 -0700: Pool renderer-1 v4-phase-a-1975101226: 20.000 FPS, 55/55 exact plays; hub verified 16536090 bytes; pass=True.

2026-10-08 06:34:33 -0700: Pool renderer-2 v4-phase-a-1975101225: 20.000 FPS, 104/104 exact plays; hub verified 33399014 bytes; pass=True.

2026-10-08 06:35:34 -0700: Pool renderer-1 v4-phase-a-1975101227: 19.995 FPS, 32/32 exact plays; hub verified 9493314 bytes; pass=True.

2026-10-08 06:36:46 -0700: Pool renderer-2 v4-phase-a-1975101228: 19.996 FPS, 55/55 exact plays; hub verified 11629620 bytes; pass=True.

2026-10-08 06:38:04 -0700: Pool renderer-1 v4-phase-a-1975101229: 19.997 FPS, 77/77 exact plays; hub verified 15481367 bytes; pass=True.

2026-10-08 06:38:51 -0700: Pool renderer-2 v4-phase-a-1975101230: 19.945 FPS, 45/45 exact plays; hub verified 11208200 bytes; pass=True.

2026-10-08 06:39:56 -0700: Pool renderer-1 v4-phase-a-1975101231: 19.942 FPS, 32/32 exact plays; hub verified 6611466 bytes; pass=True.

2026-10-08 06:41:49 -0700: Pool renderer-2 v4-phase-a-1975101232: 19.998 FPS, 72/72 exact plays; hub verified 21063389 bytes; pass=True.

2026-10-08 06:42:22 -0700: Pool renderer-1 v4-phase-a-1975101233: 19.973 FPS, 52/52 exact plays; hub verified 16576993 bytes; pass=True.

2026-10-08 06:43:29 -0700: Pool renderer-2 v4-phase-a-1975101234: 19.999 FPS, 38/38 exact plays; hub verified 9685831 bytes; pass=True.

2026-10-08 06:44:56 -0700: Pool renderer-1 v4-phase-a-1975101235: 19.993 FPS, 58/58 exact plays; hub verified 17019291 bytes; pass=True.

2026-10-08 06:46:00 -0700: Pool renderer-2 v4-phase-a-1975101236: 19.999 FPS, 53/53 exact plays; hub verified 14547900 bytes; pass=True.

2026-10-08 06:47:04 -0700: Pool renderer-1 v4-phase-a-1975101237: 19.991 FPS, 35/35 exact plays; hub verified 9715935 bytes; pass=True.

2026-10-08 06:47:54 -0700: Pool renderer-2 v4-phase-a-1975101238: 19.990 FPS, 25/25 exact plays; hub verified 7222188 bytes; pass=True.

2026-10-08 06:49:53 -0700: Pool renderer-1 v4-phase-a-1975101239: 19.975 FPS, 56/56 exact plays; hub verified 20825683 bytes; pass=True.

2026-10-08 06:51:37 -0700: Pool renderer-1 v4-phase-a-1975101241: 19.912 FPS, 40/40 exact plays; hub verified 10449072 bytes; pass=True.

2026-10-08 06:52:21 -0700: Pool renderer-2 v4-phase-a-1975101240: 19.970 FPS, 121/121 exact plays; hub verified 35178828 bytes; pass=True.

2026-10-08 06:54:19 -0700: Pool renderer-1 v4-phase-a-1975101242: 20.000 FPS, 85/85 exact plays; hub verified 17867836 bytes; pass=True.

2026-10-08 06:54:51 -0700: Pool renderer-2 v4-phase-a-1975101243: 19.999 FPS, 72/72 exact plays; hub verified 14946606 bytes; pass=True.

2026-10-08 06:56:16 -0700: Pool renderer-1 v4-phase-a-1975101244: 19.995 FPS, 44/44 exact plays; hub verified 8744754 bytes; pass=True.

2026-10-08 06:56:43 -0700: Pool renderer-2 v4-phase-a-1975101245: 19.997 FPS, 25/25 exact plays; hub verified 6762910 bytes; pass=True.

2026-10-08 06:59:13 -0700: Pool renderer-2 v4-phase-a-1975101247: 19.947 FPS, 55/55 exact plays; hub verified 16869484 bytes; pass=True.

2026-10-08 06:59:18 -0700: Pool renderer-1 v4-phase-a-1975101246: 19.985 FPS, 58/58 exact plays; hub verified 20354067 bytes; pass=True.

2026-10-08 07:00:51 -0700: Pool renderer-2 v4-phase-a-1975101248: 19.999 FPS, 40/40 exact plays; hub verified 9706038 bytes; pass=True.

2026-10-08 07:02:13 -0700: Pool renderer-1 v4-phase-a-1975101249: 19.978 FPS, 94/94 exact plays; hub verified 20007428 bytes; pass=True.

2026-10-08 07:02:20 -0700: Pool renderer-2 v4-phase-a-1975101250: 19.976 FPS, 17/17 exact plays; hub verified 4949120 bytes; pass=True.

2026-10-08 07:03:49 -0700: Pool renderer-1 v4-phase-a-1975101251: 19.987 FPS, 24/24 exact plays; hub verified 5144569 bytes; pass=True.

2026-10-08 07:04:11 -0700: Pool renderer-2 v4-phase-a-1975101252: 19.999 FPS, 33/33 exact plays; hub verified 6577553 bytes; pass=True.

2026-10-08 07:06:37 -0700: Pool renderer-2 v4-phase-a-1975101254: 20.000 FPS, 53/53 exact plays; hub verified 18493211 bytes; pass=True.

2026-10-08 07:06:47 -0700: Pool renderer-1 v4-phase-a-1975101253: 19.984 FPS, 64/64 exact plays; hub verified 21632248 bytes; pass=True.

2026-10-08 07:07:54 -0700: Pool renderer-1 v4-phase-a-1975101256: 19.995 FPS, 10/10 exact plays; hub verified 2564293 bytes; pass=True.

2026-10-08 07:09:21 -0700: Pool renderer-2 v4-phase-a-1975101255: 19.981 FPS, 80/80 exact plays; hub verified 19216384 bytes; pass=True.

2026-10-08 07:10:26 -0700: Pool renderer-1 v4-phase-a-1975101257: 19.993 FPS, 54/54 exact plays; hub verified 17270213 bytes; pass=True.

2026-10-08 07:11:30 -0700: Pool renderer-2 v4-phase-a-1975101258: 19.998 FPS, 53/53 exact plays; hub verified 10309556 bytes; pass=True.

2026-10-08 07:12:11 -0700: Pool renderer-1 v4-phase-a-1975101259: 19.990 FPS, 25/25 exact plays; hub verified 5619770 bytes; pass=True.

2026-10-08 07:14:36 -0700: Pool renderer-1 v4-phase-a-1975101261: 19.999 FPS, 48/48 exact plays; hub verified 14645871 bytes; pass=True.

2026-10-08 07:14:45 -0700: Pool renderer-2 v4-phase-a-1975101260: 19.996 FPS, 64/64 exact plays; hub verified 24717606 bytes; pass=True.

2026-10-08 07:16:59 -0700: Pool renderer-2 v4-phase-a-1975101263: 19.996 FPS, 44/44 exact plays; hub verified 13365507 bytes; pass=True.

2026-10-08 07:18:19 -0700: Pool renderer-1 v4-phase-a-1975101262: 19.987 FPS, 121/121 exact plays; hub verified 31052872 bytes; pass=True.

2026-10-08 07:19:31 -0700: Pool renderer-2 v4-phase-a-1975101264: 20.000 FPS, 71/71 exact plays; hub verified 14706315 bytes; pass=True.

2026-10-08 07:20:18 -0700: Pool renderer-1 v4-phase-a-1975101265: 19.998 FPS, 40/40 exact plays; hub verified 9298488 bytes; pass=True.

2026-10-08 07:21:25 -0700: Pool renderer-2 v4-phase-a-1975101266: 19.944 FPS, 35/35 exact plays; hub verified 7178703 bytes; pass=True.

2026-10-08 07:23:43 -0700: Pool renderer-2 v4-phase-a-1975101268: 19.997 FPS, 43/43 exact plays; hub verified 14990314 bytes; pass=True.

2026-10-08 07:24:05 -0700: Pool renderer-1 v4-phase-a-1975101267: 19.987 FPS, 77/77 exact plays; hub verified 28139103 bytes; pass=True.

2026-10-08 07:25:21 -0700: Pool renderer-2 v4-phase-a-1975101269: 19.989 FPS, 35/35 exact plays; hub verified 9136561 bytes; pass=True.

2026-10-08 07:25:33 -0700: Pool renderer-1 v4-phase-a-1975101270: 19.984 FPS, 25/25 exact plays; hub verified 5918232 bytes; pass=True.

2026-10-08 07:26:50 -0700: Pool renderer-2 v4-phase-a-1975101271: 19.994 FPS, 22/22 exact plays; hub verified 4669531 bytes; pass=True.

2026-10-08 07:27:41 -0700: Pool renderer-1 v4-phase-a-1975101272: 19.993 FPS, 52/52 exact plays; hub verified 11143384 bytes; pass=True.

2026-10-08 07:28:44 -0700: Pool renderer-2 v4-phase-a-1975101273: 19.991 FPS, 32/32 exact plays; hub verified 7033167 bytes; pass=True.

2026-10-08 07:30:40 -0700: Pool renderer-1 v4-phase-a-1975101274: 19.998 FPS, 68/68 exact plays; hub verified 21381521 bytes; pass=True.

2026-10-08 07:31:13 -0700: Pool renderer-2 v4-phase-a-1975101275: 19.997 FPS, 52/52 exact plays; hub verified 16621096 bytes; pass=True.

2026-10-08 07:32:18 -0700: Pool renderer-1 v4-phase-a-1975101276: 19.961 FPS, 28/28 exact plays; hub verified 9033844 bytes; pass=True.

2026-10-08 07:33:08 -0700: Pool renderer-2 v4-phase-a-1975101277: 19.995 FPS, 37/37 exact plays; hub verified 9850567 bytes; pass=True.

2026-10-08 07:33:50 -0700: Pool renderer-1 v4-phase-a-1975101278: 19.989 FPS, 19/19 exact plays; hub verified 5189166 bytes; pass=True.

2026-10-08 07:34:49 -0700: Pool renderer-2 v4-phase-a-1975101279: 20.000 FPS, 26/26 exact plays; hub verified 6282138 bytes; pass=True.

2026-10-08 07:35:42 -0700: Pool renderer-1 v4-phase-a-1975101280: 20.000 FPS, 33/33 exact plays; hub verified 7810485 bytes; pass=True.

2026-10-08 07:38:02 -0700: Pool renderer-2 v4-phase-a-1975101281: 20.000 FPS, 65/65 exact plays; hub verified 23151001 bytes; pass=True.

2026-10-08 07:38:07 -0700: Pool renderer-1 v4-phase-a-1975101282: 19.979 FPS, 47/47 exact plays; hub verified 17126001 bytes; pass=True.

2026-10-08 07:39:27 -0700: Pool renderer-1 v4-phase-a-1975101284: 19.998 FPS, 19/19 exact plays; hub verified 4501342 bytes; pass=True.

2026-10-08 07:40:05 -0700: Pool renderer-2 v4-phase-a-1975101283: 19.993 FPS, 53/53 exact plays; hub verified 13033048 bytes; pass=True.

2026-10-08 07:41:30 -0700: Pool renderer-1 v4-phase-a-1975101285: 19.996 FPS, 51/51 exact plays; hub verified 10531535 bytes; pass=True.

2026-10-08 07:41:55 -0700: Pool renderer-2 v4-phase-a-1975101286: 19.938 FPS, 33/33 exact plays; hub verified 7270717 bytes; pass=True.

2026-10-08 07:43:23 -0700: Pool renderer-1 v4-phase-a-1975101287: 19.998 FPS, 32/32 exact plays; hub verified 7001946 bytes; pass=True.

2026-10-08 07:44:22 -0700: Pool renderer-1 v4-phase-a-1975101289: 19.988 FPS, 14/14 exact plays; hub verified 4985441 bytes; pass=True.

2026-10-08 07:44:53 -0700: Pool renderer-2 v4-phase-a-1975101288: 19.985 FPS, 58/58 exact plays; hub verified 20176987 bytes; pass=True.

2026-10-08 07:47:10 -0700: Pool renderer-1 v4-phase-a-1975101290: 19.999 FPS, 86/86 exact plays; hub verified 19670066 bytes; pass=True.

2026-10-08 07:47:32 -0700: Pool renderer-2 v4-phase-a-1975101291: 19.976 FPS, 77/77 exact plays; hub verified 16977591 bytes; pass=True.

2026-10-08 07:49:41 -0700: Pool renderer-1 v4-phase-a-1975101292: 19.972 FPS, 67/67 exact plays; hub verified 14508102 bytes; pass=True.

2026-10-08 07:49:43 -0700: Pool renderer-2 v4-phase-a-1975101293: 19.998 FPS, 45/45 exact plays; hub verified 10537921 bytes; pass=True.

2026-10-08 07:51:35 -0700: Pool renderer-1 v4-phase-a-1975101294: 19.998 FPS, 34/34 exact plays; hub verified 7464679 bytes; pass=True.

2026-10-08 07:52:42 -0700: Pool renderer-2 v4-phase-a-1975101295: 20.000 FPS, 75/75 exact plays; hub verified 21302350 bytes; pass=True.

2026-10-08 07:54:21 -0700: Pool renderer-2 v4-phase-a-1975101297: 20.000 FPS, 38/38 exact plays; hub verified 8718341 bytes; pass=True.

2026-10-08 07:54:33 -0700: Pool renderer-1 v4-phase-a-1975101296: 19.973 FPS, 72/72 exact plays; hub verified 20136175 bytes; pass=True.

2026-10-08 07:57:04 -0700: Pool renderer-1 v4-phase-a-1975101299: 19.971 FPS, 57/57 exact plays; hub verified 16039316 bytes; pass=True.

2026-10-08 07:57:16 -0700: Pool renderer-2 v4-phase-a-1975101298: 19.982 FPS, 67/67 exact plays; hub verified 18954268 bytes; pass=True.

2026-10-08 07:58:32 -0700: Pool renderer-1 v4-phase-a-1975101300: 19.982 FPS, 17/17 exact plays; hub verified 3682467 bytes; pass=True.

2026-10-08 07:59:07 -0700: Pool renderer-2 v4-phase-a-1975101301: 19.994 FPS, 30/30 exact plays; hub verified 6127874 bytes; pass=True.

2026-10-08 08:01:31 -0700: Pool renderer-1 v4-phase-a-1975101302: 19.969 FPS, 69/69 exact plays; hub verified 21632605 bytes; pass=True.

2026-10-08 08:01:34 -0700: Pool renderer-2 v4-phase-a-1975101303: 19.978 FPS, 49/49 exact plays; hub verified 17193364 bytes; pass=True.

2026-10-08 08:02:59 -0700: Pool renderer-2 v4-phase-a-1975101305: 19.996 FPS, 22/22 exact plays; hub verified 5382631 bytes; pass=True.

2026-10-08 08:03:14 -0700: Pool renderer-1 v4-phase-a-1975101304: 19.999 FPS, 32/32 exact plays; hub verified 8992658 bytes; pass=True.

2026-10-08 08:04:47 -0700: Pool renderer-1 v4-phase-a-1975101307: 19.994 FPS, 21/21 exact plays; hub verified 5022588 bytes; pass=True.

2026-10-08 08:05:30 -0700: Pool renderer-2 v4-phase-a-1975101306: 19.996 FPS, 63/63 exact plays; hub verified 15776536 bytes; pass=True.

2026-10-08 08:06:39 -0700: Pool renderer-1 v4-phase-a-1975101308: 19.934 FPS, 33/33 exact plays; hub verified 6899752 bytes; pass=True.

2026-10-08 08:09:11 -0700: Pool renderer-2 v4-phase-a-1975101309: 20.000 FPS, 92/92 exact plays; hub verified 30595810 bytes; pass=True.

2026-10-08 08:09:16 -0700: Pool renderer-1 v4-phase-a-1975101310: 19.980 FPS, 45/45 exact plays; hub verified 17470463 bytes; pass=True.

2026-10-08 08:10:34 -0700: Pool renderer-1 v4-phase-a-1975101312: 19.885 FPS, 14/14 exact plays; hub verified 3949400 bytes; pass=True.

2026-10-08 08:10:57 -0700: Pool renderer-2 v4-phase-a-1975101311: 20.000 FPS, 34/34 exact plays; hub verified 9334338 bytes; pass=True.

2026-10-08 08:13:03 -0700: Pool renderer-1 v4-phase-a-1975101313: 19.943 FPS, 68/68 exact plays; hub verified 16199566 bytes; pass=True.

2026-10-08 08:13:06 -0700: Pool renderer-2 v4-phase-a-1975101314: 19.998 FPS, 58/58 exact plays; hub verified 11347728 bytes; pass=True.

2026-10-08 08:14:58 -0700: Pool renderer-1 v4-phase-a-1975101315: 19.998 FPS, 34/34 exact plays; hub verified 6593553 bytes; pass=True.

2026-10-08 08:16:04 -0700: Pool renderer-2 v4-phase-a-1975101316: 19.998 FPS, 63/63 exact plays; hub verified 21069315 bytes; pass=True.

2026-10-08 08:17:23 -0700: Pool renderer-1 v4-phase-a-1975101317: 19.977 FPS, 47/47 exact plays; hub verified 15461882 bytes; pass=True.

2026-10-08 08:17:55 -0700: Pool renderer-2 v4-phase-a-1975101318: 19.995 FPS, 37/37 exact plays; hub verified 11085609 bytes; pass=True.

2026-10-08 08:19:01 -0700: Pool renderer-1 v4-phase-a-1975101319: 19.991 FPS, 25/25 exact plays; hub verified 8147535 bytes; pass=True.

2026-10-08 08:19:44 -0700: Pool renderer-2 v4-phase-a-1975101320: 19.952 FPS, 32/32 exact plays; hub verified 7913184 bytes; pass=True.

2026-10-08 08:21:10 -0700: Pool renderer-1 v4-phase-a-1975101321: 20.000 FPS, 55/55 exact plays; hub verified 10865855 bytes; pass=True.

2026-10-08 08:21:37 -0700: Pool renderer-2 v4-phase-a-1975101322: 19.999 FPS, 36/36 exact plays; hub verified 6724842 bytes; pass=True.

2026-10-08 08:22:38 -0700: Pool renderer-1 v4-phase-a-1975101323: 19.995 FPS, 22/22 exact plays; hub verified 11440492 bytes; pass=True.

2026-10-08 08:24:46 -0700: Pool renderer-2 v4-phase-a-1975101324: 19.996 FPS, 84/84 exact plays; hub verified 22652848 bytes; pass=True.

2026-10-08 08:25:32 -0700: Pool renderer-1 v4-phase-a-1975101325: 19.936 FPS, 83/83 exact plays; hub verified 23019457 bytes; pass=True.

2026-10-08 08:26:48 -0700: Pool renderer-2 v4-phase-a-1975101326: 19.994 FPS, 39/39 exact plays; hub verified 11139934 bytes; pass=True.

2026-10-08 08:26:49 -0700: Pool renderer-1 v4-phase-a-1975101327: 19.977 FPS, 10/10 exact plays; hub verified 2446953 bytes; pass=True.

2026-10-08 08:28:10 -0700: Pool renderer-1 v4-phase-a-1975101328: 19.977 FPS, 12/12 exact plays; hub verified 2331077 bytes; pass=True.

2026-10-08 08:28:41 -0700: Pool renderer-2 v4-phase-a-1975101329: 19.986 FPS, 28/28 exact plays; hub verified 6661371 bytes; pass=True.

2026-10-08 08:31:07 -0700: Pool renderer-1 v4-phase-a-1975101330: 19.986 FPS, 57/57 exact plays; hub verified 21934550 bytes; pass=True.

2026-10-08 08:31:10 -0700: Pool renderer-2 v4-phase-a-1975101331: 19.995 FPS, 56/56 exact plays; hub verified 15276935 bytes; pass=True.

2026-10-08 08:32:48 -0700: Pool renderer-1 v4-phase-a-1975101332: 19.993 FPS, 31/31 exact plays; hub verified 8774608 bytes; pass=True.

2026-10-08 08:33:34 -0700: Pool renderer-2 v4-phase-a-1975101333: 19.994 FPS, 50/50 exact plays; hub verified 14551879 bytes; pass=True.

2026-10-08 08:34:24 -0700: Pool renderer-1 v4-phase-a-1975101334: 19.999 FPS, 18/18 exact plays; hub verified 5624554 bytes; pass=True.

2026-10-08 08:35:43 -0700: Pool renderer-2 v4-phase-a-1975101335: 19.961 FPS, 51/51 exact plays; hub verified 11041912 bytes; pass=True.

2026-10-08 08:36:16 -0700: Pool renderer-1 v4-phase-a-1975101336: 19.995 FPS, 33/33 exact plays; hub verified 6644543 bytes; pass=True.

2026-10-08 08:38:40 -0700: Pool renderer-1 v4-phase-a-1975101338: 20.000 FPS, 43/43 exact plays; hub verified 15464228 bytes; pass=True.

2026-10-08 08:40:16 -0700: Pool renderer-2 v4-phase-a-1975101337: 19.988 FPS, 139/139 exact plays; hub verified 36654437 bytes; pass=True.

2026-10-08 08:41:47 -0700: Pool renderer-1 v4-phase-a-1975101339: 19.980 FPS, 91/91 exact plays; hub verified 23147921 bytes; pass=True.

2026-10-08 08:43:11 -0700: Pool renderer-2 v4-phase-a-1975101340: 19.982 FPS, 89/89 exact plays; hub verified 19819161 bytes; pass=True.

2026-10-08 08:43:11 -0700: Pool stopped: heldout count coverage reached
