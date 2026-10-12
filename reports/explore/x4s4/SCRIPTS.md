# X4S-4 scripts, r5 for Sol re-review (exploration, NEVER ADOPTABLE)

The design is frozen at PLAN r3 87809ae0. The history of the script set:

| Round | Script set | Sol verdict |
|---|---|---|
| r1 | 13fb31d0 | REQUEST_CHANGES (18 findings) |
| r2 | f15691b5 | REQUEST_CHANGES (R2-F1–F10) |
| r3 | 8c443f23 | REQUEST_CHANGES (R3-F1–F8) |
| r4 | 15048bd4 | REQUEST_CHANGES (2a933467: R4-F1–F6). Sol verified 92/92, the unchanged evaluation runner and hooks, the 29-file seed inventory, and that no group signals remain. |
| r5 | this commit | — |

r5 fixes R4-F1 to R4-F6, with Sol's cases as named negative tests. It also makes the fixtures Sol called partial complete:
- phase documents now carry schedule, launch and exit evidence;
- the holdout fixture now has a full receipt/gate pair.

Nothing has been run on any host. Everything below was done offline on 127x05, using synthetic fixtures and disposable git repositories under /dev/shm.

## Index

| File | r5 | SHA-256 |
|---|---|---|
| `x4s4io.py` | unchanged | `2e8e626831a1807cac99534e3d71c134fa9345ef214bfb312f44752172e9ec56` |
| `studytree.py` | changed (R4-F1) | `4caf72d49f7604bff4830c64703760e662e98cec76c8bdf98a33bd0a18e515e8` |
| `driver.py` | changed (R4-F2, R4-F3) | `c47c3389dc4358ed7bedae6df0b1bfff2d8114670981dd729267c3d42d00c473` |
| `supervise.py` | changed (R4-F2) | `5645c6fa8eb967c76ee97e1c1459acbade99210ab3179731a79736d0b75ccf40` |
| `label.py` | changed (R4-F5) | `a4b6794e8ee77c876d527c73fb3743f6fdc4cd0002ce2b50ae0db21a4f111844` |
| `qualify4.py` | changed (R4-F5) | `73925fb0327ef36553c7290560438142c590c326a318e3dcec24e042bc899bb1` |
| `write_report.py` | changed (R4-F4, R4-F6) | `1e634d034e55f24ac442b2288f0212b71d0bfed6f47ff43b749ecdb991d4e96e` |
| `test_x4s4_offline.py` | changed | `2120fcf0410fcd4a564ece9795cde2cb14e7a1383cd4e43c11f78f3fa4582a46` |
| `collect_w.py` | unchanged | `68c187e0f2dabd3cf708083522e618c0b264b499d9efc560a950d415d2711a3a` |
| `verify_onpolicy.py` | unchanged | `b85837d704aa7b1f1cf4a18a47099efce1b8108def97b59af1efb527a0152040` |
| `diagnose.py` | unchanged | `aef97380a6de1885938b929240536a6cf8c2e75ec9e1bc0bd7c54db0e18c8a17` |
| `reduce.py` | unchanged | `bb6fc580d3d3e84457edd67b45ff799ab5c1fab2393d2b74b89e0108267201bf` |
| `audit_seeds.py` | unchanged | `1e1ac591afc936359f29b7b2d25ddd83ff24709a7558492c0d45655a35e3d76c` |
| `run_fit.sh` | unchanged | `867dc31b87cd7ce20771a2fdd31a67d30b38d283f080265e9e6f5aa13c298b9c` |
| `seed-sources.json` | unchanged (v2, 29 sealed declarations) | `bf57cda0b925cc99de6765a3fcf88053a89ef228d7e24fc1fcb36b5ca0bec002` |
| `run_collect.py` | unchanged | `f945ac6c266267d52689df9cd0b3a658705740a513b86866e16d3786dc64780b` |
| `collect.py` | unchanged | `ce29b1311cc0489a32f09885fd8f44c5df40ed9d9d7292597b4567c9fa006494` |
| `contention.py` | unchanged | `0139abc5590fdb1bd5698bde97b9d63362ebc929c2eb85b14f27cb5d0ae53be3` |
| `plan.json`, `plan-collect.json`, `plan-qual-capture.json`, `idx-*.json` | unchanged | `13840cc6…`, `57f6a142…`, `45052215…`, `4587c7ed…` |

Every owned Python file compiles under `/usr/bin/python3` 3.8.10 and under 3.12. `bash -n run_fit.sh` passes. The evaluation runner and the reused files are byte-identical.

## Sol r4 findings → fixes → named negatives

**R4-F1: gate ↔ verifier-receipt binding.** `studytree.authenticate_gate` now requires the pinned verifier receipt to have the complete successful shape: passed, sealed, mode, the shared fields and the mode's identity fields. The receipt must also equal the gate on every shared field:
- the exact batch list (name, manifest SHA, rows, roots, games);
- rows, roots, rows per arm, single-candidate share and source-list SHA;
- the input identities: label plan, label receipts and parity for O/holdout; selection, O gate, acceptance and receipts for O_W.

The batch inventory and complete seal re-verification follow. This applies to every consumer (fit admission, diagnostic holdout, report) and every mode.

Negatives, with "Sol R4-F1" first, using the genuine verifier output from `verify O`:
- a training corpus (C+0) with the gate re-pinned beside its unchanged authentic receipt is refused;
- gate rows, source list or plan identity that differ from the receipt are refused;
- an incomplete receipt body (passed/mode only) and an unsealed receipt are refused.

**R4-F2: STOP and deadline before every spawn; calibration.**
- `prepare_students` returns immediately on STOP or after the hard stop.
- `run_calibration` makes the unchanged calibrator monitored, exclusive GPU work. It is admitted under the DISPATCH flock shared with diagnose.py, only with no STOP, the deadline unmet, no unresolved anomaly, no live fit or reporting phase, and admissible resources. The parent polls `calibration_breach` (STOP, deadline, memory, GPU, PSS, study caps) and stops its verified PIDs on a breach. A nonzero exit or a result returned after the deadline is rejected, and the file is renamed `.rejected`.
- `supervise.admit_phase` refuses a STOP link and an expired deadline (`--stop-at` or HARD-STOP-UTC.txt) before `io.spawn`.

Negatives (Sol's two boundaries):
- STOP and past-deadline calibration are not admitted and `prepare_students` launches nothing;
- an in-flight calibration is stopped by PID with an anomaly;
- a late success is rejected, while a clean one is accepted;
- the supervisor refuses STOP, a past `--stop-at` or a past HARD-STOP before spawn (also checked statically: admission precedes `io.spawn`).

**R4-F3: stopped-fit reconciliation.** `fit_state` reconciles a stopped (partial) completion exactly like a final one. It needs segment `returned` plus a known zero exit of this launch, or the exact-attempt ACK resolution if the status is unknown. The frozen trainer satisfies this on the driver's SIGTERM: it writes `stopped=true`, returns and exits 0. Otherwise the state is `failed`, which raises a blocking `fit-<id>-exit` anomaly and is never resumed.

Negatives:
- Sol's case (stopped, segment failed, exit 17) is `failed` with an anomaly and no launch;
- an unknown exit blocks;
- the clean authorized-stop control resumes.

**R4-F4: model identity coverage.** The reduced student list must have no duplicates, contain the four primary students and only declared students. `identities.students` must cover exactly that list, and each identity must equal the staged student (plan for R3a, READY for the rest). The diagnostic's `student_checkpoints` must cover exactly the five students with staged checkpoints and thresholds.

Negatives:
- Sol's `identities.students = {}` case;
- each single student omitted, including R5W;
- a duplicate student;
- a diagnostic missing R5W;
- the earlier WRONG-checkpoint and fake-identity cases.

**R4-F5: validated phase execution evidence.** `qualify4.phase_evidence(phases, bank)` requires:
- schedule.json and launch.json present;
- the bank's range with seeds of the form base+index;
- one arm inside its bank-C allocation for collection;
- schedule config equal to launch config, and one config across phases;
- every block proof a scheduled index;
- an exit classified as `clean` (reason None, rc 0) or `interrupted` (a declared guard stop, including `parity_pause`), with no live group members.

Anything else refuses, for example rc 17 with no reason. The receipt pins this record (file SHAs, status, config, arms, scheduled/proved counts), and label admission plus later consumers re-derive it.

Negatives:
- Sol's returncode-17 exits;
- Sol's missing schedule/launch;
- a schedule/launch config mismatch, phases on two configs, and a live group at exit;
- the allowed `memory_guard` interruption passes as `interrupted`;
- the r4 stale/deleted/changed-exit probes still refuse.

**R4-F6: renderer freeze order and strength.** `write_report` now requires `--contention-sha` and `--freeze-commit`. It runs the reducer's full `reduce.verify_freeze` (readonly single-link receipt, SHA, verified commit walk on origin/main, schema, phase set, the full census/launch/exit/SETTLED/block/game SHA, size and st_mtime_ns inventory, retired.json) **before opening results.json**, then binds results to that receipt and commit.

Negatives:
- Sol's read-spy: a missing receipt is refused and `results.json` is never opened;
- Sol's post-reduction census change is refused;
- a wrong declared SHA and an off-main commit are refused.

## Offline test results (127x05, /dev/shm, nice 19, cores 0–3, no host contact)

`test_x4s4_offline.py` passes **96/96 under -O0, -O and -OO with umask 077 and 022** (exit 0 in all six). Receipts (umask 077 runs):

| Mode | Receipt | SHA-256 |
|---|---|---|
| -O0 | [receipts/offline-tests-O0.jsonl](receipts/offline-tests-O0.jsonl) | `c5f32a40f31ab082a329c989470fa335c72620ca70f0784467618e7a40e593c7` |
| -O | [receipts/offline-tests-O1.jsonl](receipts/offline-tests-O1.jsonl) | `e97e997494b28917c0c430f821b9eb2906da18de66fc02f90c4adfc0d0b7119a` |
| -OO | [receipts/offline-tests-O2.jsonl](receipts/offline-tests-O2.jsonl) | `c578bc4b56c6189b4f3d64943df68f7b1307a921383441787e04fe3d3c0a6b8b` |

**Not covered offline** (qualification §6 on 01, after a GO):
- the native §6 checks;
- the real v2 seed audit with range/count completeness;
- the live STOP test;
- the staged RUNTIME-INVENTORY: x4s4/supervise.py, x4s4io.py, studytree.py, qualify4.py, x4s3/run.py, runtime.sh, fit/run_fit.sh, fit/loader6.json, inputs/assets.npz.
