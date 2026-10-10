# Fleet input contract (review draft)

Uses the frozen r3 specification in `spec-pins.json` and the public row names in
T1 candidate ba3dc8b0 (`reports/explore/t1/receipts/corpus-contract-draft.json`).
Independent review remains required. This package generates neither matches nor
outcomes and never controls a client. This worker executes only light Linux05
smoke runs; T1 separately owns execution on its reporting hosts.

T1 uses **measure_tiers.py unchanged**, with the same `TierBackend.work` as Mac:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  nice -n 10 /absolute/pinned/python -B /absolute/e4v3/measure_tiers.py \
  --fleet-reference --bundle /absolute/reviewed-reference-inputs \
  --runtime-root /absolute/fresh-frozen-runtime \
  --native /absolute/qualified-native/clasher_core.abi3.so \
  --manifest-sha256 APPROVED_TIERS_PINS_SHA256 \
  --output /absolute/new-host-reference-receipt
```

`nice 10` is the current reporting plan's value. The runner checks host, nice,
SCHED_OTHER, physical masks and slot count **against the pinned plan**. It derives
its own five-core mask and **every other occupied reporting slot** from that plan.
`--search-cpus` is optional and must agree with the derived reference slot;
`--background-cpus` and `--load-cpu` are rejected in fleet mode.

All other slots run the same complete own-tier corpus loop, rotating K0c/S/K2/K4
in 50-state blocks with their real 1/1/3/5-core masks. Normal and console profiles
therefore have 10 and 7 background slots, respectively, under the current T1 plan.
There is **no fleet perception worker**. Mac and Linux smoke retain replay-driven
perception. Each reference warms all slots for >=300 seconds, measures exactly
300 distinct states per tier for three rotated repeats, and measures each state's
200 and 160 ms deadline loop three times with the frozen 8 ms reserve.

The end-of-reporting reference placement and host-exclusion timeline are a
coordinator-directed amendment, pending review against PREREG §6.1. References
require a pinned END marker declaring reporting complete and outcomes sealed.
The runner reads only timing/census data. A mean physical-core MHz difference
above 5% fails the reference; this added clock gate remains a review draft.
Raw independent 1 Hz reporting and reference clocks remain SHA-bound.

`tiers-pins.json` schema is `clasher.e4v3.inputs.v1`:

- `profile`: `fleet-reference`; `final`: false; `threshold`: 0.5005528330802917.
- `specification`: exact `spec-pins.json` contents.
- `files`: relative input path -> SHA256, including `states.pkl`, frozen
  v1/R3a/calibration, exactness references and all profile/corpus source receipts.
- `runtime_files`: qualified frozen runtime relative path -> SHA256; generated
  with `prepare_bundle.runtime_pins(root)` and its qualified source binding.
- `measurement_files`: this package's `.py`, `.sh`, `spec-pins.json` -> SHA256.
- `sets.golden`: 125 unique IDs. Pinned `golden.json` native scores and
  `belief-reference.json` posterior/ledger/sample/RNG references are checked on
  **every host before timing**. Separate native/belief-only golden fixtures need
  no policy inputs. A mismatch beyond the registered r3 tolerance drops ALL tiers.
- `sets.speed`: ordered own-tier ID lists for `K0c`, `S`, `K2`, `K4`, exactly 300
  distinct IDs each; rows' tier labels must agree.
- `corpus_receipt`: relative pinned T1 `corpora.json`. Its `tiers` retain capture
  health (`eligible_search_opportunities`, `deadline_cut`, `suspended_transaction`),
  selected-state `{id,sha256}` inventory, selected suspended count and source
  capture SHAs. Inventory IDs and counts must agree with `sets.speed` and rows;
  historical per-row pickle SHAs are provenance, not reserialized on another host.
- `deadline_replay_semantics`: reviewed disclosure of committed posterior copies
  and disabled resumable private preparation. Both fleet and Mac use this value.
- `topology`: `P`: all Linux logical IDs; `E`: empty; labelled Linux accounting.
- `reference_load_profile`, for example:

```json
{
  "plan": "reporting-plan.json",
  "host": "127x01",
  "console_rule": false,
  "slot_count": 11,
  "reference_slot": 0,
  "warmup_seconds": 300,
  "perception": "none",
  "reporting_mhz": "reporting-mhz.jsonl",
  "reporting_end": "reporting-end.json"
}
```

All three source paths above must appear in `files`. The plan is the pinned T1
plan containing `compute.hosts`, physical CPU lists/census CPU, nice, scheduler,
slot width/count, console count, SMT policy and forbidden hosts. Reporting MHz
uses T1's existing rows `{utc, slots, physical_core_mhz:[{cpu,mhz},...]}`. The END
marker contains `{host, reporting_complete:true, outcomes_sealed:true}`.

`states.pkl` executes only after all pins pass. Each production speed, agreement
or scheduled decision row has **exactly these 20 top-level fields**:

| Field | Meaning |
|---|---|
| `id`, `tier`, `seed` | Unique string ID, own tier, excluded game seed |
| `info` | Physical `fair_player.Information`; keep **info.packet physical**; tick is `info.tick` |
| `reserved_packet` | Exact own-channel reserved packet, used by mask/inference/candidates |
| `pending` | Ordered Reservation objects or dicts: submitted,due,action,card,cost |
| `opponent_elixir` | Public D1-derived planner value |
| `d1_before` | Pre-poll D1Tracker attribute dict, excluding builder |
| `d1_events` | Complete accepted public recorder history including seats |
| `d1` | Committed post-update D1, checked after the decision timer |
| `policy_rng_state` | CPU Torch generator state immediately before fallback |
| `candidate_rng_state` | NumPy state immediately before candidate generation |
| `belief_before` | Committed public posterior copy with `_pending=None` |
| `belief_had_suspended_transaction` | Boolean presence of original live private work |
| `belief_rng_state` | NumPy state immediately before public opponent sampling |
| `opponent` | Sampled public hypothesis, never the true opponent deck |
| `root_rng_state` | Same RNG immediately before R.root, after belief.sample |
| `root`, `root_digest` | Hypothetical native root and digest |
| `strata` | Exactly `{elixir,legal_play_count,bins}`; bins validated against [3,6]/[1,128] |

Unknown or missing fields fail closed. `belief_resume`, top-level `tick`,
`elixir`, `legal_play_count`, and `replay_timestamp_seconds` are rejected.
Mac's pinned `packet_schedule` binds `{id,tick,timestamp_seconds,offset_seconds,
opportunity}` separately; tick must equal the row's `info.tick`, and offsets must
agree with sealed timestamps. Production rows require `d1_before`/`d1_events`;
the direct post-D1 shortcut is confined to legacy Linux smoke.

Capture includes **all >1-candidate public search opportunities**, including
live deadline cuts and decisions before live root construction. T1 reconstructs
eligibility/posterior/sample/root on independent no-deadline copies after the live
timer. The live game remains unchanged. Probes 0/1/2 are excluded. Suspended
private work is cleared in the copy and disclosed per row; no partial preparation
credit is replayed. **This deadline-replay amendment remains pending review.**
No-deadline replay checks D1, sampled opponent, pre-root RNG and root digest.
Deadline replay retains cutoff/fallback/no-complete-play and wall distributions.

Replay fixture cloning occurs before packet arrival and is separately recorded as
`replay_setup_seconds`. Timed work includes D1 update, mask, frozen CPU
`CachedPolicy` (S with its registered threshold), belief preparation, proposals,
candidates, sample/root, native scoring and reduction. Checks and agreement
formatting occur after the timer. MPS uses the explicitly synchronized adapter.

Each host produces SHA-sealed `speed-reference-raw.jsonl`,
`deadline-reference-raw.jsonl`, `capacity.jsonl`, native/belief exactness receipts,
source plan/MHz/END/corpus receipts and completion receipt. Host summary JSONs have
a `scope` key in addition to tier keys.

Pool host receipts with the same runner:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /absolute/pinned/python -B /absolute/e4v3/measure_tiers.py \
  --pool-fleet-references --pool-input /absolute/approved-pool-input.json \
  --pool-input-sha256 APPROVED_POOL_INPUT_SHA256 \
  --output /absolute/new-pooled-reference-receipt
```

```json
{
  "schema": "clasher.e4v3.fleet-pool.v1",
  "hosts": [
    {"directory": "/absolute/host-reference-receipt", "manifest_sha256": "SHA256"}
  ]
}
```

Pooling verifies every complete host's seal, code/specification/policy pins,
native125/belief125×ON/OFF qualification, matching corpus/runtime/plan, exactly
three raw repeats per state and both deadline budgets. **Initial per-state walls
are medians of all raw hosts × repeats.** Each host's geometric mean speed ratio
(pooled state wall / host state median) must lie within ±5%; hosts outside are
explicitly excluded in one pass. Remaining raw observations are pooled again;
a retained host outside ±5% after pooling fails for review without further
iteration. Native/action/forward mismatches from even an excluded host fail ALL.
Deadline rates pool raw counts, retaining per-state distributions and numerators.

Outputs are SHA-sealed `speed-reference.json`, `deadline-reference.json`,
`pooling.json` (source seals, retained/excluded hosts, both host ratios and rule),
`fleet_reference.json` (registration metadata), and `pool-complete.json`. T1 merges
the `fleet_reference.json` tier-independent metadata into its reviewed
`registration.json`, with original SHA-bound source receipts, the separate
student/golden/belief refs, corpus receipt and packet schedule. This does not
freeze the packet or authorize reporting/Mac work.
