# END A5 fixed-code smoke: independent health/result review r1

- Reviewer: independent Opus, on 127x05, read-only. I made no SSH connections, ran no backends or timing, made no commits and edited no T1 files. I didn't run the verifier.
- Written 2026-10-12T06:03Z, against origin/main 40e0462c. The A5 adoption is 46ab6923 (merge 8799a0d6).
- Attempt: `end-a5-smoke-127x08-0a87166f-r1`.
- Received at `end-received/127x08/end-a5-smoke-127x08-0a87166f-r1/`. Below, `DM/` means its `durable-measurement/`.
- Local computation used `nice -n 19 taskset -c 63 python3 -I`. Scratch scripts are in `/tmp/a5smoke-review/`.
- **I opened no old-code attempt data:** nothing from A6, 01 r1 or 08 r2/r3. From the A6 review I used only its criteria; the only A6 number used is the 55 m 11 s duration basis, which A5 §6 itself cites. I opened no reporting outcomes and no heldout data.

## Verdict: **PASS_WITH_NOTES**

The smoke ran the A5-adopted bytes with the pinned argv and exited 0. Its 29 sealed outputs hash-match manifest 476b50b5. I recomputed every A6-style gate from the raw files, and each one reproduces and passes.

**The race fix was exercised in the regime that failed 08 r2/r3:**
- the admit-guard duration was D ≈ 1.092 s;
- the first sample came 1 ms after the admit reply;
- the telemetry scan taken just before that sample saw **none** of the 10 workers;
- yet the guard owned all 10 at that sample, and `foreign_compute` stayed empty in all 2124 + 476 guard rows.

Nothing blocks the A5 references. The notes below are procedure and descriptive items. One remaining formal step: R4 requires the full C-a to C-d and verifier flow, so the smoke counts as "passed" only after T1's approved verifier ACKs it at or after C-d = **06:13:24Z** (exit 05:51:44Z + 1300 s).

## Findings

### Q1: approved bytes, argv, identity

1. **`measurement_files` equals the A5 commit inventory, 18/18.**
   - I recomputed sha256 of the 18 inventory files (`.py`/`.sh` plus `spec-pins.json` directly under `…/mac-e4-package/e4v3/`) with `git show 8799a0d6:`. `DM/fleet-identity.json` `measurement_files` is dict-equal to that set, with no missing, extra or differing entries.
   - `fleet_validity.py` is `0775b704905324d7…`, and the `runtime_files` entry for `fleet_validity.py` is also 0775b704.
   - The five A3 code SHAs are unchanged: measure_tiers 6066228b, fleet_reference c767a6e0, tier_backend 02e2139f, state_rows 3899276b, prepare_bundle a1c59fa3.
   - The inventory is identical at origin/main 40e0462c. It also matches `reports/explore/t1/receipts/END-A5-runtime-manifest-inventory-diff.json` `full_18_inventory`, whose only diff entry is `fleet_validity.py`.
2. **Other identity fields:**
   - native `44874fd6…`;
   - `load_profile.slot_count` = 11, `warmup_seconds` = 300, `nice` = 10;
   - `search_cpus` [0..4] plus 10 background masks of 5 (55 distinct CPUs);
   - `manifest_sha256` = c84d65ed…, equal to the argv `--manifest-sha256` and to the launch-preparation and launch receipts;
   - host 127x08, `end_kind` = `unpoolable-smoke`, `live_actions=false`.
3. **The argv is the pinned argv.**
   - `sha256(argv.nul)` = 7e4acfa5…, which equals the pinned `END-A5-smoke-approved-argv-08-r1.nul` and `argv_nul_sha256` in `END-A5-smoke-launch-preparation-08-r1.json` (ea5e3d59, 053f898d).
   - Decoded, it equals `measurement_argv` in `END-A5-smoke-launch-receipt-08-r1.json` (**615c7f4e**, commit 50775f0b) element for element:
     - the A5 runtime `end-a5-0775b704-0108-r1/runtime/…/e4v3/measure_tiers.py`;
     - the smoke bundle;
     - `--native …/native/clasher_core.abi3.so`;
     - `--fleet-reference`;
     - `--manifest-sha256 c84d65ed…`.
   - The frozen launch argv `END-A5-smoke-approved-frozen-argv-08-r1.nul` (58501e29) decodes to the receipt's `launch_command`. That command is `nice -n 10 taskset -c 61 bash END-frozen-detach-aeeb3003.sh … END-approved-exit-push-0a87166f.sh <job> <measurement argv>`.
   - The receipt records:
     - C5 pre-exec gate passed: parent nice 0, SCHED_OTHER, `command_byte_equal`;
     - E4 python at nice 10 and SCHED_OTHER;
     - no signals sent;
     - launch SSH closed at 04:55:46Z;
     - `source_commit` 8799a0d6, `reporting_guard_freeze` 24817e16, `wrapper_sha256` 0a87166f.
   - `sha256(PREPARED.json)` = **be30258e**, equal to `END-A5-smoke-receive-prepare-08-r1.json` (053f898d) and `prepare_proof_sha256`.
   - `END-A5-smoke-prelaunch-checks-08-r1.json` (915a86c9) records:
     - C1 with no earlier wrappers;
     - console 0;
     - actual apt-daily run and exit verified (exit at 23:59:28Z, 10-11);
     - next apt-daily at 08:49:07Z;
     - `prelaunch_assertions_pass` true.
4. **Exit and outputs.**
   - `exit.json`: exit_code 0 at 05:51:44Z, with `measurement_exists`. `detach.json`: launched 04:55:46Z, pgid 1334939.
   - `TRANSFER-COMPLETE.json` is at 05:51:49Z with `hash_verification_pending: true`. That is left to the verifier, but I recomputed the hashes myself:
     - `sha256(DM/receipt-manifest.json)` = 476b50b5…, which equals `receipt-manifest.sha256`;
     - all 29 entries match;
     - no file is missing or extra, apart from the manifest pair itself;
     - scope is FLEET-REFERENCE and status is complete.
   - `detach.log` holds only the progress lines: 125/125 exactness, 125/125 belief/RNG exactness, and 3/3 repeats. There are no warnings or tracebacks.

### Q2: health gates, recomputed from raw

5. **Exactness.**
   - `DM/exactness-tiers.json`: passes, 125/125 `workers_equal`, 125/125 `zero_budget_immutable`, maximum relative difference 0.0 (K0c, K1, K2 and K4).
   - `DM/belief-exactness.json`: passes, 250/250 exact (125 with the deadline on), maximum relative difference 0.0, `posterior_weights_cumulative_ledger_samples_rng_exact` true.
   - `fleet-complete.exactness_class` = EXACT.
6. **Reference validity** (`DM/capacity.jsonl`, script `cap.py`).
   - **Census:** 2124 rows from 05:00:26.8Z to 05:51:18.6Z, split into 275 warmup, 712 speed and 1137 deadline rows. This matches `reference-validity.json` `observations=2124 passes=true`.
   - Every row has `passes=true`, `reason=null` and rules `frozen-t1-op1-op2-op3-op4-op5-op6-v1`.
   - Max sample gap 2.548 s, with 0 `sample_gap_over_3_seconds` flags.
   - SSH: 0 SSH-family CPU ticks, 0 stops, and 0 ticks and 0 stops across all per-block SSH meters.
   - Console count 0 on every row.
   - `foreign_compute` and `foreign_active` were empty on every row.
   - System bus (dbus pid 2001, start_ticks 1269): 0 interfered, 0 retired, core fraction max 0.0046.
   - Idle service `v4-validation-cache-renewed-20261010-08r1`: interfered=false on every row, with cpu 0 and no new children. It is `retired=true`, consistent with the retired 08 HTTP cache; retirement is not a failure reason for idle services in `ReportingGuard`.
   - OP-5 seed admissions: 0 (`guard-sources/parent-source-seed-admission.json` `accepted: []`).
   - Allowlist occurrences (2601 lines; 538 admission, 2063 block): **only** `system_dbus` pid 2001, with no OP-2 confirmations.
   - **Maintenance:** the only maintenance-family process name seen at any time is `unattended-upgr`, the idle shutdown helper present on all 2124 rows. No apt, dpkg, motd, packagekit or update-notifier process appears at any time.
7. **Block validity** (`DM/guard-blocks.jsonl`, script `blk.py`).
   - 238 begin/end pairs, all paired and all passing: 22 warm, 72 speed and 144 deadline. This matches `reference-block-validity.json` `blocks=238 passes=true`.
   - Block SSH: 0 ticks and 0 stops. Console 0.
   - `foreign_compute` and `foreign_active` were empty, and idle interference was 0.
   - dbus max 0.0040.
8. **C5 consistency.** The launch SSH closed at 04:55:46Z, before admission at 05:00:26.8Z. The census shows zero SSH-family activity through the last row at 05:51:18.6Z, and T1's quiet-health receipts from 05:00Z to 05:43Z record `host_probed=false`.
9. **MHz comparison.** I recomputed it independently from `DM/reporting-full-occupancy-mhz.json` and the speed/deadline census, over the 55 pinned physical cores (search plus background masks).
   - The reporting side has 14,646 rows, all 127x08, all with slots=inflight=11.
   - The reference side has 1,849 rows (712 + 1137).
   - The ratio is 1.00232326 (|Δ| = 0.232%), which passes the ≤5% gate. It equals `reporting-mhz-comparison.json` to within float summation order (1e-15).
10. **Memory.**
    - MemAvailable was 120.80 GiB at admission. The minimum was 113.36 GiB on the census (05:24:31Z, speed phase) and 113.87 GiB on the blocks.
    - So the run used about 7.4 GiB for 13 owned processes. The A3 budget for 08 is 39.25 GB (11 × 1.226 GB peak + the 24 GiB floor; `END-A3-memory-08.json`), and the 24 GiB floor was never approached.
    - This is a host-level check only, because per-process RSS isn't recorded.
11. **fleet-complete.** completed, EXACT, repeats=3, **`poolable=false`**, `outcome_access=false`, `live_actions=false`, final=false. This is correct for a smoke:
    - `end-evidence.json` kind = `unpoolable-smoke`;
    - all seven `_a6` sources are `synthetic:true`;
    - `source-plan.json` has profile `e4v3-unpoolable-smoke` and status UNFROZEN;
    - the launch receipt has `unpoolable:true` and `reference_attempt:false`.
12. **Deadline lateness, per cell against its own budget** (`DM/deadline-reference-raw.jsonl`, 7200 rows = 4 tiers × 2 cells × 300 × 3).
    - **1.0 / 200 ms:** 0 rows over 200 ms and 0 over 208 ms.
    - **0.8 / 160 ms:** 11 rows over 160 ms (S ×6, max +5.33 ms; K2 ×3, max +6.16 ms; K4 ×2, max +8.32 ms). **2 rows exceed the 168 ms budget + 8 ms reserve**, with the largest at K4 +8.32 ms.
    - `cut_return_over_208_ms` is 0 in both cells, because it uses an absolute 208 ms threshold. As in the A6 review, it therefore doesn't show the 160 ms cell's reserve overruns.
    - This is descriptive. No lateness gate applies to fleet references.
    - GC (`DM/gc-events.json`, 3554 events): the largest pause inside a decision-deadline window was 21.9 ms (68 such events). Two gen-2 pauses had no decision deadline: 134.4 ms (`opportunity=true`, `decision_deadline=null`) and 170.9 ms (not an opportunity).
    - 12 rows had `belief_had_suspended_transaction`; 58 had preparation hits.

### Q3: was the fix actually exercised?

13. **Yes. D was in the race-triggering regime.**
    - `guard-admission.json` utc 05:00:26.7759Z. First capacity row utc 05:00:26.7769Z, which is **+0.97 ms**. Its `interval_seconds` = 1.0932, so **D ≈ 1.092 s**: above 1 s and well above the ~0.93 s threshold in `END-08r2-DIAGNOSIS-r1.md`. (For comparison: 08 r2 was 1.24 s at +0.001 s; A6 was 0.928 s.)
    - The admission's own census took 0.852 s (`ssh_family_sample.seconds`), and the idle-service meter block took 1.062 s.
    - With D > 1 s the overdue sample fires the moment the admit reply is sent, which is exactly when `fleet_reference` starts spawning.
14. **All 10 background workers were owned at the first post-admission sample.**
    - The admission owned 3 pids: E4 1334946, the mp resource tracker 1335070 and the monitor 1336322.
    - Capacity row 0 owns 13: those 3 plus **workers 1336343–1336352** (start_ticks 158063214–223).
    - Row 0's telemetry `processes` scan contains **none** of the 10 workers. That scan runs inside the same sample, after `timestamp` 1580632.137 and immediately before the guard's ownership snapshot 1. Row 1's scan contains all 10.
    - The worker start_ticks correspond to about t = 1580632.14–.23 s since boot. So the workers were born during and after the start of this sample, spanning the window between snapshot 1 and the guard's census snapshot. This is the r2 failure geometry.
    - The record keeps only the union `owned_pid_start_ticks`, so I can't name which workers were reached only by the new census pass. Under 94d0e7f2, the diagnosis predicts some would have been flagged here; on 0775b704 none were.
    - The owned set was the same 13 pids with the same start_ticks on all 2124 capacity rows and all 476 block rows. No new descendants appeared, and no pid was de-owned (no pre-exec/vfork residual fired).
15. **`foreign_compute` stayed empty throughout** (0/2124 census rows, 0/476 block rows), and so did `foreign_active`.
16. **Genuinely foreign processes: none that the frozen classifier flags.**
    - **What was handled:** the system dbus-daemon is handled as `allowlist_kind=system_dbus` (all 2601 allowlist occurrences), and is metered at ≤0.0046 core. The retired idle service and `unattended-upgr` were handled as idle.
    - **INFO, a recurring unowned `python` process.** Telemetry shows 102 successive short-lived processes with comm `python`, each living about 20–30 s, back to back from 05:00:26Z to 05:51:18Z.
      - None is E4-owned. None is in `foreign_compute`. CPU mean is 0.000–0.001 cores, and `foreign_over_one_core_seconds` is 0.
      - They aren't idle-service `new_children` and they aren't SSH-family, since SSH ticks are 0.
      - The frozen `host_audit.foreign_compute` flags any argv0 `python*` process unless it is excused before ownership is checked. Each instance must therefore match one of the frozen exemptions, for example:
        - one of the exact root-owned commands (the list includes `python /etc/jupyterhub/cull_idle_servers.py --timeout=3600`);
        - an empty cmdline;
        - an argv0 that differs from the comm.
      - I can't identify which without cmdlines; the smoke doesn't record them and I may not SSH.
      - This is frozen T1 classifier behaviour, unchanged by A5: r3 recomputes `foreign` with the frozen classifier on the census rows. It has no CPU impact. Not a gate.
    - **Telemetry-only owned-flag lag, as in A6.** In the 1 Hz telemetry `processes[].owned` flag, the 10 workers show `owned=false` for their first 60 rows. That produced the only `foreign_over_one_core_seconds` entries, all on owned workers. The resource tracker 1335070 is never flagged as owned by telemetry. The authoritative guard set had all of them from row 0, so no gate is affected.

### Q4: blockers and procedure for the A5 references on 01/08

17. **Nothing in the smoke blocks the A5 references.** The required steps before they rely on it are:
    - **(a) Smoke ACK.** T1's approved verifier must ACK the smoke at or after C-d 06:13:24Z (R4: full C-a to C-d and verifier flow). The ACK must match manifest 476b50b5 and the C-a pins, as for A6.
    - **(b) Pre-launch reference assertions (carried over from A6 review finding 9).** Assert that `end-evidence` kind = `counted-reporting` with no `synthetic` sources, and that the plan is the C1 frozen copy with `reporting_hosts` [127x01, 127x08].
      - `END-A5-reference-launch-preparation-01-r1.json` records `unpoolable:false` and `source_inputs_unchanged:true`.
      - `END-A5-runtime-manifest-inventory-diff.json` records that the 01 and 08 base bundles (5df0fa00 and 93daf063) differ from A3 only in `fleet_validity.py`.
      - However, I didn't find the end-kind and plan-status assertions recorded **explicitly** for the A5 references. **T1 should record them before each reference launch.**
    - **(c) Post-exit check (A5 §5.1).** Require all 18 `measurement_files` equal to the 8799a0d6 inventory above, plus native 44874fd6, slots 11, warmup 300 and **`fleet-complete.poolable == true`**. Any mismatch is a failed attempt: STOP.
    - **(d) Duration basis.**
      - The smoke's wall time was **55 m 58 s** (04:55:46 → 05:51:44): exactness 4 m 40 s, background start 1 m 12 s, warmup ~5 m, 3 repeats 44 m 38 s, sealing ~25 s.
      - That is 47 s longer than the 55 m 11 s A6 basis that A5 §6 and the launch receipt use.
      - **Use ≥ 55 m 58 s (the larger observed value) plus the 1300 s C-d for the 01/08 reference schedule.**
    - **(e) 08 window.** 08's next apt-daily is at 08:49:07Z (prelaunch receipt). If the ≥2 h clearance is measured at launch, as the A6 review read it, the 08 reference must launch by about **06:49Z**. That is roughly 35 min after the earliest smoke ACK, and still needs a fresh C2, a V2 prepare proof and the C-a pins. Otherwise it is deferred per §6, without any relaxation. This is a schedule note only.
    - **(f) RG1.** Have no SSH or ControlMaster session open to the timed host at admission. The smoke shows this works: zero SSH-family ticks throughout.
18. **Minor receipt hygiene (non-blocking).**
    - `END-A5-runtime-manifest-inventory-diff.json` carries `"A5_adopted": false` next to `"status": "ADOPTED"`. The first is stale.
    - The smoke's `end-evidence.json` `repository` points at `end-a3-f6cebbaa-0108-r1/source`. That directory holds the synthetic evidence input sources, not code. The runtime, measurement files and argv are all A5, so this is informational only.

### Q5: outcome exposure

19. **None found.**
    - A key scan of every output except the census found no outcome, win/loss, crown, reward or elo fields. The only hits were:
      - `outcome_access=false` and `outcomes_read=false`;
      - `outcomes_sealed=true`;
      - the plan's `outcome_barrier` text;
      - exactness `score_sha256` hashes;
      - `speed-reference.json` `result.scores`/`action`/`candidates`. These are deterministic search-candidate scores on qualification-class corpus states (the measured object, as in the A6 review), not game outcomes.
    - Runtime file names such as `score.py` appear only as pins.
    - The T1 receipts I read carry only health flags, hashes and schedule.
    - I opened no reporting outcomes, heldout data, or old-code (A6, 01 r1, 08 r2/r3) attempt data.
