# X4S-4 scripts, r8 for Sol re-review (exploration, NEVER ADOPTABLE)

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
| r8 | this commit | — |

r8 closes the guard class, not only R7-F1 to R7-F3. Every long-running or spawning path, in qualification and in
production, was audited against one checklist. The table in "Guard audit (r8)" below records each path, and every row
has a named test. The sections for r7, r6 and r5 below are kept as the record of the earlier findings. The
QUALIFY-RUNBOOK is updated in a separate commit that pins this one.

Nothing has been run on any host. Everything below was done offline on 127x05, using synthetic fixtures and disposable
git repositories under /dev/shm.

## Index

| File | r8 vs r7 (81d78349) | SHA-256 |
|---|---|---|
| `guard.py` | new (R7-F1–F3: the generic guard runner) | `545ab3b42de7652f0a08cee8fda9f4c980afcc3b824fc6ba190f1091e62de9fb` |
| `x4s4io.py` | unchanged since r7 | `2e8e626831a1807cac99534e3d71c134fa9345ef214bfb312f44752172e9ec56` |
| `studytree.py` | changed (bounded measurements, admit, Enforcer, fresh_verdict, guarded_output, require_guard) | `51a74b001df910840c83eaf540c436afb41e9c92863648f0d58358c07be19eaa` |
| `driver.py` | changed (GPU Enforcer, fresh acceptance, stop_live_fits) | `6138d9d3e5ed8ec58dc3709967f6757147d79ef9c8331874c8e4b9c245a43943` |
| `supervise.py` | changed (bounded admission, Enforcer, final_reason) | `7b5c887513803ba9838516641df930de92ef2640d3483aeac22f005ed612b030` |
| `label.py` | changed (guarded parity/plan; runs under guard.py) | `ff91730f4ef3536d53d97b28dca813afb522b87e9ded7248c4844a98d3f28c19` |
| `qualify4.py` | changed (runs under guard.py; child-side QualGuard) | `c0d0732f6a09c7a2084d35dfb3c8cccb7ae412ee03fd2e1e3babb5e64eac0b1c` |
| `write_report.py` | changed (guarded results/diagnostic; runs under guard.py) | `26f101006b6f823e96ab0ba20652305c693d4f99983458aec794c441df6dcb48` |
| `test_x4s4_offline.py` | changed (r8 guard-audit rows, fixtures) | `9fd165046d543f6a3abdafe5903d671868072b89aa8f52520bcaf0d3ec3d52de` |
| `collect_w.py` | changed (runs under guard.py) | `4fdee319e93e859e2ddbc8988d06e00d3f1047b95a9eef35c2fb16ea3f193729` |
| `verify_onpolicy.py` | changed (guarded batches, label receipts, OW inputs; runs under guard.py) | `3e5af9100fdcee1d989d8971ca29596a49dba3db95b4b3193f32f82ab3426cbe` |
| `diagnose.py` | changed (runs under guard.py) | `7511eff3e644ab7226fe1b59d7f379a838902d264123cfef71645e37c80ffbfa` |
| `reduce.py` | changed (guarded C5 receipt; runs under guard.py) | `8258a858fc03ac546cca9ec984344cfe25e23c6bb91f51d3e9b6255ec356c1bb` |
| `audit_seeds.py` | unchanged since r7 | `1e1ac591afc936359f29b7b2d25ddd83ff24709a7558492c0d45655a35e3d76c` |
| `run_fit.sh` | unchanged since r7 | `867dc31b87cd7ce20771a2fdd31a67d30b38d283f080265e9e6f5aa13c298b9c` |
| `seed-sources.json` | unchanged since r7 (v2, 29 sealed declarations) | `bf57cda0b925cc99de6765a3fcf88053a89ef228d7e24fc1fcb36b5ca0bec002` |
| `run_collect.py` | unchanged since r7 | `f945ac6c266267d52689df9cd0b3a658705740a513b86866e16d3786dc64780b` |
| `collect.py` | unchanged since r7 | `ce29b1311cc0489a32f09885fd8f44c5df40ed9d9d7292597b4567c9fa006494` |
| `contention.py` | changed (runs under guard.py) | `994d0391a4e577a9f1a8bc7f9b90401bae0d9cb31ea6bd3ee8fcf5dbded99a8c` |
| `plan.json`, `plan-collect.json`, `plan-qual-capture.json`, `idx-*.json` | unchanged | `13840cc6…`, `57f6a142…`, `45052215…`, `4587c7ed…` |

Every owned Python file compiles under `/usr/bin/python3` 3.8.10 and under 3.12. `bash -n run_fit.sh` passes. The
evaluation runner and the reused files are byte-identical. No frozen consumer changed: `label_game`'s write role
became a module global (default `'data'`, unchanged behaviour) so that smoke-pack can confine its labels to `<job>/qual`.

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

`test_x4s4_offline.py` passes **116/116 under -O0, -O and -OO with umask 077 and 022** (exit 0 in all six).
Receipts (umask 077 runs):

| Mode | Receipt | SHA-256 |
|---|---|---|
| -O0 | [receipts/offline-tests-O0.jsonl](receipts/offline-tests-O0.jsonl) | `24d4ac49dd0b609463caffca678d523aa7bc6efd1dcb72b4f0a983caabad47c8` |
| -O | [receipts/offline-tests-O1.jsonl](receipts/offline-tests-O1.jsonl) | `ddaddc5908908cd13b545c0c334aca80458a5c1b2d37f6559a794fd9f3e7bff9` |
| -OO | [receipts/offline-tests-O2.jsonl](receipts/offline-tests-O2.jsonl) | `d80308d90c6554ef203e913b6903e20e5e10e8537a865b959a1f4587ef932422` |

**Not covered offline** (qualification §6 on 01, after a GO):
- the native §6 checks;
- the real v2 seed audit with range/count completeness;
- the live STOP test;
- real smoke-pack labelling (native scorer) and the GPU trainer check (Q6);
- guard.py against real host measurements (it was tested offline with stubbed readings and real child processes);
- the staged RUNTIME-INVENTORY: x4s4/supervise.py, x4s4io.py, studytree.py, qualify4.py, guard.py, x4s3/run.py, runtime.sh,
  fit/run_fit.sh, fit/loader6.json, inputs/assets.npz.
