# Public placement mask v2 (opt-in; not a frozen-gate amendment)

`mask_version=1` remains the default. This version number is independent of
observation contract v5 and of the older tensor backend's `SimplePublicMaskV2`.
No gates (b)/(c), T5/T11 training, frozen evaluation registrations, or v4
perception-worker files are changed. Do not overwrite their snapshots, masks,
cached tensors, admission receipts or result labels.

The r9/game006 exact replay contains six illegal model submissions: BombTower
at ticks 3030/3040/3050 and RoyalHogs at 3840/3850/3860. The detailed guard
receipt identifies **timed payload occupancy for all six**, including the
payload half of the combined building guard. The seat-0 model acts first.
The replay reproduces all 88 original accept/reject results. V1 allowed all
49 model submissions; six were rejected (12.245%): BombTower 3/10, RoyalHogs
3/4, other candidate cards 0/35. Across those states, 80/39,435 v1-legal
placement bits were engine-illegal (0.203%). V2 has zero false positives or
false negatives over all 202,752 placement bits; Rust/Python agree at all 88
states. This selected failure case is not a population-rate estimate.

V2 resolves every building's odd/even world anchor before strict square
overlap, uses serialized public body aliases for building radii, checks
visible timed payloads with inclusive circle/circle or circle/square contact,
and follows engine Crown Tower, air collision, ground relocation, terrain,
spell-target and formation-margin rules. The simulator's v2 fast mask also
restores bridge tiles unlocked by tower destruction. The old replay memo is
bypassed in v2 because its key omits payloads. [Detailed rules and evidence](reports/mask-v2/RULES.md).

The follow-up [capability census and visibility review](reports/mask-v2/BLOCKERS.md)
covers every current `blocks_deployment` route: Balloon, Giant Skeleton and
Bomb Tower death bombs, the falling Skeleton Barrel container, and Mighty
Miner's ability bomb. All are already represented in v2. Real-game public
effect evidence is recorded per type; complete opponent-view coverage of each
blocking interval remains a **live-admission requirement**, not an assumption.
Unseen or uncertain blockers require public-history-only conservative handling
or abstention, never insertion of private entity positions.

The [100,000-state audit](reports/mask-v2/summary.json) covers 132 distinct
recorded perspectives: 12,993 C56 and 87,007 S122-extension states, **230,400,000
placement bits**. V1 has 10,044 / 94,499,637 false-positive legal bits (0.01063%)
and errors in 1,352 states (1.352%). V2 has **722 false-positive bits in 40
states, zero false negatives**. Every residual is Cannon placement blocked by
an **enemy underground Goblin Drill hidden by contract v5**; an audit-only
counterfactual explains all 722, with zero unclassified residuals. The public
mask deliberately does not read those hidden positions. Thus unconditional
engine equality is not claimed; admitting that scope requires a separately
qualified public observation or engine rule change.

In payload-present states, the engine rejects 6,287 / 1,268,463 v1-legal bits (0.496%);
v2 has zero mismatches there. Sample v1 rates by card include BombTower
369/324,979 (0.114%), RoyalHogs 204/696,624 (0.0293%), Cannon 2,314/2,242,333
(0.103%) and MinionHorde 1,489/352,308 (0.423%); full card/situation counts are
in the receipt. One of 4,237 v1-legal **original human-coordinate** actions is
illegal (IceSpirit; 0.0236%). Retained/projected replay labels instead have
3/4,278 illegal actions under v1; v2 leaves the two hidden-Drill Cannon labels.
The v2 mask also admits one original Cannon-coordinate action blocked by the
hidden Drill. These are retained states from the first four source shards,
not an unbiased estimate of every recording or policy's proposal distribution.

All 11,062 computed oracle geometries match the simulator's v2 fast/scalar
guards. Rust/Python placement masks agree at 507 sampled human states plus
88 gate states (595 total). Tests: **111 passed, one skipped**; an additional
pre-existing empty-payload-query performance test fails identically in the
unchanged baseline (888 calls), documented separately. The audit reconstructs
IL_Replay sources; it does not rewrite frozen sidecars or use their old masks
as an engine oracle. [Rules/proof limits](reports/mask-v2/RULES.md),
[source pins](reports/mask-v2/runtime-pins.sha256), [test log](reports/mask-v2/tests.log).

S5's 1,536 archived games contain 5,770 rejections / 204,454 submitted commands
(2.822%); S6's 1,280 contain 1,448 / 147,286 (0.983%). These are **execution
rejections**, including noisy/delayed/stale commands. Those receipts retain an
action hash, not decision boards or individual proposal IDs: per-card
occupancy rates and search-proposal mask error rates cannot be recovered from
them. See `reports/mask-v2/s5-summary.json` and `s6-summary.json`; do not label
all of those rejections as this bug.

Enable explicitly with `PublicActionMaskBuilder(..., mask_version=2)` or
`ContractV5ActionMaskBuilder(..., mask_version=2)`; the cached wrapper and
`DiscreteTileActionSpace` accept the same flag. For C56 search, pass it to
**every** `PublicScriptedOpponent` and to
`c56_controller.metadata(builder, mask_version=2)` before constructing
`NativeScripts`. The planner rejects a mixture of v1/v2 rollout providers.

Upcoming adoption requires new registrations and artifact identities:

- **V2 proposer serving:** opt in at mask construction; qualify identity and
  payload coverage, logits/mask alignment, calibration, retained legal action
  mass, latency and fresh paired gameplay. Refit/retrain or validate the changed
  candidate distribution explicitly; do not relabel T5/T11 results.
- **L2-v4 runtime:** opt in for proposal filtering, Python rollouts and native
  rollouts together; rebuild/pin the Rust binary and metadata, rerun full
  placement parity, planner/deadline tests and fresh clean/noisy/delayed gates.
- **Live actuator:** establish public payload detections and board orientation,
  test localization/occlusion and all tile/anchor boundaries, recheck the latest
  observation at execution time, and qualify stale/simultaneous-command rejection
  handling. A mask at proposal time cannot authorize a later changed board.

Exact official-client parity is **not established**. Repository anchor/overlap
captures use Null's 15.535.86 and explicitly disclaim official parity. Public
reports support death-bomb blocking qualitatively, not current exact radii.
Official live boundary captures are an actuator-admission requirement. Hidden
enemy state, RNG, combat/deployment timers and engine cache internals must not
be added to the public mask to force equality.
