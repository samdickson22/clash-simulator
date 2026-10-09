# Perf audit: fleet/ops tooling and experiment harnesses

Audited 2026-10-08, from about 23:30Z to 00:05Z (UTC), from 127x05. I changed no code, committed nothing, killed nothing and touched no tailscale, crontab or roader paths.

**Scope:** `reports/strategy_council_20260928/fleet/` (fleet_run.sh, fanout.sh, hub_mirror.sh, lease v1 and v2), `imitation/evaluation/` (run_gate, run_p16, register, seed_audit, smoke, p16_adapter), `imitation/gates-bc/operations/` (seed_inventory, parallel_inventory, run_host, pilot.sh), `src/clasher/analysis/loss_review/` (simulate, delay_simulate, delay_runtime, reduce_traces), the `reports/explore/{search-ab,delay-fixes}` launchers and guards, and T11 staging and backup (copy_store.py, backup_checkpoints_home2237.py).

**Method and disclosures:**
- Measurements were light and read-only, mostly on 127x08 at nice 19 with one process. Its T5 GRU job was never touched.
- On other hosts I only read small receipts and logs and ran `uptime`, `nvidia-smi` and `ps`.
- **Deviation 1:** my first import-timing run on 08 wrote 1,010 `.pyc` files into 08's `.venv` and `src/`. I deleted exactly the files newer than the run and the empty `__pycache__` dirs they created. The 90 older `.pyc` files are untouched, and the later timings used a scratch `PYTHONPYCACHEPREFIX` that I have since removed.
- **Deviation 2:** I ran one `/proc` scan of about 1.5 s at nice 19 on 127x15 (lease host). That is outside the "profile only on 08" allowance. It was a single read-only pass.

---

## 0. Where the wall-clock actually goes (context for the ranking)

| Pipeline | Size | Measured unit cost | Estimated wall |
|---|---|---|---|
| Gate (b) | 1,152 games: 640 h2h (B, 2 seats) plus 512 scripts (A and B, 2 seats) | h2h about 83 s per game per worker (pilot 03-r11: 32 games, 16 workers, 167 s); scripts about 38 s (03-r1: 77 s for 2 games per worker, 29 CPU-s per game) | about 72,600 slot-s: **76 min at 03@16 alone, 38 min at 32 slots** |
| Gate (c) | 1,792 games: 576 P16 2-game jobs, 128 h2h 2-game jobs, 384 C56 | P16 about 15 s per game (cqual-03-r5: 4 games in 60.6 s); startup of the 2 processes per job about 6–7 s | about 33,000 slot-s: **about 9 min at 64 slots** |
| Gates (b)/(c) seed audits | 5 home hosts plus 3 leases | single-process scans ran about 74 min and were killed; parallel r4 took 10–55 min per host | **about 2 h on the gate-prep critical path** (20:55 to 22:57Z) |
| Exploration sims (delay-fixes, search-ab) | delay-fixes 1,000–1,250 pairs × 8 arms; search-ab similar | about 38–44 wall-s per game when unpaused (25-pair shard of 200 games in 398–457 s at 22 workers) | hours. Dominated by **pauses and idle hosts**, not by per-game cost |
| T11/T5 host staging | 244 GB v2 store per host | 2,191 s per host, about 111 MB/s effective | 36 min per host bring-up or host-loss recovery |

The CPU snapshot at about 23:50Z covered 11 reachable hosts; 07 was unreachable and 06 is not in the pool.
- **CPU:** load1 summed to about 220 of 1,408 threads (about 16%). 03 was at 1.3, 02 at 5, 11 at 5 and 16 at 7.6.
- **GPUs:** 01 was mostly idle (loader I/O probe, 0–32%), 13 was at 0%, 03's driver is broken, and 08 ran at a 25–40% duty cycle.

The ranking below follows that picture.

- **Gates are small compute jobs.** Their wall-clock is set by process (qualification and review), not by CPU.
- **Exploration sims and staging are where ops tooling wastes real hours.**

---

## Ranked opportunities

### 1. GPU guard SIGSTOPs exploration workers about 43% of the time, with no measurable benefit (QUICK WIN)

**(a) Files**
- `src/clasher/analysis/loss_review/delay_runtime.py::GPUWatch.watch` (used by `delay_simulate.py --gpu-guard`, which `reports/explore/delay-fixes/launch_shards.py` always passes).
- `reports/explore/search-ab/gpu_guard.py`, `home_worker.py` and `lease_worker.py`.
- Rule: on any instantaneous `nvidia-smi` utilization sample below 80, SIGSTOP all workers; SIGCONT only after 3 (delay) or 5 (search-ab) consecutive samples of 80 or more, sampled every 2 s.

**(b) Evidence, measured from the guards' own logs**

Pause fractions from all `gpu*.jsonl` guard logs, as fraction of samples paused:

| Host | Paused fraction | Notes |
|---|---|---|
| 127x11 | **100%** | 623 samples. The GPU job (v4 packed inference, 3 CPU-bound processes) sits at a steady 75–79%, so the workers never resume. |
| 127x16 | 69% | |
| 127x09 | 63% | |
| 127x04 | 43% | |
| 127x08 | 41% | |
| 127x14 | 26% | |
| 127x15 | 24% | |
| 127x13 | 12% | |
| **Total** | **4,428 of 10,208 samples (43%)** | |

On 08, the delay-fixes shard p0125 (26 workers, 200 games) took **1,082 s**. Identical 200-game shards took 398 s on 13 and 443–457 s on 15. Mean game wall was 123 s against 38–44 s elsewhere.

The pauses buy nothing on 08:
- The T5 GRU trainer alternates about 14 s at 100% GPU with about 20 s at 25–30% within each 36-s step. Its main Python thread is pegged at 100% CPU.
- The low phase stays at 25–30% **while all 26 workers are stopped**, so the trainer itself is the bottleneck.
- Trainer throughput during steps with workers ≥80% paused was 234.7 rows/s. The overall median is 237.1 rows/s (p10 218, p90 244). There was no measurable gain from pausing.
- With about 100 idle hardware threads, the only plausible interference path is SMT sibling sharing. Pinning prevents that without pausing.

**Secondary defects**
- `GPUWatch` has no idle-GPU exemption (home_worker's `memory.used>1024` test). If a host's GPU job ends, utilization reads 0 and workers stay paused until the 04:29Z cutoff.
- `lease_worker.py` hard-kills shards at 840 s. On 100%-paused hosts this produces zero progress, then SIGTERM, and in-flight games are discarded.
- Wall-time `latency_seconds` telemetry in `delay_simulate` and `simulate` includes stopped time; `cpu_latency_seconds` is fine.
- `simulate.py --decision-budget` uses `perf_counter` deadlines. Under a SIGSTOP, a decision in progress would hit its deadline at once and truncate the search. No budget run was found under a guard on any host, so this is latent.

**Fix**
- Run sim workers under `chrt --idle 0` (SCHED_IDLE) and `taskset` them away from the GPU job's cores and SMT siblings. SCHED_IDLE work cannot preempt the feeder thread.
- Replace the absolute "≥80% util" rule with a *relative* guard: compare the GPU job's own progress metric (train.jsonl rows/s, or a 60-s mean utilization) with sims running against a baseline with sims paused, and throttle only on a drop of more than 5%.
- Keep the memory/idle exemption.

**(c) Expected gain**
- Exploration sim throughput about **1.75× fleet-wide** (1/(1−0.43)).
- About 3× on 08/09/16, and from zero to full on 11.
- This directly shortens delay-fixes and search-ab, the simulator search experiments.

**(d) Effort:** about 1.5–2 h (shared guard module plus a launch-flag change), plus a 30-min A/B on one GPU host.

**(e) Risk**
- Exploration game outcomes are unaffected for fixed-rollout arms, because pausing never changes RNG or rollout counts.
- An exact check is possible: rerun one paused shard unpaused and compare `actions` and `winner` per game bit-for-bit (`--resume` already validates seeds).
- The only risk is to GPU co-tenants. The A/B above measures it.

**(f) Frozen dependency:** none. Exploration only, no prereg. The "≥80%" wording is a coordinator or fleet-policy promise, so get the coordinator's OK to redefine it as "≥X% of the GPU job's own baseline throughput".

### 2. Fleet pull-queue for idle CPU/GPU, plus lane robustness (largest structural win)

**(a) Today's launchers**
- Every experiment has its own launcher: `reports/explore/delay-fixes/launch_shards.py` (already a per-lane pop queue), `search-ab/lease_launch.py`, `gates-bc/operations/launch_*.py`, `fleet/fanout.sh` and `run_host.py`.
- Hosts are allocated by hand in coordinator threads.
- `launch_shards.py::lane` does `if process.returncode: return`. One wrapper failure permanently retires that host's lane: 16 lost its lane on p0125 after the v2 aggregate-key bug and needed a manual `continue16.py`.

**(b) Evidence**
- Snapshot: about 16% of fleet CPU threads busy, while the per-host policy allows 80–96 Clasher processes. GPUs on 13 (0%) and 01 (mostly idle) are free.
- Gate host 03 sat at load 1.3 because gates are held for review.
- The between-experiment gaps in PROGRESS files are typically 10–40 min per host, waiting on a coordinator message.

**Proposed MVP ("pull, never push")**
- A queue directory on the hub: `/mpac/sdicks02/jobs/clasher/queue/{pending,claimed,done,failed}/`. Each task is a JSON file holding argv, resource class (`cpu:N`, `gpu:MiB`), allowed hosts, label, `deadline_utc`, `max_attempts` and an idempotent resume flag.
- Each host runs one small agent under `fleet_run.sh` (home) or `run_v2.sh` (lease). Every 30 s it:
  1. Checks local capacity: console users, load, free cores, GPU free memory, lease validity and the project host split (01–04/07/08 home; leased hosts per lease file).
  2. Claims a task by atomic `mv pending/X claimed/HOST-X` on the hub over one multiplexed SSH connection. `rename` is atomic on one filesystem, so no lock server is needed.
  3. Runs the task *through the existing wrapper*, so all supervision, PSS caps and deadlines remain authoritative.
  4. Writes the exit receipt and moves the task to `done` or `failed`. Failed tasks requeue with backoff until `max_attempts`.
- Tasks stay the existing idempotent shard commands; delay_simulate and simulate already resume from per-game files.

**(c) Expected gain**
- For embarrassingly parallel backlogs (exploration sims, self-play or search sweeps, seed scans, reductions), raising average utilization from about 16–30% to about 60% of the policy cap is **2–3× more experiment throughput** at zero hardware cost.
- It also removes 10–40 min human-latency gaps per host per experiment.
- For gates (b)/(c) and frozen T11 runs the value is small. Those are allocation-constrained by design and should keep their dedicated registered launch paths.

**(d) Effort:** 6–10 h for the MVP agent plus enqueue CLI and a dry-run mode. The lane-retry quick fix in `launch_shards.py` (requeue the shard, retire the host after 3 failures) takes **under 1 h**.

**(e) Risk**
- Correctness risk is low: tasks are the same commands with the same receipts, and duplicate execution is prevented by atomic rename plus the existing label locks.
- Operational risk is moderate: the agent must enforce the host split and lease expiry. Mitigate by making the agent refuse any host not listed in the lease or ownership files, and by running it under the wrappers.

**(f) Frozen dependency:** none. Never route frozen gate or T11 registrations through it until separately qualified.

### 3. Large-store staging is 10× below LAN speed

**(a) Files:** `imitation/t11/copy_store.py::sync_files` and `main` (`rsync -cr` from 127x01, then a serial Python `sha()` over every file). The same pattern appears in `prestage_home.py`, `fleet/fanout.sh` (rsync then `rsync -acni` verify pass) and the checkpoint pullers.

**(b) Evidence**
- `copy-receipt.json` on 16: 243,896,560,373 bytes in **2,191 s, about 111 MB/s**. The LAN measures 9.4 Gbit/s, about 1,175 MB/s.
- PROGRESS-T11 records the sender running a full source `-c` checksum pass before any payload moved, with two receivers pulling from the hub at once.
- Python SHA then re-reads all 244 GB serially: SHA-256 runs at 1.95 GB/s per core on 08 (sha_ni), but the reads come from NVMe because the store is larger than RAM.
- In total, three full passes plus one single-stream SSH transfer.

**Fix**
- On a fresh destination, drop `-c`; size+mtime is enough because the SHA pass follows anyway. Use `-c` only to repair files whose SHA mismatched.
- Split the explicit file list into 4–8 size-balanced groups with one rsync each, so several SSH streams can saturate 10 GbE.
- Hash each file in a thread pool as soon as its group finishes, overlapping hashing with transfer.
- For several receivers, fan out as a tree (hub to A, then hub and A to B and C) instead of N pulls from the hub.

**(c) Expected gain:** about 36 min to **about 6–8 min per host**, roughly 4–5×. This is on the critical path of every T11/T5 GPU-host bring-up and host-loss recovery; two host losses (02, 07) happened today.

**(d) Effort:** about 2–3 h for a new `copy_store_v2.py`.

**(e) Risk:** none to data integrity. The per-file SHA-256 manifest check is unchanged and exact.

**(f) Frozen dependency:** copy_store.py is cited by T11 receipts, so ship the change as a **new path**. Receipts already record hashes, not the copy method.

### 4. Seed-inventory scans: about 2 h of gate-prep critical path, mostly avoidable

**(a) Files:** `imitation/gates-bc/operations/seed_inventory.py::main` (per-line Python loop running 3 regexes plus `decode` and a `replace('_','')` copy per line), `parallel_inventory.py` (path-hash sharding) and `imitation/evaluation/seed_audit.py::scan` (whole-file `rglob`, no cache).

**(b) Evidence, from receipts in `gates-bc/receipts/parallel-r4/*`**
- Single-process scans on 5 hosts ran from about 20:55 to 22:02Z. Each had accumulated 4,400–4,545 CPU-s when it was killed; there was no completed-file checkpoint, so **about 6.2 CPU-h were discarded**.
- The parallel restart took 10 min on 03 and 16 min on 04 (31 shards each), 30 min on 08 and 40 min on 01 (7 shards each), and 55 min on 02 (31 shards, slow clocks).
- The team's own benchmark (`audit-regex-benchmark-r3.log`) showed an equivalent optimized regex path running **3.3× faster** (1.399 s to 0.428 s on a 74 MB trace). It was not adopted, to avoid restarting audits.
- Path-hash sharding ignores file size, so a few large `.jsonl.gz` traces set each host's tail.

**Fix: new versioned scanner `seed_inventory_v2`**
- Use the r3 regex path.
- Use LPT sharding: sort files by size, largest first, and assign each greedily to the least-loaded shard.
- Append per-file results to a JSONL checkpoint so an interrupted scan resumes.
- **Most valuable:** keep a persistent per-host index keyed by `(st_dev, st_ino, size, mtime_ns)`. For each file it stores the sha256 plus the sorted unique set of all ≥5-digit integer literals, seed fields and formula lines. A future audit against any new proposed seed set (gate d/e, new namespaces) then becomes an intersection that takes seconds per host, plus a scan of changed files only.

**(c) Expected gain:** the first full scan runs about 3–5× faster (regex plus LPT). Re-audits drop from about 1–2 h to minutes. This shortens prep for every future registered gate.

**(d) Effort:** about 4–6 h, including an equivalence run.

**(e) Risk:** moderate, because this is audit evidence. Exact check: run v1 and v2 over the same roots and require identical `overlap`, `formula_files`, `seed_fields`, `filename_seeds` and per-file sha256 maps. The existing r3 benchmark already covers the regex boundary cases.

**(f) Frozen dependency:** gates (b)/(c) audit receipts were produced with v1. **Do not regenerate them.** Use v2 for new gates only, disclosed in their prereg.

### 5. Exploration shard overhead: about 15–20% per shard from startup and tail (QUICK WIN)

**(a) Files:** `loss_review/delay_simulate.py::main` and `simulate.py::main` (one ProcessPool per shard, FIFO case order), `delay-fixes/launch_shards.py` and `search-ab/lease_launch.py` (25-pair shards; ssh, admission and rsync between shards).

**(b) Evidence:** I replayed per-game wall times from the shard receipts through 22-worker FIFO and LPT schedules.

| Shard | Receipt wall | FIFO model | LPT model | Ideal (sum/22) |
|---|---|---|---|---|
| p0050 (13) | 398 s | 369 s | 357 s | 343 s |
| p0100 (15) | 457 s | 425 s | 410 s | 398 s |
| p0175 (15) | 443 s | 413 s | 377 s | 364 s |

- About 30 s per shard is startup: `initialize()`, fork, checkpoint, `-B` imports.
- 26–50 s per shard is tail (games run up to 95–129 s against a mean of 38–44 s).
- Lane overhead between shards (ssh, lease admission, rsync back) comes on top.

**Fix**
- Quick: use 100-pair shards, which cuts startup and tail to about 4–5% of a shard (`--resume` keeps restart granularity per game), and submit cases longest-arm-first.
- Fuller: one persistent per-host pool that pulls cases across shards. This fits naturally into #2.

**(c) Expected gain:** about 1.15–1.2× on exploration sim wall-clock, on top of #1.

**(d) Effort:** 0.5 h for the shard size plus an LPT `sorted(pending, key=arm_cost)`; about 3 h for a persistent pool.

**(e) Risk:** none to results. Games are seeded per case, and order does not change outcomes. Exact check: compare per-game `actions` sha against the existing shards.

**(f) Frozen dependency:** none (exploration).

### 6. Every Python process recompiles all source (`-B` / `PYTHONDONTWRITEBYTECODE=1` everywhere) (QUICK WIN, small)

**(a) Files:** `fleet/fleet_run.sh`, `fleet/lease/env.sh`, `run_p16.py` (spawns `-B` adapters), `run_gate.py`, `run_host.py`, `pilot.sh`, and all launchers.

**(b) Evidence, measured on 08 at nice 19:**

| Startup | With `-B` (current) | With a warm bytecode cache via `PYTHONPYCACHEPREFIX` |
|---|---|---|
| `import torch, clasher.rl.eval, selfplay_env, contract_v5` | 3.3 s | **1.63 s** |
| Full P16-adapter-like startup (torch, imports, load_policy, s2902 checkpoint, ContractV5 builder) | 3.65–3.76 s | 2.2–2.5 s |

`-B` only suppresses *writing*. With `PYTHONPYCACHEPREFIX=/mpac/sdicks02/cache/pyc/<snapshot>` and a one-time `python -m compileall` into that prefix, `-B` processes still *read* the cache. Source trees stay byte-identical with no `__pycache__` beside pinned files, which is why `-B` was adopted.

**(c) Expected gain:**
- Gate (c) spawns about 1,400 processes (704 jobs × 2), saving about 2,000 slot-s (about 6% of gate c, or 0.5–3 min wall).
- Exploration saves about 2 s per shard and per helper.
- Small, but nearly free.

**(d) Effort:** under 1 h.

**(e) Risk:** very low. Bytecode is a deterministic compile of the same source, and the source hashes are unchanged.

**(f) Frozen dependency:** gates (b)/(c) qualification receipts record the environment. Apply to exploration and ops now; for gates, add it only if the coordinator agrees *before* freeze. Never mid-gate.

### 7. Gate (b)/(c) execution: leave the code alone, add slots and isolation

**(a) Files:** `imitation/evaluation/run_gate.py::main` (static `i % workers` sharding, `verify(manifest)` before every game or job, `may_start` with a host-global load1 ceiling of 20), `run_p16.py` (one 2-game subprocess per pair), `gates-bc/operations/run_host.py` (gate b at ≤16 workers per host with 3-core tasksets on cores 0–47).

**(b) Evidence and skepticism**
- `verify(manifest)` hashes about 120 MB of pinned files (runtime-bc-v1 is 79 MB, inputs 36 MB). At 1.95 GB/s that is about 0.1 s per game, **under 0.5% overhead. Not worth touching.**
- The startup overhead in run_p16 is about 15% of gate (c), but gate (c) is only about 9 min at 64 slots.
- Static sharding across hosts with very different clocks (02 at about 1.48 GHz, 07 at 0.55 GHz, 04 at 3.6 GHz, from PROGRESS) means the slowest host sets wall time. Dynamic O_EXCL claim files would fix that, but run_gate.py is pinned in the manifest and needs a new snapshot and review cycle, worth more than the minutes saved.
- The real risk is the **host-global** load1 ceiling of 20 in `may_start`. Any co-tenant (for example, a delay-fixes shard on 03) stalls gate (b) with `admission_wait` messages and no progress.

**Recommendation (zero code)**
- Reserve 03 exclusively for the gate (b) window; it currently runs at load 1.3.
- Exclude 03 from the exploration queue and guards during the window.
- Optionally requalify 03 at up to 21 three-core workers on cores 0–62. pilot.sh already supports this layout, which gives about 1.3× on gate (b).

**(c) Expected gain:** gate (b) about 76 min down to about 58 min at 03@21, or about 38 min with 01 and 04 admitted. The stall avoidance protects the schedule rather than adding speed.

**(d) Effort:** 0 h of code, about 1 h for a requalification pilot.

**(e) Risk:** timing qualification only. p99 ≤200.36 ms and zero >250 ms decisions must be re-shown.

**(f) Frozen dependency:** **yes.** run_gate, run_p16, smoke and register are manifest-pinned. Make no code changes; concurrency changes must go through the existing qualification and prereg path.

### 8. Lease v2 supervisor overhead and lock hold times (low priority)

**(a) File:** `fleet/lease/lease_watch_v2.py`.
- `supervise` calls `processes()` every second, scanning all of `/proc`.
- `check_all` runs every 60 s inside the exclusive `aggregate-v2.lock`: `smaps_rollup` for every tracked Clasher process plus `nvidia-smi`.
- `accounting()` rewrites the JSON registry every second for every supervisor.

**(b) Evidence**
- A full `/proc` stat scan takes 40 ms on 08 (1,383 processes) and 53 ms on 15 (1,400 processes), so each supervisor burns about 4–5% of a core.
- `smaps_rollup` over all own processes takes 0.56 s on 08 (63 processes) and 1.06 s on 15 (113 processes). That is about 1–1.5 s per minute of exclusive lock hold, which delays admissions.
- With 6 jobs per host this costs about 0.3 cores; minor.

**Fix:** a single per-host accounting daemon, or tracking descendants via `/proc/<pid>/task/*/children`, which is O(tree) instead of O(host).

**(c) Gain:** under 1% of host CPU, and admission latency of about 1 s.

**(d) Effort:** about 3–4 h.

**(e) Risk:** this is safety-critical code that was hot-fixed today with 47 tests.

**(f) Frozen dependency:** no, but **do not touch until the 05:00Z lease end**; then fold it into #2.

### 9. Checked and not worth changing

- **`hub_mirror` (v2 on 01 to 04):** about 7.5-min cycle every 30 min with `--bwlimit=50 MB/s`. That gives an RPO of about 30 min, which is acceptable.
- **T11 checkpoint backups (`backup_checkpoints_home2237.py`):** they already skip by size and mtime_ns. Checkpoints are about 36 MB each, so triple hashing costs under 0.1 s.
- **`reduce_traces.py`, `summarize.py` and `human.py`:** already fork-parallel.
- **`register.py`:** hashing runs once at freeze, so it is negligible.

### Cross-reference: not my area, but it dominates wall-clock

- **T5 GRU on 08:** the main Python thread is at 100% CPU, the GPU alternates 100% with 25–30% within each 36-s step, and throughput is 237 rows/s. That is roughly half the GPU wasted, a trainer input-path issue.
- **T11 home I/O:** 20.9% GPU, 538 MB/s reads, 18.9k major faults/s (PROGRESS-T11).
- **v4 packed inference on 11:** 3 single-threaded CPU-bound processes at 75–79% GPU.
- These belong to the training and perception audits. They are larger than everything in this report except #1–#3.

---

## Quick wins (under 2 h each)

1. **GPU guard (#1):** SCHED_IDLE plus pinning, a relative guard, and an idle-GPU exemption. **About 1.75× fleet exploration throughput** (from 0 to full on 11).
2. **`launch_shards.py` lane retry and requeue (#2 subset):** prevents a whole host going idle after one wrapper failure.
3. **100-pair shards with longest-first case order (#5):** about 1.15× on exploration sims.
4. **`PYTHONPYCACHEPREFIX` with precompile (#6):** about 1.7 s per process start; exploration and ops now, gates only with pre-freeze sign-off.
5. **Reserve 03 exclusively for the gate (b) window (#7):** the load-ceiling stall risk becomes zero, with no code change.

## 10-line summary

1. Gates (b)/(c) are small compute jobs (about 38–76 min and about 9 min); their code is manifest-pinned, so leave it alone (#7).
2. The biggest ops waste is the GPU guard: exploration workers are SIGSTOPped 43% of the time fleet-wide (100% on 11).
3. Pausing gives no measurable benefit: the 08 trainer runs at 235 vs 237 rows/s paused vs overall, and its 25–30% GPU phases persist while all workers are stopped.
4. Fix: SCHED_IDLE plus pinning and a relative throughput guard, about 2 h, for about 1.75× exploration throughput.
5. The fleet ran at about 16% CPU in the snapshot, with idle GPUs on 13 and 01; a hub queue that hosts pull from (6–10 h) could give 2–3× experiment throughput.
6. The T11 244 GB store staged at 111 MB/s against a 1,175 MB/s LAN; dropping `-c`, using parallel streams and overlapping SHA (2–3 h) cuts 36 min to about 7 min per host.
7. Seed audits cost about 2 h of gate prep, including 6.2 discarded CPU-hours. A v2 scanner with a cached literal index (4–6 h) makes future re-audits take minutes.
8. Exploration shards lose 15–20% to startup and tail; 100-pair shards with longest-first order is a 30-minute fix.
9. `-B` makes every process recompile (3.3 s vs 1.6 s import); `PYTHONPYCACHEPREFIX` keeps source trees pristine and halves startup.
10. Disclosures: I created then removed 1,010 `.pyc` files on 08 and ran one 1.5 s `/proc` probe on 15; I made no code edits, kills or commits.
