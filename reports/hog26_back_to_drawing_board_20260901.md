# Hog 2.6 back-to-the-drawing-board decision

Date: 2026-09-01

## Decision

Stop the fresh factorized/StrategyBot-imitation lineage.  Do not run the
packaged spatial-teacher CUDA continuation.  Its purpose was to test whether the
Python development gain transferred to the authoritative Simple Gym; the broad
matched Simple result was already decisive at 0-14 for both initializer and
candidate.

The replacement is a compact continuous-time event policy trained by direct
Simple-Gym policy iteration.  PPO is not the initial skill builder.  The older
hazard-gated Hog checkpoint remains a frozen behavioral control and rollout
teacher, not a trainable parent or promotion target.

## What the headline metrics hid

The selected fresh initializer reported 84.424% exact action accuracy on its
24,256-row validation set.  That number is dominated by 21,361 repeated wait
rows (88.065% of the set):

- wait accuracy: 92.224%;
- play recall: 97.029%;
- conditional card accuracy: 96.649%;
- exact tile accuracy on play rows: 28.739%;
- reconstructed exact complete-action accuracy on play rows: 778/2,895,
  **26.874%**.

So the initializer did not learn 84% of meaningful Clash Royale decisions.  It
learned when the demonstrator waited and which card the demonstrator used, but
reproduced only about one in four complete placements.  It then placed on
roughly 11-15% of decisions and lost every authoritative Simple game.

This is not an “epochs” problem.  Longer spatial-teacher training increased
offline tile accuracy into the 50-63% range while fixed free-running breadth
fell from 9-5 at update 20 to 4-10, 7-7, 5-9, and 3-11.  More fit to the same
target made gameplay worse.

## Root-cause accounting

### 1. Wait rows were treated as ordinary repeated classifications

The useful older Hog control uses an accumulated play hazard and acts on about
7% of decisions.  The fresh model replaced that with an independent
play/wait/ability classification every 400 ms and acted around 12%.  Earlier
DAgger attempts proved that scalar weighting could not recover both parent play
recall and wait precision.

Action timing is an event-time problem.  A policy should predict a rate per game
second, not a class per model invocation.  Otherwise changing video cadence,
dropped frames, or decision interval changes policy behavior.

### 2. The spatial label was one action, not an optimality set

Many legal tiles are strategically equivalent or nearly equivalent, while
others differ by one decisive tile.  One-hot cross entropy simultaneously
penalizes valid alternatives and provides no consequence signal for a bad tile
that resembles the demonstration.  A StrategyBot action is also not an outcome
authority.

Short counterfactual rollouts did not fix this.  Only 2/9 winners agreed between
24- and 128-decision horizons; terminal continuations changed the winner again.
Outcome-first terminal labels were correct in principle, but prior repair
attempts had only dozens of roots and moved errors between matchups.

### 3. We trained on the wrong state distribution

The fresh behavior corpora came from Python simulator/heuristic trajectories.
The Python development screen was positive while the exact same policy was 0-14
in the authoritative Simple Gym.  All future skill-producing data must be
collected and labeled through the Simple Gym.  Python remains a mechanics/parity
oracle, not a policy-training proxy.

### 4. PPO was being asked to invent tactics from long-horizon outcomes

Direct Simple PPO was numerically stable, but repeatedly transferred wins among
fixed bots rather than increasing aggregate skill.  Two expanded 56-game
screens were effectively flat or worse than the frozen control.  Stability,
reward, KL, and teacher accuracy did not predict improvement.

The initial learner therefore needs counterfactual action comparisons and a
replayable off-policy objective.  On-policy PPO can be reconsidered only after a
policy already reproduces the behavioral control and the value model ranks
held-out alternatives.

### 5. Model size and generic memory are not the leading blockers

The failed fresh model was about 1.63 million parameters, not the earlier six
million.  The structured 64-channel memory had already beaten a matched LSTM in
prior gameplay.  Widening the network or restoring a dense LSTM would not repair
the timing, target, state-distribution, or objective defects above.

## What is discarded

- Python-backend outcome training as evidence for Simple-Gym skill.
- Exact-action accuracy as a primary behavior metric.
- One-hot StrategyBot tile imitation as the main spatial authority.
- A categorical wait label on every fixed-rate observation.
- PPO as the first consequence-learning stage.
- Local adapters, scalar thresholds, and another continuation of the retained
  or fresh checkpoint families.
- The prepared spatial-u20 CUDA gate.  Its prerequisite transfer hypothesis has
  already failed.

## What is retained

- The authoritative Simple PyTorch Gym and its direct CUDA Graph path.
- Current-client 494-token typed vocabulary, exact public mask v2, canonical
  actor projection, immutable mechanics descriptors, and private critic split.
- Packed relational entity attention and a slot-equivariant card pointer.
- A card-conditioned categorical 18x32 map as the unrestricted environment
  output; continuous XY regression remains rejected.
- Model-owned typed clock/cycle/resource state.  Learned residual recurrence is
  optional and starts at width zero or 16, not a 384-unit LSTM.
- The older hazard-gated Hog checkpoint only as a frozen behavior teacher and
  gameplay control.  Its known defects are not inherited as architecture.

## Replacement architecture

### Continuous-time competing-event policy

At each public observation the network emits two non-negative rates per game
second: placement and champion ability.  For elapsed time `dt`:

```
P(wait)  = exp(-(lambda_play + lambda_ability) * dt)
P(event) = 1 - P(wait)
```

The event probability is split by the two cause rates.  A placement event is
then factorized into a shared hand-card pointer and that card's exact legal
18x32 tile distribution.  Wait is the absence of an event, not a fifth action
class competing with four card slots.

This gives exact normalized PPO/off-policy log probabilities, gradients into
timing, and cadence invariance.  Deterministic inference integrates cumulative
hazard against a fixed survival threshold; elapsed public game time, not number
of model calls, advances it.

The first isolated implementation is `src/clasher/rl/event_policy.py`.  Its unit
gate proves normalization, legality, finite gradients, reset semantics, and
equivalent survival/trigger behavior when one interval is split into smaller
calls.

### Compact state/action encoder

The first trainable family should target roughly 0.8-1.2 million parameters:

- d_model 96, two packed actor attention layers;
- mechanics-primary card/entity descriptors plus a bounded identity residual;
- typed model-owned public tracker;
- learned recurrent residual widths 0 and 16 as the first A/B;
- continuous-time event rates;
- slot-equivariant card pointer;
- existing exact card-conditioned heatmap;
- separate privileged V and actor-visible factorized Q heads.

No architecture width increases until this family reproduces the frozen
control in closed-loop Simple games.

## Replacement learning algorithm

### Stage 0 — soft behavioral reproduction

Collect trajectories directly in the Simple Gym from the frozen Hog control,
all six strategies, and random.  Store complete recurrent histories and the
teacher's calibrated factor distributions, not only its argmax action:

- continuous-time event rate/survival target;
- conditional play/ability cause;
- card-pointer distribution;
- card-conditioned tile distribution;
- privileged outcome/value target.

Train full-sequence KL/distillation with no class weighting.  Iteratively add
student-induced states (DAgger), again retaining full teacher distributions.
The student must reproduce the control in free play before policy improvement.

### Stage 1 — terminal counterfactual policy improvement

At stratified Simple-Gym roots, evaluate a diverse legal candidate set under a
common continuation policy:

- teacher action and wait;
- top-K teacher and student actions with spatial non-maximum suppression;
- strategy proposals;
- a small seeded legal exploration set.

Branches run to first terminal.  Rank first by win/draw/loss, then by terminal
tower state; dense discounted reward cannot override outcome.  Use common
randomness and replay-disjoint roots.

Train a factorized Q/V model and a KL-regularized advantage-weighted policy:

```
weight(a, s) = clip(exp((Q(s,a) - V(s)) / beta))
```

This is approximate policy iteration/IQL-style learning.  It can reuse every
root, explicitly compares alternatives, and cannot silently move the policy far
from the known behavioral control as PPO did.

### Stage 2 — iterative league improvement

Only after held-out action ranking and closed-loop reproduction pass, alternate:

1. collect current-policy roots against stratified fixed bots and historical
   policies;
2. branch candidate actions to terminal on CUDA;
3. update Q/V and the advantage-weighted actor;
4. freeze a candidate;
5. run paired gameplay gates before it can become the next continuation policy.

Human video data supplies a behavior prior and later calibration/OOD evaluation;
it is not required to prove the new learning loop on Hog 2.6.

## Hard gates

### G0 — mathematical contract

- action probability sums to one at float tolerance;
- illegal actions have exactly zero mass;
- survival over 0.4 s equals survival over two 0.2 s observations;
- deterministic trigger time is invariant to the same cadence split;
- timing/card/tile gradients are finite;
- hand permutation and canonical seat tests remain exact after integration.

### G1 — behavior reproduction

- three seeds;
- event-time NLL, event calibration, conditional card accuracy, and within-one/
  two-tile metrics reported separately—no aggregate exact metric;
- deterministic placement cadence within one percentage point of the control;
- at least 56 paired Simple games per arm;
- student aggregate score no lower than control, no opponent bucket more than
  one game worse, and no 3-crown-rate regression.

Failure here rejects the architecture before counterfactual collection.

### G2 — counterfactual authority

- at least 1,000 unique training roots and 300 replay/seed-disjoint roots before
  fitting an improvement policy;
- every branch reaches first terminal;
- held-out best-outcome ranking, pairwise AUC, Brier/calibration, and candidate
  coverage are reported;
- improvement/regression counts use paired confidence bounds;
- no short-horizon or dense-reward label can override terminal outcome.

### G3 — gameplay promotion

- three independent training seeds;
- paired seats, decks, roots, and environment seeds;
- random plus all six strategies, frozen control, and held-out deck variants;
- positive aggregate score lower confidence bound;
- no worse worst-opponent result and no materially worse defense/tower-damage
  tail;
- only then expand beyond Hog 2.6 or add learned residual memory/search.

## Immediate implementation order

1. Integrate the continuous-time distribution behind a fresh-only config; do
   not alter legacy checkpoint behavior.
2. Add full-factor teacher export from the frozen control on direct Simple
   trajectories.
3. Train the compact zero-residual and 16-residual students and run G1.
4. Only a G1 survivor earns CUDA terminal-root collection and G2.
5. Do not buy a long training run until G1 proves the new actor can at least
   preserve known gameplay.
