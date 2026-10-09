# Perf audit synthesis: where Clasher's wall-clock goes, ranked

Written 2026-10-09 ~00:40Z on 127x05 from the five subsystem audits in `reports/perf-audit/`: engine, search, imitation, perception and ops. References like "engine #3" point into those reports. Nothing was changed.

**Current state:**
- Gates (b) and (c) were frozen and launched at 00:14Z: gate (b) on 03@16 (about 1.8–2.5 h), gate (c) on 02@16 (about 3–4 h).
- The T5 GRU pauses at 04:40Z.
- The leases end at 05:00Z; seed21 then moves from 16 to 04, and seed22 stays on 01.
- The L2-v4 PREREG is still a DRAFT, and T9/E4 have not run.
- The lockstep perception candidate (commit 8fed7b07) has not been admitted.

**Ranking:** expected wall-clock saved on current and upcoming work, divided by effort. A correctness blocker that would waste a whole pipeline counts as savings.

## 1. Top 15
"New path" means a new file, subclass, binary directory or flag, with an equality receipt; the pinned original is never edited. Speed-ups are measured unless marked "est." (estimated).

1. **Perception capture clock (BLOCKING)**
   - Owner: perception #1.
   - Files: `l1/shared_epoch_inference_v4.py`, `shared_epoch_inference_packed_v4.py`, `vectorized_capture_candidate_v4.py`. The bug is `service=(now-started[i])`. Downstream: `persisted_grid_decode_v4` → `validation_replay_v4` → `scoring_v4`.
   - Effect: lag of 38–52 s per match, so event recall at 500 ms collapses and the 24-epoch selection measures contention, not the model. The gates missed it because epoch 1 has 0 predictions.
   - Effort: 15 min to confirm; 2–3 h for per-branch clocks, plus an amendment and a re-gate.
   - Exactness: decoder records other than the clocks stay byte-equal; the new clocks must reproduce the single-branch replay lag.
   - Frozen: new driver and schema. The lockstep candidate must use the same clock attribution.
2. **Exploration GPU guard**
   - Owner: ops #1 / engine #1 / search #9.
   - Files: `loss_review/delay_runtime.py::GPUWatch` (used by `delay_simulate.py --gpu-guard`); `search-ab/gpu_guard.py`, `home_worker.py`, `lease_worker.py`.
   - Speed-up: 1.75× fleet-wide, about 3× on 08/09/16, and from zero to full on 11. Shard p0125 on 08 took 1,082 s against 398–457 s for identical shards elsewhere. The GRU ran at 234.7 rows/s with sims paused vs a 237.1 median.
   - Effort: 1.5–2 h plus a 30-min A/B.
   - Fix: run sims at idle priority (`chrt --idle`), pinned away from the GPU job's cores and SMT siblings; throttle only if the GPU job's own rows/s drops more than 5%; add an idle-GPU exemption.
   - Exactness: per-game `actions` and `winner` identical with and without pauses.
   - Frozen: none, but the coordinator must agree to redefine the "≥80% util" rule. The A/B also settles the "08 GRU starved by sims" claim.
3. **GRU history build off the trainer thread**
   - Owner: imitation #3.
   - Files: `imitation/t5/variants.py:GRUPolicy.encode`, `t5/resources.py:release_pages`.
   - Stage A, at the 04:40Z pause: release pages once per step instead of per piece, about 8–10% (est.).
   - Stage B: loader workers build the same history pieces and hand them over pinned: 34.5 → about 21 s/step, 237 → about 400 rows/s (est.).
   - Effort: under 1 h for stage A; 4–6 h plus 2 h of qualification for stage B.
   - Exactness: bit-exact, checked by CPU and CUDA replay of all sections.
   - Frozen: operational adapter with a qualification receipt.
4. **DDP dropout-on gap**
   - Owner: imitation #1/#4.
   - Files: `t11/ddp/counter_dropout.py`, `t5/operations/gru_counter_dropout.py`, `t11/ddp/engine.py`.
   - Problem: the T11 mask is 103 integer ops and the GRU's 144 int64 ops per chunk; est. +3–4 s per T11 step against 0.7 s, far worse for the GRU.
   - Effort: 1 h for a p=0.1 benchmark; 4–6 h for a fused mask (Triton, or compiling only the mask generator).
   - Exactness: `torch.equal` on masks across all 17 sites; keep the `x*keep/(1-p)` step eager.
   - Frozen: candidates are qualification-only; add a dropout-on throughput gate before switching.
5. **Live scorer Python fixes**
   - Owner: search #1 / engine #3.
   - Files: `stage5/fair_player.py::Resources.root` (re-serializes the 1.49 MB config per root); `src/clasher/live/decision.py::RustPlanner.score` (recomputes the opponent's first moves per candidate).
   - Speed-up: 15 → 5.5 ms per root, −36 to −55 ms per decision, and 240 fewer GIL-held calls (about 20 ms).
   - Effort: 1 h.
   - Exactness: payloads byte-identical (36/36 so far, check ≥1,000); per-candidate scores equal.
   - Frozen: subclass only; adopt before the PREREG freezes.
6. **Release the GIL in native per-call methods**
   - Owner: engine #2 / search #1.
   - Files: `engine-rs/src/lib.rs` `step`/`apply_action`; `scripts.rs` `select_action`/`apply_discrete`/`evaluate`/`rollout`/`rollout_commands`, wrapped in `py.allow_threads` like `scripts.rs:645`.
   - Speed-up: today 0.5× and 1 of 20 candidates; est. 4–7.6× throughput and 15–20 of 20 after.
   - Effort: 1–2 h plus parity tests and a Mac rebuild.
   - Exactness: identical digests and scores with no deadline.
   - Frozen: new binary directory, never an in-place `.so`; needs a PREREG amendment or inclusion. Fallback if the Mac rebuild slips: score candidates one at a time on one thread (measured 2.7 of 20).
7. **x86-64-v3 build**
   - Owner: search #2.
   - Files: `engine-rs/build.sh` (`RUSTFLAGS`).
   - Speed-up: 1.25× rollouts (5.37 → 4.29 ms).
   - Effort: 0.5 h plus the 200-root exact replay.
   - Exactness: digests identical on 171 rollouts.
   - Frozen: separate binary directory (`CLASHER_DELAY_NATIVE_DIR`), new runs only, never on the Mac.
8. **T11 seed21 at the 05:00Z move to 04**
   - Owner: imitation #7.
   - Files: use `t11/loader_io_home.py` (io12, qualified for 01 and 04) instead of `loader_adapter_home2237.py`.
   - Speed-up: est. +20–40%, about 2–3 h saved.
   - Effort: under 1 h; use prefetch 2 if memory pressure on 04 is high.
   - Exactness: already qualified, including CUDA replay.
9. **`Resources()` startup**
   - Owner: engine #4.
   - Files: `battle.py:346` tower-data loader (re-parses 3.1 MB `gamedata.json` 404 times); `native_tilemap.py:103 nearest_native_path_id`.
   - Speed-up: 24 → 10 s with caching, 1 s with an on-disk cache keyed on all source, gamedata and `.so` hashes.
   - Effort: 1 h (2–3 h for the disk cache).
   - Exactness: config and template digests unchanged; parity suite passes.
   - Frozen: gates use their own copied snapshot, so they are unaffected; prefer a subclass.
10. **Live P1 `DecoderAdapter`**
    - Owner: perception #3.
    - Files: `src/clasher/live/perception.py:V4Perception`, `vectorized_runtime_adapter_v4.DecoderAdapter`.
    - Speed-up: −22 ms per frame (CUDA analog), likely more on MPS.
    - Effort: 1.5–2 h.
    - Exactness: record equality on MPS with train recordings.
    - Frozen: must land before T9/E4; `l1_v4.py` untouched.
11. **Exploration shard shape**
    - Owner: ops #5 / #2 / engine #8.
    - Files: `delay_simulate.py`/`simulate.py` `main` (FIFO `pool.map`); `launch_shards.py::lane` (`if process.returncode: return` retires a host for good).
    - Change: 100-pair shards, longest games first, requeue failed shards and retire a host after 3 failures.
    - Speed-up: 1.15–1.2× on top of item 2.
    - Effort: about 1.5 h.
    - Exactness: per-game `actions` SHA unchanged.
12. **Store staging**
    - Owner: ops #3 / imitation #10.
    - Files: `t11/copy_store.py`, `copy_leased_store.py`, `prestage_home.py`, `fleet/fanout.sh`.
    - Speed-up: a 244 GB copy goes from 36 min (111 MB/s) to about 6–8 min.
    - Effort: 2–3 h for a new `copy_store_v2.py`: no `-c` on fresh copies, 4–8 size-balanced LAN streams, hashing overlapped with transfer, tree fan-out.
    - Exactness: the per-file SHA-256 check is unchanged.
13. **Live P4 HUD reader in v4 mode**
    - Owner: perception #4.
    - Files: `runtime.py:p4` (`hud_reader` exists only for v3).
    - Problem: the HUD arrives at ≥61 ms age vs the 60 ms bound, so taps wait or expire, hurting E4's ≥90% first-attempt acceptance.
    - Effort: 3–4 h for a 2.1 ms CPU reader.
    - Exactness: CPU-vs-MPS HUD agreement on train recordings.
    - Frozen: must land before the P4 verifier re-test; do not relax the 60 ms bound instead.
14. **Validation capture: shared work hoist and tail dedupe**
    - Owner: perception #2, overlapping the lockstep candidate.
    - Change: stop repeating `prepare_pixels`, H2D, the HUD block (about 56 syncs), ring stacks and equality syncs in each of the 9 branches.
    - Speed-up: est. 1.8–2.5× (lockstep CPU measured 1.83–1.93× exact); about 5 h → 2.5 h of remaining capture.
    - Effort: 4–6 h.
    - Exactness: byte-identical decoder records; batch size stays 1, since batching at 2 or more changes bits (amendment 08 and the GPU01 probe).
    - Sequencing: after item 1; coordinate with the lockstep owner.
15. **C56 script early exit and mask hoist**
    - Owner: search #4 / engine #5.
    - Files: `c56_scripts.rs::c56_ranked`; `scripts.rs:93-131 occupied()`; `scripts.rs:250-360 mask()`.
    - Speed-up: est. 1.1–1.2×; in 61% of calls nothing is affordable. Less on top of item 7.
    - Effort: 2–3 h.
    - Exactness: trace digests, plus `public_mask` equality on ≥100k roots.
    - Frozen: new binary directory.

## 2. Quick wins (under 2 h each)
| # | What | Owner | Effort | Gain | When |
|---|---|---|---|---|---|
| Q1 | Confirm the clock lag (item 1) | perception | 15 min | Saves the whole selection grid | Now |
| Q2 | Pass the selected body threshold to `V4Perception` (today it defaults to 0.5); a correctness fix | perception | 15 min | Live matches the sealed selection | Before T9 |
| Q3 | Dropout-on DDP benchmark (item 4) | imitation | 1 h | Prevents a multi-day regression | Before any DDP decision |
| Q4 | GPU guard fix (item 2) | ops | 1.5–2 h | 1.75× exploration | Now; keep 02 and 03 untouched |
| Q5 | Shard shape and lane retry (item 11) | ops | 1–1.5 h | 1.15–1.2× | With Q4 |
| Q6 | x86-64-v3 build (item 7) | engine | 0.5 h | 1.25× rollouts | New runs |
| Q7 | Config reuse and opponent-move hoist (item 5) | search | 1 h | −36 to −55 ms per decision | Before PREREG freeze |
| Q8 | GIL release (item 6) | engine | 1–2 h | est. 15–20 of 20 candidates | Before PREREG freeze |
| Q9 | GRU page release once per step (item 3, stage A) | imitation | <1 h | 8–10% | 04:40Z |
| Q10 | Seed21 with io12 (item 8) | imitation | <1 h | +20–40% | 05:00Z |
| Q11 | `lru_cache` in `Resources()` (item 9) | engine | 1 h | 24 → 10 s | Next launch |
| Q12 | `DecoderAdapter` (item 10) | perception | 1.5–2 h | −22 ms per frame | Before T9/E4 |
| Q13 | Blocking queue reads instead of 2–3 ms polls in `runtime.py` (perception #7) | perception | 1–2 h | −4 to −5 ms p50 | Before T9/E4 |
| Q14 | `PYTHONPYCACHEPREFIX` plus `compileall` (ops #6) | ops | <1 h | Startup 3.3 → 1.6 s | Exploration now; gates only with sign-off |
| Q15 | 8 dev-pass workers and memory pressure in status receipts | imitation | 1 h | 1–3 min per epoch | Next resume |
| Q16 | Packet cache per tick and seat in `simulate` | engine | 0.5 h | −2% | Optional |

## 3. Structural changes and sequencing
- **S1. Fleet pull queue** (ops #2; 6–10 h; 2–3× experiment throughput).
  - The fleet sat at about 16% CPU, with idle GPUs on 13 and 01.
  - Design: queue directories on hub 127x01; hosts claim jobs by atomic `mv`; run each job through the existing wrappers.
  - The agent must refuse hosts outside clasher's own (01–04/07/08) or the lease file, and must check `who` and load.
  - Do not route frozen gate or T11 runs through it.
  - Build after Q4/Q5 and after 05:00Z; fold in the persistent per-host sim pool and the lease_watch_v2 cleanup.
- **S2. DDP for T11 and the GRU**
  1. Q3 benchmark.
  2. Fused masks (4–6 h).
  3. Dropout-on throughput gate (2 h).
  4. GRU DDP on top of item 3 stage B: est. 18 h → 4–6 h per epoch.
  - T11 DDP needs S3 first.
- **S3. Compact lossless v2 store** (imitation #2; 8–10 h).
  - 165 → 75–85 GB, below RAM; +20–60% on T11-type runs; 2.3× faster copies.
  - Also: a lazy manifest instead of the 988 MB JSON every loader inherits, and `row_ids` as a column.
  - Exactness: full-column uint32-view equality, batch equality, checkpoint replay.
  - New store path; mostly for the GRU-on-v2, T12 and DAgger. Bundle the `optimizer_step` cleanup (3–8%) into the same qualification.
- **S4. Native search sharing**
  - Order: split rollouts only where the 3 opponent styles diverge (6–8 h, est. 1.4–1.6×), then share the 27-tick delay trunk (3–4 h, 1.15×), then fix allocator churn (1–6 h, 1.1–1.3×).
  - Combined with items 7 and 15: est. 2–2.5× on rollouts (the gains overlap).
  - New methods only (e.g. `search_candidates_shared`); leave `search_candidates` and `rollout` as they are.
- **S5. Seed inventory v2** (4–6 h): faster regex, size-balanced sharding, resumable checkpoints and a persistent index, so re-audits take minutes. New gates only.
- **S6. Perception export**
  - Latest-query temporal head (101 → 23 ms on CPU; not bit-exact, so only in the CoreML export with decision-level parity).
  - Overlap the temporal prefix with the tracker (1–5 ms).
  - Items 10, 13 and Q13 are prerequisites for 2 renderers, which would cut L2-v4 from 29 h to 14.5 h.
- **S7. New-run-only:** `torch.compile` (1.3–1.8×, tolerance-qualified) and contiguous-chunk sampling for future temporal models (10–25×, new preregistration). Both need S3 first.
- **Sequence:**
  1. Now: Q1, Q2, Q4–Q8. Leave 02 and 03 alone until the gates finish (b about 02:15–02:45Z, c about 03:15–04:15Z).
  2. 04:40Z: Q9.
  3. 05:00Z: Q10; then item 14 once item 1 lands.
  4. Then S2 steps 1–3 alongside S1; then S3, stage B with GRU DDP, and S4.
  5. Before the next gate: S5. Before T9/E4: items 10 and 13 and Q13.

## 4. What not to do
**Low value:**
- torch_sim or GPU rollouts: about 2,000× behind Rust per core, and not exact.
- Python-engine micro-fixes (about 2%). Cython and a native packet builder only if the outer game becomes the bottleneck.
- Transposition caching (roots never repeat) or a learned leaf value presented as a speed fix.
- Changing `run_gate` for `verify` or sharding: under 0.5%.
- Perception T7 training speed: saves under 10 min.
- Imitation: `gc.freeze`, window-sorted prefetch, CUDA graphs, frozen-run sampler locality, extraction reruns, bootstrap work beyond reusing identical draws.
- `lease_watch_v2` or `hub_mirror` changes before 05:00Z.

**High risk:**
- Touching anything the running gates depend on: pinned code, the `.so`, concurrency, bytecode settings. Never co-schedule on 03 or 02 during their windows.
- Replacing `clasher_core.abi3.so` in place.
- Copying the v3 binary to a non-v3 machine.
- Editing sealed files: `fair_player.py`, `delay.py`, `c56_rollout_planner.py`, `l1_v4.py`, the capture and grid sources, the T4 trainer, `copy_store.py`.
- Claiming batched perception is exact.
- fp16 on the reference path, CPU captures, a CUDA MPS daemon, more capture processes per GPU, or 540×1140 emulator frames.
- fp16/bf16 feature storage.
- Changing dev batch size or using `torch.compile` in frozen seeds.
- Relaxing the 60 ms HUD bound.
- Regenerating gate (b)/(c) audit receipts.
- More GPU experiments on 01: the lockstep probe cut T11 to 51%.

## 5. Correctness flags
1. The capture clock bug (item 1).
2. The body-threshold default in `V4Perception` (Q2).
3. In 67% of the Mac suite's active searches every candidate scored −2.0, and a phantom princess Tower appeared at the KingTower position. The owner should check this before the L2-v4 PREREG freezes.
4. `GPUWatch` has no idle-GPU exemption, and `lease_worker` kills paused shards at 840 s.
5. `latency_seconds` includes paused time.
6. `simulate --decision-budget` deadlines would cut searches short while a shard is paused (latent).
7. The coordinator's "GRU starved by sims" diagnosis conflicts with the measured evidence.