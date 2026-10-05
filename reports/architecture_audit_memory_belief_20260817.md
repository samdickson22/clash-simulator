# Clasher architecture audit: model-owned memory and public belief

Date: 2026-08-17  
Scope: read-only architecture decision audit; no training, checkpoint mutation, or
production-source edit performed

## Executive decision

Do not return to the 384-unit LSTM as the default, and do not make the policy
stateless. The evidence favors a **typed, model-owned recurrent state machine plus
a small learned residual**:

1. current-frame vision supplies only current public evidence and confidence;
2. deterministic model state owns clock fallback, event deduplication, revealed
   cards, cycle arithmetic, and elixir arithmetic;
3. uncertain observations update a belief/interval rather than a fabricated exact
   value;
4. entity-specific model state owns association, occlusion, HP/status carry, and
   attack/status onset timers;
5. a small diagonal/leaky residual represents tactical history that is not captured
   by the typed state.

The currently retained checkpoint is not yet that architecture. It uses the good
small structured core, but its opponent-resource estimate is deliberately gated
out and its public cycle state is absent. The newer exact public-state tracker in
the dirty checkout is a promising implementation milestone, not a trained or
promoted checkpoint.

## Current retained artifact

Retained checkpoint:

`checkpoints/fresh_structured_causal_v1_seed1062701/resource_belief_gated_seed1063602/resource_u10_gate0.pt`

- SHA-256: `3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88`
- trainable parameters: 1,536,447
- structured-memory parameters: 8,250
- persistent width: 64
- actor domain: `causal-frame-v1`
- `public_history_slots=0`, `public_seen_card_slots=0`
- opponent-resource policy gate: exactly zero
- no LSTM or GRU

Its structured cell reserves channel zero for a fixed decision-step clock and
channel one for an opponent-resource estimate. The other 62 channels are
independent input-conditioned leaky accumulators initialized over timescales from
roughly two to 300 decisions. There is no dense previous-state-to-candidate matrix.

This is materially different from a feed-forward model: it carries history, but
with a constrained update rule rather than unrestricted LSTM state mixing.

## What the deployment boundary permits

The strict current-frame contract is correct in principle. The camera side may
emit the current public observation, current clock OCR, current deployment/card
play cues, current combat/status cues, and confidence. It must not precompute
opponent history, cycle, elixir, status durations, attack clocks, or temporal
motion. Those updates must remain inside the serialized model state.

The older `CausalVisionTracker` performs external temporal association, motion,
and HUD/HP carry. It remains useful as an offline teacher, but it does not satisfy
the final self-contained deployment rule. Production experiments should use
`causal-frame-v1`, not treat `causal-vision-v1` performance as deployable proof.

The actor/critic boundary is also appropriate: the actor excludes opponent hand,
cycle, elixir, invisible objects, simulator IDs, and future information; the
privileged critic may use them during simulator training.

## State taxonomy

| Quantity | Information class | Current-frame availability | Correct mechanism |
|---|---|---|---|
| Visible game clock and phase | public | directly rendered/OCR-able | direct input with confidence; model-owned clock/timestamp fallback for gaps |
| Own hand, Next, and elixir | public to the player | directly rendered | direct current-frame input; model-owned carry only when confidence is missing |
| Visible entities, position, HP, current effect cues | public | directly detected, sometimes occluded | direct input plus model-owned per-entity temporal filter |
| Public card mechanics and elixir costs | public immutable rules | available after identity detection | frozen parameters/buffers inside the model package |
| Opponent card-play events | public | onset/deployment cue is detectable but noisy | current-frame event input plus model-owned latch/deduplication |
| Revealed opponent deck cards | public history-derived | not recoverable from one frame | deterministic model-owned set update |
| Plays until a revealed card can return | public history-derived | not recoverable from one frame | deterministic model-owned cycle counter |
| Exact opponent hand | private | not directly visible in live play | belief set/marginals over hands consistent with public history; never actor truth |
| Unseen opponent cards and initial queue | private | not directly visible | deterministic candidate set plus optional learned deck prior |
| Opponent elixir | private but history-calculable under perfect detection | not directly rendered | `start + public regen - public observed spends`, clamped at each step, all inside model state |
| Opponent elixir after missed/ambiguous plays | private and uncertain | not exactly recoverable | lower/upper interval or calibrated distribution plus confidence, not a point fabricated as exact |
| Attack/status remaining time | history-derived from public onset and known rules, with visual uncertainty | onset/presence may be visible; exact native clock is not | typed model-owned timers with uncertainty; learned residual only for ambiguous onset/association |
| Entity identity through occlusion, velocity, last HP | public history-derived | absent during occlusion | model-owned object slots/data association |
| Opponent strategic intent and multi-push plan | latent | not directly calculable | small learned residual recurrent state if gameplay A/B proves value |
| Legal play state | mostly public current state | own hand/elixir/arena occupancy visible | current-frame rule computation inside exported package; long learned recurrence is not inherently required |

### Important clarification: “possible opponent hands”

This should not mean “guess popular decks containing cards already shown.” The
rule component is a deterministic filter over states still compatible with the
public play sequence. A learned deck/archetype prior may weight those compatible
states, but must not remove rule-compatible possibilities or pretend an exact hand
is known.

The old public-history hand classifier supports this distinction. Across two
seeds, recent-four plus persistent seen cards obtained only 21.7–29.6% top-four
recall on chronology/archetype tests and essentially zero exact-hand accuracy.
Part of that is model weakness, but exact hand identity is also irreducibly
ambiguous before the initial queue and full deck are revealed. The action policy
should consume availability/marginal belief, not a brittle four-card point guess.

## Evidence about generic recurrence

### Large accepted-6M LSTM

The legacy 6.19M checkpoint has one 384-unit LSTMCell. Mechanistic probes found:

- three hidden-state principal directions explained 95.24% of general-corpus
  variance; effective hidden/cell participation ratios were 2.44/2.75;
- opponent-has-played AUC rose from 0.812 in current input to 0.999 in recurrent
  state on held-out games;
- own-elixir and play/Hog decisions were more linearly decodable from the cell;
- zeroing prior hidden/cell state changed only 0–1.01% of sampled deterministic
  immediate actions, with mean distribution TV below 0.009.

This proves the LSTM contains history, not that 384 dense units are necessary.
Removing the top three hidden PCs cannot be interpreted as “381 wasted
dimensions”: the intervention removed both historical and current-context
directions and changed two of six recorded strategy outcomes, including a matched
spell-control game from a 1–0 win to a 1–2 loss. It is a load-bearing circuit
ablation, not a clean recurrence-necessity test.

### LSTM, GRU, feed-forward, and structured comparisons

- In the older one-epoch architecture screen, the raw stateless feed-forward arm
  was slightly worse than the matched LSTM on joint/type NLL. That arm had no
  explicit public belief, so it is only a lower bound and cannot establish that
  an LSTM is required.
- The GRU was independently dominated by the corresponding LSTM in that screen.
  There is no evidence-based reason to prioritize another generic GRU sweep.
- On 128 complete held-out episodes (19,586 samples), the later 64-channel
  structured model beat the matched LSTM on joint NLL (`0.6256` vs `0.6302`),
  play recall (`60.46%` vs `57.30%`), played-card slot accuracy (`40.79%` vs
  `35.92%`), within-one-tile placement (`35.79%` vs `19.88%`), and
  within-two-tile placement (`40.23%` vs `25.22%`). It lost 1.12 points of
  action-type accuracy.
- In a matched 24-game six-strategy screen, structured scored 12–12 while the
  weights-identical causal-frame LSTM scored 2–22. This is the strongest direct
  architecture evidence, although four games per matchup is only a screen.

Decision: keep the structured family. Use the large LSTM only as an experimental
control, not as the default or as proof that generic recurrence is necessary.

## Clock, cycle, and resource findings

### Clock

The structured decision clock was effectively exact in fixed-cadence simulator
probes: 2,064 decisions, MAE `7.16e-7`, correlation approximately one. Clock is
not a reason to retain an LSTM.

However, the retained checkpoint advances by a fixed amount per policy decision.
That is fragile to variable live cadence, dropped frames, and a policy runner that
changes decision interval. The in-progress tracker improves the design by using
the current public clock observation when confident and falling back internally
when missing. The robust version should also store the prior current-frame
timestamp inside model state so fallback advances by elapsed time, not invocation
count.

### Learned resource estimate

The retained lineage’s learned resource channel is not calibrated. Its best
bounded fit reached normalized MAE `0.266` (about 2.66 elixir) and correlation
`0.064`. Opening the policy gate at 25%, 50%, or 100% failed matched gameplay;
gate zero remains the only retained behavior.

Later event/resource experiments did not solve it. On the same 2,122-decision
probe, the best update-30 event arm reported normalized MAE `0.2182` (about 2.18
elixir) and correlation `0.0428`; another reported MAE `0.2245` and negative
correlation. The entity-trace arm was worse (MAE `0.3936`, correlation `-0.125`).
These are not useful opponent-elixir estimates.

### Deterministic tracker in the current dirty source

The new `StructuredPublicStateTracker` is the right conceptual correction:

- it is parameter-free and part of recurrent model state;
- it latches/deduplicates a current-frame play cue;
- stores up to eight revealed IDs, subsequent-play counts, return-availability,
  missed-play lower bound, uncertain-event mass, and confidence;
- integrates public clock observations;
- obtains card cost from the policy’s frozen internal card-feature buffer;
- computes regeneration under single/double/triple elixir and spends once per
  latched event;
- exact tests cover duplicate cues, four-card return, missed/repeated events,
  episode reset, regen phases, cost subtraction, cap, and closed-gate behavior.

But it is currently uncommitted, has no promoted checkpoint, and has an important
policy-interface gap: `_run_memory` stores the public tracker in the returned
`hidden` state, but the action path appends only the `cell` output. Thus the
tracked card IDs/counts/availability are carried across calls but do not directly
condition action selection. They currently affect policy memory only indirectly
through the resource update. Before any training claim, expose a typed embedding
of the public tracker to the policy (preferably as revealed-card belief tokens)
behind a behavior-safe gate or train it from initialization.

The tracker also gives up point-estimate correctness after a missed event by
dropping confidence. The next representation should preserve an elixir interval
or small particle/set belief, not merely a low-confidence scalar.

## What truly needs state across frames

The minimum unavoidable state is not an LSTM. It is:

1. episode/time continuity for OCR gaps;
2. opponent play-event novelty/deduplication;
3. revealed deck and cycle bookkeeping;
4. opponent resource arithmetic and uncertainty after missed cues;
5. own HUD carry across short detector failures;
6. per-entity association through motion/occlusion and typed onset timers;
7. optionally, a learned tactical residual for intent/tempo that the above does
   not explain.

A pure one-frame feed-forward policy cannot do items 1–6 under the stated
self-contained-model rule. A generic dense LSTM is not the cleanest way to do
them. The architectural question is the size and usefulness of item 7 after
items 1–6 are explicit.

## Ranked discriminating experiments

### 1. Exact typed-state parity and exposure audit (must precede training)

Arms:

- current structured gate-zero parent;
- identical weights plus deterministic public tracker, closed policy gates;
- tracker exposed only to auxiliary prediction heads;
- tracker encoded as revealed-card tokens/resource interval but still closed to
  policy actions.

Required exact gates:

- current-frame-only inputs; no external history, cycle, elixir, motion carry, or
  reward;
- bit-identical legal actions/logits between parent and closed-gate upgrade on at
  least 128 complete recurrent episodes and fixed live-game seeds;
- under exact simulator event/clock teacher: clock error at floating-point noise,
  cycle counter/availability accuracy 100%, resource error at floating-point
  noise, duplicate event count zero, correct episode resets;
- injected duplicate, missed, ambiguous, and delayed event cases produce the
  predeclared confidence/interval behavior and never silently claim exact state;
- public cycle features are verifiably consumed when their policy gate is opened.

Reject on any external temporal input, state leakage, sequence-reset mismatch,
duplicate spend, or exact-teacher mismatch.

### 2. How much learned residual is actually needed?

Train from the same initialization/data order on complete causal sequences:

- typed deterministic state only (zero learned residual channels);
- typed state plus 16 diagonal/leaky residual channels;
- typed state plus 32 diagonal/leaky residual channels;
- current 62-channel learned residual;
- matched compact LSTM control.

All variants must receive identical current-frame observations, masks, card
buffers, critic supervision, optimizer, sequence lengths, and three seeds. Match
total non-memory width and keep total parameters within 5%, or report both
parameter-matched and compute-matched comparisons.

Small screen promotion criteria:

- 128 complete held-out recurrent episodes per seed;
- versus the current structured control: joint NLL no worse than `+0.01`,
  action-type accuracy no worse than `-0.5` percentage points, play Brier no
  worse than `+0.005`, conditional card-slot and within-two-tile accuracy no
  worse than `-1.0` point;
- 48 matched complete games (two independent four-game blocks across six
  strategies): score no lower than control, no matchup worse by more than two of
  eight, and no new near-all-play or near-all-wait failure;
- eight frozen whole-archetype held-out games no worse than control.

Reject an arm immediately if it violates the live contract, collapses play rate,
or regresses both offline proper scoring and paired gameplay. Only surviving arms
earn a larger promotion tournament.

Full promotion criteria:

- at least 240 paired games spanning the six strategies, multiple historical
  neural policies, seats, decks, and seeds;
- paired score improvement with bootstrap 95% lower bound above zero;
- at least 80 whole-deck/archetype quarantine games with score-delta lower bound
  above `-0.02`;
- no worse worst-opponent or worst-archetype score;
- recurrent proper-scoring/calibration gates above retained;
- no material latency regression at the production live cadence.

### 3. Perfect-event versus vision-event belief A/B

Evaluate the same frozen model state updater with:

- exact current-frame simulator event/clock pulses;
- held-out vision events/OCR;
- controlled event corruption matching measured false-negative, duplicate,
  ambiguity, and timestamp-error rates.

The existing serialized live-inference contract supplies initial deployment
gates: clock MAE <= 1.0 second, opponent-elixir MAE <= 0.5 elixir, cycle accuracy
>= 95%, no missing/extra predictions, placement within one tile >= 90%, HP MAE
<= 0.10, and visible-status F1 >= 0.90. Use a meaningful predeclared minimum
sample count rather than the current default of one.

Do not open resource/cycle policy gates unless the held-out vision arm passes.
If point elixir cannot meet the threshold under real missed-event rates, switch
the policy interface to calibrated intervals/quantiles and gate on interval
coverage and width rather than forcing an inaccurate point estimate.

### 4. Typed entity memory versus global residual

The current structured core is global and cannot by itself maintain stable
identity/HP/status state for multiple occluded entities. Compare:

- current-frame entities plus global structured memory;
- model-owned fixed-capacity entity slots with identity/team/position matching,
  confidence decay, velocity, HP carry, and typed status/attack timers;
- the entity-slot model plus 16 global learned residual channels.

Use simulator-generated occlusion/crossing/status-onset sequences and manually
audited video sequences. Promote only if association ID switches, position/HP
error during gaps, status F1/timer error, recurrent action metrics, and complete
games all improve without any external tracker.

## Rejected or deprioritized choices

- **Large LSTM as default:** structured recurrence already beat it directly and
  is much smaller. Keep only as a control.
- **Generic GRU sweep:** dominated by LSTM in the independent architecture
  screen; no current evidence justifies priority.
- **Pure current-frame feed-forward policy:** useful lower bound, but cannot own
  required cycle/resource/event/entity state.
- **Externally accumulated public history:** violates the final packaging rule;
  the `public_history_slots` path must remain disabled for deployment unless the
  history buffer itself moves inside serialized model state.
- **Post-hoc opening of a learned resource channel:** already failed at 25%, 50%,
  and 100% due distribution shift. Train the typed state from initialization or
  expose it gradually under proper prediction and gameplay gates.
- **Cutting the LSTM to the three PCA dimensions:** PCA variance is not causal
  sufficiency, and the top-three patch changed complete-game outcomes.
- **Exact opponent-hand point prediction:** live information is genuinely
  ambiguous; represent compatible states/marginals and confidence instead.

## Final recommendation

The next fresh model should be feed-forward **over current entity/card tokens plus
explicit recurrent state tokens**, not stateless and not driven by a monolithic
LSTM. The first state tokens should be public clock/confidence, resource
mean-or-interval/confidence, eight revealed-card/cycle slots, and a small bank of
model-owned entity tracks. Start with 16 learned residual channels and include
zero- and 32-channel arms in the matched A/B. This isolates the real question:
after the calculable game state is represented correctly inside the model, how
much latent tactical memory still improves complete-game play?

