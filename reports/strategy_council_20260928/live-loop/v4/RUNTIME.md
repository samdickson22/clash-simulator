# v4 pipelined runtime

Implementation: `src/clasher/live/`; invocation: `python -m clasher.live`.
This is an offline-renderer runtime implementation and a train-only replay harness.
S6 delay-aware planning is adopted and enabled by default. Production remains
unqualified: formal v4 weights, runtime latency qualification, the v4-HUD verifier
re-test, and the L2-v4 PREREG are still prerequisites.

No emulator or renderer was launched, configured, queried, or tapped in this task.
The recorded-media tests use a mock input channel. The original two train recordings remain
on 127x04 under `/mpac/sdicks02/repos/clasher-runtime-data/`; nothing was deleted.
The frozen research tracker, collector, APK/hook, frozen split and perception
PREREG remain unchanged. The latency revision adds an exact runtime tracker adapter;
no git commits were made.

## Processes and transport

Perception and belief now run in separate spawned processes, matching DESIGN §2.1:
five workers plus the parent supervisor (six application processes), and Python's
small spawn resource-tracker helper. All stages use host monotonic timestamps.

| Process | Implementation | Responsibility |
|---|---|---|
| P0 | `capture.py`, `runtime.p0` | Authenticated screenshot stream or timestamp-paced train replay; sanitize pixels; publish capture/decode timestamps. |
| P1 | `perception.py`, `runtime.p1` | Per-frame body/HUD and gap-preserving temporal events; publish latest public observation and raw pixel HUD. |
| P2 | `belief.py`, `tracker.py`, `runtime.p2` | Exact accelerated tracker v3, own ledger, four hypothesis-stratified roots, versioned belief snapshots. |
| P3 | `decision.py`, `runtime.p3` | Unchanged adopted S6 delay-aware search: four roots, horizon 160, interval 10, three styles, common 200 ms deadline. |
| P4 | `actuation.py`, `runtime.p4` | Sole actuator owner; fresh pixel HUD; mock input in these measurements; verification/retry and reliable ledger feedback. |
| P5 | `runtime.run` | Warmup/start barrier, heartbeats, compressed logs, provenance, owned-PID shutdown. |

The capture ring has 64 slots of 540×1140×3 uint8 pixels (~118 MB). A slot lock
and sequence stamp prevent torn reads; the consumer copies before inference.
The producer never waits: overwrite the oldest slot at wraparound, or drop an
incoming frame if its slot is being copied. Loss counts are logged. At a queue
age of 150 ms, P1 skips alternate sequence numbers, retaining real timestamps.
At 400 ms it discards the frame. Neither adapter clears temporal history on a gap.

Perception, belief and HUD queues each hold two latest values. Older frame values
are droppable. Perception IPC contains no pixel array. An acknowledgement watermark
retains one-shot event candidates in successive observations until P2 consumes them;
its 4,096-candidate bound fails closed. EOF retries a failed last publication and
waits for P2 to consume the last published sequence before supervisor draining.
P2 skips intermediate body/HUD frames, preserves actual timestamps, deduplicates
events, and incorporates reliable actuator feedback independently of inference.
The command queue holds one message; a shared outstanding-command token covers
queued, transporting, verifying and retrying states. The eight-entry feedback
queue is reliable: saturation terminates the run rather than discarding a spend
or terminal result. The 2,048-entry logging queue never stalls capture; lost log
messages have an explicit counter. Normal shutdown drains logs. The default
five-second heartbeat timeout stops the pipeline; only its recorded child PIDs
can be terminated. There is no automatic restart or resend after a process fault.

P3 searches on ten-tick cadence, a new opponent event with q≥0.5, an integer
elixir threshold crossing, or verification feedback. Triggers are rate-limited
to one per 200 ms and suppressed while a command is outstanding. Snapshots carry
ledger revisions; P4 rejects old revisions, repeated command IDs, expired
commands, and decisions based on frames preceding a terminal result. A decision
expires 400 ms after its source frame. Transport errors remain ambiguous/pending.

For the legacy fallback only, P4 runs its small standalone v3 HUD reader on the
latest capture while P1 processes bodies. This implements the latest-frame
pre-tap check and keeps raw HUD distinct from optimistically spent belief state.
V4 uses the shared-backbone HUD published by P1; there is no hidden-state verifier.

## Belief and fair-information boundary

The opponent tracker uses `live/tracker.py:TrackerV3`, an output-identical
acceleration of **frozen `search-noise-s4/TrackerV3`**, adopted unchanged by S5.
The frozen files are not edited. `belief.frozen_tracker=True` retains the reference
path for paired proof. Dependencies still load through isolated bootstrap aliases
without replacing application imports. The live adapter uses the frozen public-event/body API. It offsets
that API's built-in six-tick age correction so v4's execution-time estimate is
applied once. The frozen tracker retains its S5 calibrated confusion/likelihood
model; v4 top-three distributions, q and sigma remain available in the logged
perception output and q controls event triggers. They are not a claim of a newly
validated tracker update rule.

The default tracker operating assumption is N90 with frozen S4 N90 resource
calibration 0.1104; this is the minimum deployment gate, **not a measured accuracy
claim for the fallback**. The final v4 event gate is in-loop opponent recall and
precision ≥90% at 500 ms, with 97/97 the target. No heldout event scoring ran here.

Own state reserves the spend and slot at submission, incorporates monotonic
terminal feedback once, and fences old HUD. Integer digit changes anchor elixir;
between anchors it uses the public engine's 178/357/537-units-per-tick regeneration.
It never erases a pending reservation with an older frame. The declared own deck
and confirmed play order determine the known cycle. Unseen initial order remains
explicitly unresolved and receives a deterministic root completion; it is not
randomly shuffled or presented as an observed/exact cycle. Own-state accuracy and
late-entry belief calibration remain separate validation work.

Replay admission checks **both receipt and frozen split membership are train**
before opening media, matches the registered decks, and verifies SHA256 of video
and timing sidecar. It passes only pixel media, public sequence/production/receipt
and PTS fields, and the declared own deck to workers. Native tick brackets,
events/HUD/object labels, evaluator data, opponent deck, and native RNG are never
player inputs. The prior catalog is the frozen training prior. `PacketBuilder`
and public hypothetical-root reconstruction are reused from L2/Stage 5;
`offline_loop`, collector/probe helpers and native observation readers are not.

## Actuation timing

The existing actuator and input channel are unchanged. The gRPC contract loads
`actuation/backend-timing.json`: verify deadline = most recent submission +
1,187.318 ms + 600 ms; rollback = deadline + 200 ms. That is 1,787.318 / 1,987.318 ms.
A single fresh-HUD retry can occur 150 ms after verification expiry and starts a
new window without another reservation. A late/stalled observation beyond rollback
cannot emit the retry. Inter-tap delay remains 20 ms.

The observed acceptance-delay equivalents (23.034/23.746 ticks p50/p99) are
wall-latency measurements, not exact execution ticks. The unchanged renderer
hook's nominal delay is 22 ticks; planning uses the measured backend p50 (23 ticks
for gRPC), as directed by the coordinator after S6 adoption. T2's 316/320 gRPC sensitivity result still fails its
99% gate. A replay mock records submissions and preserves all ledger/verification
logic, but cannot change recorded video; any replay confirmations are coincidental
pixel matches, not acceptance or playing-strength evidence.

## Adopted S6 integration

P3 imports `search-noise-s6/delay.py:DelayAwarePlanner` and its `own_state.py`
dependency unchanged, without running the research bootstrap. `delay_aware=True`
is the default runtime config and CLI setting. The adopted scorer constructs a
candidate-dependent pending root, leaves the physical model unspent, and executes
the command once at t+d. Subsequent own rollout commands also obey the single
pending command rule. The horizon, opponent scripts and leaf remain S6's.

`timing.py` reads the selected backend's `p50_ticks` and rounds to the nearest
nonnegative integer (`floor(p50_ticks + 0.5)`). Current profiles give **23 ticks
for gRPC** and **24 for ADB-spawn**. No planner delay is hard-coded. `--backend`
and `--backend-timing` select one profile/file for both P3 and P4; P5 rejects
conflicting selectors before starting workers. P4 still uses that profile's
p99 milliseconds for verification. The ADB profile supports replay comparisons;
the live input implementation is gRPC and requires its matching profile.

S6's original scorer rejects deadline mode. The runtime therefore calls its
unchanged scorer on one candidate at a time, with a native-call deadline guard.
Only candidates whose three styles finish on **all four roots** enter the mean;
partial scores are discarded. Stable ties use S6's 1e-9 epsilon. A 5 ms allowance
before the common 200 ms deadline covers reduction and IPC; native calls are
cooperatively bounded, not forcibly preempted. Actual overruns are logged. If no
candidate finishes, P3 waits. With d=0 or `delay_aware=False` in an offline config,
S6 delegates to the original native scorer without additional RNG draws.

P4's state machine is the sole live pending-command authority. Its feedback
includes command ID, cost, remapped slot, before-HUD, attempts and backend delay.
P2 mirrors this reservation; P3 neither submits a second S6 live channel nor
subtracts its spend again. Both scheduling and `RustPlanner.decide` block while
pending, including after the predicted due tick and across a retry. Only P4's
pixel-confirmed acceptance/failure releases the reservation. S6's ephemeral
`CommandChannel`s exist solely inside hypothetical candidate rollouts and never
alter runtime ledger state. Snapshot revision/expiry/terminal fences still apply.

An optional `--delay-hook module:function` remains an offline experimental override
with the previous `(resources, info, opponent_roots, candidates, DelayContext)`
ABI; `nominal_command_ticks` now contains the selected profile's rounded p50.
Real gRPC input requires the adopted scorer, matching timing profile and completed
qualification receipt. Source provenance includes both imported S6 files and the
selected timing file.

`tests/live_v4/test_s6_parity.py` compares P3 against direct, unmodified S6
full-list scoring over the same four roots on three recorded Phase A train inputs
(seed 1975100700). It checks every candidate score and the chosen action, unchanged
own input state, d=0/flag-off equivalence to the original scorer, and deadline
selection using only complete candidates. The fixture records its source log hash
and runtime/model provenance. Original pixel outputs have terminal-looking tower
states and tied scores; an explicitly synthetic nonterminal tower variant adds
non-tied scoring and checks that positive delay changes scores. It is not claimed
as another real pixel observation. Reservation tests cover one spend/slot past the
predicted due tick, retry identity, and shared per-backend timing.

## V4 weights and export integration

`V4Perception` constructs `PerceptionV4`, loads the checkpoint state dict, and calls
`PixelPerception.step(image, episode, timestamp_ms)` unchanged. CPU and MPS are
supported. The adapter records actual completion/availability, canonicalizes
unknown HUD values, preserves native absolute side orientation (0 opponent,
1 own), and maps public building identities from static card metadata.
The upstream 32-feature cache/16-token temporal window, body association, event
age/sigma and calibration are preserved. Only a new episode resets history.

Provide `--checkpoint selected.pt --calibration selected-calibration.json` with:

```json
{"spells": [], "thresholds": {"default": 0.5}, "calibration": {}, "qualification": "unqualified"}
```

The empty example is a schema illustration, not deployable calibration. The
actual vocabulary comes from checkpoint `cards`/`bodies`; model weights are in
`model`. Validation-selected thresholds/isotonic knots and a qualified checkpoint
must replace the example. No random or shakedown weights were benchmarked as v4.
CoreML/ANE package conversion, export parity and a package-backed model adapter
remain the T7 export work in `l1/EXPORT.md`. The eager/MPS reference adapter is the
integration point for that work; this implementation does not claim ANE timing.

The available diagnostic fallback used the repository's v1 body checkpoint and
v3 HUD/temporal interfaces. The documented v3 temporal weights were absent on the
Mac, so the measured variant is explicitly `v3-body-hud-only`. Optional
`--events v3-last.pt --selection selection.json` enables the v3 temporal network
on the last three actual frames, with retained history and conservative fusion.
Neither fallback variant qualifies v4 events. Known secondary-spawn and spell
limitations remain model-quality limitations, not hidden-label repairs.

## Replay and launch commands

Use an existing environment with Torch, NumPy, OpenCV, SciPy, Ultralytics for the
fallback, and the repository's built `clasher_core` extension. No new framework
was introduced. On 127x04 the existing GPU environment ran **CPU only**, with
Torch/BLAS/OpenCV threads limited to one and four Rust search threads total.
Legacy YOLO initialization can change Torch's thread count; the worker restores
one after warmup. Auto-install is disabled. The old trusted YOLO checkpoint needs
legacy object loading and dill; the run reused dill from the existing project
environment in a task-local dependency directory.

```bash
export PYTHONPATH="$PWD/src:$PWD/engine-rs:/path/to/task-local-dependencies"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
nice -n 10 /path/to/python -B -m clasher.live \
  --replay /path/to/train-matches/v4-phase-a-1975100700 \
  --split /path/to/frozen/split.json \
  --prior /path/to/frozen/train/human_deck_catalog.json \
  --body /path/to/body.pt --hud /path/to/hud.npz \
  --output /path/to/new-run
```

`--frames N` bounds a smoke run; omit it for the complete recording.
`runtime_bench.sh DATA OUTPUT PYTHON` runs the two admitted train recordings under
the existing detached `fleet_run.sh`. It retains partial/failed output and skips
only completed runs; use a fresh label after an interrupted attempt.

**After Phase A, in an independently owned/qualified renderer slot only**, connect
to an already running renderer. This command does not launch or configure it:

```bash
cd /Users/sam/Desktop/code/clasher
export PYTHONPATH="$PWD/src:$PWD/engine-rs"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
nice -n 10 /path/to/python -B -m clasher.live \
  --grpc-port "$OWNED_GRPC_PORT" --proto-dir "$OWNED_PROTO_DIR" \
  --discovery "$OWNED_DISCOVERY_FILE" --episode runtime-v4-smoke \
  --own-deck "$OWN_DECK_COMMA_SEPARATED" \
  --prior "$FROZEN_TRAIN_PRIOR" --perception v4 --device mps \
  --checkpoint "$QUALIFIED_V4_CHECKPOINT" --calibration "$VALIDATED_CALIBRATION" \
  --backend offline-renderer-grpc --mock-input \
  --output "$NEW_RUN_DIRECTORY"
```

For real taps, remove `--mock-input` and supply `--qualification path.json`, whose
`verifier_pass`, `perception_pass`, and `delay_planner_pass` are all true after the
corresponding actual qualifications. The current T2 result cannot support that
receipt. This is an explicit readiness check, not a request for an emulator action
in the current task. Stop the supervisor with Ctrl-C or SIGTERM to its recorded
PID; it stops and joins its own children. Never use a process-name kill.

## Logging and validation

Each new output directory contains `config.json`, `provenance.json`, `pids.json`,
`latency.jsonl.gz`, and `metrics.json`. Provenance includes runtime/tracker/actuator/
weights/S6/native-extension hashes, package versions, split/media identities and host.
Compressed logs carry sequence/command IDs, monotonic stamps, queue age, drops,
public perception outputs, event candidates, own/opponent summaries, roots,
ledger revisions and pending commands. The first full replay preceded the final
addition of richer public-output logging; its timing records and source hashes
remain intact. No production-fidelity claim follows from a mock run.

Latency metrics separate capture, decode, body/HUD, temporal/fusion, belief,
search, P4 HUD refresh and tap transport. Frame-to-tap starts at the **decision's
original source-frame production** and ends after first-attempt transport returns;
it is never rebased to the fresh pre-tap HUD. Ambiguous submissions and retries do
not count as new first-attempt latency samples. The capture timestamp is replayed
at original pacing with recorded production-to-receipt delay; CPU media decode is
additional measured harness work. Model/resource warmup precedes the start barrier.

`python -B -m unittest discover -s tests/live_v4 -v` runs process, ring, ledger,
trigger, adapter, fair-boundary, and supervisor tests. It includes bounded-ring
overflow, a 650 ms P1 stall with alternate/expired drops, a stalled P3 result that
cannot submit, duplicate command IDs, stale terminal fences, ambiguous transport,
backend-relative acceptance, 1.2-second temporal gaps, V4 ABI canonicalization,
and train-only admission before media opening. The gRPC test uses an in-memory
fake RPC and never opens a socket. The unchanged T2 actuator tests are separate.

## Historical measured latency (before the split/acceleration revision)

**FAIL against the fleet diagnostic latency/throughput budget.** Two complete
train recordings (1975100700 and 1975100701), 8,071 captured frames, 5,700 processed
(70.62%), 2,371 accounted drops, 14.11 processed FPS. Both workers completed without
errors, log loss or temporal resets. There were 715 search calls, including 183
multi-candidate searches, and zero deadline overruns. P4 recorded 65 mock taps
(51 first attempts, 14 permitted retries), with no duplicate `(match, command,
attempt)` and no tap without an active reservation. All 51 first submissions came
from the first match; the second produced wait decisions, so it has no standalone
frame-to-tap estimate.

The following full-match baseline predates S6 integration and used immediate scoring.

| Stage, milliseconds | Samples | p50 | p95 | p99 | DESIGN stage verdict |
|---|---:|---:|---:|---:|---|
| Capture production → receipt | 8,071 | 9.32 | 10.83 | 32.47 | FAIL 3/10 |
| Decode + sanitize | 8,071 | 0.74 | 2.04 | 2.65 | PASS 4/8 |
| Fallback body/HUD | 5,700 | 44.47 | 48.32 | 51.00 | FAIL 15/25 |
| Fallback temporal fusion (no temporal weights) | 5,700 | 0.09 | 0.20 | 0.26 | PASS timing only; not v4 quality |
| Frozen tracker + own ledger + root sampling | 5,700 | 22.25 | 48.02 | 157.05 | FAIL 3/10 |
| Active Rust search (four roots) | 183 | 73.91 | 94.32 | 121.45 | PASS 110/200 |
| P4 latest-pixel HUD refresh | 8,071 | 4.07 | 4.69 | 4.92 | Additional fallback work |
| Mock two-tap submission | 65 | 20.07 | 20.08 | 20.09 | PASS mock only |
| **Source frame → first tap submission** | **51** | **312.26** | **386.47** | **405.57** | **FAIL p50≤200 and p99≤400** |

Capture queue age was 148.36 ms p50 / 351.92 ms p99; belief-to-decision queue age
was 1.95 / 15.33 ms. The combined perception/belief worker is the CPU bottleneck.
This measurement does not establish that a qualified v4 model on ANE/MPS and a
quiet Mac will pass. The CPU host was shared: launch load 61.64/53.70/33.81, no
console users, with 51 Python processes observed across all jobs (within the 96
worker cap). This task's pipeline used five application processes and at most four
concurrent native search threads, all nice 10. No GPU computation was requested.

**Initial pre-S6 validation:** 20 runtime unit/integration/fault tests passed (10.288 s), seven
unchanged T2 actuator tests passed, and both complete recorded-media integration
audits passed. `integration-audit.json` verifies capture counts, full drop
accounting, reservations, duplicate prevention and process/log integrity.
Passing these functional checks is independent of the failed latency budget.

Full results and provenance are under `runtime-results/fleet/`, aggregate samples
under `RUNTIME-METRICS.json`, and test output in `RUNTIME-TESTS.txt` and
`runtime-results/actuator-tests.txt`. `RUNTIME-VALIDATION.json` retains the compact
integration/Mac receipts. Raw `runtime-results/` is ignored by the repository
policy but preserved locally; the compact reviewable files are outside that rule. Development smoke runs are retained on 127x04 as
`/mpac/sdicks02/jobs/clasher/runtime-v4-replay-dev*`; failures are not silently removed.

The Mac latency test was **deferred**. At 07:29:02 UTC, load was 4.60/5.07/5.28,
but `kern.memorystatus_vm_pressure_level` was 2, so normal memory pressure was not
established while T1 collection was active. Only read-only health queries and
read-only checkpoint copies occurred. `runtime-results/mac-preflight.json`
retains the evidence. Fleet CPU results are not Mac/ANE or emulator-on results.

## Historical S6 integration validation (2026-10-08)

**27 runtime unit/integration/fault/native-parity tests passed in 38.468 seconds
on 127x04**, CPU only, nice 10. The three recorded frames (0, 50, 186) each had
21 candidates; direct S6 and P3 agreed on every score and chose 1550, 1453 and 283.
The full nonterminal variant had 20 candidates and non-tied scores; it agreed
with S6 and selected wait. Full scoring took 894.3 ms in the generous-deadline
parity test. With the real 200 ms deadline, 2 candidates finished across all four
roots in 196.1 ms, with no overrun; the action matched S6 restricted to those
completed candidates. This preserves score semantics but does not claim equal
playing strength to the entire fixed-budget S6 benchmark when searches truncate.

A 200-frame train-only replay of seed 1975100700 through all five processes used
the adopted scorer at d=23 and mock P4. It processed 115 frames, dropped 85 by the
bounded-age policy, made 14 searches and 3 first submissions, and recorded zero
search overruns, worker failures, logging losses, duplicate taps, overlapping
reservations or unreserved taps. All reservations resolved. Startup initially
exposed a ready/heartbeat race; the supervisor now starts stall clocks at the
common ready barrier. That failed attempt remains under `s6-record-r1` on 127x04.

| Short S6 replay stage, ms | p50 | p99 |
|---|---:|---:|
| Capture | 9.27 | 14.09 |
| Decode | 0.71 | 1.99 |
| Fallback body/HUD | 45.76 | 50.40 |
| Fallback temporal fusion | 0.18 | 0.33 |
| Belief | 36.31 | 165.22 |
| Search (includes wait-only decisions) | 144.22 | 196.82 |
| P4 pixel HUD refresh | 4.52 | 4.67 |
| Mock submission | 20.08 | 20.09 |
| **Frame → first submission (n=3)** | **387.89** | **391.19** |

**Budget verdict remains FAIL**: p50 exceeds 200 ms, and this three-submission
sample cannot qualify p99. Throughput was 11.44 processed FPS / 57.5%, below the
required 18 FPS / 95%. This short integration check supplements the full pre-S6
baseline above; it is not a replacement full-match latency study. Mac testing was
not resumed and the original memory-pressure deferral remains in force.

Reviewable evidence: `RUNTIME-S6-TESTS.txt`, `RUNTIME-S6-VALIDATION.json`, and the
train-only fixture in `tests/live_v4/fixtures/s6-train-inputs.json`. Raw replay
logs/provenance are retained under `runtime-results/s6-record-r2/` locally and on
127x04. No emulator/renderer or heldout data was used for this integration.

## Latency revision: implementation and equality

`tracker.py` keeps the frozen resource, event likelihood, cycle-mixture, pruning,
calibration and sampling rules. It changes execution only:

- Advance cloned hands by exact integer regeneration segments and refill-expiry
  jumps, including the 2,400/4,800 tick boundaries. The first rounding and final
  division match the frozen tick loop.
- Cache repeated fixed-lag cycle updates using immutable cue contents, event-count
  hazard and retained input identity; changed board corroboration invalidates the key.
- Index compatible prior decks, preserving original deck and sum order; warm
  prior-only presence tables for up to three reveals before the start barrier.
- Skip provably empty unresolved-hand enumerations; avoid rejected-branch clones
  and V2 hand-summary work that V3 immediately overwrites.
- Compute one exact CDF per resource array and reuse it across summaries and four
  root draws; cache hypothesis weights without changing any RNG draws.
- Accumulate shifted resource slices without allocating zero-filled full-lattice
  temporaries. Optional dependency-free `lattice.rs` fuses the elementwise work;
  NumPy still supplies the original capped pairwise reductions. No fast-math,
  reassociated sums, FMA, probability truncation or sparse approximation is used.

The uniform contamination in frozen v3 makes all 100,001 lattice entries nonzero.
Pruning this to sparse support would change the frozen distribution. The optimized
runtime therefore retains dense probabilities and their exact reduction order.

Build the optional kernel **on the target fleet/Mac host**, before launching:

```bash
# Fleet environment: source /mpac/sdicks02/env.sh
bash reports/strategy_council_20260928/live-loop/v4/build_lattice.sh
```

The build uses plain `rustc`, no cargo dependencies, and produces `_lattice.so`
(Linux) or `_lattice.dylib` (Mac). The loaded library and Rust source hashes enter
runtime provenance. Without it, the exact optimized NumPy path remains available;
`CLASHER_TRACKER_NUMPY=1` explicitly selects that fallback.

**Exact equality PASS: 32,837 recorded updates**, with no tolerances. All final
accelerated timings below use the built Rust kernel, on one CPU thread for belief. The
paired check compares the bytes of both complete 100,001-value resource arrays
(committed and current), every float64 summary and hand mass, all cycle states,
four stratified roots per update, and the NumPy generator state after sampling.
Both objects share the same interpreter/hash environment and independent generators
seeded 6108. This is equality to the frozen reference on the tested traces, not
an assertion that the frozen tracker is calibrated for new perception weights.

The inputs are all 22,602 updates in S4 development traces 000/002 (both seats,
N97/N90/N64), plus 10,235 pixel-derived observations from replayed Phase A **train**
seeds 1975100700/701/702. S5 adopts these same frozen S4 tracker bytes; there is no
separate S5 development-trace corpus in the available checkout. No S5 confirmation
or heldout trace was substituted. Phase replay membership is checked before its
public log is opened. Tracker inputs contain public candidates and body positions;
truth fields in archived development containers never enter either tracker.

| Paired replay, ms/update | Updates | Frozen p50 / p95 / p99 | Accelerated p50 / p95 / p99 |
|---|---:|---:|---:|
| S4 dev 000 | 12,078 | 12.60 / 29.52 / 42.14 | 2.08 / 3.02 / 8.04 |
| S4 dev 002 | 10,524 | 13.67 / 29.30 / 43.01 | 2.15 / 2.93 / 6.99 |
| Phase A train 700 | 5,654 | 24.39 / 56.90 / 235.13 | 3.04 / 9.70 / 13.48 |
| Phase A train 701 | 2,413 | 22.86 / 51.20 / 241.99 | 2.81 / 5.42 / 12.91 |
| Phase A train 702 | 2,168 | 30.94 / 61.29 / 260.31 | 3.20 / 10.39 / 20.20 |
| **All paired updates** | **32,837** | **14.96 / 43.82 / 68.01** | **2.22 / 4.18 / 12.19** |

Median speedup is **6.75×** and p99 speedup **5.58×** on the pooled paired
inputs. Development rows time tracker + distribution + four roots; Phase A rows
also include the existing own-ledger update. These microbenchmarks exclude
comparison/assertion time and startup warmup. They do not replace the full
pipeline timing below. **The requested ≤10 ms p99 is still missed**: pooled
12.19 ms, with Phase A trace tails of 13.48/12.91/20.20 ms.

The frozen v3/v2, DerivedD1, ELT, noise model and calibration all match the original
`dev-code-freeze-v2.json` hashes (`RUNTIME-FROZEN-INTEGRITY.json`).
`RUNTIME-TRACKER-PARITY.json` records input hashes, output digests, source/library
hashes, sample counts and before/after timings. `tracker_parity.py` reproduces the
comparison. All 33 runtime/S6/optimization tests pass in 44.598 s on 127x04;
the five focused optimization tests also pass with the Rust kernel disabled.
`RUNTIME-LATENCY-TESTS.txt` retains the full test log.

Profiling found 17.54/27.14 seconds in frozen tick-by-tick hand advancement on
1,000 N90 updates. A final 5,654-observation tail attribution identifies cycle
mixture updates as the remaining dominant burst: `_hands_event` p99 8.82 ms
before the other update work. GC alone has p99 0.97 ms, resource transitions
1.84 ms, resource evidence 1.73 ms, summary 1.47 ms, sampling 0.60 ms (stage
quantiles are not additive). No pruning, weakened likelihood, fewer roots, or
changed search semantics was used to force a pass.

## Final fleet replay latency

**Budget verdict: FAIL.** The final constant-source suite completed on 127x04
with **14 train matches, 223 first-attempt submissions**, 263 total mock submissions
(40 permitted retries), and 2,824 searches (479 active, zero deadline overruns).
It captured 29,971 frames, perceived 29,968 and updated belief on 29,958:
**99.957% processed at 19.975 FPS**. The 13 omitted belief frames are accounted for
by three capture/perception drops and ten latest-observation replacements.
All runs completed with zero worker failures, log loss, duplicate/unreserved taps,
overlapping reservations or unresolved terminal reservations.

The frozen-train sequence was 1975100700–707 and 1975100710–715. Seeds 708/709
are not train and were skipped by registration membership before opening media.
All 14 source/provenance hashes agree for the runtime and loaded lattice library.
This includes the same original 700/701 recordings and twelve additional train
matches; no match was excluded for producing wait decisions.

| Final fleet stage, ms | Samples | p50 | p95 | p99 | DESIGN p50/p95 verdict |
|---|---:|---:|---:|---:|---|
| Capture production → receipt | 29,971 | 9.40 | 11.01 | 32.62 | FAIL 3/10 |
| Decode + sanitize | 29,971 | 0.81 | 0.99 | 2.34 | PASS 4/8 |
| Fallback body/HUD (CPU) | 29,968 | 44.80 | 51.00 | 52.63 | FAIL 15/25 |
| Fallback temporal fusion | 29,968 | 0.10 | 0.21 | 0.30 | PASS timing only 5/10 |
| Tracker + own ledger + four roots | 29,958 | 6.21 | 16.83 | 23.91 | FAIL 3/10; p99 also >10 |
| Active S6 Rust search, four roots | 479 | 143.44 | 196.40 | 197.02 | FAIL p50; PASS p95 110/200 |
| P4 latest-pixel HUD refresh | 29,971 | 3.97 | 4.72 | 5.06 | Additional fallback work |
| Mock two-tap submission | 263 | 20.07 | 20.08 | 20.09 | PASS mock only 45/80 |

| End-to-end scenario, ms; n=223 | p50 | p95 | p99 | p50≤200 / p99≤400 |
|---|---:|---:|---:|---|
| **Fleet measured** | 246.40 | 318.23 | 340.41 | FAIL / PASS |
| **Projection only:** body/HUD 15 + temporal 5 ms | 220.83 | 291.86 | 315.15 | FAIL / PASS |
| **Projection only:** body/HUD 25 + temporal 10 ms | 235.83 | 306.86 | 330.15 | FAIL / PASS |

Each projection subtracts the **actual source-frame** body/HUD plus temporal
service time from each measured first-attempt latency and adds the indicated
DESIGN stage budgets. Quantiles are then recomputed over those paired samples.
The 20 ms and 35 ms rows are separate budget scenarios, not inferred Mac p50/p95
observations. Capture, decoding, measured queues, S6 search, latest-HUD wait and
mock transport are retained. This is not a simulated reschedule or a confidence
bound: faster perception may also change queues and decisions.

Capture queue age is 18.64/44.64/60.34 ms p50/p95/p99 (historical median 148.36 ms).
Perception→belief queue age is 1.55/2.51/2.81 ms; belief→decision is
2.05/3.45/19.47 ms. Throughput and end-to-end p99 pass, but measured median latency,
both projected medians and the **23.91 ms in-pipeline belief p99** fail. The
isolated 12.19 ms paired p99 must not be substituted for this live-pipeline number.
Active S6 search also exceeds its 110 ms median stage allowance; the historical
74 ms search result used the earlier immediate scorer. The scorer, four roots,
candidate completion rule and 200 ms deadline were not weakened.

The CPU host was shared, all task processes were nice 10, Torch/BLAS/OpenCV used
one CPU thread, and search used four native threads. No GPU computation was used.
Launch preflights recorded zero console users; account Python counts were 1–14
before adding the seven runtime/helper processes, below the 96-process ceiling.
Observed launch loads were 1.72–5.23 (one-minute average). The exploratory suite
and paired proof overlapped some final matches; the final matches ran after those
jobs completed. This is not a quiet-Mac qualification.

Reviewable receipts: `RUNTIME-LATENCY-METRICS.json`, `RUNTIME-TRACKER-PARITY.json`,
`RUNTIME-FROZEN-INTEGRITY.json`, and `RUNTIME-LATENCY-TESTS.txt`. Reproduction tools:
`latency_suite.py`, `latency_report.py`, `tracker_parity.py`, `build_lattice.sh`.
The final raw logs, configs, hashes and PID receipts remain on 127x04 at
`/mpac/sdicks02/jobs/clasher/runtime-latency-replays-r2-results/`.
The mixed-version development suite `runtime-latency-replays-r1-results/`,
failed smoke attempts and all profiles remain preserved and excluded from the
final aggregate. Local compact logs are under `runtime-results/latency-revision/`.

```bash
# Run on 127x04 from /mpac/sdicks02/repos/clasher, using a fresh unique label.
bash reports/strategy_council_20260928/fleet/fleet_run.sh runtime-latency-new-label \
  /mpac/sdicks02/envs/clasher-gpu/bin/python -B \
  reports/strategy_council_20260928/live-loop/v4/latency_suite.py \
  --data /mpac/sdicks02/repos/clasher-runtime-data \
  --matches /mpac/sdicks02/repos/clasher-v4-data/matches \
  --output /mpac/sdicks02/jobs/clasher/runtime-latency-new-label-results
```

This retains the historical metric definition: `frame_to_tap` records completion
of the mock two-tap submission for **attempt 1**, including the 20 ms inter-tap
interval. It is not input acceptance latency or the instant of the first physical
touch. Retries are excluded from the end-to-end sample set. The historical full
baseline used immediate search; this revision preserves the adopted S6 scorer.
The baseline host was also much busier. Thus the end-to-end comparison is not a
controlled code-only speedup; the paired tracker experiment above is.


## Mac replay gate and exact deferred command

**Deferred at 2026-10-08 09:13 UTC; no Mac measurement was run.**

No Mac work is authorized while T1 Phase A is collecting. The local
`T1-PROGRESS.md` does not confirm collection has stopped; the time estimate alone
is not an unlock. This revision has made **no Mac connection or measurement**.
After T1 explicitly records collection stopped, run the following on the Mac.
It stages only train replay inputs from 127x04, uses MPS and mock input, and never
launches, queries or taps an emulator. Its 2,400-frame limit is about two minutes
of recorded media plus warmup. Use a fresh timestamped directory.

```bash
cd /Users/sam/Desktop/code/clasher
mac_run="$PWD/reports/strategy_council_20260928/live-loop/v4/runtime-results/mac-latency-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$mac_run/data/match" "$mac_run/data/weights"
rsync -a --include='*.py' --include='*.rs' --exclude='*' \
  127x04:/mpac/sdicks02/repos/clasher/src/clasher/live/ src/clasher/live/
rsync -a 127x04:/mpac/sdicks02/repos/clasher-runtime-data/matches/v4-phase-a-1975100700/ \
  "$mac_run/data/match/"
rsync -a 127x04:/mpac/sdicks02/repos/clasher-runtime-data/weights/ "$mac_run/data/weights/"
rsync -a 127x04:/mpac/sdicks02/repos/clasher-runtime-data/registration/split.json "$mac_run/data/split.json"
rsync -a 127x04:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/search-noise-s4/runtime/support/human_deck_catalog.json \
  "$mac_run/data/prior.json"
export PYTHONPATH="$PWD/src:$PWD/engine-rs"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
nice -n 10 rustc --crate-type cdylib --edition=2021 -C opt-level=3 \
  src/clasher/live/lattice.rs -o src/clasher/live/_lattice.dylib
nice -n 10 .venv/bin/python -B -m clasher.live \
  --replay "$mac_run/data/match" --split "$mac_run/data/split.json" \
  --prior "$mac_run/data/prior.json" --body "$mac_run/data/weights/body.pt" \
  --hud "$mac_run/data/weights/hud.npz" --device mps --mock-input --frames 2400 \
  --output "$mac_run/run" > "$mac_run/console.log" 2>&1
cat "$mac_run/run/metrics.json"
```

This tests the available body/HUD fallback on actual MPS. It does not qualify
formal v4/ANE perception or emulator-on throughput. Actual Mac timing and ARM
bit parity remain unmeasured until that gated run.

## Remaining L2-v4 prerequisites

1. Selected formal v4 weights, frozen validation calibration, event/body/HUD
   gates and export parity. In-loop events ≥90/90 at 500 ms; 97/97 target.
2. A quiet Mac replay/emulator-on throughput and latency run: ≥18 processed FPS,
   ≥95% of captured frames, p50≤200/p99≤400 ms frame-to-submission, perception
   p95≤40 ms and search overruns≤1%. Fleet results cannot substitute for it.
3. P4 re-test with the v4 HUD head: ≥300 positive and ≥300 negative trials and
   the coordinator's ledger-relative spend predicate, reaching ≥99% sensitivity
   and specificity. Existing T2 P4 remains unchanged and unqualified.
4. Own-state/cycle/elixir validation, pixel lifecycle/end/result reader, L2-v4
   PREREG, and T9 smoke before the paired O/P/S/S-d evaluation. There is no
   result-screen or match-start controller in this pixel-playing runtime.
