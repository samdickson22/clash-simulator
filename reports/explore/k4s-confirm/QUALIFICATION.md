# PREREG-K4S per-host qualification procedure (r3 §4.1; checklist F-6)

Run this on every named host before it is admitted. 127x03 was qualified during freeze preparation; 01, 04 and 08
are qualified at launch. Qualification reads no outcome.

1. **Stage the runtime from an S1 runtime pinned at `f81f3655…`.** On 03 that runtime is the X4S2 job; on 01 it is
   the S1 job; on 04 or 08 use any SHA-verified copy.
   ```
   runtime base: python stage_k4s.py --job $JOB --overlay <k4s-confirm checkout> [--base B --inherited-pin P]
   ln -s <owned STOP path> $JOB/STOP            # owned STOP; the runner and every game poll it
   ```
   This verifies every inherited file (1557), every native-source file (77) and every input, against the pin
   and plan.json.
2. **Export the staging extras** with `export_staging_extras.sh $JOB extras.tar` on a git checkout, then extract them
   into `$JOB/repo`. The extras are:
   - the frozen T1 reference runtime, needed for the K4@1.0 ≡ T1 K4@200 hash check;
   - 4 committed receipts read by the unchanged T1 OP-5 tests.
3. **Pin.** Run `runtime.sh reports/explore/k4s-confirm/pin.py --job $JOB`, which writes `runtime-pin.json`.
4. **Batteries.** Run `K4S_JOB=$JOB taskset -c 0-4 nice -n {10|19} bash reports/explore/k4s-confirm/qualify.sh`:
   - host audit (recorded);
   - source binding;
   - SD1 manifest check;
   - the inherited T1 test suite (OP-1..OP-7) plus the K4S tests and the verifier tests;
   - guard-deck regeneration, which must be byte-identical (sha `6d51628b…`, card support);
   - T1 125-state battery;
   - K4S 125-state qualification (`qualify_k4s.py`);
   - belief ON/OFF (125/250);
   - source-stability verify.
5. **Games.** Run `K4S_JOB=$JOB nice -n {10|19} bash reports/explore/k4s-confirm/qualify_games.sh` on cores 5–39. It
   covers:
   - no-deadline command hashes for K4 (K4S runtime), T1 K4-200 and K4S-200, on qualification seeds 0 and 1;
   - every arm charged (sleep share 1 − c ± 0.02 on every exit path);
   - zero budget (every decision returns the SD1 default);
   - `check_games.py`.
6. **STOP test.** Run `runtime.sh reports/explore/k4s-confirm/stop_test.py --job $JOB --stop <owned STOP> --cores 5,6,7,8,9`.
   The drain must take ≤ 5 min with 0 owned processes left. The supervisor STOP path is exercised again in the
   excluded smoke.
7. **Receipt.** Run `runtime.sh reports/explore/k4s-confirm/make_qualification_receipt.py --job $JOB --out qualification-$HOST.json`,
   then commit it under `reports/explore/k4s-confirm/receipts/`.

The nice level is 19 during preparation on shared hosts and 10 at launch, as for reporting. Qualification seeds are
`4503605837370496+[0,8)`: indices 0–4 for the games, 6 for the STOP test.
