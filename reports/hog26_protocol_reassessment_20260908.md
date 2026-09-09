# Hog 2.6 outcome objective: September 8 reassessment

Authority: existing `clasher-event-policy` worktree, branch
`codex/hog26-event-policy-redesign`, source HEAD
`559fe9fc75e7ae64078d1887d6c17bc5b5e0ed59` before these edits. The Desktop checkout
was read for its handoff and instructions only. Existing datasets, checkpoints,
and historical reports were preserved. No final labels were opened.

## Decision

Continue complete-game TRAINING-data collection with the frozen behavior policy.
Do not fit the proposed primary candidate yet. The original protocol remains an
unaltered historical artifact; use
`reports/hog26_procedural_outcome_protocol_reassessed_20260908.json` going forward.
Its explicit `training_readiness` blocks candidate fitting until the margin design
and final evaluation coverage rules are frozen. The overall objective is active,
not achieved. No search, policy update, PPO, or policy promotion is authorized by
these results.

## Verified data and corrected exposure

Shard 0 still hashes to
`7edd615cfe63400bd64644b6be7d26dbd9532fca00f05bebfb3e29d7e7849a3f`.
Its existing audit has 128 complete games, 58,161 rows, 51 wins and 77 losses.
Balanced is 24/64 wins, random 27/64. There are only 11 late matchup clusters,
with wins in two. Thousands of adjacent decision rows are not thousands of
independent late outcomes. Zero natural draws in this shard does not validate
natural draw calibration; controlled mirrored draws address a different question.

All three retained legacy natural training corpora contain actual `split-lane`
episodes. Existing protocol tests only inspected the new shard schedule. Used the
existing complete-episode subset utility to retain balanced, slow-push, and random
in new artifacts, preserving all originals. Retained 96 + 24 + 24 = 144 games
and 67,286 rows; removed 48 whole split-lane games. Each subset passed the corpus
audit. Compared every retained row tensor, episode label, ordinal, and hidden/cell
reset with the selected source episodes: exact equality. Stream and categorical
indices are deliberately remapped by the subset utility; source indices and SHA
provenance are in the individual subset reports. Summary:
`reports/hog26_legacy_filter_verification_20260908.json`.

The frozen behavior policy's direct training corpus seed1261001 and validation
corpus seed1262001 both declare all seven opponent styles including split-lane;
the policy report pins their SHA values and paths. Therefore the amended claim is
held-out opponent data for NEW outcome-head fitting/calibration only. The full
behavior-policy lineage and historical model-development decisions have seen this
style. This experiment cannot establish whole-system unseen-opponent performance.

Generated-family isolation likewise applies to generated combinations, not all
ancestral original decks. Structural deck compilation is not strategic realism:
family-000 includes a Cannon + Inferno Tower + Rocket combination, alongside
Hog/Goblin Barrel mixtures. Broader coverage is a useful hypothesis, not an
established diagnosis or a substitute for tests against coherent original decks.

## Margin capacity defect measured on actual training targets

The model uses `0.5 * (1 - public_progress)**6 * tanh(raw)` as its correction to
current public tower margin. Time progress is not certainty about future tower
damage. The following bounds use exact complete-game targets from shard 0 only.
For each row, a perfect predictor constrained by this cap could improve absolute
error by at most `min(abs(terminal_margin - current_margin), cap)`.

| Sampling | Phase | Samples | Current-margin MAE | Maximum power-6 improvement |
|---|---|---:|---:|---:|
| All retained rows | early | 31,884 | 0.30068 | 0.15138 |
| All retained rows | middle | 24,833 | 0.19178 | 0.01476 |
| All retained rows | late | 1,444 | 0.18245 | 0.00020 |
| Trainer phase representatives | early | 128 | 0.31340 | 0.14273 |
| Trainer phase representatives | middle | 126 | 0.17056 | 0.00769 |
| Trainer phase representatives | late | 14 | 0.07925 | 0.00015 |

The trainer chooses at most one row per episode/phase near the phase center; its
"phase-balanced" evaluation is not the mean of every retained decision row.
Every selected late target is outside the power-6 correction cap. A low late
regression can be obtained simply by nearly reproducing current margin. That is
not proof of learned future damage. Lower powers have greater representational
capacity, but these oracle bounds do not show they learn or generalize better.
Results for powers 0, 1, 2, 4 and 6 are recorded in
`reports/hog26_margin_capacity_reassessment_20260908.json`.

The prior static/GRU failures do not rule out memory or richer state. They shared
strong output suppression and small data distributions; the old narrative that
coverage is definitively the bottleneck was too strong. Candidate architecture
must be predeclared after training-only diagnostics, before new selection and
calibration labels. Do not merely lower an acceptance threshold.

## Executable safeguards and remaining acceptance design

The candidate wrapper now refuses protocols without an explicit resolved review,
requires successful audits bound to current corpus SHA values, checks procedural
family role disjointness and exact collection authority/seed/game counts, and
checks actual episode opponent indices across all fitting/calibration inputs.
Missing, failed, or stale audits cannot be replaced by file-existence checks.
The original protocol cannot silently launch fitting through this wrapper.
The underlying research trainer remains a general-purpose tool; this is not a
security boundary against someone deliberately bypassing the campaign wrapper.

Amendment predeclares eight physical controlled-draw final games (16 paired actor
views), seed1278703, and replication seeds1278802/1278803. All three candidate
state digests must be frozen before final labels; all seeds must pass, with no
best-seed selection. Paired actor views are not independent physical games.
These are declarations, not completed collections or acceptance results.

Still required before fitting: choose the margin representation/output constraint
and predeclare per-seat/per-style and late-outcome evidence adequacy. Existing
aggregate metrics cannot by themselves establish all of those claims. Preserve
all existing numerical thresholds and reject insufficient coverage explicitly.
Fresh final evaluation execution and exact-terminal ranking must enforce the
amended declarations before any controller improvement.

## Continued work and validation

Launched only training shard 1 (bridge-pressure + reactive-defense, 128 complete
games, seed1278502) using the amended protocol. Its supervisor executes the
protocol-bound audit only after collection succeeds, and does not launch model
fitting. Process record:
`reports/hog26_procedural_shard1_resume_20260908.json`; log:
`reports/hog26_procedural_shard1_resume_20260908.log`.
At launch no matching Clasher collection/training process was active, system
memory free percentage was 76%, and a RoadForge CPU workload was left untouched.
Process liveness is not a completed shard. Do not read or train from partial rows.

Validation: 12 focused tests passed across protocol, candidate wrapper, shard
runner, and audits; Ruff passed. Original shard 0 was hash-verified and its prior
audit inspected without overwriting it. New subset and controlled-draw training/
selection corpus audits passed. No trained candidate or final acceptance exists.

## Continuation: calibration leakage and training-family screens

Found a further executable protocol defect: `train_hog26_actor_outcome.py` fitted
probability shrinkage on calibration labels at initialization and every epoch,
then used those calibrated scores to choose the outcome epoch. Thus calibration
labels could affect selected weights despite the post-selection isolation claim.
The trainer now holds shrinkage at one during epoch selection (training-only prior
correction remains), freezes both selected epoch states, records their combined
pre-calibration digest, and fits shrinkage exactly once afterward. A regression
test runs the actual optimizer and selection loop twice with opposite calibration
labels: histories, selected epochs and selected-state digests are identical, and
calibration is called once per run. Historical reports are not retroactively fixed.

Ran the predeclared training-only family screen:
`hog26_margin_family_screen_plan_20260908.json`, results
`hog26_margin_family_screen_20260908.json`. It fits 48 small margin heads: four
whole-family folds, two seeds, public-global/full structured inputs, powers 0/1/6,
fixed 30 epochs, and the same episode/phase-weighted Huber loss as the campaign.
No development, calibration or final outcome corpus was used. These are
supervised diagnostic heads, not policy updates or promoted candidates.

| Margin inputs / power | Overall OOF MAE gains, two seeds | Late gains, two seeds |
|---|---|---|
| Public globals / 0 | +0.04403, +0.04641 | -0.00297, +0.00038 |
| Public globals / 1 | +0.04208, +0.04266 | -0.02166, -0.02323 |
| Public globals / 6 | +0.02581, +0.02584 | +0.00012, +0.00012 |
| Structured / 0 | +0.05553, +0.05503 | -0.03647, -0.03064 |
| Structured / 1 | +0.05612, +0.05620 | -0.03887, -0.03839 |
| Structured / 6 | +0.02719, +0.02705 | +0.00013, +0.00013 |

OOF means each prediction comes from a model fitted without that entire training
family fold. Some variants meet the old pooled point gates but that does not earn
promotion. Public-global power 0 regresses overall on families006/007 by 0.01672
and 0.01253; its late regressions in other folds range approximately 0.06–0.09.
Only 14 late episode representatives exist across all folds. Neither a favorable
pooled metric nor the tiny positive gated corrections resolve this failure.

The existing temporal model previously prohibited power 0 entirely. It now permits
zero as an explicit ungated diagnostic while retaining the old default and behavior.
A test verifies finite nonzero late gradients at power 0; existing causal-prefix
and default-gate tests pass. A second predeclared family screen tests the existing
32-projection/16-memory GRU at powers 0 and 1, two seeds, exact per-game zero resets,
complete ordered trajectories, and fixed final epoch. Its plan is
`hog26_margin_temporal_family_screen_plan_20260908.json`. Different sequence batches
and learning rate mean it is not a compute-matched architecture comparison.

Separately perturbed nine future-label/unused arrays in four complete real training
games (1,897 rows). All 398 structured actor features remained bitwise identical.
See `hog26_actor_feature_causal_perturbation_20260908.json`. This strengthens feature
exclusion evidence beyond metadata; it does not prove live-vision equivalence.

Current focused verification: 33 tests passed; Ruff passed. Candidate fitting stays
blocked. Do not open selection/calibration labels while the candidate design is
unresolved; do not silently call successful pooled diagnostics final acceptance.

The temporal screen completed all 16 fold fits. Power 0 has pooled MAE gains
+0.03000/+0.03248 but late regressions -0.06649/-0.06754. Power 1 has pooled gains
+0.03708/+0.03866 but late regressions -0.01811/-0.01896. Both seeds fail the
predeclared late point gate for both powers. No memory candidate is promoted.
Stop architecture screens on shard0 alone; inspect the broader style shards next.

Before any new selection/calibration/final labels, the amendment now declares
explicit per-phase, seat, opponent and joint-slice coverage. A slice needs eight
independent matchup clusters and two clusters containing each decisive outcome;
insufficient coverage is an inconclusive rejection, not permission to cherry-pick
extra seeds. Genuine natural phase margin learning requires at least +0.001 MAE
improvement and a nonnegative clustered lower 95% bound, in addition to the old
overall/non-regression gates. Seat/style aggregate scores must pass separately.
These rules still need executable enforcement; readiness explicitly blocks on it.

To avoid the already visible small-sample limitation, unopened selection and
calibration budgets become 128 games each. Generated final evaluation becomes
576 games: 16 decks x balanced/reactive-defense/split-lane x both seats x six
replicates. The separate reserved original deck gets 36 games under the same
styles/seats/replicates. The 576-game count does not guarantee coverage: a policy
that almost never reaches late winning states may still produce an inconclusive
rejection. Broader final style coverage separates new-deck effects from the held-out
head-opponent effect. The source training-shard schedules, including the live
shard1 process, are unchanged. All three candidate state digests must still freeze
before final collection. There is no final launcher or implicit permission to
spend this evaluation budget before development acceptance.

## Executable public-slice acceptance

`scripts/hog26_public_slice_gates.py` now evaluates natural games separately for
all phases, seats, opponent styles and their declared joint combinations. Empty
combinations remain in the report and reject acceptance. Counts use distinct
seed/style/deck/ordinal clusters, with paired seats kept together. The margin
interval resamples whole clusters and compares learned absolute error with current
public tower margin on the same rows. Copying the baseline cannot pass the phase
learning gate. Controlled-draw games cannot contribute to these natural metrics.

The trainer applies these checks after epoch selection and the one-time calibration
step. They are required for development acceptance and for final acceptance when
final data is supplied. The campaign wrapper passes the protocol path and requires
its hash and passed slice report in the output. The separate reserved original
deck must pass its overall challenge; its smaller subgroup results remain visible
without claiming the same subgroup precision as the larger generated test.

Regression cases cover a good pooled score hiding a bad style, an entirely missing
joint slice, duplicated observations pretending to add independent clusters,
zero-change margin predictions, invalid probabilities, paired-cluster resampling,
and controlled-draw contamination. The real trainer test exercises the gate path
and still proves calibration-label invariance of selected weights and epochs.

Applied the new evaluator to shard0 with explicit constant class probabilities
and the current-margin baseline as a coverage diagnostic. All four late joint
slices fail coverage. Balanced has 5/3 clusters for seats0/1; random has 3/3.
Neither random late slice contains a win. This result is recorded in
`hog26_shard0_public_slice_coverage_20260908.json`; it is not a candidate evaluation.

The implementation blocker is resolved for these metric and coverage checks.
Candidate fitting remains blocked on a defensible margin design after inspecting
broader training styles. Final collection and frozen-state evaluation orchestration
still need implementation before any final labels are opened. No final evaluation
or controller improvement has occurred.

## Training shard 1 completed

Seed1278502 finished all 128 games and its automatic audit passed. Recomputed
corpus authority matches `af8ea0ba2e37c4a870af71ad2228cae713273a095a9d8da80a6f39b1d1ecc8f6`.
It retained 53,092 rows in 9,556.634 seconds, or 5.56 useful rows/s. Outcomes were
56 wins and 72 losses. Bridge-pressure produced 41/64 wins; reactive-defense
produced 15/64. This describes performance against these scripted opponents,
not human competence. The shard contains 14 late matchup clusters, only two
containing a win.

The union audit of shards0/1 passed on 256 complete games, 111,253 rows, 107 wins
and 149 losses. There are 128 early, 119 middle and 25 late matchup clusters,
with wins in only four late clusters. Audit artifact:
`hog26_procedural_train_shards01_audit_20260908.json`.

Started the remaining declared training shard, seed1278503, against slow-push
and spell-control. Its supervisor will audit after successful collection.
Process authority is `hog26_procedural_shard2_resume_20260908.json`; use that
record and live process checks rather than the old shard1 PIDs.

Predeclared repetitions of the static and temporal family screens on the new
bridge/reactive training corpus retain the original hyperparameters, family
folds and seeds. Plans and outputs use prefixes
`hog26_margin_bridge_reactive_screen` and
`hog26_margin_bridge_reactive_temporal_screen`. These supervised diagnostics
use complete audited training games only. No new development, calibration or
final labels have been opened, and no candidate fitting has been cleared.

The bridge/reactive repetitions finished. Public-global power0 fails both seeds
with late MAE regressions about 0.046 and negligible overall gains. Static full-state
power6 meets the old pooled point screen, but its late gains are only about 0.00010.
The GRU with power1 reaches late gains +0.00035/+0.00105 on this shard, compared
with negative late gains on shard0. These outcomes do not establish a robust
candidate under the stricter natural phase learning and coverage gates.

A training-label diagnostic identifies a loss/metric mismatch hypothesis to test
before another architecture change. The existing trainer uses SmoothL1 with its
default quadratic region, while margin acceptance uses MAE. On late phase
representatives, mean versus median remaining-margin change is -0.07614 versus
-0.00732 on shard0 and -0.08088 versus -0.01453 on shard1. Even same-data mean
constant corrections worsen MAE by 0.02144/0.00428, whereas same-data median
constants improve it by 0.00274/0.00875. These descriptive constants are not
held-out predictions or promotion evidence. Artifact:
`hog26_margin_loss_target_diagnostic_20260908.json`.

Next safe model experiment: predeclare an unchanged-family-fold comparison of
absolute versus Huber margin loss on these completed training shards. Preserve
all thresholds and test counterfactual ranking later; improved MAE alone does
not establish calibrated expected action value. Do not infer that loss alignment
will fix unseen families, rare late wins, or outcome calibration.

## Absolute-loss comparison

Completed 96 additional fold fits under four predeclared paired plans. Only the
margin loss changed; source corpora, powers0/1, architectures, seeds, folds,
optimizers, and fixed final epochs match their Huber comparators. No configuration
clears the +0.001 per-phase point-learning floor across both training shards and
both seeds. The linear-gated GRU improves late MAE by +0.00198/+0.00274 on the
bridge/reactive shard, but still regresses late on the balanced/random shard.
No candidate is promoted. Comparison artifact:
`hog26_margin_absolute_loss_comparison_20260908.json`.

This comparison does not establish calibrated expected utility: absolute-error
regression estimates a conditional median. Exact-terminal action-ranking gates
remain mandatory regardless of MAE gains.

Measured current training weight totals from the actual corpus arrays. Late rows
receive 3.65% of total weight in shard0 and 5.47% in shard1. The existing weighting
balances each game's reached phases and gives games equal mass; it does not
balance aggregate early/middle/late mass. Next bounded training-only diagnostic:
compare this weighting with aggregate phase balance, normalizing using fitting
folds only. Preserve the complete-game rows and held-out-family splits, and keep
all acceptance thresholds unchanged. A successful weight test would still need
independent development, calibration, replication and final evaluation.

## Aggregate phase-weight comparison and spatial information loss

Completed the 96 predeclared phase-weight fold fits. The fitting-weight helper
uses fitting rows only, zeroes withheld rows, and verifies one-third full-fold
weight mass for each phase. Three focused tests cover those invariants and the
missing-fitting-phase rejection. No configuration clears the phase-learning
point floor across both shards and both seeds; only one of 24 pooled model/seed
results passes that point floor at all. The previous loss/weight settings remain
unaccepted. Artifact: `hog26_margin_aggregate_phase_comparison_20260908.json`.

The temporal minibatch implementation still divides by each selected batch's
weight sum. Therefore one-third full-fold weight mass is not proof of exactly
one-third averaged optimizer influence. The comparison report records this
limitation. Correct that denominator before using aggregate weighting as an
unbiased production objective; do not retroactively relabel these runs.

Found an exact information-loss example in training shard0, row13. Swapping only
the positions of a visible enemy Ice Spirit and Princess changes raw coordinates
by up to 0.20625, but all 398 pooled actor features are bitwise identical. Independent
column-wise mean/max pooling destroys the unit-stat/position association. A static
head cannot distinguish these instantaneous inputs. A recurrent head might infer
some associations from history; this experiment does not rule that out, prove an
alternate reachable trajectory, or establish different terminal outcomes.
Artifact: `hog26_actor_summary_spatial_collision_20260908.json`.

Next representation experiment must preserve associations between visible unit
mechanics and position, rather than changing only loss/power/width on this pooled
summary. Use the same complete-game training-family folds, preserve actor-only
inputs, and leave all development, calibration and final labels unopened until
the candidate design is fixed. No model is promoted by the information-loss test.

## Spatial-mechanics representation and matched control

Implemented the experimental `spatial-mechanics` actor representation. It appends
visible mechanics-position moments and visible entity counts before the public
global suffix, producing 808 features for this policy. On the recorded collision,
coordinate swapping now changes features by 0.04125. Joint entity permutation
preserves the result within floating-point tolerance; empty sets are finite and
the final 18 public globals are unchanged. Three tests cover these properties.
The campaign primary remains unchanged and blocked; this new representation is
an experimental option, not an accepted model.

Completed 64 fold fits comparing the full 808-feature input with the added-feature
block zeroed. Parameter count, initialization seeds, dimensions, loss, fitting
weights, optimizer, epoch budget, and family folds were matched. All eight pooled
full-feature model/seed results have worse late MAE than their ablated controls.
No full-feature result clears the +0.001 phase point-learning floor for every phase.
The information-loss demonstration therefore does not establish that these added
moments improve forecasting. Artifact:
`hog26_spatial_mechanics_comparison_20260908.json`.

Inspected fitting versus withheld-family errors as well. Some late errors already
fail on fitting-phase representatives, especially for the recurrent model and
bridge/reactive shard; other cases improve in fit then reverse out of fold.
Do not describe every failure as pure overfitting or pure information loss.
The next data-scale comparison should fit the combined audited training corpora,
with all episodes from each withheld generated family excluded together. Separate
per-shard fits each used only 96 fitting games. Do not continue feature-only tuning
on these small separate folds as if it were the declared full training mixture.
Final labels remain unopened, thresholds unchanged, and shard2 continues collecting.

Current focused validation: 42 tests passed, including the real calibration
isolation regression and public-slice gates; Ruff passed.

## Combined training mixture and frozen actor-state screen

Extended the family screen to consume multiple separately pinned corpora without
writing a merged corpus or discarding provenance. Each source records its role,
seed, SHA, row/episode offsets and counts. Only declared procedural training and
legacy training inputs are permitted. Whole generated families are excluded
across every procedural source; auxiliary games remain fitting-only. Source-role
and family-exclusion tests pass, including rejection of a selection corpus even
if an audit path is present for it.

The combined static screen completed 32 fold fits on six audited sources totaling
404 games and 180,091 rows. Each fold fits 340 games and evaluates the excluded
64 procedural games. The 148 auxiliary games never contribute to withheld metrics.
Public-global powers0/1 regress late by roughly 0.019–0.029. Full-state powers0/1
regress late by roughly 0.011–0.036. Both seeds fail the old late non-regression
gate for every configuration. No candidate is promoted. Artifact:
`hog26_margin_combined_training_screen_20260908.json`.

Inspected the existing frozen policy feature path. `repair_features` concatenate
its public actor encoding with its actor recurrent memory, before any critic
value is used. The replay uses recorded past actions, exact game resets and
previous rewards forced to zero. One complete 450-row training episode produces
210 features in 0.759 seconds on one CPU thread; perturbing future labels and
unused action/reward arrays leaves them exactly unchanged. This is a causal
extraction probe, not a full inference-parity or predictive acceptance result.
Artifact: `hog26_policy_state_extraction_probe_20260908.json`.

Started the predeclared combined-data screen using this existing
`policy-plus-public-globals` representation, with the same families, seeds, absolute
loss, aggregate phase weights and fixed epoch budget. Its plan and output prefix
is `hog26_margin_combined_policy_state_screen`. Only new supervised outcome heads
are fitted; behavior-policy weights remain frozen. No critic inputs, policy
updates, new development/calibration labels, or final labels are used. This also
avoids the separate learned-GRU minibatch-normalization confound in prior screens.

The frozen-policy-state screen completed all 16 fold fits in 253.62 seconds.
All four pooled configurations fail the old late non-regression screen.
Power0 late MAE improvements are -0.02950/-0.03130; power1 gives
-0.01332/-0.01560. Every configuration also regresses against bridge-pressure
by 0.02731–0.03345, despite overall improvements of 0.02666–0.03546.
No candidate is promoted. The 35 late representatives are limited diagnostic
evidence, not independent acceptance. This result rejects the tested frozen
representation/head combination, not public recurrence in general. Decision
and fold fitting-versus-withheld errors are preserved in
`hog26_margin_combined_policy_state_decision_20260908.json`.

The next collection dependency is the existing live shard2, followed by its
protocol-bound audit. Do not start another feature sweep or open development
labels merely to find a passing variant of these repeatedly examined folds.

Added an early refusal in the generic trainer for the combination of a
generalization protocol and holdout corpora. The previous route loaded holdout
labels before refitting; a post-fit digest comparison is not a frozen-head
evaluation path. The refusal occurs before any model or corpus load. An actual
CLI-main regression test replaces both loaders with failing sentinels and proves
no artifact is written. All 18 trainer tests and Ruff pass. A separate frozen-head
final evaluator remains required before final collection; this guard alone does
not provide final evaluation or acceptance.

Implemented `scripts/hog26_frozen_outcome.py` as the checkpoint-loading
component for future direct final evaluation. It requires external file/state/
policy/protocol SHA pins, validates development eligibility and absence of prior
holdout inputs, checks architecture against the report, strictly loads the state,
and disables gradients. Fitted calibration buffers are preserved. Eleven tests
pass, including exact calibrated prediction round-trip and rejection of altered
state, architecture, pins, or ineligible reports. Ruff passes. These synthetic
tests prove loader behavior only; no real accepted checkpoint exists yet and
the full final evaluator, freeze manifest, corpus preflight, and acceptance
orchestration remain to be implemented. Collector PID33283 remains live at
about one hour elapsed; no duplicate collection or training was started.

Added `scripts/freeze_hog26_outcome_cohort.py` to pin the primary and both
replicas before final collection. It requires current audited fitting inputs,
accepted development checkpoints, exact declared seeds/design/weighting, and
identical declared fitting, validation and calibration bytes. It refuses a
missing or duplicate replica, changed prior, or any existing final corpus
directory, report, or audit. The trainer now records sequence_steps so replay
configuration can be bound. The current under-review protocol deliberately
cannot publish a manifest. Eight cohort tests plus the loader/trainer tests
pass, 37 total; Ruff passes. No manifest was created and no final labels opened.
This records absence of declared final paths at freeze time, not proof that
no external process has ever observed equivalent labels. Final collection must
consume the manifest and enforce it before creating those paths.

Implemented `evaluate_frozen_predictions` in
`scripts/evaluate_hog26_frozen_outcome.py`. It requires an eval-mode head with
gradients disabled, exactly one corpus for each declared final seed and episode
budget, complete public label authority, and matching public-global feature
suffixes. It computes existing natural public slices, decisive clustered phase
confidence, natural draw probability, and separate controlled-draw recognition
gates. Mixed natural/control aggregate metrics are diagnostic only. State
digests before and after must agree; even a public-metric pass leaves ranking
pending and policy updates forbidden. Five synthetic tests pass, including
reserved-deck failure concealment, natural/control margin isolation, omitted
corpora, and training-mode rejection. Ruff passes. No real final labels were
used. The metric function is not yet a standalone final evaluator: cohort/audit
preflight, public feature extraction, and report publication must be connected
before use on final data.

Connected cohort preflight, final-corpus audit and collection-authority checks,
public feature replay, all-replica evaluation and report publication in the
frozen evaluator CLI. The caller supplies the exact manifest SHA. Corpus
loading occurs only after cohort validation and all stage audits; collection
reports must bind both protocol and frozen cohort SHA. Metadata verifies
generated families, reserved deck/styles, or paired controlled physical games.
Every candidate is evaluated and any failure rejects the cohort. Nine evaluator
tests pass, with synthetic metric tests and mocked orchestration tests covering
early refusal, provenance, all-seed evaluation and no optimizer construction.
The 19 loader/cohort tests also pass; CLI --help and Ruff pass. Code committed
locally as 93bcf548. This is not a real final-data end-to-end acceptance run.
Final collection orchestration still must produce the required provenance, and
no accepted model or frozen manifest exists.

Added the final collection command `scripts/collect_hog26_frozen_final.py`.
It verifies the pinned cohort, uses exact declared generated/reserved/control
arguments, writes an exclusive start receipt, and publishes cohort/protocol
provenance after the exact game-budget audit. Failed attempts remain recorded
and block automatic duplicate collection or refreezing. The stage runner now
refuses development/calibration collection without explicit ready design status,
including historical protocols lacking that status. Eighteen collection/cohort/
stage tests pass and Ruff passes. Tests use synthetic files and mocked collectors;
no real final collection was run. Shard2 remains live; its latest progress is
chunk5 at3949.59 seconds with10 streams completed. Partial labels remain unused.

## Phase-sampling mismatch

A new descriptive audit of the two completed procedural training shards shows
that 10/14 and 11/21 late phase representatives are the last recorded decision
in their game. The nearest-center selector substitutes the final row when a
game ends before the phase midpoint. Median remaining decisions is zero in
both late representative sets. This changes the forecasting horizon represented
by the score. Equal-game/reached-phase weighted late fitting baseline MAE is
0.12105/0.14431, versus 0.07925/0.08676 on the selected representatives.
The fraction already within0.01 of terminal margin rises from weighted
0.10647/0.04484 to representative0.50000/0.19048.

Artifact: `hog26_margin_phase_sampling_diagnostic_20260908.json`. These are
audited training-only descriptive results, not new fits or final evaluation.
The failed candidates remain rejected. This is a sampling/estimand mismatch,
not evidence that any rejected model forecasts well. Do not fit only the
endpoint-heavy representatives to manufacture a passing score. Before further
candidate fitting, resolve how evaluation measures the full phase distribution
and separately expose terminal-adjacent states. Preserve the historical scores
and freeze any justified protocol amendment before selection/calibration/final
labels. No thresholds or sampler implementation changed in this diagnostic.

Added an additional full-phase margin gate to the still-under-review protocol.
For each natural generated game and reached phase, calculate MAE over every
recorded state, then weight game-phase means equally. Bootstrap seed/style/
deck/ordinal clusters so paired seats remain together. Require the unchanged
phase learning point/lower-95 floors and cluster coverage in every phase, in
addition to all existing representative-point gates. Controlled draws and the
reserved-original challenge remain separate. Both trainer and frozen evaluator
use this through the shared public-slice adapter. No collected training shard
arguments, model design, or existing thresholds changed.

A synthetic model that is perfect at representatives but wrong between them
passes the old gates and fails the new gate. Additional tests show that
increasing row count in one game does not increase its phase weight or cluster
count, and controlled-draw margin labels cannot change natural acceptance.
Fifty focused tests pass; Ruff passes. No additional fit or final data was used.
This resolves the margin sampling coverage omission by adding evidence, without
retroactively accepting any rejected candidate. Full-phase classification
calibration should also be assessed before claiming broad live-state coverage.

Extended the additional full-phase gate to outcome probabilities using the
same equal-game-within-phase weights. It reports weighted NLL, Brier, top-label
and per-class ECE, decisive AUC, and predicted/empirical class mass. Every phase
must meet the existing ECE, phase AUC and maximum natural draw probability
thresholds. Representative gates and full-phase margin gates remain required.
Zero natural draw mass is reported as such; controlled draws are excluded.
Hand-calculated weighted AUC/tie and calibration tests pass. A head with accurate
margins and landmark probabilities but wrong probabilities between landmarks
is rejected. Fifty-three focused tests and Ruff pass. The still-under-review
protocol includes this additional requirement before any new development or
final labels. Selection/calibration/final corpus directories remain absent.
Collector33283 remains live at1h25m; no additional training was launched.

## Coverage-budget reassessment

The unopened development schedule previously had32 games per style/seat,
which repeats the training sample size rather than solving late coverage.
Balanced training produces5/3 late games and2/1 late wins across seats;
reactive-defense produces10/9 late games and1/1 late wins. Required joint
coverage is8 clusters with2 wins and2 losses. A descriptive multinomial
planning calculation using these small observed rates gives the weakest
balanced slice only0.00658 probability of meeting coverage at32 trials.
At256 trials, a union bound across the four seen style/seat slices is0.99178
under the plug-in assumptions. This is not a guarantee for new families or
split-lane, nor evidence of predictive acceptance. Artifact:
`hog26_late_coverage_budget_diagnostic_20260908.json`.

Fixed the still-unopened budgets at256 games per generated style/seat:
1024 selection games,1024 calibration games,1536 generated final games.
Actual inadequate coverage still rejects; no adaptive top-ups are authorized.
The controlled/reserved scopes and budgets remain unchanged. This implies
a multi-day local evaluation workload. No collection was launched, candidate
readiness remains under review, and all unopened-stage directories are absent.
Eighteen collection/cohort/stage tests pass. The active128-game training shard
and its arguments are unchanged.

## Completed declared training collection

Shard2 finished normally in9442.77 seconds and passed its protocol audit:
128 complete games,56347 retained rows,47 wins/81 losses/0 draws. Corpus SHA
`611699015ae3a506454aa8a9f11ae009213ae773d4213266b2f9f120f39314e1`.
Both collector and supervisor exited. Reverified all three corpus hashes and
audited their union:384 games,167600 rows,154 wins/230 losses/0 draws; every
check passed. The union report is
`hog26_procedural_train_complete_audit_20260908.json`.

Shard2 contributes17 late episodes with2 wins, both against spell-control.
Its weighted late baseline MAE is0.07483 versus0.05023 on representatives.
Detailed training-only counts are in
`hog26_shard2_completed_training_diagnostic_20260908.json`.

Started the predeclared complete-mixture static margin comparison, retaining
the existing feature/power/seed grid and fixed30-epoch budget. It now uses all
three audited training shards plus the four permitted auxiliary corpora,
532 games/236438 rows. Each whole-family fold excludes96 procedural games
across all shards and fits436 games. Added full-phase equal-game margin
reporting alongside unchanged historical representative metrics. Six focused
screen tests and Ruff pass. Plan/output prefix:
`hog26_margin_complete_training_screen`. This is supervised training-family
diagnostic work only; no development/calibration/final labels are opened and
no behavior-policy parameters are updated. The candidate remains under review.

The complete-mixture screen finished32 fold fits in183.45 seconds. All8
configurations still regress on late representatives. Public-global power0
gives representative late gains -0.00493/-0.00178 while full-phase late gains
are +0.02546/+0.02764. Both pass the historical -0.01 non-regression screen,
but neither meets the amended +0.001 representative learning gate. No candidate
is promoted. Full-state power0 late full-phase gains are only +0.00014/+0.00229;
power1 gives +0.00717/+0.00595 while representative errors still regress.
`hog26_margin_complete_training_decision_20260908.json` preserves pooled and
fold phase comparisons. The correct diagnosis is now useful full-phase learning
with a terminal-heavy representative failure, not no late forecasting at all.
Resolve the previously documented temporal minibatch normalization confound
before drawing conclusions from a further recurrent full-mixture comparison.

## Corrected temporal weighting and public-global history

Fixed the temporal diagnostic loss denominator. Uniformly shuffled episode
minibatches now divide by their expected fitting-weight mass, using the fitting
fold mean episode weight, rather than renormalizing by each batch actual mass.
A gradient counterexample verifies that averaged minibatch gradients match the
full weighted objective; the old formula does not. Padding has zero loss and
gradient. Eight focused tests and Ruff pass. Old temporal plans must explicitly
declare the corrected normalization before rerunning, preserving the distinction
from historical reports.

Actual complete-mixture weighting arithmetic over1000 random batchings per
fold gives old late effective mass0.31806–0.31998 versus the0.33333 target.
The corrected mean is0.33322–0.33389. This is a measurable but modest bias;
it is not evidence that normalization alone explains the predictive failure.
Artifact: `hog26_temporal_batch_weight_bias_20260908.json`.

Started a bounded16-fit public-global history diagnostic on the complete
532-game training mixture, using the existing temporal projection32/memory16,
fixed30 epochs, powers0/1 and seeds1278911/1278912. Inputs are only the18
public globals in complete causal game order. The normalization fix is explicit
in the plan. Comparison with static public globals is not compute-matched
because optimizer batching and learning rate differ. Plan/output prefix:
`hog26_margin_complete_public_history_screen`. No behavior policy updates or
new development/calibration/final labels are involved.

The corrected public-global-history comparison completed16 fold fits in
289.33 seconds. Power0 representative late gains are +0.000071/+0.003169;
full-phase late gains are +0.02192/+0.02300. One seed misses the representative
learning floor, and individual family-fold late regressions reach0.04174.
Power1 representative late gains remain negative, -0.01051/-0.01310. No
candidate is promoted and recurrence is not declared sufficient. The result
is recorded in `hog26_margin_complete_public_history_decision_20260908.json`.
Before another margin architecture trial, assess WDL learnability on this
completed training mixture with the same family isolation and fit-only prior
correction. The primary objective needs both calibrated outcome probabilities
and margin forecasting; margin-only diagnostics cannot establish either final
acceptance or readiness for policy learning.

## WDL learnability on the completed training mixture

Added an outcome-classification mode to the audited family screen, reusing
its exact source roles, corpus hashes and whole-family exclusions. The new
classification implementation trains only ActorOutcomeHead weights at a fixed
epoch budget. Class weights and empirical episode prior use fitting labels
only; no withheld shrinkage or epoch selection is allowed. It reports natural
representative and full-phase weighted NLL, Brier, ECE, classwise ECE, decisive
AUC, and probability/class mass, with fold-specific fitting-prior baselines.
Controlled training draws remain auxiliary fitting inputs, never withheld
natural examples. A label-flip test proves withheld outcomes cannot change
class weights or prior. A small real fit checks fold coverage. Eleven focused
tests and Ruff pass.

Started the two predeclared complete-mixture WDL diagnostics using public
globals and the existing structured summary, each hidden16, fixed30 epochs,
seeds1278921/1278922 and four family folds. Plans/output prefixes are
`hog26_wdl_complete_globals_screen` and `hog26_wdl_complete_summary_screen`.
Runs are sequential on one CPU thread. These are learnability diagnostics,
not acceptance or permission for search/policy updates. No new development,
calibration, or final data is opened.

Both WDL diagnostics completed,35.59s for globals and76.01s for summary.
Public-global representative overall decisive AUC is0.84458/0.83227 with
ECE0.02109/0.01833 and NLL improvement0.23201/0.22353 over each fold fitting
prior. Full-phase early AUC is0.67165/0.68487, middle0.89709/0.88786, and
late0.80538/0.85648. Structured summaries give overall AUC0.80582/0.81881
and ECE0.09980/0.08251; full-phase late AUC falls to0.72462/0.65915.
These are repeatedly examined training-family diagnostics, not independent
acceptance. Natural draw labels are absent, so natural draw calibration is
not established. Decision artifact: `hog26_wdl_complete_training_decision_20260908.json`.

Outcome discrimination is now demonstrably learnable in this training mixture;
the bottleneck is not uniformly missing public outcome information. A bounded
next hypothesis is to test the fitting-only outcome encoder as margin features,
with a matched frozen-random-encoder control. Preserve WDL head calibration and
all family exclusions; do not use withheld outcomes to build transferred features.

## Matched outcome-encoder margin transfer

Added a bounded transfer comparison to the training-family WDL screen.
Each fitting-fold WDL head supplies its16-dimensional public-global trunk
embedding; the matched control uses an exact copy of that trunk before fitting.
Both append the unchanged18 public globals and fit the same hidden16 margin
head, with identical initialization seed, row order, fixed30 epochs, absolute
loss, aggregate phase weights, and constant0.5 residual bound. The outcome
encoder stays frozen; its state digest is checked after margin fitting.
Tests verify detached features and unchanged public suffixes, invariance to
withheld margin targets, and encoder immutability. Six focused tests pass and
Ruff passes.

Started `hog26_outcome_margin_transfer_screen_plan_20260908.json`:8 WDL fits
and16 matched margin fits over the same completed training-family folds. No
new data roles or actor-policy updates are introduced. This tests whether
learned outcome features help the unresolved margin problem; it is not a new
independent acceptance run or a promoted deployment architecture.

The matched transfer screen completed in94.63 seconds. Learned-encoder
representative late gains are +0.00244/-0.00338, versus random-control
-0.00351/+0.00225. Learned full-phase late gains are +0.03399/+0.02802,
versus random +0.02583/+0.03025. Overall and middle-phase transfer improve,
but neither late measurement consistently beats the control across seeds.
WDL representative and full-phase metrics exactly reproduce the prior run,
confirming the margin experiment did not alter those predictions. No candidate
is promoted. Decision: `hog26_outcome_margin_transfer_decision_20260908.json`.
This does not resolve the margin bottleneck and does not justify another
small transfer variation as independent evidence.
