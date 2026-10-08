# D1 and packed-store API

`derived_d1.DerivedD1(costs)` accepts `PublicEvent(tick, kind, name, amount,
x, y)` through `accept(event)` or cumulative `update(tick, events)`. Kinds:
`card`, `ability`, `collector`. Costs are a public catalog, not a deck prior.
`derived()` returns names; `sidecar_observer.SidecarObserver(builder)` converts
them through the pinned v5 `card_action` vocabulary. The class is a context
manager around frozen `reconstruct_perspective_v5(..., row_observer=observer)`.
After reconstruction, call the observer once on its retained battle if
`game.summary['terminal_context_row']` is true. `arrays()` returns `(d1, audit)`.
Audit arrays are kept in a separate directory. `intent_targets(compact, d1,
cut_tick)` returns target-only arrays. See `replay_sidecars.py` for the adapter.

Queue/refill semantics: full pending queues can contain 4–8 cards; D1 exports
the first four, plus queue length. Unknown card = token 0. Refill is integer
milliseconds. Elixir has both float32 and exact integer units (1e-4 elixir).
Histories are newest first, length 8. Features are `[min(age_ticks/1200,1),
x/18, y/32]`, with coordinates rotated to the learner at the bottom. Ability
history has separate IDs and ages. Own deck is the known initial hand+queue
order; this is also the intent-class order. Intent includes the current row's
labelled play, if present, at delay zero. Delay boundaries are twelve geometric
values from 0.05 to 10 seconds, then the tail bin. Missing future play is
right-censored at the cut tick. Intent values are targets, never inputs.

Store: `imitation/data/c56-store-v1/{train,dev,eval,eval_ood}/`.
Every named column is a `.npy` file loadable with `np.load(..., mmap_mode='r')`.
Each role has `manifest.json` (array dtypes/shapes/hashes, row/entity counts,
perspective boundaries). Root `manifest.json` pins roles, eval spec and sidecars.
All retained source rows are present; `excluded_leak` perspectives are absent.

`PackedStore(root, role)` loads read-only columns in `.arrays`. `batch(indices)`
returns rows, expanded boolean action masks, padded entity IDs/levels/features,
and entity mask. Entity features remain the 17 frozen compact columns; the
model should use its v5 mapping. Raw ragged columns are `flat_entity_*` and
`entity_offsets` (N+1). `mask_index` addresses root `mask_table.npy`, deduplicated
across the corpus; `source_mask_index` preserves the original local index.
`source_unit` and `source_row` locate originals using root `plan.json`.

`weights` includes supervision validity and the frozen quality/mode/balance
factors. Proxy and family counts use train perspectives only; the balance factor
is the minimum of their 1/sqrt(count) caps, c=1 (no tuning), so both group caps
hold without multiplying redundant caps. `wait_ipw` is 4 on waits and 1 otherwise:
multiply it only for epoch samples that keep 25% of waits. Evaluation uses
all supervised rows with natural unit weights, as the frozen specification says.

Baseline timing output preserves `play_wait_nll` / `play_wait_brier` over all
supervised rows (frozen JSON definition). The additional `*_playable` metrics,
`playable_rows`, `hazard_calibration_playable` and `ece_playable` use rows with
at least one legal card play, matching the DESIGN/model timing denominator.
P16 scores cover 648 dev and 705 eval perspectives; eval_ood has no P16 slice.
CPU scoring uses two disjoint unit partitions (S122 reserves 78 hub workers), keeps whole recurrent
perspectives intact, and merges raw statistics before computing calibration.

This is an interface description, not a PASS receipt. Fitting waits on
`data/receipts/T3-PASS.json`; S122 observer qualification waits on T1-PASS.
