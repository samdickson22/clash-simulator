# Simple Gym enabled-card coverage audit (refreshed 2026-08-27)

## Scope and authority

This report audits the 66 unique public roots and 33 source decks in
`decks.json` at clean commit `1a641bb81ea4d866d8923bd1c841803b24280091`.
The admission authority is `compile_standard_simple_setup` with
`canonical_lane_globals=true`. That path composes the expanded
`FastSpawnBlueprintCatalog`, policy-visibility, Champion-ability,
special-travel, triggered-impact, and atomic heterogeneous-spawn catalogs; a
bare `FastCardCatalog` is not the production admission boundary.

The frozen artifact was regenerated in memory and checked byte-for-byte with:

```text
uv run --frozen --python 3.12 python \
  scripts/build_simple_supported_decks.py --check
```

The check reported support-profile SHA-256
`9e8dbfe1edf10835bd2138f237dcc917b65dc1f44f39bc26ff221da4d6aaefab`.
A focused CPU gate covering admission plus navigation, visibility, abilities,
special travel, triggered impacts, and heterogeneous action spawns passed
**99 tests**, with **50 CUDA variants skipped** on the Mac. No full-suite,
terminal-episode, or accelerator claim is derived from that focused run.

## Authoritative admission result

- Public roots: **66/66 training-supported; 0 rejected**.
- Source decks: **33/33 training-supported; 0 rejected**.
- The committed `training_decks/simple_gym_supported_v1.json` contains all 33
  source decks and pins public-action-mask contract v2 and canonical lane
  globals.
- Public attack-plane assignment remains 27 direct, 27 projectile, 8 area,
  and 4 attack-unsupported. Barbarian Barrel, Log, Skeleton Barrel, and
  Tombstone are nevertheless admitted through their rolling or payload owners.
- All **15/15** public roots which require a defining spawn payload are
  supported. Goblin Gang is now one six-slot atomic action event with both
  typed child groups rather than a partial homogeneous deployment.
- The enabled corpus compiles 13 triggered descriptors across 11 roots, with
  zero malformed and zero duplicate profiles. All declared visibility,
  Champion-ability, and special-travel profiles in the enabled corpus compile
  successfully.

Admission means each public root has a bounded, deterministic, zero-Python-
fallback practical-Gym execution path. It does **not** establish exact live-
game mechanics, exercise every root in a terminal episode, or promote a
training backend/checkpoint.

## Former omissions closed since the previous audit

The following are runtime integrations, not admission-by-assertion:

- Archer Queen: typed ability ownership, legal simulator ability action,
  elixir/cooldown/cast/duration state, Cloak multipliers, invisibility, and
  target unavailability.
- Royal Ghost and Tesla: serialized fade/hide/rise state shared by targeting,
  secondary effects, structured observation, reset, and replay.
- Bandit, Mega Knight, and Miner: fixed-shape dash/leap/underground phases,
  interruption/immunity gates, damage, Crown Tower scaling, spawn/landing
  effects, and displacement.
- Bowler, Fireball, Firecracker, Giant Snowball, Rocket, and Tornado:
  serialized impact/recoil/impulse commands. Tornado attraction retains its
  serialized scan cadence and target-speed percentages.
- Electro Wizard and Ice Wizard: deployment-area damage/status; Ice Golem:
  death-area slow in addition to death damage.
- Goblin Gang: one all-or-nothing, stable-order deployment of three typed stab
  Goblins and three typed Spear Goblins, including capacity rollback.

Triggered integration suppresses duplicate damage where the ordinary attack,
travel, or death-burst owner already commits it. The focused runtime tests cover
those ownership seams as well as reset and deterministic replay.

## Stale omission flags

Three legacy `FastCardCatalog` diagnostics are still set at this commit:

- `Bowler.omits_displacement=true`;
- `Tornado.omits_displacement=true`; and
- `Firecracker.omits_recoil=true`.

They no longer describe production-runtime omissions. Each root has one valid
triggered descriptor, and the integrated runtime consumes it. No production
path reads either flag; they are stale catalog-local diagnostics left from the
earlier attack-only owner. Report tooling must not count them as open gameplay
gaps. Removing or redefining them remains bookkeeping debt so future audits do
not mistake them for authority.

## Complete 66-card classification

The partition below lists every enabled public root exactly once. “Useful
baseline” means this audit found no additional card-specific gap beyond the
shared physics, calibration, and evidence limits in the next sections. It does
not mean live-game equivalence.

### Useful baseline within the practical Gym (50)

Baby Dragon, Balloon, Bandit, Barbarian Barrel, Battle Ram, Bomb Tower, Bomber,
Bowler, Cannon, Dart Goblin, Earthquake, Electro Dragon, Electro Spirit,
Electro Wizard, Fireball, Firecracker, Freeze, Giant, Giant Snowball, Goblin
Barrel, Goblin Gang, Golem, Ice Golem, Ice Wizard, Inferno Dragon, Inferno
Tower, Knight, Lava Hound, Log, Lumberjack, Magic Archer, Mega Knight, Mega
Minion, Miner, Mini P.E.K.K.A, Musketeer, Night Witch, P.E.K.K.A, Poison,
Princess, Rocket, Royal Delivery, Skeleton Barrel, Tesla, Tombstone, Tornado,
Valkyrie, Witch, X-Bow, Zap.

### Training-supported with bounded card-specific approximations (16 roots)

| Card | Represented now | Remaining approximation or policy boundary |
|---|---|---|
| Archer Queen | full simulator ability lifecycle and Cloak effects | public-mask-v2 deliberately hard-masks the ability action, so the production policy cannot select the defining mechanic; this is a promotion blocker for Archer Queen policy coverage |
| Arrows | travelling target-area damage | serialized arrow waves are collapsed into one bounded impact event, losing between-wave shield/death/spawn timing |
| Archers, Bats, Guards, Minions, Skeletons, Spear Goblins, Wall Breakers | correct homogeneous count and typed bodies | ordinary multi-summons use one generalized circular formation rather than each native formation/contact relaxation |
| Dark Prince | shield, charge, ordinary bridge routing | serialized river-jump capability is not modeled; the unit routes through a bridge |
| Graveyard | serialized cast cadence and 12 typed Skeleton waves | each one-child wave uses deterministic hashed geometry on a fixed-radius ring rather than live-game spatial RNG across the area |
| Hog Rider | building targeting and ordinary bridge routing | serialized river-jump capability is not modeled; the unit routes through a bridge |
| Ice Spirit | homing impact, splash freeze, source consumption | the hop trajectory/timing is represented by the ordinary homing effect |
| Prince | charge and ordinary bridge routing | serialized river-jump capability is not modeled; the unit routes through a bridge |
| Royal Hogs | four-unit deployment, building targeting, bridge routing | serialized river-jump capability is not modeled; the units route through bridges |
| Royal Ghost | serialized fade/invisibility/targetability | `is_hover_unit` is dropped by the fast catalog, so navigation/body-plane behavior is ordinary ground movement |

Bandit, Mega Knight, and Miner now have fixed-step special-travel phases;
Bowler, Fireball, Firecracker, Golem, Giant Snowball, Ice Golem, Mega Knight,
Rocket, and Tornado now have serialized displacement/recoil commands. Their
straight-line, presentation-free travel is acceptable for the current 2-D
projection, but every one still inherits the shared lack of body collision,
mass-chain resolution, and calibrated contact physics. That shared blocker is
not counted again as a unique card omission. Archer Queen's unavailable public
action is different: it removes a policy choice and remains a direct promotion
blocker.

## Spawn and payload status

The expanded catalog uses private typed child rows which never become
hand-facing public identities. It supports, among other paths:

- Battle Ram -> two Barbarians;
- Goblin Gang -> three stab Goblins plus three Spear Goblins atomically;
- Lava Hound -> six Lava Pups;
- Golem -> death burst, two Golemites, and nested child death handling;
- Night Witch, Tombstone, and Witch periodic/death children;
- Goblin Barrel impact Goblins;
- Balloon and Bomb Tower delayed bombs;
- Skeleton Barrel's delayed container and Skeleton payload;
- Royal Delivery and Graveyard scheduled payloads;
- Lumberjack's death Rage area; and
- Barbarian Barrel's rolling terminal spawn.

Capacity rejection is explicit and deterministic. Synthetic rows require typed
entity tokens and cannot appear in public decks or actor hands.

## Remaining practical-RL promotion blockers

1. **Crown Tower combat is inert.** `standard_tower_spec` gives all six tower
   rows `card_id=0`. The combat selector special-cases those rows so they can
   acquire air/ground targets, but the ordinary effect allocator rejects every
   attack command whose card ID is not positive. A tower can therefore point
   `target_id` at an enemy while never allocating damage. King activation is
   also absent: the King row can acquire from battle start rather than waking
   on damage or Princess Tower loss. Existing standard tests cover tower
   positions/stats and terminal tests cover deterministic outcomes, but no
   current Simple-runtime test proves Princess/King retaliation. This alone
   prevents a high-fidelity combat or trained-policy promotion claim.
2. **First-hit clocks and target retention.** `TensorCardCatalog` preserves
   serialized `load_time_ms`, but `FastCardCatalog` does not carry it and new
   entities initialize `cooldown_ticks=0`. Fifty enabled attacking roots carry
   a nonzero serialized load value; 49 have a positive derived first-hit delay,
   yet an in-range Simple entity can currently attack as soon as deployment
   completes. Ordinary targeting also recomputes the nearest legal target every
   tick instead of retaining a target and applying general retarget timing;
   only the damage-ramp family has a bounded retarget-grace owner. This is a
   broad combat/DPS and focus-selection gap.
3. **Navigation and body physics.** The new retained two-bridge state machine
   prevents ordinary ground units from walking straight across the river. It
   is still not native pathfinding: placed buildings do not participate in a
   full obstacle/route graph, and the Gym lacks general collision avoidance,
   body separation, serialized mass/hover behavior, push chains, and river-jump
   travel. These are policy-visible positioning dynamics, not cosmetic
   differences.
4. **Deployment targetability.** Ordinary target selection excludes every
   entity with nonzero deployment ticks. Whether and when a deploying body can
   be damaged is policy-visible and has not been calibrated against live-game
   traces for this Gym.
5. **Public ability policy.** The simulator legal mask exposes Archer Queen's
   implemented ability, while `SimplePublicMaskV2Provider` intentionally emits
   `ability=false`. The two masks are correctly kept as different domains, but
   current production collection cannot learn to press Cloak.
6. **Current-source accelerator recertification.** The committed terminal CUDA
   and 10-launch/zero-sync throughput artifacts were produced before the
   navigation, visibility, ability, travel, triggered-impact, and
   heterogeneous-spawn integrations. They remain valid historical evidence,
   not certification of commit `1a641bb8`.
7. **Current training-stack assembly.** The isolated newer-main routing gate
   was built from an older Simple Gym source snapshot. The current mechanics
   tree has not yet been assembled, recurrent-policy tested, CUDA-tested, and
   committed on a safe stabilized-main integration branch.
8. **Real-game calibration.** The current read-only corpus gate is `fail`:
   37/37 observed regulation-to-overtime transitions are correct, but the 95%
   Wilson lower bound is 0.905942 rather than the required 0.95. Exact tensor
   public-mask equivalence and independently labelled combat trajectories, HP,
   statuses, and outcomes are unavailable. Admission and serialized values do
   not substitute for those channels.
9. **Exercise coverage.** Focused mechanic tests prove their declared seams;
   seeded terminal episodes prove only the cards/actions actually exercised by
   their policies. No current evidence establishes full free-running mechanic
   visitation over all 66 roots.

## Evidence boundary

The 66/66 and 33/33 numbers prove fail-closed admission for the current public
manifest. The 13 triggered descriptors and atomic Goblin Gang event prove
compiled ownership, while focused tests prove the exercised transition seams.
None of those facts independently proves live-game calibration, current-HEAD
CUDA performance, recurrent-policy behavior, or safe checkpoint promotion.
