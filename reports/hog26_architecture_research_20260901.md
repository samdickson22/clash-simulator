# Clasher Hog 2.6 architecture research reset

Date: 2026-09-01  
Status: research decision; no checkpoint promotion and no long training run

## Bottom line

The primary failure was not insufficient model size or insufficient epochs.  We
trained and selected under the wrong likelihood/replay contract and the wrong
teacher distribution, and then decoded one weighted classifier as if it were
an ordinary posterior:

1. the factorized student used an 8x play-class loss weight, but inference did
   not subtract `log(8)` from the play logit;
2. timing was graded mostly by repeated wait rows;
3. conditional card/location targets came from bots that almost never used the
   win condition or principal ranged defender;
4. arbitrary mid-game recurrent chunks started from zero state;
5. the training trajectories came from the Python policy proxy while promotion
   used the Simple PyTorch Gym; and
6. PPO received the burden of discovering long-term tactical improvements from
   a weak initializer without a reliable action-value teacher.

The replacement should keep the proven relational encoder, structured model-
owned state, slot-equivariant card pointer, and full legal heatmap.  It should
change data, timing, recurrent replay, and policy improvement before changing
encoder width.

The recommended system is:

- the existing well-ranked timing score with held-out affine calibration,
  interpreted as a continuous-time event rate, with the uncalibrated decoder
  and a discrete-delay head as bounded controls;
- direct-Simple, student-state policy distillation from the frozen behavioral
  control using a validated tempered distribution;
- coverage-stratified conditional supervision with importance correction back
  to natural behavior probabilities;
- stored recurrent state plus burn-in;
- actor-visible and privileged outcome-value pretraining on complete games;
- search-guided conservative policy iteration over simulator-evaluated legal
  candidates; and
- synchronous PPO plus a frozen behavior KL as the first online-RL control;
  V-trace/UPGO is reserved for a genuinely asynchronous actor pipeline.

## New quantitative findings

### The 84.4% accuracy was not meaningful action competence

Selected checkpoint:

`checkpoints/hog26_factorized_executed_strategy_e3_seed1244001/candidate.pt`

Validation decomposition:

| Measurement | Value |
|---|---:|
| rows | 24,256 |
| teacher play rows | 2,895 (11.94%) |
| wait rows | 21,361 (88.06%) |
| reported overall exact action | 84.42% |
| predicted play rate | 18.43% |
| play recall | 97.03% |
| reconstructed play precision | 62.84% |
| false plays | 1,661 |
| false plays per true play | 0.574 |
| complete card-plus-tile exact on play rows | 26.87% |
| card correct when acting | 94.68% |
| conditional exact tile | 28.74% |
| within one tile | 48.91% |
| within two tiles | 60.66% |
| correct lane | 80.55% |
| tile Chebyshev error median / p90 | 2 / 9 tiles |

The high overall number therefore measured an overactive model correctly
repeating many waits.  Its 1,661 false plays were more than half as numerous as
all real plays in the validation set.

The summed stochastic play probability provides an important qualification:

| Timing probability metric | Value |
|---|---:|
| actual play rate | 11.94% |
| mean predicted play probability | 16.91% |
| ROC-AUC | 0.9863 |
| Brier | 0.04769 |
| ten-bin ECE | 0.04979 |

The representation ranks likely play moments well, but its probabilities are
miscalibrated and overconfident.  For example, rows with mean predicted play
probability 0.45 contain only 9.1% teacher plays; the 0.75 bin contains 33.0%.
This further argues for retaining the encoder and replacing/recalibrating the
timing contract rather than widening the network.

A two-parameter Platt calibration was then fit on 19,647 naturally occurring
play-legal training rows and evaluated unchanged on 5,247 validation rows:

| Metric | raw | calibrated |
|---|---:|---:|
| mean predicted play probability | 16.91% | 11.35% |
| Brier | 0.04769 | 0.03077 |
| NLL | 0.13819 | 0.09728 |
| ten-bin ECE | 0.04979 | 0.01024 |
| precision at 0.5 | 62.84% | 81.79% |
| recall at 0.5 | 97.03% | 81.62% |
| predicted play rate at 0.5 | 18.43% | 11.91% |

The fitted scale/bias were `1.23724` and `-2.10654`.  This is offline evidence,
not a gameplay fix, but it changes the implementation order: first reuse and
calibrate the existing score; do not initialize another timing MLP.  Convert
the calibrated probability for the 0.4-second simulator interval into a rate
`-log(1-p)/0.4`, then rescale by actual elapsed time.  The continuous-time
module remains useful as a cadence-safe probability/decoder contract.

The global calibration is **not** eligible for deployment.  Per-strategy audit
showed that it repairs the overconfident balanced/reactive-defense/slow-push
subsets, but worsens bridge-pressure, spell-control, and split-lane Brier and
recall; the latter teachers already had nearly separable raw timing.  This is
more evidence that six incompatible heuristics should not be collapsed into one
behavior authority.  Fit timing calibration anew on the single frozen neural
teacher's direct-Simple trajectories and require per-opponent, not aggregate,
held-out improvement.

### The largest timing error was an omitted class-prior correction

The pretrainer's `play_weight` was exactly `8.0`.  Weighted cross-entropy does
not learn the natural class posterior: at its population optimum, the play
logit is shifted upward by `log(8)`.  Recovering the natural posterior requires
subtracting `log(8) = 2.07944` before normalization.  The independently fitted
Platt bias, `-2.10654`, is only `0.02710` away.  That near identity is strong
mechanistic evidence that much of the apparent timing collapse was an inference
contract error, not insufficient representation.

A zero-training replay-disjoint validation pass applied only this principled
prior correction:

| Metric | raw weighted logits | subtract `log(8)` |
|---|---:|---:|
| exact flat action accuracy | 84.42% | 89.23% |
| predicted play rate | 18.43% | 10.11% |
| play precision | 62.84% | 87.48% |
| play recall | 97.03% | 74.09% |
| wait accuracy | 92.22% | 98.56% |
| false plays | 1,661 | 307 |
| mean stochastic play probability | 16.91% | 9.84% |
| play Brier | 0.04769 | 0.03322 |
| play NLL | 0.13819 | 0.10438 |

The result replicated across all three independently initialized students:

| seed | exact raw -> corrected | play precision raw -> corrected | predicted play rate raw -> corrected |
|---:|---:|---:|---:|
| 1244001 | 84.42% -> 89.23% | 62.84% -> 87.48% | 18.43% -> 10.11% |
| 1244002 | 84.74% -> 89.40% | 62.92% -> 86.54% | 18.50% -> 10.81% |
| 1244003 | 84.89% -> 89.61% | 62.45% -> 85.61% | 18.72% -> 11.49% |

Corrected play recall spans 74.09%-82.42%; this is a real precision/recall
tradeoff, not a claim that `-log(8)` is the final threshold.  It does show that
the raw decoder was wrong in the same direction for every seed.

The natural validation play rate is 11.94%, so the exact prior correction is
slightly conservative while the two-parameter held-out fit is better calibrated
in aggregate.  The correction is nevertheless the right no-fit diagnostic.  A
fresh model should train timing on natural chronological frequencies and use
head-specific sampling only for conditional card/tile losses; it should not
need this inversion at all.  Any intentional timing class weight must be stored
in the checkpoint contract and inverted at inference.

Most importantly, the no-training correction **does not transfer to closed
loop**.  The same four-game, paired-seat Simple screen used for the original
collapse test produced:

- balanced: 0-2, zero placements in 264 decisions;
- random: 0-2, zero placements in 713 decisions; and
- aggregate: 0-4, zero placements in 977 decisions.

The raw checkpoint also went 0-4, but placed on roughly 11% of decisions.  The
prior correction therefore reveals a sharp learner-state distribution shift:
on fixed teacher trajectories it removes false plays; on the policy's own
trajectories it falls into all-wait.  This rules out shipping a scalar bias and
strengthens the DAgger requirement.  It also falsifies any claim that the
offline 89.23% action accuracy is sufficient behavior competence.

A fixed-seed 4-row x 64-decision closed-loop bias sweep maps the cliff:

| play-logit bias | placements by row | aggregate placement rate |
|---:|---|---:|
| `0.0` | 7 / 7 / 7 / 7 | 10.94% |
| `-0.5` | 8 / 8 / 8 / 8 | 12.50% |
| `-1.0` | 0 / 0 / 8 / 0 | 3.12% |
| `-1.5` | 0 / 0 / 0 / 0 | 0.00% |
| `-log(8)` | 0 / 0 / 0 / 0 | 0.00% |

The non-monotonic `-0.5` result is not a mathematical contradiction: changing
one early decision changes every later state.  It is evidence that aggregate
cadence is a brittle emergent trajectory property here, not a threshold that
can be tuned safely from fixed rows.

Checkpoint selection compounded the mistake.  The pretrainer ranked eligible
epochs lexicographically by overall flat-action accuracy, then tile accuracy,
then weighted loss.  It did not compute play precision, false plays per true
play, Brier, ECE, or closed-loop score.  Because 88.06% of validation rows are
waits, this is not a competence objective.  Future selection must be
component-balanced and calibration-aware, with gameplay as a hard gate rather
than an after-the-fact observation.

The problem is not isolated to the offline script.  The recurrent trainer's
online StrategyBot auxiliary defaults to a 4x play weight on the same policy
timing logits.  G4 must set that path to natural-frequency likelihood (or apply
an explicit, tested importance correction); otherwise PPO and teacher losses
pull the deployed prior in different directions.  Every timing loss that
touches policy logits now belongs in the class-prior audit.

### The behavior corpus barely contained Hog or Musketeer

The 78,693-row training corpus contained 9,773 placements:

| Card | Plays | Share of placements |
|---|---:|---:|
| Ice Spirit | 1,949 | 19.94% |
| Skeletons | 1,944 | 19.89% |
| Log | 1,893 | 19.37% |
| Ice Golem | 1,883 | 19.27% |
| Cannon | 1,776 | 18.17% |
| Hog Rider | 151 | 1.54% |
| Fireball | 121 | 1.24% |
| Musketeer | 56 | 0.57% |

This was systematic, not random scarcity:

- split-lane and spell-control produced zero Hog and zero Musketeer plays;
- reactive-defense produced 4 Hog plays in 15,690 rows;
- bridge-pressure produced 13 Hog and 3 Musketeer plays;
- only balanced used Hog materially (113 plays), and it still never used
  Musketeer; and
- only slow-push used Musketeer materially (53 plays), while using Hog 21 times.

Those strategies remain useful opponents and candidate proposers.  They are
disqualified as the primary behavior teacher for Hog 2.6.

A direct four-row, 64-decision Simple trace of the selected student made this
failure visible in closed loop.  It placed 28 times: Cannon 6, Ice Spirit 8,
Fireball 2, Skeletons 4, Log 4, and Ice Golem 4.  It used **zero Hog Riders and
zero Musketeers**.  The policy did not mysteriously forget its win condition;
it reproduced the exact omissions rewarded by its dominant supervision.  A
95% conditional card accuracy on this corpus is therefore misleading.

### The old direct-Simple control is a better initializer teacher

A new direct-Simple MPS trace used the frozen rebound control across both seats,
all six strategy styles, and random.  Across the first 64 decisions per row
(896 decisions total), it placed at 6.25% and used:

- Hog Rider 14 times;
- Ice Golem 14;
- Ice Spirit 14;
- Musketeer 12; and
- Cannon 2.

Every row used Hog.  This is only a 25.6-second behavior probe and does not prove
teacher strength, but it is a substantially healthier Stage-0 distribution
than the heuristic corpus.  The same frozen family previously scored about
31-25 in a 56-game Simple matrix, so it is a low-level control rather than an
expert ceiling.

Its hazard path does not repeat the fresh student's class-weight bug.  The
checkpoint records positive weight `80.9908`, and deterministic inference
explicitly subtracts `log(weight)` before accumulating event probability.  The
retained candidate and the direct-Simple update-0 wrapper have tensor-identical
model weights; only checkpoint metadata differs.  That makes it a coherent
behavior anchor, while still requiring temperature/card-support validation
before soft-logit distillation.

A new direct-Simple DAgger probe queried that frozen control on 896 states
induced by the fresh student across seven opponent styles:

| Measurement | Value |
|---|---:|
| student play rate | 11.38% |
| frozen-control play rate | 4.35% |
| reconstructed comparable rows | 882 |
| exact action agreement | 86.51% |
| student play precision vs control | 20.59% |
| student play recall vs control | 53.85% |

The control's 39 placements were Ice Golem 25, Cannon 8, and Hog 6; the student
again used Hog zero times.  This proves the control supplies useful missing
timing/Hog corrections on learner states, but its short DAgger support is not a
complete deck curriculum.  G1 therefore needs both control-induced trajectories
(which previously exercised Hog, Musketeer, Ice Spirit, Ice Golem, and Cannon)
and a subsequent student-state DAgger wave.  Training only on either state
distribution repeats exposure bias in the opposite direction.

Machine-readable audit:
`reports/hog26_factorized_failure_audit_seed1257001.json`.

### Zero-state recurrent chunks were a real mismatch

The behavior pretrainer divided each complete episode into independent
64-decision chunks and called `model.initial_state(...)` for every chunk.  It
stored neither the preceding recurrent state nor a burn-in prefix.

When the selected checkpoint was re-evaluated as uninterrupted complete
episodes instead:

| Metric | zero-reset chunk report | continuous episode |
|---|---:|---:|
| overall exact | 84.42% | 84.13% |
| complete play exact | 26.87% | 25.61% |
| conditional tile exact | 28.74% | 27.47% |
| within two tiles | 60.66% | 61.10% |

This is not the main collapse, but the direction is consistent.  One episode's
exact accuracy fell to 58.67% while the median was 87.90%, so aggregate metrics
also conceal matchup-specific recurrent failures.

### Direct-Simple learner-state labels expose the real imitation gap

The decisive audit ran the selected student in the production Simple Gym and,
on those exact learner-induced states, queried each current tensor StrategyBot
without changing the executed action.  Each style used two paired-seat rows and
64 decisions:

| teacher style | student plays | teacher plays | play recall | exact full action |
|---|---:|---:|---:|---:|
| bridge-pressure | 16 | 46 | 34.78% | 64.84% |
| slow-push | 14 | 33 | 27.27% | 70.31% |
| spell-control | 14 | 46 | 30.43% | 64.84% |
| reactive-defense | 14 | 2 | 100.00% | 89.06% |
| split-lane | 14 | 44 | 31.82% | 65.62% |
| balanced | 14 | 46 | 30.43% | 64.06% |

Aggregate exact agreement is 536/768 = 69.79%; aggregate play recall is
69/217 = 31.80%.  The current Simple teachers choose Hog 90 times and
Musketeer 4 times.  The student chooses both zero times.  Its 86 placements
instead repeat nearly the same Cannon/Ice Spirit/Ice Golem/Skeletons/Log loop
under every style.  Against reactive-defense the direction reverses: the
teacher waits while the student overplays.

These strategies are still narrow heuristics—the style-specific card counts
are highly concentrated—so this does not promote them to expert authority.
It proves two narrower points: the old Python strategy corpus does not represent
the production Simple learner-state contract, and direct-Simple DAgger can
surface exactly the missing Hog/defense decisions.  Strategy actions belong in
the search candidate set and a bounded auxiliary DAgger arm, while the frozen
neural control remains the behavior anchor.

Machine-readable prior/strategy audit:
`reports/hog26_factorized_prior_and_strategy_audit_20260901.json`.

### Human spatial data is useful but insufficient as a complete teacher

The retained 1,000-game visual corpus contains 575 Hog identities and 151 strict
Hog placement rows in the training split.  It also has 214/74 Musketeer and
419/102 Cannon identity/strict-location examples.  This is useful supplemental
spatial evidence despite its older client vocabulary.

Only five of the 1,000 actor episodes contain all eight Hog 2.6 cards; together
they provide 377 rows and 219 observed plays.  One additional episode overlaps
seven cards and one overlaps six.  That is enough for a human-behavior holdout
and qualitative sequence audit, not enough to train the recurrent policy.

Hog placement is concentrated: six canonical tiles cover 84.77% of strict
training examples.  Defense is not: the top twelve tiles cover only 55.4% of
Musketeer, 64.7% of Cannon, 53.8% of Ice Spirit, and 34.5% of Skeleton placements.
Therefore:

- mechanics-general candidate anchors can cover Hog offense efficiently;
- a macro-only action space would impose an unacceptable defensive ceiling;
- the final policy must retain a context-conditioned full legal heatmap; and
- the older human set may supervise only validated card/tile components, never
  current timing, private state, or current-client variants.

The newer YouTube proof currently has only seven visually accepted complete
card-plus-tile events from one match.  It is a pipeline proof, not enough policy
supervision.

## Lessons from primary research

### AlphaStar: factor timing and arguments, retain supervision during RL

[AlphaStar](https://www.nature.com/articles/s41586-019-1724-z) used human
imitation, an autoregressive action decomposition, an explicit 128-way delay
head, separately updated action/delay/argument losses, recurrent trajectories,
a supervised-policy KL during RL, and a diverse PFSP league.  Its released
[supplementary architecture and pseudocode](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-019-1724-z/MediaObjects/41586_2019_1724_MOESM2_ESM.zip)
also show:

- the location output remained a full masked 256x256 categorical map rather
  than a small hand-written macro vocabulary;
- actor trajectories carried an initial recurrent state;
- supervised training carried final recurrent state into the following
  trajectory; and
- RL actors computed teacher logits on the student's observations/actions.

Transferable lesson: split timing/card/location and keep a behavior teacher on
student-induced states.  Non-transferable lesson: AlphaStar's enormous network,
16,000 actors per player, and full league scale are not a sensible first Clasher
experiment.

### OpenAI Five: PPO can work, but only at a scale we have not approached

[OpenAI Five](https://openai.com/index/dota-2-with-large-scale-deep-reinforcement-learning/)
established that recurrent PPO/self-play can solve a long-horizon competitive
game.  The earlier system description reports roughly 180 years of gameplay per
day, 256 GPUs, and 128,000 CPU cores.  Its success is evidence that PPO is not
fundamentally incapable, not evidence that another short Clasher PPO run is the
best use of our budget.

### DAgger and policy distillation: use the learner's state distribution

[DAgger](https://proceedings.mlr.press/v15/ross11a.html) formalizes the compounding
error from training only on expert-induced states.  Our positive offline/negative
free-running gap is exactly that failure pattern.

[Policy Distillation](https://arxiv.org/abs/1511.06295) and
[Distilling Policy Distillation](https://proceedings.mlr.press/v89/czarnecki19a.html)
support learning from teacher distributions rather than only one-hot actions,
but also warn that the exact distillation formulation and control-policy state
distribution matter.  The retained Hog policy's unit-temperature stochastic
distribution was previously 0-8 even when deterministic behavior was usable.
Therefore its raw logits are not automatically an expert distribution.  We must
temper and validate the factor distribution before using it as a target.

### R2D2: recurrent replay needs stored state and burn-in

[R2D2](https://openreview.net/pdf/387fb2fcee8f74c53cf707a9856f40c458f33933.pdf)
found that zero-start replay sequences misestimate early values and can cause
destructive recurrent updates.  Stored state and burn-in were beneficial
together.  This applies directly to Clasher's long episodes and invalidates
arbitrary mid-game zero-state chunks as the default recurrent training contract.

### Expert Iteration and MuZero: let search discover, let the network generalize

[Expert Iteration](https://arxiv.org/abs/1705.08439) separates planning from
generalization instead of requiring one neural policy to do both.  That is the
right lesson for a project with an exact simulator and a weak behavior prior.

[MuZero](https://www.nature.com/articles/s41586-020-03051-4) is not the right
implementation: learning dynamics we already possess would add unnecessary
error and complexity.  Search-guided policy/value targets are the useful part.

### IQL and conservative policy iteration: constrain improvement to evidence

[IQL](https://arxiv.org/abs/2110.06169) avoids evaluating unseen actions and
extracts a policy through advantage-weighted behavioral cloning.  Clasher can
make this better posed by actively adding simulator-evaluated candidate actions
to the dataset.

[Conservative Policy Iteration](https://homes.cs.washington.edu/~sham/papers/rl/aoarl.pdf)
and [Safe Policy Iteration](https://proceedings.mlr.press/v28/pirotta13.html)
motivate an explicit small mixture step rather than relying on an opaque KL
penalty.  The implementation now supports:

```
pi_next = (1 - alpha) * pi_behavior + alpha * pi_improved
```

The total-variation change is bounded by `alpha`.  `alpha` must be selected from
held-out lower-confidence evidence; it is not another scalar tuned after seeing
the promotion matrix.

### IMPALA/V-trace: conditional on actor lag, not a reflexive rewrite

[IMPALA](https://proceedings.mlr.press/v80/espeholt18a.html) provides off-policy
correction for lagged distributed actor trajectories.  AlphaStar combined
V-trace with UPGO and separate factor losses.  Clasher's current optimized
Simple collector is synchronous, however, so there is no policy-lag problem for
V-trace to solve.  The first online control should retain synchronous PPO while
fixing initialization, value authority, factor losses, and teacher anchoring.
Adopt V-trace/UPGO only if multi-actor asynchronous scaling creates measured
lag; then it is a justified comparator rather than architecture cargo cult.

### Calibrated outcome distributions: do not collapse uncertainty into reward

[A Distributional Perspective on Reinforcement Learning](https://proceedings.mlr.press/v70/bellemare17a)
shows why a return distribution can contain useful information that its mean
does not.  Clasher does not need a full C51 Bellman implementation for the
first value gate: every collected complete game already supplies an exact
categorical win/draw/loss label and an exact terminal tower margin.

[Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html)
also makes the important distinction between classification accuracy and
probability reliability.  Search needs the latter.  A value that ranks held-out
games but says `0.9` on events occurring 60% of the time will systematically
overtrust shallow branches.

The first value therefore predicts a three-way terminal outcome distribution,
not discounted dense return.  A separate conditional tower-margin distribution
is an auxiliary/tie-break.  Post-hoc temperature calibration is fit only on a
frozen development split and reported by phase/opponent/seat.  Terminal branch
results always override the bootstrap prediction.

### Timing alternatives

[FiGAR](https://arxiv.org/abs/1702.06054) and AlphaStar both support making
duration/delay an explicit action output.  A discrete delay head is therefore a
real control, not a straw man.  It has two Clasher costs:

1. a blind delay can miss a newly deployed opponent threat; and
2. variable-duration transitions require semi-Markov reward/discount handling.

The continuous-time hazard stays responsive at every public observation and
preserves the existing fixed-step return semantics.  It is the lead candidate;
an interruptible delay head earns only a bounded timing A/B before any SMDP
trainer is built.

### Clash-specific external evidence

[vegetableleaf/ClashAI](https://github.com/vegetableleaf/ClashAI) independently
converged on two useful project-level choices: specialize one deck first, and
warm-start RL with imitation rather than learn live from scratch.  It also uses
factored card/location actions.  Those choices support the Hog-only G0/G1
scope.  Its current Icebow stack additionally relies on deck-specific reward
rules and runtime corrections such as Rocket auto-aim and range-aware defensive
placement.  Those can produce useful behavior, but they violate Clasher's
generalized/data-driven objective and would hide whether the network learned
the tactic.  Borrow the staged curriculum, not the card-specific controller.

The recent
[lsteno/clash-royale-complete](https://github.com/lsteno/clash-royale-complete)
DreamerV3 project reports basic success against random but instability and
negative returns against stronger opponents, with noisy semantic extraction
hurting planning.  That is Clash-specific negative evidence for learning a
world model when Clasher already owns simulator dynamics.  It reinforces the
decision to spend capacity on behavior/value/search rather than MuZero/Dreamer.

## Alternatives considered

| System | Strength | Fatal/current concern | Decision |
|---|---|---|---|
| Scale current PPO | Simple, known code | Repeatedly shifts bot wins; requires massive experience | reject as first stage |
| AlphaStar-style V-trace/UPGO | corrects lagged distributed actors; factor losses | no current policy lag; requires competent start | defer until asynchronous scaling |
| R2D2 | replay efficient and recurrent | max over 2,306 actions invites unsupported-action error | reserve control with candidate-constrained support |
| IQL/AWR | avoids unseen actions; replayable | cannot improve beyond dataset support; adds learned Q/V error | later comparator after active coverage |
| Exact-simulator Expert Iteration | directly compares consequences | branch simulation expensive; continuation-policy bias | primary label generator with value bootstrap |
| MuZero/world model | powerful planning | redundant learned dynamics | reject |
| Decision Transformer | simple offline sequence objective | no large corpus of strong winning trajectories/returns | reject now |
| Macro-only policy | fast initial competence | cannot express context-dependent defense | reject as final; proposals only |
| Pure reactive feed-forward | fast and testable | cannot preserve cycle/resource/entity continuity | diagnostic control only |
| Generic large LSTM | expressive | earlier structured memory won; inefficient and opaque | compact control only |

## Revised architecture

### State encoder

Do **not** shrink and rewrite the encoder at the same time as timing/data.  Use
the existing 128-wide, three-layer packed relational actor as the reference,
then compare a 96-wide/two-layer compact arm only after behavior reproduction.
The first bottleneck is supervision, not the 1.6M parameter count.

Exact parameter audit of the selected fresh checkpoint supports that decision:

| Component | Parameters | Share |
|---|---:|---:|
| total actor + critic model | 1,628,884 | 100% |
| actor entity encoder | 736,896 | 45.2% |
| training-only critic encoder | 539,520 | 33.1% |
| tile decoder | 132,736 | 8.1% |
| structured recurrent cell | 8,250 | 0.5% |

Removing memory cannot materially repair throughput or strategy; it is half a
percent of this model.  The deployable actor excluding critic/value is roughly
1.07M parameters.  The earlier six-million-parameter LSTM lineage is not the
architecture under diagnosis here.

Inputs remain:

- packed public entities with confidence;
- mechanics-primary card/entity descriptors plus bounded identity residual;
- own hand, Next, roster, and elixir;
- public clock/events;
- canonical lane/tower globals; and
- exact label-independent public mask.

### Model-owned state

- typed clock fallback, revealed deck/cycle, and opponent-resource interval;
- cumulative event hazard;
- stored recurrent state and a burn-in prefix for replay;
- zero versus 16 learned global residual channels as the first memory A/B; and
- a typed entity-slot tracker before vision deployment, because a global 16-way
  residual cannot reliably preserve several occluded/missed entities.

The exact-simulator competence gate may precede entity-slot integration, but no
long “deployment” lineage may skip the measured corruption/entity-memory gate.

Current source does not yet meet the first bullet when deterministic public
tracking is enabled.  `_run_memory()` stores the exact clock/card/cycle tracker
in recurrent `hidden`, but emits the separate learned `cell` as policy memory;
the tracker influences resource updates yet its revealed-card/cycle channels are
not directly available to the action heads.  The fresh implementation must
project a bounded typed tracker summary into `policy_memory` and prove nonzero
causal use.  Merely carrying correct values in serialized recurrent state is
not evidence that the actor consumes them.

### Actor

1. calibrated continuous-time competing placement/ability rates, initially
   derived from the existing timing score rather than a new timing network;
2. slot-equivariant card pointer conditional on a placement event;
3. full card-conditioned legal 18x32 heatmap;
4. optional actor-visible factorized Q over the same factors; and
5. separate privileged outcome value.

The discrete-delay control predicts a bounded next-decision delay and is
interruptible on opponent-play/entity-onset/tower-damage events.  It is not yet
eligible for RL because variable-time discount correctness is unimplemented.

## Revised data program

### Dataset roles

| Source | Allowed role |
|---|---|
| frozen direct-Simple Hog control | Stage-0 behavior distribution and rollout continuation |
| student-induced Simple states | DAgger teacher queries and policy-improvement roots |
| current tensor StrategyBots | opponents, candidate actions, and one bounded direct-Simple auxiliary DAgger arm; never sole behavior authority |
| 1,000-game older human corpus | low-weight validated card/tile prior for unchanged cards |
| new YouTube data | future current-client behavior/vision calibration after yield grows |
| simulator private state | critic/value labels only, never actor input |

### Head-specific sampling

Do not balance the full sequence by duplicating action rows; that corrupts event
calibration.

- timing/event loss: full chronological sequences at natural frequency;
- card-pointer policy loss: natural teacher play rows; stratified sampling is
  allowed only with exact inverse-propensity correction back to the declared
  teacher distribution;
- tile loss: because it is conditional on a known card, batches may stratify by
  card, threat/offense context, lane, and outcome, but natural per-card spatial
  calibration is still reported;
- value loss: complete games stratified by outcome, phase, opponent, deck, and
  seat for coverage, with likelihood weights restoring the declared deployment
  mixture before probability calibration; and
- human spatial loss: separate batches with provenance/confidence and no timing
  gradient.

Rare-card minimums are a collection gate, not a class-weight shortcut.  If Hog
or Musketeer support is low, collect more relevant trajectories/roots; do not
shift their policy logits and hope inference later recovers the intended prior.

### Stage-0 size

Start with roughly 512 frozen-control training games, 128 replay/seed-disjoint
validation games, and one 56-game paired behavior gate per seed.  This should
yield on the order of ten thousand learner placements at the observed 6.25%
short-trace teacher cadence, subject to the actual complete-game length and card
support audit.  Do not assume balance: stop collection or resample roots until
every card/phase minimum is met.  Add one student-state DAgger wave only after
the first offline fit.

## Revised learning program

### G0 — timing A/B

Common encoder/data/conditional heads:

- current independent categorical gate control;
- affine-calibrated categorical gate;
- the same calibrated score interpreted/integrated as continuous-time hazard;
- interruptible 16-bin delay head, supervised/evaluation only.

Report event NLL, Brier, ECE, precision, recall, false plays per true play,
inter-event-time error, card usage, cadence under 0.2/0.4/0.8-second observation
rates, and closed-loop control reproduction.  Hazard wins only if it preserves
behavior and cadence across rates; mathematical elegance is not evidence.

### G1 — behavior reproduction

- teacher timing from the existing positive-weight-corrected hazard bridge;
- hard executed actions plus conditional card/tile teacher factors at the
  previously admitted hazard-gated temperature `0.1` (re-gated on the new
  replay-disjoint corpus before use);
- student-state DAgger;
- stored recurrent state plus burn-in;
- exact and empirical-corruption arms;
- three seeds; and
- no policy-improvement objective yet.

Mandatory gameplay:

- no-op opponent sanity;
- random and all six strategies;
- frozen teacher;
- both seats and held-out opponent decks;
- 56 games/arm minimum.

The student must match the teacher aggregate score within one game, introduce no
bucket regression larger than one game, preserve card-usage support, and keep
3-crown/tower-damage tails no worse.  Failure rejects the architecture before
search or RL.

### G2 — outcome value

Generate complete games once and label every recurrent state with final
win/draw/loss plus terminal tower state.  Train:

- an actor-visible three-class win/draw/loss distribution;
- a privileged three-class teacher for low-variance representation learning,
  followed by explicit actor-visible distillation rather than privileged search;
- a conditional terminal tower-margin distribution; and
- multi-horizon tower-damage dealt/received prediction as auxiliary heads, not
  policy reward.

Do not regress the discounted scalar return as the principal target.  At 600
decisions the existing `0.995` discount shrinks a terminal unit reward to about
`0.049`, so local dense shaping can reverse the actual outcome ordering.  The
game-result head uses undiscounted complete-game labels.  Search utility is
`P(win) - P(loss)`; expected tower margin breaks only near-ties.  Direct terminal
branch outcomes override both.

Require held-out Brier, AUC, and calibration separately for early/mid/late game,
opponent, seat, and outcome class.  Require three independently initialized
models (or bootstrap heads) and report disagreement; high-disagreement roots
must use terminal continuation or be excluded, not confidently pseudo-labeled.
Value-guided branches are prohibited until these gates pass.

The calibration split retains the natural declared opponent/outcome mixture.
Any class-balanced training sampler must carry exact sampling probabilities and
importance-correct the likelihood.  Otherwise G2 would repeat the same omitted
prior correction that broke play timing.

### G3 — search-guided conservative improvement

Candidate set per root:

- behavior action and wait;
- spatially deduplicated top-K behavior/student actions;
- StrategyBot proposals;
- human-prior proposal where applicable; and
- seeded legal exploration.

Run 64/128-decision branches with actor-visible calibrated outcome bootstrap.
A stratified terminal subset audits rank stability.  If short/value rankings do
not agree with terminal outcomes at the predeclared rate, improve the value
model or extend horizon; never fit the policy to unstable labels.

Every candidate at a root must use the same frozen continuation policy,
opponent, post-root RNG stream, and recurrent-state fork.  This estimates a
one-step deviation `Q^pi(s,a)` rather than comparing different downstream
controllers.  It can miss a tactic requiring several coordinated novel moves;
that is an explicit limitation.  Iterate collection after each accepted small
policy update instead of pretending one search wave solved multi-step planning.
Use paired common-random-number branches wherever simulator stochasticity
remains, and fingerprint the complete root/action/continuation contract.

For the first iteration, do **not** fit another dense action-value head.  Use the
observed branch utility (terminal outcome when available; otherwise calibrated
G2 bootstrap) directly in the behavior-weighted candidate target, then apply
explicit conservative mixing.  This avoids extrapolating values to the other
roughly 2,300 actions.  A factorized Q/IQL arm is a later comparator and may
train only on explicitly evaluated candidates.

Compare `alpha` values on frozen development roots once; lock the selected
alpha before gameplay.  Choose the largest alpha whose paired
improvement-minus-regression lower confidence bound is positive.  Do not
interpret `alpha` itself as a statistical safety guarantee.

Initial evidence floor:

- at least 1,000 unique train roots;
- at least 300 replay/seed-disjoint validation roots;
- all opponent styles, seats, phases, and learner play/wait states;
- candidate coverage and outcome-class diversity reported; and
- a terminal-audit subset large enough to bound improvement-minus-regression.

### G4 — online control and league

Run bounded synchronous PPO from the G3 winner with:

- split event/card/tile losses;
- frozen-teacher factor KL;
- recurrent stored state plus burn-in;
- stratified fixed/historical opponents; and
- rollback after every bounded phase.

If actors later collect with stale parameters, add a measured policy-version
lag histogram and compare V-trace/UPGO.  Do not introduce it while collection
is synchronous.

Only a model already above the frozen teacher starts self-play.  Weak-vs-weak
self-play is not a curriculum.

## Compute implications

Local MPS is suitable for unit math, corpus audits, small fits, and occasional
behavior traces.  The 14-row/64-decision direct-Simple card-usage trace took
about 90 seconds; a two-row no-op game remained unfinished after 128 decisions
and was deliberately stopped.  Broad local gameplay is not a productive inner
loop.

CUDA should be used in stages:

1. collect Stage-0 direct-Simple trajectories;
2. train/evaluate the timing A/B;
3. stop unless G1 reproduces the control;
4. generate complete outcome/value games;
5. stop unless G2 calibrates;
6. only then spend on branch search.

Do not fund a long PPO continuation or thousands of terminal branches before
the cheaper gates pass.

## Immediate implementation changes

1. Freeze the 0-4 factorized students as diagnostic controls; do not repair
   them with another scalar bias.
2. Build a direct-Simple factor-trajectory collector that stores initial
   recurrent state and burn-in context, and collect the frozen neural teacher
   plus a bounded tensor-strategy auxiliary arm.
3. Train timing on natural chronological frequency (`play_weight=1`); sample
   card/tile conditionals separately.  Persist any future class weights in the
   checkpoint and add an exact inverse-prior regression test.
4. Keep the continuous-time module and legacy hazard bridge as a G0 arm.  Fit
   any affine calibration on train only and test both categorical and
   cumulative-hazard decoding before adding a timing network.
5. Add the discrete-delay control only at the supervised timing boundary.
6. Change counterfactual policy targets from KL-only anchoring to an explicit
   conservative mixture; implemented and unit-tested.
7. Add separate timing/card/tile datasets and metrics, including per-card
   support and play precision.
8. Run the small G0/G1 package on CUDA before any further architectural work.

## Falsifiers

Abandon this program, rather than patch it indefinitely, if any of the following
holds:

- neither hazard nor delay reproduces teacher cadence across observation rates;
- a random-initialized student cannot reproduce the frozen control after one
  DAgger wave;
- actor-visible value remains uncalibrated after complete-outcome pretraining;
- candidate coverage is low or short/value rankings remain terminal-unstable;
- conservative updates still trade one fixed-bot win for another with no
  aggregate lower-bound gain; or
- empirical visual corruption destroys behavior before entity-memory exposure.

The fallback would be training-time search with the frozen policy at inference,
or choosing an easier single deck—not another threshold/head attached to the
same failed actor.
