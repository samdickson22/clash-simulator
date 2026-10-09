# Perf audit: simulators (Python engine, Rust `clasher_core`, harnesses)

Auditor: engine lane, 2026-10-08/09. Code was read-only. All measurements ran on **127x08 CPU**: at most 4
concurrent processes, nice 19, `/tmp/sdicks02/perfaudit` (now deleted), synthetic seeds `2**50+k` with
train-prior decks only. No eval, heldout or frozen data, and no running job, was touched. The 08 GPU (GRU) was
at 99% before and after. 08's checkout is `db1d17a` + WIP. `battle.py`, `entities.py` and `pathfinding.py` are
byte-identical to 05's; `lib.rs` and `scripts.rs` differ only by the delay-fixes opt-in method.

## 0. What actually costs wall-clock (measured)

**One exploration sim game** (`loss_review/simulate.run_game`, S6 planner, single thread, fixed budget). These
are 4 games instrumented with wrappers, without cProfile:

| part | d0 g1 | d0 g2 | d27 g1 | d27 g2 | share |
|---|---|---|---|---|---|
| total game CPU (s) | 28.95 | 20.32 | 19.79 | 18.35 | |
| native search (`score_candidates`) | 17.81 | 12.43 | 11.97 | 11.13 | **~61%** |
| Python engine `BattleState.step` (outer game) | 6.22 | 3.25 | 3.94 | 2.93 | 16-21% |
| `build_public` (contract-v5 packets, 1.1-1.3 ms each) | 1.90 | 1.63 | 1.53 | 1.55 | 6-8% |
| `Resources.root` (public root, ~15 ms each) | 1.07 | 1.09 | 0.82 | 1.05 | 4-5% |
| `candidates` (Python mask, rank, script) | 1.00 | 1.01 | 0.67 | 0.78 | 3-5% |
| Python scripted opponent | 0.35 | 0.37 | 0.31 | 0.39 | 2% |
| **per-launch `initialize()` (Resources)** | **25.3** | 25.3 | 25.5 | 25.5 | paid once per launch, before fork |

**Microbenchmarks (08, one core):**

| quantity | value |
|---|---|
| Rust `BattleState.step` | 74k-140k ticks/s (the 8-13 entity roots); ~65k ticks/s averaged inside the d27 game |
| Python engine step | 1,000-2,750 ticks/s (whole scripted game 1,008 ticks/s; 6,001 ticks in 5.95 s) → **Rust ≈ 50-110×** |
| Native rollout (160 ticks, 30 script calls) | 3.9-4.3 ms. Engine ≈ 55%, native C56 script (`view`+`mask`+`c56_ranked`) ≈ 45% |
| Native `select_action` at a root (affordable hand) | 82-102 µs. Inside rollouts the average was 14.5 µs (146k calls), because most calls have no affordable card |
| Native clone | 3-5 µs. Python clone: 1.4 ms |
| Native search, 20 candidates × 3 styles | 244-275 ms at 1 thread; 135-153 ms at 2; 73-80 ms at 4 (3.4× at 4) |
| **`Resources.root()`** | **15.0-15.6 ms**: `json.dumps(config)` 9.8-10.2 ms (config is **1.49 MB** of JSON on every call), Rust re-parse 4.8 ms (1.9 MB snapshot) |
| Imports | numpy+torch 2.1 s, `clasher.battle` 0.62 s, `c56_controller.resources()` 0.46 s, **`fair_player.Resources()` 23.9 s** |

**Rust hot spots** (`perf`, launched under perf because `ptrace_scope=2`; native search loop over 13 public roots;
shares of native time):

| hot spot | share |
|---|---|
| allocator churn (`malloc`/`_int_malloc`/`free`/`consolidate`/`RawVec::finish_grow`/`memmove`) | **≈23%** |
| `NativeScripts::mask` + `rint` + `ceil` + `c56_ranked` | **≈23%**, mostly per-tile, per-body `round_ties_even` in `occupied()` |
| `tick_once` self time (inlined combat/movement) | ≈15% |
| `prepare_route` + `astar::find` | ≈12% |
| `Entity::clone` | ≈3-4% |
| `target`, avoidance | ≈5-7% |

**GIL measurement (decisive for the live loop).** The S6 delayed rollout shape is a Python loop that calls native
`select_action`/`apply_discrete`/`step(10)`:

| configuration | throughput vs 1 thread |
|---|---|
| 2 threads | **0.61×** |
| 4 threads | **0.50×** |
| `search_candidates` (calls `py.allow_threads`) at 4 threads | 3.82× |

Only `search_candidates` releases the GIL (`scripts.rs:645`). `BattleState.step`, `select_action`,
`apply_discrete`, `evaluate`, `rollout` and `rollout_commands` all hold it.

**Exploration duty cycle.** The delay-fixes receipts (1,000 games) show wall/CPU ≈ 1.6 (mean wall 51-100 s vs
CPU 33-62 s). The `--gpu-guard` logs on 08 explain it:

| shard | sim paused | GPU while paused | GPU while sim running |
|---|---|---|---|
| p0125 | 73% of samples | 46% | 100% |
| p0150 | 61% of samples | **1%** | 98% |

The guard pauses the sim when the GPU job dips on its own. It does not protect anything.

## 1. Ranked opportunities

Ranking is by wall-clock impact on what runs now or soon: exploration and robustness sim A/Bs, the L2-v4 live
loop and its S-d sim arms, future gates. Gates (b)/(c) run from the frozen `runtime-bc-v1` snapshot and are
deadline-paced (200 ms per search). No engine change can speed them up, and none may touch them.

### #1 GPU-guard duty cycle in exploration sims (harness) — QUICK WIN
- **(a) Files:** `reports/explore/search-ab/gpu_guard.py`; the `GPUWatch` in `src/clasher/analysis/loss_review/delay_simulate.py:242`
  (`--gpu-guard`). Both SIGSTOP the whole group on any single 2 s sample under 80% and resume only after 5
  consecutive samples at or above 80%.
- **(b) Evidence:** see the duty-cycle table in section 0. p0150 had the GPU at 1% while the sim was stopped:
  the dips are the GRU's own phases (eval, checkpoint, loader), not CPU contention. Overall wall/CPU is 1.6.
- **(c) Speed-up:** **1.3-2.5×** on exploration-sim wall on GPU-sharing hosts (08, leased hosts with perception
  jobs). It affects the exploration A/B, delay-fixes and the upcoming robustness and S-d sim batches.
- **(d) Effort:** 1-2 h. Make the guard causal: on a dip, pause; if the GPU has not recovered within 10 s,
  resume and suppress the guard for 5 min. Alternatively, use a 60 s rolling median, or detect GPU-job CPU
  starvation directly (loader D-state / run-queue).
- **(e) Risk:** none to results (scheduling only). Bit-exactness is irrelevant.
- **(f) Frozen dependency:** none. These are exploration-lane scripts; coordinate with that lane's owner.

### #2 Release the GIL in native per-call methods (Rust bindings) — QUICK WIN (code); amendment needed for L2-v4
- **(a) Files:** `engine-rs/src/lib.rs:3493` `BattleState.step` (also `apply_action`), and
  `engine-rs/src/scripts.rs` `select_action`, `apply_discrete`, `evaluate`, `rollout`, `rollout_commands`.
  Wrap the bodies in `py.allow_threads`. Consumers: `src/clasher/live/decision.py:58-158` `RustPlanner` (4 Python
  threads × `DelayAwarePlanner` d=27, Python-orchestrated `delayed_rollout` in `search-noise-s6/delay.py:90`),
  and any S-d sim arm reusing that scorer.
- **(b) Evidence:** measured 4 threads = 0.50× of one thread on this exact call shape. That is worse than serial,
  because of GIL convoying. With the GIL released, `search_candidates` reaches 3.82× at 4 threads.
- **(c) Speed-up:** about **4-7.6×** more completed rollouts per wall second in the live P3 scorer (from 0.5×
  serial to about 3.8×). It cuts L2-v4 decision latency, or completes more candidates within the 200 ms
  deadline, and gives the same speed-up to S-d/L2 sim arms that use `RustPlanner`. No effect on single-thread
  fork-pool sims.
- **(d) Effort:** 1-2 h of code, plus a rebuild and the parity suite (`test_parity.py`, stage 2/3/4 tests).
  PyO3 0.23 `allow_threads` on `&mut self`/`&self` pyclass methods is fine: borrow flags still guard aliasing.
- **(e) Risk:** results are bit-exact per call, because the GIL does not touch native state. Equality check:
  identical digests and identical score vectors on a fixed root corpus with no deadline. Under a deadline the
  *set of completed candidates* grows, so decisions legitimately change. That is a declared behaviour change,
  not a bug.
- **(f) Frozen dependency:** **yes.** The L2-v4 runtime and PREREG pin the planner ("S6 delay-aware, K=4 roots …
  200 ms"). Ship it as a new extension filename/runtime dir behind a flag, and request a prospective PREREG
  amendment before L2 starts. Never replace `engine-rs/clasher_core.abi3.so` in place: delay-fixes workers on 08
  import it right now (`PYTHONPATH=…/engine-rs`).

### #3 Public-root construction re-serializes a constant 1.49 MB config on every root — QUICK WIN
- **(a) Files:** `reports/strategy_council_20260928/engine-speed/stage5/fair_player.py:111-174`
  `Resources.root` (`json.dumps(dict(..., config=self.config))`) and `lib.rs:3480` `BattleState::new` (full
  serde parse, including config).
- **(b) Evidence:** 15 ms per root = 10 ms dumps + 4.8 ms parse + ~0.4 ms template deepcopies. I verified a
  splice (`json.dumps(state)[:-1] + ', "config": ' + CACHED_CONFIG_JSON + '}'`): **36/36 payloads
  byte-identical**, at 0.67 ms instead of 10 ms. The live `RustPlanner.decide` builds **4 roots serially inside
  the 200 ms deadline (≈60 ms, 30% of the budget on 08-class cores)**. Exploration: 4-5% of game CPU.
- **(c) Speed-up:**
  - Step 1 (Python splice): 15 → ~5.5 ms per root.
  - Step 2 (a Rust `BattleState.from_state(state_json, config_source)` sharing `Arc<Config>` from a prebuilt
    handle): → ~1 ms.
  - Live: returns ~55 ms of the 200 ms search budget. Exploration: −4% CPU per game.
- **(d) Effort:** step 1 is 0.5 h; step 2 is 3-4 h.
- **(e) Risk:** step 1 is byte-identical (string equality check, done). Step 2 is exact if the digest of the
  constructed state equals the old path's digest; check this on ≥1,000 roots.
- **(f) Frozen dependency:** **yes.** `fair_player.py` is sealed Stage 5 code, used by gates (frozen snapshot
  copy) and live. Implement it as a subclass/new module (e.g. `fast_root.py`, `Resources` subclass) and opt in
  from exploration and L2 code. Never edit the sealed file.

### #4 `Resources()` startup is 24-25 s per process/launch — QUICK WIN
- **(a) Files:** `fair_player.py:39-109` `Resources.__init__`. Its biggest costs:
  1. `differential.config()` (`engine-rs/differential.py:385`) calls `initial()` 403 times. Each
     `BattleState.__post_init__` → `_create_towers` → `battle.py:346 _load_princess_tower_character_data`
     **re-reads and re-parses the 3.1 MB `gamedata.json`** (≈22 ms; ≈9 s total).
  2. `native_tilemap.py:103 nearest_native_path_id` is a pure-Python 36×64 scan at ≈1 ms per call (2,304 calls
     for `lane_ids` plus every spawn).
  3. 56 demo battles × 201 Python ticks (≈11k ticks, ~60% of init).
- **(b) Evidence:** cProfile (57 s instrumented, 24 s real): ticks 36 s, `config()` 16 s, `json` decode 9 s,
  `nearest_native_path_id` 5.3 s. In fork-pool sims the whole host idles during init: 25 s × 26-96 workers per
  launch. delay-fixes launched ≥10 shards on 08 alone. Gate workers pay it per process.
- **(c) Speed-up:**
  - Option A: `lru_cache` on the tower-data loader (keyed by path + mtime) and on `nearest_native_path_id`
    (keyed by its 3 integer args) → init ≈24 → ≈10 s.
  - Option B: a pickle/marshal cache of `(templates, config, meta)` keyed by SHA of the source files, gamedata
    and `.so` → ≈1 s.
  - Exploration launches: 25 s × N-worker idle per shard removed (≈5-10% of a 300-400 s shard wall).
- **(d) Effort:** A is 1 h; B is 2-3 h.
- **(e) Risk:**
  - A is exact: both functions are pure. Check: `json.dumps(config)` and template-dict digests are equal before
    and after.
  - B is exact if the cache key is complete. A stale cache is the risk, so include all source hashes.
- **(f) Frozen dependency:**
  - The `battle.py` and `native_tilemap.py` edits change Python files that gates' `runtime-bc-v1` *copies* (not
    imports). Main-repo edits are safe for gates, but must pass the Python↔Rust parity suite. Pure caching keeps
    all digests.
  - Option B lives in new code (a `Resources` subclass).

### #5 Native C56 script mask: hoist per-body geometry out of the 2,304-tile loop (Rust)
- **(a) Files:** `engine-rs/src/scripts.rs:93-131` `occupied()` (3× `round_ties_even` + `ceil` per body **per
  tile**), `scripts.rs:250-360` `mask()`, `c56_scripts.rs:20-205` `c56_ranked`, `scripts.rs:164` `view()`
  (per-call alloc + sort).
- **(b) Evidence:** script work is ≈23% of native time (mask 10-11%, `rint` 6-7%, `ceil` 1.5%, `c56_ranked`
  4-5%). Complexity is O(4 cards × 576 tiles × n_bodies) rounding ops per call (~26k `rint` per affordable card
  at n≈15). `public_mask_v2.rs` already precomputes building geometry, so it is the template.
- **(c) Speed-up:** native rollouts ≈1.15-1.25×, so native search and every rollout consumer gain the same
  (exploration games −10-13% CPU, live search more candidates).
- **(d) Effort:** 3-4 h.
  - Precompute `(bx, by, bh, r)` per body once per view.
  - Compute the "any free zone tile" `any()` once per (slot, radius), not once per blocked tile.
  - Add an exact "no affordable card → 2304" fast path *after* `champion_can_activate`, keeping the Mirror
    cost rule.
- **(e) Risk:** low. Exact if the same float expressions are computed once instead of repeatedly (no
  reassociation). Checks:
  - `public_mask` equality against the current binary on ≥100k roots (the mask-v2 parity harness exists).
  - Identical `search_candidates` scores/digests.
- **(f) Frozen dependency:** the extension is shared. Build to a new path or module and gate it by flag/runtime
  dir. Gates use their own snapshot `.so`.

### #6 Native allocator churn: reuse buffers in A*, routing and avoidance (Rust)
- **(a) Files:**
  - `engine-rs/src/astar.rs:135-170` `find` allocates 5×2,304-element vectors plus a heap per call.
  - `lib.rs:1581` `prepare_route` clones `config.costs` (2,304 i64) per route.
  - `lib.rs:1818` `avoidance_grid` builds 576 `Vec`s per tick and grows them by push.
  - `lib.rs:1844` `update_avoidance` does a full `Entity::clone()` per troop per tick.
  - `lib.rs:2599` `occupied()` does `vec![false; 2304]` per tick, plus `cells`/`signatures` collects.
- **(b) Evidence:** `malloc`/`free`/`finish_grow`/`memmove` ≈23% of native samples (DWARF call graphs attribute
  most of it to `RawVec::finish_grow` and to `calloc`/`free` from `tick_once`). `Entity::clone` is 3-4%.
- **(c) Speed-up:** native ≈1.15-1.3× (on top of #5; together ≈1.3-1.5× on rollouts).
- **(d) Effort:** 4-6 h. Use thread-local scratch for A*, a cost overlay instead of a clone, a flat bucket
  array (or a cleared, reused grid kept in `BattleState` and `#[serde(skip)]`), and borrow the needed fields
  instead of cloning the entity.
- **(e) Risk:** low-medium. It is pure memory management and exact if the iteration order of buckets is kept;
  bucket order affects avoidance results, so keep push order. Check: full-game digests (`stage2_matches`,
  stage 4 C56 matches) and rollout trace digests equal to the current binary.
- **(f) Frozen dependency:** same as #5. Ship as a new binary path.

### #7 Outer sim game in Python: 16-21% of sim CPU
- **(a) Files:** `simulate.py` loop (`b.step()` on the Python `BattleState`, `battle.py:727-905`) plus
  `contract_v5.build_public`.
- **(b) Evidence:** 2.9-6.2 s per game on the Python step and 1.5-1.9 s on `build_public`. Simulate builds the
  same seat's packet twice on decision ticks: telemetry at `tick%5` and `observe()` at `tick%10`. That is about
  350 duplicate builds, ≈0.4 s per game.
- **(c) Speed-up:**
  - (i) Cache the packet per `(tick, seat)` in the harness: −2%, 0.5 h, exact.
  - (ii) Cython-compile the unchanged `src/clasher` (measured 1.40-1.51× fewer cycles, byte-identical digests,
    `engine-speed/README.md` §3a, `build_cython.py` exists): −5-7% per game, 1 day including packaging.
  - (iii) Run the outer game natively. This needs a native contract-v5 packet builder and is 3-5 days. It would
    remove ≈25% of sim CPU and make scripted-only games ~50-100× faster.
- **(d) Effort:** as above.
- **(e) Risk:**
  - (i) none.
  - (ii) low: proven byte-identical before; re-run es_pure/p16_identity.
  - (iii) high: new parity surface for packets.
- **(f) Frozen dependency:** the Python engine is the authoritative oracle, so never edit it for speed without
  the parity suite. (ii) and (iii) must be opt-in runtimes.

### #8 Fork-pool tail and scheduling in sim harnesses
- **(a) Files:** `simulate.py:206` / `delay_simulate.py:240` `pool.map(..., chunksize=1)` in schedule order.
- **(b) Evidence:** game CPU varies 18-62 s (the arms differ; I0/IF are 1.8× S0). A shard with 200 games on 26
  workers ends with a straggler tail of up to about 1 game length (~60-100 s of mostly idle workers per shard).
- **(c) Speed-up:** 3-8% of shard wall. Submit the longest arms (I0/IF, full-length seeds) first, or run one
  long-lived pool across shards instead of per-shard launches. The latter also removes repeated init (#4).
- **(d) Effort:** 1 h.
- **(e) Risk:** none. Order does not affect per-game results (all seeds are explicit per case).
- **(f) Frozen dependency:** none (exploration lane).

### #9 Not recommended (skeptical notes)
- **torch_sim / batched GPU games.** 92k lines; no current consumer (last commit 2026-10-04; only Sept hog26
  probes). It is not byte-identical by design. Measured earlier at 8-41 row-ticks/s (CPU/MPS) vs ~700 for one
  Python core, and it is now ~2,000× behind Rust (~100k ticks/s/core). With ~1,400 idle cores, CPU Rust gives
  ≈10^8 ticks/s fleet-wide. GPU vectorization of this branch-heavy rule engine is not competitive. Freeze it.
- **Python↔Rust call overhead.** Measured as negligible single-threaded: a Python-orchestrated S6 rollout is
  3.86 ms vs 4.28 ms for an in-native rollout on a similar root mix. The problem is the GIL (#2), not the
  crossing.
- **Native clone (3-5 µs) and `index(id)` linear scans** (n≈10-30): not worth touching.
- **Python-engine algorithmic micro-fixes** (P1-P5 from the engine-speed study): 1.11× on a component that is
  16-21% of sim CPU, i.e. ≈2%. Skip unless bundled with #4/#7(ii).
- **Gates (b)/(c).** They are wall-bound by the 200 ms deadline × ~300-400 searched decisions per game plus
  ~6-9 s of Python outer game. No engine work changes their wall. Throughput there is a concurrency/timing-
  admission question (ops lane).

## 2. Parity constraints (how to change the engines safely)
- Python `src/clasher` is the authoritative oracle. Rust is admitted per stage by digest identity: stage 2 has
  64 terminal games, 2,048 live imports and exhaustive masks; stage 3 has 3,999 candidate traces; stage 4
  covers C56. Every change must reproduce `hex_digest`, rollout trace digests and the full-RNG hash exactly
  against the current binary. Float reassociation breaks this, so only hoisting identical expressions,
  memoizing pure functions, reusing buffers and releasing the GIL are "free".
- Checks to rerun:
  - `engine-rs/test_parity.py`, `test_stage2.py`, `test_stage4*.py`, `stage2_matches.py`;
  - the mask-v2 ≥100k-state parity harness for #5;
  - a new A/B digest diff of `search_candidates(..., trace=True)` on ≥1,000 fixed roots, old `.so` vs new;
  - `json.dumps(config)` and template digests for #3/#4.
- Deployment rule: build to a new module or file in a new runtime dir; never overwrite
  `engine-rs/clasher_core.abi3.so` while any job imports it (README; live delay-fixes jobs on 08 do).

## 3. Quick wins (<2 h each)
1. #1 causal GPU guard: 1.3-2.5× exploration wall on shared hosts.
2. #2 `py.allow_threads` in the per-call native methods: 4-7.6× live-scorer throughput. Flagged binary plus a
   PREREG amendment for L2-v4.
3. #3 step 1, cached-config splice in a `Resources` subclass: byte-identical (36/36 verified); root 15 → 5.5 ms;
   frees ~40 ms of the live 200 ms budget.
4. #4 option A, `lru_cache` on `_load_princess_tower_character_data` and `nearest_native_path_id`: init
   24 → ~10 s, exact.
5. #7(i) per-tick packet cache in simulate: −2% per game, exact.
6. #8 longest-first submission / persistent pool: −3-8% shard wall.

## 4. Ten-line summary
1. Sim game CPU: ~61% native search, 16-21% Python outer engine, 6-8% packets, 4-5% root rebuild; init 25 s per launch.
2. Biggest wall loss is not code: the exploration GPU guard SIGSTOPs sims 45-73% of the time, while the GPU sits at 1-46% anyway.
3. A causal guard (pause, check recovery, back off) is 1-2 h and gives 1.3-2.5× on exploration wall on shared hosts.
4. Live L2-v4 scorer: Python-orchestrated native calls hold the GIL, so 4 threads run at 0.50× of one thread (measured).
5. `py.allow_threads` in step/select/apply/evaluate is exact and 1-2 h; expect 4-7.6× scorer throughput (new binary + PREREG amendment).
6. `Resources.root` re-dumps a 1.49 MB config per root (15 ms; 60 ms of each live 200 ms decision). A byte-identical splice is verified 36/36.
7. `Resources()` takes 24 s because it re-parses the 3.1 MB gamedata.json 404 times plus a slow path-id scan. lru_cache gives ~10 s; a pickle cache gives ~1 s.
8. Rust hot spots: ~23% allocator churn (A*, avoidance, entity clones) and ~23% script mask rounding. Together ≈1.3-1.5× on rollouts, exact.
9. Keep Python as the oracle. Ship native changes only as new binaries proven digest-identical; gates' frozen snapshot is unaffected.
10. Don't invest in torch_sim/GPU batching (≈2,000× behind Rust per core) or Python micro-fixes (≈2%); gates are deadline-bound.
