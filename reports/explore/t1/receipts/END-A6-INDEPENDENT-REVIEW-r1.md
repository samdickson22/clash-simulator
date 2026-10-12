# END A6 smoke: independent health/result review r1

- Reviewer: independent Opus, on 127x05, read-only. I made no SSH connections, ran no backends or timing, made no commits and edited no T1 files.
- Written 2026-10-12T02:39Z, against origin/main d7c9a496 (receipts at fc473e2d).
- Attempt: `end-a6-127x01-0a87166f-r1`.
- Received at `end-received/127x01/end-a6-127x01-0a87166f-r1/` (paths below are relative to it unless absolute).
- Local computation used `nice -n 19 taskset -c 63 python3 -I`. Scratch scripts are in `/tmp/a6review-sd/`.

## Verdict: **PASS_WITH_NOTES**

A6 ran the approved bytes and argv, exited 0, and its 29 sealed outputs hash-match manifest da9230ad. I recomputed every health/validity gate from the raw files, and each one reproduces and passes. Nothing outcome-revealing is exposed.

Nothing blocks the 08 reference. However, the schedule now has essentially **no slack for the 01 reference under the current 08→01 serial order**. That needs a coordinator decision now (finding 9).

## Findings

### Q1: approved bytes and argv, exit, outputs

1. **The argv is the approved argv.**
   - `sha256(argv.nul)` = d3a6e81e… This equals `argv_nul_sha256` in `reports/explore/t1/receipts/END-A6-launch-preparation-01-r1.json` and `END-A6-launch-receipt-01-20261012T011336Z.json`, and the pinned `/mpac/…/END-A6-approved-argv-01-r1.nul`.
   - Decoded, the argv equals `measurement_argv` element for element:
     - staged A3 runtime `end-a3-f6cebbaa-0108-r1/runtime/…/e4v3/measure_tiers.py`;
     - `--native …/native/clasher_core.abi3.so`;
     - `--fleet-reference`;
     - `--manifest-sha256 ede18ecc…`.

2. **The code identity is the A3 runtime, as recorded by the run itself.** In `durable-measurement/fleet-identity.json`:
   - `manifest_sha256` = ede18ecc…;
   - `measurement_files`: `measure_tiers.py` 6066228b, `fleet_reference.py` c767a6e0, `tier_backend.py` 02e2139f, `state_rows.py` 3899276b, `prepare_bundle.py` a1c59fa3;
   - `native_sha256` = 44874fd6…, which equals `source_reference.native_sha256`;
   - `load_profile.slot_count` = 11, `warmup_seconds` = 300, `nice` = 10.

   The same five SHAs match `git show origin/main:` and `f6cebbaa:` of `…/mac-e4-package/e4v3/`, the copy in `END-A3-package-f6cebbaa.tar`, and `END-A3-runtime-01.json` `source_pins`.

   I can't hash the runtime on 01 itself without SSH. The binding rests on the run's self-record plus `validate_bundle` (start and end), which `fleet_reference.run` calls.

3. **Exit and outputs.**
   - `exit.json`: exit_code 0, utc 02:08:47Z. `detach.json` shows launch at 01:13:36Z. `TRANSFER-COMPLETE.json` is at 02:08:52Z and there's no PUSH-FAILED.
   - The SHAs of `argv.nul`, `exit.json`, `detach.json` and `detach.log` equal `source_metadata_sha256` in `END-A6-postexit-C1-C4-01-20261012T0231Z.json` (C4).
   - I recomputed the manifest:
     - `sha256(receipt-manifest.json)` = da9230ad…, which equals `receipt-manifest.sha256` and the ACK receipt;
     - all 29 entries match, with no extra or missing files;
     - scope is FLEET-REFERENCE and status is complete.
   - `detach.log` holds only the progress lines: 125/125 exactness, 125/125 belief exactness, and 3/3 repeats. There are no warnings or tracebacks.
   - The ACK is valid. Verification ran at 02:30:58Z, which is at or after C-d 02:30:27Z (= exit + 1300 s). The verifier is 753722c9, with the C-a pins.

### Q2: gates, recomputed from raw

4. **fleet-complete** (`fleet-complete.json`): completed, EXACT, repeats=3, `poolable=false`, `outcome_access=false`, `live_actions=false`. This is correct for a smoke: `end-evidence.json` kind = `unpoolable-smoke`, and every `_a6` source is `synthetic:true`.
   - Exactness: `exactness-tiers.json` passes 125/125 (workers_equal, zero_budget_immutable). `belief-exactness.json` passes 250/250 exact.
   - The maximum relative difference is 0.0 in both files.

5. **reference-validity and reference-block-validity**, recomputed independently from `capacity.jsonl` and `guard-blocks.jsonl`.
   - **Census:** 2449 rows from 01:18:30Z to 02:08:21Z.
     - Every row passes and carries rules `frozen-t1-op1-op2-op3-op4-op5-op6-v1`.
     - Max sample gap 2.12 s, with 0 `sample_gap_over_3_seconds` flags.
     - SSH: 0 SSH-family CPU ticks, 0 ssh stops, and 0 block SSH ticks.
     - Console, foreign_compute, foreign_active, system-bus interfered/retired, idle-service interfered and seed admissions: all 0.
     - dbus core fraction max 0.0061.
     - The only maintenance-family processes present are idle daemons (`unattended-upgr` shutdown helper, `cron`, `snapd`, `sshd`). No apt, dpkg or motd process appears at any time.
   - **Blocks:** 238 begin/end pairs, all passing.
     - 22 warm, 72 speed and 144 deadline blocks, which is exactly the expected 216 measured set plus warmup, with nothing missing or extra.
     - SSH: 0 SSH ticks, 0 flagged blocks and 0 SSH processes.
     - dbus/idle: 0 interference; dbus max 0.0074.
   - **Consistency with C5.** The launch SSH closed at 01:15:04Z, before admission at 01:18:30Z. The census shows zero SSH-family activity through the last row at 02:08:21Z. T1's C1 SSH at 02:31:47Z came after both the exit (02:08:47Z) and C-d.

6. **MHz comparison.** I recomputed it from `reporting-full-occupancy-mhz.json` (29,170 rows, all slots=inflight=11) against the reference speed/deadline census (2,120 rows) over the 55 pinned physical cores.
   - Ratio 0.99922632, |Δ| = 0.077%, which passes the ≤5% gate.
   - This matches `reporting-mhz-comparison.json` to the last digit.
   - The reporting MHz rows are real 01 reporting and replacement-r1..r3 rows, relabelled `synthetic` for the smoke.

7. **Backend memory against the A3 budget.**
   - The A3 budget is 11 × 1.226 GB peak + 24 GiB floor = 39.25 GB (`END-A3-memory-01.json`).
   - Observed MemAvailable was 120.8 GiB at admission and at least 113.2 GiB at any point (02:00:08Z, deadlines), with the block-level minimum at 113.6 GiB.
   - The run therefore used about 7.6 GiB for 13 owned processes. That is within the 11-peak budget, and nowhere near the 24 GiB floor.
   - Per-process RSS isn't recorded, so this is a host-level check only.

8. **Deadline lateness and cutoff tail** (`deadline-reference-raw.jsonl`, 7,200 rows = 4 tiers × 2 cells × 300 × 3).
   - The 1.0/200 ms cell had 5 rows over 200 ms (K2 ×4, max 203.2 ms; S ×1, 200.3 ms) and 0 cut-returns over 208 ms.
   - The 0.8/160 ms cell had 10 rows over 160 ms. Six of them exceeded 168 ms (budget + 8 ms reserve): K2 max 174.0 ms (+13.96 ms) and S max 172.7 ms (+12.74 ms).
   - The `cut_return_over_208_ms` counter uses an absolute 208 ms threshold for **both** cells, so these 160 ms-cell reserve overruns show as 0 there. This is a descriptive point, not a gate: no lateness gate applies to fleet references, and A3-P is Mac-only.
   - GC: the largest pause inside a deadline window was 21.1 ms. The 177 ms gen-2 pause fell outside any opportunity.
   - Twelve rows replayed a suspended transaction, as the corpus selection expects.
   - **Note:** pooling/PC reporting should state per-cell overruns against each cell's own budget, not rely on the 208 ms counter.

   **Low, telemetry-only note.** In `capacity.jsonl`, the per-process `owned` flag lagged for the 10 background workers (pids 1822397–406) during FleetBackground start-up, 01:18:30–01:19:47Z, which produced 61 `foreign_over_one_core_seconds` rows. Pid 1821164 (an mp helper) is never flagged as owned. The authoritative guard set (`owned_pid_start_ticks`, 13 pids) included all of them from row 0, foreign_compute stayed empty, and the first guarded block began at 01:19:49Z. No gate is affected.

### Q3: blockers and procedure for the 08/01 references

9. **Nothing blocks the 08 reference. The 01 window, however, is practically lost under strict serial order.**
   - **Observed A6 timeline (01:13:36 → 02:08:47 = 55 m 11 s):**

     | Phase | Duration |
     |---|---|
     | exactness | ~4 m 54 s |
     | background start-up | 1 m 19 s |
     | warmup | 5 m 00 s |
     | 3 × (speed 5.5 min + deadlines 8.9 min) | 43 m 30 s |
     | sealing | ~26 s |

     The references use the same path, so expect about 55 min each on the identical 3990X.
   - **The serial path to the 01 launch:** 08 launch L → exit at L + 55 m → C-d (+1300 s) → ACK, C1 on 08, then fresh C2/motd, roster and prepare-proof commit on 01. That puts the 01 launch at about **L + 80 min**. To meet 01's cutoff of 04:17:43Z, **L must be ≤ about 02:55–02:57Z**.
   - As of 02:39Z, 08 is still in a prelaunch layout hold (d7c9a496, ruling L1).
   - **Required:** the coordinator must decide one of the following now, before the 08 launch:
     - (a) keep 08→01 and accept that 01 is deferred per c6387611, to after 01's 06:17:43Z apt-daily. The next clean window then needs launch by 11:36:48Z because of apt-daily-upgrade at 13:36:48Z.
     - (b) run **01 first**. 01 is already C1-clean (02:31:47Z) and its window closes first; 08's window allows a launch until about 06:49Z (apt-daily 08:49:07Z).
     - (c) allow the 01 launch to depend on 08's *launch*, not 08's ACK. C5 forbids SSH only into the timed host.

     Rulings 0b45a3dc/c6387611 fix the order at 08→01, so (b) and (c) need a new ruling. Don't relax any margin.
   - **Required for each reference bundle, before launch:**
     - assert that `end-evidence` kind = `counted-reporting`, with no `synthetic` sources;
     - assert that the plan is the C1 frozen copy with `reporting_hosts` [127x01, 127x08] (A6's `source-plan.json` was the `e4v3-unpoolable-smoke` profile, status UNFROZEN);
     - **after exit:** require `fleet-complete.poolable == true`, plus the same five code SHAs, native 44874fd6, slots 11 and warmup 300.

     A reference that silently comes out `poolable=false` would burn the window.
   - **Recommended:** T1 should record this observed 55 m 11 s timeline as the duration basis for the 08/01 schedule. The 02:06Z ruling had none.

### Q4: outcome exposure

10. **None found.**
    - A key scan of all outputs except the census found no outcome, win/loss or crown fields.
    - `outcomes_read=false` and `outcomes_sealed=true` wherever present; `blind-ledger.json` has no events and is sealed.
    - `speed-reference.json` `result.scores` are deterministic search candidate scores on qualification-class corpus states (corpus seed bank, not reporting games). They are the reference's measured object, not game outcomes.
    - The T1 receipts carry only health flags and hashes.
    - I didn't open the corpus payloads or reporting outcomes.
