# Reviewed-input contract (implementation draft)

Targets the SHA-bound r3 documents in `spec-pins.json`; independent review is pending.
No reporting games, client input or outcome reads are implemented here.

T1 runs this **same file and same TierBackend.work** on its authorized exclusive
01/03/08 hosts. This worker does not access those hosts. Unlike Linux smoke mode,
fleet mode requires nice 10, five physical search cores, a separate five-core
frozen-corpus background slot and a separate TRAIN perception CPU. The load
profile must first be reviewed as comparable to the reporting-game load; merely
setting the boolean below is not evidence of that review.

```
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  nice -n 10 /absolute/pinned/python -B /absolute/e4v3/measure_tiers.py \
  --fleet-reference --bundle /absolute/reviewed-reference-inputs \
  --runtime-root /absolute/fresh-frozen-runtime \
  --native /absolute/qualified-native/clasher_core.abi3.so \
  --search-cpus 0,1,2,3,4 --background-cpus 5,6,7,8,9 --load-cpu 10 \
  --manifest-sha256 APPROVED_TIERS_PINS_SHA256 \
  --output /absolute/new-fleet-reference-output
```

CPU IDs are examples: T1 binds reviewed physical masks on each host, excludes SMT
siblings and overlaps, and stages fresh output directories. Fleet mode warms
loaded work for at least 300 seconds, takes **three rotated repeats of 50-state
blocks** for all four own-tier corpora, and executes 200 and 160 ms deadline loops
with the same 8 ms reserve. It records full walls, cutoff, fallback, no-complete-play,
perception and independent 1 Hz CPU/process census. It does not generate matches.

`tiers-pins.json` schema is `clasher.e4v3.inputs.v1`:

- `profile`: `fleet-reference`; `final`: false; `threshold`: 0.5005528330802917.
- `specification`: exact contents of `spec-pins.json`.
- `files`: relative input paths -> complete SHA256 (including `states.pkl`, R3a,
  calibration, v1, TRAIN media/timing/registration and load weights).
- `runtime_files`: qualified frozen runtime relative paths -> SHA256; use
  `prepare_bundle.runtime_pins(root)` to generate these and verify qualified source.
- `measurement_files`: this directory's `.py`, `.sh`, and `spec-pins.json` -> SHA256.
- `sets.golden`: 125 unique IDs; pinned `golden.json` native references and
  `belief-reference.json` posterior/RNG references are required and checked before
  reference timing on every host. These golden IDs may be separate legacy rows.
- `deadline_replay_semantics`: reviewed disclosure of clearing suspended private
  work in sealed copies; required in the production pooled registration packet.
- `sets.speed`: `K0c`, `S`, `K2`, `K4` -> ordered lists of **at least 300 distinct
  string IDs each**, captured from that tier's excluded smoke histories.
- `topology`: `P`: all Linux logical CPU IDs; `E`: empty; labelled Linux accounting.
- `reference_load_profile`: `reporting_load_profile`: true, `warmup_seconds`: >=300,
  `background_cpus`: the exact five IDs, `replay_cpu`: the exact replay ID. Include
  the reviewed load profile identifier and supporting source receipts in `files`.
- `load`: `kind`: `v3-body-hud-only` or admitted `v4`, `label`, `target_fps`: 20,
  `config`: pinned relative `body`, `hud`, `geometry` and `device`: `cpu` for fleet;
  `split`: pinned TRAIN registration; `matches`: pinned relative match directories.
  V4 additionally requires its authenticated owner launcher and selection.

`states.pkl` is a SHA-approved pickle of public/sampled rows, loaded only after all
pins match. A union file can contain golden and packet rows as well as speed rows.
Own-tier speed rows require:

| Field | Meaning |
|---|---|
| `id`, `tier`, `seed` | Unique string ID, K0c/S/K2/K4, excluded game seed |
| `info` | Physical frozen `fair_player.Information`: seat, tick, physical own state, public events, physical confidence packet. **Do not overwrite info.packet with its reserved version.** |
| `reserved_packet` | Exact `ch.own_packet(info,R.builder).packet` at current poll |
| `d1_before` | Dictionary of D1Tracker attributes **excluding builder**, before current poll |
| `d1_events` | Complete accepted public recorder event list up to this poll, including seats |
| `d1` | Post-update D1 row, used to verify reconstruction |
| `policy_rng_state` | CPU Torch generator ByteTensor before fallback sampling, including earlier policy-only polls |
| `candidate_rng_state` | NumPy candidate RNG state before current candidate call |
| `belief_before` | Committed `Belief` at packet entry, with `_pending=None` |
| `belief_had_suspended_transaction` | Boolean recording whether the original live belief had private suspended work; seal `_pending=None` in a COPY only |
| `belief_resume` | Optional lossless `{tick, events, steps_completed}` if an independently reviewed capture can certify counted yields |
| `belief_rng_state` | NumPy state before sampled-opponent draw |
| `opponent` | Actual **sampled public hypothesis**, never the true opponent deck |
| `root_rng_state` | Same NumPy RNG state immediately before R.root, after belief.sample |
| `root`, `root_digest` | Frozen hypothetical native root bytes/string and digest |
| `pending` | Ordered Reservation objects or dictionaries: submitted,due,action,card,cost |
| `opponent_elixir` | Public D1-derived value used by the frozen planner |
| `strata` | At least `elixir`, `legal_play_count`; include preregistered bins |

Store tick in `info.tick`; also storing `tick` explicitly is useful for audits.
Eligible speed rows represent actual search opportunities, not blocked policy-only
polls. Seal prior policy-only history through D1 and policy RNG states.

A suspended belief generator is unpicklable. The coordinator's capture contract
seals a COPY of the committed posterior with `_pending=None`, records
`belief_had_suspended_transaction`, and leaves the live collector unchanged.
No-deadline calls already discard suspended work. For deadline references, both
fleet and Mac replay the identical full public-history update without partial
preparation credit. **That is a disclosed deadline-replay amendment, pending
independent review; it is not established live-loop equivalence.** Raw deadline
rows and the summary retain the flag/count. Do not silently mark it qualified.
An optional lossless counted-yield `belief_resume` descriptor is supported, but
must not be substituted without a reviewed corpus contract change.

No-deadline reference calls reconstruct and check the sampled opponent and root.
Deadline calls permit a different completed subset/fallback, retain every observed
wall, and compare population rates rather than asserting action equality.
The runner includes D1 advance, reserved mask, inference, belief update/sample,
candidates, root, scoring and reduction; no submissions or late engine actions.

Outputs `speed-reference.json` and `deadline-reference.json` contain a receipt
`scope` key in addition to their four tier keys; pooling consumes those tier keys.
Each host's raw receipt has its own SHA manifest. The coordinator pools per-state
median walls and deadline counts, checks host differences within 5%, and seals the
combined reference packet. This mode does not itself perform cross-host pooling,
freeze inputs, or grant reporting authorization.
