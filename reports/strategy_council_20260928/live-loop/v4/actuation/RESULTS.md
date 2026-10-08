# T2 actuation results

Verdict: FAIL — restated 99% pixel sensitivity gate is not met; actuator remains unqualified for production.

All 640 factorial trials retained; 16 cells × 40. Original 623 rows are untouched; 17 completion rows are in `actuation/trials-completion-20261007.jsonl`. No trials were excluded after outcomes.

| Transport | Acceptance | Two-tap p95 | D_b p50 / p99 | Sensitivity |
|---|---:|---:|---:|---:|
| grpc | 320/320 | 26.91 ms | 1151.69 / 1187.32 ms | 316/320 (98.75%) |
| adb-spawn | 320/320 | 85.39 ms | 1190.65 / 1335.14 ms | 318/320 (99.38%) |

Chosen transport remains persistent gRPC with 20 ms inter-tap delay. Its D_b equivalents are 23.034 / 23.746 ticks (p50/p99, nominal 50 ms ticks). The retained trials measure first native observation, not exact native execution. Do not present these fractional tick equivalents as exact hook ticks; the unchanged hook's nominal command delay is 22 ticks.

Specificity: 40/40 (100.00%); 20 no-input and 20 selection-only windows, each 1.787 seconds. Native hand preservation and nondecreasing elixir corroborate every negative. This is the empirical point gate, not a claim that a 99% population lower confidence bound has been established.

Host GPU, median screenshot delivery 59.13 FPS; native negative-window stepping 19.995 ticks/s. Pixel-minus-native observation p95 39.92 ms.

## Each of the four gRPC misses

- Cell ['grpc', 0.0, 3, 0.1], trial 30, seed 1974100729, tick 739: native elixir 3.1022, HUD elixir 9; acceptance 1137.89 ms; 58.34 FPS; HUD clock 144. No pixel detection before the 1.8 s observation limit. HUD baseline elixir error; likely reader miss. Native acceptance is timely. Raw frame/after-HUD trace was not retained, so short-lived stale pixels versus digit misread cannot be conclusively separated.
- Cell ['grpc', 0.0, 24, 0.1], trial 4, seed 1974100903, tick 739: native elixir 3.1022, HUD elixir 9; acceptance 1147.21 ms; 58.89 FPS; HUD clock 144. No pixel detection before the 1.8 s observation limit. HUD baseline elixir error; likely reader miss. Native acceptance is timely. Raw frame/after-HUD trace was not retained, so short-lived stale pixels versus digit misread cannot be conclusively separated.
- Cell ['grpc', 0.0, 24, 0.1], trial 29, seed 1974100927, tick 1020: native elixir 3.1040, HUD elixir 9; acceptance 1135.10 ms; 58.89 FPS; HUD clock 130. No pixel detection before the 1.8 s observation limit. HUD baseline elixir error; likely reader miss. Native acceptance is timely. Raw frame/after-HUD trace was not retained, so short-lived stale pixels versus digit misread cannot be conclusively separated.
- Cell ['grpc', 0.0, 24, 0.1], trial 35, seed 1974100933, tick 1020: native elixir 3.1040, HUD elixir 9; acceptance 1136.69 ms; 58.88 FPS; HUD clock 130. No pixel detection before the 1.8 s observation limit. HUD baseline elixir error; likely reader miss. Native acceptance is timely. Raw frame/after-HUD trace was not retained, so short-lived stale pixels versus digit misread cannot be conclusively separated.

Every miss is Cannon (cost 3). The erroneous baseline of 9 makes the unchanged cost±1 spend predicate seek a post-play HUD near 6 instead of the actual near-zero balance. The HUD clock agrees with the native pre-tap tick at its one-second resolution. All four native acceptances leave more than 600 ms before the 1.8 s trial limit, and capture is roughly 59 FPS: there is no evidence of slow native acceptance or a gross frame-delivery stall. Baseline HUD error is directly recorded; attribution to the digit reader rather than brief stale imagery remains an inference. None is excused from the denominator; sensitivity stays 316/320 = 98.75%. No thresholds or reader were tuned.

## Stale re-tap reproduction

- stale-retap: 2 taps attempted, 1 accepted, measured spend 4.000; second command {'state': 'tap', 'slot': 1}.
- pending-ledger: 1 taps attempted, 1 accepted, measured spend 4.000; second command {'state': 'blocked', 'reason': 'pending'}.

Both arms use the same seed and cached pre-tap HUD. The stale arm sends a second command at 700 ms; the ledger arm blocks it as pending and keeps the optimistic spend. This isolates the redundant-command failure mode, not an additional successful double spend. The injected second-play demand is 1/1 in each paired arm; natural planner demand frequency was not measured by this transport bench and remains for simulator/runtime evaluation.

## Timing implementation and limits

`actuator.py` loads `actuation/backend-timing.json`: verification deadline = most recent submission + measured D_b,p99 + 600 ms; rollback = deadline + 200 ms. For gRPC these are 1787.32 and 1987.32 ms. The single retry retains the existing 150 ms wait after the deadline, requires a fresh HUD with the card present and affordable, and starts the same backend-relative window for the retry without a second reservation. No retry is emitted after rollback. Existing fresh-HUD remapping, confirmation predicate, single outstanding command and one-second failure hold remain.

Seven actuator unit tests cover configured deadlines, delayed acceptance, no early retry, one retry, spend preservation and rollback, absent/unaffordable/stale retry blockers, HUD remapping and false confirmations. Collector/storage/converter tests are recorded separately in `validation-20261007-final.log` (the original short synthetic timing failures are retained separately).

Renderer relaunch receipt: `emulator-host/relaunch-20261007/complete.json`; emulator-5584, adb 5042, gRPC 8558, probe 26794, read-only AVD, host GPU, 2 cores / 3 GiB. Pinned attestation SHA256 `864227bf7208aa9c06cd976db3fa0734a32277b0552f92e496ad283a917b4a93`; IPv4 and IPv6 UID REJECT rules rechecked. APK, hook and command age are unchanged. No new attestation was created.

T1 is independent: it uses scheduled native receipts for exact execution labels, not this pixel verifier. T2 failure blocks production P4 qualification; it does not block preregistered T1 acquisition. Delay-aware planner and S-d simulator validation belong to the coordinator’s separate player task.

All raw factorial, stale and specificity rows are preserved under `actuation/`; development trials remain diagnostic only. The retained baseline has no raw screenshot/after-HUD sequence, which limits retrospective miss attribution.
