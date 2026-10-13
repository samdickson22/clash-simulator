# X4S-4 scripts, r9 for Sol re-review (exploration, NEVER ADOPTABLE)

The design is frozen at PLAN r3 87809ae0. The history of the script set:

| Round | Script set | Sol verdict |
|---|---|---|
| r1 | 13fb31d0 | REQUEST_CHANGES (18 findings) |
| r2 | f15691b5 | REQUEST_CHANGES (R2-F1–F10) |
| r3 | 8c443f23 | REQUEST_CHANGES (R3-F1–F8) |
| r4 | 15048bd4 | REQUEST_CHANGES (2a933467: R4-F1–F6) |
| r5 | ffde20ac | REQUEST_CHANGES (3fcf0d2f: R5-F1–F4). R4-F1, F4 and F6 resolved; 96/96 reproduced in all modes and umasks. |
| r6 | 0fc0f243 | REQUEST_CHANGES (10385f37: R6-F1–F3). R5-F2–F4 resolved; 105/105 reproduced. |
| r7 | 81d78349 | REQUEST_CHANGES (4cd3331f: R7-F1–F3). R6-F1 and R6-F3 resolved; R6-F2 partial. |
| r8 | 86fa3c5d | REQUEST_CHANGES (bc8255f0: R8-F1–F8). Coordinator ruling SR-1: an external watchdog becomes the host-safety backstop. |
| r9 | this commit | — |

r9 implements coordinator ruling SR-1 (COORDINATOR 2026-10-13 00:47Z). The Sol r9 scope is:
1. the external watchdog;
2. R8-F4 and rule H-1;
3. no regressions in correctness, evaluation identity, outcome-blindness or I/O confinement.

Under SR-1 the in-process guards become defence in depth. R8-F1/F2/F3/F5/F6/F7/F8 are disclosed residuals covered by
the watchdog; the trivial ones are fixed (see "Sol r8 dispositions"). The guard audit (r8), r7, r6 and r5 sections
below are kept as the record. The QUALIFY-RUNBOOK is updated in a separate commit that pins this one.

Nothing has been run on any host. Everything below was done offline on 127x05, using synthetic fixtures, real
watchdog processes against temporary jobs with fake du/nvidia-smi, and disposable git repositories under /dev/shm.

## Index

| File | r9 vs r8 (86fa3c5d) | SHA-256 |
|---|---|---|
| `watchdog.py` | new (SR-1: the external watchdog) | `903618a8fb0c697015a0fcca65b8fcdf1bf3ebce80f7c6da22644d163b437885` |
| `guard.py` | changed (watchdog required, study/readout markers, live-worker refusal) | `a66b04dd2acbf572bcc86852bc551ca7220252484f43d809f7f6877f4b9f57ef` |
| `x4s4io.py` | unchanged since r8 | `2e8e626831a1807cac99534e3d71c134fa9345ef214bfb312f44752172e9ec56` |
| `studytree.py` | changed (watchdog_ok, HALT, h1_reason, guarded_output H-1, uncached fresh disk) | `28d93ef3d8b23f5bb4bb3c5398599f18009bc7317bd36e028efcc701b651ffb5` |
| `driver.py` | changed (watchdog in final_gate/main, markers, STOP exit, READY H-1) | `07881c1ab463965e7f0320b1cfcf0262cf9496ac4fb792ce33c99337a922daa5` |
| `supervise.py` | changed (watchdog required, markers) | `ae51e9b937385d7f66fb1f465a5775d792c536f80c0de0592103b97bcc9a7f42` |
| `label.py` | changed (block H-1) | `00d8f9634d9e62f1685af981d80341f1a02d6c2f74ecfdbfad9a3b740d7ab9e3` |
| `qualify4.py` | changed (trainer receipt; block H-1) | `05cc98fdcac7f22d429ce497630e39e68185672b4dfe9053944e1822256225fd` |
| `write_report.py` | changed (guarded label plan) | `d4a1b9cfb5f8d8fbb9af8a134eebaf73b376840cb7c3c11af641e796f9746da2` |
| `test_x4s4_offline.py` | changed (r9 watchdog, R8-F4, H-1 rows) | `9456d9cc641443482bbd6783bb7ebe190ba7258ef93f235bee8b4a9bb51f2949` |
| `collect_w.py` | changed (authenticated O gate) | `ed69531e209049019ef56665fcb2723c906df7fd9f4ffe95108b346ac413871e` |
| `verify_onpolicy.py` | changed (authenticated O gate; guarded label plan) | `80351c3ba544aae1f37ff2a83aa7aff7d71127964a8e1b46ae49b972cbfd4c7a` |
| `diagnose.py` | unchanged since r8 | `7511eff3e644ab7226fe1b59d7f379a838902d264123cfef71645e37c80ffbfa` |
| `reduce.py` | changed (block H-1) | `22652490abb1cafc03b619dd2c99694f2440853a07656c171ea476ae590175a1` |
| `audit_seeds.py` | unchanged since r8 | `1e1ac591afc936359f29b7b2d25ddd83ff24709a7558492c0d45655a35e3d76c` |
| `run_fit.sh` | unchanged since r8 | `867dc31b87cd7ce20771a2fdd31a67d30b38d283f080265e9e6f5aa13c298b9c` |
| `seed-sources.json` | unchanged since r8 (v2, 29 sealed declarations) | `bf57cda0b925cc99de6765a3fcf88053a89ef228d7e24fc1fcb36b5ca0bec002` |
| `run_collect.py` | unchanged since r8 | `f945ac6c266267d52689df9cd0b3a658705740a513b86866e16d3786dc64780b` |
| `collect.py` | unchanged since r8 | `ce29b1311cc0489a32f09885fd8f44c5df40ed9d9d7292597b4567c9fa006494` |
| `contention.py` | unchanged since r8 | `994d0391a4e577a9f1a8bc7f9b90401bae0d9cb31ea6bd3ee8fcf5dbded99a8c` |
| `plan.json`, `plan-collect.json`, `plan-qual-capture.json`, `idx-*.json` | unchanged | `13840cc6…`, `57f6a142…`, `45052215…`, `4587c7ed…` |

Every owned Python file compiles under `/usr/bin/python3` 3.8.10 and under 3.12. `bash -n run_fit.sh` passes. The
evaluation runner and the reused files are byte-identical. No frozen consumer changed: `label_game`'s write role
became a module global (default `'data'`, unchanged behaviour) so that smoke-pack can confine its labels to `<job>/qual`.

## SR-1 external watchdog (r9): `watchdog.py`

It is one file of about 240 lines, stdlib only, with no study imports. It has three subcommands: `start` (the launcher:
detached with `start_new_session`, the study marker stripped, waits for the first heartbeat), `status` and `run`.

- **Placement.** Runbook step W0 starts it after staging and before Q1. It runs outside the study tree.
  - The study tree is every live process whose exec environment carries `X4S4_STUDY=<job>`.
  - `guard.py`, `supervise.py` and `driver.py` refuse to start without that marker and without a live watchdog
    (`studytree.watchdog_ok`: recorded pid and start time alive, heartbeat < 30 s, not halted). The driver's
    `final_gate` checks the watchdog before every launch.
  - Every study child inherits the marker. The calibration child's explicit environment now carries it too.
- **Checks.** Each cycle is ≤ 10 s, start to start, and every measurement is bounded:

| Check | Breach |
|---|---|
| STOP (lexists) | not a breach by itself; the study tree must be empty 180 s after STOP appeared (covers the trainer's 120 s checkpoint) |
| deadline file | study processes before it exists; content changed after first read (held in memory); production study processes alive 180 s after the deadline (it works like STOP) |
| MemAvailable | < 24 GiB, or unreadable |
| memory PSI | unreadable; readable high PSI is not a breach (frozen rule: dispatch inhibition only) |
| study processes | > 70 |
| study PSS (smaps_rollup) | > 96 GiB, or unreadable |
| `du -sb <job>` | > 100 GB, failed, or > 5 s |
| `nvidia-smi memory.used` | > 40 GiB, failed, or > 3 s |
| the cycle itself | runs in a worker thread joined with 30 s; a stall is a breach |

- **Deadline and the E8 readout (my interpretation of SR-1, flagged for the coordinator).** A HALT at the
  deadline itself would make the designed post-stop readout (contention, reduce, report; E8) impossible: it would be
  killed, refused by every entry point, and discounted by H-1. So at the deadline the in-process guards stop
  production; the watchdog then requires every production study process to be gone within the 180 s grace, and any
  survivor is a HALT.
  - Only processes marked `X4S4_READOUT=1` are exempt, and only from the deadline. `guard.py` sets that marker exactly
    for `--readout`, which is restricted to the three readout scripts. guard.py, the driver and the supervisor refuse
    it anywhere else.
  - H-1's deadline condition likewise does not apply to `--readout` guard receipts. HALT and STOP still apply to them.
- **HALT.**
  1. `<job>/HALT.json` is created exclusively (0444, fsync'd file and directory; the first reason wins) with its
     epoch, reason and readings, and `STOP` is created.
  2. Every study process is stopped one at a time by PID, each re-verified by (pid, starttime, marker) immediately
     before its signal. It gets TERM, then KILL after 20 s. There are no group signals.
  3. The tree is re-scanned every second until it is empty.
  4. The watchdog stays in kill mode, so HALT is a hard stop: any later study process is stopped too, and every entry
     point refuses new work.
- **Records.** `watchdog/heartbeat.json` holds readings only. `watchdog.log` holds HALT and signal records.
  `watchdog/stop-periods.jsonl` holds STOP start and end times for H-1.
- **No results.** The watchdog reads only /proc, STOP, the deadline file, du/nvidia-smi output and its own files. A
  static test checks its string literals.
- **Tests.** These use the real watchdog process with fake du/nvidia-smi and synthetic marked processes.
  - Healthy run: heartbeat, no HALT, study processes untouched.
  - STOP honoured within the grace: no HALT, and the STOP period is logged.
  - After the deadline, readout-marked processes alone cause no HALT; a production process then does.
  - Each of 14 breaches produces a read-only HALT.json and STOP, stops every study process (a TERM-ignoring one by
    KILL), then stops a later study process too, and leaves another job's process untouched. The 14 breaches are:
    production processes after the deadline, deadline missing or changed; memory; unreadable PSI; process count; PSS; disk; du failure; du timeout;
    GPU over; GPU failure; STOP not honoured; a stalled cycle.
  - After HALT, the runner, supervisor and driver refuse new work.
  - The launcher leaves the watchdog unmarked in its own session; `status` works, and a second start is refused.
  - Static checks: stdlib only, verified one-by-one PID signals, no result paths.

## R8-F4 (r9): every producer → consumer edge requires the producer's matching passed receipt

| Producer (receipt) | Output | Consumer(s) | Check |
|---|---|---|---|
| guard.py qualify4 smoke-pack (`guard-q6-smoke-pack`) | `qual/smoke-pack/batch-0000` | Q6 trainer | **new:** `guarded_output` before anything is imported or opened |
| guard.py verify_onpolicy O (`guard-p7-verify-O`) | `data/O-VERIFIED.json` (+ corpus) | fits (driver), **new:** collect_w (O_W target), **new:** verify OW | `authenticate_gate('O')` (guarded gate + receipt + corpus re-verification) |
| guard.py label plan (`guard-p4-label-plan`) | `data/label-plan.json` | label run; **new:** verify O/holdout; **new:** write_report | `guarded_output` |
| guard.py qualify4 parity (P3) | parity receipt | label plan (and recheck at run/verify) | `guarded_output` (r8) |
| guard.py label run | `label-receipt-*` | verify O/holdout | `guarded_output` (r8) |
| guard.py frozen packer | `onpolicy*/batch-*` | verify (all modes) | `guarded_output` (r8) |
| guard.py collect_w | selection, acceptance smoke | verify OW | `guarded_output` (r8) |
| guard.py verify (O/holdout/OW) | the gates | fits, diagnostic, report | `authenticate_gate` (r8) |
| guard.py contention / reduce / diagnose | C5 receipt / results.json / diagnostic | reduce / report / report | `guarded_output` (r8; an unguarded diagnostic is shown as unavailable) |
| supervisor phases (supervisor-exit, block proofs) | games, captures | qualify4, label plan, reducer | phase evidence + block proofs (r5–r7), plus H-1 on each block |
| driver (READY, accepted calibration) | runtimes | driver reporting dispatch | READY + H-1 |

Tests: missing, failed and changed-identity receipts are refused at the trainer, `collect_w.o_target`, verify O
(label plan), verify OW (O gate) and the report. With its receipt, the trainer passes the check.

## Rule H-1 (r9): late outputs never count

`studytree.h1_reason(job, t)` returns a reason if t is:
- at or after `HALT.json`'s epoch (an unreadable HALT fails closed);
- at or after the deadline (an unreadable deadline fails closed);
- inside a STOP period (the watchdog's log, or a STOP present now).

Completion time is the output's own mtime. H-1 is enforced:
- in `guarded_output` (every guarded consumer), on the guard receipt's write time;
- in `qualify4.block_h1`, on each block proof's write time: `proved_game` refuses, `parity_inventory` skips, and
  `label.authenticate_block` drops;
- in `reduce.load_student`, which skips the block and counts `h1_excluded` (then the fixed-N rule / disclosed
  `--allow-prefix` apply);
- in `driver.ready` / `fits_settled`, on READY (Sol's late READY, R8-F7).

Tests cover each point (after HALT, unreadable HALT, during and after a STOP period, after the deadline, a readout
receipt after the deadline, STOP present now, block, parity, proved_game, reducer, late READY), plus in-time controls.

## Sol r8 dispositions (SR-1)

- **R8-F1 (in-flight verdict, M/E during final verification):** residual. The watchdog covers the tree throughout.
- **R8-F2 (whole owned group):** a guard.py child that exits 0 with live group members is now refused, and the members
  are stopped by verified PIDs. Residual: pool workers outliving a SIGKILLed runner remain study processes, so they are
  counted, limited and stopped on any HALT by the watchdog. Their outputs never count (no passed receipt).
- **R8-F3 (cached disk):** admission and fresh verdicts now clear the du cache before measuring. The watchdog measures
  du every cycle.
- **R8-F4:** fixed (above).
- **R8-F5 / R8-F6 (driver intervals, supervisor/driver PSI, final GPU, fit acceptance):** residuals. The watchdog
  enforces unreadable PSI, GPU, memory, PSS, count and disk for the whole tree at all times.
- **R8-F7 (work after the last checks):** the late READY is covered by H-1. The rest is residual, and H-1 removes any
  output completing during STOP or after HALT/the deadline.
- **R8-F8 (deadline read inside expiry):** residual. Caching the parsed deadline inside studytree was tried and
  reverted, because the suite moves deadlines mid-test, so it was not a trivial fix. The watchdog holds the deadline in
  memory, and its cycle has a 30 s stall limit.
- **Process exits:** the generic two-minute STOP figure now names the fit exception. The watchdog's STOP grace is
  180 s.

**Mutation check (r9)**, observed on the final bytes, in two batches. The originals were restored and their hashes
verified against the matrix snapshot.
- **Batch 1:** the watchdog never kills, the stall check is removed, `guarded_output` ignores H-1, and the trainer
  check is removed. All 14 breach cases failed, along with the four guarded-output H-1 checks and both trainer
  negatives.
- **Batch 2:** block H-1 returns None, the reducer skip is removed, `ready()` ignores H-1, the O gate is read directly
  in collect_w and verify OW, and the label-plan check in verify is removed. The block, parity, proved_game, reducer
  and late-READY H-1 checks failed, along with the collect_w, verify OW and verify label-plan negatives.

## Guard audit (r8): every long-running or spawning path × one checklist

The checklist, applied to every row:
- **(A) Admission:** a fresh, bounded resource admission before any work.
- **(M) Live monitor:** the frozen running-work rules, with every measurement bounded.
- **(E) Independent expiry:** expiry that a blocked measurement, native call or loop cannot stall.
- **(L) STOP/deadline last:** checked last, immediately before the spawn and before any receipt.
- **(F) Fresh guards at final acceptance:** an output counts only after fresh guards, and its consumer enforces that.

These are shared mechanisms in `studytree.py`:
- `bounded()`: any measurement runs with a deadline, and a miss is a breach. `du` is now bounded at 40 s (it was
  900 s), and `nvidia-smi` at 20 s.
- `admit()`: cheap STOP/deadline, then one bounded measurement (dispatch_ok, admission and an optional GPU rule), then
  STOP/deadline again, last.
- `Enforcer`: a thread that every 1 s does only cheap checks: STOP (lexists), the immutable deadline, and the age of
  the last completed verdict. It never measures. A verdict older than `MONITOR_STALE` = 75 s is a breach. It can be
  re-armed for each child.
- `fresh_verdict()`: a fresh bounded monitor verdict, then STOP/deadline last.
- `guarded_output()`: an output counts only through a PASSED `receipts/guard-*.json` that names it with its current
  identity: a file SHA, or a sealed directory's manifest SHA.
- `require_guard()`: the child side. It refuses to run without a live `guard.py` runner, and a watchdog ends the child
  if the runner disappears.

`guard.py` is the generic runner (new in r8). It provides A, M, E, L and F for any command, including the
byte-identical frozen packer.

| # | Path (runbook steps) | A admission | M live monitor (bounded) | E independent expiry | L STOP/deadline last | F acceptance (consumer) | Test |
|---|---|---|---|---|---|---|---|
| 1 | `guard.py` runner (every row marked "runner") | `studytree.admit` + cheap check after registration, immediately before spawn | thread: `studytree.monitor` on the child group (+ GPU ≤ 40 GB with `--gpu`) every 5 s | Enforcer (STOP, deadline, verdict > 75 s) → verified-PID TERM/KILL, failed receipt, exit 3; SIGTERM to the runner does the same; owned children exit if the runner dies | before spawn; under the acceptance lock before the passed receipt | exit 0 + declared outputs (seals verified) + `fresh_verdict` + cheap last → `guard-<name>.json`; consumers use `guarded_output` | "row 1 - guard.py runner", "shared Enforcer", "process exits" |
| 2 | Q1 unit tests (pytest) | runner | runner | runner | runner | the guard receipt is Q1's evidence | row 1; runbook row |
| 3 | `qualify4` Q2 hashes, Q3 frozen, Q4 round trip/parity, Q6 smoke-pack/trainer (`--gpu`), P3 parity | runner | runner; inside, cheap halts per state/capture/game/parity iteration | runner; the child refuses to run without it | runner; and `QualGuard.finalize` (fresh verdict, then cheap) | runner; smoke-pack takes a fresh verdict before and after the pack; label admission requires a guarded parity receipt | "R6-F2 (child side)", "guarded acceptance", "child binding" |
| 4 | `collect_w` Q5 acceptance, P9 O_W collection | runner (`--add`); plus its own admission | runner; plus its own dispatch monitor | runner; the child refuses to run without it | runner | runner; verify OW requires a guarded selection and acceptance receipt | "guarded acceptance", "child binding" |
| 5 | `label.py` P4 plan, P5 run | runner (`--add 50` for the run) | runner; plus the run's own dispatch monitor | runner; the child refuses to run without it | runner | runner; the run requires a guarded plan; verify requires guarded label receipts (`--new-files`) | "guarded acceptance", "child binding" |
| 6 | frozen packer P6 (O, holdout), P9 (O_W) — R7-F3 | runner (`--add 2`) | runner | runner (verified-PID stop; the packer stays byte-identical) | runner | runner verifies the sealed `--output` batch; verify_onpolicy refuses any batch without a passed guard (a post-STOP pack never counts, even with a valid seal) | "guarded acceptance" (verify_batch), row 1, runbook row |
| 7 | `verify_onpolicy` P7 (O, holdout), P9 (OW) | runner | runner | runner; the child refuses to run without it | runner | runner; `authenticate_gate` (fit admission, diagnostic, report) requires a guarded gate | "guarded acceptance" (gate), "child binding" |
| 8 | `diagnose` P11 | runner `--gpu`; plus its own lock | runner (+ GPU); plus its own `guard_factory` | runner; the child refuses to run without it | runner | runner; write_report renders an unguarded diagnostic as unavailable | "guarded acceptance", "child binding" |
| 9 | `contention` P13, `reduce` P14, `write_report` P15 | runner `--readout`: deadline-exempt for these three scripts only; STOP and resources still apply | runner | runner | runner (STOP last) | runner; reduce requires a guarded C5 receipt; write_report requires a guarded results.json | row 1 (`--readout`), "guarded acceptance", "child binding" |
| 10 | `supervise.py` phases: Q2 run/collect, Q4 smoke collection, Q7, Q8, P1, P2, P12 reporting | `admit_phase` = `studytree.admit` (bounded) + `--stop-at` | its loop: memory, PSS, admission (du ≤ 40 s), console helper (≤ 15 s), parity watch; a heartbeat after each bounded block | Enforcer → thread-safe `stop()` (verified PIDs) on STOP, deadline or verdict > 75 s | `final_check` after admission and census, immediately before spawn; `final_reason` before a clean exit | `final_reason` = fresh verdict + cheap last before a clean exit is recorded; consumers `phase_evidence` and driver settle | "supervise.py" row; R5-F1 supervisor case |
| 11 | `driver.py` P10/P12: fits, calibration, READY, reporting launches | `resources_ok` (bounded measurements) + `final_gate` | `Fits.guard` each tick; `calibration_breach` each poll; each healthy verdict feeds the Enforcer | Enforcer re-armed per GPU child → trainer-PID SIGTERM / verified-PID stop on STOP, deadline or a stale guard; any driver exit stops live fits (`finally`) | `final_gate` inside `launch()` (cheap last); calibration rejects STOP after the last poll | calibration result and READY only after a fresh verdict; reporting via the supervisor's final verdict | "driver.py" row; "process exits"; R5/R6 driver cases |
| 12 | Q0 seed audit | — | — | — | — | — | Runs on 127x05 from a /dev/shm export over pinned blobs only. It is not study work on 01. |
| 13 | Staging S0–S3 | S0 preflight (memory, PSI, GPU, disk, absent `J`) | — | — | — | the staging check transcript | Runs before T exists (no HARD-STOP yet), so the guards cannot apply; the copies write only into `J`. |

Runbook: a static test joins continued shell lines and requires every qualify4, label, verify, collect_w, pack,
diagnose, readout and pytest command to run under `$GRD`/`$GRDG`. It also requires both production packs to declare
their batch as a guarded `--output`.

**Residuals (disclosed).** SIGKILL cannot be handled in-process:
- If the driver is SIGKILLed, a running fit continues under its frozen stop file until the driver restarts. The
  restarted driver guards it on its first tick.
- If a supervisor is SIGKILLed, an evaluation runner child continues until the driver flags the attempt, as since r2.
- If `guard.py` is SIGKILLed, owned children exit within about 2 s. A frozen packer or pytest child may finish, but its
  output never counts, because no passed guard receipt exists for it.

The runbook uses only STOP and PID-only SIGTERM, never SIGKILL by pattern.

## Sol r7 findings → fixes (r8)

- **R7-F1 (fresh acceptance):**
  - `QualGuard` (now the child side) takes a fresh bounded verdict, then STOP/deadline, before the smoke pack, after it,
    and in `finalize`.
  - `guard.py` takes a fresh bounded verdict, then STOP/deadline under its acceptance lock, before any passed receipt.
    Consumers accept only that receipt.
  - The same rule now applies to supervisor clean exits, driver calibration results and READY.
  - Tests:
    - a memory breach or STOP arriving after the child exits 0 → a failed guard receipt and no guarded output;
    - the supervisor's `final_reason` under memory 0 or STOP;
    - a calibrator returning while memory is breached → rejected.
- **R7-F2 (expiry independent of measurement):**
  - The Enforcer never measures. A verdict older than 75 s is a breach, and measurements are bounded (du 40 s, GPU
    20 s, `bounded()` deadlines).
  - Admission is one bounded measurement, followed by cheap checks last.
  - qualify4 checks STOP/deadline again before and after scientific initialization.
  - Tests:
    - with the live monitor blocked inside du, STOP, the deadline, and staleness each stop the child within the budget;
    - a blocked admission measurement and STOP during the measurement are refused with no spawn;
    - the Enforcer fires while a measurement is stuck;
    - inactive Enforcers never go stale;
    - `fresh_verdict` turns a measurement deadline miss into a breach.
- **R7-F3 (production packer):**
  - P6 and P9 run the byte-identical packer under `guard.py --output <batch>`.
  - `verify_onpolicy` refuses any batch without a passed guard receipt for its current manifest. So a pack completed
    after STOP or a breach is never accepted, even with a valid seal.
  - Test: verify refuses an unguarded batch.

**Mutation check (r8)**, observed. Each batch ran the whole suite. The originals were restored and their hashes
verified before the matrix.
- **Batch A** removed Enforcer staleness, made admission unbounded, and removed the runner's fresh acceptance verdict
  and its STOP/deadline-last check. These cases failed:
  - row 1: blocked admission measurement, live staleness while blocked, STOP at the end;
  - the shared Enforcer: staleness;
  - supervise.py: blocked admission;
  - driver.py: stale guard.
- **Fresh acceptance verdict alone removed:** the end-of-run memory breach fails. That test was first made
  deterministic: the breach appears only after the live monitor has finished, so only acceptance can see it.
- **Batch B** made `guarded_output` accept anything, made `require_guard` a no-op and made `stop_live_fits` a no-op.
  These failed:
  - row 1's acceptance sub-checks;
  - the guarded-acceptance row;
  - the child-binding row;
  - the process-exits row.

  Three probes were hardened so that a mutant which runs on is recorded as a failure rather than aborting the group.

## Sol r6 findings → fixes → named negatives (r7)

**R6-F1: cheap checks last in the final gate.** `driver.final_gate` first runs the exclusion and status
reconciliation: unresolved anomalies, a live diagnostic, calibration or reporting phase, and every `fit_state`, which
may read the whole events log. Only then does it check STOP (lexists) and the immutable hard stop, so nothing slow
lies between those checks and `io.spawn` in `launch()`. Locked exclusion and the rollback paths are unchanged.

Negative: a genuine completed R5 (launch, returned segment, completion, matching zero child_exit). STOP, or the
deadline, is introduced while the gate's own events-log read completes. `launch()` returns None, `io.spawn` is never
reached, and R5 still reconciles as done. A static check confirms the order.

**R6-F2: guarded qualification.** Every `qualify4` subcommand runs under `QualGuard`.
- **Admission, before any work:** no STOP (lexists), before the hard stop, `studytree.dispatch_ok` (MemAvailable
  ≥ 24 GiB; PSI readable and ≤ 10), and `studytree.admission` (≤ 70 processes including this job; ≤ 100 GB).
  The job's group is then registered (`cpujob-qual-*`).
- **Watcher thread, every 5 s:** applies `studytree.monitor`, the frozen running-work rules (STOP, hard stop,
  MemAvailable < 24 GiB or unreadable, PSI unreadable, own PSS > 50 GiB or unreadable, process and disk caps). High
  PSI is never a stop rule, so dispatch inhibition and the stop rules stay distinct. A breach is latched.
- **Halt points:** the work halts with `QualHalt` at its next check:
  - each state in `frozen`;
  - each capture in `roundtrip`;
  - each parity watch iteration;
  - before and after every smoke-pack game;
  - immediately before the pack, in the frozen packer's per-source callback (`memory_guard` = frozen floor + guard),
    and after the pack;
  - before the trainer opens the batch.

  The labeler's halt hook is the guard during smoke-pack. If no check is reached within 60 s of a breach (a long
  native call), the watcher writes the failed receipt and ends the process (exit 3).
- **finalize():** rechecks STOP, the deadline and the latched breach immediately before the receipt is written. A
  receipt never passes after any of them.
- **trainer:** also gets the fit GPU rules: GPU readable and ≤ 8 GiB used at admission; unreadable or > 40 GB live
  is a breach.
- **Runbook:** Q1 (unit tests, no study inputs) is the only unguarded step. It is checked for STOP before it starts
  and bounded by `timeout 300`.

Negatives, from Sol's reproductions:
- STOP or the deadline at the 48th (last) score: halt, no batch;
- STOP inside the frozen packer (third source): halt, no sealed batch;
- STOP right after the pack returns: halt, not accepted;
- admission refuses PSI 11, unreadable PSI and STOP, and PSI is actually measured;
- live checks: MemAvailable 0 latches `memory_guard` and halts; unreadable PSI is a breach; PSI 50 is not;
- the watcher expires an unacknowledged breach (failed receipt, exit 3, no later receipt);
- the round-trip loop halts at the next capture after STOP (2 scoring calls, not 96);
- finalize writes passed=false under STOP and under the deadline;
- the real CLI (`main parity`) refuses at admission with STOP present and exits 1;
- trainer GPU: unreadable or 50,000 MiB refuses admission; 45 GiB live is a breach;
- the job's group is registered.

**R6-F3: digest failures fail smoke-pack.** smoke-pack requires:
- every game finished;
- rows + drops = attempted for each game;
- attempted = all captures;
- zero `digest_mismatch`;
- no drop reason other than `no_scored_root`;
- at least one sealed game.

A `no_rows` game passes only when its captures all lacked a scored root.

Negatives and controls:
- digest failure on every root of one game (`no_rows`): fails, no batch;
- one digest failure inside a sealed game: fails, no batch;
- controls: two whole no-scored-root games (14 sealed + 2 no_rows; 42 rows + 6 drops = 48) and two single
  no-scored-root roots both pass with complete accounting.

**Mutation check (r7).** Each mutant was run, then the originals were restored and their hashes verified before the
matrix:
- restoring the r6 gate order fails R6-F1 (STOP and deadline);
- removing the in-pack/post-pack/per-capture/finalize checks fails the in-pack, after-pack, round-trip and finalize
  cases;
- removing both the post-game and pre-pack checks fails the late-score cases (each layer alone suffices);
- removing both the digest and the undeclared-drop checks fails the digest cases (each layer alone suffices).

## Sol r5 findings → fixes → named negatives

**R5-F1: STOP and the deadline at the final spawn boundary.**
- `driver.final_gate()` runs inside `launch()`, the single spawn helper, immediately before `io.spawn`, after every
  lock wait and every slow preparation or admission step. It checks STOP (lexists, so a dangling link counts), the
  immutable hard stop, unresolved anomalies, and exclusion: a live diagnostic, calibration, reporting phase or fit. A
  refusal creates nothing and records a `launch_refused` event.
- The fit path also re-runs the gate after `prepare_fit_dirs` (the tree walk and corpus re-verification) and before
  any resume rename. If the in-launch gate refuses after the renames, they are rolled back in reverse, so the stopped
  attempt stays resumable rather than turning into a fresh start.
- The reporting path re-runs the gate after the runtime-inventory checks and before writing `indices-a<k>.json`. An
  indices file left by a refused launch is set aside (`.refused-<t>`) so it never blocks the next attempt number.
- Calibration: a STOP seen after the child exits (not only the deadline) rejects the result, which is renamed
  `.rejected-<t>` and returns `stopped`. Only an accepted result gets
  `receipts/calibration-<id>-accepted-<launch_id>.json`. `prepare_students` re-checks STOP and the deadline after
  calibration, before rebuilding the runtime and again before publishing READY.
- `supervise.final_check` repeats the STOP/deadline check after `admit_phase` and the ForeignCensus baseline,
  immediately before `io.spawn`.

Negatives:
- fits: STOP or the deadline crossing during the DISPATCH.lock wait or the corpus preparation: no child, no receipt;
- fit resume: STOP after the renames is refused inside `launch()`, and segment, complete and the launch receipt are
  restored;
- reporting: STOP or the deadline crossing during the lock wait or the resource admission: no indices file, no child,
  a `launch_refused` event;
- calibration: STOP or the deadline crossing during resource admission: `not_admitted`, no child;
- Sol's post-return control: the calibrator creates STOP, writes its output and exits 0 between parent polls. The
  result is `stopped`, the output is set aside, and there is no acceptance receipt;
- READY is not published when STOP appears after an accepted calibration; the no-STOP control publishes it;
- the supervisor's final check refuses STOP and a past deadline, and is statically ordered after admission and the
  census, before `io.spawn`.

**R5-F2: calibration is owned, counted and excluding work.**
- `studytree.groups` enumerates `receipts/calibrate-*` groups, so calibration counts in the process census and admission.
- `diagnose.live_study_work` lists live calibrations, so `acquire_lock` refuses the diagnostic while one lives.
- In the driver, `live_calibrations()` feeds `resources_ok`, `final_gate` and therefore every fit, calibration and
  reporting launch.
- `reconcile_calibrations()` runs at the top of every tick, and nothing else is dispatched in a tick that found work.
  The driver runs calibration synchronously, so at that point any live calibration group belongs to an earlier driver
  incarnation, and its status cannot be observed. The driver stops it by verified PIDs, sets its output aside
  (`.orphaned-<t>`), and writes `receipts/calibration-<id>-orphan-<launch_id>.json`. Calibration is redone later under
  normal admission. A calibration output with no acceptance receipt (an earlier incarnation's unknown exit) gets the
  same set-aside disposition and is never used.

Negatives, using a real `/bin/sleep` group at the calibration receipt boundary, as in Sol's reproduction:
- it is in `studytree.groups` and the process census;
- the diagnostic lock is refused;
- `resources_ok`, the final gate, a second calibration and a fit launch are all refused, with no spawn;
- a restarted driver stops it by PID (the group is gone), sets the output aside and records the disposition, and the
  next reconciliation is a no-op;
- the other direction: a live diagnostic lock refuses calibration;
- an unaccepted output is set aside;
- static: reconciliation gates `fits.tick(); prepare_students(); games_tick()` in the main loop.

**R5-F3: case-level phase evidence.** `qualify4.phase_evidence` now requires:
- schedule `indices` as a sorted unique int list;
- unique `(index, arm)` cases with seed base+index, whose index set equals `indices`, with the same arm set at every
  index (exactly one in-allocation arm for bank C);
- every block proof named `NNNN.json` for a scheduled index, with proof index and seed equal to the case, `order`
  exactly that index's scheduled arms, and `games` naming exactly those cases;
- a typed exit: `reason`, `returncode` and the `remaining_group_pids` list must all be present, and the list empty;
- `clean` = reason None, returncode 0 and full coverage (every scheduled index proved; `complete_blocks` agrees);
- `interrupted` = a declared guard stop with a returncode in `INTERRUPTED_RETURNCODES` = {0, 1, −SIGTERM, −SIGKILL}.
  0 means the runner finished as the guard fired; −15 and −9 are the supervisor's verified-PID teardown; 1 is Python's
  exit after its pool workers were stopped first. The unproved indices are recorded as `dropped`;
- anything else refuses.

The pinned record adds `dropped`, and label admission re-derives it as before. The test fixture `finish_phase` now
schedules exactly the cases a phase attempted. A phase with an unproved attempted case gets the guard interruption the
supervisor would record (memory_guard, −15), so the fixture no longer masks coverage.

Negatives, Sol's four cases plus four more:
- a clean exit with 4 scheduled and 3 proved;
- a reason-only exit;
- a permitted reason beside returncode 17;
- a K4S-120 schedule at C 3500–3502 whose proofs and games are S-200;
- a duplicate case;
- a proof naming an unscheduled game;
- an exit without its process list;
- an unknown returncode.

Controls: a SIGTERM guard interruption passes, with `dropped=1`, and the healthy complete control passes. Label
admission accepts the healthy receipt and refuses it once the schedule is widened to an uncovered clean case. Two r5
plan probes now refuse earlier and more specifically: games added after the receipt hit `not a scheduled index`, and
the changed-exit probe uses a valid but different exit, so it still exercises `evidence changed`.

**R5-F4: launch-specific resolutions.** An unknown-exit resolution is
`receipts/fit-<id>-exit-resolution-<launch_id>.json`, selected by the current launch. A prior attempt's resolution
can neither authorize nor obstruct a later one. Consumed ACK and RESOLVED names carry a random suffix, so two
attempts settled within one second cannot collide.

Negative: Sol's two resumed unknown partial attempts.
- Attempt 1 fails until its exact ACK arrives, then becomes `stopped`, with resolution-A1.
- After the resume archive, attempt 2 fails: the first resolution does not count.
- Re-presenting attempt 1's ACK is a stale-ACK anomaly.
- Attempt 2's own ACK reconciles it into resolution-A2. Resolution-A1 is unchanged, and two consumed ACKs are kept.

**Q-D2(a): `qualify4 smoke-pack --phases <smoke collection phases> --threads 1 --out <job>/qual/smoke-pack.json`.**
- It authenticates every smoke game exactly as `roundtrip` does, through the shared `smoke_games`: block proof SHA,
  projected terminal identity, capture identity, and cover of indices 0–7 × K4S-120/S-200 exactly once.
- It writes the plan `<job>/qual/smoke-plan.json` (0444), labels every capture with the unchanged
  `label.label_game` (frozen teacher, `--threads`) into `<job>/qual/smoke-raw` (role `qual`), and packs once with
  the frozen `pack()` into `<job>/qual/smoke-pack/batch-0000`, then verifies the seal.
- All three destinations must not exist; there is no resume.
- STOP or the hard stop ends labelling (`label.halt_reason`). That fails the receipt, and nothing is packed.
- Smoke bank only; nothing is written under `<job>/data`.
- `trainer --packed <job>/qual/smoke-pack/batch-0000` then re-verifies and opens it, as in r5.

Test, with the scorer stubbed as in the pipeline tests:
- 16 games and 48 captures, all sealed, and the packed batch seal verifies;
- the batch lies under `<job>/qual/`, the plan is read-only, and `<job>/data` stays empty;
- a rerun refuses;
- STOP halts labelling with no pack;
- a forged smoke game is refused before any write.

**Mutation check.** Disabling each fix in turn makes the matching named cases fail:
- `final_gate` returning None: the three R5-F1 dispatch cases;
- calibration ownership, reconciliation and exclusion removed: R5-F2;
- the fixed resolution path restored: R5-F4, with Sol's exact `exists` refusal;
- the coverage and arm-binding checks removed: R5-F3.

The originals were restored and their hashes verified before the matrix below.

## Offline test results (127x05, /dev/shm, nice 19, cores 0–3, no host contact)

`test_x4s4_offline.py` passes **120/120 under -O0, -O and -OO with umask 077 and 022** (exit 0 in all six).
Receipts (umask 077 runs):

| Mode | Receipt | SHA-256 |
|---|---|---|
| -O0 | [receipts/offline-tests-O0.jsonl](receipts/offline-tests-O0.jsonl) | `69076bd791d6415659eb95ee091082358e4f0ae759e478839d8754f3de4ff7f8` |
| -O | [receipts/offline-tests-O1.jsonl](receipts/offline-tests-O1.jsonl) | `c4fa4807e16dda26348ff448423a445c3bda002f5aada0937f97e86926f987cb` |
| -OO | [receipts/offline-tests-O2.jsonl](receipts/offline-tests-O2.jsonl) | `6f408c8f848ede2f1947400056fd7e862b67e843294f11cadc6aa2ae294987fd` |

**Not covered offline** (qualification §6 on 01, after a GO):
- the native §6 checks;
- the real v2 seed audit with range/count completeness;
- the live STOP test;
- real smoke-pack labelling (native scorer) and the GPU trainer check (Q6);
- guard.py against real host measurements (it was tested offline with stubbed readings and real child processes);
- watchdog.py against the real du/nvidia-smi on 01 (offline it ran as a real process against /proc, the real
  MemAvailable reading, fake du/nvidia-smi and a fake PSI file). W0 and `watchdog.py status` are its first host check;
- the staged RUNTIME-INVENTORY: x4s4/supervise.py, x4s4io.py, studytree.py, qualify4.py, guard.py, x4s3/run.py, runtime.sh,
  fit/run_fit.sh, fit/loader6.json, inputs/assets.npz.
