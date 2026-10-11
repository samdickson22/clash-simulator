# PREREG-K4S per-host qualification procedure (r3 §4.1; checklist F-6)

**Every host named in the freeze needs an accepted qualification receipt before the freeze** (r3 §4.1, and §7
steps 5–6). The proposed host set {127x03, 127x04} was qualified during freeze preparation on the exact runtime
bytes to be frozen. Any later change to those bytes, or any other host, needs a fresh qualification before the
freeze. A launch-time repeat is a separate recheck; it does not replace qualification. Qualification reads no outcome.

1. **Stage the runtime from an S1 runtime pinned at `f81f3655…`.** On 03 that runtime is the X4S2 job; on 04 it is a
   LAN copy of it under `/mpac/sdicks02/jobs-k4s/` (04's `/mpac/sdicks02/jobs/clasher/` is perception evidence and is
   never written). On 01 it is
   the S1 job; on 04 or 08 use any SHA-verified copy.
   ```
   runtime base: python stage_k4s.py --job $JOB --overlay <k4s-confirm checkout> [--base B --inherited-pin P]
   ln -s <owned STOP path> $JOB/STOP            # owned STOP; the runner and every game poll it
   ```
   This verifies every inherited file (1557), every native-source file (77) and every input, against the pin
   and plan.json.
2. **Export the staging extras** with `export_staging_extras.sh $JOB extras.tar` on a git checkout, then extract them
   into `$JOB/repo`. The extras are:
   - the frozen T1 reference runtime (ef4c073a bytes), needed for the K4@1.0 ≡ T1 K4@200 checks;
   - 4 committed receipts read by the unchanged T1 OP-5 tests.
3. **Run the driver** (steps 3–7 below run in order, detached):
   `K4S_JOB=$JOB OWNED_STOP=<owned STOP> NICE={10|19} setsid bash reports/explore/k4s-confirm/run_qualification.sh`.
   - **Pin:** `pin.py` writes `runtime-pin.json`.
   - **Source binding:** `source_binding.py record` snapshots every staged K4S file and the staged T1 tree, and checks
     the T1 tree against `t1-reference-expected.json`, generated from git ef4c073a. `plan.json` is compared after
     reversing only the job-path substitution; no file may be missing or extra.
4. **Batteries.** Run `K4S_JOB=$JOB taskset -c 0-4 nice -n {10|19} bash reports/explore/k4s-confirm/qualify.sh`:
   - host audit (recorded);
   - source binding;
   - SD1 manifest check;
   - the inherited T1 test suite (OP-1..OP-7) plus the K4S tests. Two host-uptime-dependent T1 OP-7 cases run via
     `test_op7_boottime.py` with a pinned CLOCK_BOOTTIME; T1 bytes are unchanged. The independent verifier's tests
     need a git checkout and run there, not on the host;
   - guard-deck regeneration: the frozen `guard-decks.json` sha must be `6d51628b…`, and the regenerated receipt
     must equal it apart from its `utc` field (card support);
   - T1 125-state battery;
   - K4S 125-state qualification (`qualify_k4s.py`);
   - belief ON/OFF (125/250);
   - source-stability verify.
5. **Games.** `qualify_games.sh` runs eleven slots on the planned work cores 0–54. It covers:
   - no-deadline command hashes for K4 (K4S runtime), T1 K4-200 and K4S-200, on qualification seeds 0 and 1;
   - full-runner injected-clock equality, T1 vs K4S, on seeds 5 and 7. This is a deterministic virtual clock that
     advances on polls and native rollouts only, with a single-thread collector;
   - every arm charged (sleep share 1 − c ± 0.02 on every exit path);
   - zero budget (every decision returns the SD1 default);
   - `check_games.py`. It checks the exact inventory and every game's identity and configuration (seed, cell,
     seat, decks, deadline, threads, kernel, arm settings, slot placement) against its driver receipt, and exits
     nonzero on any failure.
6. **STOP test.** Run `runtime.sh reports/explore/k4s-confirm/stop_test.py --job $JOB --stop <owned STOP> --cores 5,6,7,8,9`.
   A running game must exit with the `owned K4S stop` interruption within 5 min, with 0 owned processes left. Only
   the STOP the test wrote is removed. The supervisor STOP path is exercised again in the excluded smoke.
   Then `source_binding.py verify` requires the K4S and T1 sources to be unchanged since step 3, and every driver
   receipt to name the staged runtime bytes and matching game hashes.
7. **Receipt.** The assembler re-verifies current evidence: the current source snapshot equals both the start and
   end snapshots, the end links to the start, the T1 reference still matches ef4c073a, and all 11 canonical
   driver receipts (`qual_tasks.py`) bind exactly their games by hash. It records the sha256 of every consumed
   artifact. Run `runtime.sh reports/explore/k4s-confirm/make_qualification_receipt.py --job $JOB --out qualification-$HOST.json`,
   then commit it under `reports/explore/k4s-confirm/receipts/`. The assembler exits nonzero unless every check
   passes.

The nice level is 19 during preparation on shared hosts and 10 at launch, as for reporting. Qualification seeds are
`4503605837370496+[0,8)`: indices 0–5 and 7 for the games, 6 for the STOP test.
