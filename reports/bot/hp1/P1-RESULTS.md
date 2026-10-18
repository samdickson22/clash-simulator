# HP1 P1 — P1-cap capacity FAIL; P1-lag scored

**Latest: the block-shuffle P1-cap run completed one epoch (63,440,158 rows) and full-dev scoring.
Dev EMA joint NLL is 0.280886193985: FAIL against ≤ 0.2774.** P1-lag completed its half-epoch training from v2 on 08; its saved EMA scored **0.279609483633**
on full natural-label dev in the guarded recovery on 04. Completed-run details follow the historical records below.

## Original P1 attempts — stopped before full-dev scoring

**Both arms were stopped at clean optimizer steps at the coordinator's direction. Neither reached its first
full-dev evaluation, so the capacity gate (dev EMA joint NLL ≤ 0.2774) is unassessed.** No completed P1 model is
recommended. The coordinator's decision was to release the GPUs because random store reads dominate wall time;
the parallel RL track already trains with command lag.

| Arm / host | Best full-dev joint NLL / best-dev step | Final saved step / sampled rows | Trainer wall time | Gate vs 0.2774 |
|---|---|---|---|---|
| P1-lag / 04 | Not measured / none | 2222 / 18,202,624 | 7:58:45 active; 8:02:39 elapsed | Incomplete; unassessed |
| P1-cap / 08 | Not measured / none | 609 / 4,988,928 | 3:29:36 active; 3:30:33 elapsed for retained run | Incomplete; unassessed |

Both final `complete.json` files have `epoch: 0`, `stopped_by_signal: true`, and `best_dev: Infinity` (the
unevaluated sentinel). Both trainers exited 0 after SIGTERM and checkpointing. There are no full-run dev events
or best-dev checkpoints; the saved files below are resumable training checkpoints.

Paths used below:

- `J04 = 04:/mpac/sdicks02/jobs/clasher/bot-hp1-p1-20261017`
- `J08 = 08:/mpac/sdicks02/jobs/clasher/bot-hp1-p1-cap-20261018-08`

| Arm | Final checkpoint | SHA256 |
|---|---|---|
| P1-lag | `J04/p1-lag-d/step-00002222.pt` | `7056da68a9bdfea6183f666f6766053dac99eba64bc03d17b8b717f2f1530370` |
| P1-cap | `J08/p1-cap-b/step-00000609.pt` | `39698acc1cac5057e0ce239ce44095c2740bf3559ab766e4dfa28d66e1dc6f0c` |

CPU-only `torch.load(weights_only=True)` audits under CPU admission validated both final checkpoint states and
configs (lag 4L/768; cap 6L/1536), with matching trainer/input pins. Each host retains
`logs/coordinator-stop.checkpoint-audit.log`; independently streamed checkpoint hashes matched those audits.
The final cursors equal the sampled-row counts above. SIGTERM was sent only to verified owned main trainers:
04 PID 3258214 / PGID 3257623 at 2026-10-18T10:55:27Z; 08 PID 423107 / PGID 422167 at
2026-10-18T10:55:28Z. The last stages ended at 10:55:42Z and 10:57:51Z respectively. At
**2026-10-18T10:58:12Z**, both process groups were absent and `nvidia-smi` showed no compute processes on either
GPU (0% utilization; 16 MiB on 04, 104 MiB on 08). Evidence on each host:
`logs/coordinator-stop.signal.log` and `logs/coordinator-stop.gpu-free.log`.

## Loader diagnosis and measured worker trial

The ~228 GiB random-mmap store exceeds each host's 128,648 MiB RAM. The admitted 30-second profiles measured:

| Host / arm | Disk reads (MiB/s) | Major faults/s | CPU (% of one core) | System share of CPU time |
|---|---:|---:|---:|---:|
| 04 / lag | 168.57 | 1987.33 | 48.40% | 86.43% |
| 08 / cap | 159.84 | 1605.00 | 53.47% | 87.34% |

Both GPU samples were at 0%. Cap was observed in `wait_on_page_bit_common`; lag had already read ~3.05 TB by its
first pause. This points to random mmap page faults and repeated disk reads under a limited page cache as the
main bottleneck. CPU decoding alone does not explain the system-time share and disk traffic.

The reviewed loader supports 0–8 workers. Its prefetch factor is fixed at 2; it exposes no prefetch argument.
Exact resume restores model, EMA, optimizer, scheduler, cursor and Python/NumPy/Torch/CUDA RNG. Worker count is
outside the resume identity contract. We preserved checkpoint/state/RNG audits and resumed the same sampler
position before trying one loader worker. No trainer code changed.

Rates below include loading. Window rates use differences of the trainer's cumulative elapsed times over the
last 50 steps of the indicated phase; host load/cache conditions changed between phases.

| Arm / phase | Workers | Last step | Phase cumulative rows/s | Last-50-step rows/s | Optimizer-only median rows/s |
|---|---:|---:|---:|---:|---:|
| Lag, before trial | 0 | 1968 | 639.46 | 241.34 | 8474.04 |
| Lag, worker trial | 1 | 2093 | 1018.28 | 1044.27 | 11493.34 |
| Lag, final fallback | 0 | 2222 | 453.14 | 309.86 | 9267.24 |
| Cap, before trial | 0 | 421 | 360.76 | 230.99 | 6515.87 |
| Cap, first comparison | 1 | 570 | 1259.73 | 1505.67 | 7760.00 |
| Cap, final | 1 | 609 | 549.59 | 213.65 | 7106.22 |

One worker improved initial overlap but did not sustain adequate throughput. Lag's group PSS reached
21,020,761 KiB at 2026-10-18T10:13:12Z, exceeding the launcher's 20 GiB threshold (20,971,520 KiB). Its owned RAM
monitor requested a clean stop at step 2093 (launcher exit 90); it resumed with zero workers at step 2094.
Cap remained on one worker until the coordinator stop. Increasing workers further was unsuitable: the earlier
two-worker GPU smoke had already reached 23,464,055 KiB. All resource incidents and retired attempts are preserved.

Evidence: each job's `logs/loader-before-w1.log`, `loader-io-diagnosis.json`, `loader-w1-before-rates.json`,
`loader-w1-resume-audit.json`, stage `*.pss.log`, and stage receipts/logs. Lag also has
`loader-w1-at-stop-rates.json`, `loader-w0-resume-audit.json`, and `p1-lag-w1-a.ram-stop`; cap has
`loader-w1-after-rates-first-comparison.json`. Final phase rates are calculated from each output's `train.jsonl`.

## Smoke, recipe and provenance

Both required GPU smokes completed 20 steps / 163,840 rows, exit 0, without a signal stop:

| Output on 04 | Start–end UTC on 2026-10-18 | Wall | Smoke-only dev joint NLL |
|---|---|---|---:|
| `J04/smoke/gpu-cap-d` | 02:43:25–02:47:57 | 0:04:32 | 0.9559744170 |
| `J04/smoke/gpu-lag-d` | 02:48:29–02:52:48 | 0:04:19 | 0.3561409024 |

Smoke scoring uses only the first 4096 dev rows. These values do not assess the full-dev capacity gate and do
not describe the later full runs. The preceding CPU smoke/resume/pin chain is recorded in
`J04/logs/pin-check-b.log` (exit 0).

All GPU runs used the reviewed `src-ff5fa65fc7ba`, `/mpac/sdicks02/envs/clasher-gpu/bin/python`, detached
`bot/detach.sh` → `bot/exit/cpu_job.sh` admission, nice 15, `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`,
`MKL_NUM_THREADS=1`, `NUMPY_MADVISE_HUGEPAGE=0`, and `CUDA_VISIBLE_DEVICES=0`. CPU caps were 70 on 04 and 105
on 08; loader trials reserved two Python slots. Original zero-worker lag reserved four; final lag reserved one.

- Lag: v2 initialization, 4 layers / FFN 768, lr 1e-4, `overlay-lag30`, epoch fraction 0.5, epochs 1,
  warmup 500, seed 2026101802, effective batch 8192 / microbatch 7168, GPU allocation cap 32 GiB.
- Cap: from scratch, 6 layers / FFN 1536, frozen T11 sampler, lr 3e-4, warmup 2000, seed 2026101801,
  effective batch 8192 / microbatch 2048, `--epochs 6 --stop-after-epochs 1` to preserve the T11 schedule.
  The first attempt (`p1-cap-a`) exhausted its 24 GiB allocator limit despite 22.96 GiB physical GPU memory
  remaining. It exited 1 before its first checkpoint; its 1:56:28 wall time is additional to the table above.
  `p1-cap-b` restarted fresh with the same recipe and a 40 GiB allocator limit, passing that batch.
- Common: tile width 64, patience 3, checkpoint interval 1000. Exact resumes removed `--init` and retained all
  scientific arguments. Lag resumed 1968→1969 and 2093→2094; cap resumed 421→422, without skipped rows.

Retained trainer segments (UTC, 2026-10-18; admission/preflight gaps excluded from active wall):

| Host / stage | Start | End | Wall |
|---|---|---|---|
| 04 `p1-lag-d` | 02:53:03 | 09:54:02 | 7:00:59 |
| 04 `p1-lag-w1-a` | 09:55:32 | 10:13:25 | 0:17:53 |
| 04 `p1-lag-w0-b` | 10:15:49 | 10:55:42 | 0:39:53 |
| 08 `p1-cap-b` | 07:27:18 | 10:08:28 | 2:41:10 |
| 08 `p1-cap-w1-a` | 10:09:25 | 10:57:51 | 0:48:26 |

Before the 08 launch, source and inputs were copied from 04 and their full SHA256 lists matched. Environment
runtime files, Python binary and symlinks matched; generated `__pycache__` files differed and were left untouched.
Store root/train/dev manifests matched 04. The 08 GPU was empty before launch. Certificate:
`J08/logs/preflight-verified.log` and the accompanying per-file lists.

Selected immutable pins (full sets are embedded in the checkpoints and `train.jsonl` start events):

| Pin | SHA256 |
|---|---|
| Qualified T4 trainer | `301caa1003ab47eadc3f56973ec5398bed4d166dc1a0163d213e60a61854959d` |
| HP1 trainer wrapper | `92f6b08d6f58f97b83a52203ffd4a389800bc92784c2cf2d1bd74a627c0cf5e2` |
| v2 initialization | `87794378b691db330d4d37b83f1a1c04fd9defad517492652fe79c20d0471fae` |
| Lag overlay metadata | `3b79111ca49af0fed974dc48632561bfeaeb1aa6815086037ec14ea8c3c4b18c` |
| Store root manifest | `7180964c1d470807a97ad7a990ac8eb145fb25d15f1c95edf165b3f87743d20f` |
| Store train manifest | `0546cfddcf79be12509953358fb499ac3be29493ba4a87893bfbfbbe0f179e68` |
| Store dev manifest | `18a7d8e732080c3b6146b21a9d0f74683aba258b3e60f01d92037b9d7f0ccd4b` |

For the original stopped arms, only this report was committed. Their data, checkpoints, prior attempts and
reviewed source remain outside git. The block-shuffle implementation below is included with this update.


## Block-shuffle retry — 2026-10-18: throughput FAIL, full epoch not launched

**The new loader removes most random-read starvation, but P1-cap still misses 8,000 rows/s.**
The throughput-only run was stopped after 73 steps / 598,016 rows, exit 0, with a resumable checkpoint.
No full-epoch retry was launched, and dev EMA joint NLL remains **unmeasured**: the capacity gate at 0.2774
is still unassessed. This is a throughput failure, not a measured NLL failure.

Implementation: `imitation/hp1/block_shuffle.py`, selected by `--block-shuffle` (default **OFF**).
It uses the frozen T11 selection function, preserving the epoch row multiset, then shuffles selected rows
within contiguous, whole-perspective chunks in physical order. The qualified feature/target builder,
packed masks, overlay labels and S122 wait-weight compensation are unchanged. One raw RAM buffer is bounded
by `--shuffle-buffer-gb` (default 20 GiB, maximum 24 GiB); one optional loader thread prefetches batches.
Contiguous copies use `MADV_SEQUENTIAL` and drop source mmap pages every 64 MiB. Complete epochs are required;
seed, epoch, buffer size and saved cursor reconstruct the same order on resume. Chunk-local shuffling changes
batch membership relative to global IID shuffling; no NLL equivalence is claimed.

Sol correctness review (`gpt-6.1-sol`, high) found temporary source-mmap residency and fractional-epoch
truncation issues in round 1. Both were fixed. Round 2 approved with no remaining findings, including the
benchmark and owned-PID cleanup. **28 HP1 tests passed** locally and in the review: exact T11 row multiset,
no duplicates, seed determinism, cursor suffixes, lag-overlay targets/weights, packed masks, ragged entities,
zero-entity rows, and cross-chunk padding. `imitation/model/train.py` and the qualified T4 code hash remain
unchanged (`301caa1003ab47eadc3f56973ec5398bed4d166dc1a0163d213e60a61854959d`).

`B04 = 04:/mpac/sdicks02/jobs/clasher/bot-hp1-blockshuffle-20261018-04`.
Detached admission receipt: PID/PGID 4099991, launch **2026-10-18T12:03:30Z**. The owned trainer was PID
4100156, nice 10, at most six observed OS threads including CUDA/runtime threads, with one loader thread.
The source was copied from `J04/src-ff5fa65fc7ba` into `B04/source`, then only the HP1 wrapper/module/tests/docs
were updated. `PYTHONHASHSEED=0`, OMP/MKL/OpenBLAS thread limits 1, `NUMPY_MADVISE_HUGEPAGE=0`, one A6000.
P1-cap was initialized from scratch: 6L/1536, AdamW 3e-4, full six-epoch cosine schedule, warmup 2,000,
EMA .999, effective batch 8,192 = 2 × 4,096, buffer 2 GiB, CUDA allocator cap 46 GiB.
The bounded harness planned at most 256 optimizer steps; it was ended early after the rate was clearly below
the required threshold. Host 08 had less CPU load at preflight (35.90 versus 04's 55.53), but was not used
because the throughput prerequisite failed on 04.

| Measurement | Rows/s / value |
|---|---:|
| Prior random-mmap diagnosis, reported point rate | ~300 rows/s (not rebenchmarked) |
| New mode, startup-inclusive, 598,016 rows / 231.044 s | **2,588 rows/s** |
| New mode, sustained steps 17–73, 466,944 rows / 92.083 s | **5,071 rows/s** |
| Optimizer-only aggregate over the same 57 steps | 5,939 rows/s |
| GPU utilization over the sustained window, 92 samples: mean / median | 73.72% / 100% |
| Observed trainer PSS during training | 11.62 GiB |

The sustained window is **12:05:52.617–12:07:24.700Z**, calibrated from the host's wall and monotonic clocks.
Its 92.083 s includes 78.621 s of optimizer/scheduler/EMA work and approximately 13.462 s outside those step
timers; a buffer transition produced an 11.168 s inter-step gap. Thus a bigger buffer could amortize refill
stalls, but the observed optimizer-only ceiling of 5,939 rows/s is already below 8,000. The GPU is now doing
substantial work; the 6L/1536 compute path is a remaining limit, alongside sequential refills. Initial full-store
selection/index construction also contributes substantial one-time startup cost. Per instruction, no further
full run or other-job changes were made after the failed measurement.

SIGTERM went only to the verified owned main PID 4100156 / PGID 4099991 at **12:07:23Z**; the qualified handler
saved step 73 after its scheduler and EMA update. The benchmark finished at **12:07:35.098Z**, exit 0.
At **12:07:41Z**, that session had no processes and 04 was back to 0% GPU / 16 MiB. Dev was deliberately skipped
by the graceful-stop path. The CPU-only checkpoint audit validated the 6L/1536 config, state, sampling pins,
finite EMA tensors and unchanged qualified source.

- Checkpoint: `B04/throughput-cap/step-00000073.pt`.
- Checkpoint SHA256: `c093471d5bf9c0452ba17b783cd26cd3c70e17bcd8def03af740b367415b08a5`.
- Wrapper SHA256: `7931cd0d7cd91d3126e320205ef135c1b0e32378243bb0618ab37c2157a67f83`.
- Block module SHA256: `d215a64b6bf7fc8ce49a286d9e92e5e3199f49524af13efefa26d31acbe66ca6`.
- Evidence: `B04/logs/{summary.json,throughput.json,gpu.csv,pss-during.txt,stop-signal.log,checkpoint-audit.json,sol-review.txt}`,
  `B04/throughput-cap/{train.jsonl,complete.json}`, and `B04/benchmark.{py,sh}`.

All times, run PIDs and SHA256 values above came from commands. Code/report publication uses a temporary index
based on `origin/main` in `/tmp/clasher-hp1-blockshuffle`, with `clasher-secret-scan`. Stores and checkpoints
remain outside git. RL actors, play-quality jobs, hosts 03/09–18 and PGID 516161 were not modified.


## Completed block-shuffle P1-cap — 2026-10-18: capacity FAIL

Following the coordinator's override of the 8,000 rows/s throughput prerequisite, a fresh P1-cap run launched on
04 at **12:12:03Z**. The earlier 5,071 rows/s result was accepted as adequate relative to the measured 5,939 rows/s
optimizer rate for that microbatch profile. The complete run finished at **15:44:24Z**, exit 0.

| Result | Value |
|---|---|
| Architecture / initialization | 6 layers, FFN 1536 / from scratch, no v2 or stopped-checkpoint initialization |
| Retained training | **63,440,158 rows; 7,745 optimizer steps; epoch 1, cursor 0** |
| Full-dev store | **11,776,480 rows**, natural labels; smoke mode OFF |
| Full-dev EMA joint NLL | **0.28088619398544684** |
| Capacity criterion | ≤ 0.2774; **FAIL**, by +0.003486193985 |
| Resumed training-loop rate, including loader | **6,173.86 rows/s**; 55,248,158 rows / 8,948.726 s |
| Whole-run elapsed / admitted segment wall time | **3:32:21 / 3:30:55**, including failed work, setup, checkpoints and full-dev scoring |

The scientific recipe was 6L/1536, AdamW 3e-4, warmup 2,000, full six-epoch cosine schedule stopped after the
first epoch, EMA .999, effective batch 8,192, seed 2026101801, tile width 64. Block mode used a 2 GiB buffer,
one loader thread, nice 10, `PYTHONHASHSEED=0`, OMP/MKL/OpenBLAS limits 1 and `NUMPY_MADVISE_HUGEPAGE=0`.

The first segment used microbatch 4,096 with a 46 GiB allocator limit. It logged 1,958 steps before CUDA OOM
on the next batch: 43.81 GiB was allocated, 1.23 GiB reserved but unused, and a further 2.25 GiB allocation
could not fit. Its last durable checkpoint was step 1,000. The run resumed **that checkpoint from this fresh
run**, with microbatch 2,048 and checkpoint interval 250; effective batch, model, optimizer/scheduler state,
EMA, seed and saved sampler cursor were retained. The 958 completed updates after step 1,000 were rolled back.
The qualified loop normalizes all microbatches by the effective-batch denominators; its accumulation test passed.
Changing the microbatch changes floating-point/dropout execution, so bitwise equality with a hypothetical
uninterrupted 4,096-microbatch run is not claimed.

| Admitted segment on 04 | UTC start–end | Outcome |
|---|---|---|
| `logs/full.*`, PID/PGID 4160369, trainer 4160430 | 12:12:03–12:58:44 | CUDA OOM, exit 1; durable step 1,000 |
| `logs/full-resume1.*`, PID/PGID 319321, trainer 319431 | 13:00:10–15:44:24 | Resume 1,000→1,001; finish epoch and full-dev, exit 0 |

`B04 = 04:/mpac/sdicks02/jobs/clasher/bot-hp1-blockshuffle-20261018-04` (as above).

| Checkpoint | SHA256 |
|---|---|
| `B04/p1-cap-full/best-dev-step-00007745.pt` | `f25328e90d9b54ea29a7c513c93955ebdd07a8a0aa4d1dad8012b72f884ba52c` |
| `B04/p1-cap-full/epoch-000-step-00007745.pt` | `df13bf97a8fe03e40fa6957313f4f87a2551253f37e7657ce7f8c12648103d78` |
| Retained fresh-run step 1,000, used for recovery | `f84993330a9321a1fcd478959c0b9923ade24340a48e4fa0bc801823807cedfd` |

A CPU-only audit under admission validated the 6L/1536 config, recipe, sampler/code pins, completed epoch and
cursor, finite EMA tensors, absence of an initialization checkpoint pin, and identical EMA weights in the
best-dev and epoch checkpoints. There is exactly one full-dev event, matching the saved best-dev score.
`stopped_by_signal: true` is the wrapper's planned stop **after** this full-dev pass; epoch 1 / cursor 0 and the
dev event distinguish it from the earlier interrupted runs. At **15:50:14Z**, 04 was at 0% GPU / 16 MiB.

Evidence: `B04/logs/{full.checkpoint-audit.json,full.checkpoints.sha256,full.start.utc,full.end.utc,
full-resume1.start.utc,full-resume1.end.utc}`, the segment logs/receipts/GPU samples, and
`B04/p1-cap-full/{train.jsonl,complete.json}`. The cap snapshot remains immutable at
`B04/source`: wrapper SHA `7931cd0d7cd91d3126e320205ef135c1b0e32378243bb0618ab37c2157a67f83`,
block module SHA `d215a64b6bf7fc8ce49a286d9e92e5e3199f49524af13efefa26d31acbe66ca6`
(the implementation published in `d692e7c83`). The subsequent fractional-epoch loader update is confined to
separate lag snapshots; it did not change the running cap source or its checkpoint pins.

## P1-lag half-epoch run and cross-host preflight

`L08 = 08:/mpac/sdicks02/jobs/clasher/bot-hp1-blockshuffle-lag-20261018-08`;
`L04 = 04:/mpac/sdicks02/jobs/clasher/bot-hp1-blockshuffle-lag-20261018-04-stage` (verification snapshot).
At the coordinator's request, P1-lag launched detached at **14:45:55Z** (trainer start 14:45:56Z),
PID/PGID 2304384, trainer 2304596. **Training completed; host OOM killed the trainer during full-dev evaluation at 16:25:16Z (exit 137).**

It starts from the v2 EMA weights, SHA256 `87794378b691db330d4d37b83f1a1c04fd9defad517492652fe79c20d0471fae`,
with a fresh optimizer, rather than either stopped pilot checkpoint. Recipe: 4L/768, lr 1e-4, warmup 500,
cosine over one half-epoch pass, EMA .999, effective batch 8,192 / microbatch 4,096, seed 2026101802,
`overlay-lag30` (27-tick command delay, maximum 30-tick label shift), natural dev labels, one loader thread,
2 GiB buffer, 40 GiB CUDA allocator cap, nice 10 and `PYTHONHASHSEED=0`.

The fractional loader selects exactly the original T11 IID prefix of `ceil(N * 0.5)` rows **before** changing
its order by chunks. It returns the original full index length so the qualified trainer retains its original
schedule and applies the fraction once. Sol review found and fixed an equals-form argument parsing edge case;
the second review approved with no remaining findings. **34 HP1 tests passed**, including fractional IID-prefix
membership, overlays, determinism and cursor suffixes. The update is published in `6c3b080e1`; the qualified T4
trainer is unchanged. Lag wrapper SHA: `8e2438c355c1979576e500df06f1680c5dfb30ae7cb9cd1ca7ac7091e5e0d379`;
block module SHA: `1b9874abc839f6132be923efa5a7f39e24b92083f6df25bde85d66bd547c8794`.

**Preflight PASS at 14:45:42.278872Z, before launch:** actual SHA256 inventories matched between 04 and 08
for all 130 train/dev store files plus shared store metadata within that count, 20,550 managed environment
files, 16,762 source files, environment/source symlink definitions, Python interpreter binary, three input files,
v2 initialization and all four overlay files. Generated Python bytecode was excluded; eval/eval_ood data were
not read. Both lag source snapshots match; the separately running cap snapshot was left unchanged.

| Matching inventory | SHA256 of the inventory file |
|---|---|
| Store (`store.sha256`, 130 records) | `0714ffb972708e6d633027e3fddf3c2456af43f19114b556b8aa05b6bba45696` |
| Environment (`env.sha256`, 20,550 records) | `cd0d1ed6d32f9f37ec03a42ba3ef19ffca4c00d484c58a4967b582222b3e4637` |
| Source (`source.sha256`, 16,762 records) | `ea19ff8829526b7f52d6953caf52e9f4b583cc214e25230e20420300247bc200` |

The inventories, interpreter/symlink/input/overlay comparisons and the machine-readable certificate are in
`L08/logs/preflight/` and `L04/logs/preflight/` (`PASS.json`). Review evidence is `L08/logs/sol-review.txt`;
launch recipe and receipts are `L08/lag-run.sh` and `L08/logs/lag.*`.


## P1-lag dev recovery after 08 host OOM — 2026-10-18

All requested half-epoch training completed on 08: **26,112,729 rows, 3,188 optimizer steps, final LR 0**,
with a final training-loop rate including loader of **5,427.94 rows/s**. The buffer was **2 GiB**, including
at the time of the failure; the advertised 24 GiB CLI limit was not used for either full run.
The lag-labelled T11 set is smaller than cap's natural-label set because the unchanged overlay masks
28,395,182 busy rows as unsupervised. The half epoch is the original IID prefix of that lag-labelled selection.

At **16:25:16Z**, the kernel global-OOM killer selected trainer PID 2304596 during dev evaluation
(`anon-rss: 9060584kB`); no full-dev NLL was saved. SSH was temporarily unresponsive despite responding to ping.
The trainer and its dev worker were gone when access returned. Only the verified owned, now-unneeded pending
CPU-audit wrapper PID/PGID 2798821 was terminated. At **16:27:06Z**, 08 had about 10.4 GB available and
GPU 0% / 104 MiB, with no remaining heavy process from this run. No further fitting or scoring is launched on 08
while its available memory is below the coordinator's 20 GB floor. Other jobs were not modified.

The checkpoint saved **before dev** contains the completed training cursor and exact EMA. Its bytes were
copied to 04 and SHA256-verified unchanged:

- Original: `L08/p1-lag-half/step-00003188.pt`.
- Recovery copy: `L04/models/lag-step-00003188.pt`.
- SHA256: `2f1be625ed086ec5ba2ec29102d3d007f3fa0164d015aa55d88b52ce876054ba`.

A detached recovery launched on 04 at **16:34:53Z**, PID/PGID 1810408, evaluator PID 1810582;
full-dev scoring began at **16:35:07.943926Z**. It opens only natural-label dev, calls the unchanged qualified
`runner.dev_joint_nll` with the original EMA, batch 1,024 and bf16, and uses **workers 0** to avoid a fork
retaining the training buffer/store/index. It makes **zero optimizer updates and no checkpoint writes**.
The external score identifies the immutable checkpoint above; no best-dev model checkpoint was written.

The recovery uses nice 10, admission 1, OMP/MKL/OpenBLAS 1, `PYTHONHASHSEED=0`, a 20 GiB GPU allocator limit,
and explicit host04/source/integrity checks. It waits for 6 GiB available before initialization and exits its
own process if available memory falls below 3 GiB. At 16:30:09Z, 04 had only 1.94 GB available; no evaluator was
started then. At recovery admission 16:34:53Z it had 9.41 GB available, and at 16:35:16Z it retained 6.05 GB.
Sol high reviewed the recovery: host/import binding, fail-closed guard and GPU-query checks were fixed;
round 3 found no remaining material bugs or scoring-validity issues. The original T4 source is unchanged.

**Recovery complete: full-dev EMA joint NLL 0.279609483633; checkpoint SHA unchanged.**
Evidence: `L08/logs/{lag.oom-recovery.log,lag.exit,lag.end.utc}`, original train/options logs,
`L04/{hp1-lag-dev-recovery.py,hp1-lag-dev-recovery.sh}`, `L04/logs/dev-recovery.*`, and
`L04/lag-dev-recovery/dev-score.json`. Cap's completed capacity FAIL remains 0.28088619398544684 vs 0.2774.


## Completed P1-lag full-dev score — recovered on 04

| Result | Value |
|---|---|
| Training completed on 08 | **26,112,729 rows; 3,188 updates; requested lag-labelled epoch fraction 0.5; cosine LR 0** |
| Training rate including loader | **5,427.94 rows/s**, versus the prior random-mmap diagnosis of ~300 rows/s |
| Full natural-label dev | **11,776,480 rows visited; 11,754,036 finite supervised NLL rows**, batch 1,024, bf16, smoke OFF |
| Full-dev EMA joint NLL | **0.279609483633426** |
| Scoring UTC start–end | 2026-10-18T17:01:09.662995+00:00–2026-10-18T17:26:50.051347+00:00 |
| Active full-dev scoring time, summed across persisted segments | **1,540.300 s** |
| Evaluator | Host 04, nice 10, workers 0, OMP/MKL/OpenBLAS 1, `PYTHONHASHSEED=0`; guarded memory |
| Wall time from original launch to recovered score | **2:40:54**, including the OOM, interrupted dev, recovery and admission waits |
| Further optimizer updates | **0**; the completed-training checkpoint was read-only |

DESIGN §7 predeclares the ≤ 0.2774 capacity gate for **P1-cap**, which **FAILS** at 0.28088619398544684.
It does not predeclare an independent natural-dev NLL gate for P1-lag; the lag score is descriptive.
No play-quality screen or subsequent RL-init decision is claimed here.

The replacement detached wrapper launched at **16:54:57Z**, PID/PGID **1955105**; after CPU admission,
evaluator PID **1995566** began scoring at **17:01:09.662995Z**. This pass started from dev row 0 and
completed without another memory stop at **17:26:50.051347Z**, exit 0.

The first recovery pass on 04 was stopped safely by its memory guard at **16:50:10.051183Z**,
when available RAM reached **3,196,866,560 bytes**, below 3 GiB. That pass produced no NLL and its logs
are archived under `L04/logs/dev-recovery-attempt1/`; the trained checkpoint was unchanged.
The replacement evaluator persists the completed batch prefix, float64 NLL sum and finite count after each
batch using atomic replacement and an exclusive lock. Its contract pins checkpoint, dev manifest, assets,
qualified source, helper source, batch size and dtype. After a memory stop, it resumes that prefix without
double-counting, preserving the qualified accumulator's arithmetic and the original per-row NLL functions.
An integration test matched the original qualified full-dev function for uninterrupted and interrupted/resumed
passes, NaN masks, partial final batches and exact suffix membership; Sol high approved the new helper.
Helper SHA256: `428f7342227c4136a5d808c2f10f270c8b2d12cbcd99ef831b53bfd71a015257`. Any subsequent memory-stop receipts remain in the
corresponding `L04/logs/dev-recovery-attempt*/` directories. No optimizer updates were made during recovery.

The scored checkpoint is **`04:/mpac/sdicks02/jobs/clasher/bot-hp1-blockshuffle-lag-20261018-04-stage/models/lag-step-00003188.pt`**,
SHA256 **`2f1be625ed086ec5ba2ec29102d3d007f3fa0164d015aa55d88b52ce876054ba`**. Its bytes match the original `L08/p1-lag-half/step-00003188.pt` before
and after scoring. No best-dev file was created: the original trainer was killed during dev, so the checkpoint's
state still records epoch 0 / cursor 26,112,729 and its pre-dev best score; the external score receipt binds this
completed-training EMA to the full-dev result above. The original v2-init pin and all training optimizer/scheduler
state are retained. The audit verified finite EMA tensors, 4L/768 config, original v2 initialization and
sampling/source pins, and the completed zero-LR cosine schedule. Workers 0 preserves the same sequential batches
and qualified EMA/bf16 NLL calculation while avoiding the memory retained by a forked dev worker.

Recovery source qualification: `301caa1003ab47eadc3f56973ec5398bed4d166dc1a0163d213e60a61854959d`; receipt `5c7e83bacc92096a30520ccdaf002321b753542a7afc489e57183df865fc7229`.
Recovery harness SHA256: `0e9cd7228cfe65f1548bb4b0ba7d431dc50d086c58248a1cbf789e286bc3cee8`. At **2026-10-18T17:27:35Z**, GPU 04 was **0% /
16 MiB**, with this evaluator gone. No new heavy process from this task was launched on 08 after
its OOM. Evidence: `L04/lag-dev-recovery/dev-score.json`, `L04/logs/dev-recovery.{log,exit,start.utc,end.utc,receipt.json}`,
`L04/logs/hp1-lag-dev-recovery-review.json`, `L04/logs/hp1-lag-dev-progress-review.json`, reviewed recovery scripts/helper and its integration test, and the original 08 train/options/OOM logs listed above. Both requested training
arms and full-dev scores are complete. No additional cap epochs were run after its capacity gate failed.
