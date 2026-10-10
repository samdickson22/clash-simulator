# Fleet input contract (review draft)

Uses the frozen r3 specification in `spec-pins.json` and the public row names in
T1 candidate ba3dc8b0, unchanged in freeze95883be0
(`reports/explore/t1/receipts/corpus-contract-draft.json`).
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

Signed Amendment 1 governs END placement. The additional committed completion,
phase, blind ledger/counted inventory, final OP-1 through OP-6 guard and ordered-attempt inputs are defined in
[FLEET-END-CONTRACT.md](FLEET-END-CONTRACT.md). References require committed T1
completion and every counted reporting/replacement phase. Stopped phases retain
verbatim exits and valid counted blocks; failed/unstarted work does not reject
the phase. Completion SHA-binds T1's committed blind ledger and health-only
counted inventory. Only full-occupancy
reporting census/MHz joins enter the <=5% signed mean-clock gate. All counted
hosts must remain in the END pool, whose host list equals the pinned reporting
host set; an outlier fails the pool for an outcome-blind
amendment. The runner reads only timing/census data. Raw independent 1Hz reporting
and reference clocks remain SHA-bound. A6 real fleet smoke is still pending.
All nine final frozen guard modules are required, including perception
confirmation, owned-supervisor identities, parent-source seed/08 join and OP-6
SSH-family budgets. Invoke T1's frozen seed admission once before census; pin
the exact live job freeze and every staged/live seed/join dependency as specified
in the END contract. Any console
user stops the reference. Independent 1 Hz sample budgets and fixed 50-state
work-block budgets are retained; SSH/idle or dbus flagged references cannot
qualify. The coordinator must explicitly open the clean window after serial/A2
transports are gone and08's HTTP cache is retired; no reference runs meanwhile.

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
  no policy inputs. Linux fleet requires EXACT, zero error; any mismatch drops
  ALL tiers. The registered r3 near-exact tolerance applies only to Mac.
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
  "end_evidence": "end-evidence.json",
  "amendment": "amendment-1.md",
  "guard": {
    "root": "t1-guard",
    "job": "/absolute/approved-t1-job",
    "freeze": "t1-freeze.json",
    "admissions": {"system-bus-admission.json": "guard-admissions/system-bus-admission.json"},
    "seed_inputs": {"REPOSITORY_SEED_OR_JOIN_PATH": "BUNDLE_COPY_PATH"}
  }
}
```

All referenced source files above must appear in `files`. The plan is the pinned T1
plan containing `compute.hosts`, physical CPU lists/census CPU, nice, scheduler,
slot width/count, console count, SMT policy and forbidden hosts. Reporting MHz
uses T1's existing rows `{utc, slots, physical_core_mhz:[{cpu,mhz},...]}` and joins
each phase's census on UTC; `inflight == slots` is required. A three-Boolean END
marker is rejected: the completion and phase files must match committed Git bytes.

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
credit is replayed. Amendment 1 ratifies this conservative replay on both platforms.
No-deadline replay checks D1, sampled opponent, pre-root RNG and root digest.
Deadline replay retains cutoff/fallback/no-complete-play and wall distributions.

Replay fixture cloning occurs before packet arrival and is separately recorded as
`replay_setup_seconds`. Timed work includes D1 update, mask, frozen CPU
`CachedPolicy` (S with its registered threshold), belief preparation, proposals,
candidates, sample/root, native scoring and reduction. Checks and agreement
formatting occur after the timer. MPS uses the explicitly synchronized adapter.

Each host produces SHA-sealed `speed-reference-raw.jsonl`,
`deadline-reference-raw.jsonl`, `capacity.jsonl`, `guard-admission.json`,
`guard-blocks.jsonl`, timestamped `gc-events.json`
with actual 200/160ms decision deadlines, native/belief exactness receipts,
source plan/MHz/END/ledger/counting/corpus receipts, raw guard occurrence files
and completion receipt. Host summary JSONs have
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
  "schema": "clasher.e4v3.fleet-pool.v2",
  "context": {"bundle": "/absolute/approved-bundle", "manifest_sha256": "SHA256"},
  "hosts": [
    {"host": "127x01", "attempts": [
      {"directory": "/absolute/host-reference-receipt", "manifest_sha256": "SHA256"}
    ]}
  ]
}
```

Pooling verifies every complete host's seal, code/specification/policy pins,
native125/belief125×ON/OFF qualification, matching corpus/runtime/plan, exactly
three raw repeats per state and both deadline budgets, and unflagged budgets
for every fixed work block. **Initial per-state walls
are medians of all raw hosts × repeats.** Each host's geometric mean speed ratio
(pooled state wall / host state median) must lie within ±5%; a counted host
outside the band fails the entire END pool. No counted host is excluded.
Every listed failed attempt is classified mechanically; at most one technical
repeat is permitted and the first passing attempt is used. Native score
mismatches from any attempted host fail ALL. Cross-host S
joint gate/ordered-top8 and K0c sample/top8 use the registered local near-tie/gate
exceptions, with >=99.5% joint agreement and zero unexplained differences per
host/tier. Logits/probabilities may vary while discrete outputs agree. Conditional
policy exemptions are recorded in `fleet-policy-agreement.json`; every common
native candidate score remains strictly exact. All original forwards remain
source-pinned. Non-exempt action/candidate/score differences fail ALL.
Deadline rates pool raw counts, retaining per-state distributions and numerators.

Outputs are SHA-sealed `speed-reference.json`, `deadline-reference.json`,
`pooling.json` (source seals, retained/excluded hosts, both host ratios and rule),
`fleet_reference.json` (registration metadata), and `pool-complete.json`. T1 merges
the `fleet_reference.json` tier-independent metadata into its reviewed
`registration.json`, with original SHA-bound source receipts, the separate
student/golden/belief refs, corpus receipt and packet schedule. This does not
freeze the packet or authorize reporting/Mac work. The A6 smoke-labelled plan
produces receipts that this production pool explicitly rejects.
