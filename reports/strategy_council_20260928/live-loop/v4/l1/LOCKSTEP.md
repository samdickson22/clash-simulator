# Lockstep experiment, 2026-10-09

**Keep the current formal run on the owner's admitted exact path. This candidate
is not admitted; 100 full-replay frames/s/GPU has not been demonstrated.** No
production/quarantine outputs, frozen sources or owner receipts were changed.
No heldout payloads or03 were accessed. All changes are new files; no commits.

`lockstep_replay_v4.py` advances a shard of matches together. Each match retains
nine independent trackers, source histories and event fusions, plus its own
causal feature ring. Numpy broadcasts association costs across lanes but retains
CPython `math.hypot`, separate Hungarian solves, detection order, high/low passes
and float32 birth-addition order. Encoder lookahead never advances causal state.
Records use the original JSON bytes; writes are buffered with fresh measured
completion journals. The default128MiB output cap protects the isolated experiment
directory; a full capture requires the owner's storage allocation.

The fallback preserves batch-one encoder/prefix/tail shapes. It reuses a pure
tail result only within the same match when the input birth maps are byte-identical,
then keeps each branch's tracker/fusion state separate. GPU `graph` mode submits
all active matches' prefix/unique-tail calls through one CUDA graph replay.
Graph recapture when birth-equivalence patterns change can erase that benefit.
**CUDA graph equality and its throughput remain unqualified.** Singleton encoder
construction now exactly follows `PixelPerception`; that fix was made after the
failed GPU probe and has CPU evidence only.

## Evidence

Receipts are in `receipts/lockstep-20261009/`.

- CPU08 real validation prefixes: epochs1/3/20, eight matches,16 frames/match,
  nine branches;384 frames and3,456 decoder records plus non-clock payloads.
  Byte comparisons and per-stream hashes match the original shared runtime.
  Full16-token windows are exercised. This is **prefix evidence**, not three
  complete epochs/matches or the three full reference cells.
- Nine CPU tests cover full-runtime isolation, dense tracker ties/gaps/HP,
  repeated fractional births and suppression, exact decoder extraction,
  batch-one tail reuse, FIFO/hash accounting and verifier rejection guards.
- GPU01 e3 layer probe: encoder, prefix and tail batching at2/4/8 all changed
  bits. Fixed cuBLAS workspace and deterministic algorithms did not repair this;
  deterministic shape-one encoder/prefix also changed bits against the baseline.
  The largest observed exact whole-layer tensor batch is **one**.
- That probe's original8-match x4-frame replay matched the completed e3 quarantine
  prefix exactly (completion SHA `a4d885946c72557f47a0cd2fa790c82ee9100ce6804abf15cc1186020e5f0787`).
  The first graph fallback failed record/payload equality. Its unequal, incomplete
  prefix rates were23.86/33.48/38.81/42.15fps at shards1/2/4/8 respectively;
  cache reads and disk serialization were excluded. These are not usable speedups.
- Required GPU shard8/16/32/64 results:8 has only the failed42.15fps prefix above;
  16/32/64 are **not measured**. No full-replay GPU rate is qualified. Concurrent
  GPU snapshots were2/13/1/25%; these include T11 and are not isolated utilization.
- T11's five-minute baseline was7,645.42rows/s; the25.20s GPU experiment interval
  was3,900.78rows/s (51.02% of baseline). All our GPU work exited and free GPU
  memory returned to18,233MiB. No further01 GPU work is permitted;02 is excluded.

Final CPU rates at epochs1/3/20 were7.13/7.30/7.02fps, with1.83/1.93/1.83x
speedups. Batch-one tail calls fell from1,152/epoch to128/171/153 respectively.
The pinned comparisons are in `cpu-real-prefix-r3.json`. They include
pixel preparation, encoder, causal runtime, extraction and JSON, and exclude cache
loading/disk writes. They demonstrate an exact CPU fallback benefit, not a GPU or
full-replay projection.

## Owner handoff

The CPU-qualified source snapshot is on08 at
`/mpac/sdicks02/jobs/clasher/lockstep-20261009-code-r3/`; receipt source hashes pin it.
`probe_lockstep_cpu_v4.py` reproduces the CPU experiment. `probe_lockstep_v4.py`
prepares a bounded CUDA comparison; it does not admit anything.

Do not launch automatically. The coordinator must assign the08 window after
2026-10-09 05:00Z, check T5 GRU exits, and externally pin a window JSON:
`schema=clasher.v4.lockstep-owner-window.v1`, `host=127x08`,
`authorized_by=coordinator`, `t5_gru_exit_checked=true`,
`starts_at_unix`, `ends_at_unix` (duration<=300s).
The operator supplies `CLASHER_LOCKSTEP_GPU_AUTHORIZED=127x08`,
`CLASHER_LOCKSTEP_OWNER_WINDOW_FILE` and its `..._SHA256`; the driver checks the
window, nice>=10, memory reserve and8GiB GPU headroom. It refuses01/02. Use the
owner's immutable bundle/cache or private read-only02 service; tokens stay off05.
Check scalar execution before graph execution, with encoder/prefix/tail batches1.
Use the owner's supervisor with a hard timeout no longer than the remaining
assigned window; the code does not create an assignment or schedule a launch.

Any future admission still requires >=3 **complete** epochs x>=8 matches,
including15–24, plus epoch1 all64 matches against the original three09 cells.
Run with `--payloads`. `verify_lockstep_v4.py` independently compares all nine
raw streams, hashes, reconstructed CPU payloads, reference-cell non-clock fields
and new FIFO clocks. It rejects prefixes and never issues selection admission.
The owner retains source authentication, metric/bootstrap gates and admission.

## Future runs

For L2/live tooling or retraining, choose and qualify batching **before** starting
a run. Pre-register tensor error bounds together with allowed prediction/metric
differences, particularly threshold crossings, tracker births, event ordering/NMS
and timing. Test dense checkpoints and tie cases, pin precision, kernel/library
versions and batch/padding policy, and use one consistent path for every cell.
A later numerical-policy change requires an amendment and replay of completed
cells. No tolerance substitution is proposed for the current formal run.
