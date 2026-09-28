> USER PAUSE 2026-09-13: Training and automatic continuation are paused pending comparison with external Clash Royale bots. Do not launch the queued late-continuation probe, further fitting, collection, search, or policy updates. The three-class campaign completed; its artifacts are preserved. A fresh pipeline requires the next user decision.

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


Rolling-body prototype exposed a native/scalar lifecycle mismatch, 2026-09-09:
- Added a diagnostic rolling-pool projector using serialized rolling-body token,
  current position, affiliation and activity. Two tests pass for private hit-
  ledger/target/payload invariance and unregistered-body rejection. No policy
  inputs or physics were changed.
- CPU native160tick probe captures50LogProjectileRolling frames. However its
  first frame is near the king launch point, approximately(8.917,2.682), at tick1.
  Runtime _rolling_commands supplies king-source coordinates as the rolling
  origin and the selected placement as its direction target.
- Instantiating scalar Log at the same player0target(3.5,14.5) creates a
  RollingProjectile at(3.5,14.5), with1.833385942seconds spawn delay and10.1tiles
  rolling range. Scalar RollingProjectileSpell.cast explicitly uses placement
  as rolling origin after casting delay. Thus the native trajectory/lifecycle
  is not merely missing a public projection; its rolling command semantics differ.
- Saved hog26_public_effect_rolling_cpu_20260909.json and
  hog26_log_origin_lifecycle_mismatch_20260909.json. Do not certify this rolling
  view or enrich training corpora with it as a scalar-equivalent public event.
  Additional MPSrolling validation was not launched after this mismatch surfaced.
- Delivery flight work is committed separately asd55982fd. The current rolling
  work remains an explicit diagnostic. Native Log origin/delay and earlier
  Arrows timing differences need adjudication before model/corpus work resumes.
  No policy updates or independent evaluation data were opened.


Native rolling lifecycle repaired and bounded scalar parity tested, 2026-09-09:
- Changed rolling commands to use selected placement as origin and owner-relative
  forward direction. Compiled casting speed/minimum distance from shared scalar
  spell metadata, with integer-corrected ceiling arithmetic for delay ticks.
- Added delay state to the rolling pool/reset templates. Pending rollers neither
  move nor hit; public projection masks their queued position until activation.
- Added the scalar Log-family rectangular footprint, preserving capsule defaults
  for generic lower-level callers. Paired damage checks exposed fractional Crown
  damage; rectangular spells now use native integer percentage ceiling arithmetic.
-22focused tests passed,7CUDAcases skipped. Paired Log/BarbLog tests onCPU/MPS0
  match both seats' positions, activity and tower HP every tick, plus terminal
  payload count/owner/position. Existing rolling, runtime spell and reset tests
  pass. Ruff and diff checks pass. This is not all-spell or full-game acceptance.
- Expanded inference authority to cover changed catalog/runtime/rolling sources.
  Verified that the old protocol now rejects current physics. Its stored source
  authority was deliberately not recaptured. Existing corpus bytes remain intact
  and must not be called collected under this repaired runtime.
- Artifact: hog26_native_rolling_repair_20260909.json. Test run43044 exited0.
  Next address remaining spell lifecycle differences, especially Arrows timing,
  then perform full-game recertification and freeze a fresh data/source protocol.
  No collection, fitting, independent evaluation labels or policy updates opened.

Single-projectile payload correction and Arrows differential, 2026-09-09:
- Single-wave projectile spells now use normalized scalar payload damage and
  explicit crown damage ratios. Fireball changes from 269 to 688 troop damage,
  Giant Snowball from 70 to 179, and Rocket from 580 to 1484. Focused runtime
  tests cover troop and crown hits. This does not certify flight trajectories.
- The paired Arrows probe records both seats over 60 ticks on CPU and MPS.
  Reports match exactly across devices. Native applies approximately 28.8 crown
  damage on tick 1 with no surviving projectile; scalar creates 30 projectiles
  in three groups of ten and applies 25 damage on ticks 20, 24, and 29 in this
  fixture. Scalar total is 75. Arrows remains defective and is not repaired by
  the single-projectile payload change.
- Artifacts: hog26_arrows_scalar_lifecycle_cpu_20260909.json and
  hog26_arrows_scalar_lifecycle_mps_20260909.json. The probe freezes other scalar
  entities and updates only spell projectiles; it is an isolated lifecycle
  comparison, not a complete-game simulator certificate.
- Independent source audit identifies required cast-time RNG consumption,
  per-wave shared stable-entity hit ledgers, delayed launches, and integer flight
  geometry. The simple runtime has no existing RNG owner. A locally seeded
  substitute would not establish scalar RNG-stream parity.
- Existing corpora remain historical data under old physics. Source authority
  remains stale by design; collection, fitting, and independent evaluation stay
  closed pending lifecycle repair and fresh protocol certification.

Parallel lifecycle and RNG audits, 2026-09-09:
- Poison differential reports reproduce shared native ticks at 20, 40, ...,
  160 versus scalar target-local ticks at 25, 45, ..., 165. A target leaving
  immediately after the first scan takes 92 lingering scalar damage and zero
  native damage. CPU/MPS reports match across all 360 recorded rows and source
  hashes were verified. Existing scalar and native tests encode contradictory
  contracts; passing the native periodic-area test does not resolve this defect.
- Artifacts: probe_hog26_poison_scalar_lifecycle_20260909.py and paired
  hog26_poison_scalar_lifecycle_{cpu,mps}_20260909.json. These isolate scalar
  target-buff/area updates and synthetic native stationary targets.
- Stock TensorPythonRandom construction fails on MPS float64 Gaussian storage.
  A diagnostic-only uncached Gaussian placeholder exposes a separate first
  twist divergence in 623 of 624 words. Initial copied words match. CPU matches
  30 scalar randrange(359) draws and final Python state. The underlying MPS
  expression defect remains undiagnosed. Root reproduced the independent audit.
- Artifact: hog26_arrows_rng_integration_audit_20260909.json. Use supplied
  CPU exact RNG state for the initial Arrows correctness integration, with
  explicit per-row reset/fanout ownership and measured cast-time transfers.
  Opening-deal generation remains separate. Shared state ingress and consumer
  ordering still require proof before claiming whole-game scalar RNG parity.
- Single-projectile payload correction and Arrows traces committed as 46ec189e.
  Arrows and Poison repairs remain required. No training or evaluation resumed.

Live scalar scheduler correction, 2026-09-09:
- Inspecting BattleState.step and running an instrumented full step corrected
  two assumptions drawn from isolated component fixtures. Live scalar projectile
  updates resolve immediately in object-ID order; the old Arrows diagnostic
  explicitly enabled deferred impact mode. Its stationary damage trace remains
  useful, but it does not prove the live scheduler's simultaneous-hit contract.
- Scalar periodic target damage runs in update_buff_component after combat and
  movement, before area-object scans. A proposed native pre-combat damage hook
  and its synthetic lethal-hit test encoded the wrong ordering. That change
  was caught during review before commit and must not be treated as accepted.
- The new probe calls actual BattleState.step without replacing its scheduler
  or enabling deferred mode. Arrows tower hits occur on ticks 20, 24, and 29
  with deferred mode false; Poison damage occurs inside update_buff_component
  on tick 25. The trace records component dispatch and source hashes.
- Artifacts: probe_hog26_scalar_frame_contract_20260909.py and
  hog26_scalar_frame_contract_20260909.json. Direct spell.cast is used before
  stepping, so this does not establish queued action-ingress timing parity.
- Arrows runtime integration must preserve live object ordering across ordinary
  and grouped projectiles. A bulk shared pre-damage collection contract would
  be incorrect. Cast RNG/geometry and standalone pool commits remain bounded
  component evidence, not full-battle acceptance.

Poison lifecycle repair and cross-phase rejection, 2026-09-09:
- Attached Poison damage now has independent source/target clocks, captured
  damage, duration refresh, lingering hits, stable-ID protection, and reserved
  source slots. Reset/fanout and every relevant allocation path preserve or
  clear the new ledger. Scans use scalar hitbox overlap.
- Final validation: 23 new CPU/MPS lifecycle/ownership tests passed; 57 affected
  regression tests passed with 29 CUDA skips. Both repaired stationary/exit
  reports agree on all 360 trace rows; root verified source hashes. Additional
  storage is 1,067,456 bytes per battle plus equal reset templates at standard
  128-entity capacities. No collector throughput claim follows.
- Whole-frame parity still fails. Actual scalar and native steps with a
  one-point shield, direct Knight damage 202, and attached Poison damage 92
  leave target HP 1908 versus 1798. Scalar direct damage breaks the shield
  before the buff; native queues the direct hit until after the buff. Both
  shields end at zero. This is a required cross-phase repair, not a tolerated
  acceptance exception. Paired mixed-hit reports explicitly reject parity.
- Added repaired lifecycle reports and the reproducible
  probe_hog26_poison_mixed_direct_hit_20260909.py with CPU/MPS reports. The old
  mismatch reports remain historical evidence. Source authority now includes
  the changed mechanic modules and scalar scheduler references; stored protocol
  hashes remain deliberately stale and collection/fitting remain closed.
- The alternative scalar collection route is feasible but not ready. A root
  actor-only probe using the frozen checkpoint builder exposes all 30 Arrows
  members before stepping, including 20 delayed launches, and encodes all as
  token 1 (<unknown>). See hog26_scalar_actor_ingress_audit_20260909.json.
  Existing scalar collectors also require reviewed public-mask and observation
  handling. Do not substitute them merely because their physics is canonical.

Scalar reference route selected for further verification, 2026-09-09:
- Independent review confirms native ordinary_troop_phase moves before testing
  attack reach at post-movement positions. Scalar combat is sequential at
  starting positions and exposes damage/status/death to later actors. A late
  DIRECT-only effect pass would repair one shield example while retaining the
  wrong frame graph. Further local native phase patches are paused; its lineage
  remains unaccepted. The original model objective, split roles and gates stand.
- Added scalar appearance receipt bindings for serialized Arrows projectiles,
  delayed-member exclusion, explicit visibility, and unresolved-effect rejection.
  Added a separate fixed-capacity body/effect actor projection with positions,
  HP/shield and static body metadata; no general entity-row builder, critic,
  runtime source-name inference, targets, damage clocks or future payloads.
- Nine tests passed, including both seats, launch eligibility, typed identities,
  private-state perturbation invariance, unresolved effects and capacity failure.
  This is Arrows-only effect coverage and a partial body feature contract; full
  visible status/animation coverage and presentation-boundary verification remain.
- A single scripted boundary successfully ran through the frozen policy using
  public-mask-v2 with all critic inputs absent and zero previous reward. Both
  seats saw 16 entities (six towers plus ten eligible arrows) and selected NO_OP.
  This proves interface compatibility only. The smoke used existing exact actor
  confidence; confidence for omitted features must be finalized with the new
  observation contract before accepting a collector. No game corpus was built.
- Artifact: hog26_scalar_public_policy_boundary_20260909.json. Next verify the
  full public appearance registry and observation confidence, then deterministic
  paired complete-game scalar replay under a distinct source/data authority.
  Old training/evaluation data are unchanged; collection/fitting stay closed.

Scalar availability and spell appearance coverage, 2026-09-09:
- Added scalar_policy_inputs: only provided position/type/body-stat features
  receive confidence. Omitted body state and projectile combat fields remain
  unknown. Reward feedback is fixed at zero; no critic inputs are accepted.
  Public-mask-v2 is computed from the five public actor tensors only.
- Added an executable frozen-policy boundary probe. Two independently
  initialized calls match actions and recurrent tensors exactly, with all
  critic fields absent. Input, recurrent, checkpoint, and source hashes are
  recorded in hog26_scalar_policy_availability_boundary_20260909.json. This
  supersedes the old all-features-exact smoke for interface confidence only;
  it is not full-game replay or actor-view acceptance.
- Expanded explicit cast appearance rules to Fireball, Giant Snowball, Rocket,
  Log, Barbarian Barrel, Goblin Barrel and Poison. All identities exist in the
  unchanged 494-token vocabulary. Pending carriers/rollers stay excluded, and
  unresolved visible effects still fail closed. Actual cast lifecycles were
  tested from both seats.
- 26 focused tests passed across appearance, core projection and confidence,
  including invariance of one seat's fixed rows/padding when only the other
  seat's visible effect count changes. Ruff/diff checks pass.
- Ordinary attack and tower projectile receipt binding is the next coverage
  requirement. No complete-game corpus or optimizer work has started. A new
  scalar source/data protocol still must be frozen before collection or fitting.

Scalar creation receipts and episode control, 2026-09-09:
- Musketeer/Cannon ordinary shot descriptors now bind actual creation receipts
  at the pre-call next entity ID. Scoped per-source wrappers preserve 80 real
  instrumented/control frames and RNG state; unknown synchronous children do
  not inherit a binding. Methods restore on normal/error exit.
- Initial tower receipts use a separate outcome vocabulary: serialized
  projectile:TowerPrincessProjectile at 494 and public_tower_shot:king at 495.
  The latter explicitly identifies a publicly observed launch origin, not a
  guessed asset. Source instance, location, owner, slot, payload and visibility
  are revalidated. 140-frame controls exercise all six towers without changing
  physics or RNG. The original policy vocabulary and weights remain unchanged.
- scalar_policy_inputs accepts only declared extra effect categories. It keeps
  outcome actor arrays intact, maps extra identities to policy <unknown>, and
  assigns zero identity confidence while retaining observed position/type.
  Actual tower projection tests cover that boundary; unknown raw identities
  outside the declared combined vocabulary still reject.
- ScalarSpellReceiptRecorder wraps actual registered spell instance calls from
  the original pending scheduler. It does not manually advance casting or copy
  scheduler logic. Eight spell rules, both seats and 90 frames each match
  control snapshots, pending queues and RNG. Unrelated battles delegate through
  unchanged; overlapping instrumentation rejects and methods restore on errors.
- ScalarReferenceEpisode preserves explicitly supplied canonical opening decks,
  separates battle RNG from learner-relative action-order RNG, requires a
  supplied public action mask, computes no reward, and never auto-resets.
  This is a new declared diagnostic scenario contract, not native seed parity.
- 40 combined receipt, tower, spell, policy-boundary and episode-control tests
  passed. Complete-game replay assembly is next; these component checks do not
  certify full actor-view coverage or authorize a training corpus.

Complete scalar replay baseline, 2026-09-09:
- Assembled the real queued-cast/tower/ordinary receipt paths, explicit openings,
  public-mask-v2, frozen recurrent policy, and existing public balanced strategy.
  Two seat-specific games for one paired diagnostic seed were each repeated;
  actor/input/action/recurrent traces, final RNG states and terminal results
  match exactly. Repeats are not independent games or acceptance evidence.
- Assembly caught Skeletons' distinct serialized body name Skeleton, now used
  by the projection. Ordinary source discovery now excludes projectile objects
  that retain their source card's stats. Receipt contexts clean up on failures.
- Before the resource precision repair, games ended naturally at ticks 5787
  and 5537 with learner losses. Learner attempts were 51/49 with zero rejects;
  opponents had 38 rejects each. All rejected attempts reconstruct as floating
  elixir deficits of 1.33e-15 through 9.18e-14, rather than placement failures.
  Example: Fireball at tick 280 had 3.9999999999999942 elixir for cost 4.
- Artifact: hog26_scalar_complete_replay_audited_20260909.json, with broad
  Python source fingerprints, card/vocabulary/checkpoint hashes, action-card
  diagnostics, exact W/D/L and normalized terminal tower margins. No training
  corpus or independent evaluation cohort was opened or written.

Scalar elixir roundoff repair and fresh replays, 2026-09-09:
- Card affordability now admits only roundoff deficits up to 1e-9 elixir;
  spending clamps negative roundoff balances to zero. A real 1e-7 deficit still
  rejects. Six focused tests cover exact/adjacent-float balances and 6000 ticks
  of rational-reference regeneration/spending across all three rate phases.
  Twelve resource/episode regression tests passed; nine projection/episode
  checks also passed. Player.py's eight legacy import/typing lint findings
  were verified identical in HEAD; changed/new diagnostic files pass Ruff.
- Fresh paired/repeated complete games terminate at ticks 4135 and 4569, with
  exact trace/RNG/terminal agreement between repeats and zero rejected attempts
  for either player. These two diagnostic trajectories are learner wins with
  normalized margins 0.2093704245973646 and 0.41242679355783307. Outcome reversal
  after the numeric fix is not a skill estimate or a tuning criterion.
- Artifact: hog26_scalar_complete_replay_elixir_fixed_20260909.json. Root
  verified its recorded source hashes against current bytes. Baseline resource
  behavior and audited loss traces are preserved separately at commit 7ff139f9.
- In-memory runs took roughly six seconds per sparse Hog matchup. This is not
  broad-deck collector throughput evidence; no training corpus was serialized.
  Next expand and audit the declared training-family appearance coverage, then
  freeze the distinct scalar collection authority before any fitting. Public
  calibration and counterfactual ranking remain entirely unaccepted.

Declared training-family coverage expansion, 2026-09-09:
- Audited only the 32 training decks in families 000--007 plus the fixed learner.
  Their union contains 63 card types. Actual deployments, 200 scalar ticks and
  synthetic parent deaths exercised 57 body types with zero unresolved body
  tokens. This one-seat mechanism probe is not full-match/visibility coverage.
- Added all 13 additional common ordinary projectile identities, including
  setup-compiled LavaPups/SpearGoblin spawn-body routes. Live source body and
  projectile authority are revalidated; special routes remain rejected.
- Spell receipts now cover all 13 unique spell objects in the training manifest,
  including BarbarianBarrel aliasing, Earthquake, Freeze, Tornado and Graveyard.
  Zap has an explicitly verified zero-persistent-entity path; no sprite is
  invented. Synchronous children remain unresolved rather than inheriting Zap.
- Corrected two API assumptions: Graveyard requires the serialized object
  registry used by load_dynamic_spells, not CardDefinition objects passed as its
  second factory argument. Zap's False result can mean a valid cast hit nothing;
  queue execution ignores that return and receipt recording must preserve it.
- 136 combined body/spell/ordinary/tower tests passed; Ruff and diff checks pass.
  Artifacts: hog26_scalar_train_body_coverage_verified_20260909.json and the
  earlier candidate inventory hog26_scalar_train_projectile_coverage_20260909.json.
  The inventory's candidate labels precede the newly completed receipt tests.
- Remaining special creation coverage includes Princess decoration/combat
  selection, Firecracker children, rolling/piercing shots and chain lightning.
  Their presence will not be bypassed or used to shrink the declared families.
  No training corpus, calibration cohort or final evaluation data was opened.

Scalar special effects and death appearance review, 2026-09-09:
- Real lifecycle receipts now cover Bowler/MagicArcher/Wallbreakers, Princess
  combat shots, Firecracker carrier/children, Electro Dragon/Spirit chains and
  the five declared death-effect families. Their component controls preserve
  scalar physics/RNG; they do not establish complete-family collector coverage.
- A chain receives only an explicit current chain-bolt category, not a guessed
  asset or private source-family identity. Timed bombs keep current serialized
  body identities in the noncombat effect group. Only exact registered internal
  Lumberjack container references are excluded; bottle rendering is uncertified.
- Review reproduced stale death authority after registration: changing an
  IceGolem death payload to Poison could publish the old IceGolem appearance.
  Emission and delayed-container guards now reject changed payloads before
  creating mislabeled effects. No rollback of prior source damage is claimed.
- Policy input accepts only the exact new chain/SkeletonContainer category
  exceptions. Extra identities remain outcome-only and map to unknown identity
  with zero identity confidence for the frozen policy; body/effect conflicts
  reject. A shared diagnostic extension registry is being integrated next.
- 206 combined actor, policy-input, common/tower/spell and special/death tests
  passed. Changed component files pass Ruff and diff checks. The new birth/death
  inventory records effect labels as diagnostic provenance only; its 63-card,
  57-body, zero-unresolved-body result remains a synthetic mechanism fixture.
- Full-game integration across the unchanged training families remains open.
  Collection authority is not frozen, and fitting/calibration/ranking remain
  closed. No holdout outcome data was read or new training corpus collected.

Integrated scalar training-family diagnostic, 2026-09-09:
- Unified lifetime recorder keeps source, Firecracker child and delayed death
  container hooks alive through episode exit. Five focused session tests and
  four episode tests pass; the diagnostic outcome extension assigns tower shots
  to 494/495, current chain category to 496 and SkeletonContainerNew to 497.
- First integrated training deck completed both seats at ticks 3790/4026 with
  exact repeats and zero rejected actions. The subsequent unchanged full run
  covered all 32 training decks, 64 distinct seat scenarios and 128 executions.
  Every scenario reached a natural terminal and repeated exactly. These are
  32 paired deck clusters, not 128 independent games.
- Independent audit verified all recorded Python bytes, the complete matching
  source file set, manifest, checkpoint, card data and vocabulary after the run.
  Raw report is 45,437,411 bytes with SHA-256
  6d70feff5c9adaafb700e2a3e346369b3a1cd0e27ad6bc71b830abbad8805df7.
  The raw report remains a local diagnostic artifact; its compact audit is
  hog26_scalar_training_family_all_decks_audit_20260909.json.
- 27 distinct effect tokens appeared at sampled decision boundaries. This
  does not prove coverage of every transient effect or complete rendering.
  No visible unbound effect caused a recorder/projection failure in this run.
- Six action rejections remain: deck index13, learner seat1, absolute seat0
  Musketeer action1368 at ticks1008 through1048 in increments of8. Exact-repeat
  status does not imply public-mask acceptance. Separate mechanism review found
  timed bombs block scalar placement but the public mask ignores effect rows;
  the six replay failures are being independently diagnosed before repair.
- Fixed manifest openings and a balanced opponent are diagnostic scope only.
  The new collection authority must independently freeze seeded canonical-name
  openings, role-local RNG streams, all existing family roles/budgets and gates.
  Do not silently relabel the native int64-ID seeded-opening protocol or count
  repeat executions as independent training games. No new corpus or fitting.

Scalar public timed-body placement correction, 2026-09-09:
- Independent replay reproduced all six deck13 failures with exact original
  actor/input/recurrent/action/terminal/RNG traces. Each had an affordable card,
  valid arena position, no ordinary building occupancy, and positive deployment
  payload occupancy: live TimedExplosive83 lay exactly at the requested center.
  This was not another elixir failure. The diagnosis is preserved separately in
  hog26_scalar_rejected_action_diagnosis_20260909.json; its internal fields are
  diagnostic evidence only, never actor or mask inputs.
- Added scalar-only public placement refinement from registered current bomb
  token/center/visibility and setup-frozen serialized radii. It uses inclusive
  scalar circle/circle and circle/placement-square geometry and removes only
  non-spell placement actions. Bombs keep effect feature7, not combat-building
  features. SkeletonContainer497 remains available to the public mask before
  the frozen policy receives unknown identity with zero identity confidence.
- The refinement has its own semantics digest, distinct from base public-mask
  tables. Replay outputs now record that actual digest, and the diagnostic
  driver rechecks both source file set and resource digests at completion.
- 45 focused payload-mask/policy/session/death-adapter tests pass. Targeted
  deck13 both-seat replays terminate at tick3600, repeat exactly, and now have
  zero rejected actions with unchanged source/resources. Refined digest:
  e65ad67bc3360c29775dcded7c07a508da48c55acd1065fcefe74cd2ec5e8e70.
- Full 32-deck recertification under this source is running separately; no
  training, opening-protocol approval or calibrated-model acceptance follows
  from the targeted repair. The preceding baseline remains preserved.

Completed timed-body mask recertification, 2026-09-09:
- All 32 training decks, both seats, completed and reproduced exactly under
  bc28e9c3: 64 distinct scenarios, 128 executions, 32 paired deck clusters.
  Rejected plays fell from six to zero. Only deck13 learner-seat1 changed its
  action sequence relative to the baseline; the other 63 sequences match.
- Independent completion audit verified source contents and file inventory,
  manifest, checkpoint, card-data and vocabulary digests. All runs recorded
  refined mask digest e65ad67bc3360c29775dcded7c07a508da48c55acd1065fcefe74cd2ec5e8e70.
  Compact artifact: hog26_scalar_training_family_payload_mask_all_decks_audit_20260909.json.
  Raw local report is 45,659,311 bytes, SHA-256
  37ef45b575c5e9f6f77149ff63c156520e60d9ae5504958eaef153646a3a6543.
- This is fixed-opening, balanced-style diagnostic coverage. Zero observed
  rejects is not a universal gate: simultaneous requests can change occupancy
  before the second action, without either actor seeing the other request.
  Future corpus audit must distinguish that concurrency from mask defects.
- Canonicalizing all 65 predefined manifest decks found 65 distinct card sets,
  with no duplicate alias groups. No held-out outcome data was accessed.
- Next authority proposals remain isolated, not active collection code:
  /tmp/hog26_scalar_opening_proposal/ contains canonical-name schedules and
  independent reconstruction tests (15 passed). Four SHA-derived streams cover
  opening, battle, action order and opponent; paired seats/repeats share identity.
  /tmp/hog26_scalar_rng_proposal/ contains an owned-RNG public random-opponent
  sampler and optional explicit action-order seed patch (13 tests passed).
  Neither proposal changes current controller behavior or authorizes collection.
- Next: integrate/review these proposals, freeze role-specific canonical
  scenario manifests and source/data/runtime authority, independently audit
  openings and RNG consumption, and build/audit complete-game retention before
  collecting the unchanged training quotas. Existing selection/calibration/final
  family roles and every acceptance gate remain unchanged. No new model fitted.

Seeded scalar openings and reserved-card preparation, 2026-09-11:
- Integrated canonical-name opening algorithm v1, distinct from native
  seeded-ordered-decks-v1. Campaign and derived seeds serialize as decimal text;
  canonical inventory is part of authority. Returned metadata cannot mutate
  the stored authority. Opening, battle, action-order and opponent streams are
  independently domain-separated. Paired seats/repeats retain shared identity.
- Independent production auditor imports no producer helpers, reconstructs
  Fisher-Yates deals and all stream/identity hashes, requires caller-pinned
  authority, and rejects unknown schema/version or self-consistent role changes.
  The episode controller accepts an explicit independent action-order seed while
  preserving its earlier default. Random opponents draw only for the actual
  opponent from public masks and own RNG state.
- Reserved RHogs AQ2.9 metadata adds ArcherQueen, RoyalDelivery and RoyalHogs
  beyond the procedural card union. Synthetic fixtures add AQ projectile token265
  and verify RoyalHog body459. A genuine ability-mask gap required current public
  deployment Boolean12 plus availability; remaining timer13 stays unavailable.
  Both-seat AQ pending/ready/cast-pending mask checks match the scalar test oracle.
- RoyalDelivery emits a stationary scheduler then a recruit, with no modeled
  falling trajectory. The session separately registers exact scheduler refs,
  validates recruit body identity, and records flight as explicitly unavailable.
  It never substitutes a target-position sprite. This is not rendering parity.
  No reserved evaluation games or outcomes were opened.
- Replay source fingerprints now cover every Python file under src/clasher and
  scripts; the former scalar-name filter omitted shared public_effect_probe.py.
  Earlier diagnostics remain scoped evidence under their recorded source lists,
  not complete dependency authority for future collection.
- 324 scalar tests passed; scalar scripts/tests pass Ruff and diff checks.
  Fresh diagnostic seed1279211: training deck13, balanced/random, paired seats,
  two exact executions each. Four distinct seat scenarios/eight executions
  completed at ticks3600/4592/3600/3600 with zero rejected card actions. All full
  initial decks and five public hand/next-card tokens match reconstruction;
  process-global Python/NumPy/Torch RNG state is unchanged by each game.
- All380 recorded Python sources and resource authority stayed unchanged.
  Compact artifact: hog26_scalar_seeded_replay_audit_20260911.json. Raw local
  report SHA-25630d346828e51905afd0e960340dcedadb21065a280ab18c1573bf0daca3dc0e8.
- Collection remains closed. Still required: full role-specific scalar protocol
  and scenario manifests, controlled true-terminal draw checks, complete-game
  corpus retention/auditing, and broader seeded/style diagnostics under the new
  deployment feature. Preserve all existing training/selection/calibration/final
  roles, budgets and gates. No new outcome model or policy has been fitted.

Fresh scalar pilot authorized and started, 2026-09-11:
- User approved a small fresh-data comparison, beginning with the planned384
  natural training games. The frozen plan preserves families000--007,32decks,
  six styles and paired seats;192relative scenarios. Fresh campaign seeds are
  1279221/1279222/1279223. No reserved selection/calibration/final role is opened.
- New per-game corpus writer retains every learner decision, including no-op
  and failed requests, with outcome/public identities and separate policy
  identity confidence. Metadata/provenance and future labels are separate from
  public feature arrays. Atomic exclusive NPZ publication occurs only after
  actual terminal, source/RNG/opening checks; independent validation checks
  shapes, complete boundaries, vocabularies, confidences, masks and labels.
- Corrected a diagnostic label mismatch BEFORE new fitting data publication:
  training margin remains the established mean of three own towerHP fractions
  minus mean of three enemy fractions. Prior scalar diagnostic total-HP-weighted
  margins remain historical; no thresholds or old reports were rewritten.
- Mirrored frozen-policy informal probes at seeds1279231/1279232 yielded seat0
  wins at tick3068, not draws. No symmetry fix or forced draw label was applied.
  A separate no-op control reached a genuine draw at tick6000,750rows,zero margin;
  this verifies the terminal label path and is explicitly excluded from fitting.
  Natural pilot draw coverage may be absent; final WDL acceptance remains gated.
- Two excluded12-game preflights covered all six styles and both seats. Final
  version retained5634decisions with zero rejected card requests. Completed
  directory resume revalidated all hashes and recollected/rewrote no games.
  Per-output OS lock prevents concurrent collectors; --resume preserves each
  existing atomic game only after exact metadata/hash/audit revalidation.
-366scalar tests and scoped Ruff passed. Frozen source authority:
  786d1095fdb266a28bd62386c96560c03c9795616efb4ec9a11c8816c349decb.
  Plan digest367979e32c9c6b055f34f2fddf148ef7ae1ca3a309c1b8d9008391da99981a4a.
  Authority covers383Python sources plus checkpoint/carddata/manifest/protocol
  and runtime. Do not edit any src/clasher or scripts Python while collecting.
- Frozen artifacts: hog26_scalar_pilot_frozen_plan_20260911.json and
  hog26_scalar_pilot_preflight_pin_20260911.json. Comparison specifications are
  fixed separately in hog26_scalar_pilot_comparison_plan_20260911.json, pinned
  as preflight evidence. Models remain untrained; no partial-pilot fitting.
- Collection started via root session55408, with verified committed games.
  Output datasets/derived/hog26_scalar_pilot_seed1279221_20260911/;
  log reports/hog26_scalar_pilot_seed1279221_20260911.log. Resume only after
  verifying that original handle/process is terminal or missing, using the same
  command and output with --resume. A polling timeout is not a stopped collector.
- Completion requires all384games and independent full-corpus audit before
  fitting. Model code/synthetic memory checks may be prepared outside the
  source-frozen tree; /tmp/hog26_scalar_pilot_models/ is owned by comparison agent.
- Model preparation subsequently finished outside the source tree:
  scalar_models.py, test_scalar_models.py and benchmark.py in that /tmp directory.
  Eight tests passed; synthetic fullgame2x750x128 forward/backward/AdamW onCPU
  thread1 took1.183seconds and peaked at1,337,999,360bytesRSS. Globals2339params;
  entity/history116900params with498tokens. No real corpus read or fitting.
  Retain synthetic_fullgame_benchmark.json as the predeclared memory prerequisite.

Whole-pilot alias rejection and corrective collection, 2026-09-11:
- First pilot completed384games/154259rows. Independent pre-fitting audit then
  rejected its first game: IceGolem became unknown hand token1. The collector's
  initial-hand check had reused the same defective generic builder resolver,
  so self-consistency and zero rejected actions did not establish valid hands.
- Exhaustive metadata audit found13affected canonical aliases: Archers,Bandit,
  BarbarianBarrel,DartGoblin,GiantSnowball,Guards,IceGolem,IceSpirit,Lumberjack,
  MagicArcher,NightWitch,RoyalGhost,SkeletonBarrel. Correct typed action IDs were
  present; the scalar hand path failed to use the typed alias registry. Unknown
  tokens made these cards unselectable, affecting trajectories and outcomes.
  Do not relabel/filter old rows as a repair. No model fitting had started.
- Old pilot remains quarantined at seed1279221 directory; machine-readable
  rejection: hog26_scalar_pilot_hand_alias_rejection_20260911.json. The failed
  globals startup log is preserved; no fitting manifest/checkpoint was produced.
- Added immutable setup-compiled ScalarHandLookup, required explicitly by actor
  projection/adapters. None remains0; unknown nonempty cards fail closed. Tests
  cover all8deck positions and24play/refill cycles for every configured deck,
  including aliases returning from the back of the cycle. All64configured names
  plus reserved3 resolve correctly; independent table audit confirms67cost/kind/
  playability/deployment entries. Scalar action execution uses actual hand names.
- Collector now validates every configured card before games; initial expected
  hands use typed vocabulary resolution. The independent corpus validator also
  rejects unknown/out-of-range/non-card hand tokens.373scalar tests passed.
- Corrective excluded preflight:12games/4941rows, all six styles/both seats,
  no unresolved hands or rejected card actions. Resume revalidated unchanged
  game hashes. Fresh no-op control reaches actual draw tick6000/750rows/margin0.
- New fixed384-game campaign seeds1279261/1279262/1279263 preserve every family,
  style, seat quota and future acceptance gate. Source authority:
  4da97f384ac4f3615e310f987f8c9bdeacbb499c340f5b9ee2c31fe61f037ffa.
  Plan digest9f5cb170209be952dae38e9238709455d169178cf8f73039ff5099ea7bc282fe.
  Frozen files hog26_scalar_handfixed_{frozen_plan,preflight_pin}_20260911.json.
- Corrective collector started root session71951; output
  datasets/derived/hog26_scalar_pilot_seed1279261_20260911/ and log
  reports/hog26_scalar_pilot_seed1279261_20260911.log. Source is frozen again.
  Resume only after verifying original process terminal/missing, with same plan,
  pin, output and --resume. No fitting until complete independent audit passes.
- Comparison implementation is prepared in experiments/hog26_scalar_pilot/,
  outside the collection source inventory. Original model specs/epochs/folds
  remain unchanged. Full audit checks exact metadata, pinned sources/resources,
  vocab/mask, actual initial hand, learner seat and all record labels/counters.
  Tree weight scale explicitly preserves the reference mean-one fitting-row
  convention; no performance result was used to choose it. Additive fitting code
  has separate source authority. No reserved outcome data was read.

Spell primary-birth correction, 2026-09-11:
- Corrective hand-fixed pilot stopped with exit 1 after 60 complete games and
  24,183 rows. Schedule 30, learner seat 0, tick 3348 failed when Zap killed
  IceGolem entity 345 and its death created FreezeIceGolemite AreaEffect 375.
  The spell recorder incorrectly adopted every entity born during a cast.
- Commit d9f2e695 observes only each audited spell's direct constructor through
  local function globals. Damage callbacks keep their original globals and
  independently owned children. Physics, spell scheduling and RNG are unchanged;
  unknown effects still fail projection. All 384 scalar tests passed.
- Exact failing game completed with 624 decisions at tick 4985. Independent
  original-recorder control bypassed only zero-entity receipt binding, with no
  physics or RNG overrides. Every result field except elapsed time matched,
  including decision traces, observations, actions, terminal and RNG digests.
  Evidence: hog26_scalar_zap_birth_comparison_20260911.json.
- Preserve the interrupted 60 games at the seed1279261 directory. They are not
  fitting data and will not be silently re-pinned to corrected source. Recollect
  the identical 384-game schedule in a separate directory after new preflight.
  No model fitting, reserved outcome access or acceptance-gate changes occurred.
- Birth-corrected preflight completed 12 games / 4,941 rows; explicit resume
  revalidated unchanged games. No-op control reached tick 6000 / 750 rows and
  genuine draw, excluded from fitting. First prior saved game also matches all
  19 decision arrays across 450 rows; this check does not cover the other 59.
- New source authority dd5ae1e3049a11fc819236ebed67e55970176faefeec6b9035501cda48b030c7.
  Plan digest 4adc5b90e4a945aacaf7e403326c2a214ce1c4a11f2d1236c7648287254806ff.
  Frozen plan/pin: hog26_scalar_birthfixed_{frozen_plan,preflight_pin}_20260911.json.
  Schedules and inherited requirements are exactly unchanged from handfixed plan.
- Collector launched root session 13368. Output directory:
  datasets/derived/hog26_scalar_birthfixed_pilot_seed1279261_20260911/.
  Log: reports/hog26_scalar_birthfixed_pilot_seed1279261_20260911.log.
  Do not edit src/clasher or scripts Python while this collector runs. Poll the
  same handle; observation timeout is not process exit. Resume only after actual
  exit or verified missing process, under the same source/plan/pin.
- Automatic comparison sequence started after user continuation, root session
  82945. Supervisor is outside frozen collection source at
  /Users/sam/Library/Application Support/ClasherMonitor/run_comparison_sequence.py.
  It holds an exclusive lock, waits for collector PID61703 and complete.json,
  then invokes the existing independently auditing runner for globals, tree,
  entity sequentially. Any nonzero exit or absent completion stops the sequence.
  No partial fitting or fitting-output reuse. Model output stems:
  reports/hog26_scalar_birthfixed_{globals,tree,entity}_comparison_20260911.
  Supervisor log: hog26_scalar_birthfixed_comparison_sequence_20260911.log.
  Live state: /Users/sam/Library/Application Support/ClasherMonitor/comparison-status.json.
  Scheduled 10-minute checks now inspect this supervisor before any fitting launch.
- Birth-corrected collection completed all 384 games / 154,811 rows across
  192 paired scenarios, with 80 wins / 0 draws / 304 losses and zero rejected
  card actions. Natural draw learning remains inconclusive; no controls added.
  Complete manifest SHA 74c745c8b42203f8cd83aa7aed19cb1ae8fb9ac9e57cf3b86c5790e745183911.
- Independent fitting-loader audit passed all 384 games and published its
  data audit in the globals fitting_manifest.json. Supervisor started globals
  PID95031; first fixed 30-epoch fold reached epoch30. This is fitting progress,
  not calibrated model acceptance. Sequential tree/entity and scheduled checks
  remain active; inspect supervisor state before launching anything else.
- Globals finished all 8 fits. Excluded-family all-state decisive AUC is
  0.76338 / 0.71023 across seeds; NLL gain +0.03382 / -0.01213. Probability
  improvement is not consistent across seeds; neither result is acceptance.
- Tree finished all 4 folds. Excluded-family all-state margin MAE 0.13867
  versus current-margin baseline 0.17733, gain +0.03865 (scenario-cluster
  95% interval +0.02096 to +0.05646). Early/middle improve, but late gain
  -0.00213 (interval -0.03256 to +0.02771); representative late gain -0.02023.
  Late coverage is only 18 games / 15 paired scenarios. Do not infer a passed
  phase gate or broad generalization from the overall improvement.
- Entity/history is active under PID7048; one fold complete and second fold
  epoch11 at scheduled check. Supervisor PID89457 remains sole sequence owner.
  No source or frozen comparison changes; no additional fits launched.
- The supervised comparison completed successfully: globals8/tree4/entity8
  fits. No collector or fitting process remained at completion review.
  Entity seed2 also failed excluded-family margin: MAE0.20761 versus baseline
  0.17733, NLL gain -0.21289. Seed1 MAE0.22122, NLL gain -0.22912. Strong
  early/middle training fits with worse excluded predictions support a
  generalization problem. No architecture or candidate is accepted.
- Consolidated completed metrics and source hashes are recorded in
  hog26_scalar_pilot_completed_comparison_review_20260911.json.
- Next experiment is a separately declared frozen-model fresh-seed diagnostic,
  not automatic expansion or refitting of the completed pilot. Exactly384games
  on the same32training decks/six styles/paired seats with seeds1279601/2/3.
  Compare every frozen fit on fresh seen families and fresh excluded families;
  this separates new-scenario failure from family transfer without changing
  training. Diagnostic labels can never become untouched acceptance evidence.
  Spec: hog26_seed_transfer_spec_20260911.json. Reserved roles/gates unchanged.
- Driver and auditor live outside the old source inventory in
  experiments/hog26_seed_transfer. Tests verify collector/auditor are unchanged
  copies except protocol import/root path, fresh role/seeds, exact quota,
  source mutation rejection and preserved decks/requirements. Three tests pass.
  Driver, evaluator, original implementation and all frozen model files become
  hashed resources in the new source authority. Original source bytes preserved.
- Fresh-seed diagnostic preflight passed 12games/4,941rows, zero rejected cards;
  explicit resume revalidated unchanged outputs. All original simulator/public
  projection source hashes match the completed birth-corrected pilot exactly.
  New source authority 2a41e9c2bc7eeb272e1c4cb941f65c8d88f9f6781c56c3897a60ee0942f6541a.
  New plan digest 84d163a01e9dbcb97b58e5fc4d9e46b29ed59037cc2867a788890457a78f60cb.
  Plan/pin: hog26_seed_transfer_{frozen_plan,preflight_pin}_20260911.json.
- Diagnostic collection plus inference-only evaluation supervisor launched root
  session47415, holding the same exclusive supervision lock as the prior sequence.
  Live state remains /Users/sam/Library/Application Support/ClasherMonitor/comparison-status.json.
  Output data: datasets/derived/hog26_seed_transfer_seed1279601_20260911/.
  Output evaluation: reports/hog26_seed_transfer_evaluation_20260911/.
  Sequence log: reports/hog26_seed_transfer_sequence_20260911.log.
  Collection log: reports/hog26_seed_transfer_collection_20260911.log.
  Evaluation independently audits the full corpus, then evaluates all20frozen fits.
  Do not change src/scripts, either experiment directory's Python, frozen models
  or pinned specs while the new sequence runs. Any failure stops the next stage.
- Existing persistent app goal remains usageLimited. Explicit create_goal attempt
  was rejected because the existing objective is unfinished; do not falsely mark
  it complete. Objective and continuation steps are in hog26_active_objective_20260911.md.
  Ten-minute scheduled checks were updated for the new diagnostic stage.

Completed fresh-seed review and next draft, 2026-09-12:
- Fresh diagnostic:384games/155496rows,86wins/0draws/298losses; all20frozen
  evaluations completed. Reverified every pinned resource and20report inventories
  with288fresh seen-family and96fresh excluded-family games per fit. No jobs live.
- Entity NLL gain is negative in all8fresh seen-family fits (-0.7054 to -0.0943)
  and all8excluded-family fits (-0.6734 to -0.0193): failure extends to new
  scenarios from trained families. Tree margin gain remains positive overall
  in all4fresh excluded folds (+0.0202 to +0.0931), but late coverage by fold is
  3/9/0/9games. No phase or model acceptance follows. Review with exact sources:
  hog26_seed_transfer_review_20260912.json.
- User-authorized backend goal clear/reset succeeded; get_goal independently
  verified active status. Earlier usageLimited notes are historical.
- Next concrete draft: hog26_data_scaling_draft_20260912.json. Add1152fresh
  training games to original384 for a1536-game comparison with unchanged models,
  epochs and folds. Diagnostic384 remains excluded from fitting and is already
  opened evidence. Implement collection, combined audit and resource checks,
  then freeze before launch. Draft collection_allowed/fitting_allowed are false.
  The scheduled prompt now advances this work instead of polling completed jobs.

Data-scaling memory prerequisite, 2026-09-12:
- No collection/evaluation processes were live; both prior experiments remain
  complete. The queued old monitoring prompt was stale; next stage is the
  separately declared1536-game scaling draft, with no new fitting started.
- Measured original384-game public arrays occupy5,362,033,796bytes; direct4x
  scaling would need21.45GB before model/reporting overhead on24GiB hardware.
  Compressed disk cost is small (31.7MB for original384); memory is the issue.
- Added storage-only compaction and variable-width batch reconstruction under
  experiments/hog26_data_scaling. Remove only trailing entity slots masked at
  every timestep AND zero in every entity field. Reject nonzero discarded
  storage. No timestep or visible entity is removed; original code is unchanged.
- Six focused tests pass. All384original games were hash-verified and checked
  in192paired batches: every reconstructed model tensor is bit-identical to
  the original batch builder. Public storage drops to926,991,522bytes, giving
  an estimated3.71GB for1536games; maximum observed width47, median20.
  Evidence: hog26_data_scaling_memory_20260912.json. This estimate is not a
  measured full1536-game training peak. Still integrate sequential audited
  compaction, combined-corpus isolation and source pinning before freeze/fitting.
- Implemented scaling_protocol.py, collect_scaling.py and scaling_dataset.py
  outside prior frozen directories. Exact new quota1152, combined1536, all
  original family/deck/style/seat allocations, three fresh scenarios per pairing.
  New clusters are disjoint from original training and opened diagnostic data.
  The preflight explicitly resets its diagnostic episode count to one.
- Combined auditing retains the original independent checks, adds384+1152game,
  192+576cluster, per-family and1152fit/384excluded counts, and rejects diagnostic
  overlap. It refuses a partial extension before reading original arrays.
  Eleven tests passed; Ruff clean. Existing simulator and model source unchanged.
- Full original384-game audit through the compact loader passed:154811rows,
 925133790retained public bytes, peakRSS1406369792bytes,5.57seconds. Evidence:
  hog26_scaling_compact_loader_20260912.json. This supports collection readiness;
  full1536-game training/tree peak remains a separate pre-fitting prerequisite.
- Scaling excluded preflight launched root session85897. Source is frozen for
  this run; no training has started. Next: confirm12-game completion and resume,
  then freeze the exact new collection plan/pin before launching1152games.
- Scaling preflight and resume passed12games/4941rows, zero rejected cards.
  Frozen source9de069399d79f7741e8087fc52ddd565b65eddfd20c2e8547de28652674008a4;
  plan4bca106e3eda28ebaa671041f6bae99eecee3c12ce61fd07eee68678c0fbbd43.
  Files: hog26_scaling_{frozen_plan,preflight_pin}_20260912.json. Collection-only
  readiness is separate from the remaining1536-game fitting memory/authority gate.
- Supervised1152-game collection launched root session66819. Data directory:
  datasets/derived/hog26_scaling_train_seed1279701_20260912/; collection log:
  reports/hog26_scaling_collection_20260912.log; supervisor log:
  reports/hog26_scaling_sequence_20260912.log. Live state in the common monitor
  comparison-status.json. No fitting is automatically launched on completion.
  Preserve all pinned Python/resources. Prepare fitting code in a separate new
  experiment directory while collecting, then verify combined audit/memory and
  freeze fitting inputs before execution. Scheduled prompt updated accordingly.
- While1152-game collection runs, fitting preparation now lives separately at
  experiments/hog26_scaling_fit. Original training/prediction function ASTs are
  unchanged; only compact batching is imported. Controlled synthetic globals
  and entity training produce bit-identical parameters after multiple updates.
- Installed sklearn1.7.2 uses float64 tree input. Added fitting-only direct
  float64 feature assembly and per-game prediction to avoid all-game float32
  storage plus indexing and conversion copies. Tests verify original feature
  values/order and no excluded-game feature access.10GiB matrix guard fails
  before allocation; no row reduction. Five preparation tests pass; Ruff clean.
- No new fitting launched. Remaining: executable comparison supervisor/runner,
  complete1536-game audit, actual memory checks and frozen fitting authority.
  Latest collection check:38/1152games,16710rows,zero rejected card actions.
- Prepared run_scaling_comparison.py in the separate fitting directory. It uses
  the complete1536-game loader, exact1152fit/384excluded fold counts, unchanged
  neural training functions and fitting-only float64 tree features. Metrics,
  original seeds and fixed epoch/iteration budgets remain unchanged.
- The runner requires a passed readiness record matching its Python inventory,
  frozen collection plan,1536-game audit and memory verification. Missing/false
  memory readiness refuses before corpus access or output creation. Seven
  preparation tests pass; Ruff clean. No real-data fitting launched.
- Remaining before execution: actual full-size memory audit, final combined
  corpus audit, matching readiness publication and supervisor. Collection is
  still active; do not change its pinned sources/resources.
- Synthetic memory check now exercises the exact scaling fit_entity route with
  two750-step games and128entities, full backpropagation and one optimizer step.
  All116900parameter gradients are finite; peakRSS1451671552bytes,1.193seconds.
  Source hashes/runtime recorded in hog26_scaling_neural_memory_20260912.json.
  No corpus rows were read or fitted. This verifies the maximal batch, not the
  full combined1536-game loader plus tree/neural training memory prerequisite.
- Collector remains healthy at112/1152games,46765decisions,zero rejected actions.
- Added check_full_memory.py outside collection source. It refuses partial data,
  audits complete1536games, retains their public arrays, and measures either
  the maximal synthetic neural batch or largest fitting-family tree matrix plus
  binning/one histogram iteration with deterministic artificial targets. No
  terminal outcomes enter probe targets and no candidate model is saved. Tree
  result is a preprocessing/one-iteration memory check, not a100-iteration fit.
- One memory-audit supervisor waits for collector PID46259 and complete.json:
  root session92460; log hog26_scaling_memory_sequence_20260912.log. Separate
  waiting lock prevents duplicates; after collection it acquires the shared
  experiment lock and runs neural/tree audits sequentially. External RSS guard
  terminates its own probe above18GiB. It never starts outcome fitting.
- Eight preparation tests pass; Ruff clean. Scheduled prompt now includes the
  waiting audit supervisor. After success, review matching data/source/runtime
  reports before publishing fitting readiness. No partial corpus fitting.
- Tightened scaling fitting readiness: the runner now verifies both underlying
  neural/tree memory report files and their SHA256s, exact source inventory,
  collection plan, runtime,1536-game/768cluster audit and measured RSS limits.
  A boolean readiness declaration alone no longer permits fitting. Neural
  evidence includes finite gradients/full750-step128entity batch; tree evidence
  includes the declared largest-fold preprocessing/one-iteration probe.
- Added publish_readiness.py to construct the readiness artifact only from
  matching completed reports. Seventeen fitting-preparation tests pass, including
  missing/mutated reports, wrong sources/runtime/data and exceeded memory limits.
  No readiness artifact was published and no outcome fit launched. Current
  collection and waiting audit supervisor remain the sole active experiment jobs.
  Do not edit scaling-fit Python once the post-collection memory probes start,
  since each probe pins the entire fitting implementation.
- Prepared post-scaling inference in experiments/hog26_scaling_eval, outside all
  active collection/memory source inventories. It retains the previous fresh-seed
  diagnostic distribution and all20scaled fits, reporting288fresh seen-family
  versus96fresh excluded-family games per fold. This remains opened diagnostic
  evidence; it cannot replace untouched acceptance data.
- The evaluator refuses before diagnostic access until globals/tree/entity are
  all complete, verifies shared1536-game fitting authority/source/vocabulary,
  pins checkpoints and its own code, and derives priors only from exact original
  384+new1152training manifests. One focused incomplete-fit refusal test passes;
  imports/CLI and Ruff pass. No scaled models exist yet, so prediction execution
  remains unverified until fitting completes. No collection source was edited.
- The1152-game extension completed with463338rows and zero rejected card actions.
  Independent full-corpus audits found1536games/618149rows/768paired clusters and
  zero diagnostic games in fitting. Neural full-batch backpropagation peaked at
  3950428160bytes RSS; the largest tree fold matrix, binning and one iteration
  peaked at9019834368bytes. Both passed the fixed18GiB cutoff with synthetic
  targets and no outcome model saved.
- Fitting readiness was published only after matching both memory-report hashes,
  the complete data audit, exact fitting-source inventory, collection-plan hash
  and runtime. Seventeen focused tests pass and Ruff is clean. Readiness:
  hog26_scaling_fitting_readiness_20260912.json.
- One locked supervisor launched the unchanged1536-game comparison, running
  globals, tree and entity sequentially with an external18GiB RSS guard. Globals
  is active; later stages start only after the previous complete.json exists.
  State: /Users/sam/Library/Application Support/ClasherMonitor/comparison-status.json.
  Supervisor log: hog26_scaling_fit_sequence_20260912.log. No duplicate fits.

- September 12 continuation moved to thread 01a09804-13c8-77f1-a297-cdea4701e0c5.
  Sam requested a persistent goal and continuous work. The goal is active for the
  actor-visible outcome model and preserved calibration/ranking protocol.
  The ten-minute scheduler and its deduplication check now target this thread;
  backups of both prior scheduler files are preserved. The fitting supervisor
  remains PID 30659 and was neither restarted nor duplicated.
- Globals completed all eight fits and the exact 30-file inventory audit passed.
  Review source is outside pinned fitting resources at
  experiments/hog26_scaling_review/review_completed.py. The current preliminary
  review is hog26_scaling_globals_preliminary_review_with_coverage_20260912.json.
  It supersedes the earlier preliminary review only by adding the existing
  eight-cluster/two-decisive-cluster coverage checks. Both artifacts are retained.
  Source and memory-report hashes match the readiness record.
- Globals out-of-fold pooled NLL gains are +0.14794955 and +0.15747944 across the
  two fixed seeds, but subgroup regressions remain. Nine of twelve late seat/style
  slices fall below an existing independent or decisive cluster coverage floor;
  four have no examples of one decisive outcome. Natural draws remain absent.
  These are diagnostic coverage comparisons, not acceptance evaluations.
  The full comparison review correctly refuses an incomplete tree stage before
  diagnostic access. Tree has completed three folds; entity remains queued.

- Prepared paired diagnostic review outside all pinned fit/evaluation source:
  experiments/hog26_scaling_review/{paired_errors,review_transfer}.py. It requires
  the completed three-model fitting review and all 20 completed original and
  scaled diagnostic evaluations before corpus access. It verifies exact output
  inventories, matching cohort audits and pinned model resources.
  Paired scenario-cluster intervals compare direct NLL, Brier and margin MAE
  changes on identical rows; prior gains remain separate because training priors
  differ. Every fold, seed and slice remains in the review. Other metric changes
  are point estimates only. Five synthetic tests pass, including zero change,
  sign reversal, and repeated-row invariance. Ruff passes. No diagnostic corpus
  was loaded for this preparation. Fixed epochs also increase optimizer updates
  with more games, so the comparison cannot isolate data from compute effects.

- Tree completed all four fixed fits and published complete.json. The supervisor
  recorded peak RSS 9,317,154,816 bytes, below 18 GiB, then launched entity PID
  75051. The latest preliminary completed-stage review is
  hog26_scaling_globals_tree_preliminary_review_20260912.json. Exact inventories
  passed for globals 30 files and tree 17 files. Shared training authority agrees;
  every prediction archive has the expected 618,149 rows, finite bounded margins,
  and valid probability mass. All source and review input hashes remained stable.
- Tree all-state margin gain is +0.04375419 overall with clustered 95 percent
  interval [0.03524417, 0.05137474], and +0.01866497 late with interval
  [0.00519808, 0.03244168]. Representative gain is +0.02973700 overall, but late
  representative gain is -0.00509034 with interval [-0.01575920, 0.00625456].
  Late coverage remains 80 games and 70 paired-scenario clusters. Bridge-pressure
  and family-007 margin gains are negative in both distributions. The fourth
  excluded fold has late representative gain -0.01752176. More data improves
  some forecasts but has not resolved required distribution/subgroup failures.
  No acceptance or diagnostic evaluation has been authorized by pooled gains.

- Entity seed 1279501 fold 0 completed in 1,464.73 seconds. Its preliminary
  single-fit review is hog26_scaling_entity_seed1279501_fold0_preliminary_review_20260912.json.
  All-state NLL is 0.21630 fitting versus 0.88790 excluded, with excluded NLL gain
  -0.32476 and decisive AUC 0.88317. Excluded margin gain is +0.04543 overall,
  but late representative gain is -0.06689 on only 10 games and 10 clusters,
  including two win-containing clusters. These are point estimates from one fit.
  The complete fixed eight-fit sequence continues without outcome-based changes.

- Entity seed 1279501 fold 1 completed in 1,365.70 seconds. Its preliminary
  single-fit review is hog26_scaling_entity_seed1279501_fold1_preliminary_review_20260912.json.
  All-state NLL is 0.19372 fitting versus 1.37018 excluded, with excluded NLL gain
  -0.75797 and decisive AUC 0.70792. Excluded margin gain is -0.01367 overall and
  -0.03469 late across all states; representative gains are -0.03444 overall and
  -0.05928 late. This second fold also shows a large fitting/generalization gap.
  Six fixed entity fits remain. No fitting settings or acceptance gates changed.

- Entity seed 1279501 fold 2 completed in 1,502.28 seconds. Preliminary review:
  hog26_scaling_entity_seed1279501_fold2_preliminary_review_20260912.json.
  Excluded all-state NLL gain is +0.03002 overall, but -0.30353 early. Late NLL
  appears strong on only five excluded games with no wins; decisive AUC is
  undefined. Excluded late margin gains are -0.05628 all-state and -0.10390
  representative. Overall representative margin gain is -0.02408. This fit
  illustrates why pooled scores cannot conceal phase regression or absent class
  coverage. Five fixed entity fits remain; the sequence is unchanged.

- Entity seed 1279501 fold 3 completed all 30 epochs. Preliminary review:
  hog26_scaling_entity_seed1279501_fold3_preliminary_review_20260912.json.
  All-state NLL is 0.15216 fitting versus 1.30073 excluded, with excluded NLL gain
  -0.70032. Excluded margin gains are -0.03760 overall and -0.08151 late across
  all states; representative gains are -0.07138 overall and -0.13296 late.
  The first seed's four fits are complete and clustered summary computation is
  active. The second seed's four fits remain. No early stopping or selection.

- Entity seed 1279501 published its complete out-of-fold summary. All five
  prediction archives for that seed passed row-count, finite-value, probability
  mass and margin-bound checks. Preliminary completed-seed review:
  hog26_scaling_entity_seed1279501_preliminary_review_20260912.json.
  All-state NLL gain is -0.54220 with clustered 95 percent interval
  [-0.75639, -0.34968]; all three phase NLL-gain intervals are below zero.
  All-state margin gain is -0.00120 overall, with interval spanning zero, but
  late gain is -0.04921 with interval [-0.08047, -0.01975]. Representative
  margin gain is -0.02734 overall and -0.09157 late, both with wholly negative
  intervals. This seed does not meet the model-quality requirements. Seed
  1279502 is running unchanged; full fitting review and fresh diagnostic remain
  pending. No candidate was selected or promoted.
- Paired diagnostic review now uses the same float64 log-loss precision as the
  published metric implementation and refuses if computed paired point changes
  disagree with the report differences. Six synthetic tests and Ruff pass.
  Actual paired diagnostic validation remains pending the completed evaluations.

- Entity seed 1279502 fold 0 completed in 1,474.22 seconds. Preliminary review:
  hog26_scaling_entity_seed1279502_fold0_preliminary_review_20260912.json.
  All-state NLL is 0.19954 fitting versus 1.00862 excluded, with excluded NLL gain
  -0.44548. Late margin gains are already negative on fitting games: -0.01591
  all-state and -0.04823 representative. Excluded late margin gains are -0.02821
  and -0.09055 respectively. WDL family generalization and late-margin fitting
  are therefore distinct problems to investigate; neither is resolved by pooled
  scores. Three fixed entity fits remain, with no settings changed.

- Read-only tower-input audit completed over all 1,536 fitted games and 618,149
  rows, verifying each archive hash against the entity fitting manifest. No
  terminal-label arrays or fresh diagnostic data were accessed. All six
  tower-health global confidences equal one, and the baseline from available
  inputs matches the recorded current-margin baseline exactly on every row.
  The model code passes those globals into the frame projection. Missing or
  confidence-masked tower health is ruled out on this fitted corpus; this does
  not identify the optimization cause. Report:
  hog26_scaling_tower_input_availability_audit_20260912.json.

- Read-only token-exposure audit verified all 1,536 training archive hashes and
  compared confidence-positive entity plus four-slot hand identities across the
  fixed family folds. Excluded games containing identities absent from fitting
  inputs total 220/384, 362/384, 363/384 and 326/384 for folds 0 through 3.
  Those folds have 6, 14, 14 and 16 such token IDs respectively. Report:
  hog26_scaling_token_exposure_audit_20260912.json. This establishes substantial
  identity covariate shift, not that learned identity embeddings cause the
  observed errors. No outcome labels or fresh diagnostic data were used.

- Existing public card-stat helpers were inspected without model changes.
  src/clasher/rl/card_semantics.py and StructuredObservationBuilder already
  provide semantic metadata; the current scalar outcome model instead uses
  learned token embeddings plus confidence-masked observations. Of the 50
  identities absent from fitting inputs in at least one fold, 28 resolve through
  the existing standalone semantic-card profile and 22 do not. Missing entries
  include projectiles, effects and spawned units. Availability is not a
  correctness or model-quality certificate. Any semantic redesign needs an
  explicit verified public-only mapping or missing-feature contract. Report:
  hog26_scaling_public_semantic_helper_coverage_20260912.json.

- Entity seed 1279502 fold 1 is complete. Preliminary review:
  hog26_scaling_entity_seed1279502_fold1_preliminary_review_20260912.json.
  All-state NLL is 0.23227 fitting versus 1.20943 excluded, with excluded NLL gain
  -0.59722. Excluded margin gains are -0.00324 overall and -0.02670 late across
  all states; representative gains are -0.02369 overall and -0.05957 late.
  The second seed therefore repeats failure on the second excluded-family pair.
  Six of eight entity fits are complete. Two remain before the full audit.

- Entity seed 1279502 fold 2 is complete. Preliminary review:
  hog26_scaling_entity_seed1279502_fold2_preliminary_review_20260912.json.
  Excluded all-state NLL gain is +0.10570 overall but -0.10275 early. The late
  slice again has only five games, all losses, so decisive AUC is undefined.
  Late margin gains are -0.06582 all-state and -0.11712 representative. Overall
  representative margin gain is -0.01989. Both seeds therefore reproduce the
  same phase/coverage failure on this family pair. One fixed entity fit remains.

- The additional paired diagnostic analysis is now frozen before scaled
  diagnostic predictions. Plan:
  hog26_scaling_paired_diagnostic_review_plan_20260912.json, SHA256
  c61755ee6682e2a61c455562be9d4a9df8b541ddab40b2eeaf2e9251423a6813.
  It pins all six Python files in experiments/hog26_scaling_review, direct
  float64 NLL/Brier/MAE reductions, 2,000 paired-cluster replicates and seed
  1279511, both distributions, all slices and 288/96 game groups. The inference
  supervisor and paired reviewer verify this source pin before access. Six
  synthetic tests and Ruff pass; incomplete fitting review still refuses before
  diagnostic access. Do not edit these analysis sources while this evaluation
  and review are outstanding without a separately documented revision.

- All 20 scaled fits and both entity summaries are complete. The supervisor
  stopped normally; entity peak RSS was 6,203,113,472 bytes. Fit-authority checking
  pinned 26 checkpoint/completion/manifest resources. Independent final review
  verified exact 30/17/30 artifact inventories, all prediction arrays, all
  distributions and slices, shared 1,536-game/618,149-row authority and source
  hashes. Completed review, written and interpreted before diagnostic access:
  hog26_scaling_completed_comparison_review_20260912.json.
- Entity all-state NLL gains are -0.54220 and -0.53414 across the two seeds;
  every phase in both distributions has a wholly negative NLL-gain interval.
  Late all-state margin gains are -0.04921 and -0.06091, and late representative
  gains are -0.09157 and -0.10326, all with wholly negative intervals. Every
  entity fitting fold also has negative late representative margin gain.
  WDL family generalization and late-margin fitting remain separate failures.
  Globals/tree findings and all coverage limitations remain as recorded. No
  candidate is accepted. Proceed only to the predeclared inference-only opened
  diagnostic, followed by the frozen paired review; no reserved data or policy work.

- The locked scaled fresh-seed evaluation launched after the finalized fitting
  review. Supervisor PID 88219; inference worker PID 88220. Both were verified
  live. The shared state pins fitting-review SHA256
  3235e254a4225e7a70bab96461dd4ef4893ec0afc1618a7c59423ab039844e22
  and the pre-prediction paired-review plan hash. Logs:
  hog26_scaling_seed_transfer_sequence_20260912.log and
  hog26_scaling_seed_transfer_evaluation_20260912.log. No fitting occurs in this
  stage. Scheduled continuations now describe the inference and paired-review
  steps; the prior scheduler file is preserved in a backup.

- All 20 scaled fresh-seed evaluations completed normally. Peak inference RSS
  was 8,787,623,936 bytes. The frozen paired review completed, validating exact
  42-file inventories for both evaluations, identical 384-game/155,496-row
  authority, all 288/96 groups and source pins. Every computed paired error
  change matched the published metric difference. Reports:
  hog26_scaling_seed_transfer_review_20260912.json and
  hog26_scaling_comparison_conclusion_20260912.json.
- On fresh seen-family games, entity overall margin error improved versus its
  original fits in all eight fits, with positive paired intervals in both
  distributions. Late margin gains still remain negative in all eight fits.
  Entity NLL gain is negative in every seen/excluded fit in both distributions;
  fresh seen-family early NLL-gain intervals are wholly negative for all eight
  fits. Failure is not confined to excluded families or sparse late examples.
- Globals retains positive overall NLL gain in all seen fits and seven of eight
  excluded fits; paired scaling gains are mixed and some late comparisons
  regress. Tree retains positive overall margin gain in every seen/excluded fit,
  but most paired scaling intervals cross zero and late representatives fail.
  The fresh diagnostic has only 21 late games, 16 clusters and one win-containing
  cluster. It cannot pass the required late coverage/calibration gates.
- The fixed comparison is closed with no accepted candidate. The next authorized
  training-only experiment will rebuild the margin component around an explicit
  current-margin residual and public numeric summaries, preserving the globals
  WDL reference. Freeze the exact model, feature contract, budgets, authority
  and memory evidence before fitting. No reserved outcomes or policy work.

- The new residual baseline is frozen in
  hog26_residual_margin_frozen_plan_20260912.json, SHA256
  43c7d690902812692a4b8cfbb56ee742ed851905bb7111421643826977002853.
  Code lives separately in experiments/hog26_residual_margin. It uses 425 public
  numeric features, two 32-unit GELU layers, 14,721 parameters and a zero-initialized
  linear margin residual. Hand columns preserve empty plus the eight declared
  Hog identities resolved through the existing alias-aware vocabulary. Counts
  are reversibly scaled by 128. No entity ID embedding, learned recurrence,
  time caps, epoch selection, class reweighting or WDL refitting is introduced.
- Fourteen focused tests and Ruff pass. The full-corpus memory audit passed
  1,536 games/618,149 rows and exact baseline initialization on every row.
  Feature matrix is 618,149 by 425 float32, 1,050,853,300 bytes, SHA256
  4b0e0b8e3a66ee46497adac492a7571cea3f625b8cf275cfc09199da933a5ccd.
  The maximal synthetic optimizer step had finite gradients. Peak RSS was
  5,370,068,992 bytes. No outcome model was saved by that probe.
- Matching readiness was published at hog26_residual_margin_readiness_20260912.json.
  One locked fitting supervisor launched: PID 15189, worker PID 15237, logs
  hog26_residual_margin_fit_sequence_20260912.log and
  hog26_residual_margin_fit_20260912.log. It runs all eight fixed fits with the
  original two seeds, four family folds, 30 epochs and unchanged margin weights.
  WDL probabilities reuse the matching globals fit. Fitting rechecks the full
  feature matrix hash against the probe. Do not modify any Python in this
  fitting directory or its pinned dependencies/resources. Prepare later review
  and inference code separately in experiments/hog26_residual_eval.

- All eight numeric residual fits completed normally. Peak supervised RSS was
  5,741,740,032 bytes. Independent audit verified all 30 expected files, source,
  plan, readiness and feature authority, valid arrays, and exact globals
  probabilities/OOF priors. Review:
  hog26_residual_margin_fitting_review_20260912.json.
- Late representative fitting margin gain is positive in all eight folds, so
  the baseline residual fixes that observed fitting shortfall. Excluded-family
  generalization still fails: late representative gains are -0.01642 and
  -0.02070, with wholly negative clustered intervals. All-state overall gains
  are +0.04180 and +0.04093, slightly below the scaled tree's point estimate.
  Bridge-pressure and family-007 representative regressions remain. WDL is
  unchanged reference evidence. No candidate accepted.
- Separate evaluator code in experiments/hog26_residual_eval is prepared for
  all eight opened-diagnostic evaluations plus paired margin error changes
  against the matching scaled tree. Three refusal tests and Ruff pass. It
  requires completed fitting review and a pre-prediction source/checkpoint pin.

- Residual inference was frozen with evaluation pin SHA256
  8c732f8bad522dc7caac8008ec9f23442633bc6729cfbf361d3471d2e78f9b97
  after full fitting review. All eight evaluations and paired margin comparisons
  completed under the shared lock and 18 GiB guard. Peak RSS was 5,962,203,136
  bytes. Independent audit verified the exact 18-file inventory, source/reference
  hashes, all 288/96 group and slice counts, finite bounded margins, identical
  globals probabilities and matching WDL point metrics. Review:
  hog26_residual_margin_diagnostic_review_20260912.json.
- Every fresh seen-family fit improves overall margin versus current margin,
  but none establishes overall paired improvement over the scaled tree. All
  eight seen-family late representative gains are negative, as are all six
  nonempty excluded-family late representative gains. The diagnostic has only
  one late win-containing cluster. Combined with the excluded-family fitting
  review, this baseline is not accepted. All models and reports are preserved.
- Next work is a public-stat representation audit before another frozen training
  test. Existing numeric summaries omit maximum unit health and explicit static
  air/targeting capabilities. The repository has compositional object registries
  and dynamic card factories that may cover the identities missing from the
  standalone semantic helper. Verify mappings and uncertainty from public data;
  do not invent traits or access hidden runtime state as model inputs.

- Public body-registry audit found 54 observed body identities, all resolvable
  without ambiguous name mappings. Existing scalar static fields are constant
  across recorded appearances. Reconstructing each body through the normalized
  object registry, existing card factory and crown-tower helper exactly matched
  all five recorded static fields for all 54 identities. Reports:
  hog26_public_body_registry_audit_20260912.json and
  hog26_public_body_stat_reconstruction_20260912.json.
- The collector's scalar projection explicitly uses card_stats metadata for
  those fields, not mutable entity speed/damage. Additional descriptors must be
  object-level physical facts. Whole-card semantic profiles aggregate nested
  payloads and deployment counts, which must not be mistaken for one body's
  DPS or flying status. No new outcome fit is authorized until the object-level
  descriptor schema and validation are frozen with a new experiment plan.

Public semantic feature implementation: added a separate, unfrozen experiment directory with direct body-stat lookup and 384 physical summary columns appended to the unchanged 425 numeric columns. Nine synthetic/static reconstruction checks pass, covering unavailable identities, padding, causality, entity order, crown visibility and parent/child semantics. A streaming audit of all 1,536 previously audited training archives is running; it reads only the nine public arrays and verifies archive hashes, with no outcome fitting. A successful feature audit will still require a separately frozen model plan and full resident memory gate.

The public semantic audit completed all 1,536 training archives and 618,149 rows with 809 finite columns; feature SHA256 0b5ac234a3adb74b40f13aefaedace2f62f3d86c395a8785b83a0303a32da10c. Ten descriptor/feature tests passed. The first streaming attempts were stopped before publication to correct equal-distance confidence tie handling and an unused variable; their logs remain preserved. No outcome fits used those earlier implementations.

The new eight-fit semantic residual experiment is frozen by reports/hog26_semantic_margin_frozen_plan_20260912.json (SHA256 c7dba3f7be9588f02897568d4ccfa71ccb5b025d5dce3e9da0d05843a6f5508a). It retains the numeric residual loss, 30 epochs, two seeds, four family folds and all data roles, adding 384 public physical summaries. Four model/gating tests passed. Full resident memory passed at 6,430,916,608 bytes, with exact feature hash agreement and zero initial baseline error; readiness is published. The shared-lock fitting supervisor is active. Preserve all Python in hog26_semantic_margin and hog26_public_semantics and all pinned resources. Prepare the separately frozen evaluator in hog26_semantic_eval; compare against both numeric residual and tree, retaining all slices. No candidate accepted.

All eight semantic residual fits completed, with peak supervised RSS 7,103,397,888 bytes. The fitting review verified all 30 files and exact globals WDL reuse. OOF representative late gains are -0.020372 and -0.023220, with wholly negative 95 percent intervals for both seeds. Every fitting-family late representative gain is positive and every excluded-family gain negative. The inference-only evaluator is frozen by reports/hog26_semantic_margin_evaluation_pin_20260912.json (SHA256 84076fff7a3840a026413d6b90dc21177c56e58b21265f33c646939009765e5e) and is running all eight paired comparisons against numeric residual and tree. No model accepted.

A separate retrospective position audit reproduces the fixed late baseline MAEs exactly. Of 80 late representatives, 65 (81.25 percent) are the final decision, versus only 3.918 percent of the all-state late evaluation mass. Baseline MAE is 0.032511 for representatives versus 0.077363 for all late states. This helps explain why unnecessary residual corrections can hurt the representative metric. The audit uses terminal timing only as analysis metadata; no terminal flag, future endpoint proximity or endpoint override enters any model. The metric and gate remain unchanged. Evidence: reports/hog26_late_representative_position_audit_20260912.json.

Semantic diagnostic closeout: all eight evaluations completed, peak RSS 6,105,120,768 bytes. The frozen closeout script hit a KeyError on preserved empty slices without a coverage object. A separate reviewer in experiments/hog26_semantic_review_close handles that existing format; no frozen evaluator, model, prediction or metric changed. The completed review verifies all 18 files, unchanged sources/resources, exact WDL reuse and both paired comparisons. On fresh seen families, all eight overall paired MAE gains over numeric residual are positive (seven wholly positive intervals for all states, three for representatives). However, all eight seen-family representative late gains remain negative, as do all six nonempty excluded-family late representative gains. All eight seen-family representative late paired points lose to tree (four negative intervals). No candidate accepted. Evidence: reports/hog26_semantic_margin_diagnostic_review_20260912.json.

Retrospective OOF decomposition across tree, numeric and semantic models: every model improves the 15 earlier late representatives but regresses on the 65 final-decision representatives. The latter baseline MAE is only 0.012847; earlier positions have baseline MAE 0.117724. This motivates testing whether public state can predict impending termination or little remaining margin change, using future events only as supervised labels. It does not authorize endpoint flags as inputs or a hard-coded zero correction. Evidence: reports/hog26_late_representative_error_decomposition_20260912.json.

The auxiliary next-decision terminal-label audit passed all 1,536 complete games: exactly one positive row per game, 1,536 positives among 618,149 rows, label SHA256 39e01ecd0a2029df096e9ce1538312f2191471a396b7370173eb2161b10c3c7a. Labels use actual terminal timing only; public inputs remain the exact semantic feature matrix. The fixed auxiliary plan is reports/hog26_terminal_auxiliary_frozen_plan_20260912.json, SHA256 5a2a531e2125b36fa8d350468e9af8666aac2080b4697f2393c52587c4a2ab7f. Five tests and Ruff passed. Full resident memory with synthetic BCE step passed at 5,739,659,264 bytes. Readiness is published and eight fixed auxiliary fits are running. No outcome model changes or opened diagnostic evaluation belong to this test.

Before auxiliary fitting, the independent review was pinned by reports/hog26_terminal_auxiliary_review_pin_20260912.json, SHA256 483eacb78463016fc58e755a6d0a49cc0cf155f016e565bbc628ae5fd333422f. It will reproduce every saved probability from its checkpoint, every fold report and OOF interval, and compare against a public phase-only terminal-frequency reference estimated exclusively on fitting families. Preserve Python in hog26_terminal_auxiliary and hog26_terminal_review.

All eight auxiliary terminal fits and the pinned independent review completed. Every saved probability reproduces exactly from its checkpoint; all fold reports, OOF compositions and clustered intervals reproduce. Peak supervised fit RSS was 6,404,931,584 bytes. Both seeds severely underpredict termination on late representatives: mean predictions 0.048997 and 0.062296 versus observed 0.8125, with late representative NLL gains versus the fitting-only phase reference -2.624936 and -2.886470. This failure also appears in fitting families, so lack of cross-family transfer alone cannot explain it. No outcome model changes or diagnostic data access occurred.

An exact replay of auxiliary seed1279501/fold0 is running in experiments/hog26_weighted_optimizer_audit/audit_clipping.py. It records existing preclip gradient norms and coefficient retention by label/phase/representative group, then requires exact equality with the saved checkpoint and predictions before publishing findings. It changes no old source or optimizer and saves no candidate. The replay holds the shared lock; a live RSS watchdog is attached. This investigates whether uniform-row batches plus large importance weights and clipping suppress rare representative examples, without yet claiming a cause or changing the next recipe.

September 13 continuation (existing frozen campaign filenames retained): the exact clipping replay reproduced auxiliary seed1279501/fold0 weights and probabilities. Late representative coefficient retention was 0.1900 and weighted logit-derivative retention 0.03313, versus nonterminal derivative retention 0.84059. These describe clipping before Adam, not effective parameter influence or a sole-cause finding. The live watchdog observed 6,567,280,640 bytes and did not terminate the replay.

A separate sampler-only auxiliary comparison is frozen by reports/hog26_terminal_weighted_sampler_frozen_plan_20260912.json, SHA256 e3941a9ecdb3628d79f7827294f1dcc1b07246933fa67f1538a42537a099a0d6. It draws the same fitting-row count per epoch with replacement proportional to the original loss weights and uses unweighted minibatch mean BCE. Exact enumeration tests verify the same expected unclipped loss and gradient; exclusion and readiness tests pass. Model, initial priors, AdamW settings, clip1, batch512, 30-epoch update count, seeds, folds and data are unchanged. Sampling changes repeated exposure and gradient noise, so it does not isolate clipping alone. Full resident memory and the 474,642-draw buffer passed at 5,944,557,568 bytes. Readiness and the independent paired review pin are published; eight fits are now running. Preserve hog26_terminal_weighted_sampler and hog26_terminal_sampler_review sources. No outcome model changes or opened diagnostic access.

Weighted-sampler auxiliary closeout reproduced all checkpoints, reports and intervals. Compared with the original sampler, both seeds worsen held-out overall and late NLL in both distributions with wholly negative paired intervals. This is not an accepted auxiliary predictor and it is not added to any outcome model.

The direct weighted-sampling margin comparison is frozen by reports/hog26_weighted_margin_frozen_plan_20260913.json, SHA256 26a18ec52c1fc90d1909eb8fa0143385b07f3e5ab63e657b5d066a5c02f1503c. It independently tests both existing numeric and semantic margin architectures with unchanged matrices, initialization, loss weights, optimizer and update count. Four tests verify expected absolute loss/gradient equivalence, original baseline initialization, excluded-row isolation and readiness refusal. Full two-matrix memory passed at 5,870,125,056 bytes, including the maximal sampling buffer and synthetic steps. Sixteen fits are running under the shared lock and 18 GiB guard. The separately prepared hog26_weighted_margin_eval directory will require all 62 fitting artifacts before pinning all sixteen opened-diagnostic evaluations, with paired comparisons against the corresponding original sampler and tree. Three evaluation refusal tests pass. Preserve fitting sources and all prior pins.

All sixteen weighted-margin fits completed and the 62-artifact fitting review passed, with supervised peak RSS 6,571,884,544 bytes. Every fitting-family late representative gain is positive and every excluded-family gain negative; all four OOF late representative gains are worse than their original sampler point estimates. No candidate accepted. The sixteen-model opened diagnostic evaluation is frozen by reports/hog26_weighted_margin_evaluation_pin_20260913.json, SHA256 cce12c89464d5139880ecc13149bc9b438f5b7857c3f11eec59f010f0f221274, and is running. Preserve all six weighted evaluation Python files.

The unfiltered training expansion is implemented separately in experiments/hog26_training_expansion. Three tests verify the 4,608-game schedule, preserved requirements, excluded preflight and refusal of partial evidence. The actual source/schedule draft validates with collection_allowed=false; no expansion games have run yet. It would add twelve new paired scenarios per training deck/style with both seats, using campaign seeds1280101/2/3, preserving the fixed policy and all existing roles. Full preflight auditing must precede collection authority.

The streamed feature prototype passed all 1,536 existing training archives, both exact frozen matrix hashes and 512 random batch reads. Cache shape618149x809, bytes2,000,330,164; semantic SHA256 0b5ac234a3adb74b40f13aefaedace2f62f3d86c395a8785b83a0303a32da10c; numeric-prefix SHA2564b0e0b8e3a66ee46497adac492a7571cea3f625b8cf275cfc09199da933a5ccd. Peak RSS2,509,733,888 bytes. This does not certify 6,144-game fitting memory. The first launch failed on a missing import path before any output data; corrected launch and failure log are preserved. A local /reports/**/*.f32 exclusion was added alongside existing generated binary exclusions in the shared .git/info/exclude to keep the 2GB cache out of automatic VCS checkpoints; no tracked ignore rule or index changed. Evidence: reports/hog26_streamed_feature_probe_20260913/complete.json.

The weighted-margin diagnostic review completed all sixteen evaluations and 38 artifacts, with supervised peak RSS6,867,173,376 bytes. Every nonempty late representative gain against current margin remains negative in both architectures and both fresh-family groups. The final comparison summary and interpretation are in reports/hog26_weighted_margin_diagnostic_review_20260913.json. No candidate accepted.

Training expansion preflight completed all twelve excluded games at peak RSS560,152,576 bytes. Independent publication reproduced all audit records, source/schedule metadata, actual-terminal flags and zero rejected actions, and checked fresh-deal disjointness. Collection is frozen by reports/hog26_training_expansion_frozen_plan_20260913.json, SHA256 a2f3a62b053eb1f197c88572588fa4020e6d5e81f3ac3570c6a4afb7d049f345; preflight pin SHA25670588673f9e239b2547d3b706fd17dc8cd6fb2e2d0ea27d0da9b3131b12fa34e. The 4,608-game collection is running under expansion_supervisor.py, with shared lock and 18 GiB guard. Preserve every Python file in hog26_training_expansion and all src/clasher/scripts sources while collecting. Every scheduled complete game is retained. No automatic fitting follows completion; the combined6,144-game audit, source pin and memory gate remain mandatory. Future combined loader/feature work belongs in a separate directory.

Parallel execution validation: four fresh processes reproduced all non-provenance arrays in the twelve excluded preflight games in21.11 seconds of worker execution, peak combined RSS1,846,984,704 bytes. Eight processes reproduced the same arrays in14.14 seconds, peak3,349,348,352 bytes. A separate production parallel collector then passed its own twelve-game preflight and independent array comparison, with peak3,456,761,856 bytes. The eight-process setting retains the full original schedule and all data/role requirements.

Parallel collection authority is reports/hog26_training_expansion_parallel_frozen_plan_20260913.json, SHA256 ba7cf0d1763bdb801f4cf2b9f89176199b4f7a2f1f57a029b4c5edeee3ac2f56; preflight pin SHA25662bb30e865ce30b894feed452b3c563d50274ad1fa751387a5083a0ecc5133cb. Only after that authority passed, owned sequential collector PID9941 was deliberately terminated. Its supervisor records exit241 from the intentional SIGTERM; this was a performance transition, not a data-validity failure. All sequential files remain intact. The prefix audit independently validated581 completed games with zero unverified tail files and published reports/hog26_training_expansion_sequential_retired_prefix_20260913.json. This partial prefix is execution evidence, not an additional fitting corpus.

The parallel collector now runs the entire unchanged4608-game schedule in datasets/derived/hog26_training_expansion_parallel_seed1280101_20260913, parent PID30196. It holds the shared lock, uses eight isolated processes with atomic validated archive publication, and enforces18GiB combined RSS. Preserve all seven Python files in hog26_parallel_expansion and all reused probe/collector/core sources. After all4608games complete, prefix_audit.py --mode compare must establish array parity with every retained sequential game before combined training access. Future expanded-corpus code lives separately in hog26_expanded_corpus and refuses partial collection or missing prefix parity before setup/arrays. No model accepted and no fitting authorized by collection.

Current execution: parallel collection completed all 4,608 new games; the full 581-game retired prefix matches exactly. The combined 6,144-game corpus and 2,465,152-row public feature cache passed independent review, with 4,684 losses, 1,460 wins and no natural draws. Late representatives now cover 325 games, 275 paired scenarios and 73 scenarios containing wins. No model is accepted. Full-size synthetic memory probes are running for the draft public tree WDL/residual-margin candidate and unchanged globals baseline. Read comparison-status.json and reports/hog26_expanded_tree_value_memory_sequence_20260913.log. Keep all completed collection, expanded_corpus, cache review and memory-probe sources immutable. New outcome fitting still requires a separately frozen model plan and memory readiness. All reserved roles and calibration/ranking gates remain unchanged.

Current execution: the expanded public outcome comparison is frozen and fitting has started under reports/hog26_expanded_value_frozen_plan_20260913.json (SHA256 a970c9ae20ec550f017b0315dd2d79eaecac9fd20c7a061ac8cd1b8556106c99). It runs eight unchanged GlobalWDL fits and eight paired tree WDL/residual-margin bundles, followed by four exact OOF reviews. The actual-loss full-size synthetic memory probe passed at 11,168,481,280 bytes, with all 2,465,152 inference rows checked; readiness reserves another 2 GiB and production retains the 18 GiB guard. The preliminary row-layout tree probe was intentionally retired after profiling column binning; its source and evidence remain preserved. Six model/storage tests passed, including exact globals updates and storage-layout tree predictions. All eleven Python files in hog26_expanded_value_fit are now frozen. Read comparison-status.json and reports/hog26_expanded_value_fit_sequence_20260913.log; do not duplicate the supervisor. No model accepted; complete every fit and exact review before a separate opened-diagnostic plan.

Expanded fitting follow-up preparation: the scientific closeout is frozen by reports/hog26_expanded_value_scientific_review_pin_20260913.json (SHA256 71780d02c001e135712c7057796f329a2729836dd6b39e540b1f49526ea3bffa). Run experiments/hog26_expanded_value_review/review_comparison.py only after all four exact OOF reviews complete. The separate hog26_expanded_value_eval directory is prepared but NOT frozen or executed against diagnostic data. Its two synthetic tests pass; actual pin publication requires the scientific closeout. It retains all sixteen models, both fresh seen/excluded groups, every slice and paired references, then reproduces checkpoint predictions, points and paired intervals. All calibration/ranking and reserved-role gates remain unchanged.

Training-support analysis after model freeze: reports/hog26_expanded_training_support_20260913.json reproduces the original 80/65 late/final counts and finds 325/271 in the expanded corpus (83.3846% final-decision representatives, versus 5.8208% of all-state late weight). Current public-margin MAE is 0.0116627 on those 271 endpoint representatives and 0.1065235 on the earlier54. Four of twelve late phase/seat/style cells remain below existing decisive-cluster floors: bridge-pressure has six clusters per seat (seat1 only one loss); slow-push has zero late wins in seat0 and one in seat1. This retrospective training analysis changes no feature, sampler, metric, quota, or frozen fit. Actual endpoint flags remain excluded from model inputs.

Current execution changed for a separately gated performance replay: all eight globals folds are complete. The first serial tree bundle (seed1279501/fold0) is still running; its classifier is complete and regressor active. The synthetic OpenMP1/8 probe reproduces complete normalized estimator state and predictions exactly for binary and three-class cases, with roughly2.3x speedup. Full-corpus equivalence is NOT yet established. The owned original supervisor PID96292 is intentionally paused; child6657 continues unchanged under guard15744 in experiments/hog26_tree_thread_handoff/guard_reference.py. This guard retains the same18GiB threshold, then retires the old launcher only after the complete first-tree bundle is audited. See reports/hog26_tree_thread_handoff_sequence_20260913.log and comparison-status.json. Do not manually resume the old parent while the takeover guard is active. A full-size eight-thread replay must match the saved serial estimator states and all-row predictions before any remaining tree fits switch threads. All original sources, outputs, model settings and data roles remain preserved.

Current execution: the first serial tree bundle completed in1713.1148 seconds and its artifacts were audited; the original supervisor and child are now retired, with all outputs preserved. Full-size thread replay is frozen by reports/hog26_tree_full_thread_replay_plan_20260913.json (SHA256 f36c61e2cad45a7e0000c7d9c069546ee2b6340f855f01a679da7ebcf9479f40) and is running under the shared lock and18GiB guard. Follow reports/hog26_tree_full_thread_replay_sequence_20260913.log. All four Python files in hog26_tree_full_thread_replay are now frozen. Require identical normalized estimator state (only copied bin-mapper thread metadata normalized) and exact dtype/shape/prediction bytes on all2465152 rows before a separate continuation authority. The unfinished hog26_threaded_value_fit directory prepares that continuation; it is not yet frozen or executable as production. All eight serial globals and the complete serial tree remain preserved. No model accepted.

Full thread replay correction: the first replay failed whole-object pickle hashing at the classifier, and all failure evidence remains preserved. An unchanged-model negative control in reports/hog26_tree_state_serialization_control_20260913.json proves that serializing/reloading the same saved estimator changes that whole-object hash even though every individual state field retains identical bytes. This is a checker false-rejection mechanism, not proof that the eight-thread model is unchanged. The corrected field-by-field replay is frozen by reports/hog26_tree_state_replay_plan_20260913.json (SHA256 c5ba01a7c3309240b51d9d22e27aa41a6be87c48f54289bf7982d2bcc3320427) and is running. It ignores no learned fields, normalizes only copied bin-mapper thread metadata, preserves component checkpoints before checks and still requires exact all-row prediction bytes. All six Python files in hog26_tree_thread_state_replay are frozen. No remaining production fit may switch threads before this corrected full-size proof and memory guard pass.

Current execution: corrected full-size thread replay PASSED all41 classifier fields, all39 regressor fields, and exact dtype/shape/prediction bytes across2465152 rows. Peak supervised RSS11257266176 bytes; no memory termination. The replay completed in284.8587 seconds excluding initial data/matrix preparation, while the serial full bundle took1713.1148 seconds including reporting; these timing scopes differ. The separately frozen continuation plan reports/hog26_threaded_value_continuation_plan_20260913.json has SHA256 dc7f350d45cff1d2a880c6c460c03920fc894dbc7afb0631beed51d594481536. All six Python files in hog26_threaded_value_fit are now immutable. Its supervisor is running seven remaining tree pairs at8 OpenMP threads, with independent copies of the eight completed globals and the verified replay pair in reports/hog26_expanded_value_threaded_comparison_20260913. Original observations, model settings, seeds, targets and weights are unchanged; every tree manifest records execution provenance. Four exact OOF reviews follow. The new scientific closeout is frozen by reports/hog26_threaded_value_scientific_review_pin_20260913.json (SHA256 1facefec6fb79755a7c67667359a89f382d27a85ff291c5b002cd397b71ff939), using hog26_threaded_value_review/review_comparison.py. Do not use the retired serial supervisor or old serial closeout for this continuation. The WIP hog26_expanded_value_eval now targets this continuation but remains unpinned and has not accessed diagnostic data. All prior failed checkers and reports are retained. No accepted model; all data-role and public calibration/ranking gates remain intact.

Current execution: all16 fold bundles and all24 model estimators are complete. Exact reviews now run concurrently in four unchanged single-thread workers under experiments/hog26_parallel_value_review/supervise.py, with one combined18GiB guard. Schedule pin is inside the continuation output at review_schedule_plan.json (SHA256 6f26b5e92851f7f0c1fc4befd7114020f53fa2a0a5729809eeecef488ae7fadd). Guard PID58095 covers existing globals seed1279501 review PID53678 plus new workers58133/58134/58135. Original continuation parent30925 is intentionally paused and must not be resumed while this guard is active; the guard will retire it after all four exact reviews finish and publish the same completion contract with explicit scheduling provenance. Worker source, seeds, metrics, bootstraps and output paths are unchanged; each process writes distinct review/OOF artifacts. All model sources and this new scheduler source are frozen. Do not start scientific interpretation or opened diagnostics before complete review. Follow reports/hog26_parallel_value_review_sequence_20260913.log and comparison-status.json.

Current execution: all four exact fitting reviews and the frozen scientific closeout are COMPLETE. Parallel review peak was6086230016 bytes; all16 checkpoints, predictions and point reports reproduced exactly. The old continuation parent30925 and parallel review guard have finished; no paused training launcher remains. The fitting conclusion is in reports/hog26_threaded_value_fitting_conclusion_20260913.json. Both tree seeds improve held-family late margin: representative MAE0.0274242 to0.0173195/0.0171308, with gain CIs[0.0060411,0.0147282]/[0.0061443,0.0148884]; all-state late gain0.0244358/0.0240862 also has positive CIs. However, early bridge-pressure margin regresses by about0.02 in both seats and both seeds with negative CIs, and late representative tree NLL trails globals. No model accepted. The separately frozen all16-model opened diagnostic is now running under experiments/hog26_expanded_value_eval/supervise.py --mode evaluate. Pin reports/hog26_expanded_value_evaluation_pin_20260913.json has SHA256 e00d4985a22c059e94d795aaa764f4d9aa097558b5c4969366ba3c5fc6d2cedb and freezes all nine Python files in that directory. Main log reports/hog26_expanded_value_diagnostic_sequence_20260913.log; detailed log reports/hog26_expanded_value_diagnostic_20260913.log. After evaluation completes, run the same supervisor with --mode review for exact checkpoint/point/paired-interval reproduction. Keep all reserved roles and public calibration/ranking gates unchanged.

Training-only post-fit localization is complete in reports/hog26_expanded_error_localization_20260913.json (SHA256 58e2b697e58562a507a4cf00a0dbd53aaf93c5032df669f4efaab2ffd1ece263). It uses no opened-diagnostic results. Late representative gains mainly come from the54 earlier positions: baseline MAE0.1065235 falls to0.0500697/0.0505440, with gain CIs[0.0360144,0.0740922]/[0.0362827,0.0734090]. The271 endpoint representatives remain near baseline (small gain intervals cross zero). Early bridge-pressure is a separate ordinary-play failure: zero of512 seat0 early representatives and only one of512 seat1 representatives are final decisions. Families003/006/007 show large negative early-bridge margin changes; fitting-family early-bridge point gains are negative in six of eight models, with the models excluding006/007 the exceptions. This supports investigating missing public temporal information or objective/capacity limitations from training evidence; it does not identify a cause or authorize changes to the frozen models. All16 opened diagnostic evaluations completed under the guard at6867550208 peak RSS; their exact review is now running.

Current execution: all16 opened diagnostic evaluations and the independent36-artifact review are COMPLETE. Review peak RSS7007797248 bytes; all checkpoint predictions, point metrics and paired intervals reproduced. The conclusion is reports/hog26_expanded_value_diagnostic_conclusion_20260913.json. Late margin gains carry to familiar families (all8 positive representative gains,7 positive intervals); excluded-family late representatives remain mixed (4 positive/2 negative nonempty cases,2 empty), though all6 beat the old scaled tree. Late tree WDL remains weaker than globals in familiar-family cases. Counts overlap diagnostic games; the entire late diagnostic has only one win-containing cluster. No accepted candidate and no fitting authorization derives from this opened diagnostic. Continue training-only investigation anchored in reports/hog26_expanded_error_localization_20260913.json: test causal public-history features and their information content before a separately frozen next outcome fit. All current models, readers, evaluators and source pins remain preserved.

Current execution: public entity-history extraction and readback passed all6144 games/2465152 rows. The97-column cache is956478976 bytes with SHA256 9fde495104adfe4a11b590e509e9fd8e4d4e62f0b287459bc916ab6fcfe5514b; no column is constant. Every game passed prefix checks,12 fixed games passed complete streaming/future-perturbation byte equality, and512 random reads matched. Peak guard RSS1199587328 bytes. History/cache plan SHA2565a4b201826d77138f9d206269d7a633fac9ed1f6cade5f855e3cc2abd14e1116 freezes both public_history Python files and all four history_cache Python files. Existing global-resource histories are unchanged; new lags1/5/20 and20-transition variation operate on24 masked entity summaries. The training-only early bridge-behavior information probe is now frozen and fitting16 classifiers under reports/hog26_early_behavior_probe_plan_20260913.json (SHA256 a612a29754c4edc425f6551106fbdee0d7431dee634c198554526c633f9b2001). It compares814 versus911 public inputs at one existing early representative per each of6144 games; style is a binary target only. Two seeds/four whole-family folds, same classifier settings, no outcome targets or auxiliary predictions as outcome input. Full6144x911 synthetic memory proof passed below0.90GB. All nine Python files in hog26_early_behavior_probe are frozen. Follow its fit log and live state, then run supervise.py --mode review. No outcome model or policy has been updated by this probe; no accepted candidate.

Current execution: the early-behavior information probe and exact review are COMPLETE. Public entity history improves overall held-family binary NLL from 0.21538291 to 0.19225271 and AUC from 0.94749527 to 0.95907974; paired NLL gain 0.02313020 has CI [0.01744572, 0.02921784]. Both seats improve, but family006 has a negative point change with an interval crossing zero. The two configured seeds produced identical prediction bytes in every representation/fold; loaded estimator seeds differ correctly, but this small, fully binned/all-feature learner has no effective seed variability. Do not count these as independent replications. This establishes usable behavior information, not outcome improvement.

A separate training-only early-margin assay is now frozen by reports/hog26_early_margin_probe_plan_20260913.json (SHA256 a76563b8d4b56911215f2c57a68139e06e2f343f104c69959ce215c7ab47c37c). All ten Python files in experiments/hog26_early_margin_probe are frozen. It compares base814 and history911 on identical existing early representatives for all 6144 games, four whole-family folds, one fixed seed1280501, equal-game absolute residual loss: eight regressors. Full-training OOF references are checked through the scientific/completion/exact-review hash chain and early bridge scores reproduce. All29 groups and seven contrasts are retained; paired intervals are unadjusted diagnostics. Comparing focused base with focused history isolates added features under the learner; comparing either with full-training trees also changes phase/sample allocation and binning. The full-shape synthetic memory gate is running, then fit and exact review follow under the shared lease. This is not a full-phase candidate or acceptance test. No model accepted.

Latest execution: all eight focused early-margin fits and exact checkpoint/point review are COMPLETE. Peak fitting RSS1193541632 bytes; review1166098432. History worsens overall early MAE from0.20913676 to0.21072830 (paired gain CI[-0.00240498,-0.00079882]); behavioral identifiability did not imply outcome improvement. Focused base814 improves versus both full-training references overall and in bridge-pressure; bridge MAE falls from0.24767778/0.24987485 to0.23052708, but its gain over current0.22701047 remains inconclusive. No full-phase candidate or acceptance claim. See reports/hog26_early_margin_probe_conclusion_20260913.json. Next separate training hypothesis: fixed public-phase-specific margin regressors with unchanged814 features and unchanged globals WDL, evaluated across every original slice/distribution. No history outcome candidate proceeds from this failed assay. All early-margin sources are frozen; do not rerun completed supervisors.

Current execution: the separate public-phase margin comparison is frozen by reports/hog26_phase_margin_plan_20260913.json (SHA256 d810b4e570c3c4566d75518b0a2f5deb82caa29b30e9985104dab3fa00e760ee). All nine Python files in experiments/hog26_phase_margin are now immutable. It fits three margin experts per seed/fold (24 regressors), using the same814 public features and original margin weights restricted/renormalized per phase. Fixed1/3 and2/3 public-clock thresholds were checked against every2465152 cache row. Same reviewed globals checkpoints provide WDL; no classifier refit. Early/middle bin subsampling may vary by seed, while late fits are expected to be deterministic and must not be counted as independent replication. Two boundary/weight tests and Ruff pass. Full-size synthetic memory is running for the largest populations: early1144736, middle730490, late22074 rows. On success, supervisor --mode run fits all eight bundles and performs two exact reviews plus scientific paired comparisons across every original slice and both distributions. This changes capacity, phase allocation and per-phase binning; it does not isolate a cause. No accepted candidate, diagnostic access or policy update.

Execution update: the phase memory gate PASSED each largest phase matrix plus all2465152 routed inference rows. Worker peak RSS9375645696 bytes, supervised peak9295806464;2GiB headroom remains below18GiB. The phase supervisor --mode run is active (parent32596, initial child32645), exec session53235. It will fit all24 regressors and perform both exact reviews plus scientific closeout automatically. Do not launch duplicate fitting/review workers. All phase sources remain frozen.

A separate boundary discontinuity audit is frozen by reports/hog26_phase_boundary_audit_pin_20260913.json (SHA256 d9500011282bb83218b29ce8d105fa0df05e18c329447c1403073af529f26ccf). Both Python files in experiments/hog26_phase_boundary_audit are immutable. This audit must wait until phase supervisor completion/exact/scientific reviews and the shared lease release. Then run its supervise.py using the phaseBoundaryEnv prefix. It compares adjacent phase experts on identical last-before/first-after public states, verifies routed OOF equality, and reports switch magnitudes without outcome-based selection or scoring. This is predictor extrapolation, not environment-action counterfactual ranking or acceptance. No boundary audit process is running yet.

Read-only feasibility audit: reports/hog26_early_margin_feasibility_audit_20260913.json checks existing early predictions against[-current enemy mean tower fraction,current own mean tower fraction], with1e-6 floating tolerance. All6144 early targets satisfy the interval. Full-tree seeds violate it at3/2 early points; focused base/history at6/7 points. None of the1024 early bridge-pressure predictions or targets violate it, so this mechanism does not explain the bridge regression. No clipping or model change was applied. Source experiments/hog26_early_margin_bounds/audit_bounds.py is preserved by its report hash. This is an exploratory training-only early check, not a full simulator invariant proof. Phase fitting continues unchanged.

Synthetic binning control: reports/hog26_binning_weight_synthetic_control_20260913.json confirms installed sklearn1.7.2 binning ignores sample weights. Two synthetic8192x2 fits with opposite100:1/1:100 weights produced identical bin-threshold bytes but different predictions, proving weights still affect the loss/fit. Local gradient_boosting.py calls _bin_mapper.fit_transform(X) without weights; binning.py uses uniform row subsampling above200000 and unweighted quantiles. Source experiments/hog26_binning_weight_probe/probe.py and package-source hashes are retained in the result. This distinguishes representative-only fitting from full-row weighted fitting, but does not establish a cause of observed outcome error. It supplies no result-dependent change to the ongoing phase comparison. A future binning/weight-allocation study, if warranted by complete training reviews, requires a separate fixed plan.

Execution scheduling update: experiments/hog26_phase_parallel_review/supervise.py is now immutable (SHA256 494f36217bc469921766bd8ad085cc7940b8c1bfc7699d5c096afa21a8f5bd60) and running in waiting mode, exec session88424; follow reports/hog26_phase_parallel_review_sequence_20260913.log. Original phase parent32596 continues fitting unchanged. Only after all eight bundles and their guards complete and the first exact review starts will the scheduler publish reports/hog26_phase_parallel_review_plan_20260913.json, pause parent32596, and run the second unchanged single-thread seed review concurrently under one combined18GiB guard. The paused original parent retains the shared lease during review. Do not manually resume it after handoff. After both exact reviews pass, the new scheduler retires that parent, acquires the lease, invokes the unchanged scientific worker and publishes phase root completion with scheduling provenance. Existing first-review exit status is unavailable to the new parent; its exact exclusive completion/OOF artifact is required and receipt memory scope is explicit. No model, data, metric or bootstrap changes. This replaces the serial review schedule only. Boundary audit remains queued after complete scientific review.

Current execution: all24 phase regressors and all eight fitting guards are COMPLETE. Largest fitting guard peak10442948608 bytes. Parallel exact reviews are now active under scheduler48595, workers51422/51648, exec session88424. Schedule plan reports/hog26_phase_parallel_review_plan_20260913.json SHA256 fb677a4947f529f800b80f225eca8f42b3eedfe3447e6a0c27a2f09641c6735c. Original parent32596 is intentionally paused and retains the shared lease; do not resume it. The new scheduler will retire it after both exact reviews and then invoke unchanged scientific closeout. Follow reports/hog26_phase_parallel_review_sequence_20260913.log and the two phase review logs. No model-quality interpretation before full review. Boundary audit remains queued.

Current execution: both phase exact reviews are COMPLETE. Every24 new regressor and all eight unchanged global checkpoint predictions and point reports reproduced. Per-worker review peaks2416738304/2411806720 bytes; first receipt explicitly records unavailable non-child exit code and verified completion/OOF authority. Original parent32596 was deliberately retired after both completions; unified session53235 ended143(SIGTERM), and PID32596 is absent. No paused parent remains. Parallel scheduler48595 now owns the lease and is running unchanged phase_science.py, child60510, log reports/hog26_phase_margin_science_20260913.log. Wait for root complete and scheduler session88424 success, then run pinned boundary audit. No accepted model.

Phase comparison and boundary audit are COMPLETE. All24 regressors and eight globals reproduce exactly; scientific closeout passed. Parallel-review aggregate peak4828545024 bytes, science2177155072; boundary1188757504. No active or paused phase process remains. See reports/hog26_phase_margin_conclusion_20260913.json. Early/middle margins improve versus old trees with positive paired intervals; late representative MAE0.01585856 versus current0.02742418, gain0.01156562 CI[0.00864704,0.01507803]. Added late improvement over old trees remains inconclusive. Late predictions are byte-identical between seeds, not independent replication. Early bridge representatives nearly match current baseline, while all-state bridge points remain about0.008-0.0095 worse with CIs crossing zero. One supported late balanced seat1 representative slice regresses versus previous seed1279502 tree (gain-0.00496344 CI[-0.01090092,-0.00034048]); do not hide it. Four late cells lack support and one seed1279501 late-random seat0 representative class-ECE point exceeds0.2. Hard routing has substantial discontinuity: same-state early-to-middle expert switch averages0.0570/0.0578 absolute,95th-percentile0.1504/0.1529. This is not an environment counterfactual ranking result. No candidate accepted. Next: separately freeze inference-only evaluation of all eight fixed bundles on the permanently opened seed-transfer diagnostic. That evaluation cannot authorize fitting, selection, calibration or acceptance. New evaluator sources are being prepared separately; all previous sources remain immutable.

Current execution: all eight fixed phase bundles are being evaluated on the permanently opened diagnostic under experiments/hog26_phase_value_eval/supervise.py --mode run, exec session23752. Its pin reports/hog26_phase_margin_evaluation_pin_20260913.json has SHA256 ede357d930127e73c30ad39e063c6f08420831d19c82a89bbb2e53d6af5bffa1 and freezes all nine Python files. Three access/checkpoint-chain tests and Ruff passed. The supervisor performs evaluation then exact prediction/point/paired-interval review automatically. Both margin contrasts keep expanded-globals WDL identical. No fitting or acceptance authority comes from this diagnostic. A separate next training hypothesis is fixed before transfer feedback in reports/hog26_overlap_margin_training_hypothesis_20260913.json: fresh smooth overlapping experts, original6144 games/features/learner, triangular public-clock gates centered1/6,1/2,5/6; original margin weights times gate, normalized per expert. This is a proposal, not execution authority. It addresses training-observed hard-switch discontinuity and retains native unweighted binning. Future fitting requires completed diagnostic review plus its own fixed source and full memory gate.

The eight-bundle phase transfer diagnostic and its exact18-artifact review are COMPLETE, with evaluation/review peaks8049246208/8049655808 bytes. No diagnostic process remains. See reports/hog26_phase_margin_diagnostic_conclusion_20260913.json. Overall gains versus current margin have positive intervals in all eight familiar and all eight excluded-family cases on both distributions. Familiar-family early/middle gains versus prior trees are consistently positive; excluded-family improvements and comparative late results are less uniform. Cases overlap384 games, and late still has only21 games/16 clusters/one win-containing cluster. No accepted model or fitting authorization derives from this set. The already fixed smooth-overlap proposal proceeds only from training boundary evidence, with new source/plan/memory readiness still required. Its core gate/inference tests pass in WIP experiments/hog26_overlap_margin; that directory is not yet frozen or authorized for fitting.

Current execution: smooth-overlap comparison is frozen and fitting has started. Plan reports/hog26_overlap_margin_plan_20260913.json SHA256 9b3b1b3318d1f60c2835f13593008700110e3fc80d149cddb45a0becaf5f741c freezes all13 Python files in experiments/hog26_overlap_margin. Do not edit or add Python there. It implements the pre-transfer training-only proposal with no setting change. Five tests pass. Statistical reuse reproduces all240 actual reference bootstrap dictionaries exactly; changed-margin controls also match the full original bootstrap on all22415 late states and325 late representatives. Source-bound proof files are preserved. The full-size synthetic memory guard passed at10100932608 supervised peak RSS with2GiB headroom under18GiB. Largest expert fitting row counts are1653689,1318176,240204. Supervisor --mode run fits24 regressors, then runs two unchanged-seed exact reviews concurrently under one aggregate18GiB guard, reusing only verified unchanged WDL statistics, and performs current/full-tree/hard-phase paired scientific comparisons. No active older diagnostic, fitting or paused process remains. New overlap fitting uses only the original6144 training games; no diagnostic values selected its configuration. No model accepted.

The follow-up overlap boundary audit is pinned before model-result inspection: reports/hog26_overlap_boundary_audit_pin_20260913.json SHA256 19763da7808795b708107f72bcdcfc7b980ccc60e8bf3586da6362a5f7212cfa. Both Python files in experiments/hog26_overlap_boundary_audit are immutable. After full overlap comparison/exact/scientific completion and lease release, run its supervise.py with overlapBoundaryEnv. It covers centers1/6,1/2,5/6 and old boundaries1/3,2/3; decomposes gate versus head changes, checks sum agreement and the6*delta_clock routing bound, reproduces OOF bytes and compares observed changes with hard-phase/full-tree/current references. No outcome target is used, and this is not action ranking or acceptance. Overlap training remains active under parent82765, exec session25172; its first bundle completed at10910351360 supervised peak RSS, second bundle is running. No old paused process remains.

An unwired bounded online encoder is now frozen in experiments/hog26_online_value_features (all five Python files). Pin reports/hog26_online_value_features_pin_20260913.json SHA256 8d7b7675c3f599edb8d2ea283c68db369a75213c1cee61158c5a1a2e25b70a63 selects16 fixed evenly spaced complete training games. Four tests pass:814-column streaming/batch byte parity,20-frame masked-global history, resets, clone/input ownership, transactional refusal and ignored optional next-card slot. The real-game audit has NOT run. After overlap comparison and overlap boundary audit finish and release the lease, run experiments/hog26_online_value_features/supervise.py --mode audit with onlineValueEnv. It checks every frame against the complete feature cache and cloned continuations without loading outcome arrays or changing any policy. Static layout/body metadata remain shared immutable resources. This is encoding parity, not visibility-mask, model-quality or counterfactual-ranking acceptance.

Current execution: all eight overlapping bundles and24 regressors are COMPLETE. Two exact reviewers5471/5472 now run concurrently under the original overlap supervisor82765 and shared18GiB aggregate guard, exec session25172. No supervisor handoff or paused parent is involved. Follow reports/hog26_overlap_margin_review-seed1279501_20260913.log and the corresponding seed1279502 log; scientific closeout follows automatically. The compact current handoff is HANDOFF_ACTIVE_TRAINING_20260913.md. After root completion, run the pinned overlap boundary audit, then the pinned16-game online encoder audit, in that order under the shared lease. No candidate accepted.

Overlap exact reviews are COMPLETE: both worker exit codes0, all24 regressors and eight globals reproduce, and the verified WDL-statistic reuse completed without discrepancies. Combined review peak4707385344 bytes. Supervisor82765 is running the scientific comparison (child10558) against current/full-tree/hard-phase margins; exec session25172 remains active. After root completion, the pinned boundary-component audit and then16-game online encoder audit remain queued. No accepted model.

Overlap fitting, exact reviews, scientific closeout and boundary-component audit are COMPLETE. No accepted model. See reports/hog26_overlap_margin_conclusion_20260913.json. Overlap improves all-state late MAE to0.04124/0.04104 versus hard0.04211, but worsens middle all-state error by0.00285/0.00309 and middle representative error by0.00405/0.00435, with negative paired intervals. Late representative MAE rises from hard0.01586 to0.01744/0.01728, also significantly worse. Overall errors worsen modestly versus hard experts while remaining better than current and original full-tree baselines. A supported late-random seat1 representative slice also regresses versus the original full tree in seed1279501. Boundary audit verifies exact OOF reconstruction and decomposition: mean actual jumps at the old first boundary shrink from0.0572/0.0581 to0.00685/0.00693; second boundary from0.0358/0.0344 to0.00406/0.00389. Routing-only components are about0.00025 and0.00009 respectively. Tree-head changes remain; this is not action-ranking acceptance. Boundary peak1426948096 bytes. The queued16-game online-feature audit is now running under experiments/hog26_online_value_features/supervise.py --mode audit. All old model processes are complete; no paused parent remains.

The 16-game online encoder audit is COMPLETE: all 6,313 frames match the audited 814-feature cache exactly, cloned continuations match, divergent clones remain isolated, and history stays bounded at 20. Peak supervised RSS 861372416 bytes; no policy/model changes. All model and boundary jobs are complete. A separate training-only numerical readiness screen is now pinned and running in experiments/hog26_training_gate_screen (all five Python files immutable). Pin reports/hog26_training_natural_rule_screen_pin_20260913.json has SHA256 f8b81a83dd10f393dd1e22904dbb1903a5e97eeb14f19732f1cead1cee1d8e27. It uses the actual preserved representative public-slice evaluator and original full-phase metric/bootstrap helpers on each held-family fold, comparing joint/hard/overlap margins with identical globals WDL. It retains the protocol's development-style subset and all training styles, separates numerical from coverage failures, and uses no reserved data. This does not test the full acceptance procedure or grant acceptance. Relative changes against prior models are distinct from the unchanged declared thresholds.

The natural-rule screen FAILED before scoring: the unchanged legacy representative evaluator rejects a zero entry in the training prior, while the scalar natural corpus has exactly zero draws. Guard exit1 and its log are preserved; all five screen Python files remain frozen. No prior smoothing, invented draw mass, gate bypass or acceptance claim was introduced. The declared corrected training draw controls are separate, but they came from the older tensor backend and cannot be silently mixed into the scalar corpus. A new excluded scalar control feasibility probe is now pinned and running in experiments/hog26_scalar_draw_feasibility (all three Python files immutable). Pin reports/hog26_scalar_draw_feasibility_pin_20260913.json SHA256 5e27a5cfd7c1442eb49877507ac561b3f538ecf2934ec5b92706ddf34a2624ee. It uses the existing unchanged scalar run(policy_selfplay=True) on identical Hog decks for seeds1281001/1281002, repeats the first exactly, and runs a no-op terminal control at1281003. Every outcome is retained and one actor view is captured per physical run. All four runs remain excluded from fitting, selection/calibration and final evidence; no-op draws do not establish natural-draw calibration or replace the required frozen-policy mirror controls. No learning or physics change occurs. The current model/encoder/overlap audits are complete; no other campaign is active.

The excluded scalar draw feasibility is COMPLETE: both frozen-policy mirror games (1281001/1281002) lost from seat0 at tick2938 with margin -0.0093283582; exact replay passed. Only the no-op control drew. All probe data remain excluded. Identical actions/success/visible counts at all368 decisions; the two seeds differ at170 action-order entries but all recorded actor/policy/recurrent hashes and other trace fields agree. A separate observational tick replay is being audited in experiments/hog26_scalar_mirror_trace_v2. The first trace audit is preserved as failed: its comparison did not normalize Python tuples against JSON lists, and its entity snapshot used hp instead of hitpoints; it emitted no completed report. V2 corrects these audit defects and preflights six initial tower snapshots, without editing frozen simulator or collector sources. No model accepted; natural-rule prior support remains unresolved. No training or reserved validation is running.

The scalar mirror tick audit v2 is COMPLETE with exact original trace/result equality after JSON representation normalization. Forty-seven logic ticks had unequal rotated tower HP; the first was779. At tick2938 seat0 king dies while seat1 retains135HP; this is not just a winner-label tie-check issue. Both mirror trace Python directories and their pins remain frozen, including failed v1. No physics changed.

A new explicitly diagnostic numerical screen is pinned/running in experiments/hog26_training_supported_metrics. All six Python files are frozen by reports/hog26_training_supported_metrics_pin_20260913.json (SHA2563b7502af33461c44ff360d2da103f7f021bc94c86ee1a93553fab1580848d7e1). It copies the representative evaluator with only its prior-domain check changed: zero is allowed for unobserved labels, observed zero-support outcomes are refused. It preserves the native positive-prior failure separately and cannot establish acceptance. Three tests pass: source diff restricted to those changes, full report equality on positive priors, native zero-prior refusal plus finite diagnostic NLL and observed-zero refusal. Same48 planned training-fold/design/style cases, unchanged priors/probabilities/margins and numerical thresholds; no reserved labels. Source/rules unchanged in scripts and old screen. Exec session75135 supervises the new audit under comparison.lock.

The supported-metrics screen is COMPLETE:48 cases, exit0, peak1451802624 bytes. Source-bound summary reports/hog26_training_supported_metrics_conclusion_20260913.json. On declared balanced/reactive-defense styles, hard-phase margins have no numerical margin failure among covered representative slices. Supported WDL failures are late balanced seat1 fold3 top-ECE0.22463/0.20229 (limit0.2), and early reactive-defense seat1 fold2 seed1279502 AUC0.535714 (limit0.55; only2win clusters). Broader styles retain fourteen supported margin-check failures across repeated seed/fold cases, especially early bridge-pressure. Counts are not independent replications. Coverage and native zero-draw prior still fail. No acceptance.

Before new fitting, a fixed comparison of the two already reviewed WDL heads (globals/trees) with identical hard-phase margins is pinned/running in experiments/hog26_training_wdl_screen. Three Python files frozen; pinSHA88a15b5f5df5e462494d014b9e378bf8e6c31ad0da68001c0a3b261ecbd74296; supplementary helper authority reports/hog26_training_wdl_screen_helper_pin_20260913.json binds unchanged supported-metric helpers. Verify helper hashes again after completion.32cases across2heads,2seeds,4folds,2style scopes. No new fitting, model combination, probability calibration, or reserved labels. Exec session97322. Initial standalone helper validation omitted torch.set_num_threads(1) and failed runtime guard; rerun with requiredthreads1 verified unchanged sources successfully.

Existing-WDL screen is COMPLETE:32cases, exit0, peak1332428800 bytes; supplementary helper hashes match after run. Source-bound conclusion reports/hog26_training_wdl_screen_conclusion_20260913.json. Full-tree WDL resolves the covered early reactive AUC failure but has covered late reactive-defense calibration failures (topECE0.20599/0.26220) and additional broad-style late failures. Neither unchanged head is a clean replacement; all prior/coverage restrictions remain.

The next supervised experiment is pinned/running: experiments/hog26_late_classifier/supervise.py --mode run, exec session34897, lateClassifierEnv. All five Python files are immutable (late_contract,fit_late,review_late,supervise,test_late). Pin reports/hog26_late_classifier_pin_20260913.json SHA256372c05fc36f0e34b0881d633dd82c64e73677658b842ef9819e7a6d32165ad9b. Hypothesis was saved before implementation in reports/hog26_late_classifier_hypothesis_20260913.json. Eight native HGB log-loss100-iteration fits on late-only22415rows; fittingfolds18499/11130/22074/15542rows. Same814features and original WDL weights restricted tolate, mean1. Both classes0/2 required, drawprobability0 recorded as absent support. Two seeds1279501/2,4family folds,8fitthreads/1inference,18GiB guard. Exact pickle prediction replay and all late fold/style metrics follow automatically. Comparison uses unchanged hard-phase margin and globals/tree WDL references, and does not create an early/late probability composite. Paired NLL bootstrap preserves game and scenario weights; duplication-invariance test passes. Identical seed outputs expected at this small population and must not be counted as independent replication. No new controls, reserved labels, calibration, policy or physics changes.

The late classifier is COMPLETE:8fits and exact saved-model prediction replays, fitpeak1506869248 bytes/reviewpeak1303347200, both exit0. Source-bound summary reports/hog26_late_classifier_conclusion_20260913.json. Candidate predictions are identical acrossseeds (one effective result). No covered representative late classification failure in either style scope; covered full-late classification checks pass. Fold2 still has no late wins and fails coverage. Representative NLL gains versus globals are positive with clustered intervals in fold3 (~0.17 for both reference seeds), but other fold comparisons remain uncertain. Margin artifacts computed on late-only aggregates are not full-phase protocol acceptance gates; unchanged hard margins retained. No composite/fresh-validation/calibration or acceptance.

Next excluded feasibility is running: experiments/hog26_mirror_order_feasibility/supervise.py --mode run, execsession78723, mirrorOrderEnv. All3Pythonfiles frozen by reports/hog26_mirror_order_feasibility_pin_20260913.json SHA256603f7ef5ec7ad7f1124f5c7ea2eb9ad76afc4b4f14aa32e929f9c0336ee012e7. Fixed16 mirrored initialorders (eight cyclic and eight reversed cyclic), deterministic unchanged frozen policy, current scalar physics, independently domain-hashed battle/action-order streams. Every outcome retained, plus exact replay of order0. Existing Scenario object supplies identical decks without mutating run.DECK or physics. One actual actorview perphysicalgame. No no-op, scripted override, outcome filtering, or fitting role. This tests opening dependence because old two-seed fixed-order mirrors had identical trajectories. Even if draws occur, this excluded data cannot be silently relabeled as training/calibration.

Mirror-order feasibility is COMPLETE:16unique physicalgames produced8wins/6losses/2draws fromseat0; exactfirstreplay passed, peak615546880 bytes. Drawsorder06/order12 terminateat3032/3329 withbothkingsdestroyed andmargin0. Summary reports/hog26_mirror_order_feasibility_conclusion_20260913.json. This is not natural draw-frequency evidence, and all16remain excluded.

Paired public-view proof is COMPLETE: excluded order0loss plus bothdraws, exactoriginalseat0arraybytes/fullphysicaltrace, actualbothseatactions and independentlyauditedoppositemargins. Bothpublicviews acceptedbyonline814encoder. Peak474562560 bytes. All4Pythonfiles in experiments/hog26_scalar_paired_views frozen by pinSHA22c30a8e49522d1a6469bcd560722590af461a2a777059bb31199ffaf0aedae6. PairedWriter wraps build/step observationally, callsoriginalonce and restoresmethods aftercontext; neverrerunsbattleforoppositeview.

Separate prospective training-control collection is now pinned/running: experiments/hog26_scalar_mirror_training/supervise.py --mode run, exec session53317, mirrorTrainingEnv. All5Pythonfiles frozen by reports/hog26_scalar_mirror_training_pin_20260913.json SHAd2049576cd62fbbfe518a92bf8f0e36c2f7bf15613925a65153e9c6dc36612b7. Four ordinary subprocess collectors, shared18GiBguard/lease, then independentserialaudit.256fixed uniquepermutations fromrole-domain1281301 excludeall16opened feasibilityorders;512actualactorviews from256physicalgames. No outcome filtering or quota, evenifdrawsupportpoor. Roletrain-scalar-mirror-controls is separate fromnaturalcalibration distribution. No fitting occurs here; anyWDLuse needsnewpinned mixing/weight plan. Outputdatasets/derived/hog26_scalar_mirror_training_controls_seed1281301_20260913. One schedule test verifiesdeterminism, uniqueness, disjointopeneddeals andzero globalRNGconsumption. All priortraining andfeasibility jobs complete.

The prospective training-control collection and independent review are COMPLETE. All256 physical games were retained:129losses/96wins/31draws fromseat0; actual paired views give225losses/225wins/62draws over202408rows. Four worker exits0; reviewexit0. Aggregate collector peak2602319872 bytes; reviewpeak410238976. Source-bound summary reports/hog26_scalar_mirror_training_conclusion_20260913.json. All31draws endbetween1671and3477ticks; none reacheslatephase. Controls remain separate fromnatural class-frequency evidence. No fitting yet.

The feature cache/audit is now pinned/running: experiments/hog26_mirror_training_features/supervise.py --mode run, execsession50275, supervisor49402/worker49413, mirrorFeaturesEnv. All4Python files frozen by pinSHA bef943c4c33a00089a5ad38ff4ddcd3d2561513634505af6638895abc5eaf182. It verifies every814-column batch/stream frame, explicitrawWDL-toLDWlabels, exactpublicclock and physicalpairidentity; labelsnever enterencoder. A separate future-fit hypothesis was written before implementation in reports/hog26_three_class_phase_hypothesis_20260913.json: same6144natural games plusall512markedtrainingcontrolviews,24public-phaseWDLclassifiers, matchinghardmargins, originalequal-game/reached-phaseweightsrestrictedperphase, actualunsmoothedcombinedprior andseparate natural/controlfrequencies, no outcome balancing. It is not a fit authorization artifact by itself; completecache and separately frozen code/plan/memoryproof stillrequired. Latephasehasno draw examples; absentclass mustremain explicit.

The control feature audit is COMPLETE: all202408×814 values reproduce streaming/batch bytes exactly, rawWDL-to-LDWlabels verified, peak513736704 bytes, exit0. Cache659040448bytes, shape[202408,814],256physical clusters/512views, no fitting. Summary reports/hog26_mirror_training_features_conclusion_20260913.json.

Three-class phase fitting is now separately pinned, with all10Pythonfiles in experiments/hog26_three_class_phase immutable. Pin reports/hog26_three_class_phase_pin_20260913.json SHA c15412931b138e64f629d4c46e97046bb0d80331f6ffd6dff4ad2f6a78725106. Same6144natural games plus512controlviews;2667560combinedrows.24classifiers over2seeds×4natural familyfolds×3public phases. Largest phase fitting populations1272408/803360/23940. Early/middle actualclasses[0,1,2]; late[0,2] in everyfold. Combinedactualfittingprior drawmass62/5120=0.012109375; natural-onlyprior stillzero and separate. This controlled mixture is not a naturaldrawrate estimate. Existinghardmargin models/predictions remain unchanged. Two tests pass for public-clock routing/absentclass behavior and exact cross-store feature materialization. Fourfold fitting controlrole is always training, never controlvalidation.

The largest-phase synthetic memory proof is being run under the shared18GiBguard before any real labels fit: threeClassEnv experiments/hog26_three_class_phase/supervise.py --mode memory. It allocates1272408×814float64, three syntheticclasses, two iterations, no checkpoint; requires2GiBheadroom before --mode run. After proof succeeds, --mode run fits8bundles sequentially, runs2exactseedreviews concurrently, then nativepositive-prior numerical screens and paired natural WDL comparisons. Allzero-draw-priorfailedlineages remainpreserved; this newpriorgetsactualcontrolsupport, not inventedmass. No reserveddata, probabilitycalibration, policyupdates or acceptance.

The three-class synthetic memory proof passed:1272408×814float64 features, three syntheticclasses, two iterations, no checkpoint or realfittinglabels. Peak11082137600bytes leaves required2GiBheadroom below18GiB. The actual campaign is now RUNNING under experiments/hog26_three_class_phase/supervise.py --mode run, execsession64635, supervisor55200; firstworker55251 fitsseed1279501/fold0. It fits24classifiers across8bundles, then runs2exactseedreviews and science automatically. All10Pythonfiles remain frozen by pinc15412931b138e64f629d4c46e97046bb0d80331f6ffd6dff4ad2f6a78725106. At an initial99second snapshot the firstworker used10.22GiB RSS and695CPUseconds, consistent with active8threadfitting. No prior process remains active. No accepted model.

A separately pinned excluded late-continuation feasibility probe is ready but NOT RUNNING. All5Pythonfiles in experiments/hog26_late_continuation_feasibility are immutable; pinSHA f8f245b2e2461eb4eb55157ce9e9514b30d9136d4d0c59c56d491bbe079a6baf. After the current three-class campaign and its exact/scientific reviews finish and release comparison.lock, run lateContinuationEnv experiments/hog26_late_continuation_feasibility/supervise.py --mode run. It uses8fresh mirrored orders disjoint fromthe16opened and256training orders, each with a real forced-pass prefix to tick4000or4800, then the unchanged frozen policy through actual terminal. No clock/state/physics shortcut; all outcomes retained. Extra zero-prefix control must reproduce originalorder0 fulltrace/arrays exactly; firstlatecase repeats exactly. Both actual views retained and allframes checked byonlineencoder. A unit test proves onlyselectedactions change before release and originalpolicyresult/hiddenstate objects pass through unchanged afterward. This is not ranking, search, calibration or fitting. ALL18physical runs remain excluded, including pre/postrelease states. Only postrelease states would have the unmodified-policy future if a distinct later training collection were designed; prefixlabels must never be silently used as original-policy targets.

The first three-class bundle (seed1279501/fold0) has completed fitting and point reports; exactreview andotherfolds pending. Preliminary natural held-family meanpDraw is0.000826 onall-state weighting; controlfitting meanpDraw0.113639 versusobserved0.121094. A separate read-only fitting diagnostic found within-control drawAUC0.97293 overstates and0.98437 atlastdecisions; actualdraw endpoints meanpDraw0.63149 versus0.04016 fordecisivecontrols. These are training-control diagnostics, not independent controlled validation or acceptance. The fixed current campaign is unchanged.

The user asked to inspect Instagram reel DdMGvYLsyL- and compare the creator's approach. The36.63s Day50 reel (2026-09-12, bz_builds_stuff/vegetableleaf) was downloaded with yt-dlp and inspected in frame sheets; ending shows a match win and+30trophies. Public repo vegetableleaf/ClashAI was inspected at commit431d34c9cebccd189cc720190fb2d04d36daa58e. User-facing comparison: their current live policy is pro-action imitation with real-engine replay generation and screen-perception adapters; our active task is terminal-value forecasting with a frozen playing policy. Their old RL/search failures and perception problems were distinguished from demonstrated live gameplay. No claim that our additional audits make us a stronger player. Current training was left intact. Evidence and read-only notes: reports/hog26_external_clashai_comparison_20260913.md and reports/external_reel_DdMGvYLsyL_20260913/. Downloaded third-party code was not executed.

Bounded follow-up: their engine wrapper imports external native_core from research/ext/cr-native-sandbox; mainrepo alone is not runnable engine. Public HF dataset VanguardX101/IL_Replay was verified ungated at revision059d43a02138a34b1b3009cc2acc7630fb99a638. Dataset card lists252238replays/17836160actions. One fixed first shard(5000replays,17432059bytes,SHA9f6127099b57d91eef64da308873a2635f72b27ae8fd9d802fc7d1767363b656) was downloaded and audited with our own streaming parser, entirely excluded fromfitting/calibration. It contains210same-base-Hog26sides butzeroexactvanilla matches, withEvo/Heroforms retained;365362placementevents allhave ticks andin-boundsnativeXY. This is a convenience shard, not a global estimate. sample_audit.json recordsalllimits. No form aliasing, replay reconstruction or externaldatafitting was performed. Anonymization removesplayerIDs/dates, limitingplayer/patchsplit claims. Existinggamebinary/runtime is notavailable frommainrepo and nohook/client/extraction workwas attempted.

A lightweight memory pass for the previousTVRoyale study used MEMORY.md:410-445 and rollout_summaries/2026-08-18T00-22-04-2aRA-tv_royale_structured_replay_feasibility.md (rollout01a0123f-282c-7cb2-9cfc-11d13bebcd52). This was context for acquisition boundaries, not a freshproof ofAPI availability. Publicdataset metadata wasverifiedlive. Include these memorycitations if a finalresponseis eventuallysent; no memoryfiles wereedited.
