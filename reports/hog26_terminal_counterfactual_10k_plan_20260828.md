# Hog 2.6 terminal-counterfactual action-ranker experiment

## Why this replaced StrategyBot distillation

Three opponent-mixture PPO campaigns and both default/tuned StrategyBot
distillation failed free-running no-regression gates. The exact tuned teacher
pilot used Candidate-17, learning rate `1e-5`, and checkpoints every two updates;
the parent scored 4-8 while the best trained checkpoints scored 3-9. The parent
already matched teacher play/wait and card choice on visited states. Nearly all
remaining teacher loss was one heuristic tile target, and fitting it moved losses
between matchups rather than improving outcomes.

The replacement target is the terminal result of an actual intervention. At a
fixed parent-policy state, evaluate the base action plus the strongest legal
candidate from every action type under an exact continued game. The learned
ranker receives only the frozen actor's public state/action features; privileged
simulation is label-only.

## Bounded authority probe

Parent:
`checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt`, SHA-256
`28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`.

One M4 CPU root with five candidates took 32.54 seconds and about 406 MB RSS.
At tick 256 the parent no-op lost 0-1. Ice Golem and Cannon alternatives won
2-0; Fireball won 1-0. This is direct evidence that the root set contains useful
causal spatial/action repairs, not merely a different heuristic opinion.

## Collection contract

`scripts/run_hog26_terminal_counterfactual_10k_seed1164601.sh`:

- fixed learner deck: Hog 2.6;
- train opponents: 1,720 card-balanced train signatures;
- validation opponents: 312 signature-disjoint validation decks;
- train/validation signature overlap: zero;
- six deterministic public-information StrategyBot continuations, rotated by
  game;
- base plus strongest legal candidate per action type, maximum six;
- terminal lexicographic authority: outcome, crowns, tower damage;
- roots begin at tick 256 and are spaced by 64 policy decisions;
- atomic per-game shards, resumable publication, combined duplicate-state
  rejection, SHA-256 input manifest;
- root gates: at least 8,000 train and 2,000 validation.

The first 189 resumable shards used a four-root cap. The rolling continuation
uses an eight-root cap; the final manifest records both observed caps. This
reduces repeated prefix simulation without relabeling existing roots.

Remote collection runs on Prime pod `446d9316faea4960a2a6d3054c11916c`, a
64-vCPU/256-GB Nebius CPU node at $1.59/hour, plus disjoint-range pod
`e4bf732f924b473a9eb807d27f8fb1bb` of the same shape. No GPU is used. Each
node publishes a hash-bound source/policy/collector/runner authority and exact
game range. The local supervisor requires ranges 0-799 and 800-1399 to cover
every train ID exactly once, and likewise partitions all 350 validation IDs,
before combination. The first 79
published shards contained 309 roots and 34 decisive base improvements (11.0%).

## Ranker and promotion gates

Three independently seeded public action-value heads are fitted to root-level
bootstrap resamples of the train split. Outcome, crown, and damage pair losses
are independently normalized so numerous damage pairs cannot drown terminal
outcomes; weights also sum to one per root within each priority so roots with
more legal candidates cannot dominate. `LoadedPublicActionValueEnsemble`
selects with a lower dispersion bound
on each candidate's paired gain over the base action, not unpaired absolute head
scores. Each member gain is normalized by its untouched-validation median
absolute paired gain, preventing arbitrary score magnitude from dominating the
ensemble. Every checkpoint carries the parent SHA so remote/local path differences
cannot bypass policy identity.

`scripts/calibrate_public_action_value_ensemble.py` compares the frozen actor,
each independently calibrated single head, and the uncertainty ensemble. It
publishes only the strongest controller that clears all of:

- at least 65% overall and terminal-outcome pairwise action-order accuracy,
  with at least 500 untouched outcome pairs;
- at least 25% ordinal terminal-regret reduction;
- at least 25 overrides;
- 95% Wilson lower bound of positive-override precision at least 75%;
- no opponent archetype with negative mean rank delta.

The selected controller descriptor is calibration-hash-bound and may name a
single head or the ensemble. This prevents a weaker ensemble from being kept
merely because it is architecturally fancier.

Only a published controller that passes the calibration gate enters gameplay;
the selector may retain either a single head or the ensemble. The 582 frozen-archetype heldout
decks are deterministically signature-stratified into 195 screen and 387
quarantine decks; both are disjoint from train, calibration, and each other.
Two exact opponent signatures used by the diagnostic threshold/cadence screen
are excluded from the promotion data. The replacement clean split contains 195
screen and 385 quarantine decks, remains pairwise signature-disjoint from the
1,720 training and 312 calibration decks, and uses fresh seeds 1164811 and
1165811. The controller is evaluated every 16 policy decisions; this cadence
was declared only after a diagnostic 12-game stride screen and therefore is
validated exclusively on the replacement clean pools.

Clean screen SHA-256:
`ecbc18a6df9855eba9ca526eb44dd762a2511d00bf2198faeb6851a27c76049d`.
Clean quarantine SHA-256:
`5590b43390b8097049d067b0a5dd462d6d2471b0fa3759e7fce298ed00e71c2c`.

The 48-game six-strategy screen
requires zero win-to-loss flips, at least two loss-to-win flips, at least five
additional crowns, and nonnegative crown delta for every strategy. The 96-game
heldout quarantine requires zero win-to-loss flips, at least four loss-to-win
flips, at least eight additional crowns, and a positive paired-score bootstrap
lower bound. Failure at any stage rejects the reranker without changing the
parent policy.

## Partial-corpus learnability and closed-loop diagnostic

An immutable mid-collection diagnostic combined 849 completed game shards into
4,881 intervention roots, including 656 decisive base improvements. It was not
used for promotion because its internal game split reused the training deck
pool. A 128-wide bootstrapped head with priority- and root-balanced loss reached
59.67% overall and 65.12% terminal-outcome pairwise accuracy on its 1,212-root
internal validation split. Its zero-observed-regression threshold produced 26
overrides: 18 strict improvements, eight ties, and zero regressions. Doubling
the network width, removing the root bootstrap, or removing the balancing loss
all reduced ranking or safety evidence, so the production architecture remains
the smaller balanced head family.

A matched 12-game heldout-deck closed-loop threshold sweep then tested whether
the learned signal affected play rather than only offline rankings. The fitted
zero-regression threshold of 1.5835 made no overrides in the small screen. A
0.50 exploratory threshold converted one loss to a win with no win-to-loss
flip; a more aggressive 0.25 threshold found additional improvements but also
caused one win-to-loss regression. These exploratory checkpoints remain
diagnostic-only. The result supports finishing the disjoint corpus and using
the predeclared calibrated single-versus-ensemble selector, while retaining a
richer entity-token state representation as the fallback if disjoint
calibration or gameplay gates reject the current pooled 192-feature state.

The next bounded objective screen trained on base-versus-candidate pairs only,
matching the deployed controller's actual comparison. On the same internal
split this raised relevant terminal-outcome accuracy from 65.12% to 70.11% and
relevant overall pair accuracy from 59.67% to 61.41%, while its accuracy over
all candidate-versus-candidate pairs remained 59.65%. In the same 12-game
closed-loop screen, an exploratory gain threshold of 1.00 again converted one
loss to a win with no win-to-loss flip (12 overrides, crown differential +2);
threshold 2.00 made one neutral override and the internally calibrated 3.14
threshold made none. This confirms that a base-relative objective is a valid
next-lineage candidate, but it does not replace the predeclared all-pairs
production fit before disjoint validation. If the production gate rejects, the
base-relative objective must be tested as a separately declared lineage rather
than retroactively weakening the current gate.

Cadence was a larger effect than either fit objective. With the all-pairs
partial head at exploratory gain 0.50, reducing query stride from 64 to 16
changed the same diagnostic 12-game result from 7-5 to 11-1: five loss-to-win
flips, zero win-to-loss flips, crown differential 5 to 18, tower-damage
differential 21,117 to 47,387, and 45 overrides across 299 queries. The
base-relative head at gain 1.00 reached 9-3. This does not promote either
partial head, but proves that stride 64 suppresses usable corrections and
justifies the clean-pool stride-16 production gate above.
