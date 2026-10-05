# Clasher action-architecture audit — 2026-08-17

## Scope and evidence boundary

This is a read-only architecture audit. It did not change production source,
train a policy, mutate a checkpoint, or run a gameplay workload. The current
source tree is intentionally dirty, so all conclusions are bound to the files
and checkpoint inspected below rather than to an assumed clean Git revision.

Primary evidence:

- `src/clasher/rl/action_space.py`
- `src/clasher/rl/model.py`
- `src/clasher/rl/imitation_objective.py`
- `src/clasher/rl/train_recurrent.py`
- `src/clasher/rl/structured_obs.py`
- `tests/test_rl_structured_policy.py`
- `reports/accepted6m_hand_slot_robustness_20260814.md`
- `reports/accepted6m_hog_slot_diagnosis_20260814.md`
- `reports/imitation_objective_design_20260809.md`
- `reports/architecture_experiment_ladder_20260811.md`
- `reports/rl_v2_training.md`

The retained structured checkpoint inspected was
`checkpoints/fresh_structured_causal_v1_seed1062701/resource_belief_gated_seed1063602/resource_u10_gate0.pt`,
SHA-256
`3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88`.
It contains 1,554,519 state-dict parameters and uses the legacy `slot`
deterministic hierarchy with no invariant slot-choice path enabled.

## Executive decision

Keep the flat 2,306-action Gym boundary and the exact per-card 18-by-32 legal
placement heatmap. Replace neither with continuous coordinates now. The first
fresh-architecture A/B should change only the high-level policy factorization:

```text
P(action)
  = P(play / wait / ability)
    * P(card identity | play, legal current hand)
    * P(tile | selected card, legal tiles)
```

The play/wait/ability gate must be a learned head trained from initialization.
The card selector must be a shared pointer/query over unordered current-hand
card tokens. The existing card-conditioned 576-tile head can remain. The final
choice is translated back to the selected card's current physical hand slot at
the environment boundary.

This is not the same intervention as enabling the existing `play-gate` decoder
or retrofitting the existing equivariant adapter. The former changes only
deterministic decoding; the latter removes a deeply used positional shortcut
after it has already shaped the representation. Both have already failed to
produce a safe replacement.

## What the current policy actually does

### Environment boundary

`DiscreteTileActionSpace` exposes:

- placement: `slot * 576 + tile`, for four slots and an 18-by-32 board;
- no-op/wait: action 2,304;
- champion ability: action 2,305.

Player-one integer tiles are canonicalized as `(x, y) -> (17-x, 31-y)`.
Continuous entity positions are canonicalized around board extents as
`(x, y) -> (18-x, 32-y)`. These are consistent coordinate conventions: tile
indices address cells, while entity coordinates address continuous cell
boundaries/centers.

The exact action mask is per card and per tile. It always admits no-op, admits
ability only when the champion rule says it is legal, and masks placements by
hand occupancy, own elixir/cooldowns, card deployment rules, tower/terrain
geometry, and current building/deployment occupancy.

### Policy factorization

The model does **not** learn 2,306 unrelated output logits. It computes:

- six high-level logits: four physical slots, wait, and ability;
- four card-conditioned 576-tile maps;
- `log P(slot/type) + log P(tile | slot)` for placements;
- the exact special-action log probabilities for wait and ability.

PPO samples the resulting exact joint categorical and computes exact joint
old/new log-probabilities. The zero-smoothing factorized imitation loss is
algebraically identical to exact 2,306-way cross entropy. Mechanics-aware
spatial smoothing changes only the expert tile target; it does not change PPO
or inference.

The retained checkpoint's six-logit head has 12,742 parameters. Its tile
query/key/bias/FiLM path has 92,417 parameters, excluding the shared 132,736-
parameter cross-attention tile decoder. These are small relative to the
1.55-million-parameter policy; shrinking the output vocabulary alone is not a
credible large throughput win.

### The positional shortcut

The high-level head receives pooled actor state plus memory and directly emits
four ordered slot logits. It does not score each current hand card through a
shared card query. The card tokens themselves also receive four different slot
embeddings by default. In contrast, the placement head already queries each
card token against shared tile keys.

This asymmetry explains why placement can be card-conditioned while card choice
remains highly physical-slot-dependent.

### Deterministic inference mismatch

The default deterministic decoder compares the strongest individual slot logit
against wait and ability. It can therefore wait even when the aggregate
probability of playing one of four cards is greater than the probability of
waiting. The optional `play-gate` decoder fixes that argmax calculation by
log-sum-exp aggregating the four slot logits, but leaves training, stochastic
sampling, the positional slot head, and the learned representation unchanged.

A raw action-type clone demonstrated the limit of this decoder-only fix. It
improved held-out likelihood and play Brier score, yet scored 0-24 with the
legacy decoder and only 4-20 with `play-gate`. A 75% blend collapsed to 3-21
and minus 53 crowns, and the play-gate version did not rescue it.

## Causal evidence from failures

### Physical slot dependence is real and severe

The accepted 6.19M diagnostic parent converted legal-affordable Hog windows at:

| Physical slot | Plays / opportunities | Conversion |
| ---: | ---: | ---: |
| 0 | 0 / 23 | 0% |
| 1 | 18 / 20 | 90% |
| 2 | 4 / 4 | 100% |
| 3 | 32 / 32 | 100% |

It preserved card plus tile on only 51.07% of all 24 hand permutations. In the
three zero-use Hog games, Hog was visible, affordable, and legal; the policy
selected a different slot on every opportunity. This was not an action-mask or
access failure.

### Exact equivariance alone is not a behavioral fix

Several interventions removed or reduced the shortcut but regressed gameplay:

| Intervention | Symmetry / offline result | Complete-game result |
| --- | --- | --- |
| Post-hoc permutation-distilled pointer | 100% card+tile preservation; equal Hog rates | 41-31/+9 vs parent 51-21/+78; random playable no-op 0.18% |
| Fresh hard structural model, epoch 1 | 100% preservation; chronology transfer improved | 1-71/-181; 99.47% playable no-op |
| Same structural model, epoch 2 | lower fit loss, worse chronology | 1-71; 99.39% playable no-op |
| Full-dose sequence permutation | preservation 28.46% -> 63.15% | 42-30/+34; balanced 0-12; 90.52% playable no-op |
| 25% permutation mixture | preservation 40.58%; mixed per-card gains | 53-19/+66, but retained a 9.81% Hog slot-0 defect |
| Fresh conditional-slot-only equivariance | 100%; strongest chronology fit, NLL 5.983 | 0-72/-184; 98.48-100% playable no-op |

The common failure is distributional and architectural, not evidence that hand
order has semantic meaning. After the first altered action, recurrent states
leave the fixed teacher distribution. The old play mass, timing, and card
choice were also entangled in the same four positional logits. Removing only
one use of those logits after training does not preserve the behavior they had
encoded.

Frozen-head PPO did not solve this. Mechanics-query-only and action-type-plus-
query four-update branches were stable but nearly behaviorally inert: the full
72-game records and Hog slot-0 failure remained byte-identical. The fresh A/B
therefore needs the clean factorization from initialization plus on-policy
correction, not another tiny adapter on the old head.

## Decision registry

### ACT-1 — Keep the flat action ID at the Gym boundary

**Decision:** retain.

The flat ID is a serialization and compatibility surface, not the model's
internal architecture. It keeps the environment, replay tools, masks, PPO
storage, and viewer stable while allowing an entirely different internal
factorization.

**Reject a replacement if:** it requires changing replay/action IDs, loses
exact legal-action masks, or changes scalar/canonical action decoding without a
demonstrated policy benefit.

### ACT-2 — Train an explicit play/wait/ability gate

**Current:** six positional logits jointly normalize four slots, wait, and
ability. `play-gate` exists only as deterministic decoding.

**Candidate:** a three-logit mode head trained from initialization. `play` is
masked when no card has a legal tile; `ability` uses its exact legality; wait is
always legal. Stochastic training and deterministic inference use the same
factorization.

**Why promising:** it separates cadence/defense from conditional card choice,
eliminates four-way probability splitting at argmax, and makes play calibration
independent of the number and arrangement of legal hand slots.

**Smallest discriminating test:** on the same frozen recurrent corpus and three
seeds, train the current head and explicit-gate head from the same
initialization family for one matched epoch. Report play NLL, Brier score, ECE,
threat-conditioned play rate, playable no-op, and complete-game activity. This
is a collapse screen, not a promotion.

**Immediate rejection:** any seed exceeds 95% playable no-op, plays on fewer
than 5% of threatened decisions, or goes 0-12 against random after the first
matched epoch while its control does not.

### ACT-3 — Replace positional slot outputs with a shared card pointer

**Current:** pooled state -> four ordered slot logits; separate slot embeddings
also distinguish the current hand positions.

**Candidate:** remove current-hand positional semantics, keep Next distinct,
project pooled state/memory to a query, and dot it with each current card token.
Normalize only over cards that have at least one legal placement. Translate the
selected card token to its current environment slot after selection.

A single 192-to-128 query would add about 24.6K weights while the three-way mode
head saves a small part of the existing final layer: under 2% of the retained
policy. Parameter-match within 5% rather than weakening the pointer to make
counts identical.

**Why promising:** the same card in a different physical hand location should
receive the same score in the same counterfactual state. Giant/Royal Giant and
other semantic transfer remains available through their card tokens; exact
identity remains available too.

**Smallest discriminating test:** all 24 current-hand permutations over at
least 1,000 frozen recurrent states, including designated Hog and six other win
conditions, before any gameplay expansion.

**Exact structural gates:** 100% selected card-identity and selected-tile
preservation; max slot-logit and location-logit permutation error <= `3e-5`;
aggregate play, wait, and ability probability error <= `1e-6`. Any failure is
an implementation rejection, not a training result.

### ACT-4 — Retain the card-conditioned 18-by-32 heatmap

**Decision:** retain as the control and first candidate's spatial decoder.

The distribution is naturally multimodal: both bridges, several defensive
kites, and multiple spell centers can be simultaneously good. A categorical
map represents that directly and accepts the exact irregular legal mask.
Current tile features include normalized coordinates, sinusoidal coordinates,
blocked/river/bridge flags, and side. Card queries interact with shared board-
conditioned tile keys, so this is not a dense learned table of 2,304 unrelated
outputs.

The imitation objective already exposes conditional-location NLL, within-one-
and within-two-tile accuracy, distance, and mechanics-tolerant accuracy. Use
those metrics instead of exact action accuracy alone.

### ACT-5 — Coarse-to-fine categorical placement is a reserve experiment

**Status:** plausible, lower priority than the gate/pointer A/B.

A valid candidate could select a coarse 3-by-4-tile region on the 18-by-32
board, then one of its 12 local cells, with exact per-card legality applied at
both levels. It preserves multimodality and exact discrete PPO log-probability.

**Do not test yet unless:** profiling shows the current tile scoring/decoder is
at least 15% of learner forward-backward time or memory. It does not eliminate
the simulator's per-tile legality work, so output-vocabulary arithmetic alone
is not evidence of speed.

**Promotion gate:** at least 1.25x matched learner examples/s or 20% peak-memory
reduction, <=0.01 worse conditional-location NLL on every disjoint split,
<=0.5 percentage-point loss within one/two tiles, identical legal-action
support, and no gameplay/defense regression. Otherwise retain the full map.

### ACT-6 — Reject direct continuous coordinate regression

**Decision:** reject for the next architecture.

A single `(x, y)` estimate averages multimodal good actions into potentially
bad center placements. Projecting a Gaussian mean or sampled point onto the
nearest legal tile changes the distribution and invalidates the simple PPO
log-probability unless the projected discrete mass is computed exactly. A
mixture density that evaluates and renormalizes mass on all 576 legal cells
recovers correctness but also gives up most claimed compute savings.

**Reopen only if:** a candidate defines exact probability for every legal
discrete action without rejection sampling or post-hoc projection, passes
multimodal two-lane synthetic tests, and beats the heatmap on both spatial and
complete-game gates.

### ACT-7 — Coordinate-autoregressive placement is also reserve-only

Predicting row then column, column then row, or a coarse cell then a fine cell
can reduce logits while retaining a categorical distribution. The first two
introduce arbitrary axis-order bias and complicated irregular masks. The
coarse-to-fine form is the only version worth screening first, under ACT-5.

### ACT-8 — Preserve canonicalization and exact masks, but audit live parity

The existing 180-degree canonical transforms are correct and should be reused.
Do not flip extracted source images merely to create the opponent example;
transform the neutral structured coordinates and action labels numerically.

For training A/Bs, both arms must receive byte-identical masks. For eventual
real inference, the actor mask must be derived only from causal public/own
state available to vision. An exact simulator mask must not leak hidden or
unobservable state into the actor. Mask disagreement against the causal live
builder is a deployment blocker, independent of architecture quality.

## Predeclared fresh A/B

### Control

- Current unordered-state encoder choice held fixed by the parent architecture
  experiment.
- Current six-logit physical-slot/wait/ability head.
- Current card-conditioned 18-by-32 placement heatmap.
- Flat environment action IDs unchanged.

### Candidate

- Current-hand tokens share one slot embedding; Next retains a distinct role.
- Three-way learned play/wait/ability gate.
- Shared state query scores each current hand card token conditional on play.
- Same card-conditioned 18-by-32 placement heatmap.
- Exact joint composition and flat environment action IDs unchanged.

### Controls

- Three fixed seeds.
- Same replay IDs, recurrent sequence boundaries, train/validation/archetype/
  chronology partitions, simulator-native rehearsal, batches, optimizer steps,
  learning-rate schedule, augmentation, and PPO transition budget.
- Parameter count within 5%; no checkpoint interpolation or inherited slot head.
- Same spatial loss and exact masks.
- Architecture chosen without final held-out human partitions.

### Staged evaluation

1. **Exact construction:** normalization, legality, all-24 permutation, player-
   perspective, and stochastic/deterministic factorization tests.
2. **One-epoch collapse screen:** three seeds; offline factor metrics plus 12
   random and 12 balanced paired-seat games per arm/seed. This can reject but
   cannot promote.
3. **Matched fit:** continue both arms for the same predeclared epochs/steps;
   stop neither selectively. Evaluate replay-, deck-, archetype-, and
   chronology-disjoint corpora.
4. **Breadth:** the established 72-game random/balanced/reactive-defense/bridge-
   pressure/slow-push/spell-control/split-lane/Hog matrix per seed, with
   identical decks, seats, and seeds for control and candidate.
5. **Direct held-out:** 96 paired-seat candidate-versus-control games per seed
   over validation and whole-held-out-archetype decks.
6. **Historical and human-meta gates:** only after all preceding stages pass.

### Promotion metrics

All are required:

- exact structural gates from ACT-3;
- action-type NLL no worse on validation, whole-archetype, or chronology;
- play Brier no worse by more than `0.005` and ECE no worse by more than `0.01`
  on any of those splits;
- card-identity accuracy no worse by more than 0.5 percentage points on any
  split and strictly better in aggregate;
- conditional-location NLL no worse by more than `0.01`, and within-one/two-
  tile accuracy no worse by more than 0.5 percentage points, on every split;
- candidate breadth score and crown margin at least the matched control for
  each seed in aggregate; no workload block may lose more than one additional
  game or two crowns relative to control;
- weighted defense-event success no worse by more than 2 percentage points,
  defensive outcome and incoming-tower-danger no worse, and threatened action
  rate no worse by more than 2 points;
- for Hog and every designated win condition, counterfactual card selection is
  exactly slot invariant; in actual play every physical slot with at least two
  legal-affordable windows has at least one use and at least 25% conversion;
- direct held-out score at least 55% in aggregate with paired bootstrap 95%
  lower bound above 50%, no losing seat, deck-family, or archetype aggregate;
- learner examples/s at least 95% of control, rollout decisions/s at least 98%
  of control, and model parameter count no more than 5% larger;
- zero illegal outputs, non-finite tensors, recurrent-state resets, or causal-
  mask violations.

### Hard rejection conditions

Reject this candidate formulation, rather than adding card-name patches, if:

- exact permutation equivariance or exact joint normalization fails;
- two or more seeds hit the collapse screen;
- the candidate again improves offline chronology while scoring below 25% in
  the breadth screen;
- playable no-op exceeds 95% or falls below 1% across ordinary workloads
  without matching human/teacher cadence and threat response;
- any designated card is systematically unavailable from one physical slot;
- direct held-out play is <=50% or the improvement is confined to one seat or
  one deck family;
- the candidate needs post-hoc timing adapters, Hog-specific rules, or relaxed
  masks to pass.

## Ranked experiment roadmap

1. **Fresh explicit gate + shared card pointer, unchanged heatmap.** Highest
   information value; directly separates the two entangled causes of the known
   slot/cadence failure.
2. **Matched control under the same new two-actor corpus and recurrent native
   rehearsal.** Necessary to avoid attributing data-pipeline gains to the head.
3. **Gate-only factorial arm, if budget allows.** Three-way gate plus current
   positional card head identifies whether cadence separation alone fixes the
   collapse. It is diagnostic, not a preferred final design.
4. **Pointer-only factorial arm, if budget allows.** Shared pointer with mode
   probability derived from the old head identifies residual timing coupling.
5. **Coarse-to-fine heatmap only after profiling meets ACT-5's trigger.** Do not
   combine it with the first head experiment.
6. **Do not train continuous-coordinate or post-hoc equivariance variants.**
   Existing causal evidence and distribution semantics make them lower-value
   than the clean factorized A/B.

## Bottom line

The 2,306-action boundary is not the problem. The high-value change is to stop
making physical hand slots simultaneously represent *whether to play* and
*which card to play*. Train those decisions as an explicit mode gate and an
equivariant card pointer from the beginning, while keeping the exact masked
18-by-32 heatmap that already handles Clash Royale's multimodal placement
geometry.
