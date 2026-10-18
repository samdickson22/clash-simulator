# HP1 P1 — partial results; stopped by coordinator

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

Only this report is committed. Data, checkpoints, prior attempts and reviewed source remain outside git.
