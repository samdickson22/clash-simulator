# Live runtime correctness and performance fixes

2026-10-09, before L2-v4 freeze and T9/E4. Implementation and receipts prepared
on 127x05; all native replay, Torch inference, process tests and timing ran on
127x08 CPU at nice 19 with CUDA disabled. At most eight Python processes from
this work were active, including spawned pipeline workers/resource tracker.
The initial implementation made no Mac access, renderer commands, gate-host
02/03 work, commits, frozen-registration edits, sealed-source edits or native
binary replacement. The later owner-review round below separately authorizes
an isolated scoped commit and push after the required secret scan.
Pre-existing working-tree changes in decision/contracts/timing/l1_v4 were
preserved. The coordinator was notified immediately after the source/log
diagnosis, after Linux causality, and after the additional empty-HUD finding.
Perception-owner coordination was requested through that coordinator.

## Correctness flag 3: absence became terminal loss

The committed Mac suite contains **440 scored searches**. **296 (67.27%)** have
every completed candidate scored -2.0. Inputs were matched to P2's processed
record by the exact search sequence, rather than the nearest preceding log
line. All 440 matches are present, across the 16 train recordings; no media,
truth labels, hidden opponent state or heldout payload was opened.

Linux causality is stronger than the original flag: **all 440 original roots
become terminal after one native tick**. In 296, the own King is missing and the
opponent King exists: winner 0, hence -2.0 for seat 1. The other **144 are
terminal draws** with both Kings missing. This outcome is independent of the
newly sampled simulation RNG. Recorded RNG states are not logged; this is a
causal reconstruction from recorded public inputs, not a claim to recover
hidden original battle state.

The chain is:

1. V3 fallback perception omits crown towers, especially the own King, and also
   emits a duplicate princess `Tower` around the opposing King at (9,3).
2. The sealed pixel `PacketBuilder` includes only current detections. The
   sealed `Resources.root` creates entities only for those rows.
3. Native cleanup checks whether each side has a King. A missing entity means
   destroyed King and sets `game_over` on tick 1.
4. `NativeScripts.phi` returns terminal loss -2 or terminal draw 0. Its ordinary
   nonterminal potential clamp is [-1.5,1.5]; this is **not a scoring-clamp bug**.

Example: train 1975100700, sequence 0 has both a `Tower` at approximately
(9.0034,3.2036), HP 0.1231, and `KingTower` at (9.0122,3.1028), without measured
HP. Both are owner 0; no owner-1 King exists. The phantom originates in the
raw perception output, not in native template alias resolution. The new model
rejects the princess identity at the King slot instead of borrowing its false
HP measurement.

**Impact:** the historical 440-search suite cannot qualify nonterminal search
latency, completion fraction, truncation rate, or playing decisions. Preserve
its receipts as measurements of the original fallback runtime. Its 186.06 ms
frame-to-submission median also cannot establish the corrected planner's total
delay: **27 ticks must be revalidated/recalibrated before freeze**. This report
does not change `backend-timing.json` or either L2-v4 draft.

## Guarded public model

`--public-tower-model` enables two new wrappers:

- `tower_model.py`: six public arena slots from `TileGrid`'s static geometry;
  canonical `Tower`/`KingTower` aliases; nearest same-owner slot within three
  tiles; reject identity/geometry contradictions; deduplicate a slot by highest
  confidence, with stable input-order ties. Correctly identified public HP
  updates an episode-local slot cache. Missing detections use cached HP or an
  explicit initial full-HP model prior at confidence 0.01. Public zero HP is
  retained through later missing detections. Caches reset on episode change.
  Crown slots precede other entities in the hypothetical packet. Raw public
  detections remain unchanged; diagnostics distinguish raw visible entities,
  priors, identity rejects and duplicates. These priors are assumptions in a
  point model, not perception measurements or an assertion of true HP.
- `public_root.py`: normalize explicit hand sentinels `None`, `''` and `'empty'`
  to missing slots without changing slot order or the logged own ledger. Reject
  unsupported hand/cycle names before native metadata access. **19/440** logged
  own hands contained `'empty'`; valid nonterminal rollouts exposed a native
  metadata panic hidden by the old instant-terminal roots. The failed first
  qualification log is retained, alongside the successful retry.

The repaired one-tick terminal count is **3/440**. These are match 1975100713,
sequences 621,694,747, retaining explicit own-King pixel HP=0. No truth was read
to override that observation. Missing-tower priors do not repair false HP
measurements, general phantom troops/buildings or deck/cycle uncertainty. A
future lifecycle/terminal reader must distinguish confirmed destruction from
sensor omission; it must not infer destruction from one absent detection.

## Exact scorer changes and measurements

`--perf-scorer` sets `cache_root_config=true` and
`hoist_opponent_moves=true`. Both can also be controlled separately in planner
config. They are independent of the public-model correction.

`perf_resources.cached_resources` subclasses the sealed Resources class and
binds its existing root function to an isolated globals dictionary. Only that
function's JSON serializer splices a cached final config value into the payload;
the sealed module and its globals are never monkeypatched. Config is static for
the instance lifetime. Reconstruction, deepcopy, player order and RNG draws
stay in the original function. The cached config is **1,488,163 bytes**.

`RustPlanner.score` computes the opponent's three initial style actions once per
root, then uses the unchanged S6 `candidate_root` and `delayed_rollout`. Style
order and addition order stay balanced/pressure/defense. Native deadlines still
discard an interrupted candidate's entire score, and the original native
object is restored in `finally`. The zero-delay/flag-off delegation is unchanged.

Linux CPU, Python 3.12.12, Torch 2.7.1+cu118, CUDA disabled:

| Measurement | Original | Optimized | Scope |
|---|---:|---:|---|
| Root serialization/deepcopy p50 | 11.06 ms | 1.70 ms | 1,000 paired payloads; excludes native JSON parsing |
| Root serialization/deepcopy p95 | 13.06 ms | 3.64 ms | Same |
| Four-root decision p50 | 1,002.27 ms | 952.77 ms | 16 full-budget corrected recorded-input decisions |
| Four-root decision p95 | 1,468.25 ms | 1,412.45 ms | Serial scoring, no deadline truncation |
| Paired decision saving p50 | | **53.08 ms** | Median of paired differences |

These are corrected, predominantly nonterminal CPU workload timings, not Mac
200 ms deadline timings. The serialization medians imply approximately 37.4 ms
saved for four roots; the integrated paired timing includes native parsing and
the first-move hoist. Absolute full-budget latency still exceeds 200 ms on one
CPU lane. GIL-release/native-build work is separately owned and is not part of
this patch or these receipts.

Exactness:

- **1,000/1,000 payload strings are byte-identical**, with equal accumulated
  SHA-256 `ae145de04c2a00d1a4a075b9719db6d454ceec3083fb3e8c87cd12b4ef8654e9`.
  Both NumPy RNG states match after the full sequence. 32 pairs additionally
  have identical parsed native digests.
- **1,312/1,312 candidate/root scores are exactly equal**, across 16 recorded
  decisions from 10 train matches. The optimized scores also equal direct
  full-list scoring by the unchanged S6 module. Root digests are unchanged by
  those initial script queries. Equality compares scorer variants within the
  same corrected public model; it does not claim old and corrected decisions
  are equivalent.
- **45/45 live tests pass**, including recorded S6 parity, d=0, deadline
  interruption, public boundaries, command ledger, stalls/expiry, process
  shutdown, ring wakeups, tower omission/duplicates/zero HP and empty sentinels.
- The real opt-in `RustPlanner` constructor and four-root reduction also pass
  a separate native smoke on a recorded input containing `'empty'`, with every
  candidate completed and the own input unchanged.

## Perception adapter and selected body threshold

`--vectorized-decoder` installs the existing `DecoderAdapter` into a separately
loaded copy of the sealed `l1_v4.py` module. Each sensor owns its module globals;
reference sensors and the formal perception process are not patched. Existing
`decoder_records_v4.py`, `vectorized_decoder_v4.py` and
`vectorized_runtime_adapter_v4.py` are loaded unchanged. Runtime provenance now
includes their hashes whenever the flag is enabled.
The executable copy loads that same unchanged `l1_v4.py` source path, whose
hash is also included in runtime provenance; a focused regression records all
four source hashes and confirms the reference decoder remains untouched.

**Q2/flag 2 is fixed independently of the speed flag.** Following the binding
owner contract relayed at ~01:00Z and recorded in
[LIVE-SELECTION-CONTRACT.md](l1/LIVE-SELECTION-CONTRACT.md), `V4Perception` requires a typed
`AuthenticatedSelection` handoff produced by a separately trusted owner
authenticator. It supplies that object's body threshold, event thresholds and
calibration explicitly to `PixelPerception`; config and calibration files have
no selection authority. It rejects unset or arbitrary JSON objects before model
loading, and selected values must be numeric, not bool, on the registered
0.1..0.9 grid. There is no implicit 0.5 or config fallback.
The selected value goes to tracker birth/admission through the unchanged
constructor; the low 0.1 candidate extraction floor is unchanged.

The new `selection.py` defines an internal handoff, **not a final joint seal
format or authentication algorithm**. The owner's trusted code-level verifier
must establish final joint authority independently and return normalized
`SelectionClaims`; the handoff checks selection/source SHA256 bindings, freezes
the selected parameters, records the verifier's source hash, and verifies the
exact checkpoint bytes and ordered card/body vocabulary before use. Workers
receive the typed object across spawn; JSON receipts contain provenance only
and cannot be reloaded as authority. No default verifier is installed, so the
pending final seal means v4 startup refuses. The current T7-only
`selection-freeze.json` (`core.body_threshold`, `core.event_thresholds`,
`core.calibration`) is explicitly insufficient for live authority.

`DecoderAdapter` remains unadmitted for formal use. Its formal gate additionally
requires the owner-authenticated decoder admission, covering full non-clock
equality and the new timing gate; MPS/live equality must be established later.
An explicit `--decoder-diagnostic` permits measurement with mock input only,
still requiring the authenticated final joint selection. The missing-selection
regression invokes both decoder flag values and asserts refusal before any
model, sensor or adapter is created. Additional tests reject JSON authority,
T7-only claims, changed selection/source/checkpoint hashes, reordered vocabulary,
and real input for unadmitted diagnostics.
Synthetic checks of forwarding/isolation and scalar/vectorized non-clock output
equality pass on CPU, including a 1.2-second gap and a selected threshold of 0.7.

The audit's CUDA analog of approximately **22 ms/frame saved** remains an
estimate for live MPS. No new MPS timing or train-recording parity is claimed.
The perception owner's subsequently confirmed offline validation capture-clock
bug delays formal selection. No validation-capture availability numbers enter
this report's before/after timings or exactness claims. The 22 ms figure is the
audit's decoder service-time analog, not validation availability evidence.
The prepared Mac tool compares complete body/event decoder records as well as
post-fusion public outputs across two train recordings, excluding availability
clocks, before enabling the adapter in a fresh suite. Runtime wall availability
appropriately changes when service time changes; it is not backdated to force
clock equality. Existing P4 v4 HUD freshness/verifier prerequisites remain open
and belong to the perception/actuation qualification work.

## Q13: blocking transport

`--blocking-queues` changes P1 ring waiting to a multiprocessing Event with a
clear-before-sequence-check pattern, P2 to blocking readability waits on both
observation and feedback pipes, P3 to a blocking queue read followed by a latest
drain, and P4 to readiness waits on both HUD and command pipes. P2 control
feedback wakes it even when no perception message arrives. Drop-oldest
publishing, event acknowledgments, stale revision checks and expiry remain.
Waits are bounded at 50 ms for heartbeat/shutdown; active P4 verification retains
2 ms timer checks. The direct v3 HUD reader retains a 10 ms ring refresh bound.
Queue readability uses the multiprocessing Queue's `_reader` pipe, which must
be covered by the pinned Python/Mac process tests.

Three paired synthetic 120-frame runs per arm, all 720 frames processed:

| Median of run medians | Polling | Blocking |
|---|---:|---:|
| Capture → P1 queue age | 2.06 ms | 1.57 ms |
| Perception → P2 queue age | 1.33 ms | 0.37 ms |
| Belief → P3 queue age | 1.67 ms | 0.36 ms |

The sum of these three hop medians falls by **2.76 ms**. Post-startup mock
frame-to-tap p50 falls **11.47 → 7.44 ms**, a **4.03 ms** reduction, but there are
only **three post-startup taps per arm**. The unfiltered median of run medians
is **13.26 → 34.71 ms**: cold belief initialization causes the first blocking
decision to consume sequence 0 while polling often advances to sequence 1.
Both the original result and the explicitly separated startup analysis are
retained. This is transport evidence, not an E4 latency or acceptance gate.

## Receipts and reproduction

All files below are under `perf-fixes/` beside this report:

- `mac-search-inputs.json.gz`: 440 train public/own/prior inputs, source log
  hashes, recorded diagnostics and exact sequences. `extract_recorded.py`
  regenerates the data from committed `runtime-results/mac-final/suite` logs.
- `live-perf-qualification-20261009-r2.json`: causal outcomes for every input,
  1,000-root byte/RNG proof, parsed digest proof, full scorer pairs, timings,
  native hash and live source hashes.
- `live-perf-tests-20261009-08r2.log` and `.exit`: 45 passing tests.
- `live-perf-threshold-20261009-08r1.log` and `.exit`: subsequent three passing
  CPU adapter tests, including the added live-constructor missing-selection
  regression in both flag modes. This historical receipt predates the stronger
  authenticated-selection handoff; the earlier config/calibration transport
  is superseded and supplies no current selection authority.
- `live-perf-selection-20261009-08r1.log` and `.exit`: 13 passing focused CPU
  tests of the binding authenticated-selection contract, adapter equality and
  live pixel ABI forwarding. Native/scorer code is unchanged by this follow-up;
  the earlier full native exactness/timing receipts retain their original source
  hashes and are not reinterpreted as formal selection or decoder admission.
- `live-perf-selection-full-20261009-08r1.log` and `.exit`: all 53 then-current live
  regressions pass on CPU, including the stronger selection handoff, process
  supervision/fault handling and unchanged recorded native S6 comparisons.
- `live-perf-contract-20261009-08r1.log` and `.exit`: subsequent 11 passing CPU
  selection/adapter tests, including the added source-provenance regression.
  It records the exact executable `l1_v4.py` and three decoder dependency hashes
  and verifies reference inference stays untouched; production sources unchanged.
- `live-perf-smoke-20261009-r1.json` and its log/exit receipt: integrated guarded
  constructor, native scoring and four-root reduction.
- `queue-benchmark.json` and `live-perf-queue-analysis-20261009-r1.json`: complete
  six-run synthetic metrics and a separately labeled startup analysis.
- The earlier test/qualification failure logs remain for auditability.

Native binary used on 08, unchanged:
`13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309`.
The sealed local dependencies as read/staged were:

```text
fair_player.py  6d2665d02da7a74083313b64693e87bf59d50b303904e614ae3136b7741f8c76
delay.py        96b0637cbc6245b4246eef06aa45e6a7b571226688777bd299b93b2c436721f2
l1_v4.py        cad13d4f958757dbb9f38732f19d73423149b9dffcc34e3c41bb7376f87e9fef
```

CPU reproduction, using an isolated staging root, a fresh fleet label, one
Torch/Rayon thread and the repository's fleet wrapper:

```bash
staged=/mpac/sdicks02/jobs/clasher/live-perf-20261009-r1
bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/fleet/fleet_run.sh \
  live-perf-replay-NEW \
  env CLASHER_ROOT="$staged" PYTHONPATH="$staged/src:$staged/engine-rs" \
  CUDA_VISIBLE_DEVICES= RAYON_NUM_THREADS=1 nice -n 19 \
  /mpac/sdicks02/envs/clasher-gpu/bin/python -B \
  "$staged/reports/strategy_council_20260928/live-loop/v4/perf-fixes/qualify.py" \
  --output /mpac/sdicks02/jobs/clasher/live-perf-qualification-NEW.json
```

**Prepared for later; not run on the off-limits Mac.** First stage the changed
live modules, unchanged decoder dependencies, the admitted selected v4 checkpoint
and final joint selection evidence into the isolated Mac runtime root through
the existing owner workflow. The final seal format and owner authenticator are
pending: **this command cannot yet run and accepts no calibration/config
substitute**. Supply the owner's trusted authenticator and a fresh result
directory after that authority exists:

```bash
cd /Users/sam/Desktop/code/clasher-runtime-v4
export PYTHONPATH="$PWD/src:$PWD/engine-rs:$PWD/runtime-data/python-deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
: "${V4_CHECKPOINT:?admitted selected checkpoint}"
: "${V4_FINAL_SELECTION:?authenticated final joint seal; T7-only receipt insufficient}"
: "${V4_SELECTION_AUTHENTICATOR:?trusted owner module:function; pending implementation}"
nice -n 10 .venv/bin/python -B -m unittest discover -s tests/live_v4 -v
nice -n 10 .venv/bin/python -B \
  reports/strategy_council_20260928/live-loop/v4/perf-fixes/remeasure_mac.py \
  --data "$PWD/runtime-data" --matches "$PWD/runtime-data/matches" \
  --checkpoint "$V4_CHECKPOINT" --selection "$V4_FINAL_SELECTION" \
  --selection-authenticator "$V4_SELECTION_AUTHENTICATOR" \
  --parity-frames 200 --maximum-matches 20 --output "$PWD/mac-perf-fixes-NEW"
nice -n 10 .venv/bin/python -B \
  reports/strategy_council_20260928/live-loop/v4/latency_report.py \
  "$PWD/mac-perf-fixes-NEW" "$PWD/mac-perf-fixes-NEW-metrics.json"
```

This performs two-recording scalar/vectorized MPS parity first, then runs the
guarded v4 train replay suite with mock input, targeting at least six matches
and 200 first mock taps. It does not launch a renderer, send real taps or edit
timing calibration. Mock replay does not establish emulator-on E4/P4 acceptance.

## Completion follow-up: coordinator ~01:20Z

The authorized CPU implementation and qualification work is complete. The full
53-test live suite and the subsequent 11 focused selection/AdapterTests pass on
127x08 CPU, with exit-0 receipts retained above. The focused follow-up includes
the executable source provenance and reference-isolation check; production
sources were unchanged after the full-suite pass.

No authenticated selected value is available today: the final joint seal and
its owner authenticator remain pending, further delayed by capture-clock
remeasurement. The pluggable handoff accepts only the separately authenticated
object bound to checkpoint bytes, ordered vocabulary, selection and source
hashes. Config/calibration fields are provisional metadata and provide no
authority or independent override; formal startup refuses without the object.
The older config/calibration threshold transport is superseded, not admitted.

The perception owner's review of AdapterTests equality remains pending and
will be relayed by the coordinator. Decoder formal admission, corrected timing
qualification and separate live-device/MPS parity remain open. No validation
capture timing is used here. No further implementation changes are planned
until the final seal format lands; the prepared Mac command remains unrun.

## Owner-review hardening: 2026-10-09 ~02:20Z

The next authorized round implements all five requirements from the read-only
[owner review](l1/reviews/LIVE-SELECTION-HANDOFF-OWNER-REVIEW-20261009.md), exact SHA
`d402274b770d9faa7d31945dc27bc3c9c443b529deafb03114c45824d785ec77`.
Its receipt and all seven original source pins matched before edits. The review
is compatible with the handoff; no finding is disputed. `selection_sha256` can
bind the whole final joint proof graph without flattening T6 or rerunning it.

1. `event_thresholds` must contain an explicit `default`. Every key must be a
   selected card or `default`, and every value must be finite, non-bool, on the
   frozen nine-value grid. Empty maps and off-grid overrides refuse before model
   loading; EventFusion's implicit 0.5 fallback cannot establish selection.
2. Spell routing is the exact ordered spell subset under the sealed public
   game-data source, using the same fixed card-ID namespace as frozen replay.
   The selected runtime/routing sources and metadata bytes are hash-bound.
   `CalibrationBinding` requires a bound measured proof and the registered
   minimum per-card support of 20. Selected knots retain their values and must
   have supported numeric [0,1] pairs, strictly increasing x and nondecreasing y,
   with known card/default keys. Missing or empty pooled calibration refuses
   unless the trusted verifier explicitly authenticates the measured raw-fallback
   policy. This does not prohibit scientifically justified empty calibration and
   does not refit, normalize or invent any calibration.
3. `decoder_admitted=True` requires a `DecoderBinding`: exact implementation ID,
   the eight-source closure and its canonical hash, bound equality and corrected
   timing proof references, and explicit device/platform/backend/Torch-version
   scopes. The actual closure and launch scope are checked before model startup
   and after isolated adapter installation. CPU/CUDA scope does not cover MPS.
4. `VerifierTrustPolicy` is supplied by independent deployment/launcher code,
   outside selection/config/calibration. Its expected entrypoint, every declared
   project import hash and package/namespace resolution are checked before
   importing the verifier and before invoking it, then rechecked afterwards.
   Executable package initializers are hashed; namespace packages have explicit
   non-executable directory pins. The CLI entrypoint must match this policy.
   The production policy and callback remain unset: arbitrary seal declarations
   cannot nominate their own trust roots. The owner must supply the reviewed
   complete closure and real evidence authenticator; the obsolete
   `joint_selection_evidence_v4.py` is not wired or executed.
5. Direct decoder diagnostics carry the explicit
   `unadmitted-decoder-diagnostic-qualification` label and source/scope provenance
   with `decoder_admitted=False`. P1 logs this qualification, and runtime summary
   labels preserve it. The existing top-level mock-actuator restriction remains;
   this is a labeling correction, not an allegation or repair of a live-tap bypass.

The checkout was pulled and already current with origin, including tower-channel
commit `138a3b57`. Its adapter and tests are preserved, as are concurrent round-2
tower changes. This round edits neither `tower_channel.py` nor `tower_model.py`,
nor the perception owner's files or held Amendment12 package. CPU tests run only
on isolated 127x01 staging under nice 19 with CUDA disabled and one Torch/Rayon
thread. No formal selection/startup, real decoder admission, Mac, heldout or
validation-capture timing work occurs in this round.

The first focused run exposed missing namespace-package handling in the new
external trust policy; it is fixed by explicit namespace-origin checks. The
first full-suite attempt had only two staging import errors (missing L2 packet
builder and round-2 synthetic tower-truth helper). Both failed attempts are
retained; no production or registration change was made to bypass a test.
The next full attempt had one failure in the tower worker's in-progress round-2
OCR test snapshot. That worker subsequently committed `52a9e102`, including an
updated test and tower model; staging was refreshed to those committed files,
without editing either tower source locally, before the final run.

Final validation: **85/85 tests pass** (`live-selection-review-full-20261009-01r3`,
65.791 seconds), including both tower-channel suites, native S6 parity/deadlines,
process/fault handling and all new selection-review rejections. The preceding
focused rerun passed 33 tests. Logs and exit receipts for every attempt are
retained under `perf-fixes/`; `live-selection-review-environment-20261009-r1.json`
records the exact staged live/test hashes, native binary, interpreter, Torch,
CPU/device scope and priority. This is synthetic/recorded-train CPU regression
evidence, not owner selection authentication or formal decoder admission.
The deployment verifier policy and real callback remain absent and fail closed.

## What L2-v4 must pin before freezing

1. Enable/pin the public reconstruction policy consistently for P/O/S/S-d:
   static slot geometry, aliases, three-tile gate, duplicate tie rule, cache
   lifecycle, missing-HP prior and explicit zero-HP semantics; keep raw sensor
   output and hypothetical state distinct. Record how any oracle/simulator
   projection enters that same policy. This correction changes behavior and
   must not be described as mere scorer parity.
2. Pin all live/new module hashes and the unchanged Resources/S6/decoder source
   hashes; config-cache immutability, native binary identity, Python version,
   thread counts, candidate ordering/RNG, root count/horizon/interval/deadline,
   reduction and partial-candidate discard semantics. Keep flags explicit in
   config rather than relying on opt-in defaults.
3. Bind selected v4 checkpoint, vocabulary, event thresholds/calibration and
   **body_threshold** to the actual authenticated final joint selection seal,
   including the owner verifier and selection/source hashes. T7-only receipts
   and JSON/config/calibration declarations provide no authority. Forward the
   same body value on scalar/vectorized paths and all deployment/export arms.
   Admit vectorized formal use only after full non-clock exactness and the new
   timing gate, plus separate Mac train-recording MPS/live equality.
4. Pin a fresh corrected nonterminal Mac latency/completion receipt and the
   resulting total-delay calibration formula/value. Preserve backend acceptance
   timing and the existing HUD freshness/verification bounds. Do not inherit
   27 ticks or the old zero-overrun claim solely from the terminal-root suite.
5. Pin blocking-queue mode, the bounded idle/verification timers and process
   tests. Complete formal v4, P4 HUD/verifier, emulator-on T9/E4 and any
   two-renderer qualification before confirmatory games. CPU exactness and
   synthetic transport timing do not replace these gates.
