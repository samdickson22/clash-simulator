# T6/T7 retained technical attempts

## Execution-clock boundary preparation, 2026-10-08 10:00 UTC

`18:v4-execution-clock-audit-20261008-r2` (1019716 / 1019718) failed before
writing an audit result: leading clamped tick did not equal the first interior
screenshot's lower tick. That equality was an implementation assumption;
native samples can advance between screenshots. The corrected check requires
constant edge clamps and monotonicity, using leading upper/trailing lower bounds
only. No timestamps are extrapolated; unsupported sides remain unavailable.
Regression r3 passes 41 synthetic cases; full audit r3 maps the identical 287
receipt population, 14,393 accepted events, zero omissions. Keep failed log/exit
and the original 14-unenclosed r1 audit. No heldout or prediction result informed
this correction, and no collector or frozen registration file changed.

## Scorer preparation, 2026-10-08

- `16:v4-scoring-tests-20261008-r1`, supervisor 3443711 / child 3443713,
  failed with a missing closing parenthesis before synthetic tests executed.
  The log and exit-1 receipt are retained. Corrected r2 (3444011 / 3444026)
  passed 135 synthetic checks and exited 0 with wrapper status PASS. Neither
  attempt opened any dataset payload, selected a model, or evaluated a gate.

## Preformal cache/labels, 2026-10-08

- `18:v4-cache-pilot-20261008-r1`, supervisor 944143, failed its exact frame
  check at requested frame 1,867. The legacy OpenCV VFR seek returned sequential
  frame 1,866; 30,693 pixel elements differed. The original incomplete cache
  remains under `clasher-lease/cache/v4-pixels/` (about 2.3 GiB). Exact sequential
  decoding plus independent sequential verification passed in `v4-pixels-r2`.
  `v4-seek-drift.json` preserves the counterexample. No failed data was deleted.
- `18:v4-cache-verify-train-20261008-r1/r2` failed before training because the
  leased source snapshot lacked the ignored historical calibration.json. It was
  copied directly from 01, unchanged; r3 passed. The partial parity directories
  and exit receipts remain. Neither failure consumed heldout or formal weights.
- `03:v4-phase-watch-20261008-r1` was briefly launched while 03 had an interactive
  `who` session and existing imitation workers exceeded the conservative
  16-worker rule. Only our verified watcher worker PID 3494183 was signalled
  SIGTERM; its wrapper 3494170 exited 0 at 06:26:58 UTC. The watch moved to T3
  scheduled one-shot receipt reads; no other job was stopped or altered.
- The first post-cleaning summary counted original visibility flags (63,061).
  The final shared cleaner/auditor requires coherent, unambiguous same-tick rich
  evidence, yielding 62,697. Both summaries are retained; r5 is authoritative.
- Serial versus parallel GPU pilot losses are not bit-identical after the first
  step (max difference 0.5334 over 64 steps). No optimization-trajectory parity
  is claimed. Independent CPU checks show exact historical augmentation tensors,
  concurrent tensors and RNG states over 32 windows. The registered arithmetic
  remains bf16 eager; training accuracy is unmeasured.

## 08:29 UTC preparation launch and diagnostic incidents

- `v4-selection-guard-tests-20261008-r1` on 16 passed all 23 synthetic checks
  and exited 0 at 08:43:55. The wrapper reported `stopped` for its post-exit
  descendant check; preserve the distinction from a clean wrapper PASS. No
  actual training run or heldout payload was opened for these synthetic tests.

- `v4-label-audit-20261008-r7` on 18 failed before child creation with EAGAIN
  because the cache gather already held the lease wrapper's host-wide workload
  lock. No label data was read by that attempt. Preserve the exit receipt; retry
  under a fresh label only after the gather's final exit. Process headroom does
  not authorize concurrent wrapper jobs on one host.
- `v4-gap-adapter-compile-20261008-r1/r2` on 16 each compiled successfully
  (child exit 0), but the wrapper marked them stopped for “job exited with
  descendants still running.” Do not report wrapper PASS. The source audit
  and 19-case schedule regression jobs did receive clean wrapper PASS receipts.
- At 08:27–08:33, implementation incorrectly switched the T6 gap diagnostic to
  decisions.jsonl based on the base PREREG alone. At 08:35, reading amendment 02
  confirmed that it explicitly corrects that path to public-frames.jsonl.gz.
  Restored the amended source in the new helper; no model replay used the wrong
  distribution. Retain the sparse-decision audit (830.632 ms p95) as diagnostic
  evidence only. The public-frame audit is rerunning under a fresh label. Frozen
  registration/amendment files remain unchanged; no formal gap gate was passed.

## Earlier shakedowns

- Initial remote launch used a relative path from the SSH home directory and did
  not start. Corrected by changing to the checkout before fleet_run.sh.
- GPU env lacked PyAV and pytest. Installed PyAV 16.0.1, pytest 8.4.2 and its
  ordinary dependencies into the existing GPU env; no Torch/NumPy changes.
  `t7-tests-20261008-1` exited 1 (pytest absent); subsequent tests passed.
- `t6-shake-20261008-1` exited 1 during HUD/cache preparation at the inherited
  450MiB JPEG-cache guard, before any optimizer step or validation scoring.
  Preserve `/mpac/sdicks02/repos/clasher-v4-training/t6-run-1/`. Re-run identical
  population and training seed as `t6-shake-20261008-2` / `t6-run-2`, explicit
  4096MiB disk guard; default remains 450MiB. Amendment 02 records this purely
  operational change. No samples or training behavior changed.
- Initial T7 smoke (`t7-shake-1`, 32 steps) exposed contradictory body metadata
  and projectile names in the label vocabulary. Keep that diagnostic checkpoint,
  but use `t7-shake-2` (64 steps, new vocabulary, train-only quarantine) as the
  current engineering receipt. Do not resume the first checkpoint under changed
  label semantics. Amendment 01 predates heldout scoring.
- T6 second attempt completed fitting, then the trusted v1 YOLO checkpoint could
  not deserialize because dill was absent. Installed dill 0.4.0; preserved the
  empty partial stage as validation-inference-missing-dill and resumed completed
  stages under `t6-shake-20261008-3`. No weights/data/training settings changed.
- T6 third attempt decoded one frame before the unchanged public-frame validator
  rejected fractional timestamp_ms from the converter. The input adapter now
  truncates to integer milliseconds exactly as the historical v3 sample_inputs
  function does. Raw input timestamps and the failed stage are retained as
  validation-inputs-producer-ms.jsonl and validation-inference-fractional-ms.
  Fourth attempt resumes the same completed fit. This changes no detector logic.
# 2026-10-08 09:23 UTC — short replay-helper test wrapper race

Lease 16 `v4-validation-replay-tests-20261008-r1`, supervisor 3490685 / child
3490687, printed 19 passing synthetic checks and child exit 0. The supervisor
reported `stopped`, reason `job exited with descendants still running`, matching
the retained short-command race. Peak two processes / 28,360,704 bytes RSS.
Retain log/exit receipt; do not present this as a clean wrapper PASS or a real
GPU replay. No retry solely to obtain a green wrapper status.

09:29 extension: r2 tests the newly added completion-journal scorer adapter,
33 checks passing, child 3493113 exit 0 / supervisor 3493111 `stopped` for the
same descendant-exit reason; peak two processes / 28,839,936 bytes RSS. Both
receipts retained. No wrapper change or broad process termination.


2026-10-08 11:30 UTC: `v4-cache-extension-tests-20261008-r1` on 16 passed
17 synthetic checks and child 3524177 exited 0. Supervisor 3524175 recorded
`stopped: job exited with descendants still running`, the known short-job
wrapper race. Preserve both outcomes; no retry for a green wrapper status.


2026-10-08 11:42 UTC discovery: `v4-cache-unique-20261008-16r1` failed exit 2
at 11:32:43 after completing all 25 selected caches. Its final `cache_manifest.py`
was absent from 16's source snapshot. Deployed that owned verifier and launched
`v4-cache-unique-verify-20261008-16r1` (3527218 / 3527221): PASS 11:44:22,
50 hashes / 395 exact checks / zero mismatches. No decoding repeated, no data
removed. Keep the original failed wrapper receipt and verification-only receipt.
