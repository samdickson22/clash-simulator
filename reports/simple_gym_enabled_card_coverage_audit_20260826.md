# Simple Gym enabled-card coverage audit (2026-08-26)

## Scope and method

This is a read-only structural audit of the 66 unique cards in `decks.json` at
commit `8d77c6d1`. `TensorCardCatalog` and `FastCardCatalog` were compiled with a
real `CardDataLoader`, first for the enabled-card union and then for all 171
public card definitions. No long interaction matrix or simulation was used.

The admission contract in `FastActionKernel` is deliberately small:

- every known troop, building, or champion with `FastCardCatalog.kind >= 0` is
  admitted as an entity;
- a spell is admitted when `effect_kind >= 0`;
- champion abilities fail closed;
- admission does **not** check whether a nonzero effect or the card's defining
  mechanics are represented.

## Inventory result

- 52 entity cards are admitted.
- 7 of 14 spells are admitted and 7 fail closed.
- Primitive assignment across all 66 cards is 26 direct, 30 projectile, 1
  area, and 9 unsupported (the 7 closed spells plus Skeleton Barrel and
  Tombstone).
- 59/66 cards are therefore action-mask admitted, but that number is not a
  mechanics-coverage claim.
- Multi-summon represents a homogeneous numeric ring. It covers Archers, Bats,
  Guards, Minions, Royal Hogs, Skeletons, Spear Goblins, and Wall Breakers at
  their serialized counts. Goblin Gang silently emits only its three stab
  goblins and drops the serialized three Spear Goblins.
- Lifetime is represented for Bomb Tower, Cannon, Inferno Tower, Tesla,
  Tombstone, and X-Bow.
- Ice Spirit has the one supported combat status: a radius-1.5 stun/freeze for
  24 ticks plus source consumption. Slow exists in the effect kernel but no
  enabled card currently compiles to it.
- Standalone shield/charge tensor primitives exist, but `SimpleGymRuntime`
  does not own, initialize, or call them. They therefore provide zero current
  enabled-card runtime coverage.

## Complete 66-card classification

The following partition lists every enabled card exactly once. “Baseline” is
only a card-shape judgment inside the current straight-line approximate combat
model; it is not scalar-Python parity or real-game acceptance.

### Baseline primitive is useful (23)

Archers, Arrows, Baby Dragon, Bats, Bomber, Cannon, Dart Goblin, Fireball,
Giant, Hog Rider, Ice Spirit, Knight, Mega Minion, Mini P.E.K.K.A, Minions,
Musketeer, P.E.K.K.A, Rocket, Royal Hogs, Skeletons, Spear Goblins, Wall
Breakers, X-Bow.

Important approximation notes: Arrows collapses its waves into one immediate
area hit; Fireball omits pushback; Ice Spirit approximates its jump as a homing
projectile and splash stun; Wall Breakers use projectile-impact splash plus
source consumption.

### Admitted with a useful base primitive, but defining mechanics are absent or materially wrong (31)

| Card | Represented now | Materially missing or wrong |
|---|---|---|
| Archer Queen | ranged projectile | Cloak/ability, ability mask closed |
| Balloon | building-target direct hit | death bomb |
| Bandit | ordinary direct melee | dash, dash immunity/damage |
| Battle Ram | building-target direct hit, source consumed | charge and two-Barbarian death payload |
| Bomb Tower | building lifetime and splash projectile | death bomb |
| Bowler | projectile splash | rolling line/pierce and pushback |
| Dark Prince | ordinary direct melee | shield, charge, 1.1-tile melee splash |
| Electro Dragon | first-target projectile | chain targets and stun |
| Electro Spirit | single-target projectile consumption | nine-target chain; current splash-stun is only an approximation |
| Electro Wizard | single-target direct hit | spawn zap, two-target attack, on-hit stun |
| Firecracker | first-target projectile | recoil and five-shard line explosion |
| Giant Snowball | projectile splash damage | slow and pushback |
| Goblin Gang | three homogeneous stab goblins | three additional Spear Goblins and heterogeneous child stats |
| Golem | ordinary building-target melee | death damage, two Golemites, Golemite death payload |
| Guards | three homogeneous melee units | shields |
| Ice Golem | ordinary building-target melee | death damage and slow area |
| Ice Wizard | splash projectile | on-hit slow and spawn-area semantics |
| Inferno Dragon | ordinary direct hit | per-target damage ramp/reset |
| Inferno Tower | lifetime and ordinary direct hit | per-target damage ramp/reset |
| Lava Hound | building-target projectile | six Lava Pups |
| Lumberjack | ordinary direct melee | death Rage area/payload |
| Magic Archer | narrow projectile impact | piercing line continuation |
| Mega Knight | **wrongly uses top-level `MegaKnightAppear` as every attack** | normal melee splash, spawn slam/pushback, jump/slam state |
| Miner | enemy-side placement and ordinary melee | underground travel and Crown Tower scaling |
| Night Witch | ordinary direct melee | periodic Bats and death Bat |
| Prince | ordinary direct melee | charge speed/damage |
| Princess | first-target projectile | 2.5-tile splash/multi-projectile presentation |
| Royal Ghost | ordinary direct melee | invisibility and 1-tile melee splash |
| Tesla | lifetime and ordinary direct hit | hidden/rise targetability state |
| Valkyrie | ordinary direct melee | 2-tile radial attack |
| Witch | splash projectile | periodic Skeleton spawning |

### Silent false-positive admission (5)

These should be treated as higher priority than ordinary approximation gaps.

| Card | Why admission is false-positive |
|---|---|
| Barbarian Barrel | legal projectile with zero damage; nested rolling damage and Barbarian spawn are ignored |
| Goblin Barrel | legal projectile with zero damage; three Goblins on impact are ignored |
| Log | legal projectile with zero damage; nested rolling damage, path hit, and pushback are ignored |
| Skeleton Barrel | entity deploys with zero damage and unsupported attack; it cannot complete its building impact and its two-stage death payload is unresolved |
| Tombstone | entity deploys as an inert lifetime blocker; periodic Skeletons and death Skeletons are unresolved in the enabled-only catalog |

### Explicit fail-closed spells (7)

Earthquake, Freeze, Graveyard, Poison, Royal Delivery, Tornado, Zap.

All seven serialize as `PeriodicArea`, but `FastCardCatalog` has no area-object
compiler. This is honest rejection rather than silent support.

## Death-child identity result

Nine enabled parents declare a death child: Balloon -> BalloonBomb, Battle Ram
-> Barbarian, Bomb Tower -> BombTowerBomb, Golem -> Golemite, Lava Hound ->
LavaPups, Night Witch -> Bat, Skeleton Barrel -> SkeletonContainerNew,
Tombstone -> Skeleton, and Lumberjack -> RageBarbarianBottle.

With the enabled-only catalog used by the current validation/runtime setup,
all nine child IDs are zero. Compiling all 171 public definitions resolves only
Night Witch -> Bat and Tombstone -> Skeleton. The other seven identities are
internal serialized payloads absent from the public definition registry, so
the current exact-typed lookup correctly fails closed but leaves the card
mechanic absent. A child/payload compiler must retain an explicit typed
internal identity rather than mapping it to an unrelated enabled card.

## Ranked generalized primitive work

1. **Serialized child/payload materialization.** Compile typed internal child
   descriptors and impact/death/periodic spawn commands. This cluster unlocks
   Barbarian Barrel, Goblin Barrel, Royal Delivery, Graveyard, Balloon, Battle
   Ram, Bomb Tower, Golem, Lava Hound, Night Witch, Skeleton Barrel, Tombstone,
   and Witch. It also provides the right seam for Lumberjack's death payload.
2. **Area-object/status/impulse primitive.** Add immediate and periodic area
   damage, duration/tick cadence, target-domain filters, tower/building
   multipliers, slow/stun, pushback, and attraction. This covers the seven
   closed spells plus Fireball, Giant Snowball, Ice Golem, Ice Wizard,
   Electro Wizard, Lumberjack, and Bowler without card-name dispatch.
3. **Attack topology.** Represent radial melee splash, line/piercing projectiles,
   nested projectile fan-out, and bounded chain/multi-target attacks. Immediate
   beneficiaries are Valkyrie, Dark Prince, Royal Ghost, Princess, Magic
   Archer, Bowler, Firecracker, Electro Dragon, Electro Spirit, Electro Wizard,
   and Mega Knight. Also restrict the top-level spell-projectile overlay to
   spell/explicit spawn commands so `MegaKnightAppear` cannot replace normal
   attacks.
4. **Wire existing modifier primitives into runtime.** Serialize and initialize
   shield/charge tables, intercept grouped damage, apply movement/damage
   multipliers, and reset charge on attack. This directly covers Guards, Dark
   Prince, Prince, and Battle Ram. Damage ramp is the same per-target timer seam
   for Inferno Dragon and Inferno Tower.
5. **Visibility/travel/ability state.** Add target-unavailable state and timed
   transitions for Royal Ghost and Tesla; bounded underground/dash/leap travel
   for Miner, Bandit, and Mega Knight; then Archer Queen ability ingress. These
   are important, but affect fewer deck cards than spawn/area/topology work.

## Admission recommendation

Until the first three clusters land, keep a separate data-derived
`mechanics_complete_enough` bit from entity/spell allocatability. At minimum,
fail closed for the five silent false positives and for Mega Knight's ordinary
attack when the top-level spawn projectile is the only compiled effect. This
prevents a broad “59 supported cards” number from silently training policies
against inert or qualitatively inverted card behavior.
