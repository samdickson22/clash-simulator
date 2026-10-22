# Offline FP64 target latency handoff

This change prepares a Mac measurement. It does not admit FP64, select a runtime,
change production loading, launch training, or qualify CPU latency without target
results. The parent owns staging, launch approval and measurement. No Mac, SSH,
network, GPU or MPS execution was performed for this handoff.

The branch starts at `1ebd0b0a3939761ae2d33eadeed27422eee042f8`.
The new package digest is
`6d8b3ca1d41089362f1a64760dc065912d416a27858c724133abb8625ff83291`.
It covers every Python file under `bot/pretrain_v1`, including the new runner,
qualification context and tests, plus the catalog. Stage that complete package
as physical files. `bench_contract.runtime_sha()` remains recorded separately.
The review verdict applies only to this offline benchmark handoff.

`bench_fp64 run` reuses the existing selected-benchmark lock with its no-follow,
nonblocking, regular-file checks. It refuses existing output directories,
including failed or incomplete attempts. It requires exact expected source,
checkpoint and canonical record-manifest SHA256 values. It verifies the complete
physical record set and bytes before each child and after each child. The shared
`bench_device.games` filter still counts increasing unique ticks per record file.
Changes to source, corpus or checkpoint invalidate the attempt.

Only an admitted, trained FP32 BC source with matching feature hash, full model
configuration, finite state and exact keys, shapes and dtypes can be converted.
The conversion occurs in memory before Session construction. Both its FP32 source
parameter identity and converted FP64 policy identity are recorded. Production
`policy.load` remains unchanged and refuses FP64 checkpoints. No production caller
passes the new `--offline-fp64` flag. Without the flag the existing benchmark path
and result fields remain unchanged.

The two children use CPU1 and CPU4, each with 200 warmup decisions and 20,000 timed
Session decisions. Timing includes Session.step, synchronization and accepted
plays fed back to History, as before. Math attention uses exactly the existing
qualification context: MHA fastpath, flash and memory-efficient attention disabled;
math enabled. Each child has a 1800-second alarm and 1830-second parent timeout.
Results must match the expected policy, dtype, scope, attention, source, runtime,
checkpoint, corpus, full cfg, feature hash, mode, thread count and decision count.
The parent also validates finite latency statistics and complete Canvasdoc CPU/RSS
accounting and recomputes the recorded budget verdict.

MPS receives `mps-unsupported.json`, bound to the same source package, source
checkpoint, record manifest and converted policy. Its status is `unsupported` and
`measured` is false. It contains no latency statistics or 20,000-poll claim. There
is no MPS probing, conversion attempt or FP32 fallback. The previous FP32 MPS
30 ms qualification failure is unchanged.

A completed attempt means the measurements are structurally valid, including a
valid latency failure. Read each CPU result's `latency_budget`: p95 must be at most
30 ms and p99 at most 50 ms, with complete telemetry. A passing timing receipt is
still only offline target evidence. Numerical qualification, complete real-record
coverage for the intended source/checkpoint, and separate runtime approval remain
required. It does not declare FP64 production qualified.

## Parent prelaunch requirements

Stage code, the selected BC checkpoint and actual replay records only under the
physical `Path.home().resolve()/clasher-pretrain-bench` directory. The runner
rejects a symlink root, symlink path components and traversal, including source
outside that directory. The output must be a fresh directory. Pin the checkpoint
SHA and canonical record-manifest SHA from the source evidence before staging;
do not derive expected pins from unverified target copies. The selected anchors
used for the earlier numerical experiments are evidence inputs, not a new model
or checkpoint selection.

The parent's prelaunch guard must find no existing benchmark job or waiter and
must verify the reviewed revision and source SHA before launching. Do not add a
standalone installer or remote orchestrator. Every SSH invocation must have an
explicit timeout. Keep all created files inside the benchmark directory. Do not
put the forbidden live replay script name in any command line. Do not use process
name killing, alter MuMu or adb ports 5037/5047/5051/5053/5061, or touch
ScreenCaptureKit or dispgrab. Leave re-drive emulators, UTM, the development server
and Canvasdoc alone.

The old 06:18 Canvasdoc idle observation is not current telemetry. Observe its
CPU and RSS during these runs. Preserve the existing `shared-load` classification
and `clean_result=false`; report `canvasdoc.idle_observed` separately. An active
Canvasdoc run remains shared load and must pass the same timing budget to count
as passing evidence. Never relabel a run as clean. Record the requested
`canvasdoc-idle` condition only when the parent currently observes idle activity.
The staged records still provide replay-realistic decision inputs.

## Commands for the parent after independent GO and launch approval

These commands are documentation only. `CODE_DIR`, `CHECKPOINT`, `CHECKPOINT_SHA256`,
`RECORDS`, `RECORDS_MANIFEST`, `RECORDS_SHA256` and `FRESH_OUTPUT` must be set by the
parent to staged paths and source-evidence pins for the intended checkpoint and
corpus. Use a separate fresh output for each checkpoint. The interpreter is an
existing compatible environment staged under the same benchmark root.

```bash
cd "$CODE_DIR"
PY="$HOME/clasher-pretrain-bench/venv/bin/python"
SOURCE_SHA256=6d8b3ca1d41089362f1a64760dc065912d416a27858c724133abb8625ff83291
"$PY" -B -m bot.pretrain_v1.bench_fp64 source-digest
"$PY" -B -m bot.pretrain_v1.bench_fp64 run \
  "$CHECKPOINT" "$FRESH_OUTPUT" "$RECORDS" \
  --records-manifest "$RECORDS_MANIFEST" \
  --source-sha256 "$SOURCE_SHA256" \
  --checkpoint-sha256 "$CHECKPOINT_SHA256" \
  --records-sha256 "$RECORDS_SHA256" \
  --load-condition shared-load
```

The source-digest print is a cross-check against the fixed reviewed value above.
The runner enforces the fixed value passed to `run`; it never substitutes its own
observed digest for an expected one.

## Local verification

Linux execution used nice >= 10, MemAvailable >= 29 GiB, load1 <= 90, hidden CUDA
devices and one thread per math library. The tests use the existing local Python
and pytest dependency directories. No installation or remote staging is needed.

```bash
nice -n 10 env CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  PYTHONPATH="/mpac/sdicks02/tmp/fp64-harness-test-deps:$PWD/src:$PWD" \
  /mpac/sdicks02/repos/clasher-pv1-rl-env271-20261022/bin/python -B -c \
  "from bot.pretrain_v1.checks.qualify_fp64 import guard; guard(); import pytest; raise SystemExit(pytest.main(['bot/pretrain_v1/tests/test_bench_fp64.py','bot/pretrain_v1/tests/test_policy_device.py','bot/pretrain_v1/tests/test_bench_load.py','-q']))"
```

Result: 46 passed, 1 skipped. The skipped legacy device test requires actual MPS.
New tests exercise the retained real 19-record fixture with the trained S100 BC
anchor converted to FP64, complete model configuration, FP32 source immutability,
production FP64 rejection, required flags and expected policy SHA, source/corpus
freshness, exact manifest and unique tick filtering, physical paths and root
symlinks, a fresh import through a symlinked source directory, individual module
file aliases, lock symlinks/FIFOs/contention, CPU1/CPU4 mocked children, unsupported
MPS receipts, timeout and corrupt child refusal, incomplete-attempt reuse refusal,
and current active/idle Canvasdoc CPU/RSS reporting. A default FP32 regression
compares actual Session decisions and byte-exact benchmark JSON against the exact
base with a deterministic clock. This is fixture verification, not Mac latency
evidence.


## Parent operational state

The parent landed the reviewed helpers and launched the exact immutable reviewed
package at 11:36:39Z on 2026-10-22. Mac owner PID 9723, nice 10, sequential v3
S100/M CPU1/CPU4 measurements. State and receipts are under
`~/clasher-pretrain-bench/offline-fp64-48795b3c7/`.
Prelaunch Canvasdoc was idle, but S100 CPU1 observed active Canvasdoc and is
reported as shared load. Its 20,000 decisions pass p95 18.207 ms, p99 27.593 ms.
Other measurements remain pending. No production precision adoption occurred.


The run completed at 11:49:48Z. Owner 9723 exited. Both S100 CPU settings pass;
both M settings miss the budget under observed shared load. All four phases
observed active Canvasdoc. See [FP64-TARGET-BENCH-READOUT.md](FP64-TARGET-BENCH-READOUT.md)
for results, telemetry and the pending idle rerun.
