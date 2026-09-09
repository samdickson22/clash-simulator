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

## Overtime stopping mechanics

Case analysis of complete-mixture public-global power0 predictions separates
32 terminal-row late samples from20 nonterminal late samples. Mean error
across the two neural seeds regresses by0.04192 on terminal rows but improves
by0.05835 on nonterminal rows. Thirty terminal rows end through an overtime
crown change, two through king destruction. This rejects the initial guess
that the pattern is mostly a near-dead-king issue. Case artifact:
`hog26_late_margin_failure_cases_20260908.json`.

Predeclared and evaluated one fixed public-history diagnostic: estimate tower
damage rates from the preceding20 observed decisions, then project damage
until the first surviving tower falls or the public remaining clock expires.
Apply only in overtime. No labels are inputs and no parameters are fitted.
Prefix-causality, reset isolation and a hand-calculated race test pass; Ruff
passes. This is a constant-rate approximation, not exact future simulation.

The diagnostic improves late representative MAE by0.02238 and equal-game
full-phase late MAE by0.01755. Terminal-row MAE falls from0.01162 to0.00391;
nonterminal late MAE falls from0.17067 to0.12482. It makes no early-game
forecast and is not a complete candidate. Plan/result prefixes are
`hog26_overtime_damage_race`. The next bounded test should combine the
existing neural regulation forecast with this explicit overtime stopping
calculation, preserving public causality and validating full-phase as well
as representative errors before changing the production candidate. No
new development/calibration/final labels have been used.

## Complete neural-regulation/overtime diagnostic

The matched hybrid screen completed8 fits in44.96 seconds. Raw neural
representative metrics exactly reproduce the earlier complete-mixture
public-global power0 runs. Replacing only overtime predictions yields
representative overall MAE gains0.03808/0.03560 across seeds. Both seeds
improve every representative and full-phase metric: late representative
gain0.02238 and full-phase gain0.01755. All four late family folds improve,
by0.05276/0.00752/0.00621/0.02752. Full-phase middle gains remain positive,
0.02631/0.02332. Artifact: `hog26_hybrid_margin_screen_20260908.json`.

Training-only paired-matchup bootstrap over36 late clusters gives lower95
improvement bounds0.00084 for representatives and0.00079 for full-phase
means. These narrow, design-selected training intervals are not independent
acceptance evidence. Artifact: `hog26_hybrid_margin_training_uncertainty_20260908.json`.

The design is now plausible for integration and independent development
evaluation. Candidate readiness remains under review until the causal history
calculation is bound into training, checkpoint configuration, feature replay
and frozen evaluation. The old primary configuration remains guarded and must
be replaced before use. No development/calibration/final data has been opened,
and no search or policy updates are authorized by this diagnostic result.

## Core candidate integration

Moved causal overtime dynamics into `clasher.rl.public_margin_dynamics` with
a compatibility import for the original diagnostic. Added the explicit
`public-global-dynamics` feature contract: one fixed-window20 causal margin
feature followed by the unchanged18 public globals. ActorOutcomeHead supports
`overtime-damage-race-v1`, uses only the18 globals for WDL, and applies the
causal margin correction only in overtime. Neural fitting explicitly disables
the override so the regulation head retains the tested fitting objective.
The trainer records dynamics and supports an explicit absolute margin loss;
Huber remains the default for historical callers.

Frozen checkpoint loading reconstructs the dynamics mode and rejects feature
contract/report mismatches. Cohort design checks include dynamics and loss.
Tests verify unchanged WDL probabilities, unchanged raw neural/regulation
margins, causal label-independent feature replay, correct absolute loss, and
dynamics checkpoint reconstruction. The existing47-test core/trainer/loader
set passes, with an additional focused11-test dynamics/cohort pass; Ruff
passes. This is not yet complete candidate integration: aggregate phase-loss
options, campaign arguments/design replacement and full trainer verification
remain before any development collection. Candidate readiness stays under
review and no new labels were opened.

## Candidate loss wiring and memory boundary

Wired absolute margin loss and optional aggregate phase balancing through
the trainer and campaign command. Cohort checks bind the declared weighting.
The real optimizer/selector regression now runs with both18-feature globals
and19-feature dynamics, absolute loss and aggregate phase weights; reversing
calibration labels cannot change selected epochs or pre-calibration state.
Thirty-three trainer/campaign/cohort tests and Ruff pass.

A contract probe on all236438 completed training-mixture rows shows exact
agreement between production dynamics features and the causal diagnostic,
with unchanged global suffixes. Production aggregate weights agree with the
screen within floating-point tolerance; maximum absolute difference0.000061
on large weights and phase mass is1/3 each. Artifact:
`hog26_dynamic_candidate_contract_probe_20260908.json`.

Measured the actual archive expansion before launching enlarged stages.
The128-game shard2 expands to1.94448GiB, implying15.55582GiB for1024 games
at similar lengths before temporary copies. Selection plus calibration plus
training cannot all be loaded as full observation corpora on this24GiB Mac.
The required global/label arrays are only0.00782GiB per128-game shard.
Next work must bound collection memory and load the declared public-global
projection for this candidate, preserving full corpus audits and provenance.
No enlarged collection was started; readiness remains under review.

## Audited public-global projection loader

Added a projection loader for the dynamic public-global candidate. It requires
a current full-corpus audit and retains original globals, terminal labels,
episode boundaries, ordinals, stream identities and reset states. It rejects
critic fields by inspecting every archive key before selecting arrays. It
does not load entity tensors or replace the full audit. Trainer and frozen
evaluator use this path only for the explicit public-global-dynamics contract.
Tests verify skipped entity reads, exact selected-array preservation, unchanged
archive bytes, stale-audit rejection, and critic-field rejection. Thirty-five
projection/trainer/evaluator tests and Ruff pass.

A real128-game shard comparison confirms every projected array and metadata
field equals the full reader. Retained array bytes fall from2087728678 to
8637072, a241.72-fold reduction. This measures retained NumPy arrays, not total
process peak memory. Artifact: `hog26_public_projection_memory_probe_20260908.json`.
The loading memory issue is addressed for this candidate; collector-side
accumulation still needs bounding before larger development stages launch.
No new development/calibration/final labels were collected.

## Disk-backed collection and full auditing

CompleteEpisodeBuilder can now spill each completed episode to owned disk
scratch and assemble final arrays with memory maps in the original stable
stream/ordinal order. Natural collection enables this for multiple episodes
per stream. Final archive and report publication happen before scratch is
released. Incomplete spools cannot be published or discarded through the
release method. Completed data are retained as paths rather than NumPy arrays;
active games, live rollout batches and OS mapping caches still consume memory.

A replay of the existing128-game/56347-row shard preserved every transition
array, episode array, reset state and recomputed terminal label exactly, then
published an archive that passed the full audit. Artifact:
`hog26_disk_episode_builder_probe_20260908.json`. The probe initially used
uncompressed episode scratch; scratch compression was then enabled and the
round-trip tests rerun to reduce disk use. No new games were generated.

Full audits now stream archive members to temporary NPY files and map their
arrays, retaining the same validation code instead of materializing all large
entity tensors in heap memory. A real-shard mapped audit produces exactly the
same report as its existing eager audit. Artifact:
`hog26_mapped_full_audit_probe_20260908.json`. Twenty-five builder, outcome,
collector and audit tests plus Ruff pass. No validation checks were removed.
Collection/audit memory storage is now addressed; inference code authority
and primary configuration replacement remain before development launch.

## Inference authority and scenario-independence reassessment

Bound candidate inference/evaluation sources and NumPy/PyTorch versions to
exact hashes. Collection protocol loading, training, frozen head loading and
cohort loading validate this authority. Replaced the guarded primary design
with public-global-dynamics, absolute margin loss, aggregate phase weighting
and power0. Declared concrete replica artifacts and added candidate-seed
selection that changes only the declared seed and output paths. Fifty-three
authority, loader, cohort, trainer and command tests pass; Ruff passes.

Before clearing readiness, checked the independence assumption behind the
expanded budgets. In the existing96-game crossed training subset, balanced
and slow-push streams each repeat one public/action transcript across all
four episodes. Random streams have four distinct transcripts each. Across
all streams there are only6 distinct balanced and7 distinct slow-push
transcripts among32 episodes per style, partly because paired seats also
match. This hash covers public globals and actions, not every simulator field.
No cross-seed matching deck/style/seat cases were available in the three
inspected legacy corpora, so cross-seed diversity was not empirically proved.
Artifact: `hog26_episode_diversity_reassessment_20260908.json`.

Runtime reset_rows restores initial templates unless ordered deck_ids are
supplied; the generic collector currently does not supply a reset-deck
provider. Repeating episode ordinals therefore does not establish independent
new scenarios for deterministic strategies. The earlier coverage-probability
calculation is conditional on an unverified independence assumption and must
not justify launch by itself. Readiness remains under review. Next work must
verify genuinely varying seeded initial scenarios, with paired-seat consistency
and an audit of scenario identity, before collecting enlarged development or
calibration data. No new evaluation games were launched.


Seeded opening implementation checkpoint:
- Added SeededDealSchedule with local NumPy RNG, precomputed ordered decks,
  distinct deals within each matchup, paired-seat relative-deal equality,
  and per-row advancement only at episode resets. Surplus unretained games
  reuse the last planned opening.
- Complete-game collection now accepts an explicit seeded-ordered-decks-v1
  opening schedule. It installs the existing reset-provider hook before the
  first policy observation, records scenario IDs and learner-visible opening
  hand tokens, and rejects publication if a retained initial hand disagrees.
  Legacy fixed-template collection remains explicit and unchanged by default.
- Repaired the misplaced reset test and built the test fast catalog on CPU
  before moving its tensors to the requested device. No production catalog
  floating-point semantics changed.
- Verification: seeded schedule, runtime reset, and collection tests: 14 passed,
  2 skipped (CUDA unavailable). Seeded reset and bridge integration ran on both
  CPU and MPS. These are functional reset tests, not full-game acceptance.
- Still required: independently reconstruct and audit scenario metadata;
  replace ordinal-only bootstrap groups with verified scenario groups;
  test actual complete-game diversity and randomized-opening training support;
  bind the final collection protocol and authority before evaluation launch.
  No new corpus, training, or evaluation was launched in this checkpoint.


Conservative independence correction:
- The corpus audit, representative-phase intervals, and full-phase margin
  gate now share episode_matchup_cluster. Deterministic natural games with
  the same style/deck are grouped across ordinals, seeds, and paired seats.
  Random-opponent games retain seed/ordinal groups with paired seats together.
- Seeded-opening declarations alone do not grant extra groups. Until opening
  reconstruction and audit are implemented, these also retain conservative
  style/deck grouping. Distinct schedule hashes are not an independence proof.
- Re-audited the completed legacy 96-game crossed training corpus. Early and
  middle groups fell from 48 to 24; late groups fell from 21 to 9. Outcomes,
  episode integrity, and public actor contracts still pass. New report:
  hog26_crossed_train4_conservative_cluster_audit_20260908.json.
- Three fixed-opening reserved-deck strategies cannot supply the required
  eight groups merely by repeating games. No acceptance threshold changed.
- Updated synthetic metric fixtures to use distinct matchups rather than
  ordinals as their coverage evidence. Added a perfect-prediction regression
  demonstrating that duplicated fixed openings still fail coverage.
- Validation: 70 focused trainer/audit/gate/protocol/frozen-evaluator tests
  passed; Ruff passed. Recaptured the protocol source authority including
  the shared cluster helper. Historical reports are preserved as historical;
  their ordinal-based interval/coverage claims are superseded by this rule.
- No collection or training launched. Opening reconstruction, complete-game
  diversity, and randomized-start training support remain outstanding.


Seeded opening reconstruction and live collection probe:
- Added an opening audit that reconstructs the exact schedule from the pinned
  supported-deck manifest, current public catalog compiler, token vocabulary,
  collection seed, matchup rows, and episode quota. It compares every declared
  scenario ID and public opening hand, then verifies recorded initial hands,
  learner seats, episode indices, and matchup identity.
- Integrated this check into the full corpus audit. Fixed-template corpora
  remain marked as lacking verified seeded openings. Reconstruction does not
  itself certify full-game diversity or statistical independence; clustering
  remains conservative pending complete-game evidence and pipeline integration.
- Added public_episode_diversity, which hashes complete actor entity IDs,
  features/masks, hands, globals, and actions. Labels and episode ordinals cannot
  make duplicate transcripts appear different.
- Tests: 91 passed, 2 CUDA skips in the combined audit, trainer, frozen-evaluator,
  protocol, collection and CPU/MPS reset suite; the additional trajectory
  diversity regression passed. Source authority updated for opening audit,
  scheduler, and collection entry point.
- Frozen training-only probe plan before collection:
  hog26_seeded_opening_diagnostic_plan_20260908.json. Seed1278951, balanced,
  Procedural train 000-0, four openings per seat, eight retained games. No
  outcome-model fitting, selection/calibration, or holdout data involved.
- Live command started with exec session75744, PID69455. First chunk completed
  after88.966seconds with zero completed games. Log:
  reports/hog26_seeded_opening_diagnostic_seed1278951.log. Output will be
  datasets/derived/hog26_seeded_opening_diagnostic_seed1278951/corpus.npz.
  Keep polling this process; do not restart because an observation yields.
- Next: wait for complete publication, full audit plus trajectory diversity,
  then decide whether verified scenario IDs can support finer grouping. Do not
  use partial shards or this mechanics probe as independent model acceptance.


Verified opening groups wired into evaluation:
- Added corpus_matchup_clusters. It runs opening reconstruction and compares
  recorded initial public hands before returning seeded-deal groups. The IDs
  omit seed/ordinal and pair physical seats by the relative ordered deal.
  Fixed deterministic openings retain conservative style/deck groups.
- The full corpus audit, representative-phase metrics, and full-phase margin
  metrics now use this corpus-level path. A fabricated recorded hand rejects
  evaluation rather than receiving a distinct group.
- The public projection retains hand_ids only for seeded-opening corpora so
  downstream metrics can repeat the opening check without loading entities.
  Hands remain public provenance; public-global model inputs are unchanged.
- Tests: 79 focused audit/trainer/gate/protocol/frozen-evaluator tests passed.
  Follow-up projection/opening tests passed14 including new projection and
  representative-phase integration cases. Ruff passed. Protocol source hashes
  recaptured; no collection-runtime source was modified during the live probe.
- This enables verified scenario grouping, not model acceptance or clearance
  to collect evaluation data. Actual complete-game probe diversity and fitting
  support under shuffled openings remain pending.
- Probe session75744/PID69455 verified live after4m34s; chunk3 completed at
  267.281seconds, completed_by_stream=[0,0]. Continue the same process.


Opening schedule bound to protocol collection:
- Found and fixed a silent fallback: procedural/final wrappers did not pass
  opening_schedule, which would have collected fixed templates even after
  schedule verification existed. Both generated and reserved natural stages
  now carry the declared schedule through collection.
- Marked completed training stages fixed-template; proposed unopened selection,
  calibration, generated final, and reserved final stages seeded-ordered-decks-v1.
  Readiness remains under review; these declarations do not authorize launch.
- Stage full audits require the expected opening schedule. Candidate input
  preflight requires seeded stages to have verified opening-audit evidence.
  Final metadata validation rejects a silent fixed-template fallback.
- Bound wrapper/audit source files in inference authority and recaptured the
  protocol hashes. Historical original protocol retains its legacy defaults.
- Validation: 50 focused command/audit/protocol/candidate/final-evaluation tests
  passed; Ruff passed. Explicit tests cover both natural final argument paths,
  fixed training declarations, and rejection of a mismatched final schedule.
- The same diagnostic collector remains live (session75744/PID69455); latest
  observed chunk4 at357.36seconds, completed_by_stream=[0,0]. No restart,
  new collection, fitting, or holdout access occurred in this checkpoint.


Complete-collector CPU comparison started without restarting MPS:
- Frozen plan: hog26_seeded_opening_cpu_probe_plan_20260908.json. Same seed
  1278951, balanced, Procedural train 000-0, ordinal0 in both seats, CPU with
  OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1. Two retained complete games.
- This duplicates the first MPS opening pair for a device comparison and must
  not enter the fitting mixture as independent extra games. No model updates.
- CPU exec session28903/PID76314 remains live. Log:
  reports/hog26_seeded_opening_cpu_probe_seed1278951.log. Output target:
  datasets/derived/hog26_seeded_opening_cpu_probe_seed1278951/corpus.npz.
- At the latest live check CPU had completed2chunks at156.537seconds with
  completed_by_stream=[0,0]; MPS had completed7chunks at644.262seconds with
  completed_by_stream=[0,1]. Initial chunk timing is not an end-to-end speed
  result. Both processes survived user interruptions and were not restarted.
- Next: after each complete publication, full corpus/opening audit. After both
  publish, compare CPU complete games to MPS ordinal0 per seat using public
  trajectories and terminal outcomes. Audit all8 MPS games for within-stream
  transcript diversity. Keep the two corpora separate and do not read partial
  spooled games to accelerate the comparison.


CPU probe completed and audited:
- Session28903/PID76314 exited0 normally. Two complete games,781 retained
  decisions,7chunks,549.172seconds. Episode lengths432/349, both learner losses,
  no draws. These are device diagnostics, not model selection or acceptance.
- Full corpus audit passed, including exact initial hands and seeded schedule
  reconstruction: one shared relative deal across two physical seats.
  Reports: hog26_seeded_opening_cpu_probe_seed1278951{,_audit,_diversity}.json.
- Stored complete public transcript digests for the later device comparison.
  One game per stream cannot establish within-stream opening diversity; the
  report explicitly marks this limitation. Do not count the CPU replica as
  additional independent data alongside the matching MPS opening pair.
- CPU completed its pair in7chunks, whereas MPS first reached[1,1] in8chunks.
  No claim of exact device parity or equivalent-work speedup is supported.
  Compare full trajectories only after MPS complete publication; do not inspect
  partial spool files. MPS session75744/PID69455 remains live at18m39s, latest
  chunk11 at1060.496seconds, completed_by_stream=[1,1].


Completed-observation device-policy replay:
- Code inspection: this balanced strategy route uses scores.argmax, not the
  random-opponent multinomial sampler. The learner is deterministic/eval mode.
- Replayed all781 completed CPU actor observations through the frozen base
  policy on CPU and MPS, with exact previous actions/rewards, full retained
  public entity arrays, exact recurrent episode resets, and batch4 replicated
  actor inputs to preserve the production inference batch shape. No optimizer.
- Both devices reproduced every stored learner action: zero mismatches in
 432- and349-decision games, also zero CPU-vs-MPS action mismatches. CPU agreement
  with the corpus checks the replay route for these games.
- This is common-input learner-policy evidence, not full simulator/strategy
  parity or general floating-point equivalence. It does not explain why MPS
  completed the first pair in a different chunk. Full MPS publication remains
  necessary to locate the first trajectory divergence. No partial MPS games
  were opened.
- Reproducible executed source preserved as
  scripts/probe_hog26_completed_policy_device_replay.py; source and input hashes
  recorded in hog26_completed_cpu_policy_device_replay_20260908.json.


Device comparison confound to check before attribution:
The CPU probe retained one episode per stream and therefore clamps surplus
resets to its ordinal0 opening. The MPS probe advances completed rows to later
openings. Their first-game initial conditions match, but the companion row
can differ after the first terminal. A correct row-isolated simulator should
preserve the remaining live game; this has not been established across these
full production trajectories. When MPS publishes, locate the first divergence
relative to the earliest terminal on either device. Do not attribute changed
first-game length to device numerics alone. The common-input policy replay
still establishes zero learner-action discrepancies on the781 CPU observations.
No new run or simulator change was made for this caveat.


MPS seeded opening probe completed; new device-mechanics discrepancy:
- Session75744/PID69455 exited0 normally. Eight complete games,3608 retained
  decisions,31chunks,2893.572seconds,7losses/1win/0draws. Full corpus audit passed
  including seeded reconstruction and all8 recorded initial hands.
- Each seat has4distinct complete public/action transcripts. Four shared
  paired-seat deal identities reconstructed exactly. This resolves the narrow
  repeated-opening mechanics defect in the probe, not broad model acceptance
  or adequate randomized-opening fitting coverage.
- Compared both completed ordinal0 games to the CPU replica. First public
  differences occur at decision15 in both seats, before earliest terminal348.
  Companion reset differences cannot explain the first divergence.
- IceSpirits token420 is absent and tower HP is0.963958 on CPU at decision15,
  but the spirit remains present and tower HP is1.0 on MPS. Public trajectories
  are exact through decision14. Learner actions match until265 in seat0 and
  throughout the common prefix in seat1. CPU/MPS lengths432/450 and349/352;
  both devices lose both first games, but seat0 terminal margins differ.
- Common-input learner replay already matched all781CPU actions on both
  devices. Investigate the IceSpirits impact/timer mechanics and opponent
  actions at the first differing event; do not attribute this to learner
  sampling or companion resets without evidence.
- New complete reports: hog26_seeded_opening_diagnostic_seed1278951{,_audit,
  _diversity}.json and hog26_seeded_opening_device_comparison_20260908.json.
  Exact executed comparison source preserved with hashes.
- No collection jobs remain running. Readiness still under review; replace
  the resolved repeated-opening issue with randomized fitting support and
  the concrete device-mechanics discrepancy. No model fitting, calibration,
  holdout evaluation, or policy updates were launched.


Ice Spirit range boundary repaired:
- Reproduced with matching four-opening schedules and128 native ticks on both
  devices. Joint actions and positions matched; first difference at native
  index106 was attack range and cooldown, followed by damage at117.
- Exact axial distance3500: CPU float32sqrt gives3500.0, MPS gives
  3500.000244140625. Subtracting1500 tower radius makes MPS miss the exact2000
  attack range. This is a geometric threshold defect, not a timer RNG issue.
- Replaced acquisition, retained-target, and post-movement attack/contact
  boundary comparisons with squared distances. Integer-unit geometry uses
  int64, without an epsilon or changed range. Fractional trait fixtures retain
  their floating radius contract. Target ranking/movement still use distances.
- Corrected production prefix traces now match in every recorded field across
  all128 ticks, including joint actions, HP, positions, target IDs, cooldowns,
  contact/attack flags, and spirit timers. Full games are not yet certified.
- Tests: targeting/locks/engine39passed24CUDA-skipped; runtime/reset/spells/
  standard25passed9CUDA-skipped. CPU/MPS exact-boundary and one-unit-outside
  regressions passed. Ruff and diff checks passed. Source authority now pins
  the three changed simulator modules.
- Readiness remains under review. Existing MPS corpora and model screens
  predate the correction and cannot establish corrected-simulator acceptance.
  Next: matched complete games with identical quotas and schedules, then a
  fitting-corpus refresh and randomized-opening learnability reassessment.


Corrected complete-game probe progress:
- CPU session23695/PID17758 exited0. Two games,781 decisions,7chunks,
  559.708seconds; both losses. Full audit and seeded opening verification pass.
- Corrected CPU corpus is byte-for-byte identical to the pre-repair CPU probe
  (SHA256d8c1bfc2727251037e2337bd08c58dd24356815116e8b7ee15ed974fec9000f8).
  Explicit public tensor/trajectory/label comparisons also all pass. This
  establishes CPU non-regression for these two games, not all prior corpora.
- Reports: hog26_corrected_cpu_probe_seed1278951{,_audit}.json and
  hog26_corrected_cpu_regression_probe_20260908.json. Do not combine identical
  before/after corpora as independent evidence.
- MPS session62160/PID17896 remains live at9m55s; latest chunk5 at547.625seconds,
  completed_by_stream=[0,0]. Same retained/surplus quota as CPU. Wait for complete
  publication, audit, then compare full public trajectories and terminal labels.


Corrected full games agree; fitting refresh frozen:
- Corrected MPS session62160/PID17896 exited0: two games,781 decisions,
  734.326seconds,7chunks, both losses. Full corpus/opening audit passed.
- CPU/MPS exact agreement on every checked complete public trajectory field,
  actions, masks, previous actions/rewards, next globals, terminal winners,
  W/D/L, terminal margins, and episode boundaries. Both lengths432/349.
  The reproduced full-game discrepancy is resolved for this paired matchup.
  This is scoped mechanics verification, not global simulator/model acceptance.
- Full comparison: hog26_corrected_complete_device_comparison_20260908.json.
- Active protocol now declares corrected seeded training shards1278961/2/3,
  128games each across the original8training families and6styles. Preserved
  old training rows and candidate-data declarations under historical keys;
  none of those pre-fix fitting corpora are eligible for the refreshed fit.
- Fresh draw controls planned: training1278964 and validation1278965,4actor
  views each. Validation control remains unopened with development/calibration.
  Existing list-field names are preserved, but their paths now name only the
  fresh training/validation controls. No old MPS auxiliary fitting data remains.
- Readiness remains under review: corrected training collection is allowed,
  candidate fitting and evaluation collection await training-family learnability
  reassessment and design freeze.33protocol/command/trainer/loader tests pass.
- Next collection: shard0 balanced/random,128complete games onMPS, seed1278961.
  Subsequent shards and training draw control follow after audited completion;
  no partial shard fitting or model/policy updates.


First corrected fitting shard complete and audited:
- Seed1278961 balanced/random:128complete games,56223decisions,48wins/80losses/
  0draws,11chunks,8796.449seconds. Corpus SHA256
  38135e48f49b5aa3200ad1ab575b31da179e71e5efc6bd2010a027d03604bea5.
- Full protocol-bound audit passed all checks: exact deck/family/style budget,
  complete boundaries and terminal labels, absent critic arrays, public mask
  v2, seeded schedule reconstruction, all128initial public hands.64paired
  scenario identities, with64early/62middle/16late reached-phase groups.
  Late groups include11withloss/6withwin/1withboth; no acceptance claim.
- Complete public trajectory hashing finds64distinct balanced and64distinct
  random transcripts. With one game per stream this does not itself measure
  repeated-opening diversity; prior four-opening probe supplies that scoped
  evidence, and paired scenario grouping remains mandatory.
- Reports: hog26_corrected_train_balanced_random_seed1278961{,_audit,
  _diversity}.json. No partial data was opened before complete publication.
- First collector session21571/PID29039 exited0; full audit process also exited0.
- Started the frozen next shard: seed1278962, bridge-pressure/reactive-defense,
  128games, MPS, OMP/MKL threads1. Active session20798/PID34414 verified live.
  Log reports/hog26_corrected_train_bridge_reactive_seed1278962.log; output
  datasets/derived/hog26_corrected_train_bridge_reactive_seed1278962/corpus.npz.
  Preserve this process, audit after full publication, then collect shard2
  seed1278963 and training draw control1278964. Candidate fitting, validation
  control1278965, selection/calibration, holdout, and policy updates stay gated.


Second corrected fitting shard complete and audited:
- Seed 1278962, bridge-pressure/reactive-defense: 128 complete games,
  51,227 decisions, 58 wins, 70 losses, zero draws. Twelve chunks completed;
  collector session 20798/PID 34414 exited 0. Audit session 16876 exited 0.
- All protocol-bound checks passed, including complete boundaries, terminal
  labels, absent critic inputs, public mask v2, exact decks/styles/split,
  reconstructed seeded openings, and all 128 initial actor hands.
- Corpus SHA256: 691b19b7bc5e6d2caa9a2d112c260ef200e1396cb904e0917e41dc19aac450b0.
- Paired scenario groups: early 64, middle 57, late 15. Late groups include
  10 with losses and 5 with wins. This is corpus evidence, not model acceptance.
- Started frozen shard 2 (third natural shard), seed 1278963, slow-push/spell-control,
  MPS, OMP/MKL threads 1. Session 31123/PID 26475 verified live.
  Log: reports/hog26_corrected_train_slow_spell_seed1278963.log.
- Next: preserve this collector, audit after full publication, then collect
  training draw control 1278964. Candidate fitting, validation control,
  selection/calibration, holdout, and policy updates remain gated.


Third corrected fitting shard complete and audited:
- Seed 1278963, slow-push/spell-control: 128 complete games, 52,049 decisions,
  46 wins, 82 losses, zero draws. Collector session 31123 exited 0;
  protocol-bound audit session 8680 exited 0 with all checks passed.
- Corpus SHA256: 57eae5b1521f0eed473aa1037bdd15ade5f99bc570baad2804c955691289e286.
- Opening reconstruction verified all 128 initial hands and 64 paired deals.
  Reached phase groups: early 64, middle 58, late 6. Late coverage is sparse:
  five groups with losses and one with a win. No model acceptance claim.
- All three corrected natural shards now total 384 games, 159,499 decisions,
  152 wins, 232 losses, zero draws. Candidate fitting remains gated.
- Started predeclared training draw control seed 1278964, two frozen-policy
  battles and four actor views, MPS, session 33985. Preserve this process.
  Log: reports/hog26_corrected_draw_training_seed1278964.log.
- Next: audit the complete draw control, then reassess learnability using only
  training-family exclusions. Validation draw control 1278965 and all
  selection/calibration/final corpora remain unopened; no policy updates.


Corrected training draw control complete and audited:
- Seed 1278964 collector session 33985/PID 31840 exited 0.
- Four actor views, 1,552 decisions, four draws, exactly zero terminal margin.
  Corpus audit passed all configured checks. Fixed-template symmetric openings
  are explicitly not verified as independent seeded natural-game scenarios.
- Corpus SHA256: 42bd17fdf53af8eee43c2b42249e269c2432b13bc1e8403e18f8410adcf7d8f8.
- All declared corrected fitting data are complete: 384 natural games plus four
  controlled actor views, 161,051 total decisions. No collector remains active.
- Next required action is training-family learnability reassessment using the
  complete corrected corpora. Candidate fitting/selection/calibration/final
  evaluation remain gated; validation draw control 1278965 remains unopened.


Corrected-data training-family reassessment completed on 2026-09-09:
- Both fixed diagnostic plans use only the three corrected natural corpora and
  corrected training draw control. Prior folds, seeds, epochs, and architecture
  were preserved. Source hashes and current audits passed before fitting.
- WDL screen completed eight fits, exit 0. Representative AUC 0.83233/0.83080,
  ECE 0.03087/0.03001, and NLL gain 0.23457/0.23390. Every phase improves NLL,
  including full-phase early gains 0.09960/0.10061. These are training-family
  diagnostics, not independent public-state acceptance or natural draw proof.
- Hybrid margin screen completed eight fits, exit 0. Pooled MAE gains
  0.01618/0.01593 pass its narrow point screen, but conceal material failures.
  Families 006/007 regress 0.03937/0.03555; bridge-pressure regresses
  0.02595/0.02360. Do not freeze the candidate from the pooled result.
- Late representative gain is 0.001925 on 60 games in 37 verified paired
  scenarios. A fixed-prediction paired-scenario bootstrap gives 95 percent
  interval [-0.01193, 0.01305]. Overall family-cluster intervals also cross zero.
  This bootstrap does not refit the heads and has only eight family clusters.
- Artifacts: hog26_corrected_wdl_complete_globals_screen_20260909.json,
  hog26_corrected_hybrid_margin_screen_20260909.json, their frozen plans, and
  hog26_corrected_margin_reassessment_20260909.json. The standalone summary
  script reconstructs opening clusters and verifies input corpus hashes.
- Decision: outcome learnability survives the corrections; the proposed margin
  design is not ready to freeze. Next inspect family/style error structure and
  public representation sufficiency before prescribing a replacement diagnostic.
  Do not tune against selection/calibration/final labels. All those corpora and
  validation draw control remain unopened. No policy updates occurred.
- All three diagnostic/summary processes exited 0. Ruff passed for the new
  summary script. No training or collector process remains active.


Corrected margin error diagnosis and public-feature comparison, 2026-09-09:
- Signed errors locate the largest regulation failure in family007. Early
  terminal-minus-current margin averages +0.01760, while the globals heads
  predict about -0.162. Bridge-pressure early targets need -0.00427 on average,
  while the heads predict -0.10907/-0.10636. This establishes systematic bias,
  not a causal proof of missing representation or optimizer failure.
- A fixed-budget public spatial-mechanics comparison completed eight fits with
  the same corrected sources, folds, seeds, hidden width, optimizer and epochs.
  It adds public mechanics-position inputs and parameters, so it is not a
  parameter-matched ablation. Overall MAE gains rise to 0.02141/0.02116.
  Families006/007 still regress 0.01969/0.02353; bridge-pressure still regresses
  0.01724/0.01745. Neither the globals nor spatial model is ready to freeze.
- The overtime hard override produces identical late predictions in both models.
  Late training inspection finds a final-decision reactive-defense state with
  projected delta +0.14767 versus actual -0.00808, and a paired scenario with
  projected +0.16022 versus actual -0.27720. Recent damage extrapolation is not
  a reliable forecast of future direction or stopping time in these cases.
  Remaining-decision counts and terminal labels are diagnostics only.
- Saved signed-error, late-error, spatial-screen and representation-comparison
  reports under hog26_corrected_*_20260909.json. Updated protocol readiness to
  replace the completed collection blocker with these observed model defects.
- Next: reassess the fixed overtime override and causal public temporal features
  together, rather than promoting the best pooled score or adding slice-specific
  exceptions. No selection/calibration/final labels or validation draw control
  were opened. Spatial screen session11035 and error analysis sessions exited0.


Causal public-history diagnostic completed, 2026-09-09:
- Added diagnostic-only public changes over1/5/20 prior decisions, recent public
  damage-race delta and horizon, preserving the current18-global suffix.
  Only public arrays and complete game boundaries enter feature construction.
  No fixed overtime override is allowed in this diagnostic mode.
- Matched control zeros all56 added history fields with identical dimensions,
  parameter count, seeds, family folds, optimizer, weights and epoch budget.
  Both variants use the corrected spatial-mechanics features. Sixteen fits
  completed, sessions71176/93521 exited0. No candidate was produced.
- Future-row perturbations leave prior features bitwise unchanged; separate-game
  extraction matches combined extraction exactly. Reset, lag and invalid-boundary
  checks passed.15focused causal/weight tests passed; Ruff passed all3code files.
- History late representative MAE gains are -0.05849/-0.05586, and full-phase
  late gains are -0.00212/-0.00201. Every fold also regresses on its own fitting
  late representatives, ranging roughly -0.030 to -0.046. Thus the late failure
  is not explained by excluded-family generalization alone.
- Results and the zero-history comparison are preserved as
  hog26_corrected_history_margin_comparison_20260909.json and the two pinned
  plans/full screen reports. This design is rejected for candidate freeze.
- Next diagnostic should distinguish fitting capacity and cross-phase loss
  interference before another generalization attempt. Preserve causal inputs,
  complete-game/family separation and all independent acceptance requirements.
  Selection/calibration/final data and validation draw control remain unopened.


Phase separation versus shared capacity diagnostic, 2026-09-09:
- Added diagnostic-only independent phase margin heads routed by public progress.
  A phase loss cannot update other heads; boundary routing and the prior causal
  history/weight tests pass.17tests total, Ruff and diff checks pass.
- Compared three width16heads with one shared width48head:41,571 versus41,569
  trainable margin parameters. Same864public spatial/history inputs, seeds,
  folds, minibatches, loss weights, optimizer and30epochs.16fits completed,
  sessions86378/37192 exited0. No runtime inference model was changed.
- Phase-specific pooled MAE gains improve to0.02908/0.02690, but late gains
  remain -0.04534/-0.04419 and bridge-pressure worsens -0.04968/-0.04986.
  Every phase-specific fit still regresses on fitting late representatives.
  Neither phase splitting nor a wider shared head yields an acceptable design.
- Preserved both plans and full reports, plus
  hog26_corrected_phase_capacity_comparison_20260909.json. These are diagnostics
  only. Do not promote pooled improvements or relax phase/opponent requirements.
- Next: test whether a materially different supervised regressor can fit the
  public late-state targets before further small neural architecture adjustments.
  Keep fitting and family-generalization evidence separate. Selection/calibration/
  final labels and validation draw control remain unopened; no policy updates.


Tree fitting-capacity diagnostic launched, 2026-09-09:
- Added training-only histogram gradient boosting with absolute-error loss,
 100fixed iterations,15leaves, min20decision rows per leaf, learning rate0.05,
 L2=1,255bins, and early_stopping=False. Fit features, targets and weights are
 sliced to fitting rows before sklearn.fit. No neural residual cap or overtime
 override. Same864causal public spatial/history features and family exclusions.
- Scikit-learn1.7.2, joblib1.5.2 and threadpoolctl3.6.0 installed with --no-deps
 into /Users/sam/.cache/clasher-margin-tree-diagnostic. Existing NumPy/Torch
 versions and pinned production inference authority verified unchanged.
-16causal/history/weight/label-isolation tests passed. Changing excluded-family
 targets and sample weights leaves all predictions bitwise unchanged. Ruff and
 diff checks passed. No production inference implementation was changed.
- Frozen plan: hog26_corrected_tree_margin_screen_plan_20260909.json. Tree config
 governs this branch; inherited neural optimizer/epoch fields are unused. Two
 inherited seeds are reproducibility runs, not necessarily distinct models:
 the tree algorithm may be deterministic at this data size with early stopping off.
- Active session81357/PID72962, verified consuming CPU with about9GiB RSS.
 Log reports/hog26_corrected_tree_margin_screen_20260909.log. Preserve the live
 job; an observation yield is not a failure. Inspect full fitting/withheld phase
 scores after completion before drawing conclusions or launching further work.
- Candidate fitting, selection/calibration/final labels, validation draw control,
 and policy updates remain gated. This diagnostic cannot establish acceptance.


Tree diagnostic complete and phase-sampling mismatch measured, 2026-09-09:
- All8tree fits completed; session81357/PID72962 exited0. Two seed runs have
  identical representative predictions, so they are reproducibility evidence,
  not distinct independently trained models. Summary script records this.
- Pooled MAE improves0.03030 and full-phase late MAE improves0.01278. However,
  late representative MAE regresses0.02459 and every excluded-family late fold
  regresses. Families006/007 pooled gain remains -0.02103. Candidate rejected.
- Trees improve fitting late representatives in3/4folds, with gains
  +0.00120/-0.00305/+0.00715/+0.01119. This improves fitting relative to the
  small neural heads but does not prove public representation sufficiency or
  family generalization. Bridge-pressure pooled gain is -0.00603.
- Natural-data sampling audit:51/60late representatives are final-decision
  states, hence85percent of representative metric mass. Final decisions carry
  only4.780percent of equal-game full-phase late mass. Middle fractions are
 15.634percent versus0.997percent; early1.823percent versus0.0723percent.
  These are different existing metric distributions, not new acceptance rules.
- Artifacts: hog26_corrected_tree_margin_screen_20260909.json,
  hog26_corrected_tree_margin_diagnosis_20260909.json, and
  hog26_corrected_phase_sampling_distribution_20260909.json.
- Next: predeclare a fitting-weight comparison covering both existing all-state
  and representative distributions, using fitting games only. Preserve both
  evaluation checks and all thresholds. A distribution mismatch is a hypothesis
  for the endpoint errors, not proof of their sole cause. Do not select a model
  using held-out evaluation labels or add family/style-specific exceptions.
- No jobs remain active. Candidate fitting and all selection/calibration/final
  evaluation data and validation draw control remain gated; no policy updates.


Fixed mixed-distribution fitting comparison launched, 2026-09-09:
- Predeclared50percent of each fitting game-phase loss mass on uniform states
  and50percent on its existing representative. Original game-phase total mass
  remains unchanged; excluded-family weights remain zero. No inference feature
  uses the representative position, future endpoint, labels or new privileged data.
-21weight/causal tests passed: exact zero-mass control, per-game-phase mass,
  excluded-representative invariance, invalid mixture values and prior checks.
  Ruff and diff checks passed. Both acceptance distributions stay unchanged.
- Neural history comparison completed8fits, session69555 exited0. Late
  representative gains improve from -0.05849/-0.05586 to -0.03694/-0.04049,
  still failing. Full-phase late gains become +0.00221/+0.00175. All fitting
  late representatives still regress. Weighting helps but is not sufficient.
- Neural comparison saved in hog26_corrected_neural_weight_comparison_20260909.json.
- Tree mixed-weight comparison running: session42230/PID86554 verified live.
  Same fixed tree configuration and corrected864public features, only weights
  changed. One seed and4family folds because prior tree seed runs were identical.
  Log reports/hog26_corrected_tree_mixed_margin_screen_20260909.log.
  Preserve the job; inspect both distributions and all slices after completion.
- Candidate fitting, selection/calibration/final data, validation draw control
  and policy updates remain gated.


Mixed-loss tree comparison complete, 2026-09-09:
- Session42230/PID86554 exited0; all4family folds complete. Overall MAE gain
  improves from0.03030 to0.03709. Late representative gain improves from
 -0.02459 to -0.00691 but remains negative. Full-phase late gain is+0.01363.
- Fitting late gains are positive in all4folds:0.02600/0.01155/0.02802/0.02789.
  Excluded-family late gains are -0.02255/+0.00374/-0.00720/-0.00851.
  Families006/007 pooled gain remains -0.01767; bridge-pressure -0.00774.
  The tree now fits its late representatives well but does not generalize
  reliably. Candidate freeze remains unjustified.
- Saved full screen, tree_weight_comparison and tree_mixed_late_errors reports
  under hog26_corrected_*_20260909.json. The worst residual errors are still
  final-decision states, including forecast -0.25520 versus current -0.13055 and
  terminal -0.13196 on balanced family001-3. Its live own tower has0.00426HP
  fraction. Other errors also overshoot near low surviving tower health.
- Public input review: current spatial summaries use pooled moments, not explicit
  attacker-to-tower distances. Public sensor contract permits position, HP,
  range, radius, damage and motion, but excludes attack-windup/cooldown fields.
  This leaves a concrete representation hypothesis: encode visible per-tower
  threat geometry as features, rather than assuming recent damage persists or
  hard-clamping predictions by progress. No causation claim from these examples.
- Next predeclare and test that public relational representation, with the fixed
  mixed loss and family folds; preserve both evaluation distributions. Do not
  add style/family-specific exceptions or tune a mixture sweep. No jobs remain
  active. All independent evaluation data and policy updates remain gated.


Public relational geometry audit and diagnostic launch, 2026-09-09:
- Collector source review found simple_projection._entity_features populates
  positions/team/kind/HP and selected status flags, leaving entity range/radius/
  damage/motion columns zero. _typed_lookups maps all crown towers toKingTower.
  These are existing projection limits, not changes to the physical game labels.
- New diagnostic features therefore use public card metadata from the frozen
  actor encoder and explicit public standard-arena fixtures, not those zero
  columns or a guessed tower identity. Six towers times8features capture HP,
  minimum opposing attacker gap, public damage magnitudes, geometric reach and
  nearby ground-attacker pressure. No attack-lock, cooldown or readiness claim;
  no projectile-coverage claim and no prediction override.
- Initial run session86439/PID98727 was intentionally stopped, exit130, after
  source inspection caught attacker radius incorrectly added to attack reach.
  Preserved original source/plan and exclusion reason in
  hog26_tree_geometry_reach_correction_20260909.json. Do not use that run.
- Corrected reach uses integer reconstructed public positions and ranges, squared
  distance versus attack range plus target radius. Tests cover exact boundary,
  attacker-radius independence, masked entities, permutation, empty/dead towers,
  units/opponent selection and immunity to unconsumed entity fields. Prior
  history/mixed-weight suite passed17tests, then all5geometry tests passed after
  adding the unconsumed-field test. Ruff and diff checks pass.
- Frozen v2plan retains tree configuration, seed, family folds and50/50loss,
  adding48public relational features for912total inputs. Current live run:
  session6910/PID796, verified100percentCPU and about9.3GiB RSS. Log:
  reports/hog26_corrected_tree_geometry_v2_margin_screen_20260909.log.
- Preserve that job and inspect full fitting/withheld phase and style results
  after completion. Candidate fitting and independent evaluation data remain
  gated; no policy updates. No production inference source was changed.


Geometry comparison complete; public event coverage omission found, 2026-09-09:
- Corrected v2geometry run session6910/PID796 exited0 after4folds. Overall MAE
  gain0.03579 is below mixed-tree baseline0.03709. Late representative gain
 -0.00780 is slightly worse than -0.00691; full-phase late gain is+0.01435.
  All fitting late folds improve, but all excluded late folds regress.
  Geometry addition does not justify a candidate freeze.
- Saved full report and hog26_corrected_tree_geometry_comparison_20260909.json.
- Audited all159,499natural training decision observations. Every corpus has
  zero projectile-kind rows, area-effect-kind rows, projectile tokens, nonzero
  motion fields and nonzero direct entity-damage fields. Public card metadata
  remains separately available; these counts concern the recorded entity view.
- Source confirms simple_projection projects only FastGymState entity slots,
  while runtime projectile/area objects live in FastEffectState and resolve in
  step_fast_effects. The typed lookup only binds troop/building bodies and the
  shared crown token. Relevant source: simple_projection.py, simple_effects.py,
  simple_runtime.py and rl/simple_pytorch_backend.py.
- This is a concrete observation coverage limitation, not proof of causation
  or of a successful replacement. The existing public-mask audit checks allowed
  inputs; it does not establish completeness of visible event coverage.
- Next: pause further head tuning and build a bounded public-event projection
  probe. Expose only publicly observable typed effect appearance/position and
  permitted motion, never hidden target locks, future hit damage or impact time.
  Verify against native effect traces and preserve frozen-policy behavior before
  deciding on audited replay enrichment or any fresh collection. No independent
  evaluation data were opened and no policy updates occurred. No jobs remain.


Bounded public-effect projection probe completed, 2026-09-09:
- Built a separate diagnostic interface accepting only observed positions,
  affiliation, generic appearance class and an explicit per-seat visibility
  mask. No source-card identity, target lock/coordinates, future damage,
  lifetime, status schedule or impact time is accepted by the projection API.
- Important audit constraint: native FAST_EFFECT_AREA also represents delayed
  direct/melee hits. Native active effects are not automatically visible sprites.
  A production appearance registry must distinguish public effects from those
  internal combat queues before any corpus enrichment. No blanket active mask.
- Four unit tests pass for visibility masking, canonical seats/appearance,
  unknown appearance masking and required boolean visibility. A known visible
  projectile fixture traverses x=0/400/800logic units, then disappears on impact.
- Native CPU and indexedMPS0probe frames are identical. Projection is read-only;
  stepping with and without it preserves identical full native state/effect
  digests and statuses. Perturbing all non-public effect fields changes no current
  projected feature or mask. The native control receives expected impact damage.
- Initial unindexedMPSfixture failed the existing strict device comparison;
  rerun with mps:0matches the actual tensor device and passes. This is functional
  fixture evidence, not complete simulator/device acceptance or a speed claim.
- Artifact: hog26_native_public_effect_probe_20260909.json. Probe scripts:
  hog26_public_effect_probe.py and probe_hog26_native_public_effects_20260909.py.
  No policy input path or production inference source was modified.
- Next: bind a public appearance registry to actual supported projectile/area
  definitions and verify native-to-public event traces. Only then assess an
  exact frozen-policy replay enrichment route, retaining all original corpus
  action/terminal-label digests. Current corpora have not been enriched. Further
  head tuning, candidate fitting and independent evaluation remain gated.


Public effect identity and lifecycle inventory, 2026-09-09:
- Compiled all73runtime card rows from the pinned supported-deck manifest.
  Found32serialized identity candidates,33internal direct-hit primitives,
  3unresolved identities,4non-effect/unsupported rows and1shared tower override.
  All production_visibility_authorized flags remain false. Inventory is not
  a visibility certificate and does not grant permission to expose native queues.
- Unresolved rows are internal LavaPups, internal SpearGoblin andArrows. Public
  visible-name lookup recovers SpearGoblinProjectile, but LavaPups lacks the
  direct serialized reference used by this first-pass inventory. Towers require
  a separate public fixture/appearance mapping because card_id0is shared.
- Executable scalar factory comparison exposes lifecycle mismatches: Fireball
  is ProjectileSpell and native projectile; Poison is AreaEffectSpell and native
  area. Arrows is a scalar ProjectileSpell with10projectiles across3waves spaced
 0.2seconds, yet its native primitive is area. Zap is scalar DirectDamageSpell,
  also native area. These native primitive labels cannot be used as visible
  object classes or spawn timings without a dedicated emission contract.
- Debug visualizer draws projectile bodies but also privileged target guides
  and source labels. Do not treat the whole debug-render frame as public actor
  evidence or feed target markers/labels into the outcome model.
- Artifacts: hog26_public_effect_registry_audit_20260909.json and
  hog26_public_effect_lifecycle_audit_20260909.json. Registry audit script passes
  Ruff and completes on the pinned supported catalog. No production path changed.
- Next: implement/verify a native public-event emission contract separately from
  combat queues, starting with serialized ordinary projectiles and explicitly
  handling tower overrides, direct-hit exclusion and Arrows/Zap lifecycle cases.
  Keep the original frozen-policy observations/actions unchanged while validating
  sidecar traces. No new collection, fitting or evaluation labels opened.


Ordinary projectile sidecar and native allocation probe, 2026-09-09:
- Added an experimental primary-attack/cast-pool adapter. Rules bind exact
  runtime names/primitives to serialized projectile identities. Exclude
  consuming, rolling, multi-target, chain, line, fan and non-damaging delivery
  carriers from ordinary-flight rules. Final registry contains18identities.
- Direct-hit area queues produce no public object. An unresolved active entry,
  area spell, shared tower/card0override, or primitive mismatch raises and stops
  enrichment rather than silently disappearing or exposing an internal queue.
  The adapter must not be applied to death/travel/triggered pools.
- Public output is typed appearance, current canonical position, observed
  affiliation and visibility only. No target, damage, lifetime or impact schedule
  is emitted. Altering those private combat values leaves projection unchanged.
-10interface/sidecar tests pass, including fail-closed unsupported events and
  direct-hit exclusion. Native allocation accepts all18ordinary identities;
  birth plus3motion steps produce identicalCPU/MPS0public frames. Full native
  state/effect digests are unchanged by projection. No frozen-policy path changed.
- Artifact: hog26_ordinary_projectile_allocation_probe_20260909.json. Rules and
  probe source hashes are recorded. This is allocation-level evidence, not an
  actual complete-game cast-route, renderer, capacity or all-effect certificate.
- Next: exercise the sidecar at the actual native runtime boundary, audit all
  effect pools/cast routes and handle tower/area/special lifecycles explicitly.
  Keep fail-closed coverage reporting and unchanged frozen-policy outputs.
  No corpus enrichment, further fitting, independent evaluation or policy update
  is authorized by the narrow probe. No jobs remain active.


Actual runtime cast-route audit completed, 2026-09-09:
- Exercised7scripted single-cast/deployment cases for160native ticks onCPU and
  MPS0: Fireball, Arrows, Poison, Zap, GoblinBarrel, Log andMusketeer. Every
  initial action succeeded. This is a bounded fixture, not complete policy games.
- A control runtime received identical actions without sidecar reads. Actor
  observations/legal masks remained byte-identical on every tick; full mutable
  native state checkpoints matched at ticks1/40/80/160. CPU/MPS actor trace hashes
  and complete case records are identical. No production policy path changed.
- Fireball produced39sidecar frames without rejection. Poison caused159rejected
  frames; GoblinBarrel69. Musketeer produced4frames but55rejections when unmapped
  tower projectiles were also active. Log occupied its separate rolling pool
  for50frames and never entered the primary effect sidecar.
- Crucial gap: Arrows and Zap each allocated an area effect but had zero active
  effect frames at the boundary. Their allocation and consumption happen in one
  tick. An active-pool-only rejection rule silently misses these public events.
- Added a complementary primary transition guard rejecting area births even
  after consumption, invalid projectile receipts, and newly born projectiles
  consumed before the boundary. Direct hit queues are not area sprites.14unit
  tests pass across guard/sidecar/projection; Ruff passes. Guard passing is not
  an all-pool certificate and no enrichment path is yet authorized by it.
- Reports: hog26_public_effect_runtime_routes_cpu_20260909.json,
  hog26_public_effect_runtime_routes_mps_20260909.json and route_comparison.
  CPU session75168 andMPS87697 exited0. No jobs remain active.
- Next: integrate transition-time public event emission/coverage, then implement
  tower, area/instant spell and separate rolling/delivery lifecycle rules. Do not
  publish partial enriched corpora based on surviving effects alone. Full-game
  frozen-policy action/label preservation remains required. Head fitting and all
  independent evaluation data remain gated; no policy updates occurred.


Tower-shot sidecar extension and transition audit, 2026-09-09:
- Frozen policy vocabulary lacks TowerPrincessProjectile. Added a separate
  outcome-sidecar extension preserving every existing policy token ID. Princess
  identity comes from serialized standard tower data. King uses an explicit
  public_tower_shot:king source category; no unverified asset name was guessed.
- Card0tower shots require exact fixed public launch coordinates and affiliation.
  Unknown origins/owners remain rejected. Current position and public source
  class are exposed, never target coordinates, future damage or hit schedule.
  Public-origin classification assumes the fixed visible arena towers; no
  real-camera source-tracking certificate is claimed.
-18tower/sidecar/transition/projection tests pass. Runtime CPU andMPS0probes
  each complete160ticks with tower rules and transition-gap accounting enabled.
  Legacy actor observation hashes remain identical to the pre-extension control.
- Musketeer now has59sidecar frames and0rejections, versus4frames/55rejections.
  GoblinBarrel has10mapped tower frames and59unhandled delivery-flight frames.
  Arrows andZap each register1transition gap despite0surviving effect frames;
  Poison registers1birth gap and159active-frame rejections. Log remains in its
  separate rolling pool. Scalar factory confirms GoblinBarrel is SpawnProjectileSpell.
- CPU/MPS case counts match, but first recorded Musketeer-fixture tower-shot y
  differs by1logic unit: CPU0.7687500119 versusMPS0.7687812448 normalized board y.
  Do not claim sidecar bit identity or a bound over unrecorded frames. Investigate
  launch/step rounding before deciding any conformance tolerance or physics fix.
- Reports: hog26_public_effect_runtime_towers_cpu/mps_20260909.json and
  hog26_public_tower_sidecar_comparison_20260909.json. CPU29461 andMPS57190
  exited0. No jobs remain active. No production policy or physics source changed.
- Next: isolate the tower projectile precision discrepancy and implement the
  still-unhandled delivery, area/instant and rolling event lifecycles. Preserve
  transition receipts and frozen-policy behavior. No enrichment or fitting yet;
  independent evaluation and policy updates remain gated.


Tower projectile precision isolated; exact offset prototype verified, 2026-09-09:
- Reproduced first tower shot at tick85 in a native Musketeer fixture onCPU/MPS.
  Both have source(3500,25500), target(3500,18460), and speed600logic units/tick.
  CPU sqrt distance is7040.0; MPS7040.00048828125. Muzzle y offsets before
  truncation are -300.0 versus -299.9999694824219, truncating to -300/-299.
  The resulting first observed projectile y is24600/24601. Cause is launch
  normalization/truncation, not the public projection or differing target state.
- Added an integer muzzle-offset prototype. For the declared coordinate domain,
  floor(abs(delta)*radius/sqrt(distance_squared)) is computed via integer quotient
  and integer-corrected square root. No epsilon or nearest-integer reinterpretation.
- Exact Python isqrt reference matches4101cases on each ofCPU/MPS0, including
  axes, the observed7040case, zero displacement, full reach and board extremes.
  Three tests pass; Ruff passes. Diagnostic code includes explicit domain checks
  and is not wired into the native hot path or certified for throughput.
- Artifacts: hog26_tower_launch_precision_probe_20260909.json and
  hog26_integer_muzzle_reference_20260909.json. Reproducer and reference test
  sources are retained. No production physics, policy, or corpus bytes changed.
- Next: integrate the exact calculation only after native trajectory/outcome
  comparisons and hot-path validation; existing corpora cannot be relabelled as
  collected under a changed runtime. Continue public effect lifecycle coverage
  with the same provenance boundary. No fitting/evaluation/policy updates.


Isolated exact-muzzle native differential checks, 2026-09-09:
- Built an explicit diagnostic allocator variant from inspected local source and
  one literal muzzle-offset replacement. Scoped process-local patching restores
  the original runtime binding after each test step. No production file changed.
- Seven160tick runtime fixtures completed for legacyCPU, exactCPU andexactMPS0.
  LegacyCPU versus exactCPU actor traces, all recorded sidecar trace hashes,
  final mutable native-state hashes and case records are identical. ExactCPU
  versus exactMPS agrees on the same measures, resolving the observed tower
  launch discrepancy within this tested scope.
- Existing attack-effect/runtime-spell semantic suites under the variant:
 5passed,2CUDA-skipped,1source/hot-path test deselected because this is a
  dynamically constructed diagnostic function. No hot-path or CUDA claim.
- The prototype includes host-synchronizing domain validation. It is not ready
  for production capture/performance use, and these8secondfixtures do not
  recertify complete-game outcomes or all geometry under changed physics.
- Reports: hog26_exact_muzzle_runtime_cpu/mps_20260909.json,
  hog26_legacy_muzzle_runtime_cpu_20260909.json and
  hog26_exact_muzzle_native_comparison_20260909.json. All runs exited0.
- Preserve production authority and existing corpora until full-game replay
  and hot-path requirements justify a physics change. Continue event-lifecycle
  coverage under the unchanged runtime meanwhile; delivery, area/instant and
  rolling routes remain unresolved. No training or independent labels opened.


Public delivery-flight route verified, 2026-09-09:
- Added an explicit SpawnProjectileSpell rule matching serialized carrier name,
  runtime primitive and public token. The supported registry admits GoblinBarrel
  without reclassifying all non-damaging carriers as ordinary attacks.
- CPU/MPS160tick route probes each capture59GoblinBarrelSpell frames plus10tower
  frames, with0active-pool rejections. Legacy actor traces remain unchanged.
  Payload count, target and future timing never enter sidecar features.
-12delivery/ordinary/transition tests passed, including appearance mismatch
  rejection, unchanged ordinary rules, and private-field perturbation. Ruff passed.
- Artifacts: hog26_public_effect_delivery_cpu/mps_20260909.json and
  hog26_public_delivery_comparison_20260909.json. CPU94028/MPS75502 exited0.
  Known legacy tower-launch CPU/MPSposition difference remains; no physics fix
  was applied and no sidecar bit-identity or complete-game acceptance is claimed.
- Rolling and area/instant routes still require separate handling. No enrichment,
  model fitting, independent labels or policy updates.
