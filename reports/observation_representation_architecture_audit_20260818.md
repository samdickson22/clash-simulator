# Clasher observation and card/entity representation audit — 2026-08-18

## Scope and evidence anchor

This is a read-only architecture audit for the fresh live-play lineage. It does
not promote a checkpoint or authorize training. The production checkout was
already heavily modified/untracked, so the audit changed no production source.

Evidence was bound to:

- repository HEAD `20cc861b23937ec884fc22335c62d5b03a027f51`;
- retained structured checkpoint
  `checkpoints/fresh_structured_causal_v1_seed1062701/resource_belief_gated_seed1063602/resource_u10_gate0.pt`,
  SHA-256 `3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88`;
- source SHA-256 values:
  - `model.py`: `28899a84e7e34c14ddf7b54824e16cb149ece260b9e6f3218e37fd5f01145944`;
  - `structured_obs.py`: `a1b2d391b612d62069f5eaeba45b4f2098f1a8bcc06322eb0a4b6426a2a756a5`;
  - `card_semantics.py`: `706522955f31fbed2ad6e88beb01c548d527742fe00db8a4b1b32163bcf615c4`;
  - `public_observation.py`: `274c137f62b8d75cdbf148b6e267592d385f91434621a46c2dfb5b5882cd06fa`;
  - neutral projection audit script:
    `e7bf8c751d7f292f4e4d58dd639079743e5a1ed1067496e096684d9a057f7527`.

The retained checkpoint config is a 1.54M-parameter, 128-wide, three-layer
global-attention actor with 128 entity capacity, five visible card tokens,
hybrid identity/mechanics input, semantic schema v3, confidence-aware causal
frame input, and 64-channel structured memory. Important config values are
`canonical_lane_globals=false`, `actor_current_hand_slot_invariant=false`, and
`public_history_slots=0`.

## Executive decision

Keep a structured entity/card policy with global relational attention and an
18x32 categorical placement surface. Rebuild the fresh lineage around six
representation corrections instead of further patching the retained weights:

1. use one absolute neutral match state and two actor projections, with exact
   180-degree actor-one canonicalization including left/right tower globals;
2. build a current-client, variant-aware vocabulary rather than a deck-local
   frozen vocabulary;
3. use model-owned mechanics as a primary compositional stream and a learned
   identity residual as the exception stream, rather than summing an
   identity-dominated embedding and hoping similarity survives;
4. represent spawned payloads compositionally by source card plus typed subtype;
5. separate current measured dynamic values from model-owned immutable card
   knowledge, with explicit confidence/missingness;
6. pack all detected entities without silent truncation and retain global
   attention as the quality control.

These are fresh-lineage decisions. Retrofitting them into a recurrent policy
that already depends on the old representation has repeatedly produced offline
wins and complete-game regressions.

## R1. Neutral spectator state to actor projection

### Current design

The new audit schema stores one neutral record in `absolute_world` coordinates,
both players' private HUD-derived state, and offline-only evidence. It creates an
actor projection containing public state plus only that actor's hand, Next card,
and elixir. Both actor projections share one `split_group_id`.

The neutral projector intentionally does not rotate pixels or world coordinates.
Downstream canonicalization is delegated to:

- `StructuredObservationBuilder._canonical_position`, which maps actor-one
  continuous points to `(18-x, 32-y)`;
- `_canonical_vector`, which negates direction for actor one;
- `DiscreteTileActionSpace`, which maps actor-one action tiles by
  `(17-x, 31-y)`.

### Concrete correctness defect

The retained checkpoint declares `canonical_lane_globals=false`. Therefore its
actor-one entities rotate 180 degrees, but the scalar `own_left_tower_hp`,
`own_right_tower_hp`, `enemy_left_tower_hp`, and `enemy_right_tower_hp` fields
retain source-world left/right labels. The source contains the corrected option
and a direct test, but the checkpoint uses the legacy semantics.

This is not a harmless naming issue: a low-HP tower can appear on canonical
right in the entity table while its scalar appears in the canonical-left slot.

### Decision

All fresh neutral two-actor data and all fresh simulator data must use
`canonical_perspective=true` and `canonical_lane_globals=true`. Do not rewrite
the retained checkpoint in place; it learned the legacy convention.

### Smallest exact gate

Construct asymmetric neutral states with distinct HP in all six towers, one
moving entity per lane, one projectile, one area effect, and deployments on all
four arena corners. Project both actors and require:

- exact team-role swap;
- exact continuous position/vector rotation;
- exact left/right tower scalar swap;
- every one of 576 tiles round-trips through actor-specific encode/decode;
- identical canonical tensors for a battle and its fully rotated/team-swapped
  counterpart;
- no opponent private HUD fields in either actor payload;
- both actor projections remain in the same split.

Any mismatch is a data-contract rejection, not an A/B tradeoff.

## R2. Vocabulary and current-client coverage

### Current design and risk

The retained checkpoint has 155 token identities, derived from 66 cards across
33 configured decks plus reachable spawned payload names. The packaged loader
currently exposes 171 definitions. `RoyalGiant` exists in the authoritative
definitions but not in the configured deck set and is absent from the retained
checkpoint vocabulary. An unseen card therefore collapses to `<unknown>`.

Vocabulary traversal also deliberately skips `evolvedSpellsData` and
`heroData`. That was defensible for the old enabled-deck gym, but it is not a
complete 2026 video/live-play representation. Evolutions, heroes/forms, and
newly introduced cards can have materially different mechanics and visuals.

### Decision

Freeze a new vocabulary manifest from the exact current-client card catalog and
the complete playable/deployable/spawned closure before H100 extraction or fresh
policy training. Encode base card, variant/form/evolution, and spawned subtype
explicitly. Do not silently alias a mechanically different evolution or form to
the base token and do not silently map a current card to `<unknown>`.

### Smallest gate

- Inventory every card/variant/payload found in the permitted YouTube corpus
  and current simulator closure.
- Require zero `<unknown>` card actions and zero `<unknown>` known entity bodies
  on the held-out canary after manual identity adjudication.
- Hold out complete card identities and complete variants from policy training;
  evaluate zero-shot mechanics transfer and later few-shot adaptation.
- Reject the vocabulary if aliases collide between genuinely different payloads
  or if adding a new card reindexes existing IDs without an explicit migration.

## R3. Learned identity versus immutable mechanics

### Current design

Each card/entity token is the sum of:

1. a learned 128-dimensional identity embedding;
2. a learned projection of 16 immutable public base mechanics;
3. for semantic v3, a learned residual projection of 20 additional mechanics;
4. entity dynamics or card-slot embedding;
5. a token-kind embedding.

The 16 base mechanics include elixir, kind, HP, damage, range, sight, speed,
hit speed, deploy time, collision radius, summon count, and target planes. The
v3 extras include DPS, building-only targeting, flight/projectile/area/death
payload/control/spawn mechanics, radius/duration, damage modifiers, and mass.
These tables are checkpoint buffers: they are model-owned at inference, not an
external runtime database.

### Existing causal evidence

The old architecture tournament rules out a simple slogan:

- identity-only attention beat matched hybrid on seed 1041001, then failed to
  repeat on seed 1041002 and was rejected;
- replacement semantic-v2 improved its local split but regressed independent
  chronology from 10.7369 to 12.4574 joint NLL and 22.29% to 21.79% type
  accuracy;
- the zero-initialized v3 residual and its 20-update outcome-grounded pilot made
  microscopic likelihood changes but failed strict discrete no-regression;
- mechanics-only linear probes showed real compositional transfer: mean
  conditional slot agreement was 86.77% on disjoint procedural validation,
  84.36% on whole held-out archetypes, and 49.41% on public human placements,
  versus the incumbent's 45.05% human accuracy. The report explicitly binds
  this to Giant/Royal-Giant-like transfer;
- conservative blends and later 120/260-game adaptations were not repeatably
  promotion-safe.

Thus immutable mechanics contain useful transfer signal, but adding a global
residual to an established identity policy has not converted that signal into
better complete games.

### Checkpoint geometry probe

A direct read-only probe of the retained checkpoint shows why the current
hybrid is not yet a strong similarity representation:

- mean learned identity norm across non-special tokens: `11.23`;
- mean base-mechanics projection norm: `2.20`;
- mean semantic-v3 projection norm: `0.81`;
- Giant/Golem identity cosine: `-0.192`, combined-token cosine: `-0.059`;
- Hog Rider/Royal Hogs identity cosine: `-0.218`, combined-token cosine:
  `-0.024`;
- Knight/Mini P.E.K.K.A identity cosine: `0.046`, combined-token cosine:
  `0.187`.

The mechanics projections themselves place related examples very close (for
example base-projection cosines `0.996` Giant/Golem and `0.999` Hog/Royal Hogs),
but the much larger nearly orthogonal identity vectors dominate the summed
token. Similarity exists as a side contribution; it does not organize the final
card space.

### Decision

Retain both sources of information, but do not repeat additive semantic
retrofitting. In a fresh lineage, make mechanics the shared compositional base
and identity a bounded residual for genuinely discrete exceptions. Preserve the
two streams until after their own normalization/gating so downstream layers can
choose between similarity and identity rather than receiving only their sum.

Static knowledge should be serialized inside the model artifact. Live vision
should emit card identity and current measurements; it should not supply a fresh
external stat table every frame.

### Smallest discriminating A/B

Matched fresh pretraining, three seeds, same parameter count within 5%:

- control: current summed hybrid token;
- candidate: normalized mechanics tower plus learned identity-residual tower,
  fused by a learned gate; initialize unseen-card identity residuals to zero;
- optional third arm only if the first candidate is promising: add a
  role-aware contrastive/metric auxiliary loss, never a direct policy-logit
  residual.

Predeclare entire card identities and archetypes that never appear in training.
Report common, rare, and zero-shot cards separately.

Promotion requires, on every seed:

- no worse held-out play/no-op Brier and ECE;
- no worse conditional card accuracy and NLL on common cards;
- material gain on rare and completely held-out cards;
- no worse within-one/two-tile placement by troop/building/spell;
- no worse complete-game crowns, worst workload, defense-event success, and
  per-win-condition utilization;
- embedding-neighbor quality is diagnostic only and can never promote a model.

Reject if mechanics gains disappear across seeds, if common-card identity
exceptions regress, or if offline transfer again produces passivity/overplay in
complete games.

## R4. Spawned entities and compositional identity

### Current design and risk

Cards, spawned troops, projectiles, and area effects share one flat token ID
table. The builder keeps aliases and canonical names distinct, and some spawned
payloads have no standalone card definition. Those tokens receive zero immutable
mechanics and must learn almost entirely from a sparse identity embedding.

This is weakest exactly where new-card transfer matters: Archer arrows, Royal
Hogs' individual Royal Hog bodies, death spawns, projectiles, and temporary area
objects are related to a source card but can become unrelated random IDs.

### Decision and A/B

Represent an entity as `(source/base card, typed subtype, variant/form)` plus
current dynamic measurements. The subtype may be troop, spawned child,
projectile, persistent area, building, or decorative/unsupported. Preserve a
learned payload residual only where required.

Smallest A/B: hold out complete spawned payload IDs while retaining their base
card mechanics and subtype. Compare flat IDs against compositional IDs on
entity reconstruction and policy gameplay for spawn-, projectile-, and
death-payload-heavy decks. Reject if composition merges payloads with different
targeting/damage/control behavior or regresses ordinary decks.

## R5. Dynamic entity feature schema

### Current design

The legacy entity row has 32 values: normalized position, relative team, five
entity kinds, HP, shield, flight, deploy/status/movement/attack flags and
timers, base speed/range/sight/collision, facing/motion, effect progress, base
damage, and tower activation.

The current causal public contract correctly zeros unavailable engine clocks and
pairs every input with explicit confidence. However, it still allows base speed,
range, sight, collision radius, and damage to be filled externally after visual
identity detection. Those values duplicate the model-owned card descriptor
stream and make the meaning of one dynamic feature position depend on an
external identity lookup.

### Decision

For the fresh model, separate three schemas:

- current measured values: position, team, kind, visible HP/shield, motion,
  visible state/onset cues, and their confidence;
- model-owned immutable identity/mechanics: cost, speed, range, targeting,
  damage, collision, mechanics and subtype;
- privileged critic-only engine truth: exact timers, hidden objects, targets,
  RNG, opponent private HUD, and exact masks.

Do not duplicate immutable mechanics inside every current entity measurement.
This also makes simulator, video, and live inference use the same actor schema.

### Smallest A/B

Train the fresh hybrid candidate with and without the five externally supplied
static entity fields, keeping the internal descriptor tower in both. Evaluate
clean simulator, confidence-degraded simulator, held-out video, and detector
identity corruption. Promote removal if clean behavior is preserved and
cross-domain/corruption performance improves; reject if dynamic transformations
require a value not recoverable from internal identity plus current measurements.

## R6. Confidence and missingness

### Current design and evidence

The public schema enforces finite confidence in `[0,1]`, zero values whenever
confidence is zero, and zero confidence on padding. The encoder adds
zero-initialized learned uncertainty residuals for entities, globals, and cards.

The retained checkpoint did learn nonzero entity/global uncertainty outputs
(final-layer norms `1.364` and `0.950`), but its card-confidence final weight and
bias remain exactly zero. It therefore ignores hand/Next confidence: a
low-confidence wrong card ID enters with the full learned card embedding.

This is material because current-frame Next matching was explicitly low
confidence, while prior public-state extraction measured only about 56--57% HP
coverage and 39--40% motion coverage.

### Decision

Confidence must affect the information path, not merely add an optional
residual. Test a confidence mixture between known-token and learned-unknown
representations, plus calibrated token dropout/identity-confusion augmentation.
Keep raw confidence as an additional input so the policy can still distinguish
missing from weak evidence.

### Smallest A/B and gates

On identical clean and corruption-matched sequences:

- control: current additive uncertainty residual;
- candidate: `confidence * observed_token + (1-confidence) * unknown_token`
  before the card/entity fusion, with explicit confidence retained;
- corrupt hand/Next identity, entity identity, HP, position, and missing entity
  rates independently according to measured extractor confusion matrices.

Require unchanged clean gameplay within paired no-regression bounds, monotonic
degradation as confidence falls, better action calibration under corruption,
and no sensitivity to arbitrary zero-filled missing values. Reject any candidate
that simply becomes passive whenever confidence is imperfect.

## R7. Hand, Next card, and own deck

### Current design

The actor receives four current hand IDs plus one distinct Next-card token. It
does not receive its full known eight-card deck. The first four card tokens use
separate learned physical-slot embeddings; the Next token uses the fifth slot.
The separate action audit has already established severe physical-slot shortcuts
and rejected post-hoc hard-invariance repairs.

### Decision

- Keep hand order only as an action-addressing fact, not a card-semantic fact.
- Keep Next distinct from the four playable cards.
- Give a multi-deck agent its own eight-card roster once at model reset (or bind
  a fixed-deck model's initial state to that roster). A player knows its own deck;
  forcing the policy to rediscover it after cycling cards is unnecessary partial
  observability.
- The roster initialization must be inside the serialized model/session state,
  not a Python match-history accumulator.

### Smallest A/B

Compare current hand+Next against hand+Next plus an unordered own-roster summary
on entirely held-out deck combinations. Keep current card identities and action
targets identical. Require better early-match value/card-choice calibration and
no new deck-signature memorization: entire archetypes and card combinations must
remain held out. Reject if the roster acts as a replay/deck leakage key rather
than improving compositional generalization.

## R8. Entity packing, padding, and truncation

### Current design and evidence

Entity rows are deterministically sorted but entity tokens have no row-index
embedding, so global attention is permutation equivariant over the entity set.
Padding is excluded by the attention mask. More than 128 live entities raises
`EntityCapacityError`; visible entities are never silently discarded.

Historical sequence widths were median 13, 95th percentile 20, and maximum 50.
Trimming 128 trailing slots to the active batch width preserved behavior and
improved the persistent attention actor path about 21% and production imitation
training about 1.45x. DeepSets alternatives were faster but failed behaviorally:
the strongest pooled candidate no-op'ed on 97.60% of playable decisions and
lost all 24 matched held-out games.

### Decision

Retain global entity attention as the quality control. Use packed/trimmed active
width everywhere practical. Keep 128 as a fail-closed schema ceiling until the
new 2026 corpus reports p99/max counts; never replace overflow with arbitrary
nearest/top-K truncation.

### Smallest gate

- Record raw detections, deduplicated entities, and actor token counts per frame
  across the canary and a crowded-event oversample.
- Require zero overflow and zero entity loss in accepted examples.
- Compare dense and trimmed/packed forward paths on full logits, values, action
  choices, and recurrent state; behavioral decisions must match exactly and
  numerical drift must remain below a declared tolerance.
- A cheaper encoder can advance only after multi-seed complete-game gates, not
  from NLL or throughput.

## R9. Attention topology and relational scope

Self-attention is global: global, card, and every valid entity token can interact
with every other valid token. Only padding is masked. This is appropriate for
cross-lane defense, support relationships, spell clusters, and target geometry.
The claim that the current attention is local is false.

The tile decoder then cross-attends all actor tokens for every canonical tile,
and card-conditioned queries score the 18x32 surface. Keep this as the spatial
control. If H100 profiling later justifies sparse attention, the smallest safe
candidate is spatially biased global attention (global/card tokens remain
global; entity pairs get relative-position bias), not a hard locality mask that
can erase the other lane.

## R10. Ranked experiment roadmap

1. **Correctness before learning:** enable canonical lane globals in every fresh
   neutral/simulator projection; exact two-actor symmetry and privacy gates.
2. **Current-client vocabulary closure:** all playable cards, evolutions/forms,
   and spawned payloads; zero unknown action/body rate on the canary.
3. **Typed neutral-to-actor adapter:** convert decoded absolute state into the
   exact policy schema and keep both actors in one split. The current audit
   script validates JSON structure but does not yet materialize final tensors.
4. **Confidence/corruption audit:** especially hand/Next, because the retained
   checkpoint's card-confidence branch is inactive.
5. **Fresh card representation A/B:** summed hybrid versus mechanics-primary
   two-stream plus bounded identity residual, on held-out cards/archetypes.
6. **Spawned-payload composition A/B:** source card plus subtype versus flat ID.
7. **Own-roster initialization A/B:** only after the basic live schema passes.
8. **Packed global-attention optimization:** retain exact entity coverage and
   complete-game quality.

## Universal promotion and rejection rules

Every representation candidate must disclose parameters, latency, corpus and
split hashes, cumulative examples/transitions, seeds, and trainable scope. The
minimum evidence is:

- three seeds;
- replay-, deck-, archetype-, chronology-, and card-identity-disjoint metrics;
- play/no-op NLL, Brier, ECE, recall, and natural-duration weighting;
- conditional card choice and per-card frequency buckets;
- troop/building/spell placement NLL and within-one/two-tile accuracy;
- confidence-corruption curves and zero-missing invariance;
- exact perspective/slot/entity-set structural audits;
- matched complete games against random, balanced, reactive-defense,
  bridge-pressure, slow-push, spell-control, split-lane, Hog/win-condition, and
  held-out decks;
- crowns, paired outcome improvements/regressions, playable no-op, defense-event
  success, and per-card utilization.

Immediate rejection conditions are private-state leakage, actor-projection
inconsistency, silent entity truncation, unknown current card actions, failed
current-client variant coverage, non-monotonic confidence behavior, or any
offline improvement paired with a material complete-game regression.

