# T1 progress

Current status: all three bodyrepair1 smoke matches passed and were checksum-verified on 127x01. Phase A has not started: detached driver 63610 is waiting for the hub readiness marker. T2 evidence is complete, with a FAIL verdict at 98.75% pixel sensitivity; that verifier is not used by collection.

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
