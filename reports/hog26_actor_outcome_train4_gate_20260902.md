# Hog 2.6 actor-visible outcome gate

## Decision

The 128-game crossed corpus is accepted as complete-game training evidence. The
free structured-summary head and both bounded structured residual candidates are
rejected. The public-global control has the best aggregate development score,
but a larger-window audit rejects it too: held-out early-game decisive AUC is
0.4808. It is not authorized for search or policy updates.

The next evidence step is broader matchup diversity, not more epochs on the
same 32 streams: collect additional current supported decks across every
strategy style and both seats, then repeat the frozen-baseline residual screen.
An untouched holdout and additional seeds remain deferred until a contextual
candidate beats the public-global baseline.

## Corpus authority and audit

- Corpus: `datasets/derived/hog26_crossed_train4_seed1276001/corpus.npz`
- SHA-256: `62aa1bbf6ff59dc020992a9f4c3e3dd030797389a842e73ed528cd9ff21ffa1a`
- Policy checkpoint SHA-256:
  `f609b60b3e7b7b574e084b15255e0fc247447e3c18d8552714213ccd0c709336`
- 128 complete episodes, 59,287 actor decision rows, four episodes in each of
  32 strategy/deck/seat streams.
- Outcomes: 91 losses, 37 wins, zero natural draws. Controlled draw corpora
  remain separate.
- Seats: seat 0 = 44 losses / 20 wins; seat 1 = 47 losses / 17 wins.
- Episode length: minimum 141, median 450, maximum 628 decisions.
- Independent checks passed: exact terminal winner to actor-relative outcome,
  exact episode label repetition on every row, terminal margin repetition,
  one start and one terminal per episode, ordinal 0-3 for every stream, finite
  numeric arrays, and no critic arrays.

## Experiments

| Candidate | State width | Trainable parameters | Selected epoch | Held-out decisive AUC | ECE | Decision |
|---|---:|---:|---:|---:|---:|---|
| Free structured summary | 398 | 8,098 | 18 | 0.4683 | 0.2126 | reject |
| Public globals, old NLL selection | 18 | 646 | 29 | 0.6087 | 0.1282 | selection policy superseded |
| Public globals, old aggregate gate | 18 | 646 | 14 | 0.6733 | 0.1214 | reject; early AUC 0.4808 |
| Frozen-global + bounded full structured residual | 398 | 7,145 | 0 | 0.6733 | 0.1214 | reject; no positive gain |
| Frozen-global + compact tactical residual | 118 | 1,905 | 0 | 0.6733 | 0.1214 | reject; no positive gain |

The public-global checkpoint is
`checkpoints/hog26_actor_outcome_public_globals_fullgate_seed1276201/candidate.pt`
with SHA-256
`1fad639704256691fd4fa696a0ad548397d8c3884e9b0d1e83848f52bee4d750`.
It is a historical control, not an accepted warm-start or promoted search value
function under the corrected across-phase gate.

## Correctness changes

1. Epoch selection now maximizes decisive ranking only among epochs that pass
   the complete development gate. Previously, monotonically improving NLL
   selected epoch 29 even though decisive AUC had already degraded materially.
2. Structured residual heads have a separate normalization boundary, begin at
   exactly zero context contribution, warm-start from an accepted public-global
   head, freeze that head, and bound the context correction.
3. The structured candidate must improve decisive AUC over its frozen baseline;
   reproducing the baseline is not a promotion.
4. Actor feature tensors, losses, and gradient norms now fail immediately on
   non-finite values. This was added after an MPS zero-upstream LayerNorm
   gradient produced NaNs; the context branch no longer uses that unsafe
   normalization pattern.
5. Aggregate AUC is no longer sufficient: early, middle, and late held-out
   decisive AUC must each clear 0.55. This rejects the globals-only shortcut
   that looked strong mostly because tower state makes late outcomes obvious.
6. Model selection and acceptance now use one representative midpoint row per
   episode per reached phase. Full row-weighted metrics remain diagnostic only;
   long games can no longer contribute hundreds of correlated copies of one
   terminal label. The training prior is likewise computed from episodes, not
   decision-row counts.
7. Final development and holdout acceptance require a deterministic 2,000-draw
   nonparametric bootstrap lower 95% bound above 0.50 for decisive AUC in each
   phase. Point estimates alone are not treated as evidence of above-chance
   generalization.

## Interpretation

The corpus increased repeated outcomes per original matchup, but it did not add
enough independent matchup diversity. The free structured model learned
training-specific entity/deck correlations, especially against the held-out
Valk Log Bait family. Constraining the context prevented catastrophic drift but
did not make those features useful. More epochs or more copies of the same
matchups would strengthen the shortcut rather than solve it.

No search, policy update, PPO, or self-play improvement is authorized by this
gate.

The exact-terminal counterfactual evaluator now rejects every historical
development-only outcome checkpoint and any checkpoint that predates the
phase/bootstrap/untouched-holdout gates. It can consume public-global,
mechanics-primary structured, bounded structured-residual, and compact tactical
heads from the current joint actor inputs, selecting the correct learner seat
without critic state. A two-branch real-runtime smoke passed, as did a mixed
public/structured prediction smoke over joint actor inputs.

## Broad-collection interim result

After adding the first four new training decks, a globals-only diagnostic on
the still-small 18-game natural development split selected epoch 12. Its
episode/phase-balanced decisive AUC was 0.6704 overall: early 0.6429, middle
0.8542, and late 1.0. It passed every point-estimate/calibration/draw gate, but
was correctly rejected because the early bootstrap lower 95% bound was only
0.3846. This is encouraging evidence that matchup diversity helps, while also
confirming that the development set needs more independent games before any
acceptance claim.

The matching 398-feature mechanics-primary structured head was materially
stronger on the same interim split: selected epoch 27, phase-balanced decisive
AUC 0.8148 overall, with early 0.7143, middle 0.8542, and late 1.0. It too was
rejected—the early lower 95% bound was 0.4615, below the required 0.50. Unlike
the original four-deck structured failure (AUC 0.4683), this is direct evidence
that independent deck diversity is repairing contextual generalization rather
than merely improving calibration.

The margin audit then exposed that the prior `terminal_tower_margin` output was
only the current public tower margin and had no trainable regression path.
A bounded, zero-initialized residual was added, but sharing the classification
trunk and classification class weights both caused held-out regression drift.
The corrected design uses a separate public-global margin branch, equal mass per
complete game (without 45/10/45 class rebalance), and independent outcome/margin
epoch selection. On the interim split it selected outcome epoch 11 and margin
epoch 1, improving phase-balanced margin MAE from 0.12079 to 0.11649. Every
phase improved (early +0.00359, middle +0.00459, late +0.00631), but the overall
gain 0.00431 remains below the current 0.005 promotion floor. This candidate is
therefore still rejected pending the broader fold.

## Broad-collection train-fold A+B result

The second 56-game shard passed the same complete-stream, terminal-label,
finite-value, seed/hash-uniqueness, and critic-absence audit. Its full outcome
mix is 34 losses and 22 wins across four additional decks, seven behavior
styles, and both seats. The deterministic primary fold retains the four
training styles only: 32 games, 14,439 rows, 20 losses, and 12 wins; output
SHA-256 `c5cfbd0ae70736788ae702fa98064eaebcf0cd944b07fc158517157de3d6d95c`.

Combined with the original corpus and fold A, the primary pool now contains
192 complete natural games, 88,965 rows, 12 decks, four training styles, both
seats, 127 losses, and 65 wins. The combined independent audit passes and finds
no seed/hash collision or private critic input.

A predeclared interim structured-summary run on this 192-game pool selected
outcome epoch 26 and margin epoch 1. Phase-balanced decisive AUC was 0.7481:
early 0.6071, middle 0.8750, late 1.0000. It remains rejected because the early
bootstrap lower 95% bound is only 0.3248. The independent public-global margin
branch improved phase-balanced MAE by only 0.00226, below the 0.005 floor.

A bounded alternative giving an otherwise independent margin trunk the full
398-feature structured summary was also tested and rejected: its best
development margin was the zero-update epoch, while every learned update was
worse. The code experiment was discarded. This rules out simply feeding the
current pooled entity summary into terminal-margin regression; it does not rule
out a future explicitly spatial or temporal damage model.

The same audit exposed a train/evaluation mismatch: acceptance gives one equal
vote to every reached early/middle/late phase, while the loss previously gave
every timestep within an episode equal weight. A bounded A/B equalized reached
phase mass inside each game for outcome classification only, retaining the
equal-game regression weights. With identical data, initialization seed, and
hyperparameters, early decisive AUC rose from 0.6071 to 0.6786, overall
phase-balanced AUC rose from 0.7481 to 0.7519, NLL fell from 0.5920 to 0.4922,
and ECE fell from 0.1752 to 0.1440. Middle/late AUC stayed at 0.8750/1.0000;
margin metrics were bit-identical to the control. The early bootstrap lower
bound is still only 0.3750 on the small interim validation set, so this is a
retained training correction, not an accepted model.

Two additional paired initialization seeds refined that conclusion. Across all
three pairs, phase-balanced training changed overall phase-balanced AUC by
`+0.0037`, `+0.0148`, and `+0.0222`, and reduced NLL in every pair. Early AUC
changed by `+0.0714`, `-0.0714`, and `0.0000`; therefore the apparent early
gain in the first seed is not stable. Phase balancing remains justified by its
consistent whole-phase ranking/calibration benefit and contract alignment, but
additional independent early-game outcomes remain the only accepted route to
narrowing early uncertainty.

Confidence intervals are now cluster-bootstrapped by complete
`seed/style/deck/episode-ordinal` matchup, so the two mirrored learner seats are
resampled together rather than miscounted as independent evidence. On the
current 18-game natural development set this reduces the early effective sample
to nine matchup clusters and widens the lower 95% bound from 0.3750 to 0.2825;
the point AUC remains 0.6786. The broader development shard is therefore
required even more strongly. All future development and untouched-holdout
acceptance uses this clustered interval and requires at least eight independent
clusters in every phase. This also closes the prior false-pass edge case where
late AUC was perfect on only three clusters.

## Seven-deck development expansion and representation screen

Broad shard C completed 56/56 games and passed the independent audit: 24,449
rows, 35 losses, 21 wins, maximum 706 decisions, corpus SHA-256
`13bf058c01831c191cec897448301f7481c16783443b70484c9fe010c4eb603f`.
Its held-out-style fold contains 24 games and 11,124 rows across four new decks,
with SHA-256
`17b99b3c43ccb2fc5d5c6c1c85bee3d3015595307988dc18df323d18a05a1a7f`.
Combined natural development now has 42 games, seven unseen decks, three unseen
styles, both seats, 20 losses, and 22 wins. It supplies 21 early and 20 middle
matchup clusters but only five late clusters, so no model can yet pass the
frozen eight-cluster-per-phase gate.

The frozen 398-feature structured candidate on this larger development set
selected outcome epoch 30 and margin epoch 1. It achieved phase-balanced AUC
0.7317 (early 0.6091, middle 0.8500, late 1.0000). The clustered early lower
95% bound remained only 0.3454. In contrast, the independent margin branch now
clearly passed its point gates: MAE improved by 0.01168 overall, with early,
middle, and late improvements of 0.01124, 0.01325, and 0.00558. The remaining
blocker is outcome representation/confidence, not terminal-margin learning.

Three bounded representation alternatives were screened at matched authority:

- Frozen policy recurrent features were worse than the mechanics summary in
  every phase: early/middle/late AUC 0.5818/0.7950/0.6250. Reusing the weak
  policy memory is rejected.
- A 12-bin team/lane/zone mechanics pool greatly improved middle AUC to 0.9700
  but reduced early AUC to 0.5727.
- Concatenating the global and spatial summaries at hidden width 16 improved
  overall AUC to 0.8014 and middle AUC to 0.9250, but early AUC remained 0.6455
  versus 0.6864 for its matched global-summary control. Width 32 and an explicit
  smooth phase mixture both made early ranking worse and are rejected.

The corpus also contains no opponent play-event or seen-card arrays; the simple
backend exports zero-width history for this checkpoint. This explains an
important irreducible-looking early ambiguity: a current snapshot cannot retain
publicly revealed opponent cards after their entities leave the arena. A
deterministic 494-bit model-owned seen-enemy-token memory was therefore tested
causally over the existing ordered trajectories. On the larger development
fold below it failed to improve ranking and was removed; no recurrent or
spatial experiment code remains in the accepted source path.

## Eleven-deck development expansion

Development shard D completed 24/24 games and passed audit: 10,067 rows, exactly
12 wins/12 losses, maximum 750 decisions, SHA-256
`6e71d22506ab60eb1f8857aaf4e5b53cabcc977159c571311c4852cc61b4037d`.
The combined natural development pool now has 66 games, 30,112 rows, 11 unseen
decks, three unseen styles, and both seats. It supplies 33 early, 31 middle,
and six late independent matchup clusters.

The plain 398-feature structured control is now the clear winner. It achieves
phase-balanced AUC 0.7409: early 0.6935 (clustered lower 95% 0.5110), middle
0.8452 (lower 0.6917), and late 0.8800 (lower 0.2857). Overall ECE is 0.1956.
Terminal-margin MAE improves by 0.01556 overall and improves early/middle/late
by 0.01687/0.01624/0.00185. Thus early and middle confidence, calibration, and
margin gates now pass. Acceptance remains impossible only because late has six
clusters rather than eight and its interval crosses chance.

The model-owned seen-token candidate with 0.1 label smoothing was worse on the
same 66 games: overall/early/middle AUC 0.7326/0.6484/0.8183 versus the control's
0.7409/0.6935/0.8452. It is rejected and removed. A final development-only
shard over four remaining control/cycle decks is collecting to add independent
late games; the frozen structured architecture will not change based on that
shard.

Epoch selection is now maximin across early/middle/late point AUC before using
aggregate AUC and NLL as tie-breakers, and still considers only epochs that pass
the point/calibration/draw gates. This aligns model selection with the eventual
all-phase acceptance rule instead of allowing aggregate AUC to sacrifice a weak
phase. Replaying the 66-game structured run selected the same epoch 29, so this
correctness tightening does not change the reported candidate or metrics.

## Fifteen-deck development and probability calibration

Development shard E completed 24/24 games and passed audit: 18 losses, six
wins, maximum 687 decisions. The final natural development pool contains 90
games, 40,269 rows, 15 unseen decks, three unseen styles, both seats, and 50
losses/40 wins. It has 45 early, 40 middle, and 11 late independent matchup
clusters, finally clearing the support floor in every phase.

The frozen structured ranker clears every ranking-confidence gate on this pool:
early/middle/late AUC is 0.6808/0.8358/0.9500, with clustered lower 95% bounds
0.5093/0.6925/0.6429. Overall ECE is 0.1534. The first finalization attempt was
still correctly rejected because its balanced 45/10/45 training objective
produced ranking logits rather than calibrated probabilities: NLL 0.9616 was
worse than the empirical train-prior NLL 0.8424.

Two correctness changes followed without altering an acceptance threshold:

1. Margin epoch selection now chooses maximum aggregate improvement only among
   epochs that pass the all-phase margin gate. The prior selector chose epoch 2
   despite a late MAE regression of 0.0296; epoch 1 passed the full margin gate.
2. The factorized outcome head now corrects its draw-vs-decisive and
   win-vs-loss logit offsets from declared training class mass to the empirical
   complete-game training prior. A single bounded decisive temperature may be
   fit on a physically separate calibration corpus; training uses uncalibrated
   logits, and validation labels never fit the temperature.

Prior correction alone improves development NLL to 0.8569 while retaining all
three ranking-confidence passes, but remains short of the required 0.02 gain
over the prior. A clean calibration split (balanced shard D calibrates;
old+C+E+draw validates) reduces NLL to 0.6732 and ECE to 0.0912. Its
early/middle/late AUC is 0.7030/0.8611/1.0000, but the early clustered lower
bound is 0.4897, narrowly below 0.50 because removing D leaves fewer validation
matchups. That split is rejected rather than relaxed.

A new-seed 24-game calibration-only shard is therefore collecting on already
known development decks. It will fit the scalar temperature while leaving the
entire 90-game development pool label-independent. The four remaining unseen
decks stay reserved for untouched holdout.
