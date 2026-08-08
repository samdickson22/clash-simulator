# Simulator optimization evidence (worktree f872)

This report records exact-simulator and RL-rollout optimization work on branch
`codex/simulator-throughput-f872`, based on Clasher `159f87d`. The training task
owns model training and manually integrates isolated simulator commits. RoadForge
attempt 27 owns the sustained CPU/RAM window; after that reservation was announced,
only source inspection, syntax checks, focused tests, and short single-process
probes were permitted. No result below is a multi-worker training benchmark.

## Measurement host and method

- Mac mini, Apple M4 Pro, 12 CPU cores (8 performance, 4 efficiency), 24 GiB RAM
- macOS 26.5.2 (25F84), arm64
- Python 3.12.13, uv 0.12.2, NumPy 2.3.5, PyTorch 2.10.0
- Fixed-seed timings use `time.perf_counter()` and report the median. Unless noted,
  there are three or four repetitions after a small warm-up.
- These small samples provide direction and regression evidence, not confidence
  intervals. Production attribution remains pending a coordinated preflight and
  multi-worker run after RoadForge releases the heavy window.

The checked-in reproduction drivers are:

```bash
.venv/bin/python scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 1 --rollout-steps 12 \
  --repetitions 3 --warmup-steps 2 --torch-threads 2 \
  --max-ticks 2048 --engine-fast-path on

.venv/bin/python scripts/perf/benchmark_stationary_rollout.py \
  --workload strategy --strategy balanced --seed 2301 --num-envs 1 \
  --rollout-steps 12 --repetitions 3 --warmup-steps 2 \
  --torch-threads 2 --max-ticks 2048 --engine-fast-path on

.venv/bin/python scripts/perf/benchmark_crowded_engine.py \
  --seed 2301 --card Knight --per-side 12 --ticks 8 \
  --repetitions 4 --mode both --clear-route-cache-per-mode

.venv/bin/python scripts/perf/benchmark_oracle_clone.py \
  --mode deepcopy --seed 2301 --oracle-seed 901 --clone-repetitions 5 \
  --plan-depth 2 --simulations 4 --action-samples 16 --decision-interval 8 \
  --reward-profile defense-v2
.venv/bin/python scripts/perf/benchmark_oracle_clone.py \
  --mode clone --seed 2301 --oracle-seed 901 --clone-repetitions 5 \
  --plan-depth 2 --simulations 4 --action-samples 16 --decision-interval 8 \
  --reward-profile defense-v2
```

Do not run these timing commands while another task owns the sustained-compute
window. The latter two drivers were added after the measurements and reproduce the
same fixed workload; they were only syntax- and lint-checked during the hold.

## Results by workload

### Stationary RL opponents

The learner uses the full recurrent structured policy (`d_model=128`). Commit
`c97bca2` avoids constructing an opponent actor/critic observation when the
opponent is stationary random or strategy code and has no policy model. Optional
strategy-bot mask reuse then consumes the already computed action mask rather than
asking the environment for the same mask again.

| Workload | Stage | Median wall time | Decisions/s | Gain from original | Rollout SHA-256 |
|---|---|---:|---:|---:|---|
| Random | original | 0.192226 s | 62.426 | - | `2248299c0702a9c8488378e204bb6c9ea374acbddda52f7b96b5b397f0e532c6` |
| Random | observation skip | 0.186778 s | 64.247 | +2.92% | same |
| Balanced strategy | original | 0.151735 s | 79.085 | - | `32ecf56d9a213e5bc96df1c60a1c55a728b80258cfbdef9b7f7940391f621c55` |
| Balanced strategy | observation skip | 0.149543 s | 80.245 | +1.47% | same |
| Balanced strategy | observation + mask reuse | 0.124734 s | 96.205 | +21.65% | same |

The final strategy gain is whole-rollout throughput for this one-environment fixed
probe. Training integrated both low-risk changes and independently passed its
structured-policy, strategy, and opponent-league gates.

### Strategy scorer card features

After the occupancy and multiprocess work, a post-optimization profile showed
`StrategyBot.select_action` still scoring 54,212 legal tile actions in a 64-step
balanced rollout. Card resolution, public stat extraction, and efficiency arithmetic
were invariant across every tile for a hand slot. The narrow refactor computes those
features once per visible hand card and retains the exact scalar spatial score. It
also keeps the first maximum encountered instead of allocating every `(score,
-action_id)` tuple; because legal IDs are ascending, this is the same smallest-ID
tie rule, including floating-point equality.

The fixed balanced-strategy command used seed 2301, one environment, 64 steps, four
warm-up steps, seven repetitions, two Torch threads, and the optimized engine:

```bash
.venv/bin/python scripts/perf/benchmark_stationary_rollout.py \
  --workload strategy --strategy balanced --seed 2301 --num-envs 1 \
  --rollout-steps 64 --repetitions 7 --warmup-steps 4 \
  --torch-threads 2 --max-ticks 2048 --engine-fast-path on
```

| Revision | Median wall time | Median decisions/s | Rollout SHA-256 |
|---|---:|---:|---|
| Per-tile card features | 0.675390 s | 94.760 | `edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645` |
| Per-hand-slot features | 0.600819 s | 106.521 | same |

This improves whole-rollout throughput by 12.41% and reduces median wall time by
11.04%. Under `cProfile`, cumulative strategy selection time fell from 0.396 s to
0.170 s and scoring time from 0.368 s to 0.155 s; feature construction cost 0.002 s.

All six strategy traces were also frozen at seed 7711 for 32 steps. Pre/post hashes
matched exactly: bridge pressure `423bb32e6664d06cd45c1bcdabddde1c7f13321d1de6bb8cb973b7d85d7d34ce`,
slow push `052b41b62f640c434295015f4f9d2621914d72e1edae34c06c26733559554066`,
spell control `eb3487cdb1fd19f9411cbbbc1a8cf196e4bc3ac54dde14dec37c1d9eb473f6d2`,
reactive defense `2ee4e97cfe3454eab3a8095af8c64824396f3d6e460a52f015d44a81dd30b3a4`,
split lane `ef52f95bb40026c86753f6807e538777dfbad15cb3654a10d0ff962b556fe7b9`,
and balanced `10ea618de170b7f9c43ce6817bc848a316c404f51f3694c99f6b1c5481af413f`.
The strategy, structured-policy, and league gate passed 30 tests. The standard
off/shadow/on rollout digest remained unchanged with zero shadow mismatches.

### Crowded exact engine

The fixed state contains 12 Knights per side and advances eight native ticks. Both
scalar and optimized engines finish with state hash
`eca1565466bd124dac3063fa70b62e55d42066849bdf4919bb3ae923501e49c7`.

| Exact change | Scalar median | Scalar gain | Fast median | Fast gain |
|---|---:|---:|---:|---:|
| Original | 0.080581 s | - | 0.084662 s | - |
| Normalized trait-name cache (`7c5933d`) | 0.072864 s | +10.59% | 0.076923 s | +10.06% |
| Reuse troop collision plane (`03e02a0`) | 0.070580 s | +3.24% incremental | 0.074680 s | +3.00% incremental |
| Cache immutable hover trait (`d8b3173`) | 0.067636 s | +4.35% incremental | 0.071533 s | +4.40% incremental |

The combined trait/collision changes improve throughput by 19.14% scalar and
18.35% fast versus the original crowded probe. This workload also proves that the
existing fast path is not universally faster: before the changes its 0.084662 s
median trailed scalar's 0.080581 s. A sparse random rollout similarly measured
about 209.996 decisions/s scalar versus 186.740 fast. The fast path therefore stays
opt-in behind its equivalence preflight rather than being forced globally.

Commit `d5a90b7` caches exact standard-arena native grid routes as immutable tuples,
keyed by start cell, goal cell, native lane, and jump-height capability. Each entity
still receives a fresh mutable list. With the cache cleared independently per mode,
cold/warm scalar timing was 0.064876/0.024070 s and cold/warm fast timing was
0.068853/0.028102 s; after four battles the cache had 84 hits and 28 misses. The
warm microbenchmark gain (181.0% scalar, 154.5% fast versus the immediately prior
uncached probe) is deliberately not presented as whole-training throughput.

### Troop placement occupancy masks

RoadForge released attempt 29 before this measurement and both coordinating tasks
confirmed a clean CPU-only window. The pre-change baseline was a temporary source
copy with `battle.py` and `rl/action_space.py` restored from artifact commit
`dd6fcb4`; all inherited rollout, strategy, reward, and reporting code therefore
remained identical. The optimized state caches a world-tile mask per troop collision
radius and invalidates every mask when the existing live-building signature changes.
It preserves the scalar predicate's fixed-point coordinate conversion and strict
squared-circle comparison. Deployment payload checks remain dynamic.

The fixed mask microbenchmark used six live Cannons, four troop cards, both players,
seed 2301, 64 decisions, two warm-up decisions, and seven repetitions:

```bash
.venv/bin/python scripts/perf/benchmark_action_mask.py \
  --seed 2301 --building-card Cannon \
  --hand-cards Knight,Giant,Archers,Musketeer \
  --decisions 64 --repetitions 7 --warmup-decisions 2 --mode both
```

| Implementation | Median wall time | Decisions/s | Exact mask SHA-256 |
|---|---:|---:|---|
| Pre-change scalar/off | 0.938376 s | 68.203 | `640614c29015b001128a181630b61456725801db1df3b197edc9109ec9b4c707` |
| Candidate scalar/off | 0.941441 s | 67.981 | same |
| Pre-change fast/on | 0.486308 s | 131.604 | same |
| Radius-cache fast/on | 0.069867 s | 916.023 | same |

The optimized fast path reduces median wall time by 85.63% and improves mask
decisions/s by 596.05% on this occupancy-heavy attribution probe. Scalar timing is
unchanged within run noise.

A separate cold-cache probe used one decision, zero warm-up decisions, and 21
fresh-battle repetitions. Median fast-path time fell from 0.007861 s (127.218
decisions/s) to 0.001326 s (753.887 decisions/s): 83.13% less wall time and
492.60% more throughput. The exact cold mask hash was
`336a840e7523e2f4aceace11bc7a3eaf9dd410b3fca954ca99a093f300d3bf2f`, so the
cache construction cost does not hide an episode-start regression.

The identical full-policy stationary driver then used one environment, 32 rollout
steps, four warm-up steps, five repetitions, two Torch threads, and the optimized
engine:

| Whole rollout | Pre-change wall / decisions/s | Candidate wall / decisions/s | Gain | Rollout SHA-256 |
|---|---:|---:|---:|---|
| Random opponent | 0.282303 s / 113.353 | 0.274430 s / 116.605 | +2.87% | `7efcac3f46f2fed53e3e4b0ee4ceda3f47e72fedc825a962a2f1563fd6e27fb1` |
| Balanced strategy | 0.333932 s / 95.828 | 0.279738 s / 114.393 | +19.37% | `500a76e31cb0d8112664d047b445afa16d695d8adf0e68965fe94ede2a75c475` |

The corresponding median wall-time reductions are 2.79% and 16.23%. These are
whole-rollout results for the fixed single-environment probes, not multi-worker
learner throughput.

### Multiprocess production attribution

After RoadForge attempt 30 released the CPU window, both coordinating tasks granted
a bounded multiprocess benchmark. The existing async queue harness used 12
persistent CPU actors, seed 2301, 12,288 transitions (6,144 two-player decisions),
64-decision actor batches, the optimized engine, actor-local random legal actions,
and no inference server, MPS/GPU, learner, checkpoint, or file writes. The baseline
used the same temporary pre-occupancy source overlay described above.

```bash
.venv/bin/python -m clasher.rl.benchmark async-queue \
  --seed 2301 --num-actors 12 --transitions 12288 \
  --actor-rollout-steps 64 --queue-size 32 --decision-interval 8 \
  --max-ticks 2048 --quiet-engine --engine-fast-path on \
  --inference-mode actor_local --inference-device cpu
```

Five repetitions per revision produced:

| Revision | Wall times (s) | Decisions/s | Median wall | Median decisions/s |
|---|---|---|---:|---:|
| Pre-change | 5.6076, 5.5342, 5.6393, 5.5133, 5.6137 | 1095.6525, 1110.1964, 1089.5027, 1114.3961, 1094.4644 | 5.6076 s | 1095.6525 |
| Occupancy cache | 5.4614, 5.3652, 5.4192, 5.4388, 5.4658 | 1124.9794, 1145.1519, 1133.7559, 1129.6565, 1124.0803 | 5.4388 s | 1129.6565 |

The occupancy cache improves median multiprocess actor throughput by 3.10% and
reduces median wall time by 3.01%. The five observed throughput ranges do not
overlap: 1089.50-1114.40 decisions/s before versus 1124.08-1145.15 after. Sample
means and standard deviations were 1100.84 +/- 10.81 and 1131.52 +/- 8.55
decisions/s respectively. This establishes production-shaped simulator attribution,
but it still excludes recurrent policy inference and learner work.

### Oracle snapshots

Commit `e4edffd` replaces oracle `deepcopy` with an exact `BattleState.clone()`.
Mutable battle, player, entity, mechanic, RNG, NumPy-cache, fast-bucket, card-loader,
and compatibility-wrapper state remains independent. Only frozen card definitions
are shared. On the fixed six-tower state, median snapshot time fell from about
9.96 ms to 0.359 ms (27.7x). The fixed depth-2, four-simulation oracle probe fell
from 114.65 ms to 53.85 ms (2.13x), with identical selected actions
`{0: 51, 1: 52}`.

### Incremental fast target-cache refresh

The fast engine previously rebuilt target membership, the ID-to-array index, and
eleven NumPy arrays at both cache refreshes of every logic tick. The incremental
path now scans the stable entity insertion order by identity. An add, removal, death,
or same-size replacement falls back to the original structural rebuild; unchanged
membership republishes only position, airborne plane, targetability, and stealth
into the existing arrays. The four data-driven post-spawn distance-priority sites
explicitly publish that otherwise-static value.

The reproducible drivers expose `--target-cache-refresh rebuild|reuse`, allowing
the old and new paths to run from the same source tree. The crowded probe used seed
2301, 12 Knights per side, 64 ticks, and 11 repetitions:

```bash
.venv/bin/python scripts/perf/benchmark_crowded_engine.py \
  --seed 2301 --card Knight --per-side 12 --ticks 64 --repetitions 11 \
  --mode on --clear-route-cache-per-mode --target-cache-refresh rebuild
.venv/bin/python scripts/perf/benchmark_crowded_engine.py \
  --seed 2301 --card Knight --per-side 12 --ticks 64 --repetitions 11 \
  --mode on --clear-route-cache-per-mode --target-cache-refresh reuse
```

| Crowded fast engine | Median wall | Ticks/s | State SHA-256 |
|---|---:|---:|---|
| Full target rebuild | 0.330096 s | 193.883 | `d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb` |
| Incremental refresh | 0.302905 s | 211.288 | same |

This is an 8.98% throughput gain and 8.24% wall-time reduction. A three-repetition
`cProfile` attribution recorded 390 cache refreshes: cumulative target-cache time
fell from 0.128 s in 390 structural rebuilds to 0.045 s in 390 incremental refreshes
plus six structural rebuilds, a 64.8% reduction in the named cache work.

Whole recurrent-policy rollouts then used one environment, 64 steps, four warm-up
steps, seven repetitions, two Torch threads, and the optimized engine:

```bash
.venv/bin/python scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 7 --warmup-steps 4 --torch-threads 2 \
  --engine-fast-path on --target-cache-refresh rebuild
# Repeat with --target-cache-refresh reuse; repeat both commands with
# --workload strategy --strategy balanced.
```

| Workload | Full rebuild wall / decisions/s | Incremental wall / decisions/s | Gain | Rollout SHA-256 |
|---|---:|---:|---:|---|
| Random | 2.000022 s / 32.000 | 1.920225 s / 33.329 | +4.16% | `1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785` |
| Balanced strategy | 2.179087 s / 29.370 | 1.976789 s / 32.376 | +10.23% | `edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645` |

The corresponding wall-time reductions are 3.99% and 9.28%. These short samples
have seven repetitions but no confidence interval and remain single-process
attribution. The recurring scalar/off, shadow, and optimized/on digest stayed
`9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349`;
shadow recorded two checks and zero mismatches. A focused target/collision/action-
mask and spawn/death interaction gate passed 240 selected tests, including explicit
array-reuse and same-size-membership-replacement coverage.

### Work explicitly not optimized

- Observation stacking: a representative profile attributed about 1 ms total to
  275 `numpy.stack` calls inside an approximately 0.8 s rollout. Buffer reuse was
  deferred because copying was not a material bottleneck.
- Idle advancement: one accidentally overlong, single-core no-op probe showed the
  fast path already improved the idle case (52.58 to 115.42 decisions/s, identical
  hash), while action-mask and reward work dominated. The process fully exited and
  both coordinating tasks were notified; no follow-up timing loop will run before
  RoadForge releases the window.

## Exactness gates

The recurring fixed rollout used seed 2301, 64 decisions, `max_ticks=2048`, two
trials, and `defense-v2` in scalar/off, shadow, and optimized/on modes:

```bash
for mode in off shadow on; do
  .venv/bin/python -m clasher.rl.determinism_check \
    --seed 2301 --decisions 64 --max-ticks 2048 --trials 2 \
    --quiet-engine --engine-fast-path "$mode" --reward-profile defense-v2
done
```

All modes produced SHA-256
`9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349`.
Shadow recorded one mask check per trial and zero mismatches. Targeting, collision,
action-mask, air/hover, route/river/bridge, clone isolation, loader, stat-wrapper,
and oracle suites passed after their corresponding shared-engine changes. The
training task independently reran combined-tree gates after each manual integration.

## Remaining production attribution

The exact action-mask occupancy cache has now passed fixed microbenchmark,
whole-rollout, scalar/shadow/on hash, all-enabled-card, cache-invalidation, and
shared targeting/collision gates, plus a matched 12-actor production-shaped queue
benchmark. End-to-end learner decisions/s remains deliberately unattributed until
the training task runs its real recurrent collector and learner configuration; that
work retains separate training ownership and requires a newly coordinated CPU/MPS
window.
