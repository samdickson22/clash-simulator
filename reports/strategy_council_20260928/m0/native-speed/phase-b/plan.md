# Native speed Phase B: build status and equivalence plan (not yet run on a device)

Date: 2026-09-28. Nothing here has touched an emulator, adb, an APK or an AVD. All new host behavior is behind flags whose defaults reproduce the current path exactly. `run_readiness_v2.py` refuses the new modes for fresh attempts until a prospective protocol declares them.

## What was built

| Item | Where | Identity |
| --- | --- | --- |
| Batched level reader (one device process per frame) | `scripts/read_native_public_levels.py` (`level_reader='batched'`), helper source `tools/native_level_walk/clasher_level_walk.c` | helper binary `4a00b4f6…167d` (reproducible), receipt `~/.cache/clasher-native-reference/level-walk-helper-build-20260928/receipt.json` |
| Phase B probe (copy of FirstLight 28d66cc; original untouched) | `~/.cache/clasher-native-reference/firstlight-source-28d66cc-phaseb`, patch `probe-build-phaseb-20260928/phaseb-source.patch` | `libcrprobe.so` `76953b60…6f09f`, receipt `probe-build-phaseb-20260928/receipt.json` + `receipt-supplement.json`; rebuild reproduces it byte for byte |
| In-probe level reader | `level_reader='probe'` → probe `observe-levels` | host pin `EXPECTED_PHASEB` |
| Delta rich telemetry | probe `observe-rich-since C P S A H V R`; host `src/clasher/rl/native_rich_delta.py` | reconstruction is byte-identical to the cumulative `observe-rich` |
| Cached compaction | `compact_native_frame(frame, event_cache=…)` | identical storage record; digests recomputed from the same bytes |
| Runner flags | `run_readiness_v2.py execute --native-level-reader {legacy,batched,probe} --native-rich-transfer {full,delta} --native-probe-build {pinned,phaseb} [--native-probe-process-identity]` | defaults: `legacy`, `full`, `pinned`, off |
| Study tools | `phase-b/speed_harness_b.py`, `phase-b/summarize_b.py`, `phase-b/bench_host_cpu.py` | reuses `../speed_harness.py` and `../compare_equivalence.py` unchanged |

Integrity checks kept for every reader: full attestation at session enter and close; runtime identity (pid and process start time) on every frame; the caller's `observe` checked against `status`, and a closing `observe` that must equal it; no caching of pointers, bodies or levels. Batched mode also checks the helper's SHA-256 inside every walk exchange and at session boundaries, and checks pid and start time before and after the walk in the same process. The host replays its unchanged walk against the helper transcript: every (address, size) must match in order, a short range triggers exactly one fresh complete walk (never a splice), and unconsumed or incomplete records fail. The probe reader re-applies every host check to the probe's facts (identity, owner and card per slot, body set equal to the ordinary frame's non-null `hp`, 3..64 component inventory, HP backlink, `raw+1` in 1..127).

## Expected savings (inference from the Phase A breakdown, 1 emulator, 0.285 s per decision)

| Mode | Replaces | Expected per decision |
| --- | --- | --- |
| batched | ~10 ADB exchanges, ~45 `dd` spawns (159 ms) | 1 exchange with 4 small spawns (sha256sum, pidof ×2, helper): ~15–25 ms, plus the existing closing pid+stat exchange |
| probe | the same 159 ms | one in-probe call, ~3–5 ms (the ordinary `observe` costs 3.6 ms) |
| probe + `--native-probe-process-identity` | also 21 ms of per-frame ADB pid checks | 0 ms per frame (ADB still checks at session boundaries) |
| delta rich | 53 ms observe-rich + 34 ms compaction | measured host CPU on late frames 37.9 → 5.3 ms (`bench-host-cpu.json`, synthetic events at ~56% of real size); response 4.5 MB → 60 KB, so probe-side encoding and socket transfer shrink as well |

Combined probe + delta + probe identity: roughly 0.285 → 0.03–0.05 s per decision (inference). The batched helper alone needs no APK change: roughly 0.285 → 0.13–0.14 s. Host CPU: about 45 fewer device process spawns per decision (these run on emulated CPU, which is host CPU) and about 33 ms less Python CPU per late decision. This matters most at 8–10 instances, where the host is CPU-bound.

## Later steps (after the live Tier A attempt ends; on an instance no attempt owns)

Prerequisites: a dedicated read-only instance with its own serial, port and lock (`pool.json` usage rules). Take the lock before any adb call. Stop if disk drops below 10 GiB.

### A. Batched helper on the current pinned probe (no APK change)

1. Push the helper (read-only AVD, so it is discarded on exit; repeat after every launch):
   `adb -s S push ~/.cache/clasher-native-reference/level-walk-helper-build-20260928/clasher-level-walk /data/local/tmp/clasher-level-walk-v1 && adb -s S shell chmod 755 /data/local/tmp/clasher-level-walk-v1 && adb -s S shell sha256sum /data/local/tmp/clasher-level-walk-v1` → must print `4a00b4f6…167d`.
2. Dual read at every decision (the branch uses the legacy reader; batched must be identical), Phase A roots and jobs 48, 49, 0, 1, 16, 17, 32, 33:
   `.venv/bin/python -B reports/strategy_council_20260928/m0/native-speed/phase-b/speed_harness_b.py run --plan reports/strategy_council_20260928/m0/native-speed/equivalence/plan/execution-plan.json --output …/phase-b/runs/dual-batched-iN --port P --serial S --job-index 48 … --native-path fast --native-branch-start snapshot --dual-read-levels --dual-readers batched --native-lock LOCK --i-own-this-instance`
3. Timing and end-to-end run with `--native-level-reader batched` (no dual reads) on the same jobs. Compare with Phase A `fast-snapshot-i2` using `../compare_equivalence.py --pair jobJ A B`. Primary gate must be identical on all 8 pairs. The expected secondary differences are `level_source.transport`, session provenance and storage digests that cover `level_source`.

### B. Phase B probe

1. Package: `package_reference_probe.py --cache ~/.cache/clasher-native-reference --probe ~/.cache/clasher-native-reference/probe-build-phaseb-20260928/libcrprobe.so --engine-pin <libg pin json> --output ~/.cache/clasher-native-reference/probe-apk-build-phaseb-<date>`. The script overwrites the shared stage's `lib/arm64-v8a/libcrprobe.so`. Afterwards, copy `probe-build-20260914/libcrprobe.so` back and verify `2ea5e10d…`. It needs about 1.6 GB of disk.
2. Install only on a dedicated instance (never an attempt's AVD). Either use a read-only instance and install per launch, or clone a separate AVD for Phase B. Run `attest`: `probe_sha256` must be `76953b60…`, and `libg_sha256` and `content_fingerprint_sha256` must be unchanged. Record the canonical attestation SHA as the Phase B pin (it replaces `864227bf…` only for Phase B runs), then run `speed_harness_b.py prepare --output …/phase-b/plan-phaseb --native-attestation-sha256 NEW`.
3. Unchanged-command check: `--native-probe-build phaseb` with legacy/full on the 8 jobs, compared with Phase A legacy and fast results. Gameplay must be identical (only the pins differ).
4. Dual reads at every decision: `--native-probe-build phaseb --native-rich-transfer delta --dual-read-rich --dual-read-levels --dual-readers batched,probe` (branch reader legacy). Every level and rich row must be identical, including the first frame after each snapshot restore (telemetry epoch change → full retransmit) and late frames with ring overflow.
5. Targeted negatives on device: frames with non-body objects (spells, projectiles, `hp: null`), destroyed towers, and an object spawned between the two reads. The bracket must reject the last case. An `observe-rich-since` with a stale cursor must produce a full retransmit.
6. Timing matrix (1 instance, then 8 concurrently for host CPU; `host-cpu.json`): fast+snapshot with (legacy, full) | (batched, full) | (probe, delta) | (probe, delta, probe identity). Summarize with `summarize_b.py` (exits 1 on any mismatch or failure).
7. End to end: `compare_equivalence.py` for legacy vs each mode, 8 pairs each; the primary gate must be identical.

### Adoption gate

All dual reads identical, all end-to-end pairs identical, no unrecovered transport failures, a separate review, then a prospective protocol declaration (new probe pin, new identical-execution floors) before any fresh use. The runner enforces the fresh-use refusal.

## Risks

- FirstLight source has no license in our copy: research use only; do not distribute the patch or binary.
- The helper runs as the adb shell user, like today's `dd`. If SELinux on some image forbids executing from `/data/local/tmp`, batched mode fails closed at the first walk.
- `--native-probe-process-identity` trusts the attested probe's `/proc/self/stat` per frame. Without it, the per-frame ADB identity checks stay.
- Probe-side delta relies on process-global, never-reset ring sequences and on record-only event encoders (verified in source for all 7 rings). The host fails closed on any gap, reorder, cursor echo mismatch or epoch change without a full retransmit.
- Cached compaction assumes events are not mutated after reconstruction. The runner only reads them.
- `observe-atomic-levels` is built into the probe but has no host support yet.
- Phase A's `speed_harness.py` wraps `compact_native_frame` with a one-argument timer. Use `speed_harness_b.py` for any run with the new code.
