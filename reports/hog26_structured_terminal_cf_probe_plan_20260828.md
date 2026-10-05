# Hog 2.6 structured terminal-counterfactual restart

## Why the pooled lineage was rejected

The completed exact corpus contains 8,445 training roots and 2,210
opponent-signature-disjoint validation roots. All three 128-wide pooled-latent
members failed the offline gate: overall pairwise accuracy was
59.43-59.65%, terminal-outcome accuracy was 62.05-62.79%, and the best member
reduced ordinal regret by only 0.58% with 11 conservative overrides. No
controller was published and no promotion gameplay ran.

Two aligned alternatives failed to fix the ceiling. Base-relative-only loss
reached 60.44% relevant overall and 64.27% relevant outcome accuracy. An
explicit candidate-versus-base interaction head reached 60.66% and 63.17%.
This rules out network width, candidate-independent scoring, and irrelevant
candidate-pair loss as the primary problem. The retained state was only the
parent's 128-dimensional pooled board vector plus 64 recurrent values; entity
tokens and raw public structured state had been discarded.

## Why the signal is still worth pursuing

On a diagnostic heldout pair of decks, the partial all-pairs head at gain 0.50
and query stride 16 changed a matched 12-game result from 6-6 to 11-1: five
loss-to-win flips, zero win-to-loss flips, crown differential 5 to 18, and
tower-damage differential 21,117 to 47,387. The signal is therefore useful in
closed loop but does not generalize across decks through the pooled feature
bottleneck.

## Structured public-state contract

The replacement collector adds only actor-public fields already available to
the live adapter:

- up to 128 entity IDs, 32 dynamic entity features, and visibility mask;
- five visible own card slots (four-card hand plus public Next);
- 18 actor-global features;
- public opponent-history/seen-card arrays when configured;
- previous own action/reward, episode-start flag, and the existing parent
  recurrent/pooled features.

Critic entities/globals, exact opponent hand/elixir/deck/cycle, targets, RNG,
pending damage, and simulator objects are absent. The contract is
`public-actor-v1`. A local and x86-64 remote one-root smoke produced identical
structured entity/global/hand hashes and exact terminal labels.

The new ranker is a permutation-invariant public set model. It combines dynamic
entity features with the parent's compositional card-stat table and a bounded
identity residual, encodes visible entities with self-attention, and lets every
candidate attend to that public entity set. Candidate permutation and entity
permutation tests are exact.

## Bounded collection

One owned Prime CPU node is collecting a fresh dense probe:

- pod `670a8d184c12464cb02a73eb17e7a860`;
- US Nebius 64 vCPU / 256 GB, $1.5872/hour;
- 300 training games from the 1,720-deck train pool;
- 100 validation games from the 312-deck disjoint validation pool;
- up to 16 roots/game, query stride 16;
- minimum 3,500 train and 1,100 validation roots;
- exact terminal StrategyBot continuations, six strategies;
- atomic per-game shards, public structured-state contract, and hash-bound
  source/policy authority.

Package SHA-256:
`79ff376864dcd30360795d02f9199b9494fbf562d63e49d5c3442955950f271b`.
The local tmux supervisor
`clasher-structured-cf-supervisor-1169001` fails closed on remote exit, verifies
all 400 game IDs and aligned structured arrays, copies the corpus, terminates
only the owned pod, and fits one 64-wide/one-layer structured head on CPU.
Before terminating the pod or fitting, a separately tested verifier requires
the exact strategy/seat schedule, unique game/tick roots, at least 10% decisive
labels, nondegenerate base outcomes, aligned finite public tensors, five valid
own hand/Next identities, legal base/best/intervention actions, and exact
candidate-validity semantics. It publishes a hash-bound corpus-quality report.

Apple MPS was tested first and rejected for this head: masked multi-head
attention produced finite forward scores and loss but non-finite gradients on
the third mini-batch, corrupting 173,903 parameters. The same batches and model
remain finite on CPU. The production fit therefore uses eight CPU threads; no
MPS performance or correctness claim is made for this architecture.

## Decision gate

This is a representation probe, not a promotion run. The 100 external
validation games are deterministically partitioned by whole game into 30
model-selection games, 30 threshold-calibration games, and 40 final-holdout
games using frozen split seed 1169102, independently of the model-training
seed. No decision root crosses partitions. The selected epoch never sees the
calibration or holdout partitions; the controller threshold never sees the
holdout partition. The structured head must materially exceed the rejected
pooled family on that untouched final holdout:

- overall pairwise accuracy at least 62%;
- terminal-outcome pairwise accuracy at least 67%;
- optimal-action rate above the pooled best of 41.99%;
- at least 25 holdout overrides and 15 strict holdout improvements;
- zero ordinal regression at the calibrated threshold on both calibration and
  final holdout.

The final 40-game holdout is clustered by game, not treated as thousands of
independent candidate pairs. A frozen 10,000-draw whole-game bootstrap requires
the 95% lower bounds for overall accuracy, terminal-outcome accuracy, and
optimal-action rate to exceed the corresponding rejected pooled references
(59.65%, 62.79%, and 41.99%). Point estimates must still clear the higher
62%/67% thresholds. This prevents correlated roots from manufacturing false
confidence. Each metric resamples only whole games that actually contain that
metric; all 40 holdout games must support overall/optimal rates and at least 20
must contain terminal-outcome pairs, eliminating zero-denominator conditioning.

A mid-collection phase audit found that the first-eligible-root schedule is
front-loaded: at 179 completed games, all 2,776 roots were between ticks 256
and 2,360, with no late-regulation or overtime roots. Card/candidate coverage
was broad, but 2,234/2,776 terminal-optimal labels were no-op. Consequently,
even an offline PASS is explicitly representation-only and cannot authorize a
controller or gameplay promotion. It authorizes a second phase-balanced corpus
first. The new tested scheduler spreads 16 target decisions from tick 256
through 5,632, retaining playability and minimum-spacing constraints; games
that end in regulation naturally contribute fewer late targets instead of
backfilling them with more early roots.

The follow-up is frozen in
`reports/hog26_phase_balanced_terminal_cf_contract_v1.json` (SHA-256
`8354b54a0a5d35c45b761fea1575198e6ac314c8ff2334dee66f9ab68d169115`):
500 fresh-seed training games, 150 fresh-seed validation games, explicit
per-phase root floors including overtime, three later independent model seeds,
and a `public-actor-v2-action-time-recurrence` contract that adds the model's
own 64-value action-time structured cell plus its one-value accumulated play
hazard while continuing to forbid simulator and opponent-private fields.
The snapshot contract is executable rather than documentary: a real champion
decision test proves the captured action-time cell is tensor-exact to the final
64 values of the policy's 192-value repair representation. For this checkpoint,
the first 63 hidden channels exactly duplicate the cell; only the final hidden
channel stores accumulated play hazard. The contract therefore stores 65 values
instead of a redundant 128. Shape, dtype, finiteness, structural identity, copy
isolation, and timing semantics fail closed.

The first remote attempt then failed closed on a newly observed transient
`ChainLightning` runtime object from Electro Spirit. Its 16 partial shards were
discarded before combination. The generalized serialized-child identity
resolver now maps that execution object to
`projectile:ElectroSpiritProjectile`; the exact offending game was replayed
with 5,814 visible entity rows and zero unknown identities, and the replacement
attempt writes to a distinct v2 output root.

The v2 schedule itself was also rejected after 68 clean shards: 12 games
reached tick 3,600 but none survived to the linearly spaced first overtime
target at tick 3,840, making the 60-root overtime floor implausible. No v2
shard was combined or fitted. The phase scheduler now accepts explicit phase
boundaries and preserves the known regulation-to-overtime boundary at tick
3,600. An exact replay of the prior tick-3,684 game published an action-time
root at tick 3,608 with zero unknown entities and exact recurrent-tail parity.
The clean replacement writes to a distinct v3 root.

## Completed training split

The first-eligible-root training split completed all 300 games and combined
atomically:

- 4,699 structured roots;
- 702 decisive base-action improvements (14.94%);
- 1,736 base terminal wins (36.94%);
- exactly 50 games per StrategyBot and 150 games per candidate seat;
- winner balance 151-149;
- ticks 256-2,360: 2,391 early and 2,308 mid, confirming zero late/overtime;
- terminal-optimal labels: 3,728 no-op and 971 placements, with every Hog 2.6
  card represented among optimal placements.

Train NPZ SHA-256:
`aa9a8370667a35bdbcb8e6346a26145dda370ca4595784eaec6000a130f964ea`.
Train report SHA-256:
`8e7931ae9e08da24208d6d54a1f8a621d347899239d9b1a82b3aeb3f583216f0`.

## Data-contract rejection and clean restart

The full training aggregate exposed 7,540 visible `<unknown>` identities across
2,674/4,699 roots: 5,653 troops, 1,664 projectiles, and 223 effects. Padding was
exactly zero, so this was not array corruption. Runtime observations selected
parent card names before serialized child identities (for example
`SkeletonWarriors` instead of typed body `SkeletonWarrior`), and timed payloads
such as BalloonBomb execute as effect containers despite carrying a serialized
building identity. The probe was rejected before fitting; validation was
stopped, the 300 complete training shards were preserved, and owned pod
`670a8d184c12464cb02a73eb17e7a860` was terminated at a final $3.42 charge.
Rejection report SHA-256:
`000604bee780b7e6a6c4a2881ff9dd881ca92ad4dce7d910102a8a6e4e6380ac`.

The replacement resolver is namespace-aware and data-driven: character,
projectile, nested rolling-projectile, buff/effect, building, timed-payload, and
tower identities resolve through serialized definitions, with no card-name
branches. On identical 12-game seeds, the pre-fix audit had 28 unknowns across
94,186 visible observations; the corrected audit has zero, spans 48 typed
tokens, and preserves every game winner and terminal tick. Corrected audit
SHA-256:
`59395974c1ca5f5d8e06f108f50a99f4f8749dfc4a21bbb6ce88befd89bd7f0f`.

The v2 collector canary then produced exact roots at ticks 256, 1,688, and
3,120 before regulation ended, zero unknown identities, valid 64+1 recurrent
arrays, and a successful v2 combination. Canary NPZ/report SHA-256:
`9da106d63f057b426dcd6dc7922fdfc9cf954ecd90f52670990f812e620f4508`
and `26d64c655481149b20063d255767d7a07e0a78804cb0993318138a587cc7bd70`.

Checkpoint selection maximizes the minimum normalized progress toward the
predeclared 62% overall, 67% outcome, and 41.99% optimal-action gates. A
41-game/634-root internal snapshot caught the need for this rule: the prior
generic selector preferred a 55% outcome epoch, while gate-aligned selection
retained the earlier 76.67% outcome epoch. That six-game internal validation is
diagnostic-only and cannot pass or fail the full representation probe.

A fixed 69-game/1,065-root internal architecture screen compared 64-wide,
32-wide, stronger weight decay, and disabled identity residual. All variants
remained within roughly one point on the 17-game validation split; 64-wide had
the best normalized gate balance (0.8976). Width reduction and removing the
identity residual did not resolve generalization, so the full fit is frozen at
64 dimensions, one layer, four heads, hidden width 128, batch size 64, and
weight decay 5e-4. No further architecture choice will be made from that small
internal split.

An apples-to-apples pooled-head control on the same 800/265-root internal split
selected 54.33% overall, 49.45% outcome, and 37.74% optimal-action accuracy.
The frozen 64-wide structured candidate selected 55.65% overall, 60.73%
outcome, and 37.74% optimal-action accuracy. The sample is still too small for
acceptance, but the 11.28-point outcome advantage shows the raw public entity
set contributes information beyond the parent pooled latent and justifies
finishing the disjoint representation probe.

The structured checkpoint loader and paired gameplay evaluator are wired and
tested. A wave-one head at its conservative calibration threshold abstained in
a one-game integration smoke. A separate diagnostic copy with gain threshold
zero made 20 legal public-state overrides and changed that same balanced-bot
game from a 1-2 loss to a 1-0 win. This proves the inference path is live; the
forced threshold is explicitly non-promotable and does not alter the full-fit
gate.

Failure closes the ranker line and redirects work toward direct policy training
with richer structured supervision. Passing triggers independent seeds,
calibration, live-controller integration, and only then the clean 48/96-game
screen and quarantine pools. The parent policy remains unchanged throughout.
The paired-gameplay finalizer also rejects incomplete or stale evidence before
applying those behavioral thresholds: it freezes the exact six strategies,
fresh seeds, query stride, candidate count, minimum tick, paired game IDs,
action-value mode, deck authorities, and balanced candidate seats.
Its quarantine confidence interval resamples within each frozen strategy rather
than pooling games indiscriminately, and every strategy must have nonnegative
paired score and crown deltas so an aggregate win cannot hide a matchup-class
regression.

## Remaining validity risk

Every current root has one deterministic continuation policy chosen from six
public StrategyBots. The strategy identity is intentionally not given to the
ranker because it is not observable in a real match. Consequently, terminal
labels contain opponent-policy Monte Carlo variance, especially when two
publicly similar states are continued by different bots. Public entity/deck
evidence plus recurrent history may reduce this ambiguity, but a structured
pass still proves only robustness to this six-bot continuation distribution.

Before claiming human-level transfer, later stages must either average each
root across several continuation policies, include frozen learned opponents in
the continuation league, or replace long-horizon single-continuation labels
with a calibrated public outcome model plus shorter exact tactical rollouts.
The PyTorch task has been given the dense multi-fork workload because making
this statistically stronger label practical depends on batched resident forks.

If this full structured probe fails, no further width, depth, identity, or
threshold search will be performed on the same labels. The next corpus contract
must additionally preserve the policy's exact pre-decision recurrent hidden and
cell state, then label each root using several StrategyBot/frozen-policy
continuations or a shorter tactical horizon plus calibrated public outcome.
That corpus can supervise the full entity-aware policy directly instead of
forcing another standalone ranker to reconstruct information that was already
inside the actor.
