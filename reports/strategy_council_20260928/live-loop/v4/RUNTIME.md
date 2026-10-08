# v4 pipelined runtime

Implementation: `src/clasher/live/`; invocation: `python -m clasher.live`.
This is an offline-renderer runtime implementation and a train-only replay harness.
S6 delay-aware planning is adopted and enabled by default. Production remains
unqualified: formal v4 weights, runtime latency qualification, the v4-HUD verifier
re-test, and the L2-v4 PREREG are still prerequisites.

No emulator or renderer was launched, configured, queried, or tapped in this task.
The recorded-media tests use a mock input channel. The two train recordings remain
on 127x04 under `/mpac/sdicks02/repos/clasher-runtime-data/`; nothing was deleted.
This implementation did not edit the tracker, collector, APK/hook, frozen split
or perception PREREG, and made no git commits.

## Processes and transport

The task's naming combines DESIGN's perception and belief workers in P2, with P5
as the parent supervisor: five application processes, plus Python's small spawn
resource-tracker helper. All stages use host monotonic timestamps.

| Process | Implementation | Responsibility |
|---|---|---|
| P1 | `capture.py`, `runtime.p1` | Direct authenticated loopback gRPC screenshot stream, or timestamp-paced H.264 replay; sanitize pixels; publish capture/decode timestamps. Live sampling targets 20 FPS from the faster screenshot RPC. |
| P2 | `perception.py`, `belief.py`, `runtime.p2` | V4 streaming model or explicit v3 fallback; gap-preserving temporal events; frozen tracker v3; own ledger; four hypothesis-stratified roots; versioned belief snapshot. |
| P3 | `decision.py`, `runtime.p3` | Rust fair search, horizon 160, interval 10, balanced/pressure/defense; four parallel single-thread roots, common 200 ms deadline. Only candidates completed at all four roots enter the mean. |
| P4 | `actuation.py`, `runtime.p4` | Sole owner of existing `actuator.py`; freshest raw pixel HUD; remap by card; persistent gRPC or mock input; verification and one retry; reliable ledger feedback. |
| P5 | `runtime.run` | Spawn/warmup barrier, heartbeat/stall detection, compressed logs, budget summaries, source hashes, owned-PID shutdown. |

The capture ring has 64 slots of 540×1140×3 uint8 pixels (~118 MB). A slot lock
and sequence stamp prevent torn reads; the consumer copies before inference.
The producer never waits: overwrite the oldest slot at wraparound, or drop an
incoming frame if its slot is being copied. Loss counts are logged. At a queue
age of 150 ms, P2 skips alternate sequence numbers, retaining real timestamps.
At 400 ms it discards the frame. Neither adapter clears temporal history on a gap.

Belief and HUD queues each hold two latest values. Older values are droppable.
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
latest capture while P2 processes bodies/belief. This implements the latest-frame
pre-tap check and keeps raw HUD distinct from optimistically spent belief state.
V4 uses the shared-backbone HUD published by P2; there is no hidden-state verifier.

## Belief and fair-information boundary

The opponent tracker is **TrackerV3 from `search-noise-s4/`, imported unchanged**,
per the S5 adoption in COORDINATOR.md. Its module dependencies are imported with
an isolated bootstrap alias so they cannot replace the application's environment
or source path. The live adapter uses the frozen public-event/body API. It offsets
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
overflow, a 650 ms P2 stall with alternate/expired drops, a stalled P3 result that
cannot submit, duplicate command IDs, stale terminal fences, ambiguous transport,
backend-relative acceptance, 1.2-second temporal gaps, V4 ABI canonicalization,
and train-only admission before media opening. The gRPC test uses an in-memory
fake RPC and never opens a socket. The unchanged T2 actuator tests are separate.

## Measured latency

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

## S6 integration validation (2026-10-08)

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
