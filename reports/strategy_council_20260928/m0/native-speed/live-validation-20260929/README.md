# Live validation on emulator-5594 (2026-09-29)

Instance: pool instance-8, `emulator-5594`, host probe port 26796, lock `/tmp/clasher-v4check-emulator-5594.lock`. Every adb call was scoped with `-s emulator-5594`. The adb server was never restarted, and the other 7 emulators and `forward_keeper.sh` were not touched. No ledger writes. Nothing under `runtime-snapshots/` and no repository source file was edited. Full evidence is in `results.json`.

Plan: the `v4-runner-check2` plan had stale source pins (8 files changed since it was made), so I re-prepared it into `plan/` with `speed_harness.py prepare`. The jobs are identical to the old plan except for `execution_sha256`, which covers the pins. All branches ran fast path, replay start, render off, with the same settings as `v4-runner-check2`.

## A. Batched level reader: BLOCKED, not run

- The helper pushed fine and its sha256 on the device is `4a00b4f6…167d`.
- Running it aborts: `executable's TLS segment is underaligned: alignment is 8 (skew 0), needs to be at least 64 for ARM64 Bionic` (exit code 134). SELinux is not the cause: adbd runs as root (`u:r:su:s0`), and the bionic loader rejects the binary before it starts.
- Cause: the binary was built with `aarch64-linux-android24-clang -static`, which gives a PT_TLS alignment of 0x8.
- Diagnostic rebuild (in `/tmp/clasher-walk-diag`, not pinned or adopted): the same flags with `aarch64-linux-android29-clang` give sha256 `43e65263…101b` and a TLS alignment of 0x40. That build loads on the device and prints its usage (exit code 2). I removed it from the device afterwards. Adopting it needs a new `LEVEL_WALK_HELPER_SHA256` pin and a new receipt.
- Fail-closed check (`a3-batched-failclosed-j0`): the runner with `--native-level-reader batched` fails in 2.7 s with `ValueError: truncated native level walk transcript`. It treats this as a job-local failure (`run_invalidating: false`), so a shard would go on and fail every job. The message also doesn't mention the loader abort.
- Steps 2–3 (dual reads, batched end to end, timing) were not run.

## B. Live link recovery: PASS with the legacy reader (step 5 skipped because A is blocked)

| Run | Fault | Recovery record | Compared with reference |
| --- | --- | --- | --- |
| `b1-legacy-forward-j0` | `forward --remove tcp:26796`, planned 3×; only the first removal found a forward to remove | 0 events | identical (457/457 decisions, commands, terminal, result) |
| `b2-legacy-forward-break-j0` | 3× at 51.9/83.1/96.5 s: forward removal plus device-side `ss -K` of the adbd→probe socket | count 3, recovered 3, total 1.11 s; forward re-added; attestation and pid/start ticks (2061/1068) verified; `observe_equal: true` | identical against v4-runner-check2, fast-replay-i1 and b1 |
| `b6-legacy-appkill-j0-j16` | `am force-stop nullsroyale.rel.free` at 34.9 s | budget exhausted after 120 s (18 attempts), `device_lost: true` | branch failed with `RunInvalidatedError`; job 16 never started (the shard stopped) |
| `post-restore-legacy-j0` | none (after restore) | 0 events | identical |

Findings:
1. Removing the forward on its own does not break the established persistent session, because adb keeps existing forwarded connections open. To make recovery actually run, the connection has to be broken as well (b2). In b1 the forward stayed missing after the run, because nothing needed to reconnect.
2. All three recoveries in b2 happened on read-only commands (`observe`, `status`). The live test never exercised the path where a fault interrupts a state-changing command (`step` or schedule).
3. When the app dies, the runner fails correctly, but only after spending the full 120 s budget. Each reconnect gets `ProbeLinkClosed`, which is classified as transient, and the `pidof` identity check only runs after a successful reconnect.
4. Job 0 wall time: 182.9 s with 3 recoveries, 184.2 s in b1, 183.0 s with no faults.

## Restore and final state

`restore_instance8.py` repeats the post-boot steps of `start_local_reference.py`, with adb scoped to this device. Receipts are in `restore-instance-8/`. After the restore: new app pid 22206, attestation `864227bf…`, ready, paused, `renderSuppressed: false`, forward `tcp:26796 → tcp:26789`. A clean branch after the restore was identical to the reference. The pinned helper is still at `/data/local/tmp/clasher-level-walk-v1`.

Tools: `chaos.py` (fault injector wrapping the runner), `restore_instance8.py`.
