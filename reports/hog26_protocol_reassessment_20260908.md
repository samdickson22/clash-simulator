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
