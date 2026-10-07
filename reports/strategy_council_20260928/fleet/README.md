# Clasher fleet

Current result: **hub rollout blocked by a native chain-targeting regression also reproduced on Mac build 42**. All four Python identity modes pass. No peer replication has run. See `PARITY-LINUX.md` before launching anything.

Clasher uses **127x01, 02, 03, 04, 07, 08**. Hub: **127x02**. 127x05 is Sam's shared T3 Code command center: do not copy the repo/venv or run builds, tests, identity checks or heavy jobs there. This task only checked its connectivity and console users before that reservation; it copied no repo or venv there. Do not use 127x06 or the roader hosts 127x09–18. Check `who` before launching work and leave headroom for console users. Host 03 has no working GPU. This bring-up validates CPU simulation; it does not qualify GPU training.

## Layout

Every node uses the same absolute paths so copied venvs and toolchain links work:

- `/mpac/sdicks02/env.sh`: Cargo, Rustup, uv, Python and cache locations.
- `/mpac/sdicks02/tools/`: copied hub toolchains, including Rust 1.97.1 and Python 3.12.13.
- `/mpac/sdicks02/repos/clasher/`: repo, `.venv`, and Linux `engine-rs/clasher_core.abi3.so`.
- `/mpac/sdicks02/repos/clasher-local-data/`: `clasher-engine-speed` and only `decoded-logic-1e505767` from the native-reference cache.
- `/mpac/sdicks02/jobs/clasher/`: logs, PID/lock/exit files and replay receipts.
- `/mpac/sdicks02/tmp/`: job scratch.

The NFS home contains only two small compatibility symlinks for historical `Path.home()` fixture lookups. They point to the same `/mpac` local-data paths on each node. Existing mode-000 cache placeholders were preserved with `.pre-fleet-20261007` suffixes. Do not redirect caches or large output into NFS home. Do not touch Tailscale, its scripts, crontab or other users' files.

## Launch, inspect, stop, resume

From the Mac, use the existing SSH aliases. Long jobs must go through the helper; it uses `nohup setsid nice -n 10`, a per-label `flock`, disk logs and an atomic exit receipt. It sets one-thread BLAS/OpenMP limits, local scratch, `CLASHER_ROOT` and the native/Python import paths.

```sh
ssh 127x02 'who; bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/fleet/fleet_run.sh my-unique-label .venv/bin/python -B path/to/job.py'
ssh 127x02 'tail -40 /mpac/sdicks02/jobs/clasher/my-unique-label.log; cat /mpac/sdicks02/jobs/clasher/my-unique-label.exit'
ssh 127x02 'pid=$(cat /mpac/sdicks02/jobs/clasher/my-unique-label.pid); ps -o pid,ppid,pgid,ni,etime,args -p "$pid"'
```

A missing exit receipt means unfinished or interrupted, not success. Inspect the log and process ancestry. A nonzero exit remains a failure. To stop an owned job, confirm its command and process group using `ps`, then run `kill -TERM -- -<verified-PGID>`. Never use broad `pkill` patterns. Preserve its log and exit receipt. Start a corrected attempt with a fresh label. If a job was interrupted without an exit receipt, rerunning its original command and label reuses its lock and appends logs. Successful completed labels are skipped; failed completed labels retain their exit code. The underlying workload must support receipt-level resume; arbitrary commands are not automatically checkpointed.

## Build and gates

Run from the repo on the hub after `source /mpac/sdicks02/env.sh`. `bootstrap.sh` uses `uv sync --frozen --python 3.12.13` and the existing `engine-rs/build.sh`. Set `PYO3_PYTHON=$PWD/.venv/bin/python` for `cargo test`; otherwise Ubuntu's Python 3.8 is selected and fails the `abi3-py312` minimum. A `.pth` in the venv makes the built extension importable without an extra install. Cargo currently discovers zero Rust tests; the Python differential suites are the meaningful engine tests.

Data-dependent gates require `jobs/clasher/transfer-ready.json`, written only after the coordinator's existing transfer finishes and source/baseline verification passes. `verify_inputs.py` compares 1,150 Mac file hashes and 179 historical Stage 6 certificate receipt hashes. `source-mac.json` preserves the expected hashes. During transfer, a separate Mac worker began the Fisherman planner fix. This run keeps the earlier 1,150-file snapshot from `/mpac/sdicks02/snapshots/clasher-fleet-20261007`; after the final sweep, those pinned files are restored on the hub. Later Mac changes are not covered. It also checks 34 replay inputs and the expected Linux extension hash. It does not reseal historical certificates for a different binary.

```sh
fleet=reports/strategy_council_20260928/fleet
bash "$fleet/fleet_run.sh" bootstrap-20261007-r3 bash "$fleet/bootstrap.sh"
bash "$fleet/fleet_run.sh" gate-sequence-linux-20261007 bash "$fleet/gate_sequence.sh"
bash "$fleet/fleet_run.sh" recorded-linux-20261007 bash "$fleet/recorded.sh"
bash "$fleet/fleet_run.sh" stage6-linux-20261007 bash "$fleet/regressions.sh" stage6
```

`identity.sh` invokes the unchanged Mac authority's commands with the same baselines. Timing is supplied by the outer helper's GNU `/usr/bin/time -v`; the Mac `/usr/bin/time -l` script is untouched. P16, C56 and random run in one sequence with Stage 2/4/5 tests and the 24-case speed differential. The cumulative Stage 6 suite runs in a separate process. Recorded replay uses four independent workers, each calling the same `oq_lib.play_game` and comparing the exact original row. Each actual replay gets its own receipt and CPU/wall times. After all eight pass, the original `broad_identity.py recorded check` validates the merged receipt against the admitted baseline. There are no synthetic or unexecuted rows.

`regressions.sh` contains the exact fast pytest selection and full Stage 2, Stage 4, Stage 5/5b and cumulative Stage 6 unittest lists. These are fresh Linux tests. Historical Mac certificates and final S122 admission remain separate.

Several saved-root tests predate cleanup commit `2def50e8d60acb574b571d47da4f42cfd7ce0d41` and initially stop at source-hash assertions. `reference-cleanup.json` records the exact old/new pairs for 23 files; `evidence/reference-cleanup-proof.json` binds each pair to the commit and its parent. `audited_suite.py` changes only the expected hash expression in memory and keeps all fixture and simulation comparisons intact. Stage 4 uses it directly. `resolve_stage6.py` waits for the original 60-test run, refuses any failure except an audited pre-replay hash mismatch, and reruns only those failed methods. Its combined receipt accounts for all 60 unique methods; it preserves the original failed run.

```sh
bash "$fleet/fleet_run.sh" stage6-resolved-linux-20261007-r2 env PYTHONPATH=engine-rs:src:reports/strategy_council_20260928/engine-speed/stage6 .venv/bin/python -B "$fleet/resolve_stage6.py"
```

The current gate fails, so do not launch replication. After the native regression is fixed and every hub gate passes on fresh pinned receipts, `fanout.sh` starts one detached copy task per target from 127x02 over campus LAN. The hub has a 1 Gbit/s link; level-1 compression reduces transfer volume. It copies tools, the repo including `.venv` and Linux extension, and local-data, preserving existing target files. It excludes build targets, bytecode and APK archives, then launches P16 smoke checks on all five peers. It never uses the roader hosts.

```sh
bash "$fleet/fleet_run.sh" fanout-20261007 bash "$fleet/fanout.sh"
```

See `PARITY-LINUX.md` for actual results and limitations. No script here resumes training, extraction, sealed evaluations or the unfinished Stage 6 planner gate.
