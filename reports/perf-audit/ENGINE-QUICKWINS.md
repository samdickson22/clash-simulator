# Native engine quick wins: Q6, Q8, Q11

Implemented and measured on 127x04 CPU, 2026-10-09 UTC, with the corrected live qualification replay subsequently measured on 127x08 CPU. No commits made. All builds used Cargo `-j 1`, nice 19; Python used nice 19 with BLAS/OpenMP threads set to 1. The largest benchmark used eight Python workers; the live replay used four workers pinned to CPUs 32–35. No heavy computation ran on 127x05. No access to 02/03, the Mac, or roader paths occurred. Existing binaries and sealed Python files were never written.

## Deliverables and baseline selection

- `engine-rs/Cargo.toml`: new, **off by default** `gil-release` feature.
- `engine-rs/src/lib.rs` / `scripts.rs`: Python bindings call unchanged pure Rust helpers through `native_call`. Without the feature this retains the GIL; with it this uses `py.allow_threads`. Covers `step`, `apply_action`, `select_action`, `apply_discrete`, `evaluate`, `rollout`, and the existing WIP `rollout_commands`. Existing native search workers continue calling helpers directly.
- `engine-rs/build_quickwins.sh`: separate output/build directories, locked release build, approved CPU-host check, v3 capability check, binary/source/toolchain manifest. Refuses an existing binary or target directory. It never calls the in-place `build.sh`.
- `engine-rs/stage_quickwins.py`: copies an archived engine source tree into a fresh directory and applies only the binding change. This handles a deployed binary older than the checkout.
- `engine-rs/quickwin_resources.py`: opt-in `Resources` subclass and `cached_resources(base_class)` factory. No shared module is patched.
- `reports/perf-audit/quickwins/qualify.py`, `test_resources.py`, and `receipts/`: reproducible qualification and measurements.
- `reports/perf-audit/quickwins/benchmark_live_gil.py` and `compare_live_gil.py`: corrected recorded-input full-budget four-root replay and exact comparison across binaries.

**A baseline distinction matters here.** The root-directory binary on both 04 and 08 is build46, SHA-256 `13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309`. The current checkout contains previously committed build48 combat corrections. A build from that checkout differs from build46 in games 200 and 891 of this corpus; one winner changes. This difference is independent of these quick wins: a fresh build without either optimization reproduces it. Build48's archived binary is `78bd9950f1059bddbc2b2d2487158ff5dc51c722500c02969ec100efe1930689`, matching its Stage 5 qualification pins.

Two separate artifact families are therefore provided, under `artifacts/native/engine-quickwins-20261009/` on 05 and `/mpac/sdicks02/tmp/engine-quickwins-20261009-v1/artifacts/` on 04:

| Directory | Combat baseline | Optimization |
|---|---|---|
| `current-gil` | Deployed build46 | GIL release |
| `current-v3` | Deployed build46 | x86-64-v3 |
| `current-gil-v3` | Deployed build46 | Both |
| `baseline` | Checkout/build48 | Neither; comparison control |
| `gil` | Checkout/build48 | GIL release |
| `v3` | Checkout/build48 | x86-64-v3 |
| `gil-v3` | Checkout/build48 | Both |

Use the `current-*` family when the required comparator is the presently deployed binary. Use the checkout family only when build48 is already the admitted comparator. This task does not admit the combat-baseline transition. Every artifact contains a `build-manifest.txt` with its full SHA-256 and source hashes. All supplied binaries are Linux x86-64; **v3 variants are Linux-fleet-only and must never be copied to the Mac or a CPU without v3 support.**

## Exactness receipts

The corpus contains 1,000 independent synthetic seeds, `2**50 + 7000000` through `2**50 + 7000999`, with eight-card decks sampled from the C56 card scope. Each native game runs to a terminal state, at most 6,001 ticks. Records include direct `apply_action` results, the full discrete-action/acceptance hash, winner, final tick, state digest and full MT RNG hash.

Each game's tick-400 root additionally checks one `rollout(trace=True, full_rng=True)` and a two-candidate, three-style traced search: **7,000 native rollouts per binary**. A separate run uses the unchanged S6 `DelayAwarePlanner.delayed_rollout`, d=27, three styles on all 1,000 roots: **3,000 additional rollouts**, comparing scores, command events, leaf digests and complete RNG states. Timing benchmarks also compare deterministic result hashes across 1/2/4/8 workers.

| Aggregate SHA-256 | Deployed build46 and all `current-*` variants | Build48 and all checkout variants |
|---|---|---|
| Games | `7868a665f110370b857478e26195f0a6293938513a1b79859d42f07f8869a2e8` | `aea0b7bab565e912dfbc733f96fae43f59a121b09fcb1e86d2cdb2dd6e0394ce` |
| Native rollout traces | `f52cb3b114d024ddb556c94242ac81f786f2faf6647ab849ce9b7467b199caaa` | Same |
| Complete game/rollout records | `8649ef76e88ab724e4b749110814ac4beffbe52b401568b02fc43d1c823e8453` | `c990d7f6b6fc7264b22300e4291902e35c19fa8da593987f850384e65d4deb09` |
| S6 d=27 traces | `428a7dac04ff84dc87fde74f72bbe770fce81cdb141645855a6f10c2ed50018d` | Same |

`current-comparison.json` and `qualified-comparison.json` are machine-checked comparisons within each family. `current-verify.json` names the deployed binary; `qualified-verify.json` names archived build48. Raw per-game records and scratch inputs remain on 04 under the evidence directory; compact receipts are checked in here.

The checkout `gil-v3` binary ran the existing stage 1/2/3/4 regression modules: **128 passed, one existing fixture-hash failure** out of 129 tests. `test_stage4_b2.B2Regressions.test_stun_resets_special_clock_but_preserves_frozen_target_observation` rejects the current `battle.py` hash before running simulation. The unchanged archived build48 binary and the fresh unoptimized control fail identically; see `parity-suite.txt` and the two `*-known-failure.txt` receipts. The fixture and pinned sources were not regenerated. Two new cache tests pass, covering nested mutation isolation, file-change invalidation and path boundary/tie equality.

## Measured speed

Fixed work: 192 rollouts over 24 tick-400 roots, three timed repeats after warmup. Below is median **wall milliseconds divided by completed rollouts**, not individual request latency. These are shared-host CPU measurements.

| Python-orchestrated rollout | 1 thread | 2 threads | 4 threads | 8 threads |
|---|---:|---:|---:|---:|
| Existing deployed binary | 3.975 | 6.351 | 7.212 | 7.700 |
| `current-gil` | 3.925 | 2.069 | 1.095 | 0.650 |
| `current-v3` | 3.220 | 4.586 | 6.082 | 6.122 |
| `current-gil-v3` | 3.175 | 1.682 | 0.898 | 0.617 |

- GIL release: **3.58× scaling at four threads**, versus 0.55× before; **6.59× throughput improvement at four threads** against the deployed binary. Eight-thread scaling is 6.04×. Single-thread cost is essentially unchanged on this workload.
- v3 alone: **1.23×** for the Python-orchestrated single-thread loop. Direct native single-thread rollout was 3.897 → 3.349 ms (**1.16×**); with GIL release the matched native comparison is 3.879 → 3.125 ms (**1.24×**). This does not reproduce a universal 1.25× improvement. Full qualification wall was 167.95 → 145.30 s, including serialization and trace hashing; that is not a pure engine benchmark.
- Together: **8.03×** four-thread throughput against the deployed binary. Eight threads have more per-call coordination overhead; four workers remain the relevant live-scorer shape.

The S6 d=27 test scores 20 candidates across four private roots, with a 200 ms cutoff, three representative root states and five repeats each. It retains per-candidate opponent-move recomputation. **Roots and candidate lists are prepared before the timer**, so this is scorer-only qualification, not full live-decision latency.

| Variant | Four-thread completed candidates, mean / 20 | Observed range |
|---|---:|---:|
| Existing binary | 1.67 | 1–3 |
| `current-gil` | 15.60 | 12–20 |
| `current-v3` | 2.40 | 1–4 |
| `current-gil-v3` | 18.33 | 17–20 |

No-deadline scores/traces remain exact. Deadline completion sets and resulting choices can change. These synthetic scorer-only numbers do not establish that 18 candidates finish including root construction. Corrected recorded-input full-budget timing follows below; prospective L2 deadline qualification is still required.

## Corrected live four-root replay: GIL priority qualification

Measured on **127x08 CPU**, using the live-runtime worker's read-only qualification tree `/mpac/sdicks02/jobs/clasher/live-perf-20261009-r1`. Input: its `perf-fixes/mac-search-inputs.json.gz`, SHA-256 `82b989c36355633fa61e4a01b3eb579fc38cdcb3c2218b34788afb85177c3c56`. This is the same deterministic 16-decision selection from 440 train recorded inputs used by the worker's `live-perf-qualification-20261009-r2.json`. All **64 corrected roots have both kings and remain nonterminal after one tick**. The old terminal-root fallback timings are not used.

Both runs enable the worker's `public_tower_model`, `cache_root_config`, and `hoist_opponent_moves` flags. They use the unchanged `RustPlanner.score` and sealed S6 delayed scorer, each decision's recorded delay, horizon 160, three opponent styles and the complete candidate list. A nonbinding 120-second deadline permits exact full-budget scores. Root construction remains serial; the parallel schedule submits four independent cores/roots to four Python threads, matching the runtime's existing shape. Warmup is excluded; each decision is measured three times under both schedules, with paired execution order alternating. Empirical p99 describes these 48 observations per schedule, not a production-tail guarantee.

| Binary / schedule | Roots + complete scoring p50 / p99, ms | Full decision p50 / p99, ms |
|---|---:|---:|
| Deployed build46, serial | 1,023.3 / 1,755.0 | 1,033.6 / 1,768.8 |
| Deployed build46, four threads | 1,519.9 / 3,130.3 | 1,532.7 / 3,142.1 |
| Generic `current-gil`, serial | 1,012.4 / 1,744.2 | 1,023.6 / 1,758.9 |
| Generic `current-gil`, four threads | **296.7 / 477.1** | **307.9 / 491.2** |

Full decision includes public parsing, packet construction, candidate generation, root construction, digest checks, scoring and reduction. The worker-compatible column starts at root construction. **GIL release gives 3.32× full-decision p50 scaling over its own serial schedule and 4.98× improvement over the deployed four-thread schedule.** It restores useful root parallelism while keeping serial cost essentially unchanged. Full-list decisions still exceed **200 ms** at p50; GIL release alone does not admit a complete candidate list within that budget. Candidate parallelism/native batching or a qualified partial-list deadline policy remains separate work.

Exact comparison covers **96 execution samples and 7,872 candidate/root scores per binary**: candidate IDs, initial root digests, every score, score hash and selected action are exactly equal across serial/four-thread schedules, repeats and binaries. Both fresh processes use `PYTHONHASHSEED=0`; config, templates, driver, input and live-source hashes also match. Aggregate result SHA-256: `86474221e979a2a0b06feda40e43a02946dc6c953ef8d8eced4a8e8fc134d2ba`. Binary SHA-256: deployed `13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309`; GIL-only `936beb7df75c36fea3121ad4ca460e648c5069d75c9cb1a0ad5145dfb2cd79a2`. No v3 or startup-cache change is included in this measurement.

**Older receipt discrepancy:** the stored worker score vectors differ on three decisions (`1975100700`, sequences 3275, 4524, 5086), including when replayed with the unchanged deployed binary. Both fresh binaries reproduce the same vectors exactly. The earlier failure and all previous/current vectors are preserved in the scratch directory and receipts; this task does not resolve the historical discrepancy or claim equality to that older receipt. The accepted GIL comparison is against fresh serial results with identical recorded inputs, roots and candidates.

The benchmark used nice 19, CPU affinity 32–35, four workers, empty `CUDA_VISIBLE_DEVICES`, and one Torch/BLAS/OpenMP/Rayon thread. GRU protection observed the trainer's own `rows_per_second_step`, stopping only this benchmark if the median of the latest three intervals fell more than 5%. No stop occurred. Median last-five throughput was **234.93 → 235.12 rows/s** across the deployed run and **235.12 → 235.12 rows/s** across the GIL run; no throughput reduction was observed. Qualification sources and the protected binary were hash-checked unchanged. The qualification tree, GPU job and existing binaries were never written.

The opt-in GIL-only binary and all raw evidence are in the new path `/mpac/sdicks02/jobs/clasher/engine-gil-live-20261009-r1/` on 08. Binary: `native-gil/clasher_core.abi3.so`. Checked-in evidence: `quickwins/receipts/live-gil/{baseline-live-r2,gil-live-r2,live-comparison-r2}.json` plus samples/logs. To repeat, use fresh output paths, CPU affinity and nice settings as above, the qualification tree's `src` and `engine-rs` on `PYTHONPATH`, and import the selected native binary before `RustPlanner` loads supporting modules. For GIL release, prepend the new binary directory; for the baseline, use the qualification tree's existing native directory. Run:

```bash
nice -n 19 taskset -c 32-35 env PYTHONHASHSEED=0 CUDA_VISIBLE_DEVICES= \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1 \
  /mpac/sdicks02/envs/clasher-gpu/bin/python -B benchmark_live_gil.py \
  --qualification /mpac/sdicks02/jobs/clasher/live-perf-20261009-r1 \
  --reference /mpac/sdicks02/jobs/clasher/live-perf-qualification-20261009-r2.json \
  --output NEW_RECEIPT.json --label CHOSEN_BINARY \
  --trainer-log /mpac/sdicks02/tmp/t5-20261008-r2/fresh-runs/gru-2026100801/train.jsonl
nice -n 19 /mpac/sdicks02/envs/clasher-gpu/bin/python -B compare_live_gil.py \
  BASELINE_RECEIPT.json GIL_RECEIPT.json NEW_COMPARISON.json
```

## Resources startup cache

The new module caches the unmodified tower loader by resolved data-file path, nanosecond mtime, size and inode (`maxsize=16`), returning a deepcopy of its nested result. Path IDs use an LRU keyed by the same three integer arguments (`maxsize=65536`). Cached battle/arena subclasses are used only by private exporter namespaces and the inherited sealed initializer. Shared `fair_player`, `differential`, `BattleState`, and arena functions remain unchanged, including when initialized concurrently by another consumer.

Final measurement: **24.23 s baseline → 11.52 s first cached initialization → 10.89 s warm initialization**, a 2.10× cold-start improvement. An earlier repeat was 23.81 → 11.41 → 10.88 s. There were 805 tower-cache hits/one miss and 8,744 path-cache hits/2,496 misses across two cached initializations.

All three initializations produce identical config, metadata and 168 templates. Config hash: `15f363ed0baba86e48ef76085fce771001f0d6d44734fa4be61eb7ed4a4e3e34`; template hash: `609640f36bee6711c211a53a2e6cc9bea77040b87002e392d5e7f044388107c8`. Metadata equality is checked within each run, preserving that process's existing token metadata. See `final-cache/resources.json`. No disk cache was added. `clear_startup_caches()` supports deliberate in-process data replacement; `Resources.root` is inherited unchanged.

## Usage and adoption

New exploration runs may select the strict deployed-baseline v3 binary with the existing flag:

```bash
export CLASHER_DELAY_NATIVE_DIR="$PWD/artifacts/native/engine-quickwins-20261009/current-v3"
# Run the existing delay_simulate command with its ordinary arguments.
```

For a general new process, put the chosen binary directory first on `PYTHONPATH` and import `clasher_core` before support code that inserts another native directory. Verify `clasher_core.__file__` and its manifest hash. Single-process fork-pool exploration should primarily adopt v3 and cached startup; GIL release helps consumers with Python threads rather than ordinary one-thread-per-process workers.

Opt-in startup, with `engine-rs`, `src`, and `engine-speed/stage5` available on `PYTHONPATH`:

```python
from quickwin_resources import Resources
resources = Resources()

# For a separately loaded fair-player Resources class:
from quickwin_resources import cached_resources
resource_class = cached_resources(resource_class)
resources = resource_class()
```

Use those imports in a **new consumer driver/adapter**. Existing exploration drivers still import sealed `fair_player.Resources`; merely adding this module to `PYTHONPATH` does not opt them into caching. No current driver, running job, or sealed file was changed by this task.

Apply the startup factory to the sealed base class before composing separate root-serialization wrappers.

To reproduce a checkout build on an approved CPU host:

```bash
export CARGO_HOME=/mpac/sdicks02/tools/cargo
export RUSTUP_HOME=/mpac/sdicks02/tools/rustup
export PATH="$CARGO_HOME/bin:$PATH"
export PYO3_PYTHON=/mpac/sdicks02/repos/clasher/.venv/bin/python
bash engine-rs/build_quickwins.sh gil-v3 artifacts/native/NEW_VARIANT
```

To preserve the current deployed combat baseline, first stage its archived source:

```bash
nice -n 19 "$PYO3_PYTHON" engine-rs/stage_quickwins.py \
  reports/strategy_council_20260928/engine-speed/stage6/build46-linux/engine-rs \
  /mpac/sdicks02/tmp/NEW_QUICKWIN_SOURCE
cd /mpac/sdicks02/tmp/NEW_QUICKWIN_SOURCE
bash engine-rs/build_quickwins.sh gil-v3 /mpac/sdicks02/tmp/NEW_QUICKWIN_BINARY
```

Qualification commands are `prepare`, `verify --label LABEL`, `delayed-corpus --label LABEL`, `bench --label LABEL`, `delayed --label LABEL`, and `compare --reference current --variants current-gil,current-v3,current-gil-v3` in `quickwins/qualify.py`. Run each label in a fresh process with its native directory first and Stage 5/S6 support directories available. The comparison requires ≥1,000 game roots and both rollout receipts and fails on any digest mismatch.

**Future gates:** use a newly registered snapshot, manifest and binary path. Prefer v3 plus cached startup for fleet runs. A threaded scorer may additionally opt into GIL release, with its timing admission repeated. The running (b)/(c) snapshots remain untouched; no result from them is reinterpreted.

**L2-v4:** after its PREREG explicitly selects the binary/feature and any changed deadline behavior, adopt **generic `current-gil` first** to retain its deployed build46 comparator and enable its existing four-root thread pool. The corrected live replay above qualifies exact full-budget scores and records the remaining 200 ms gap. Fleet `current-gil-v3` can follow its own recorded-input timing qualification; cached startup can compose through the new resource factory. Requalify completed-set action parity and deadline overruns separately. Mac usage requires a separately built and qualified Mac-native GIL-release binary; this task neither builds nor transfers one. The v3 artifacts are never a Mac option.
