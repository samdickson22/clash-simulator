# X4S-4 scripts, r7 for Sol re-review (exploration, NEVER ADOPTABLE)

The design is frozen at PLAN r3 87809ae0. The history of the script set:

| Round | Script set | Sol verdict |
|---|---|---|
| r1 | 13fb31d0 | REQUEST_CHANGES (18 findings) |
| r2 | f15691b5 | REQUEST_CHANGES (R2-F1–F10) |
| r3 | 8c443f23 | REQUEST_CHANGES (R3-F1–F8) |
| r4 | 15048bd4 | REQUEST_CHANGES (2a933467: R4-F1–F6) |
| r5 | ffde20ac | REQUEST_CHANGES (3fcf0d2f: R5-F1–F4). R4-F1, F4 and F6 resolved; 96/96 reproduced in all modes and umasks. |
| r6 | 0fc0f243 | REQUEST_CHANGES (10385f37: R6-F1–F3). R5-F2–F4 resolved; 105/105 reproduced. |
| r7 | this commit | — |

r7 fixes R6-F1 to R6-F3 narrowly (driver.py, qualify4.py, tests). Sol's cases are named negative tests. The r6 text
below the r7 section is kept as the record of R5-F1–F4 and the Q-D2(a) smoke-pack. The QUALIFY-RUNBOOK is updated in a
separate commit that pins this one.

Nothing has been run on any host. Everything below was done offline on 127x05, using synthetic fixtures and disposable
git repositories under /dev/shm.

## Index

| File | r7 vs r6 (0fc0f243) | SHA-256 |
|---|---|---|
| `x4s4io.py` | unchanged since r6 | `2e8e626831a1807cac99534e3d71c134fa9345ef214bfb312f44752172e9ec56` |
| `studytree.py` | unchanged since r6 | `0cd352b5b02b0e29d0c6929eeba6766cb343e5b923077372a0a6153f9b3525c5` |
| `driver.py` | changed (R6-F1) | `818fc3d4ee7f8a784b7a33a0db54b7df2ebb5811f041a123151ebfa38fe480dc` |
| `supervise.py` | unchanged since r6 | `b4662a66a4a5ce808ab668f7e2831a195581e00355ee3561bfd98a795ce2b5b4` |
| `label.py` | unchanged since r6 | `78622dcb8f0cc4eed3e2f89da614df76f8df3d06e6cd0c6507c4a07642673b06` |
| `qualify4.py` | changed (R6-F2, R6-F3) | `c6166c888912d51db8972fe1b9f9256664921930ea06a395ad409b2894adce0a` |
| `write_report.py` | unchanged since r6 | `1e634d034e55f24ac442b2288f0212b71d0bfed6f47ff43b749ecdb991d4e96e` |
| `test_x4s4_offline.py` | changed (r7 negatives) | `8f74b25e000aeee2ddaff82db49978535fec0322c73f585ab1d513ab833e01f2` |
| `collect_w.py` | unchanged since r6 | `68c187e0f2dabd3cf708083522e618c0b264b499d9efc560a950d415d2711a3a` |
| `verify_onpolicy.py` | unchanged since r6 | `b85837d704aa7b1f1cf4a18a47099efce1b8108def97b59af1efb527a0152040` |
| `diagnose.py` | unchanged since r6 | `f691989bab7d7fc672645402e74bd53e8fce5fbaf6db5d2b8ae80638a738e3a4` |
| `reduce.py` | unchanged since r6 | `bb6fc580d3d3e84457edd67b45ff799ab5c1fab2393d2b74b89e0108267201bf` |
| `audit_seeds.py` | unchanged since r6 | `1e1ac591afc936359f29b7b2d25ddd83ff24709a7558492c0d45655a35e3d76c` |
| `run_fit.sh` | unchanged since r6 | `867dc31b87cd7ce20771a2fdd31a67d30b38d283f080265e9e6f5aa13c298b9c` |
| `seed-sources.json` | unchanged since r6 (v2, 29 sealed declarations) | `bf57cda0b925cc99de6765a3fcf88053a89ef228d7e24fc1fcb36b5ca0bec002` |
| `run_collect.py` | unchanged since r6 | `f945ac6c266267d52689df9cd0b3a658705740a513b86866e16d3786dc64780b` |
| `collect.py` | unchanged since r6 | `ce29b1311cc0489a32f09885fd8f44c5df40ed9d9d7292597b4567c9fa006494` |
| `contention.py` | unchanged since r6 | `0139abc5590fdb1bd5698bde97b9d63362ebc929c2eb85b14f27cb5d0ae53be3` |
| `plan.json`, `plan-collect.json`, `plan-qual-capture.json`, `idx-*.json` | unchanged | `13840cc6…`, `57f6a142…`, `45052215…`, `4587c7ed…` |

Every owned Python file compiles under `/usr/bin/python3` 3.8.10 and under 3.12. `bash -n run_fit.sh` passes. The
evaluation runner and the reused files are byte-identical. No frozen consumer changed: `label_game`'s write role
became a module global (default `'data'`, unchanged behaviour) so that smoke-pack can confine its labels to `<job>/qual`.

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

`test_x4s4_offline.py` passes **108/108 under -O0, -O and -OO with umask 077 and 022** (exit 0 in all six).
Receipts (umask 077 runs):

| Mode | Receipt | SHA-256 |
|---|---|---|
| -O0 | [receipts/offline-tests-O0.jsonl](receipts/offline-tests-O0.jsonl) | `69db7363327d36341d3e9a136434d061e72a1a8af7084567566fca8a679cf09c` |
| -O | [receipts/offline-tests-O1.jsonl](receipts/offline-tests-O1.jsonl) | `f6aacdda08a4093e77f6197a0407915d740d66942a8e7899b46040d85f297734` |
| -OO | [receipts/offline-tests-O2.jsonl](receipts/offline-tests-O2.jsonl) | `090e2546ae341207f2e510591426dc7bb93ecd45608eda4191f0ca752cc866da` |

**Not covered offline** (qualification §6 on 01, after a GO):
- the native §6 checks;
- the real v2 seed audit with range/count completeness;
- the live STOP test;
- real smoke-pack labelling (native scorer) and the GPU trainer check (Q6);
- the staged RUNTIME-INVENTORY: x4s4/supervise.py, x4s4io.py, studytree.py, qualify4.py, x4s3/run.py, runtime.sh,
  fit/run_fit.sh, fit/loader6.json, inputs/assets.npz.
