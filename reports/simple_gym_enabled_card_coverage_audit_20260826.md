# Simple Gym enabled-card coverage audit (2026-08-26)

## Scope and method

This is a structural audit of the 66 unique cards in `decks.json` on the active
practical-Gym branch. `TensorCardCatalog`, `FastCardCatalog`, and the expanded
`FastSpawnBlueprintCatalog` were compiled with a real `CardDataLoader`. No long
interaction matrix or simulation was used.

The admission contract in `FastActionKernel` is deliberately small:

- every known troop, building, or champion with `FastCardCatalog.kind >= 0` is
  admitted as an entity;
- a spell is admitted when `effect_kind >= 0`;
- champion abilities fail closed;
- the separate data-derived `training_supported` plane rejects zero-payload
  effects, inert entities, and declared-but-unresolved death children; the
  legal action mask requires this plane.

## Inventory result

- All 52 entity cards and 12 of 14 spells are structurally allocatable. The
  blueprint-expanded truthful training inventory accepts 60/66 public roots.
- Training admission rejects 6: two zero-payload rolling projectiles and four
  roots with unsupported nested spawn/action payloads.
- Newly admitted since the 54-card inventory: Balloon, Bomb Tower, Night Witch,
  Skeleton Barrel, Tombstone, and Witch.
- Primitive assignment across all 66 cards is 27 direct, 29 projectile, 6
  area, and 4 unsupported (Graveyard, Royal Delivery, Skeleton Barrel, and
  Tombstone).
- The raw 64/66 allocatable count is therefore not exposed as legal training
  support.
- The 60-card count requires constructing `SimpleGymRuntime` with the matching
  expanded `spawn_blueprints`. A bare `FastCardCatalog` retains its conservative
  support plane and does not make the spawn-root claim.
- Multi-summon represents a homogeneous numeric ring. It covers Archers, Bats,
  Guards, Minions, Royal Hogs, Skeletons, Spear Goblins, and Wall Breakers at
  their serialized counts. Goblin Gang silently emits only its three stab
  goblins and drops the serialized three Spear Goblins.
- Lifetime is represented for Bomb Tower, Cannon, Inferno Tower, Tesla,
  Tombstone, and X-Bow.
- Ice Spirit retains its radius-1.5 stun/freeze plus source consumption. The
  generalized area compiler now also emits stun for Freeze and Zap and slow
  for Earthquake and Poison.
- Shield and charge primitives are now initialized and advanced by
  `SimpleGymRuntime`; their focused runtime coverage is separate from this
  broader admission audit.

## Complete 66-card classification

The following partition lists every enabled card exactly once. “Baseline” is
only a card-shape judgment inside the current straight-line approximate combat
model; it is not scalar-Python parity or real-game acceptance.

### Baseline primitive is useful (47)

Archers, Arrows, Baby Dragon, Balloon, Bats, Battle Ram, Bomb Tower, Bomber,
Cannon, Dark Prince, Dart Goblin, Earthquake, Electro Dragon, Electro Spirit,
Fireball, Freeze, Giant, Goblin Barrel, Guards, Hog Rider, Ice Spirit, Inferno
Dragon, Inferno Tower, Knight, Lava Hound, Magic Archer, Mega Minion, Mini
P.E.K.K.A, Minions, Musketeer, Night Witch, P.E.K.K.A, Poison, Prince, Princess,
Rocket, Royal Hogs, Skeleton Barrel, Skeletons, Spear Goblins, Tombstone,
Tornado, Valkyrie, Wall Breakers, Witch, X-Bow, Zap.

Important approximation notes: Arrows collapses its waves into one immediate
area hit; Fireball omits pushback; Ice Spirit approximates its jump as a homing
projectile and splash stun; Wall Breakers use projectile-impact splash plus
source consumption. Tornado preserves its damage/cadence but explicitly omits
attraction; the other newly admitted areas preserve serialized cadence,
target-domain filters, tower/building scaling, and available slow/stun state.
Battle Ram and Lava Hound now materialize their typed death children, while
Goblin Barrel materializes three typed Goblins on projectile impact. Balloon,
Bomb Tower, and Skeleton Barrel now execute bounded delayed payload containers;
Night Witch, Tombstone, and Witch execute serialized periodic waves. Chain,
line, damage-ramp, circle, multi-target, shield, and charge primitives cover
the corresponding cards listed above.

### Useful base primitive, but defining mechanics are absent or materially wrong (15)

Golem and Lumberjack are masked because their nested payloads remain
unsupported; the other rows remain admitted approximations.

| Card | Represented now | Materially missing or wrong |
|---|---|---|
| Archer Queen | ranged projectile | Cloak/ability, ability mask closed |
| Bandit | ordinary direct melee | dash, dash immunity/damage |
| Bowler | rolling line projectile | pushback |
| Electro Wizard | two-target direct hit with on-hit stun | spawn zap |
| Firecracker | five-ray impact fan | recoil |
| Giant Snowball | projectile splash damage | slow and pushback |
| Goblin Gang | three homogeneous stab goblins | three additional Spear Goblins and heterogeneous child stats |
| Golem | ordinary building-target melee | death damage, two Golemites, Golemite death payload |
| Ice Golem | ordinary building-target melee | death damage and slow area |
| Ice Wizard | splash projectile | on-hit slow and spawn-area semantics |
| Lumberjack | ordinary direct melee | death Rage area/payload |
| Mega Knight | splash melee | spawn slam/pushback, jump/slam state |
| Miner | enemy-side placement and ordinary melee | underground travel and Crown Tower scaling |
| Royal Ghost | splash melee | invisibility |
| Tesla | lifetime and ordinary direct hit | hidden/rise targetability state |

### Zero-payload rolling projectiles, masked from training (2)

These should be treated as higher priority than ordinary approximation gaps.

| Card | Why admission is false-positive |
|---|---|
| Barbarian Barrel | structurally allocatable zero-damage projectile; nested rolling damage and Barbarian spawn are ignored |
| Log | structurally allocatable zero-damage projectile; nested rolling damage, path hit, and pushback are ignored |

### Explicit fail-closed unsupported spells (2)

Graveyard, Royal Delivery.

Both declare spawned-unit/action payloads that the area kernel cannot
materialize. Earthquake, Freeze, Poison, Tornado, and Zap are newly admitted by
the generalized periodic-area compiler; spawn-bearing areas remain honestly
closed rather than silently dropping their defining payload.

### Exact blueprint-expanded support inventory

Supported public roots (60): Archer Queen, Archers, Arrows, Baby Dragon,
Balloon, Bandit, Bats, Battle Ram, Bomb Tower, Bomber, Bowler, Cannon, Dark
Prince, Dart Goblin, Earthquake, Electro Dragon, Electro Spirit, Electro
Wizard, Fireball, Firecracker, Freeze, Giant, Giant Snowball, Goblin Barrel,
Goblin Gang, Guards, Hog Rider, Ice Golem, Ice Spirit, Ice Wizard, Inferno
Dragon, Inferno Tower, Knight, Lava Hound, Magic Archer, Mega Knight, Mega
Minion, Miner, Mini P.E.K.K.A, Minions, Musketeer, Night Witch, P.E.K.K.A,
Poison, Prince, Princess, Rocket, Royal Ghost, Royal Hogs, Skeleton Barrel,
Skeletons, Spear Goblins, Tesla, Tombstone, Tornado, Valkyrie, Wall Breakers,
Witch, X-Bow, Zap.

Rejected public roots (6): Barbarian Barrel, Golem, Graveyard, Log, Lumberjack,
Royal Delivery.

### Whole-deck training coverage

The frozen supported-deck builder accepts 9/33 source decks: Pekka Bandit EWiz
Bridge Spam; MK Miner ID Bats; Giant; WB Valk Log Bait 2.8; Pekka Bandit EWiz
Poison; Hog 2.6 (Zap); Pekka Loon IWiz EDrag; LavaLoon Miner; and Giant Double
Prince. The other 24 decks contain at least one of the six rejected roots.

## Death-child identity result

Nine enabled parents declare a death child: Balloon -> BalloonBomb, Battle Ram
-> Barbarian, Bomb Tower -> BombTowerBomb, Golem -> Golemite, Lava Hound ->
LavaPups, Night Witch -> Bat, Skeleton Barrel -> SkeletonContainerNew,
Tombstone -> Skeleton, and Lumberjack -> RageBarbarianBottle.

The expanded blueprint catalog creates private typed child rows and supports
Battle Ram -> two Barbarians, Lava Hound -> six Lava Pups, Night Witch's Bats,
Tombstone's Skeletons, and Witch's Skeleton waves. Goblin Barrel has a typed
impact spawn. Balloon, Bomb Tower, and Skeleton Barrel use bounded delayed
payload containers. Golem and Lumberjack remain closed because their nested
payload shapes are not yet representable. Synthetic rows are never public hand
identities.

## Ranked generalized primitive work

1. **Remaining nested payloads.** Golem/Golemite recursion, Lumberjack's Rage
   action/container, Graveyard scheduling, Royal Delivery's action payload,
   and the rolling Barbarian Barrel/Log shapes remain fail closed.
2. **Impulse and displacement.** The periodic-area/status kernel now covers
   damage, cadence, target domains, scaling, slow, and stun. Generalize
   pushback/attraction for Tornado, Fireball, Giant Snowball, Bowler, Ice Golem,
   and spawn/death impacts without card-name dispatch.
3. **Visibility/travel/ability state.** Add target-unavailable state and timed
   transitions for Royal Ghost and Tesla; bounded underground/dash/leap travel
   for Miner, Bandit, and Mega Knight; then Archer Queen ability ingress. These
   remain the largest fidelity gaps among already admitted roots.

## Admission gains versus fidelity corrections

The increase from 54 to 60 supported roots comes only from periodic-spawn and
delayed-payload execution: Balloon, Bomb Tower, Night Witch, Skeleton Barrel,
Tombstone, and Witch. Chain topology (Electro Dragon/Spirit), line topology
(Magic Archer/Bowler), fan topology (Firecracker), and damage ramps (Inferno
Dragon/Tower) did not increase admission because those roots were already
training-supported; those changes correct the transition dynamics seen by RL.
Likewise circle/multi-target, shield, and charge work improved already-admitted
cards without changing the support count.

## Admission recommendation

The data-derived `training_supported` bit is now separate from entity/spell
allocatability and required by the legal mask. It fails closed for zero-payload
spells, inert entities, and unresolved declared death children. The loader's
top-level projectile overlay is also restricted to actual spells, so
`MegaKnightAppear` no longer replaces Mega Knight's ordinary direct attack.
This prevents the broad raw “64 allocatable cards” number from silently
training policies against inert or qualitatively inverted card behavior.
