# X4S-4 scripts, r10 for the SR-2 fix-check (exploration, NEVER ADOPTABLE)

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
| r9 | a701d610 | REQUEST_CHANGES (1b68d637: R9-F1–F8). Ruling SR-2: fix all eight, then one diff-only fix-check. |
| r10 | 8bde7397 | Fix-check (e5b71aae): six FIXED; R9-F3 and R9-F7 NOT FIXED. Ruling SR-3: one narrow closure each. |
| r10.1 | this commit | — (the coordinator verifies the diff) |

r10 fixes Sol r9's eight findings, each with a named test, and changes nothing else (ruling SR-2). The sections
below it (r9, r8 and earlier) are kept as the record. The QUALIFY-RUNBOOK is updated in a separate commit that pins
this one.

Nothing has been run on any host. Everything was done offline on 127x05, with synthetic fixtures, real watchdog
processes against temporary jobs (fake du/nvidia-smi/PSI) and disposable git repositories under /dev/shm.

## Index

| File | r10.1 vs r10 (8bde7397) | SHA-256 |
|---|---|---|
| `watchdog.py` | changed (SR-3: R9-F3 readout root) | `aad317db1e68068ea73c1764818fcef7e494cc8c4777a97bd54e3815c4d1300d` |
| `packw.py` | changed (SR-3: R9-F7 inventory) | `664b9dc085f055f3bf64e39ca62cd1b5466d3e57ddc92e55479b737d5f156b8b` |
| `guard.py` | unchanged since r10 | `0c9bbd20cc0a08f617c1bc8902f040ea24d5ab78cee5f508ffb33c4c35c7893c` |
| `x4s4io.py` | unchanged since r10 | `2e8e626831a1807cac99534e3d71c134fa9345ef214bfb312f44752172e9ec56` |
| `studytree.py` | unchanged since r10 | `39b0c1513ef3e8ce491991894db7d137fff2ed831dae4083e4bda2d47fd9e5c5` |
| `driver.py` | unchanged since r10 | `98ab91c4e5383285afb8607a40e3e81b543a96d6cc40b6467a8ff009971e43bf` |
| `supervise.py` | unchanged since r10 | `ae51e9b937385d7f66fb1f465a5775d792c536f80c0de0592103b97bcc9a7f42` |
| `label.py` | unchanged since r10 | `72cf7e2a6affebcfaf7269ce2d1851a2705a32b468344cb0e579e7910e96b7b1` |
| `qualify4.py` | unchanged since r10 | `05cc98fdcac7f22d429ce497630e39e68185672b4dfe9053944e1822256225fd` |
| `write_report.py` | unchanged since r10 | `0ab155b24203a16eefac6cf53c2a30f624779321505e2d9a48a60ecb22df8ed9` |
| `test_x4s4_offline.py` | changed (SR-3 tests) | `545ea9d60ee2db6b6084e40213e957311eb59a371c224abeddb9778fbd6a7006` |
| `collect_w.py` | unchanged since r10 | `0cb4167206e27ef97c4352d68aa5ac2e2ba9a46ddfd25e36393442c8015324f8` |
| `verify_onpolicy.py` | unchanged since r10 | `80351c3ba544aae1f37ff2a83aa7aff7d71127964a8e1b46ae49b972cbfd4c7a` |
| `diagnose.py` | unchanged since r10 | `a199d3ed64c87117a5c5746ca9145ca1eb12f1bcb24f65a3f38c5ae13fb4ed01` |
| `reduce.py` | unchanged since r10 | `db3530934869ef962f1e040092e9953d94501a915de3e9d436e49dbb655b0ba4` |
| `audit_seeds.py` | unchanged since r10 | `1e1ac591afc936359f29b7b2d25ddd83ff24709a7558492c0d45655a35e3d76c` |
| `run_fit.sh` | unchanged since r10 | `867dc31b87cd7ce20771a2fdd31a67d30b38d283f080265e9e6f5aa13c298b9c` |
| `seed-sources.json` | unchanged since r10 (v2, 29 sealed declarations) | `bf57cda0b925cc99de6765a3fcf88053a89ef228d7e24fc1fcb36b5ca0bec002` |
| `run_collect.py` | unchanged since r10 | `f945ac6c266267d52689df9cd0b3a658705740a513b86866e16d3786dc64780b` |
| `collect.py` | unchanged since r10 | `ce29b1311cc0489a32f09885fd8f44c5df40ed9d9d7292597b4567c9fa006494` |
| `contention.py` | unchanged since r10 | `994d0391a4e577a9f1a8bc7f9b90401bae0d9cb31ea6bd3ee8fcf5dbded99a8c` |
| `plan.json`, `plan-collect.json`, `plan-qual-capture.json`, `idx-*.json` | unchanged | `13840cc6…`, `57f6a142…`, `45052215…`, `4587c7ed…` |

Every owned Python file compiles under `/usr/bin/python3` 3.8.10 and under 3.12. `bash -n run_fit.sh` passes. The
evaluation runner and the reused files are byte-identical. No frozen consumer changed: `label_game`'s write role
became a module global (default `'data'`, unchanged behaviour) so that smoke-pack can confine its labels to `<job>/qual`.

## SR-3 closures (r10.1): exactly two changes

1. **R9-F3, the readout root (`watchdog.py`).** A readout root must meet all of these:
   - its environment has `X4S4_READOUT=1`;
   - `argv[0]` is a Python executable;
   - the interpreter's script position, after plain flags only (`-B -u -E -s -I -O -OO`, never `-c` or `-m`), is
     exactly `GUARD_PATH`, the reviewed `guard.py` in the watchdog's own directory;
   - guard.py's options before `--` include `--readout`;
   - the wrapped command after `--` passes guard.py's own allowlist `studytree.readout_invocation`. That function is
     pure and imported from the same directory, not copied; it is the watchdog's only non-stdlib import.

   Tests:
   - eight argv unit cases (real, `-c`, `-m`, another guard path, no `--readout`, `--readout` only after `--`, a
     non-allowlisted wrapped command, a non-Python executable);
   - the former `-c` positive fixture is now a negative and HALTs after the deadline (in both the r9 and r10 tests);
   - the positive is a **real guard.py Runner** subtree. It uses a temp copy of watchdog/guard/studytree whose
     `x4s4io.JOB` names the temp job and is otherwise byte-identical. The Runner admits, spawns its allowlisted child,
     and that subtree keeps running after deadline + grace, while a bare READOUT-marked process HALTs and the HALT then
     stops the Runner tree.

   The ancestry and cleaned-environment checks are unchanged.
2. **R9-F7, the pack inventory (`packw.py`).** Any `game-*` entry that is not a real directory is **refused**, not
   skipped. `check_inventory` then asserts, immediately before the frozen packer is called, that the authenticated set
   equals exactly the packer's `game-*/manifest.json` glob under each root.

   Tests:
   - an authenticated real game plus a `game-*` symlink to a sealed game with no evidence is refused, and the packer
     (spied) never runs;
   - a game appearing after authentication is refused by the inventory check;
   - equal inventories pass.

**Mutants (r10.1)**, observed:
- reverting the readout predicate to "a guard.py token anywhere" makes both inert-token negatives fail;
- making `check_inventory` a no-op makes the inventory-change negative fail;
- skipping non-real `game-*` entries again makes the symlink negative fail.

The originals were restored and their hashes verified before the matrix.

## Sol r9 findings → r10 fixes → tests (SR-2)

**Watchdog.**
- **R9-F1 (stall covers writes and teardown).** The worker thread does every measurement, heartbeat and log write,
  and marks progress after each step. A failed write (for example a FIFO or symlink at a control file) is itself a
  breach. The main thread never touches job files while supervising.
  - HALT runs from the main thread. HALT.json and STOP are written by a helper bounded at 5 s; teardown uses only /proc
    scans and PID signals, and its log records are queued for best-effort writing. So neither a stuck log nor a stuck
    measurement can delay stopping the tree.
  - Test: a FIFO at heartbeat.json HALTs and stops the tree. A FIFO at watchdog.log plus a memory breach still HALTs
    and stops the tree. Stall detection is unit-tested through `due()`.
- **R9-F2 (≤ 10 s cadence).** Measurements start every CYCLE = 9.5 s and must finish within MEASURE_BUDGET = 8 s
  (du 4 s, nvidia-smi 2 s). The main thread HALTs on an overdue measurement or when no measurement has started within
  CYCLE + 0.5 = 10 s. The separate 30 s no-progress stall rule remains.
  - Test: real heartbeats are about 1.0 s apart with a 1.0 s cycle (max gap ≤ 1.5 s). A 3 s measurement HALTs as
    overdue. A late start is unit-tested.
- **R9-F3 (membership and readout binding).** A process is a member if it carries `X4S4_STUDY=<job>`, descends from a
  member (started no earlier than its parent), or was seen as a member before with the same (pid, starttime). So
  exact-environment helpers (`io.run_checked`) and cleaned-environment execs stay counted and stoppable. Every kill
  re-verifies (pid, starttime, membership).
  - The deadline exemption covers only the subtree of a readout runner (a member whose command line is guard.py with
    `--readout` and whose environment has `X4S4_READOUT=1`).
  - `guard.py --readout` accepts only the exact invocation `/bin/bash <repo>/reports/explore/x4s3/runtime.sh
    <repo>/reports/explore/x4s4/{contention,reduce,write_report}.py …` (`studytree.readout_invocation`).
  - H-1's deadline exemption needs that invocation and that script's declared output (`readout_exempt`: contention →
    `receipts/contention-exclusion.json`, reduce → `analysis/results.json`, report → none).
  - Test: a cleaned-env exec and its `env -i` helper are counted (2) and stopped on HALT. Sol's inert-token argv is
    refused. A receipt with the inert argv, or with an undeclared output, is not exempt; the exact one is. After the
    deadline a readout runner's subtree runs while a bare `X4S4_READOUT=1` process HALTs.
- **R9-F4 (malformed readings).** These are measurement failures:
  - PSI without a `some` line, or with avg10 non-finite or outside [0, 100];
  - MemAvailable without exactly one `kB` line;
  - a smaps_rollup without exactly one Pss line;
  - du output that is not `<int ≥ 0>\t<job>`;
  - nvidia-smi output empty or negative.

  A valid high PSI is still not a breach (frozen rule).
  - Test: nan, inf, −1, 101 and no-`some` PSI, MemAvailable without its unit, du garbage and negative du, and
    empty and negative GPU readings all HALT. PSI 99.5 does not.

**Integrity.**
- **R9-F5 (durable STOP evidence).**
  - `watchdog.py resume` is the only sanctioned STOP removal. It durably records the period's start (the existing
    open record, or STOP's own mtime) before unlinking STOP, and the end after, and it is refused after HALT.
  - `watchdog.py stop` records the start before creating STOP.
  - The watchdog creates the history file at start. `studytree.stop_periods` fails closed when the history is missing,
    and keeps a period's earliest start.
  - The runbook never uses `rm STOP`; Q8 uses `watchdog.py resume`.
  - **Clock margin.** File mtimes come from the kernel's coarse clock, which can trail `time.time()` by up to one
    tick. So H-1 widens every boundary (HALT, deadline, both ends of each STOP period) by `H1_MARGIN` = 0.05 s, the
    conservative direction. The matrix found this: one of six runs counted an output written milliseconds after a STOP
    record.
  - Test: a stop/resume pulse completed before the next watchdog cycle leaves start + end, and an output completed
    inside it is excluded while an earlier one counts. A raw STOP is recorded before removal. Missing history fails
    closed. Resume after HALT is refused. An mtime 10 ms before the recorded start is still inside the period.
- **R9-F6 (H-1 on dependencies).**
  - A final fit completion whose `complete.json` or final checkpoint fails H-1 is `stopped`, not `done`.
  - A resume uses `admissible_checkpoint`, the newest step whose completion passes H-1. If there is none, the
    driver raises a blocking `fit-<id>-resume` anomaly.
  - `accepted_calibration` requires the receipt and the output to pass H-1.
  - READY is checked at every consumer (`studytree.ready_student`): the driver, the reducer, the diagnostic and the
    report.
  - Raw seal reuse requires `raw_evidence` (below), which includes H-1 on the seal. A seal without evidence is set
    aside as `unaccepted-game-…` (outside the packer's `game-*` glob) and redone.
  - Test: each of these, including a raw label seal completed during STOP that is set aside even with a passed
    receipt, and the in-time controls.
- **R9-F7 (packing and resume edges).**
  - `studytree.raw_evidence` requires each raw label game to appear with its current manifest SHA in a passed, in-time
    label receipt of its set (label receipts now carry `game_manifests`). Each O_W game must appear in the guarded
    selection, and the seal itself must pass H-1.
  - The new `packw.py` authenticates every input game before calling the byte-identical frozen packer. The runbook's
    P6/P9 use it.
  - Test: missing, failed-only and changed-identity producer evidence are refused; with evidence the packer packs.
    O_W packing needs the selection. The runbook has no direct packer call.

**Regression.**
- **R9-F8 (watchdog confinement).** The watchdog keeps a small stdlib confined writer for its own files, documented
  as the narrow routing exception:
  - directory fds come from an O_NOFOLLOW walk from `/`;
  - leaves are O_NOFOLLOW|O_NONBLOCK and must be single-link regular files;
  - temps are exclusive (O_EXCL), uniquely named and cleaned up;
  - HALT.json is exclusive and 0444.
  - Test: a symlinked heartbeat target, a hard-linked history, a FIFO log (no blocking) and a symlinked pid file are
    refused, and the outside sentinels are unchanged. A symlinked job path or watchdog directory is refused. Static
    checks: builtin `open()` only for /proc and the host meminfo/PSI, and every `os.open` is O_NOFOLLOW.

**Editorial.** The runbook's introduction now states Q-D1's single combined GO.

**Producer → consumer edges added by r10 (R9-F7, R9-F6)**, extending the r9 table below:

| Producer (evidence) | Output | Consumer | Check |
|---|---|---|---|
| guard.py label run (passed, in-time label receipt with `game_manifests`) | raw label games `data/raw-<set>/<arm>/game-NNNN` | packw (P6); label resume | `raw_evidence`: listed with the current manifest SHA, and the seal passes H-1 |
| guard.py collect_w (guarded selection) | raw O_W games `data/raw-OW/game-NNNNN` | packw (P9); collect_w resume | `raw_evidence`: in the guarded selection with this manifest, and the seal passes H-1 |
| driver fit (complete.json, step-*.pt) | final model / resume checkpoint | `fit_state` (done), `Fits.launch` (resume) | H-1 on complete.json and the checkpoint; `admissible_checkpoint` |
| driver calibration (acceptance receipt) | calibration | `prepare_students` → READY | H-1 on the receipt and the output |
| driver READY | runtime/student identity | driver dispatch, reduce, diagnose, report | `ready_student` (H-1) at every consumer |

**Mutation check (r10)**, observed on the r10 bytes before the H1_MARGIN edit (a three-line change with its own test
in R9-F5). The originals were restored and their hashes verified before the matrix.
- **Batch A** made five watchdog mutations: write failures ignored, the overdue rule removed, the ancestry closure
  removed, the PSI range check removed, O_NOFOLLOW dropped. Each of R9-F1, F2, F3, F4 and F8 failed.
- **Batch B** made these integrity mutations, and each of R9-F5, F6 and F7 failed:
  - resume without the durable start, and missing history tolerated;
  - fit, calibration and READY H-1 checks removed;
  - raw-reuse evidence and packw input authentication removed.

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

## HR-2 r2 (Sol fix-check r1, REQUEST_CHANGES): coherent pass state, late returns, monotonic freshness

- **HR2-F1, a false HALT at a pass transition.** The worker cleared `done` before assigning the new `start`, so the
  main thread could pair "unfinished" with the old start. The same pattern existed in the **fast lane since R9**:
  `m_done = None` before `m_start = t0`. With a 9.5 s cycle and an 8 s budget, a poll between the two statements
  would see a start 9.5 s old and HALT. It did not cause 14:32:50Z, whose heartbeat shows a measurement genuinely
  running from 14:32:42.87 to 14:32:50.97.
  - **Fix:** each lane's pass state is one immutable monotonic `(start, done-or-None)` tuple (`fast_pass`,
    `slow_pass`). It is replaced by a single assignment and read once by `due()`. No lock is held across I/O.
- **HR2-F2, a late return accepted.** Both workers now compare the monotonic completion with that pass's own start.
  A pass returning after its budget (slow 120 s, fast 8 s) is a breach whether or not a poll saw it overdue, and it
  never replaces the last good result. A return exactly at the budget is allowed.
- **HR2-F3, wall-clock freshness.** The last good slow result is a new immutable dict stamped with its monotonic
  completion (`mono`). The age check and the reported `slow_age` use the monotonic clock; `epoch` is diagnostic
  only. The startup check was already monotonic.

**Shared state across the three threads** (fast worker, slow worker, main), each read once per decision:

| Field | Writer | Readers | Publication | Hazard |
|---|---|---|---|---|
| `fast_pass` | fast worker | main `due()` | one tuple assignment | none (was F1 in the fast lane) |
| `slow_pass` | slow worker | main `due()` | one tuple assignment | none (was F1) |
| `slow` (last good) | slow worker | fast `slow_verdict` (local copy) | a new dict swapped whole; only in-budget, in-limit passes | none |
| `members_now` | fast worker | slow worker (`list()` once) | a dict replaced whole | none (Sol confirmed) |
| `breach` | both workers | main | goes None → value only; `if self.breach is None` | either worker's reason may win; both HALT (benign) |
| `progress` | fast worker | main (one read) | float assignment | none |
| `halted` | main | both workers (loop condition) | set once | none |
| `started` | `__init__` | fast `slow_verdict` | constant | none |
| `logq` | all | fast worker (`flush`) | `queue.Queue` | thread-safe |

**Tests (added to `test_hr2`):**
- **F1:** the real slow worker (Sol's 119.9 s passes, the next start 0.15 s late) and the real fast worker (0.5 s
  passes every 9.5 s) run on a virtual monotonic clock. The supervisor `due()` is evaluated after EVERY publish of
  pass state, last-good result or breach. There is no false HALT.
- **F2:** exactly at the budget is accepted; just over it (120.15 s; fast 8.15 s) is a breach, and the previous good
  result stays intact. Both lanes are covered.
- **F3:**
  - a +200 s wall step keeps a 1 s-old result fresh;
  - a −1 h step cannot hide a 181 s-old one;
  - `slow_age` is monotonic;
  - a slow thread dead between passes expires (unit), and a real watchdog whose slow thread dies after its first pass
    HALTs and stops the study process.
- **Sol's non-blocking note:** the positive slow-walk test also asserts that the watchdog and the marked process stay
  alive.

**Mutation check:** 14 mutants, each killed. These are the 8 from HR-2 and 6 new ones:
- F1 two-step publish (slow);
- F1 two-step publish (fast);
- F2 late return accepted (slow);
- F2 late return accepted (fast);
- F2 boundary made inclusive (`>=`);
- F3 wall-clock age.

## HR-2: two measurement lanes; the 14:32:50Z HALT

**The HALT.** At 14:32:50Z (T2 + 1.9 h), during P9 O_W collection beside the R5 fit, the watchdog HALTed with
"measurement overdue (> 8 s)". The last completed reading at 14:32:42.87Z was healthy (58 processes, 95 GiB
MemAvailable, PSI 2.94, PSS 35 GB, disk 38 GB). There was no host stall: O_W games completed up to 0.8 s before
the HALT. The watchdog recorded no per-phase timings, so this is the best-supported diagnosis:
- **The budget didn't add up.** The single 8 s measurement held the 4 s-bounded disk walk, the 2 s-bounded
  nvidia-smi, and the unbounded scan and PSS sum. Each part could stay inside its own bound while the sum crossed
  8 s, which is exactly an "overdue" rather than a "failed" reading.
- **The walk grew.** J had reached 564,490 entries. The walk took 2.45 s on the idle host afterwards (against
  0.24 s at 62k entries), more under the fit's page-cache pressure, and ABBA would grow J further.
- **PSS alone can't explain it.** smaps_rollup was checked offline on 05: an 8 GB-mapped process under fault and
  mmap churn read in 35 ms median, 67 ms max. environ was instant.
- The R5 fit had one 7.3 s step ending 14:32:45.7Z (normally 2.0 s), consistent with host I/O contention in that
  window.

**The class.** A reading whose cost grows with the study must not share the fast lane's budget. A slow but healthy
reading must not HALT, and a stuck one must still be bounded.

**The change (`watchdog.py` only).**
- **Fast lane:** the existing worker, cycle 9.5 s, budget 8 s. It keeps the scan, STOP and the stop grace, the
  deadline, MemAvailable, PSI, the process count and nvidia-smi (2 s).
- **Slow lane:** a new worker for member PSS (smaps_rollup) and the job's apparent size (the HR-1 walk).
  - It starts a pass every SLOW_CYCLE (30 s). Each pass is bounded by SLOW_BUDGET (120 s): the walk's own timeout is
    the pass's remainder, and the main thread HALTs a pass still running after SLOW_BUDGET.
  - Only a complete, in-limit pass becomes the last good result.
  - Its limit breaches (PSS > 96 GiB, disk > 100 GB) and failed readings HALT as before.
- **Age checks in the fast lane:** it HALTs if the last good result is older than SLOW_MAX_AGE (180 s), or if none
  arrived within SLOW_MAX_AGE of start. SLOW_MAX_AGE must exceed SLOW_CYCLE + SLOW_BUDGET, so a healthy pass can
  never look stale; this is validated at start.
- **Diagnosability:** per-phase timings of both lanes (`timing`, `slow_timing`, `slow_age`) are in the heartbeat.
- **What changes for safety:** PSS and disk are now checked every ≤ 150 s instead of ≤ 10 s. Memory safety rests
  on the MemAvailable floor, which stays in the fast lane. Disk growth is GBs per hour, against a 100 GB cap.

**Tests (`test_hr2`).**
- **The regression:** the real watchdog over a 150k-entry job. Its walk (0.55–0.62 s) exceeds the fast budget
  (0.3 s), yet there is no HALT, heartbeats continue, and the slow result stays within its age bound.
- **A bounded slow pass:** a walk beyond SLOW_BUDGET HALTs and stops the tree.
- **due() unit:** a stuck pass with no return HALTs after SLOW_BUDGET; a finished or in-budget pass does not; the
  fast overdue rule is unchanged.
- **slow_verdict() unit:** stale results, and none at start, HALT; a fresh result feeds the readings.
- **Arguments:** the max-age validation.
- **Slow-lane HALTs:** disk over, PSS over and an unreadable directory all still HALT.
- All r9/r10 watchdog cases, including R9-F2's timing and overdue checks, pass with small slow-lane settings.

**Mutation check:** 8 mutants, each killed:
- the walk back in the fast lane (this reproduces the incident);
- no stuck-pass overdue;
- no stale-age check;
- no missing-at-start check;
- slow breaches ignored;
- the slow worker not started;
- the max-age validation removed;
- the slow pass unbounded in both the walk and the main thread.

## HR-1 (COORDINATOR 77a01d88): the disk reading is an own bounded walk; the 11:57:58Z HALT

**The HALT.** At 11:57:58Z, during P5 labelling, the watchdog's `du -sb <job>` exited 1. label.py's 48 workers seal
each game into `game-NNNN.tmp/` and rename it, and GNU du exits 1 when an entry vanishes between readdir and stat.
Rule R9-F4 (a failed reading HALTs) then ended the study. `studytree.disk_bytes`, used by admission and the in-process
monitors, ran the same du; it returned None on failure, which fails closed in-process.

**The change.** Every earlier `du -sb` line in this file is superseded by `studytree.tree_bytes(root, timeout)`, a
pure-stdlib os.scandir/lstat walk.
- It computes the apparent size as `du -sb` does: the root and every entry's st_size, each inode once, no symlink
  followed.
- An entry that **vanishes** mid-walk is skipped and counted. That means ENOENT at lstat, ENOENT or ENOTDIR at a
  subdirectory's scandir, or a directory gone mid-iteration.
- **Everything else raises:** EACCES, EIO, any error at the root, a missing or non-directory root, and running past
  the timeout. The watchdog still HALTs on these.
- The watchdog uses it with the same 4 s bound (`--du-timeout`) and records `disk_vanished`. `--du` is gone.
  `studytree.disk_bytes` uses it with DISK_TIMEOUT 40 s (None on any error).
- On the real job (62,655 entries, 33 GB) the walk took 0.24 s and matched `du -sb` apart from the root's own size.

**Other measurement paths, audited against the same "benign concurrent writer" class:**
- The process scans (watchdog `Tree.scan`/`pstat`/`penv`, `x4s4io.owned_pids`/`proc_stat`) skip vanished pids and
  zombies.
- The PSS readers (watchdog and `studytree.pss_bytes`) skip exits. A zombie's smaps_rollup raises ESRCH, which was
  checked on 05.
- MemAvailable, PSI and nvidia-smi have no concurrent-writer exposure.

**Tests (`test_hr1`):**
- parity with `du -sb` (a symlink and a hard link included);
- deterministic vanishing (4 kinds) through an injected scandir;
- every other error raises: 6 injected errors, a missing root, a file root, a real chmod-000 directory, timeout 0;
- 150 walks under 4 real label-like writers renaming and removing, with hundreds of vanished entries and no failure;
- `disk_bytes` is never None under the writers, and is None for an unreadable directory;
- statically, no du remains;
- the regression: the real watchdog over a 10k-entry job with 8 writers plus a churn of short-lived marked processes
  (exits and zombies) runs 6 s with no HALT.

The r9 and r10 watchdog cases now run on the real walk:
- disk over: `--max-disk 1`;
- disk-walk failure: a chmod-000 directory;
- timeout: `--du-timeout 0`;
- an overdue measurement: a slow fake nvidia-smi;
- the `du garbage` and `negative du` parse cases are replaced by the unreadable-directory case.

**Mutation check:** 11 mutants, each killed:
- a vanished entry raises;
- EACCES tolerated;
- EIO tolerated;
- root errors tolerated;
- ENOTDIR not tolerated;
- no timeout;
- hard links counted twice;
- symlinks followed;
- a mid-iteration vanish raises;
- disk_bytes returns 0 on error;
- the watchdog goes back to du, which also HALTs in the live test and so reproduces the incident.

## SA-5 (COORDINATOR 5483e9d6): `qualify4 parity --final` for P3

**The defect.** A failed P3 could never reach label.py's exact-receipt exception, for two reasons:
1. `check_parity` accepts a parity receipt only through a passed guard receipt (R7), but `qualify4 parity` exits 1
   whenever passed=false, so its guard failed.
2. The default mode calls `pause()`, creating STOP, and only then writes its receipt. The receipt therefore completed
   inside a STOP period, and rule H-1 excludes it.

The offline test missed both because its fixture blessed the failed receipt with a synthetic passed guard receipt.

**The change, in `qualify4.py` only:**
- `parity --final` is a single final check. It never calls `pause()`, and it refuses `--watch`.
- The step exits 0 iff `final_check_completed(receipt)`: the receipt is final, carries the per-arm reading, and has
  neither an error nor a halt. The C7b verdict stays in `passed`, and the receipt records `final_mode: true`.
- Without `--final`, behaviour is unchanged: the Q4 smoke check and live use still pause and exit 1.
- label.py is unchanged. The coordinator rejected the label-side alternative.

**Tests (`test_sa5`):** every check runs the REAL `guard.py` Runner over a child running the real `qualify4.main`,
with `io.JOB` set to the fixture job.
- A low side with `--final` passes the guard, writes passed=false, final and final_mode, and raises no STOP or
  PARITY-PAUSE.
- The default mode is unchanged: the guard fails, and PARITY-PAUSE and STOP appear.
- With `--final`, each of these exits 1: a non-final phase set, `--watch`, a check error, a halted final verdict.
- The exit rule is unit-tested on its own.
- **End to end:** real guard → `parity --final` → `label.make_plan`. The plan accepts the receipt only with an authentic
  exact-receipt exception; none, or a wrong SHA, is refused. A default-mode failed receipt stays refused even with an
  exception, which is the pre-SA-5 blocker.
- **Fixtures:** `parity_doc` never blesses a failed receipt; failed receipts now come only from the real guarded run.
  `bless`/`bless_into` refuse any JSON whose `passed` is not True, unless the call is an explicit negative
  (`allow_failed=True`). The only such call is the label-receipt mismatch negative, which must still be refused.
- **Mutation check:** 9 mutants, each killed:
  - final mode still pauses;
  - `--final` ignored;
  - exit by verdict;
  - exit always 0;
  - the rule ignores final;
  - the rule ignores the per-arm reading;
  - the rule ignores error;
  - the rule ignores halt;
  - `--watch` allowed.

## SA-4 (COORDINATOR 08723c23): the in-loop C7b watch is one-sided

`supervise.parity_watch` is the only code change. qualify4 and label.py `check_parity` are unchanged.
- **High side pauses.** If any evaluated arm has any metric (cutoff, student-default or overrun %) more than 2 pp
  above its X4S-3 reference (`pct[k] > x4s3_r3a[k] + 2.0`), the watch writes PARITY-PAUSE and STOP as before. The
  receipt also lists `high_side`.
- **Low side is recorded, not paused.** If the reading is out of band but nothing is above +2 pp, the watch appends
  the reading, without the game inventory but with its SHA, to `<job>/receipts/parity-lowside.jsonl` through the
  confined append. That file is disclosed in RESULTS.
- **Failures stop.** A monitor exception, or a low-side record that cannot be written, stops with
  `parity_monitor_failed`.
- **P3 stays the binding check.** It is unchanged, with the coordinator's low-side pre-ruling.
- **Tests (`test_sa4`, plus the R2-F8 fixture moved to the high side).** Each rule has one discriminating scenario:
  - low side only: no pause, and one record per watch;
  - high side;
  - the strict threshold: 77.4 pauses; 77.2 and 73.4 are in band;
  - a low cutoff with another metric above its reference but by less than 2 pp: recorded, not paused;
  - a low cutoff with high student-default (S-200) or high overrun (K4S-120): pauses;
  - an unevaluated arm, including `high_side()` on two arms;
  - a monitor exception;
  - a failed low-side record through a symlink, with the outside sentinel unchanged.
- **Mutation check.** 10 mutants, each killed:
  - direction flipped;
  - no +2 pp margin;
  - any → all;
  - cutoff only;
  - `evaluated` ignored;
  - low side pauses;
  - low side not recorded;
  - record failure ignored;
  - monitor exception ignored;
  - high side not paused.

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

`test_x4s4_offline.py` passes **128/128 under -O0, -O and -OO with umask 077 and 022** (exit 0 in all six).
Receipts (umask 077 runs):

| Mode | Receipt | SHA-256 |
|---|---|---|
| -O0 | [receipts/offline-tests-O0.jsonl](receipts/offline-tests-O0.jsonl) | `091ca62add843832d0c8492e2151605ac293a981907472f32b1a5c589ba927ec` |
| -O | [receipts/offline-tests-O1.jsonl](receipts/offline-tests-O1.jsonl) | `ab7033615f639c55389d5950fe27b54cd439fafbd32bf68482ec28aa005ec834` |
| -OO | [receipts/offline-tests-O2.jsonl](receipts/offline-tests-O2.jsonl) | `26cd76db667aa840f9bcb6b18db2c65ceddb9b41feb456cc8144ee2bac6a471a` |

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
