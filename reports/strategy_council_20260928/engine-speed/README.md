# Engine speed: what it would take to make the simulator 30-100x faster

Date: 2026-10-02/03. Host: Mac mini M4 Pro (8P + 4E cores, 24 GB), shared with two PPO runs,
oracle-qualification workers and the C56 agent throughout (load 8-36). All runs used `nice -n 10`.
Nothing under `src/` was edited. Prototypes live in `~/.cache/clasher-engine-speed/`. The log,
with every command and PID, is in `PROGRESS.md`.

## 1. Short answer

1. **For PPO the simulator is not the bottleneck.** The engine is 5-8% of the CPU spent per PPO
   decision (5% of wall samples, about 8 of 93 CPU-ms). The PPO update is two-thirds of the CPU
   (66%; 81% of samples including prefix reconstruction): the recurrent recipe replays full
   episode prefixes, and that replay plus the policy forwards is the cost. An infinitely fast engine would raise single-run
   PPO throughput by about 5% (57.5 to about 61 decisions/s in the measured 64-env layout).
   Collection alone would gain about 1.35x.
2. **For search it is half the bottleneck.** One srp planner call (the teacher that passed
   oracle qualification) costs about 3.1 core-seconds. 52% of that is engine ticks. 46% is the
   public script choosing moves inside the rollouts, and most of that is building the
   neural-network observation. Clone is 1.3%. A faster engine on its own caps srp at about 2x.
   Porting the engine and the script controller together gives about 30-60x.
3. **Only a compiled core reaches 30-100x on the engine.** The Python engine spends about 20
   million instructions per tick on about 12 live entities. The profile is flat: the top function
   is 5% self time. What I measured or prototyped:
   - Python-level algorithmic fixes: 1.11x fewer instructions for five fixes. Byte-identical.
   - Cython, compiling the unchanged source: 1.34-1.39x fewer instructions, 1.40-1.51x fewer
     cycles. Byte-identical.
   - PyPy: 0.77x. CPython 3.14: 0.95x.
   - torch_sim / Simple Gym: 8-41 row-ticks/s, against about 700 for one Python core. It is not
     byte-identical by design, and MPS used 23 GB at B=256.
   - Exact Rust port of the A* router: 52x faster, 0 route mismatches in 2,000 cases.
4. **Recommendation: a staged Rust core (pyo3), with the Python engine kept as the reference
   oracle and byte-identity digests as the gate.** It starts with two days of free wins, then a
   1-2 week spike with a hard go/no-go. Full 16-card parity is about 25-40 engineer-days, plus
   15-30 for C56. Section 5 has the details.

## 2. Measured profile

### 2.1 Engine alone (random-legal full matches, main `src/`, CPython 3.12)

`es_engine.py` / `es_pure.py` play full random-legal matches (both seats deploy whenever they can,
decision every 5 ticks, 6001-tick cap) and digest the full battle state every 20 decisions.

- Throughput: 585-805 step-only ticks/s per core, depending on host load (`pure_cp312_r1`,
  `pure_base*`). Load moves CPU time by about 30%, because nice'd processes migrate between P- and
  E-cores. Comparisons below therefore use **instructions retired** (`/usr/bin/time -l`), which do
  not depend on load. All A/B pairs have identical digests, so they did the same simulated work.
- About 19k Python calls and 5.6k `getattr` per tick (cProfile). About 21M instructions per tick
  including the harness.
- `BattleState.clone()` (deepcopy) costs 2.9 ms on 3.12 and 2.1 ms on 3.14 (`pure_cp3*`).
- The frozen pilot-runtime-v4 engine looked about 25% faster than main `src/` on 2 matches. That
  comparison was not run under the same load and the trajectories differ, so treat it as
  unconfirmed. It is noted because the 09-28 fidelity merge may have added cost.

Stack-sampled subsystem shares (`results/engine_sample_off.json`, 9,725 samples; shares of the
whole loop including the harness's legal mask):

| subsystem | share | main functions |
|---|---|---|
| pathfinding | 28.6% | `ground_path_waypoint` → `native_route_goal_cell` 14.2% (lru miss on every move, since the key holds the exact position), `_cached_dynamic_grid_route` / `_native_grid_route` A* 10.9% |
| targeting | 20.0% | `get_nearest_target` 15.4%, `_retain_or_acquire_target` 8.8% (towers rescan every tick), `_is_valid_target` → `is_expected_to_die_from_projectiles` (an O(n) scan per candidate, so O(n²) per scan) |
| legal mask (harness, not engine) | 15.0% | `_legal_action_mask_legacy` |
| collision | 8.9% | `_accumulate_troop_collision_for` (O(n²)) |
| tick grids | 5.4% | `native_spatial`, `native_building_cost_cells` |
| combat / movement | 4.4% / 4.4% | |
| rewards, avoidance, quantize, object phase | 2.4 / 2.4 / 1.2 / 1.3% | |

Top self-time: `native_spawn_tile_blocked` 5.0%, `tiles_to_logic_units` 4.6%,
`native_route_goal_cell` 4.4%, `_compute_native_route_goal_cell_units` 3.8%,
`is_expected_to_die_from_projectiles` 3.5%, the A* loop 3.3%, then a long tail under 3% each.
Interpreter overhead (attribute lookups, calls, boxing) is the real cost, spread everywhere.

### 2.2 PPO rollout + update (`es_rollout.py`, one actor's share: 8 envs, 1 thread, real PPO update)

`results/rollout_w8_s1.json`: collect 31.2 CPU-ms per decision, update 61.9 CPU-ms per decision
(single thread). Sampled shares of all CPU:

| part | share | per decision |
|---|---|---|
| `ppo_update` (forward/backward over 2×128-step sequences, 2 epochs) | 73.0% | |
| recurrent prefix reconstruction | 7.6% | |
| learner policy forward (collection) | 6.3% | ~10 ms |
| **engine step** (5 ticks) | **5.1%** (engine itself ~4.7%) | ~8 ms |
| opponent (policy forward / script, its observation and mask) | 5.9% | |
| learner observation + mask | 1.4% | |
| glue | 0.8% | |

This agrees with the pilot throughput study (`pilot/throughput/README.md`). With 64 envs, 8
workers, 4 threads in worker mode, collection alone runs at 276 decisions/s. The update costs
13.8 ms per decision on 4 CPU threads (8.2 on MPS), and a single run reaches 57.5 decisions/s.
The update cost is fixed by the recipe (full-prefix replay, minibatch of 2 sequences), not by
the simulator. Amdahl: the engine is about 26% of collection CPU, so an infinitely fast engine
gives collection about 1.35x and the whole loop about 1.05x.

### 2.3 Search: one srp planner call (`es_srp.py`, oracle-qualification `ScriptRolloutPlanner`)

`results/srp_s12.json` (12 calls on real game states, frozen pilot-runtime-v4, loaded host):
3.09 CPU-s per call, 21 rollouts, 3,360 engine ticks and 632 script decisions per call.

| part | share |
|---|---|
| engine step | 51.6% (about 1,930 ticks/s inside rollouts) |
| script: structured observation build (`public_observation.py`) | 29.0% |
| script: public projection | 10.0% |
| script: decide | 7.0% |
| clone | 1.3% (1.0-1.3 ms each) |
| apply_action / phi | 0.8% |

Engine time inside srp, by subsystem: targeting 36%, pathfinding 11%, collision 10%, tick grids
10%, combat 9%, avoidance 3%, quantize 3%.

## 3. What each option buys and costs

Speedups are on engine ticks per core-second unless stated. "Parity" means byte-identical state
digests against the validated 16-card engine.

### (a) Algorithmic fixes in the Python engine

Prototype in `~/.cache/clasher-engine-speed/proto/src` (copy of `src/`), five fixes:
- P1: `native_spawn_tile_blocked` becomes a table lookup.
- P2: dynamic A* uses a building-cost overlay instead of copying the 2,304-cell cost dict.
- P3: A* heap keeps a position index instead of `list.index`.
- P4: the occupied-cell frozenset is memoised per building snapshot.
- P5: `get_nearest_target` runs the cheap pure filters (plane, building-only, sight) before the
  expensive validity check.

| check | result |
|---|---|
| es_pure digests vs unmodified engine (4 matches, 2 A/B pairs) | identical |
| c56 `p16_identity.py check` (12 scripted 16-card episodes + branches, 15,949 digest boundaries) | 0 mismatches |
| instructions retired (whole process) | 526.8G → 472.2G = **1.11x** (cycles 1.05-1.13x) |

Further candidates, in order of share: a per-tick pending-projectile-damage index (replaces the
O(n²) `is_expected_to_die_from_projectiles`), a tower target cache that rescans only when the
spatial grid changed in range, a precomputed candidate list for the route goal cell (it is
recomputed for every moving troop every tick), and a spatial grid for troop collision. Each is
worth roughly 3-8%. Every one touches validated semantics, such as tie order and in-tick damage
reservation, so each needs its own parity proof.

- Cost: 1-2 engineer-days per fix, including parity checks. About 1.5-2x in total after 2-3 weeks.
- Ceiling: about 2x. The profile is flat and interpreter-bound.
- Parity risk: low to medium per fix, all gated by digests. C56: low; the fixes are in shared code
  and C56 cards benefit too.

### (b) Interpreter and compiler changes (same source)

| variant | instructions / CPU | clone | digests |
|---|---|---|---|
| CPython 3.12 (baseline) | 1.00 | 2.9 ms | — |
| CPython 3.14 | 0.95x step-only CPU | 2.1 ms | identical |
| PyPy 3.11 (7.3.23) | 0.77x (JIT warm-up visible; warm matches reach parity at best) | 6.3 ms | identical |
| **Cython 3.3, pure-Python mode, no source change** (battle, entities, pathfinding, arena, kinematics, native_tilemap, unit_traits, native_spatial, placement) | **1.34-1.39x fewer instructions, 1.40-1.51x fewer cycles, 1.54-1.67x step CPU** | — | identical (es_pure); Cython + P1-P5 passes p16 with 0 mismatches |

The only Cython incompatibility is numba's `@njit` in `battle.py`, which rejects compiled
functions. Moving that single helper into an uncompiled module fixes it. es_pure digests are
identical with and without numba.

- Cost: about 1 day to add a build step (setuptools/cythonize, for engine modules only) plus CI.
- Gain: about 1.4-1.5x on the engine. On workloads dominated by the script and its observations
  it is smaller, because the `rl/` observation code was not compiled:
  - c56 p16 set (instructions): baseline-src 2,162G, P1-P5 2,119G (1.02x), Cython + P1-P5
    1,925G (1.12x); 0 mismatches each.
  - srp planner, 8 real calls (`run_srp_ab.sh`), main `src/` against Cython + P1-P5: chosen
    actions and rollout ticks identical; 41.7G → 33.3G instructions per call (1.25x); CPU
    3.77 → 3.04 s per call (1.24x). Compiling `rl/public_observation.py` and
  `structured_obs.py` is the obvious next step.
- Ceiling: typed `cdef` classes could reach 3-5x, but the engine depends on dynamic attributes
  (`getattr(entity, "...", default)` about 5,600 times per tick) and dataclass deepcopy. That
  rewrite would cost about as much as a Rust port and reach a lower ceiling.
- Parity risk: very low (same bytecode semantics). Free-threaded 3.14 adds no cores and was not
  pursued.

### (c) Finishing torch_sim (Simple Gym / resident engine)

- State: 92k lines. `pytest` gives 516 passed, 260 skipped, 6 failed. The failures are stale
  expectations after the 09-28 fidelity merge (for example Fireball tower damage 269), the
  rolling Log / Barbarian Barrel runtime, a dependency test, and standard setup. The executor
  differential (`python -m clasher.torch_sim.differential episode|crowded`) **no longer runs on
  main**: `SelfPlayBattleEnv.__init__()` has dropped the `simulation_backend` argument it passes
  (`logs/torchsim_diff_*.log`), so the torch executor is disconnected from the env. Simple Gym
  semantics are
  "contract, not parity": the code itself says it is not byte-identical to the Python engine.
  The resident engine has no tests and has not changed since 08-27. 27 of the 40 C56 cards are in
  the Simple manifest.
- Throughput on this Mac (`benchmark_simple_gym.py`, measured now):
  - CPU, B=64, 128 entities/128 effects: **8.3 row-ticks/s**.
  - MPS, B=64, 128/128: **40.8 row-ticks/s**, 8.3 GB footprint.
  - MPS, B=256, 128/128: hit **23 GB** (19 GB graphics), pushed the host into 15 GB of swap, and
    was killed.
  - Bounded capacities: MPS B=64 48/64 **74.8** (3.7 GB); MPS B=128 32/32 **215.4** (3.7 GB);
    CPU B=64 48/64 **58.1**. Digests were stable across repetitions.
  - Earlier study (08-28): MPS 84 row-ticks/s at 128/128 and 851 at 16/16 with B=128; A6000 CUDA
    graph 2,666 at 48/64. Even the A6000 was only 1.65x the M4's Python.
  - One Python core does about 700 ticks/s.
- Cost to make it useful: re-sync with the fidelity merge, close the parity gap for 16 cards, and
  add C56. That is weeks to months. It still could not be byte-identical, because float32 tensor
  math and fixed-capacity pools differ from the scalar engine.
- Verdict: **no**. It is slower than Python on this hardware, has no parity, and does not fit in
  memory at useful batch sizes.

### (d) Compiled core (Rust via pyo3)

Micro-prototype: `rust_astar/` is an exact port of `pathfinding._native_grid_route` (weighted
octile A*, priority-only binary heap, right child checked before left, decrease-key by sift-up).
Cases come from the unmodified engine (`es_astar_export.py`, 2,000 random routes with tower and
building overlays). Result: **0 / 2,000 route mismatches. Python 2,813 µs per route, Rust 54 µs:
52x** on a loaded host.

Whole-tick estimate. Python spends about 20M instructions per tick (about 1.7M per live entity).
The same work in a native struct-of-entities loop is on the order of 10^4-10^5 instructions.
Expect **30-100x per core for ticks and 100-1000x for clone** (a `Vec` memcpy instead of
deepcopy). Search also gets cheap snapshots, so rollouts can share prefixes.

Hot subsystems only (A*, targeting scan and collision in Rust, the rest in Python) is not worth
it. The data lives in Python objects, every crossing pays attribute marshalling, and with a flat
profile Amdahl caps the gain at about 1.5-2x.

Whole tick:

- Size: the engine is about 22k lines of Python. `battle.py` 2.9k, `entities.py` 7.3k, spells
  1.9k, pathfinding 0.8k, cards/mechanics/effects/factory 5.8k, the rest about 3k. torch_sim and
  `rl/` are excluded.
- Cost: **25-40 engineer-days** for the pilot 16 cards at byte parity (a port of about 1.5-2k
  lines a day with agents, plus parity debugging). **15-30 more for C56** (40 new cards, many
  sharing mechanic families). **3-5 days** for the public script and observation encoder in
  Rust, which search needs; without them srp gains only about 2x.
- Parity hazards (all known, all testable):
  - Python `random.Random` (MT19937, `random()`, `randrange` via `getrandbits` rejection); the
    engine uses only `randrange` and `random`.
  - `round()` is round-half-to-even; use `round_ties_even`.
  - Floor versus truncating division and modulo of negatives. The engine already uses
    `trunc_div` explicitly.
  - `math.isqrt` (32 uses).
  - `math.hypot` (1 use): CPython has its own algorithm, so port it.
  - sin/cos (3 uses each): the same macOS libm in both.
  - dict insertion order for entity iteration: use `IndexMap`.
  - Stable sorts.
- Gates: es_pure digests, the c56 p16 identity set (15,949 boundaries), and the native-validated
  scenario suites, all run against the Python oracle.
- Maintenance risk: two engines. Every fidelity fix must land in both. Mitigation: Python stays
  the oracle, new mechanics land in Python first, and CI runs the differential digest suite on
  every engine change.

### (e) More parallelism or a different process layout

- PPO: CPU is saturated. Three seeds at 64/8/4 in worker mode give 88.5 decisions/s in
  aggregate. Running one learner on MPS raises that to 114.7, but MPS memory (8-9 GB per run)
  allows one MPS run at most (`pilot/throughput`). More processes buy nothing: the 12 cores are
  already busy. Learner-mode batched inference on MPS is slower than per-worker CPU inference.
- Search: srp calls are independent, so they scale linearly with free cores. On this host that
  means 5-10 workers next to the PPO runs. That is at most 2x over today's oracle-qualification
  layout and does not reduce cost per call.
- Ceiling: about 1-2x. Useful only as a scheduling decision.

## 4. What a faster simulator buys end to end

| workload | today | engine 1.5x (Cython + fixes) | engine 50x (Rust) | engine + script/obs 50x (Rust) |
|---|---|---|---|---|
| srp call (core-s) | 3.1-3.8 | measured 1.24x (Cython + P1-P5); ~1.6x expected with compiled `rl/` obs | ~1.5-1.9 (2.0x) | ~0.06-0.1 (30-50x) |
| 300 DAgger-labelled battles (core-h) | ~120 | ~95 (~75) | ~60 | ~3-4 |
| PPO single run (dec/s, 64/8/4) | 57.5 | ~59 | ~61 | ~61 (learner-bound) |
| PPO after a learner fix (e.g. update ≤2 ms/dec) | — | ~180 | ~210 | collection then bound by policy inference (~19 CPU-ms/dec), not the engine |

The PPO rows are estimates from the Amdahl shares in 2.2. The learner fix (stored recurrent
state with burn-in instead of full-prefix replay, bigger minibatches) is outside this study's
scope, but nothing else makes PPO decisions/s scale.

## 5. Recommendation and staged plan

**Build a Rust engine core behind pyo3, staged and gated. Ship the free Python-side wins first.
Keep the Python engine as the byte-identity oracle.** Each stage below has a go/no-go
measurement.

**Stage 0: free wins, about 2-4 days.** No semantic change.
- Cython build of the engine modules, plus `rl/public_observation.py`, `structured_obs.py` and
  `action_space.py`.
- Land P1-P5 through normal review.
- Give srp's rollouts a direct-state script path: decide from the battle state without building
  the full public observation, or cache the observation per forked tick.
- Go if: es_pure digests are identical, the c56 p16 check shows 0 mismatches, the native-validated
  16-card suite passes, at least 1.4x fewer engine instructions, and srp core-s per call down at
  least 1.5x on the `es_srp.py` workload with identical chosen actions.

**Stage 1: Rust spike, 5-8 days.**
- Write a `clasher_core` crate: arena, tile map, towers, A*, targeting, collision, movement, combat
  clock, MT19937.
- Port 3-4 simple troops (Knight, Archers, Giant, Musketeer).
- pyo3 `BattleState`-compatible API: `step`, `clone`, `apply_action`, `digest`.
- Differential harness: the same digest format on scripted scenarios.
- Go if: digests are byte-identical over at least 2,000 scenario ticks per card for the slice, at
  least 30x ticks/s per core against CPython on the same scenarios, and clone under 20 µs. No-go
  means stopping at Stage 0 and adding more P-fixes.

**Stage 2: 16-card parity, 20-30 days.**
- All pilot-16 mechanics.
- Python-side shim so `SelfPlayBattleEnv` can choose `--simulation-backend rust`.
- Go if: the p16 identity set shows 0 mismatches over 15,949 boundaries, es_pure random-legal
  digests are identical over at least 20 matches, the native-validated scenario suite passes, and
  the frozen pilot evaluations replay exactly (`oq_check_harness`-style: same outcome, end tick
  and tower HP).

**Stage 3: search stack in Rust, 3-5 days.**
- Public script controller and reward potential in Rust.
- srp rollouts run entirely native, with batched candidate rollouts.
- Go if: srp chosen actions match Python on at least 200 recorded calls, and core-s per call is
  at least 20x lower.

**Stage 4: C56, 15-30 days, in lockstep with the C56 agent.**
- Each new card lands in Python first, validated there, then ports with a per-card differential
  test.
- Go per card family: zero digest mismatches on the C56 scenario screen for that family.

**Stage 5: PPO collection API, 3-5 days, only after the learner recipe is fixed.**
- Vectorised N-env stepping and an observation tensor builder in Rust.
- Go if: rollout decisions/s improve at least 2x end to end with the fixed learner.

## 6. Decisions needed from the user

1. Whether to fund the Rust core: Stage 1 spike (5-8 days), then 16-card parity, search stack
   and C56 (about 45-75 engineer-days in total). The alternative is to stop after Stage 0
   (about 1.2-1.6x).
2. PPO will not speed up from the simulator alone. The learner recipe (full-prefix recurrent
   replay, minibatch of 2 sequences) needs a separate decision and owner.
3. Coordination with the C56 agent: the proposed rule is that new mechanics land in Python first,
   then in Rust, and that C56's p16 identity set becomes the shared parity gate.
4. torch_sim (92k lines, executor disconnected from the env, 6 stale tests): freeze it or retire
   it as a training backend.

## 7. Raw numbers (all in `results/` and `logs/`)

| run | metric |
|---|---|
| `pure_cp312_r1` / `pure_cp314_r1` / `pure_pypy_r1` | 527 / 497 / 393 ticks/s CPU (step-only 585 / 557 / 449); clone 2.88 / 2.10 / 6.35 ms; digests identical |
| `pure_base312_c2_{a,b}` vs `pure_cy_c2_{a,b}` | instructions 524.5G → 392.5G and 524.7G → 377.6G; cycles 135.3G → 96.6G and 129.5G → 85.5G; identical |
| `pure_base_p5i_{a,b}` vs `pure_proto_p5i_{a,b}` | instructions 526.8G → 472.2G and 526.9G → 474.3G; identical |
| `p16_check_{base,proto,cyproto}.log` | 0 mismatches / 15,949 boundaries each; 2,162G / 2,119G / 1,925G instructions |
| `srp_s12` | 3.09 CPU-s per call; engine 51.6%, script observation 29.0%, projection 10.0%, decide 7.0%, clone 1.3% |
| `srp_ab_{main,cyproto}_c{0,8}` | per call 41.7G vs 33.3G instructions; identical actions |
| `rollout_w8_s1` | collect 31.2, update 61.9 CPU-ms per decision; 2.6M-parameter council actor |
| `simplegym_*` | CPU B64 128/128: 8.3; MPS B64 128/128: 40.8; MPS B64 48/64: 74.8; MPS B128 32/32: 215.4; CPU B64 48/64: 58.1 row-ticks/s. MPS B256 128/128 killed at 23 GB. B1024 not run |
| `torchsim_pytest*.log` | 516 passed, 260 skipped, 6 failed |
| `rust_astar` | 2,000 routes: 0 mismatches; 2,813 µs → 54 µs per route |

## Files

- `PROGRESS.md`: resumable log with every command and PID.
- `es_common.py`: digest, sampler, timers.
- `es_classify.py`: subsystem classifier.
- `es_engine.py`, `es_pure.py`: engine drivers.
- `es_rollout.py`: PPO share.
- `es_srp.py`: srp call profile.
- `es_cmp.py`: digest A/B.
- `es_astar_export.py` and `rust_astar/`: Rust micro-port.
- `es_sg_summary.py`: Simple Gym summary.
- `run_*.sh`: launchers.
- `results/`: JSON plus collapsed stacks. `logs/`: raw logs, including `/usr/bin/time -l` output.
- Scratch, outside the repo, at `~/.cache/clasher-engine-speed/`:
  - `proto/` (P1-P5) and `proto_c56/` (P1-P5 on the c56 baseline-src).
  - `cy_base/`, `cy_proto/`, `cy_proto_c56/` (Cython builds).
  - `cp312cy/`, `cp314/`, `pypy/` (venvs).
  - `astar_cases.*`.
