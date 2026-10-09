# Performance audit: search and planning players

Auditor: search/planning area, 2026-10-08. The audit was read-only for code. Measurements ran on 127x08 CPU at nice 19,
in one process with at most 8 threads, on synthetic seeds `2**48+990000…990500` (each checked against
`reports/explore/loss-review/seeds.json`). No eval or heldout data was touched, and no running job was touched. Scratch
lived in `/tmp/sdicks02-perfsearch` on 127x08 and has been deleted. All timings are from Zen2 3990X; Mac numbers are
quoted only from existing receipts.

Overlap with sibling reports: `engine.md` already covers the GIL problem, the `Resources.root` config splice and
allocator churn, and `ops.md` covers the GPU guard. They are restated here only where this audit adds new
search-specific measurements. Those new measurements are live completion counts, build flags, rollout sharing and
script early exit.

## 0. Where the search time goes (measured)

| Quantity (127x08, nice 19) | Value |
|---|---|
| One native C56 rollout (horizon 160, interval 10, 6–11 entities) | 3.0–5.7 ms |
| of which `BattleState.step(160)` without scripts | 1.4–2.9 ms |
| `NativeScripts.select_action` (C56 script), per call | 78–129 µs, 30 calls per rollout |
| One decision: about 20 candidates × 3 styles, fixed budget (U0 / Stage 5 path) | 171–297 ms |
| The same through the S6 Python delay loop (`delay.py`) | 202–317 ms (Python glue +10–15%) |
| `search_candidates` with threads 1/2/4/8 (GIL released) | 183/104/59/38 ms (4.9× at 8) |
| `Resources.root` (public root reconstruction) | 14.1 ms = 9.7 config `json.dumps` + 4.8 Rust parse + deepcopy |
| `C56RolloutPlanner.candidates` (Python) | 2.6–6.4 ms; builds the v5 mask 3× per call |
| Native rollout perf profile, loop window | prepare_route+A* 20.5%, tick_once 14.4%, `rint` 9.6% + mask 6.2% + c56_ranked 2.3% (scripts ≈20–25%), malloc/free/consolidate ≈18% |
| delay-fixes exploration, all 737 games | decisions are 69–84% of game CPU; 33–61 CPU-s per game |
| Stage 5b deadline player (gate-(b) arm A shape) | search p99 161 ms, 84 truncations over all r3 decisions. The 200 ms deadline seldom binds. |

## 1. Ranked opportunities

### #1 Live L2-v4 P3 scorer: the GIL turns 4 roots into fewer than 1. Roots eat 30% of the deadline.

**(a) Files**
- `src/clasher/live/decision.py::RustPlanner.decide/score`: a 4-thread `ThreadPoolExecutor`, with one S6 core per root.
- `reports/strategy_council_20260928/search-noise-s6/delay.py::DelayAwarePlanner.delayed_rollout/score_candidates`, a Python loop over `step`, `select_action` and `apply_discrete`.
- `engine-rs/src/lib.rs::BattleState.step` and `engine-rs/src/scripts.rs` `select_action`/`apply_discrete`/`evaluate`. These hold the GIL; only `search_candidates` calls `py.allow_threads`.
- `stage5/fair_player.py::Resources.root`.

**(b) Evidence**
- I replicated the `RustPlanner.score` logic verbatim, including `DeadlineNative`, with 4 roots, d=27 and a 200 ms deadline, on 3 midgame states with about 20 candidates:
  - Roots take 58–64 ms.
  - Only **1.0 candidate** completes on all four roots with 4 threads.
  - **2.7** complete with a single-thread, candidate-major loop over the same scorer.
- Without a deadline, 4 roots run in 782–1262 ms sequentially and in **1419–2495 ms with 4 threads** (1.8–2.0× slower: convoy on the GIL).
- The same 4 roots through native `search_candidates`, which releases the GIL, take 181–310 ms with 4 Python threads, about one root's cost.
- This matches `live-loop/v4/RUNTIME.md` on 127x04: "2 candidates finished across all four roots in 196 ms".
- Per candidate, `score_candidates(root, seat, [c])` recomputes the 3 opponent first moves: 3 × 20 × 4 = 240 extra `select_action` calls, about 20 ms of GIL-held work.

**Caveat: the Mac receipts may hide this.** The Mac suite (`runtime-results/mac-final/suite/*/latency.jsonl.gz`) shows 440 active searches, a p50 of 55 ms and 1 truncation. However, **67% of all candidate scores there are exactly −2.0**, and in 8 of 12 matches *every* active search scored all candidates −2.0. Rollouts that end in an immediate loss are trivially fast, so the Mac latency qualification probably did not exercise real rollouts.
- Fleet replays with `delay_aware=false` have no −2.0 scores.
- The sample frame shows a princess `Tower` (hp 0.09) detected at the KingTower position.
- Possibly a phantom crown in sudden death. This needs owner verification. It is a correctness flag, not a performance item.

**(c) Expected gain** (affects every live L2-v4 decision, which has a hard 200 ms wall)
- Candidate-major sequential loop: 2.7× completed candidates (measured).
- Root config-JSON splice: −36 ms of the 200 ms on Zen2. The byte-identical payload has `config` as the last key, so `json.dumps(rest)[:-1] + ', "config": ' + CACHED + '}'` produces the same bytes.
- Hoisting the `others` computation: −20 ms of GIL time.
- `py.allow_threads` in `step`/`select_action`/`apply_discrete`/`evaluate`, or a native S6 scorer with internal threads: estimated **15–20 of 20 candidates** complete, versus 1 today. At the measured ≈10 ms per candidate across 4 parallel roots, about 190 ms of budget is left once the roots are cheap.

**(d) Effort**
- Candidate-major loop, splice and others-hoist: 2–3 h, Python only.
- allow_threads build: 1–2 h plus a Mac rebuild and requalification.
- Exact native S6 port: 8–12 h.

**(e) Risk and checking**
- All four changes are score-exact. Completion sets differ, but scores do not.
- Checks:
  - per-candidate score equality against direct S6;
  - action equality restricted to the completed set (the existing RUNTIME parity test does this);
  - payload byte equality for the splice.

**(f) Freezes**
- `delay.py` (sha `96b0637c…`), build48 native `9263a8f7…` and `src/clasher/live/` hashes are "held fixed" by L2-V4-PREREG.md.
- **That PREREG is still DRAFT.** This is the window to adopt the change. Otherwise ship it new-path behind a config flag such as `planner.schedule=candidate_major` or `native_s6=true`, and amend the PREREG.
- Don't edit `delay.py` or `fair_player.py`. Subclass them in a new module.

### #2 Build the native engine with `-C target-cpu=x86-64-v3` for fleet runs (1.25×, digest-identical, no code change)

**(a) Files:** `engine-rs/build.sh` and `Cargo.toml` (`profile.release`). The flag can go in `RUSTFLAGS` at build time.

**(b) Evidence**
- I built a clean copy of the current `engine-rs/src` three times in scratch: baseline, `x86-64-v3`, and `x86-64-v3` with fat LTO.
- I ran 171 rollouts with `trace=True, full_rng=True`. These produce per-decision `hex_digest` plus full Mersenne Twister state, and a final digest.
- **All builds gave identical digests (`b862b081…`).**
- ms per rollout, best of 3:

  | Build | ms per rollout |
  |---|---:|
  | Baseline | 5.34–5.41 |
  | v3 | **4.29** |
  | v3 + LTO | 4.36 (LTO adds nothing) |

- Why it helps: without SSE4.1, every `round_ties_even`/`ceil` becomes a libm call. `rint` alone is 9.6% of loop samples, mostly from the mask's per-tile body rounding.
- Why it stays exact: Rust/LLVM does not contract mul+add to FMA without fast-math, so IEEE results are unchanged.

**(c) Gain:** about 1.25× on all native rollout CPU on the fleet: exploration self-play, future gates, Stage 5-style evaluations, and fleet replay tests. No effect on the Mac (aarch64 has native `frint`).

**(d) Effort:** 0.5 h, plus a run of the existing Stage 5 200-root exact replay and the engine parity tests on the new binary.

**(e) Risk:** low.
- All fleet hosts are Threadripper 3990X (AVX2/FMA present).
- The binary must not be copied to a non-v3 CPU.
- An exact digest check is possible and was done on a sample.

**(f) Freezes:** gate manifests pin `engine-rs/*.so`. Ship the build as a separate directory, for example via the existing `CLASHER_DELAY_NATIVE_DIR` pattern, and only for new runs.

### #3 Fork-at-divergence rollouts across the 3 opponent styles (≈40% of tick work shareable)

**(a) Files:** `engine-rs/src/scripts.rs::search_candidates`, `rollout_until` and `delay_commands.rs::command_simulation`. In Python, `C56RolloutPlanner.score_candidates` and S6 `score_candidates` loop over styles × candidates independently.

**(b) Evidence**
- For each candidate, the three style rollouts start from the same root.
- On 7 midgame roots × 8 candidates, a Python replica of `rollout` gave exactly equal values (168/168) and showed:
  - the opponent's first move was **identical across all 3 styles in 100% of roots**;
  - the trajectories stay identical until the style scripts first disagree;
  - a fork tree saves **40%** of tick work.
- Divergence is late because 61% of script calls have nothing affordable (see #4), and reserve thresholds of 4/7/9 elixir make all styles wait together.

**(c) Gain:** about 1.4–1.6× on rollout CPU. It affects every fixed-budget search: delay-fixes arms, Stage 5/gate players and live.
- Exploration per-game CPU falls about 25–35%, since decisions are 70–84% of game CPU.
- Live and gates gain more completed candidates per deadline.

**(d) Effort:** 6–8 h in Rust. Write a new method, for example `search_candidates_shared`, that advances one state, evaluates the 3 style scripts at each decision, and clones only when the moves differ. Add a test harness.

**(e) Risk:** bit-exact by construction. The engine is deterministic given state, RNG and moves, and `clone` copies the RNG. The check is equality of `trace`/`full_rng` digests and scores against `search_candidates` over a few hundred roots.

**(f) Freezes:** new method only. Don't change `search_candidates` or `rollout`, which are used by frozen Stage 5b, the gates, and the L2-v4 d=0 delegation.

### #4 C56 script early exit and per-call hoists inside rollouts (≈1.1–1.2×)

**(a) Files**
- `engine-rs/src/c56_scripts.rs::c56_ranked`, which always builds `view()` and `mask()` before scoring.
- `scripts.rs::mask`:
  - per tile × body, it computes `round_ties_even` for `blocker_radius`, `b.x` and `b.y` in `occupied()`;
  - the 576-tile `zone` vector is rebuilt per call;
  - the `(0..576).any(…)` ring check is tile-invariant but sits inside the tile loop.

**(b) Evidence**
- 61% of `select_action` calls in rollouts (5,040 sampled) had no affordable card, so the result is always 2304.
- The script/mask work is about 20–25% of loop samples (perf).
- Per call, `view`, `mask` and `zone` allocate `Vec`s (2306 + 576 bools, plus bodies).

**(c) Gain**
- Early exit (check `f32clip(elixir/10)*10 + 1e-6` against hand costs, with the Mirror rule, after `champion_can_activate`): about 10–14% of rollout time.
- Hoisting the per-body rounding and caching zone tables: 3–8% more on non-v3 builds, less on top of #2.
- Computing view+mask once for the 3 styles at shared states pairs naturally with #3.

**(d) Effort:** 2–3 h.

**(e) Risk:** exact if comparisons are replicated literally, with the same float ops. Check with the trace digests as in #2 and with `public_mask` equality against Python (`c56_controller.verify`).

**(f) Freezes:** new binary only.

### #5 Shared delay prefix across candidates (d=27 paths)

**(a) Files:** S6 `delay.py::delayed_rollout`, `delay_commands.rs::command_simulation` (capacity 1), and live P3.

**(b) Evidence (code reading)**
- In S6 and in capacity-1 `rollout_commands`, a non-wait candidate is only *pending* until tick +27.
- Until then the own side makes no decision, so the state for a given style is identical across all non-wait candidates.
- That is 27/160 = 17% of ticks, plus 2 opponent script calls, per (candidate, style).

**(c) Gain:** about 1.15× for the d=27 arms (U27/S27/I0/IF) and live. It composes with #3 into a single prefix tree: one 27-tick trunk per decision, rather than 60.

**(d) Effort:** 3–4 h on top of #3.

**(e) Risk:** exact. The checks are the same as for #3.
- The N2/N4 arms (capacity >1) make own reserved decisions during the delay, so they are excluded.

**(f) Freezes:** new path only. The native `rollout_commands` order (own then opponent execution at the same tick) differs from S6 (opponent then own). Do not swap one for the other without an equality test.

### #6 Allocator churn in rollouts (engine-adjacent; see engine.md)

**(a) Files**
- `lib.rs::prepare_route`: `self.config.costs.clone()`, an 18 KB `Vec<i64>` per route recompute; `route_occupied.contains` is a linear scan.
- `scripts.rs::mask/view`: per-call `Vec`s.
- `Entity::clone`.

**(b) Evidence:** `_int_malloc`, `free`, `malloc`, `malloc_consolidate` and `unlink_chunk` together are about 18% of loop samples. `prepare_route` self-time is 17.5%.

**(c) Gain:** 1.1–1.2× from a `mimalloc` global allocator or thread-local scratch buffers.

**(d) Effort:** 1–2 h for the allocator; 3–4 h for scratch buffers.

**(e) Risk:** exact; allocation does not affect results. Check with the digest test.

**(f) Freezes:** new binary only.

### #7 Python candidate generation redundancy

**(a) Files**
- `src/clasher/rl/c56_rollout_planner.py::candidates`: calls `mask_builder.build` once, then `bot._ranked_actions(all_plays=True)` (mask again, about 2,300 `Decision` objects and a full sort, of which only the top 4 are used), then `bot.decide` (mask a third time).
- `public_action_mask.py::_deploy_zone` is 13 of 19 ms in a 5-call profile.
- The imitation paths (`imitation/evaluation/search.py`, `delay_fixes.imitation_candidates`) call `candidates()` twice, plus a future mask.

**(b) Evidence:** 2.6–6.4 ms per call. About 6–9 mask builds per imitation decision.

**(c) Gain:** −2 to −10 ms per decision. That is 1–5% of exploration decision CPU and 1–3% of the live deadline.

**(d) Effort:** 1–2 h. Write a subclass that builds the mask once and passes it down, and uses `heapq.nsmallest` keyed on `(-score, action_id)`. The existing exact `CachedContractV5ActionMask` can be reused for v1 masks.

**(e) Risk:** exact. Check with `candidates` list equality, including the RNG draw order: `rng.choice` must still be called with the same pool.

**(f) Freezes:** `c56_rollout_planner.py` is pinned by both the gate manifests and the L2-v4 frozen manifest. Subclass it in a new module only.

### #8 IF arm: `hypothetical_packet` parses a 1.9 MB snapshot per decision

**(a) Files:** `src/clasher/analysis/loss_review/delay_fixes.py::hypothetical_packet`, which calls `json.loads(sim.snapshot())`.

**(b) Evidence:** snapshot is 2.7 ms and `json.loads` is 16.7 ms, so about 19 ms per IF decision. The snapshot embeds the full config, and only the entities and own player are read. Over about 286 decisions, that is roughly 5.5 s of the 17.6 CPU-s per game by which IF exceeds I0.

**(c) Gain:** about −9% of IF game CPU. A native entity-only export, like the existing `public_view` (0.006 ms), or a `snapshot(include_config=False)` method would remove it.

**(d) Effort:** 1–2 h, including a new native method.

**(e) Risk:** exact; compare packet arrays byte-for-byte.

**(f) Freezes:** exploration code is running now (delay-fixes shards). Change it only for new runs.

### #9 Exploration wall: the GPU guard (cross-reference ops.md #1)

On 127x08 shard `p0125`, all 26 search workers were SIGSTOPped in 72.7% of guard samples over the last 0.29 h.

- With everything paused, the GRU trainer's GPU averaged 45.5%; only 26% of those samples were ≥80%.
- At audit time the trainer was single-thread CPU-bound at 99% CPU with about 25% GPU, and the box was 98.7% idle.
- Pausing does not raise GPU use, so the guard costs about 3.7× wall on that shard.

Adopt the relative/causal guard proposed in `ops.md`.

### #10 Not recommended now

**GPU-batched rollouts on `torch_sim`.** The simplified engine is neither C56-complete nor bit-exact to the native engine. The search also needs about 60 rollouts × 160 ticks per decision with branching scripts, which is a poor fit for the GPU.

**Learned leaf value to shorten the 160-tick horizon.** This could give 2–3×, but it changes play. Treat it as a research arm with its own preregistration, not a performance fix.

**Transposition or cross-decision caching.** Every decision samples a new opponent hypothesis and a new RNG seed, so roots never repeat. Within a decision, duplicate candidates are already de-duplicated. The only exact sharing is the prefix sharing in #3 and #5.

## 2. Quick wins (under 2 h each, all exact)

1. **x86-64-v3 rebuild for fleet runs (#2): 1.25× rollouts, digest-identical (measured).** 0.5 h plus replay check.
2. **Live P3 candidate-major single-thread loop (#1): 1 → 2.7 completed candidates per 200 ms (measured).** About 1 h. This is pre-freeze; the L2-v4 PREREG is still DRAFT.
3. **Root config-JSON splice (#1, also engine.md): 14 → about 5 ms per root;** −36 ms of every live decision on Zen2, and −2 to −4% of exploration CPU. About 0.5 h.
4. **Hoist the opponent first moves per root in live P3 (#1): −240 `select_action` calls per decision.** 0.5 h.
5. **`py.allow_threads` on `step`/`select_action`/`apply_discrete`/`evaluate` (#1): unblocks the 4-root parallelism.** 1–2 h, plus a new Mac build.
6. **Guard fix (#9, see ops.md).** About 1.5 h.

## 3. Freeze map for this area

**Pinned by the gate (b)/(c) manifests** (`imitation/evaluation/register.py`):
- all `src/clasher/**/*.py`, so `c56_rollout_planner.py`, `public_action_mask.py`, `contract_v5.py`, `action_space.py` and `c56_scripted.py`;
- `engine-rs/*.so`;
- `engine-speed/stage5/*.py` (`fair_player.py`);
- `stage5b-r3/deadline_player.py`.

**L2-v4:**
- `frozen-manifest.json` pins `src/clasher/rl/c56_rollout_planner.py`.
- The PREREG holds fixed S6 `delay.py`, build48 native and `src/clasher/live/`. It is still DRAFT.

**Exploration:** `delay_fixes.py` and `delay_simulate.py` are live in running shards. Use them for new runs only.

**How to ship every item above:** as new modules, new native methods or a separate binary directory, behind a flag. Each one comes with a digest or score-equality receipt against the frozen path.

## 4. Ten-line summary
1. Live L2-v4 P3 is GIL-bound: with 4 roots on 4 threads, only 1 of 20 candidates finishes in 200 ms on Zen2 (measured).
2. The same scorer run single-threaded, candidate by candidate, finishes 2.7, and building the roots takes 60 of the 200 ms; that fix is Python-only and exact.
3. Releasing the GIL in native step/select (1–2 h, exact) should finish 15–20 of 20; adopt it before the L2-v4 PREREG (still DRAFT) is frozen.
4. Flag: in 67% of the Mac suite's active searches, every candidate scores exactly −2.0, so the Mac latency result may not reflect real rollouts.
5. Rebuilding the engine with target-cpu=x86-64-v3 makes rollouts 1.25× faster with identical trace and RNG digests (measured); it takes 0.5 h and needs no code change.
6. The 3 opponent-style rollouts share about 40% of their ticks (measured), so a fork-at-divergence native search would give about 1.4–1.6× exactly (6–8 h).
7. At d=27, the first 27 ticks are identical across all candidates; a shared trunk adds about 1.15× (3–4 h, exact).
8. 61% of in-rollout script calls can't afford any card; an early exit plus mask hoists gives about 1.1–1.2× (2–3 h, exact).
9. The exploration GPU guard keeps 127x08's search workers paused 73% of the time to no effect; fixing it (see ops.md) is the biggest wall-clock win for search experiments.
10. All of these are frozen paths, so ship them as new methods or binaries behind flags, with digest-equality receipts; skip GPU/torch_sim rollouts.
