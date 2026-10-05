# Pilot throughput benchmark (post-admission, admission-scope decision v1)

Script: `scripts/perf/benchmark_council_pilot_throughput.py`. It runs the real council actor (2.6M parameters, fresh weights) against the council opponent pool in its initial phase: 50% public scripts, 50% two fresh initial policies. Each run does 2 warm-up collections and 1 untimed update, then 3 measured cycles. A cycle is one 128-step rollout followed by one real PPO update with the signed recipe: 2 epochs, minibatch of 2 sequences, clip 0.2, lr 1e-4, target KL 0.02, exact full-prefix reconstruction. Mean episode prefix over the measured cycles is about 380 steps, close to steady state. Everything ran in a temp dir; no checkpoint was written outside it. The Mac mini is an M4 Pro (8P+4E, 24 GB), with one emulator using about 0.6 core throughout. One JSON per run is in this directory.

The first `baseline` and `env8-learner-cpu` runs overlapped my own test runs. They were rerun (`*-rerun.json`), and the reruns are the numbers used below.

## Single run (alone on the machine)

"Workers" is the number of actor processes. "Mode" is where inference runs: `worker` means a CPU policy copy in each actor process; `learner` means one batched forward over all envs in the learner process. Column key: dec/s includes updates. Collect is collection-only dec/s. Update is ms of update per decision. p95 fwd is the p95 time of the batched learner forward, in ms. Learner, actors and MPS are peak GB. The actor figure sums RSS across processes, so shared torch pages are counted more than once. Cores is average cores busy.

| Config | Envs | Workers | Mode | Learner / inference device | Threads | dec/s | Collect | Update | p95 fwd | Learner | Actors | MPS | Cores |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| current kit | 8 | 2 | worker | cpu/cpu | 2 | 33.5 | 94 | 19.2 | – | 4.4 | 3.6 | – | 2.0 |
| | 8 | 4 | learner | cpu/cpu | 4 | 46.5 | 124 | 13.4 | 15 | 4.7 | 2.5 | – | 3.0 |
| | 8 | 4 | learner | mps/mps | 4 | 41.0 | 69 | 9.9 | 64 | 1.5 | 2.0 | 8.5 | 1.1 |
| | 32 | 8 | learner | cpu/cpu | 4 | 50.4 | 158 | 13.5 | 50 | 6.4 | 6.3 | – | 3.2 |
| | 32 | 8 | learner | mps/mps | 4 | 69.2 | 161 | 8.2 | 71 | 2.0 | 4.9 | 8.7 | 1.2 |
| | 64 | 8 | learner | cpu/cpu | 4 | 51.0 | 163 | 13.5 | 90 | 7.4 | 6.8 | – | 3.3 |
| | 64 | 8 | learner | mps/mps | 4 | 74.2 | 190 | 8.2 | 95 | 3.1 | 5.3 | 9.0 | 1.2 |
| | 64 | 8 | worker | cpu/cpu | 4 | 57.5 | 276 | 13.8 | – | 5.6 | 12.3 | – | 4.1 |
| | 64 | 8 | worker | mps/cpu | 4 | **82.6** | 268 | 8.4 | – | 1.8 | 12.3 | 8.4 | 2.7 |
| | 64 | 8 | learner | mps/cpu | 4 | 84.2 (71.6)* | 164 | 5.8* | 89 | 3.7 | 6.1 | 8.6 | 2.1 |

\* Some updates in this run stopped early on the KL guard. The figure in brackets normalizes to full two-epoch updates.

## Three concurrent runs (one per seed)

| Layout | Per run dec/s | Aggregate |
|---|---|---|
| 3 × current kit (8 envs / 2 workers / 2 threads, CPU) | 24.5, 24.3, 24.1 | 72.8 |
| 3 × 64 envs / 8 workers / 4 threads, worker mode, CPU | 29.4, 29.4, 29.7 | 88.5 |
| 64/8/4 worker mode: 1 × MPS learner + 2 × CPU | 48.6, 32.9, 33.2 | 114.7 |

Three MPS runs were not tested. Each 64-env MPS run allocates 8.4–9.0 GB of driver memory, so three would not fit in 24 GB. Swap already rose to about 10.8 GB during the 3 × CPU test.

## Findings

1. **The learner update is the bottleneck, and its cost per decision is fixed by the recipe.** Each 2-sequence minibatch replays both sequences' full episode prefixes with the current weights (about 380 steps each on average), then does forward and backward over 2 × 128 steps, twice per update. That costs about 13.5 ms per decision on 4 CPU threads, 19 ms on 2 threads and 8.2 ms on MPS, whatever the number of environments. More environments only help collection.
2. **Batched learner-side inference is slower on CPU here.** The CPU forward is compute-bound and scales linearly with batch size. Per-worker inference and per-worker reconstruction run in parallel across processes, while learner-side reconstruction at chunk start runs serially in the learner. Worker mode collects 276 dec/s at 64 envs versus 163 for learner mode. With MPS inference the batched forward takes about 95 ms p95 at 64 envs and is still not faster than per-worker CPU inference. Learner mode stays available: it is partition-invariant and bit-identical to the admitted collector.
3. **CPU is saturated at about 88 decisions/s in aggregate.** 64 envs raises per-run speed alone (33.5 → 57.5), but with three seeds the aggregate only rises from 72.8 to 88.5 (+22%). The GPU is the only real extra compute: 1 MPS + 2 CPU reaches 114.7 (+58%).
4. **The MPS learner has two costs.** First, each seed's ledger allows only 72 accelerator-hours, and with `device = "mps"` everything that seed runs is charged, including the warm start and all evaluation games. Evaluation plays single-game batch-1 inference, and the micro benchmark shows that is about 3× slower per forward on MPS (13 ms vs 4 ms). Second, the driver allocation is about 9 GB.

## Recommendation for this Mac mini

**Within the current ceilings:** all three seeds on CPU with `num_envs = 64`, `actor_workers = 8`, `torch_threads = 4`, `rollout_inference = "worker"`, `device = "cpu"`, `smoke_decisions = 98304` (100,000 is not divisible by 64).

- Estimated training: 10M decisions per seed at about 29.5/s ≈ 94 h.
- Adding the warm start (3–5.5 h) and evaluation (about 3,600 games per seed at 15–25 s each, 15–25 h), total wall time is **about 115–125 h (4.8–5.2 days)**.
- The current kit measures 24.3/s per seed, about 135–145 h (5.6–6 days) on the same basis.

Two things change at 64 envs:

- The 20-update critic warm-up spans 163,840 decisions, so the 98,304-decision smoke is entirely critic-only.
- Periodic checkpoints (every 200 updates) come every 1.64M decisions, about 15 h.

`num_envs = 32` would keep one or two actor updates in the smoke and checkpoint every 0.82M decisions. Its per-run speed is similar, but worker mode at 32 envs was not benchmarked under concurrency.

**Faster, if the accelerator ceiling is raised for one seed:** run seed 2901 with `device = "mps"` and the other two on CPU, all 64/8/4 in worker mode. The MPS seed would need about 80–90 accelerator-hours against the 72-hour ceiling. The estimated total is **about 100–110 h (4.2–4.6 days)**. Raising the ceiling is a budget decision that this work does not make.

Projections assume untrained-policy episode lengths and no KL early stops. Real KL stops shorten updates, so the estimates are conservative. Treat them as ±25%.
