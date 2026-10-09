# B6: one prepared Mac E4 measurement session

Coordinator: `0523ae6f`. Prepared on Linux; **no Mac access or measurements have occurred**. Run only after Sam authorizes this particular Mac session. Budget approximately **60–90 minutes**, assuming the recordings, artifacts and an existing native arm64 Python environment are staged first. Preserve an incomplete session if prerequisites or timings exceed this allocation; do not shrink the registered sample or repeat packets to claim a pass.

This is a public-frame, train-only replay experiment, not ladder play. Scripts contain no actuator, device controller, taps, account login or networking. The in-memory command sink cannot control the client. Any emulator use is limited to Sam-owned offline replay/capture; Sam must arrange it under `live-play-authorization`. Its earlier authorization does not authorize this worker to access the Mac. Keep the offline reference emulator isolated from the official client. No client memory reads, hidden opponent decks, validation/heldout measurements, detection evasion or randomized concealment timing.

## What is measured

1. Four paired cells: W-screen8 explicitly OFF/ON × **four roots on one/four executor threads**, using one newly built GIL-release W library. All cells use real `RustPlanner.decide`, public root reconstruction, candidate generation, native rollouts and complete-candidate reduction. One thread serializes the same four roots; it does not reduce K. Deadlines include public packet construction, all four root constructions and reduction; 5 ms reserve remains the production implementation's choice.
2. Original and isolated vectorized `V4Perception` on the same chronological train pixels, alternating AB/BA. Full P1 timing includes preparation, forward, host transfers, tracking, event fusion and tower/crown/result work, with MPS synchronization before/after. Both complete raw decoder records and fused public outputs are compared, excluding **only availability clocks**. Capture/video decode is separately timed. First 16 frames per recording stay in raw receipts and have separate cold distributions; initialization is also retained. First decisions of new planners are labelled separately; the parent process has already been warmed by preparation, so these are not cold OS/process starts. Four additional native/planner samples use fresh spawned interpreters under the same replay load (one per cell), recording import/setup, constructor and first-decision latency; OS/file caches are uncontrolled. These descriptive single samples are retained under `cold/` and do not provide a cold-start p95 estimate.
3. `TowerChannel.step`: all six public slots on actual sanitized pixels. The integrated P1 tower/crown/result adapter has its own distribution; no <2 ms target is applied to the larger combined adapter.
4. Released **v1 EMA** policy, SHA `d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed`, CPU, one Torch thread, T=1: real serving feature preparation + top-8 `propose`, and `sample` as a separate fallback metric. Loaded and unloaded measurements are saved. D1 histories come from the original sensor’s observed public events; cycle fields remain explicitly unknown; tracker elixir is labelled a model prior with `elixir_exact=False`. This measures the v1 serving API on public runtime packets, not gate-(b)/(c) sidecar equality or fallback strength. The policy is never installed into production search.

A fresh cohort contains **at least 1,000 unique nonterminal packets**, from at least two train recordings. Every packet is checked by stepping all four reconstructed roots once; instant terminal roots and no-search frames are excluded with reasons. The historical 440-row corpus is not repeated to create a nominal 1,000-packet test. Each deadline cell processes the same selected frames again through actual video decode → original P1 → P2 → P3 → in-memory submission. A separate spawned process continuously performs paced recorded capture/decode/original perception throughout search and loaded fallback measurements. Its real processing FPS, capture age, errors and exit code are recorded; it may fall behind rather than inventing 20 FPS.

**Timer definitions:** `decision_ms` is P3 entry through command construction and in-memory serialization. `frame_to_mock_ms` is the actual contiguous foreground video-read/P1/P2/P3/mock service interval. It excludes emulator screenshot transport, IPC queues and real tap submission/acceptance. Exact-mode records use P3 timing only. This direct replay harness cannot establish five-process loop freshness, P4 acceptance or formal E4. W timed-WAIT cooldown is reset for independent paired packets; production cadence/defaults are unchanged.

## Gates and interpretation

- **Decision:** loaded real nonterminal search p95 **≤200 ms** in each cell; ≥1,000 paired packets, identical paired cohort, valid complete-root admission. All samples, including first decisions and cooperative native deadline overruns, count. Overruns, partial completion, candidate completion fraction and no-complete-candidate/fallback-needed rates are reported. The independent reducer checks all four score lists: an interrupted candidate's partial root score cannot be admitted. Record per-cell outcomes; a slow serial control makes the conservative whole-matrix verdict FAIL even if ON/four threads passes. [DESIGN §2.6 and §2.8](../DESIGN.md) specifies K=4/four threads and 200 ms; [W-screen8 adoption](../../../../explore/w-screen8/RESULTS.md) requires loaded p95 ≤200 ms before changing the live default.
- **Perception engineering budget:** warm full P1 p95 **≤40 ms** for both decoders, at least 1,000 warm frames each; retain cold results separately. [DESIGN §2.3 and §5.1](../DESIGN.md) sets p50 25/p95 40 ms with emulator running. **The later [L2-V4-PREREG E1](../L2-V4-PREREG.md) makes the perception-stage 40 ms row descriptive**, because formal end-to-end latency is gated in E4. Report this distinction, not a new confirmatory rule. An emulator-free recording replay is not emulator-on budget acceptance.
- **Exactness:** 32 no-deadline packets per W arm, compared across one/four threads (64 thread pairs), with exact candidate ordering, complete per-root score arrays (including W’s intentional unrefined `None` masks), reduced score arrays and actions. Exact W scoring uses the native `None` budget, never an infinite native budget. Candidate coverage includes intentional screening omissions as well as deadline truncation; it is not an isolated root-timeout rate. OFF/ON are behaviorally different and are not required to agree. Decode mismatches retain both full records and a FAIL. Neither a successful replay nor A14 grants vectorized live timing/admission.
- **Tower/fallback:** descriptive latency; the tower channel's historical <2 ms mean goal and B5's proposer p99 ≤15 ms target are engineering diagnostics, not formal L2 qualification. [Tower report](../tower-channel/REPORT.md), [next-compute plan B5/B6 and candidate e](../../../PLAN-NEXT-COMPUTE-20261009.md).
- **Formal E4 stays unqualified.** [L2-V4-PREREG E4](../L2-V4-PREREG.md) separately requires formal weights, emulator-running T9, eight unscored smoke matches, real gRPC acceptance, ≥18 FPS, ≥95% processed, gap p99 ≤150 ms, frame→submission p50 ≤260/p99 ≤400 ms, ≤1% overruns and P4 acceptance gates. That future work is outside this package's authorization.

## Required staging from Sam/owners (0–15 min)

Supply an existing native arm64 Python **3.12+** environment with Torch/MPS, NumPy, OpenCV, SciPy, Pydantic, msgspec, pygame and gymnasium, plus Rust/cargo/rustup and Xcode command-line tools. Do not copy a Linux extension or the x86-64-v3 quickwins binary. Installed Python distributions, Torch/backend, interpreter and Rust compiler identity are recorded in receipts.

Supply two or more frozen **train** match directories, each with `receipt.json`, `frames.jsonl`, `video.mp4`, and the original registration `split.json`; choose chronological prefixes totalling enough eligible frames for 1,000 unique searches (default 1,500 frames per match). Admission checks train membership and recorded media hashes before inference. Supply the frozen train prior catalog, released v1 checkpoint, selected v4 checkpoint and final joint selection proof graph. Independent checkpoint/prior/split/selection SHA256 values must come from the owner's inventory, not be guessed from package examples.

**Currently blocked dependencies:** the final joint selection authenticator and trusted deployment policy are not supplied by the repo. Sam/perception owner must supply an independently reviewed `owner_launcher.py`, its independently pinned SHA, and all verifier/proof/import files. It exports `load_selection(selection_path)` and calls the existing `load_authenticated_selection(..., trust_policy=reviewed_policy)`, returning an `AuthenticatedSelection`. The reviewed policy must enumerate/hash the real verifier closure. No JSON/T7-only receipt can replace this authority. Do not edit `selection.py`, set private authentication tokens, or add a permissive launcher. Both decoder arms use the identical authenticated selected values; vectorized measurement sets `decoder_diagnostic=True` and stays unadmitted.

The source baseline is **`444661fadf2a68c48544c5fc573c4e21d4ad1263`**. `configs/source-pins.json` SHA-binds all executable/native research dependencies and relevant static metadata. One dependency was uncommitted at that baseline: `dependencies/l1_v4.py` is an exact, unmodified snapshot of the perception owner's threshold-capable ABI, SHA **`cad13d4f958757dbb9f38732f19d73423149b9dffcc34e3c41bb7376f87e9fef`**. Install it only in the isolated measurement checkout. It is not a scientific source edit or a selection seal. A later owner release with different bytes needs a new reviewed package/source pin, never silent repinning during a run.

## Isolated checkout and native macOS build (15–30 min)

Run these **on the authorized Mac only**. `package_rev` is the pushed package commit Sam/coordinator reviewed. Set a fresh checkout/build/output path; the existing live installation is not the target.

```bash
export package_rev='<reviewed package commit>'
export runtime_root='/Users/sam/Desktop/code/clasher-mac-e4-NEW'
export build_root='/Users/sam/Desktop/code/clasher-mac-e4-build-NEW'
export result_root='/Users/sam/Desktop/code/clasher-mac-e4-receipts-NEW'
export PYO3_PYTHON='<absolute existing native arm64 Python 3.12+>'
package=reports/strategy_council_20260928/live-loop/v4/mac-e4-package
cd /Users/sam/Desktop/code/clasher
# Network git fetch is Sam's staging, not client/emulator networking.
git fetch origin worker/mac-e4-package-20261009
git worktree add --detach "$runtime_root" 444661fadf2a68c48544c5fc573c4e21d4ad1263
git -C "$runtime_root" checkout "$package_rev" -- "$package"
cd "$runtime_root"
cp "$package/dependencies/l1_v4.py" src/clasher/vision/l1_v4.py
export CLASHER_ROOT="$runtime_root" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 RAYON_NUM_THREADS=1
"$PYO3_PYTHON" -B "$package/scripts/measure_mac.py" verify-sources
nice -n 10 bash "$package/scripts/build_mac.sh" "$runtime_root" "$build_root"
```

`build_mac.sh` checks **Darwin/arm64**, then runs exactly:

```bash
rustup target add aarch64-apple-darwin
# CARGO_TARGET_DIR is the fresh versioned build directory, PYO3_PYTHON native arm64.
# RUSTFLAGS is empty: no x86 ISA flags or fleet binaries.
nice -n 10 cargo build --locked --manifest-path engine-rs/Cargo.toml \
  --release --features extension-module,gil-release --target aarch64-apple-darwin -j 2
```

It copies `target/aarch64-apple-darwin/release/libclasher_core.dylib` to `clasher_core<sysconfig EXT_SUFFIX>` in the fresh build directory, tests import and `NativeScripts.score_wait_screen8`, and writes **`build.json`** with the newly measured **Mac binary SHA256**, source-manifest SHA, toolchain, `file` architecture and `otool` linkage. A Mac binary SHA cannot be truthfully predeclared before this build. The identical binary is imported before research modules in every cell and worker. [Linux build reference](../../../../../engine-rs/build_quickwins.sh) is deliberately not invoked.

## Combined measurement (30–75 min)

After independent SHA values and staged paths are set, run once. If MPS is unavailable, explicitly use `--device cpu` and preserve that backend in the receipt; it cannot be relabelled MPS/ANE evidence. Existing ANE artifacts are outside this eager-MPS/CPU package.

```bash
: "${V4_CHECKPOINT:?owner staged checkpoint}"
: "${V4_CHECKPOINT_SHA:?independent owner SHA256}"
: "${V4_FINAL_SELECTION:?final joint proof graph entrypoint}"
: "${V4_FINAL_SELECTION_SHA:?independent owner SHA256}"
: "${OWNER_LAUNCHER:?reviewed independent deployment launcher}"
: "${OWNER_LAUNCHER_SHA:?independent reviewed launcher SHA256}"
: "${V1_CHECKPOINT:?released v1 EMA checkpoint}"
: "${TRAIN_PRIOR:?frozen train prior}"
: "${TRAIN_PRIOR_SHA:?independent prior SHA256}"
: "${TRAIN_SPLIT:?frozen recording registration split}"
: "${TRAIN_SPLIT_SHA:?independent split SHA256}"
: "${TRAIN_MATCH_A:?first train recording directory}"
: "${TRAIN_MATCH_B:?second train recording directory}"
nice -n 10 "$PYO3_PYTHON" -B "$package/scripts/measure_mac.py" session \
  --sam-authorized-replay --native-dir "$build_root" --device mps \
  --checkpoint "$V4_CHECKPOINT" --checkpoint-sha256 "$V4_CHECKPOINT_SHA" \
  --selection "$V4_FINAL_SELECTION" --selection-sha256 "$V4_FINAL_SELECTION_SHA" \
  --owner-launcher "$OWNER_LAUNCHER" --owner-launcher-sha256 "$OWNER_LAUNCHER_SHA" \
  --fallback "$V1_CHECKPOINT" \
  --fallback-sha256 d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed \
  --prior "$TRAIN_PRIOR" --prior-sha256 "$TRAIN_PRIOR_SHA" \
  --split "$TRAIN_SPLIT" --split-sha256 "$TRAIN_SPLIT_SHA" \
  --match "$TRAIN_MATCH_A" --match "$TRAIN_MATCH_B" \
  --frames-per-match 1500 --output "$result_root"
```

The replay acknowledgment flag documents Sam's prior authorization; it is not an approval mechanism. No CLI exposes a live input or emulator address. Session input/config hashes, environment, raw samples, selected source provenance and all exit failures stay in the fresh output directory. A process exit of zero means **experiment completed**, not gates passed. Read `complete.json` and the distributions. If fewer than 1,000 unique eligible packets exist, the session fails without measuring a reduced decision suite; retain it and choose a longer predeclared train prefix in a new directory.

## Review receipts (75–90 min)

Inspect `build.json`, `session.json`, `selection-provenance.json`, `decoder-comparison.json`, `perception.jsonl`, `cohort.json`, `paired-cohort.json`, `decisions.jsonl`, `decision-summary.json`, `loaded-replay.jsonl`, both fallback summaries/raw logs, `cold/`, and `complete.json`. `failure.json`, `decision-partial-summary.json` and load error files preserve interrupted attempts. No log is overwritten or missing sample silently treated as a pass.

Record emulator status separately: this harness never starts or inspects one. Even with Sam's emulator replay running, direct replay timing does not establish screenshot-to-action transport or T9 acceptance. Return binary/config hashes, cold/warm distributions, per-cell decisions, exactness and deadline-admission outcomes to the coordinator. Do not change production W defaults, decoder admission, selection thresholds/calibration, backend timing or `planner_total_delay_ticks`. Historical 27 ticks remains a labelled experimental input; the corrected terminal-root diagnosis requires fresh separate calibration before freeze. [Runtime/perf history](../RUNTIME-PERF-FIXES.md); [Mac history and remaining prerequisites](../RUNTIME.md); [A14 restrictions](../l1/reviews/AMENDMENTS-13-14-REVIEW-20261009.md) and [vectorized amendment](../l1/amendments/08-vectorized-decoder-20261008.md). The reported ~10× record-only decoder speedup is not a live-MPS timing claim.

## Linux harness validation

Only standard-library logic tests run on **127x03 CPU with nice 19**, one thread; no Torch import, native build, inference or heavy work on 05. Test logs/exit JSON are under `receipts/`. These exercise quantiles, pin tampering, replay-only/Mac refusal, partial-root discard, stable ties, pair identity, exactness, cold-sample handling and four-root scheduling. They do not claim a Mac session ran. The coordinator's independent B6 Opus review remains a separate review step before Sam runs the package.
