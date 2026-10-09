# Performance audit: imitation pipeline

Auditor run 2026-10-08 23:40–00:10Z. This was a read-only audit: no code edits, no signals, no git. The only profiling was on 127x08 CPU (one to four threads, nice 19, train data only), and scratch files were removed afterwards. I read /proc, nvidia-smi and logs of the running jobs on 127x01 and 127x08 without attaching to them. No eval, eval_ood or heldout data was touched.

## 0. What I measured (the evidence base)

| Item | Value | Source |
|---|---|---|
| T11 seed22 (127x01, io12 adapter) step-only rate | median **11.6k rows/s** over the last 200 steps | `rows_per_second_step` in train.jsonl |
| T11 seed22 windowed rate, loader included | 9.7k (400 steps), 8.7k (200 steps). Cumulative since the 23:23 resume is 7.1–7.3k. | train.jsonl |
| T11 seed22 per-step stalls | step-only rate drops to **432–980 rows/s** on some steps (11002–11003, 11014–11016) | train.jsonl |
| 127x01 memory PSI at 23:52Z | `full avg10=54% avg60=50% avg300=31%`. IO PSI is only 3–10%, CPU PSI is about 0. | /proc/pressure |
| 127x01 GPU utilisation over a 10 s window during stalls | mean 13.6%; only 2 steps completed in 10 s | nvidia-smi at 250 ms |
| 127x01 RAM | 125 GB total, about 107 GB page cache, 1–7 GB free. Direct reclaim is active (pgscan_direct +38k pages in 5 s). | free, /proc/vmstat |
| T11 memory per process | Trainer: 8.5 GB anonymous, 9.5 GB private dirty. Each of the 12 loaders: about 7.8 GB anonymous, mostly still shared COW, with 120–200 MB private. | smaps_rollup |
| T4 qualified ceiling (data cached) | 12.15k rows/s at about 90% GPU utilisation on the v1 store. Microbatch 2048–7168 all give 11–12k. | `imitation/model/receipts/throughput-0935/*` |
| T11 seed21 (127x16, loader6) | 7.7k rows/s, steps 8933→10312 between 21:23:54 and 21:48:18 | t11/receipts/status-127x16-* |
| T11 dev pass | about 7 min per epoch (epoch end 20:55:21 to training resumed at about 21:02) | same receipts |
| v2 train store | 143.74M rows, 318,766 perspectives, 184 GB in total. `flat_entity_features` alone is float32 [1.607e9, 17] = **109 GB**. The columns build_batch actually reads total about 165 GB. | headers on 127x08 |
| Row mix (10M-row C56 sample) | 99.8% supervision-valid, **95.4% waits**, 11.08 entities per row on average (max 73) | train columns |
| Epoch sampling | about 63.4M of 143.7M rows per epoch (44%) | PROGRESS-T11 cursor |
| v2 train `manifest.json` | **988 MB JSON**: 10.6 s to parse, 3.7 GB peak RSS. Loaded by every PackedStore open, and the trainer's object heap is inherited by every loader. | measured on 08 |
| Entity feature exactness (1.8M-entity sample) | fp16 and bf16 are **not** exact. 12 of 17 columns have ≤256 distinct values. Col0 = k/18000 and col1 = k/32000 exactly for 100% of the sample. Cols 9/14/15 have 35k/330k/311k distinct values. | measured on 08 |
| Other float columns | global_features: 18 columns, each with ≤55,898 distinct values (≤65,536, so uint16 codes fit). Recent-play features: ≤1,154/55/65 distinct values. opp_ability_ages: ≤1,201. | measured on 08 (300k rows) |
| GRU (127x08, T5 frozen) | **34.5 s/step (237 rows/s)**. Step 1334 after 12.75 h, still in epoch 0 (cursor 10.9M of about 15.4M). | train.jsonl |
| GRU thread split | Main thread (forward with in-forward history build) 412 CPU-min. `pt_autograd` (backward) 345 CPU-min. Wall time is 765 min. | /proc/…/task |
| GRU GPU by phase | Forward phase 16–35% utilisation at about 160 W. Backward phase **100% at 288 W**. | nvidia-smi at 200 ms |
| GRU kernel overhead | 1.07e9 minor faults; system time is 30% of process CPU | /proc/stat |
| `build_batch` CPU cost (warm, 1 thread) | GRU-style history pieces (about 1,003 rows): **33.6k rows/s**. With the per-piece `release_pages` that GRU does: **24.5k rows/s**. `release_pages` takes 6.0 ms per call. An 8192-row batch takes 0.175 s (47k rows/s). | profile on 08, C56 train |
| Model size | SetPolicy 2,254,938 parameters; GRU 2,477,274. That is 9–10 MB of fp32 gradients per step. | CPU instantiation on 08 |
| Counter-dropout masks (DDP candidates) | T11 `counter_dropout.mask` issues **103 aten ops per call** (int32, each over the full activation). GRU `gru_counter_dropout.mask` issues **144 aten ops per 1M-element chunk** (int64, Philox-10, in a Python chunk loop). On CPU they are 2.7–3.6× slower than native dropout. On GPU, native dropout is a single fused kernel. | torch.profiler on 08 CPU |
| DDP qualifications so far | Both T11 (`qualify_gpu_worker.py: dropout=0`, `install(model, dropout_override=0)`) and the GRU reference (`gru_ddp_reference_nodropout.py`) ran with **dropout disabled**. **No throughput with counter-dropout enabled has been measured.** | code |

**Headline diagnosis.**
- **T11 is GPU-step-bound at about 11.6k rows/s.** It is degraded by **page-cache thrash**, not by raw IO or CPU: the 165 GB working set is larger than RAM, memory PSI "full" is 30–55%, and individual steps stall for seconds. That puts the realised rate at roughly 7–9.7k.
- **The GRU is limited by two serial phases of about equal length.** One is a CPU-bound forward phase that builds history synchronously in the trainer thread. The other is a GPU-bound backward phase that recomputes 32 history rows per endpoint.
- **The DDP rollout plans have an unmeasured, probably very large, per-GPU slowdown from eager integer dropout masks.**

---

## 1. Ranked opportunities

Ranking is by expected wall-clock impact on what is running or about to run: T11 (2 seeds), the GRU (paused for perception at 04:40Z, then resumes), DDP rollout for both, and later imitation runs.

### #1. Fuse the counter-dropout mask before any DDP rollout (T11 and GRU)

**(a) Files.**
- `imitation/t11/ddp/counter_dropout.py`: `mask`, `drop`, `_attention`.
- `imitation/t5/operations/gru_counter_dropout.py`: `philox_word`, `CounterDropout.mask` (Python 1M-element chunk loop), `install().attention`.
- `imitation/t11/ddp/engine.py`: `optimizer_step(compute_chunk=1024)`.

**(b) Evidence.**
- The T11 mask runs about 26 full-tensor int32 passes per site; 103 aten ops were counted. Per optimizer step at 8192 rows and T≈96, the sites total about 7.5e9 elements:
  - FFN hidden: 8192·96·768 per block.
  - Two residual sites: 192 wide.
  - Attention probabilities: 8192·6·96², plus the checkpoint replay.
  - Cross-attention: on play rows only.
- At about 300 B of traffic per element (int32 read and write × 26) and about 650 GB/s, that is **about 3–4 s per step of extra GPU time against the current 0.7 s**. A6000 per-GPU throughput would fall to about 2k rows/s, so world-3 would deliver about 6k rows/s, less than one GPU today (9.7k).
- The GRU Philox version is much worse: int64, about 144 ops per element-chunk. Per history piece (1024 rows, T≈80, 4 blocks) that is about 0.5e9 masked elements. With 250 pieces per step, forward plus checkpoint replay, the estimate is **tens of minutes per step against 34.5 s today**. Even if this estimate is 5× too pessimistic, GRU DDP would be slower than the single-GPU original.
- Neither cost appears in any receipt, because every qualification ran with p=0.
- The explicit fp32 attention (materialised [B,6,T,T] scores) adds about 10–20% over SDPA even at p=0.
- `compute_chunk=1024` costs little compared with the masks. T4's 1024-microbatch figure (5.9k rows/s) was the first, cold candidate in `memory-sweep.json`, so treat it as unreliable. Use ≥3584 anyway, because counter-dropout masks do not depend on chunking.

**(c) Expected gain.** Generate each mask in one kernel (Triton kernel or `torch.compile` of the integer-only mask function). The hash then runs in registers, at about 30–60 integer ops per element, which is compute-bound at about 20 int-TOPS. Expected overhead is about 5–10% of a step. This turns DDP from "slower than 1 GPU" into close to linear: gradient allreduce is 9–10 MB per step, about 10–20 ms on 9.4 Gbit/s, which is 2–3% of a 0.7 s step and under 0.1% of a GRU step. It affects T11 and GRU training wall time on any DDP plan: up to 2–3× with world 2–3.

**(d) Effort.** About 4–6 h: a Triton or compiled mask for each scheme, an exhaustive equality test, and a p=0.1 throughput benchmark at world 1.

**(e) Correctness.** **Bit-exact is checkable and expected.** Integer xor, shift and multiply are deterministic and wrap mod 2³² in both eager CUDA and Triton. Compile **only the bool-mask generator**. Keep `x*keep.to(dtype)/(1-p)` eager, because Inductor would fuse the bf16 multiply and divide in fp32 and change the rounding. Verify `torch.equal` on masks across all 17 sites, bucket widths, padding and row ranges, including rows ≥2³².

**(f) Frozen status.** These DDP candidates are qualification-only, not production. A mask-identical kernel keeps the mask contract and can be re-frozen as a new candidate. **Required:** add a dropout-on throughput gate before any production switch.

### #2. Shrink the T11 working set below RAM: a lossless compact v2 store, plus removing the manifest heap

**(a) Files.**
- New store variant derived from `…/imitation/data/v2-store-v1/train`.
- A decode adapter in front of `imitation/model/batching.py:build_batch`, where entity, global, recent-play and ability features are gathered.
- `imitation/model/store.py:PackedStore._load_t3` parses the 988 MB manifest and builds the 1.15 GB `row_ids`.
- `imitation/t5/resources.py` (`release_pages`) and the T11 `loader_io_home.py` MADV_RANDOM.

**(b) Evidence.**
- The working set (about 165 GB of read columns, 109 GB of it entity features) is larger than the 125 GB of RAM. The epoch touches 44% of rows uniformly at random, so nearly every 4K page.
- Memory PSI full is 30–55%, and refaults stall even the trainer's main thread (code pages and pageable temporaries), giving steps at 432–980 rows/s.
- The realised rate is 7–9.7k against an 11.6k step ceiling. T4 ran the same code at 12.15k with the store cached.
- Lossless re-encoding from the measured value sets, each decoding bit-exactly to the same float32:

  | Data | Encoding | Size |
  |---|---|---|
  | Entity col0 | uint16, k/18000 | |
  | Entity col1 | uint16, k/32000 | |
  | Entity col9 | uint16 dictionary if ≤65,536 values (verify on the full column), otherwise float32 | |
  | Entity cols 14/15 | float32 | |
  | 12 low-cardinality entity columns | uint8 dictionary, or 7 booleans bit-packed | |
  | Entity total | 20–26 B per entity instead of 68 | **109 → 32–42 GB** |
  | global_features | uint16 | 10.4 → 5.2 GB |
  | Recent-play features | uint16 + 2×uint8 | 27.6 → 9.2 GB |
  | opp_ability_ages | uint16 | 4.6 → 2.3 GB |

- The total read working set drops to about **75–85 GB**, with page-cache headroom on 125 GB hosts.
- Parsing the manifest lazily (the trainer needs only `target_start` and counts) frees about 3–4 GB of trainer heap that every forked loader inherits. Storing `row_ids` as a column frees 1.15 GB of anonymous memory per process tree.

**(c) Expected gain.**
- T11-type runs: from 7–9.7k to about 11–11.6k rows/s sustained (+20–60%). This removes the multi-second stall steps and makes the 12-worker/prefetch-4 tuning unnecessary.
- Cold resumes become fast. Resumes are frequent after host losses and leases.
- Store copies shrink by about 2.3×.
- Two jobs per host become feasible.
- It is the prerequisite for DDP on every host: each rank still touches the whole store over an epoch.
- Timing: this would cover only the tail of the current T11 seeds (about 8–9 h left each), but it applies to the GRU-on-v2, ablations, T12 and DAgger retrains.

**(d) Effort.** About 8–10 h:
- Streaming encoder with 8 processes over 184 GB: about 10–20 min of IO.
- Decode adapter: a vectorised `table[code]` gather in build_batch.
- Full-column round-trip equality pass.
- Qualification: 65,536-row tensor/order equality plus checkpoint replay, the same procedure as io12.

**(e) Correctness.** **Bit-exact is checkable.** Decode every column fully and compare its bytes with `np.array_equal(view(uint32))`. build_batch's output tensors are then identical. Risk: a high-cardinality column the sample missed. The full-column check catches it, and that column then stays float32.

**(f) Frozen status.** Running T11 pins the store manifest hash and the T4 code hash. Deploy as an operational adapter with a new store path and a qualification receipt, as io12 was, or for new runs only. Do not mutate v2-store-v1.

*Cheaper alternative with the same goal (also bit-exact):* an **epoch materialiser**. The epoch order is fully determined at epoch start (PCG64 shuffle). One bucketed sequential pass (about 184 GB read plus about 82 GB written to scratch NVMe, a few minutes) writes the epoch's rows in consumption order, so training reads sequentially. RAM no longer matters, but it costs 82 GB of scratch per seed and about 12 h to build. Prefer the compact store.

### #3. GRU (frozen T5 recipe): move the history build out of the trainer thread. Bit-exact, about 1.6–1.7×.

**(a) Files.**
- `imitation/t5/variants.py:GRUPolicy.encode`: synchronous `build_batch(self.history_store, unique[loc])`, then `release_pages(...)` on every one of about 250 pieces per step, then a pageable `.to(device)` inside `encode_context`. The checkpoint replays the H2D during backward.
- `imitation/t5/resources.py:release_pages`.

**(b) Evidence.**
- The main thread spends 18.5 s per step at 16–35% GPU utilisation. The backward phase spends 15.5 s per step at 100% GPU.
- About 250k history rows per step at 24.5k rows/s gives about 10 s of pure build_batch CPU, plus page refaults.
- `release_pages` takes about 1.5 s per step (250 × 6 ms) and drives the 1.07e9 minor faults and 30% system time.
- Pageable H2D of about 3 GB per step each way, forward and replay, serialises with the GPU.

**(c) Expected gain.**
- Have loader workers precompute the exact same history pieces: same `history_indices`, same 8192-group count sort, same 1024 split. Pieces depend only on the endpoint indices, which are known from the frozen order.
- Deliver them pinned. Drop the per-piece `release_pages`; release once per step if a resource bound requires it.
- The forward phase then drops from about 18.5 s to about 5 s (GPU-bound). The step goes from 34.5 s to about 20–21 s, which is **237 → about 400 rows/s**.
- Epoch time goes from about 18 h to about 11 h. Over 12 epochs (patience 3) that saves several days.
- A quick partial version (drop the per-piece `release_pages` only) gives about 8–10%.

**(d) Effort.** About 4–6 h for the adapter and pinned queue, plus about 2 h for qualification: a short CPU and CUDA replay comparing all checkpoint sections.

**(e) Correctness.** **Bit-exact is checkable.** build_batch is deterministic, and the GPU kernel order, shapes and dropout RNG consumption are unchanged. Checkpointing still records the same CUDA RNG state, because no new CUDA RNG calls are introduced.

**(f) Frozen status.** GRU is frozen as T5 plus the gate-a amendments. Deliver as an operational adapter with a qualification, the same way T11's io adapters were done. **The 04:40Z pause is the natural switch point.**

### #4. The GRU multiplier is DDP, gated on #1

**(a) Files.** `imitation/t5/operations/gru_elastic_qualify*.py`, `gru_counter_dropout.py`.

**(b) Evidence.** A step takes 20–34 s against about 10 MB of gradients, so communication is negligible. Each rank builds its own history pieces, which also parallelises the CPU-bound phase.

**(c) Expected gain.** World 2–3: about 2–3× on top of #3. That brings an epoch to about 4–6 h instead of 18 h.

**(d) Effort.** Already in progress. The added work is the fused mask from #1 and a dropout-on throughput gate (about 2 h).

**(e) Correctness.** The equivalence bars are already defined in the amendments.

**(f) Frozen status.** Elastic qualification only; production has not switched.

### #5. Future temporal models: change the GRU sampling recipe (new path only), about 10–25×

**(a) Files.** A new variant next to `variants.py:GRUPolicy` and `history_indices`.

**(b) Evidence.** Every supervised endpoint re-encodes up to 32 history rows with gradient (checkpointed, so forward + replay + backward). Mean perspective length is 778 rows on C56 and 451 on v2, so most windows are full. That is about 31 extra trunk passes per supervised row.
- Within the frozen recipe nothing can be cached exactly. Weights change every step, and duplicate encodes in a step consume different dropout draws.
- With **contiguous-chunk sampling**, each batch is 8192/L chunks of L consecutive rows plus a 31-row burn-in, and every chunk row is supervised. The cost per supervised row drops from about 32 trunk passes to (L+31)/L. That is about 2 at L=32 and about 1.25 at L=128.
- Option: **detached history encodes** (no_grad, bf16). This saves about 2/3 of the history cost (about 3×), but changes the gradient.

**(c) Expected gain.** About 10–25× on temporal-model training wall time.

**(d) Effort.** About 6–10 h, plus a new preregistration.

**(e) Correctness.** Not equivalent to the frozen recipe: batches are correlated and shuffling differs. Mitigate by mixing ≥128 chunks per batch from distinct perspectives.

**(f) Frozen status.** New experiment only. The current GRU addendum must keep the frozen recipe.

### #6. `torch.compile` of the trunk and tile head for new runs, about 1.3–1.8× on the GPU step

**(a) Files.** `imitation/model/network.py`: `SetPolicy.encode`, `Block`, the tile head in `forward`.

**(b) Evidence.**
- One step is about 9–10 TFLOP, run in 0.7 s, which is about 14 TFLOPS (about 10% of A6000 bf16 peak).
- The work is dominated by memory-bound elementwise ops under autocast: fp32 LayerNorm outputs, dropout, residual adds, GELU, casts. There are also `typed` scatter tensors of about 1.6 GB per 7168 microbatch.
- Shapes come from 5 width buckets, so expect about 5–10 graphs. `tile_rows` is a dynamic dimension (mark it dynamic or pad to buckets).
- The GRU's numpy calls force graph breaks, so compile only `SetPolicy.encode` there.

**(c) Expected gain.** About 1.3–1.8× on the step-bound rate (11.6k to about 15–20k rows/s per A6000), once #2 removes the IO limit. It affects all new imitation training and dev or score inference.

**(d) Effort.** About 4–6 h, plus a T4-style numerical qualification (they already have bars: relative-L2 parameter update ≤0.05, etc.).

**(e) Correctness.** **Not bit-exact.** Fused rounding differs and Inductor uses a different dropout RNG stream. Only tolerance equivalence is possible.

**(f) Frozen status.** T4 code hashes are pinned by T5, T11 and gate-a. New runs only, behind a flag.

### #7. T11 seed21: resume on 127x04 with the io12 adapter, not loader6 (quick win)

**(a) Files.** The deferred plan `imitation/t11/receipts/home-resume-plan-2026100821-home04-2237.json` uses `loader_adapter_home2237.py` (6 workers). The io12 adapter `loader_io_home.py` already asserts host ∈ {127x01, 127x04} and was qualified bit-exact at 8, 10 and 12 workers.

**(b) Evidence.** Seed21 runs at 7.7k with loader6 on 16. Seed22 with io12 on 01 runs at 9.7–11.3k in windows.

**(c) Expected gain.** About +20–40% for seed21's remaining roughly 4 epochs, which is about 2–3 h less wall time.

**(d) Effort.** Under 1 h: an amendment, the io freeze path, and the command.

**(e) Correctness.** Bit-exact. It was already qualified, with CUDA replay of all sections.

**(f) Frozen status.** Needs only the existing operational-amendment pattern. Consider prefetch 2 instead of 4 if memory PSI on 04 is high: 48 in-flight batches is about 6 GB of shm, which competes with the page cache.

### #8. Host-side hygiene in `optimizer_step` (bit-exact, about 3–8%)

**(a) File.** `imitation/model/train.py:optimizer_step` (T4, frozen).

**(b) Evidence.**
- `bb[key][:, :width]` makes non-contiguous pinned slices, so `.to()` does a CPU `contiguous()` (single thread, because `set_num_threads(1)`) and a pageable, effectively synchronous copy of about 65–90 MB per step.
- `torch.nonzero(play)` on GPU forces a sync on every microbatch. `totals.cpu()` and `error_if_nonfinite` sync once more each.

**(c) Expected gain.**
- Transfer full-width tensors, then slice on the device.
- Compute `tile_rows` from CPU `y`, which gives identical indices, and transfer it.
- Prefetch the next microbatch's H2D on a side stream.
- Together, about 3–8% of the step-bound rate.

**(d) Effort.** About 2–3 h.

**(e) Correctness.** Bit-exact: the same kernels and the same inputs.

**(f) Frozen status.** Code pinned by the T4 hash, so it must go through an operational adapter with replay qualification. Batch it together with #2 rather than requalifying separately.

### #9. Dev pass

**(a) Files.** `imitation/model/runner.py:dev_joint_nll` (`batch_size=min(microbatch,1024)`, `workers=args.workers`=1). `loader_io_home.py` deliberately leaves dev at the original DataLoader.

**(b) Evidence.**
- The dev pass takes about 7 min per epoch on about 11.7M dev rows, which is about 5% of epoch wall time.
- The tile head is computed for every dev row, but `joint_nll_rows` needs it only for plays (about 4.6% of rows).
- T4 measured dev inference at 9.7k rows/s at batch 1024.

**(c) Expected gain.**
- Bit-exact: give dev 8 workers. The data order is identical, so this saves perhaps 1–3 min per epoch.
- New path: run the tile head only for supervised plays, and use a larger batch. Dev becomes about 2–3× faster.

**(d) Effort.** About 1 h for the bit-exact part; about 2 h for the new path.

**(e) Correctness.** Worker count: bit-exact. Batch size or tile-row restriction: about 1e-3 per-row bf16 differences (T4 `batched-dev-comparison.json`). That can flip near-tie best-dev selection.

**(f) Frozen status.** dev_joint_nll drives frozen selection and patience. Only the worker change is allowed for running seeds.

### #10. Store and checkpoint transport

**(a) Files.** `imitation/t11/copy_store.py` and `…/imitation/copy_leased_store.py` both use a single `rsync -cr --partial` stream over ssh, followed by a separate sha256 of every file.

**(b) Evidence.** The recorded copies ran at about 61 MB/s (86 GB in 1,417 s; other copies took 1,257–1,283 s). A single ssh/rsync stream is far below the measured 9.4 Gbit/s LAN.

**(c) Expected gain.** Use 8–16 parallel per-file rsync streams over LAN addresses, skip `-c` on fresh destinations, and run the sha256 checks in parallel. A 184 GB copy drops from about 50 min to about 4–6 min; with #2, about 2 min. This matters for every host move, DDP staging and lease.

**(d) Effort.** About 2 h.

**(e) Correctness.** Identical bytes; the final sha256 verification stays.

**(f) Frozen status.** Not frozen.

### #11. Evaluation and bootstrap

**(a) Files.** `imitation/model/evaluate.py` (`summary_cluster_cis`, `_cluster_ci`, `report_slices`), `runner.evaluate_checkpoint`, `t5/score.py`, `t11/score.py`.

**(b) Evidence.** Bootstrap is already vectorised: multinomial cluster weights @ per-cluster sums. Gate-4 totals were 1,217 s of scoring and 697 s of analysis, which is about 0.5% of training cost. The before and after stages redraw identical multinomials with the same seed and the same cluster count.

**(c) Expected gain.** Reuse the draws between stages, which halves analysis time (about 6 min saved per report set).

**(d) Effort.** About 1 h.

**(e) Correctness.** Bit-exact: the same PCG64 stream is reused.

**(f) Frozen status.** Sealed RESULTS-v1, and the GRU addendum must reproduce the identity and multiplicity hashes. Any change must reproduce the 10000×N weight-matrix hash exactly.

### #12. Data extraction and store build (low priority: one-off)

**(a) Files.** `replay_sidecars.py` (1 h 50 m wall, about 412k CPU-s, about 62 cores busy), P16 upgrade (3 h 08 m), `t11/build_store.py` (already ProcessPool with disjoint writers), `s122/extract_s122.py` (about 29k perspectives per hour per host), `finish_data.py`.

**(b) Evidence.** All of these are already parallel and have finished. No rebuild is scheduled.

**(c) Gain and plan.** If v3 data is built:
- Emit the compact encoding from #2 directly.
- Write a lean manifest that keeps per-perspective summaries in a side file, not in the 1 GB `manifest.json` that every training process parses.
- Shard the extraction across the fleet; it is embarrassingly parallel per unit.

**(d) Effort.** About 2–4 h when the next build happens.

**(e) Correctness.** Exact by construction.

**(f) Frozen status.** Do not touch v1/v2 artifacts.

### Considered and rejected or deprioritised

- **fp16/bf16 feature storage.** Not lossless: col0 is only 18.5% exact, col16 only 1.6%. Rejected for frozen runs; the dictionary or fixed-point encoding in #2 is lossless.
- **Sampler locality (block shuffling) for T11.** It would change the frozen iid order. For new runs it is unnecessary once #2 makes the store RAM-resident.
- **Window-sorted prefetch inside the frozen order.** At about 1.5% row density per 48-batch window, read amplification is no better than the current MADV_RANDOM.
- **CUDA graphs.** Variable widths and `tile_rows` sizes make them awkward. Use compile (#6) instead.
- **Gates (b)/(c) games.** Search decisions are deadline-bound at 200 ms by design (`smoke.play`, `deadline=start+.2`), and a game is about 750 decisions. The only legitimate speed-up is more concurrent games on uncontended cores, which the gate thread already manages. The policy's share inside the deadline belongs to the search/live audit.
- **`gc.freeze()` before forking loaders.** Loader private dirty memory is only 120–200 MB, so COW is not the problem today.

---

## 2. Quick wins (under 2 h each)

1. **Seed21 on 04 with the io12 adapter instead of loader6** (#7). Bit-exact, already qualified, about +20–40% for its remaining epochs.
2. **Benchmark the T11 and GRU DDP candidates with dropout ON** (p=0.1, world 1, 20 steps) before any rollout decision (#1). About 1 h, and it may prevent a multi-day regression.
3. **GRU: drop the per-piece `release_pages`** (release once per step) at the 04:40Z pause/resume (#3 partial). Bit-exact, about 8–10%.
4. **Give the dev pass 8 workers** for the running seeds (#9). Bit-exact, saves 1–3 min per epoch per seed.
5. **Parallel LAN rsync and parallel sha256 for store and checkpoint staging** (#10). About 10× faster copies.
6. **Add memory PSI** (`/proc/pressure/memory` full avg60) to status receipts. Throughput regressions on 01 track it, not IO MB/s.

---

## 3. Ten-line summary

1. T11 is step-bound at about 11.6k rows/s per A6000. It realises 7–9.7k because a 165 GB working set thrashes 125 GB of RAM (memory PSI full 30–55%; some steps stall at about 500 rows/s).
2. Top risk: both DDP candidates were qualified only at dropout 0. Their eager integer counter-dropout masks (103 int32 ops per call for T11; 144 int64 ops per 1M-element chunk for the GRU) should cost several seconds per T11 step, and far more per GRU step.
3. Fix: generate each mask in one fused kernel (Triton, or compile of the mask only). That keeps masks bit-exact and makes DDP close to linear, since the 9–10 MB per-step allreduce is about 2% of a step.
4. A lossless compact v2 store (fixed-point and dictionary columns, verified on the sample) cuts the read set from about 165 GB to 75–85 GB. Expect +20–60% for T11-type runs, faster resumes and copies, and DDP readiness. It is bit-exact checkable.
5. GRU: 34.5 s/step = 18.5 s CPU-bound forward (synchronous history build_batch plus 250 `release_pages` calls per step) + 15.5 s GPU-bound backward.
6. Building GRU history pieces in pinned loader workers is bit-exact and should take it from 237 to about 400 rows/s; DDP adds another 2–3×. The 04:40Z pause is the switch point.
7. Under the frozen GRU recipe, cached prefixes cannot be exact. Contiguous-chunk sampling for future temporal models would be about 10–25× cheaper (new preregistration).
8. torch.compile of the trunk and tile head should give about 1.3–1.8× on the GPU step for new runs only (not bit-exact; the T4 hash is pinned by T5/T11/gate-a).
9. Quick wins: seed21 with io12 on 04, a dropout-on DDP benchmark, dropping the GRU per-piece `release_pages`, 8 dev workers, parallel LAN rsync, and memory PSI in status receipts.
10. Evaluation (about 0.5% of cost) and data extraction (one-off, already parallel) are low priority. Only exact bootstrap-draw reuse is worth doing.
