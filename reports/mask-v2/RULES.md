# Placement rule audit

The authority for simulator acceptance is `BattleState.deploy_card`, before
`PlayerState.play_card` mutates resources. The comparison harness uses the
scalar action-space guards for all 2,304 placement bits, independently checks
the optimized mask, and exercises `deploy_card` itself in boundary tests by
intercepting its first resource mutation. No-op is a policy wait. Champion
abilities are a separate contract: v5 Python retains its own public HUD rule;
the scripted Rust policy deliberately leaves ability selection disabled.

`summary.json` includes a per-card census, normalized card aliases, and explicit
situation bins: payload present; no payload with more than six live buildings;
and no payload with at most six live buildings. The last bin can include an
ordinary building after a Crown Tower dies; it does not mean "no ordinary
building". Original human coordinates are checked at the recorded decision
opportunity using the replayer's discrete coordinate encoder. Labels after
adjacent-tile projection are counted separately. Source prefixes, alternating
learner seats and retained replay cuts define the sample; no claim of unbiased
policy-wide or corpus-wide incidence is made.

**Terrain and territory.** The command must be in bounds and outside permanent
blocked cells. Ordinary cards require the current friendly deployment zone;
destroyed enemy Princess Towers unlock the corresponding pocket and bridge.
Enemy-side-capable non-spells still obey permanent terrain and Crown Tower
exclusion. Ordinary spells are arena-wide; rolling/territory spells follow
the deployment zone; walkable-target spells additionally reject water. V1's
public candidate construction conflated arena-wide walkable spells with
territory spells. The scalar simulator's optimized mask separately omitted
unlocked bridge strips; its v2 branch now uses the arena's authoritative zones.
For buildings, the optimized v2 mask consults the actual deployment guard,
avoiding a second, potentially stale candidate-pruning cache.

**Crown Towers.** A requested non-spell position cannot lie in an alive Princess
Tower's inclusive square of half-width 1.5 or a King Tower's inclusive square
of half-width 2. This is a command exclusion, separate from ordinary building
collision. V1 used a padded generic building square/circle instead. There is
no additional general troop-versus-troop occupancy or arbitrary tower-distance
ban. Formation child relocation/tower avoidance occurs after command acceptance;
only the data-driven horizontal anchor margin is an additional rejection guard.

**Buildings.** Footprint size is `max(1, ceil(2 * max(0, radius)) + 1)`, with the
engine's missing-radius default. Every command resolves through `building_anchor`:
odd sizes use half-tile centers, even sizes world-floor to integers; blocked
terrain/river/edge footprints search the static valid anchors, with native
world-coordinate tie ordering. Strict rectangle overlap with any live building
rejects the command. Tangent rectangles are allowed. V1 normally checked the
requested point with half-tile padding; contract v5 special-cased only
enemy-side buildings. V2 resolves all buildings in world coordinates before
rotating back. The source-card-to-visible-body mapping repairs zero-radius
descriptor aliases such as GoblinHut_Rework and ElixirCollector without
changing the model's frozen semantic features.

**Visible payloads.** `blocks_deployment` is a capability on TimedExplosive,
not on every deploying troop. DeathSpawn creates these for serialized death
children with `deathDamage` and no `hitpoints`; MightyMiner's visible ability
bomb is another route. Living troops sharing the parent token are distinguished
by their public effect/body kind. Source identity determines the static radius;
the engine retains source card_stats on these effects, so assuming the token
always names the child bomb is wrong. V2 uses no hidden deployment timer.
Troop requests reject inclusive circle contact (`distance <= mover + payload
radius + 1e-9`); buildings reject inclusive circle-to-resolved-square contact.
Spells ignore these blockers. Once the engine effect expires, it stops
blocking; a lost live-camera detection alone is not proof of expiry. The six r9
failures all take this path; the original line-number-only
receipt could not distinguish the two halves of the building guard.
The [complete capability census and visibility review](BLOCKERS.md) enumerates
every current route and documents how the live actuator must handle unconfirmed
or genuinely hidden blocking phases without private inputs.

**Troops.** Ground troops first reject a payload at the requested position,
then search square rings 0..30 for a valid anchor. Candidate anchors require
walkability, all four native half-tile spawn cells clear, the applicable zone,
one-cell-versus-building footprint clearance, and payload clearance. A building
over the requested ground-troop point generally causes relocation, not rejection.
Air troops do not use that search: they reject strict integer-logic-unit
circle overlap with a live building using the full deployment radius. V1's
generic circular/padded-square test did not reproduce either rule exactly.

**Fair inputs.** V2 reads only accepted public identity, visible row membership,
body/effect kind, position, static card metadata, board orientation, own HUD
hand/elixir, public tower status and accepted own Mirror history. It neither
takes a BattleState argument nor reads an opponent hand, deck, RNG, entity timer,
combat target or engine occupancy cache. Native geometry uses the corresponding
public view and static tables; timed effect positions are decoded at the same
float32/millitile boundary. Tests alter opponent-private state and hidden status
columns without changing v2's result.

**Observed residual.** The completed 100,000-state audit has exactly 722
false-positive Cannon bits across 40 states, and no false negatives. Every bit
is explained by an enemy underground Goblin Drill omitted from the actor view:
revealing just the hidden building in an audit-only counterfactual makes those
bits agree with the engine. No counterfactual result enters the public mask,
training data or action selection. There are no unclassified observed residuals.
This is a documented exception to equality, not a passing blanket exactness gate.

**Limits requiring separate qualification.** Replay evidence does not establish
equality for camera-localized/truncated/unknown rows,
unsupported future effect identities, or delayed/simultaneous application.
An enemy underground building omitted by contract v5 is not a permissible hidden
input. Python's membership-only building cache can retain an underground Drill's
old location (documented in engine-speed/STAGE6.md); a stateless public mask
cannot reproduce that private cache history. The existing Rust engine also caps
air deployment radius at 0.5 in `apply_action`, unlike Python's full radius;
v2 public masks implement Python's acceptance rule. These engine/observation
classes need separately versioned repairs or explicit scope exclusions if
encountered. Do not weaken the public-information contract to imitate them.

**Official game check.** Supercell's [March 2019 balance notes](https://supercell.com/en/games/clashroyale/blog/release-notes/balance-update-coming-3-4-2/)
confirm Bomb Tower death damage, but publish no placement-radius specification.
A [firsthand 2021 player report](https://www.reddit.com/r/ClashRoyale/comments/ndk5e7/)
describes inability to place troops/buildings over the surviving bomb. This is
qualitative historical corroboration only. The repository's building anchor,
bank, overlap and avoidance captures derive from Null's 15.535.86, not the
official client. Neither those captures nor the web sources establish exact
official-client contact/radius/rounding parity in October 2026.
