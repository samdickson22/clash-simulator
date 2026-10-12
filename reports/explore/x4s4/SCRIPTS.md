# X4S-4 scripts, r4 for Sol re-review (exploration, NEVER ADOPTABLE)

The design is frozen at PLAN r3 87809ae0. The history of the script set:

| Round | Script set | Sol verdict |
|---|---|---|
| r1 | 13fb31d0 | REQUEST_CHANGES (18 findings) |
| r2 | f15691b5 | REQUEST_CHANGES (R2-F1–F10) |
| r3 | 8c443f23 | REQUEST_CHANGES (e839e1dc, R3-F1–F8), with several groups APPROVE_WITH_CONDITIONS |
| r4 | this commit | — |

r4 fixes R3-F1 to R3-F8 and adds a negative test for each of Sol's 15 r3 edge probes. Nothing has been run on any host. Everything below was done offline on 127x05, using synthetic fixtures and disposable git repositories under /dev/shm.

## Index

| File | Status in r4 | SHA-256 |
|---|---|---|
| `x4s4io.py` | changed (R3-F7, R3-F8) | `2e8e626831a1807cac99534e3d71c134fa9345ef214bfb312f44752172e9ec56` |
| `studytree.py` | changed (`dispatch_ok`, `authenticate_gate`) | `7ebb6e4e0c1c516c69689febc52dd5b631c28a21c5b09026697c066a6fab524c` |
| `run_collect.py` | unchanged | `f945ac6c266267d52689df9cd0b3a658705740a513b86866e16d3786dc64780b` |
| `collect.py` | unchanged | `ce29b1311cc0489a32f09885fd8f44c5df40ed9d9d7292597b4567c9fa006494` |
| `label.py` | changed | `ecd88cc00143be41ebc7b3c4c1d1bf103767f45acb27278617dd389a3fb3c57e` |
| `collect_w.py` | changed | `68c187e0f2dabd3cf708083522e618c0b264b499d9efc560a950d415d2711a3a` |
| `verify_onpolicy.py` | changed | `b85837d704aa7b1f1cf4a18a47099efce1b8108def97b59af1efb527a0152040` |
| `diagnose.py` | changed | `aef97380a6de1885938b929240536a6cf8c2e75ec9e1bc0bd7c54db0e18c8a17` |
| `contention.py` | unchanged | `0139abc5590fdb1bd5698bde97b9d63362ebc929c2eb85b14f27cb5d0ae53be3` |
| `qualify4.py` | changed | `da45ee8c92e10c8cb9d13a7d1d42ae5be86d20841553ff1b0de24b62aff0382a` |
| `supervise.py` | changed | `fc7c4c50e52833e747067b042b59f52494f90e695c3ae8e847448a8599a1e5df` |
| `run_fit.sh` | changed | `867dc31b87cd7ce20771a2fdd31a67d30b38d283f080265e9e6f5aa13c298b9c` |
| `driver.py` | changed | `1f09b6d5136a879c98d48000cb371cb3dca1f8e1defd70a5a560a476d0dfdd47` |
| `reduce.py` | changed (identities) | `bb6fc580d3d3e84457edd67b45ff799ab5c1fab2393d2b74b89e0108267201bf` |
| `write_report.py` | changed | `17bb025cbee72ec57fd3489f8b59c714eef1dd2c98358226e9d43d48b48eb95e` |
| `audit_seeds.py` | changed (rule v2) | `1e1ac591afc936359f29b7b2d25ddd83ff24709a7558492c0d45655a35e3d76c` |
| `seed-sources.json` | regenerated (v2) | `bf57cda0b925cc99de6765a3fcf88053a89ef228d7e24fc1fcb36b5ca0bec002` |
| `plan.json`, `plan-collect.json`, `plan-qual-capture.json` | unchanged | `13840cc6…`, `57f6a142…`, `45052215…` |
| `idx-qual.json`, `idx-smoke.json` | unchanged | `4587c7ed…` |
| `test_x4s4_offline.py` | changed | `774a2f9f654b4de7569c5fcb7c05cfeb13faeb13a54b58a3d1af67aa33178cf9` |

Every owned Python file compiles under `/usr/bin/python3` 3.8.10 and under 3.12. `bash -n run_fit.sh` passes. The evaluation runner and the reused files remain byte-identical.

**Wording correction (Sol R3-F1).** x4s4io routes every read, write, subprocess and signal of the X4S-4-owned Python. The unchanged shell and frozen consumers do not use it: `run_fit.sh`, the frozen `fit_runtime.py` and trainer, the frozen loader, `calibrate.py`, the inherited runner, and the emitter. For them, r4 instead validates their write destinations and authenticates their inputs immediately before launch, as described under R3-F1. They are not described as routed through the module.

## Sol r3 findings → fixes → fixtures

Every probe in Sol's r3 edge record (15 entries) has a named fixture.

| # | Fix | Fixtures |
|---|---|---|
| R3-F1 | **Fit write contract.** `prepare_fit_dirs` runs before every fit launch, fresh or resumed. It creates the directories and validates the complete existing trees the frozen writers open or append, `fits/<id>` and `cache/fit`: no symlink, hard link or special file anywhere. It pins `run_fit.sh` and `loader6.json` against RUNTIME-INVENTORY, checks the resume checkpoint is single-link, and re-authenticates the data gate (`studytree.authenticate_gate`). It passes the authenticated batch names to `run_fit.sh`, which no longer reads JSON or creates directories and refuses a TMPDIR the driver did not prepare. The gate SHA is recorded in the launch receipt. | **Sol's probe:** a symlinked `fits/R5/runtime.json` (the frozen writer's target) is refused before launch, and the sentinel is unchanged. Also refused: a hard-linked `train.jsonl`, a link inside `cache/fit`, an unpinned loader amendment and an unauthenticated gate. The batch-argument launch is tested. The shell refuses no or bad batches, a missing gate and a symlinked TMPDIR. |
| R3-F2 | **Live and stop paths.**<br>(1) Each acceptance game runs in an owned worker under a polling parent. A breach (STOP, including a dangling link; hard stop; memory; PSS; tree; disk) stops the worker's verified PIDs. A game completing after the hard stop is rejected, and passing also requires the deadline unmet at the end.<br>(2) The live fit guard enforces the study process and disk caps, and its memory, GPU and PSS checks continue through teardown. Only the wall and loss rules are skipped there.<br>(3) Label dispatch and acceptance dispatch wait while `studytree.dispatch_ok` fails (MemAvailable below 24 GiB, or PSI unreadable or above 10). This only delays; high PSI never becomes a kill threshold.<br>(4) `supervise.admit_phase` applies memory/PSI and the reserved process/disk caps immediately before `io.spawn`, including for direct collection and qualification launches. | **Sol's probes:** acceptance passing past the deadline is now false, with a `past_hard_stop` row. An in-flight STOP during acceptance makes the parent kill the worker by PID within seconds; this runs in an isolated session. A live fit at 71 processes is stopped. Teardown with MemAvailable 0 is stopped. High-PSI label dispatch submits nothing, while the monitor keeps running. The low-memory / high-PSI supervisor launch is refused before spawn (also checked statically: admission precedes `io.spawn`). |
| R3-F3 | `studytree.authenticate_gate` checks, before any frozen loader opens a corpus:<br>• the gate's mode;<br>• the verifier receipt SHA pinned in the gate, and that the receipt passed in the same mode;<br>• the exact batch inventory;<br>• every batch's complete seal re-verification against the gate's manifest pin.<br>The diagnostic holdout uses it, and so do fit admission and report authentication. The trainer-qualification consumer requires a packed batch under `<job>/qual`, its seal re-verified, and assets matching the inventory. | **Sol's probe:** a fully sealed training corpus (seed C+0) swapped into the holdout path is refused. An extra batch and an edited verifier receipt are refused. The authentic gate passes. |
| R3-F4 | `reduce.py` writes `identities` into the results: plan path and SHA, C5 receipt SHA and freeze commit, retired SHA, each reduced student's checkpoint and threshold, and the gate SHAs. `write_report.authenticate` reconciles all of them with the current evidence:<br>• the C5 receipt bytes are committed at the named commit (verified git walk) on origin/main;<br>• retired.json and the plan are unchanged;<br>• the gates match and are re-authenticated against their corpora;<br>• the staged students match;<br>• the diagnostic's holdout gate equals the authenticated gate, its heldout64 SHA is the fixed pin, and its checkpoints and thresholds equal the reduced students'. | **Sol's probes:** the report refuses fake C5 strings (`not-a-sha`/`not-a-commit`) and a diagnostic with `WRONG` checkpoints. It also refuses results reduced under other gates or checkpoints, results without identities, a diagnostic with another held-out64 or holdout, and an off-main C5 commit. The valid chain is accepted. |
| R3-F5 | Parity receipts pin each phase's `schedule.json`, `launch.json` and `supervisor-exit.json` SHAs (`evidence`) and the bank. Label admission accepts only bank C, re-derives the evidence and refuses missing or changed final evidence. The plan records the receipt path and phases, and `label run` and O/holdout verification re-run the full parity admission (`recheck_parity`). `qualify4 parity --bank smoke` runs PLAN §6.2 parity on the smoke bank. | **Sol's probe:** deleting both phases' supervisor-exit after a passing receipt is now refused. Changed exit evidence and a smoke-bank receipt are refused for labeling. **Sol's probe:** valid smoke-bank games pass with `--bank smoke` and are refused as bank C. |
| R3-F6 | Attempt anomalies (`exit-*`, `fit-*-exit`) clear only through the attempt-bound ACK. Every other anomaly clears only through `ACK-<key>.json = {anomaly_sha256: SHA-256 of the exact ANOMALY file, disposition: continue, owner}`. That ACK is consumed, and the anomaly and ACK are archived in `RESOLVED-<key>-<t>.json`. Anything else keeps blocking. | **Sol's probe:** a malformed `ACK-driver-exception.json` blocks and is not consumed. A dangling-link ACK, a stale-SHA ACK, and a generic ACK on an attempt anomaly also block. A valid ACK is consumed and archived. |
| R3-F7 | `open_append` classifies the leaf with `fstatat` before any open, and refuses a non-regular, linked or hard-linked leaf. It opens with `O_NONBLOCK|O_NOCTTY|O_NOFOLLOW` (creation `O_EXCL`), re-checks the inode after open, then clears `O_NONBLOCK`. `loads_strict` refuses numbers that decode to non-finite floats (`1e999`). Projections refuse duplicates of dropped keys. | **Sol's probe:** append to a FIFO with no reader is refused under a 5 s alarm. Exponent overflow (positive and negative) and a projected duplicate are refused. |
| R3-F8 | `run_checked` no longer calls `killpg`. On timeout, overflow or lingering pipes it enumerates the helper session's verified `(pgid, starttime)` members and kills each PID. No group signal remains in any owned file. | **Sol's probe:** a timed-out helper and its background grandchild are both gone (unique-marker match, with a live-helper positive control). Static check: no `killpg`. |

**Seed inventory (Sol decision 5).** Rule v2 excludes the six review/response/check/conformance support documents from the sealed-declaration list, as Sol asked. It is regenerated at the same pinned commit 7f82af0d: 7,705 sources, source-list SHA 844ab589…, **29 sealed declarations** (3 seed audits and 26 PREREG/draft/freeze/amendment files). Omissions now include `sealed` 2,687, `outcome_path` 812 and `alias_of_excluded` 55. Sol's approved rules for decisions 1–4 are unchanged.

## Offline test results (127x05, /dev/shm, nice 19, cores 0–3, no host contact)

`test_x4s4_offline.py` passes **92/92 under -O0, -O and -OO with umask 077 and 022** (exit 0 in all six). Receipts (umask 077 runs):

| Mode | Receipt | SHA-256 |
|---|---|---|
| -O0 | [receipts/offline-tests-O0.jsonl](receipts/offline-tests-O0.jsonl) | `0beca248188689c5493f87c27929c50144881ca50fe2011c0a6d7b2c34b2e8c2` |
| -O | [receipts/offline-tests-O1.jsonl](receipts/offline-tests-O1.jsonl) | `b9da73d8ea2701174c140598f734551260fb266a071f652b0388573746412217` |
| -OO | [receipts/offline-tests-O2.jsonl](receipts/offline-tests-O2.jsonl) | `3127453b4f418252de8aa3fcef055532067e0ea9bdfffc49b56575f2ff206c89` |

**Not covered offline** (qualification §6 on 01, after a GO):
- real W scoring and the 125 native references;
- command hashes and C8/root round trips;
- the emitter acceptance replay;
- RootTeacherStore compatibility;
- the GPU diagnostic;
- the real seed audit (`seed-sources.json` v2) with completeness evidence;
- the live STOP test;
- the staged RUNTIME-INVENTORY: x4s4/supervise.py, x4s4io.py, studytree.py, qualify4.py, x4s3/run.py, runtime.sh, fit/run_fit.sh, fit/loader6.json, inputs/assets.npz.
