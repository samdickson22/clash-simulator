# Simple Gym enabled-card coverage audit (2026-08-26)

## Scope and authority

This report audits the 66 unique public cards and 33 decks in `decks.json` at
clean commit `37e4fff3`. The authoritative path is
`compile_standard_simple_setup` with `canonical_lane_globals=true`, including
the expanded `FastSpawnBlueprintCatalog`; a bare `FastCardCatalog` is not the
production admission boundary.

The frozen artifact was regenerated in memory and checked byte-for-byte with:

```text
uv run python scripts/build_simple_supported_decks.py --check
```

The check reported support-profile SHA-256
`9e8dbfe1edf10835bd2138f237dcc917b65dc1f44f39bc26ff221da4d6aaefab`.
Focused support tests passed 11 tests with 2 CUDA skips. No broad CPU suite or
long simulation was run for this inventory refresh.

## Authoritative admission result

- Public roots: **66/66 training-supported; 0 rejected**.
- Source decks: **33/33 training-supported; 0 rejected**.
- The committed `training_decks/simple_gym_supported_v1.json` contains all 33
  source decks and preserves public-action-mask contract v2 and canonical lane
  globals.
- Public attack-plane assignment is 27 direct, 27 projectile, 8 area, and 4
  attack-unsupported. The four attack-unsupported roots—Barbarian Barrel, Log,
  Skeleton Barrel, and Tombstone—are nevertheless truthfully admitted through
  their separate rolling or spawn/payload runtime owners.
- All 14 public roots with defining spawn payloads are supported by the
  expanded blueprint compiler/runtime.

Admission means the root has a bounded, deterministic, zero-fallback practical
Gym execution path. It does **not** mean exact scalar-Python parity or exact
current-game mechanics.

## What closed the final six admission gaps

The previous inventory admitted 60 roots. The final six became eligible through
generalized runtime owners rather than card-name tick dispatch:

- Barbarian Barrel and Log: fixed-shape rolling paths, swept hits, damage,
  impulse, and Barbarian Barrel's terminal Barbarian spawn.
- Golem: death burst plus typed Golemite materialization and nested death
  processing.
- Graveyard and Royal Delivery: fixed-shape scheduled/delayed spawn execution.
- Lumberjack: typed death payload plus bounded positive Rage area state.

These were true admission gains. The chain, line, fan, circle, multi-target,
damage-ramp, shield, and charge integrations primarily corrected transition
fidelity for roots that were already admitted.

## Complete 66-card classification

The partition below lists every enabled public root exactly once. “Useful
baseline” means no additional card-specific omission is currently called out
by this audit; the global movement/physics limitations later in the report
still apply to every card.

### Useful baseline within the practical Gym (49)

Archers, Baby Dragon, Balloon, Barbarian Barrel, Bats, Battle Ram, Bomb Tower,
Bomber, Cannon, Dark Prince, Dart Goblin, Earthquake, Electro Dragon, Electro
Spirit, Freeze, Giant, Goblin Barrel, Golem, Graveyard, Guards, Hog Rider,
Inferno Dragon, Inferno Tower, Knight, Lava Hound, Log, Lumberjack, Magic Archer,
Mega Minion, Mini P.E.K.K.A, Minions, Musketeer, Night Witch, P.E.K.K.A, Poison,
Prince, Princess, Rocket, Royal Delivery, Royal Hogs, Skeleton Barrel,
Skeletons, Spear Goblins, Tombstone, Valkyrie, Wall Breakers, Witch, X-Bow,
Zap.

Representative mechanics now present in this group include typed impact/death
children, periodic waves, delayed payload containers, scheduled casts, rolling
spells, death bursts, Rage, chain attacks, piercing lines, damage ramps, radial
splash, shields, and charges.

### Training-supported with known card-specific approximations (17)

| Card | Represented now | Known omission or approximation |
|---|---|---|
| Archer Queen | ordinary ranged projectile | Cloak ability is closed at the ability-action mask |
| Arrows | target-area damage | serialized waves are collapsed into one bounded area event |
| Bandit | ordinary direct melee | dash travel, immunity, and dash damage are absent |
| Bowler | swept rolling line damage | pushback is explicitly omitted |
| Electro Wizard | two-target attack with on-hit stun | deployment spawn zap is absent |
| Fireball | projectile splash damage and tower scaling | pushback is absent |
| Firecracker | five-ray impact fan | recoil is explicitly omitted |
| Giant Snowball | projectile splash damage and slow | pushback is absent |
| Goblin Gang | three homogeneous stab Goblins | three heterogeneous Spear Goblins are absent |
| Ice Golem | building-target melee and death damage burst | death slow area is absent |
| Ice Spirit | homing impact, splash freeze, source consumption | hop trajectory/timing is approximate |
| Ice Wizard | splash projectile | on-hit slow and spawn-area semantics are absent |
| Mega Knight | target-centered splash melee | spawn slam/pushback and jump/slam travel are absent |
| Miner | enemy-side placement and ordinary melee | underground travel timing is absent; Crown Tower scaling needs calibration |
| Royal Ghost | target-centered splash melee | invisibility/fade targetability is absent |
| Tesla | lifetime and ordinary attack | hidden/rise targetability state is absent |
| Tornado | periodic damage/cadence | attraction/displacement is explicitly omitted |

The catalog's explicit fidelity flags currently mark Bowler and Tornado for
omitted displacement and Firecracker for omitted recoil. The table also records
important omissions that are not yet represented by a catalog flag.

## Spawn and payload status

The expanded catalog uses private typed child rows that are never hand-facing
public identities. It supports, among other paths:

- Battle Ram -> two Barbarians;
- Lava Hound -> six Lava Pups;
- Golem -> death burst, two Golemites, and nested child death handling;
- Night Witch, Tombstone, and Witch periodic/death children;
- Goblin Barrel impact Goblins;
- Balloon and Bomb Tower delayed bombs;
- Skeleton Barrel's delayed container and Skeleton payload;
- Royal Delivery and Graveyard scheduled payloads;
- Lumberjack's death Rage area; and
- Barbarian Barrel's rolling terminal spawn.

Capacity rejection remains explicit and deterministic. Synthetic child rows
require typed entity tokens and cannot appear in public decks or actor hands.

## Remaining practical-RL fidelity risks

1. **Movement, navigation, and body physics.** The dense Gym uses simplified
   objective navigation rather than full production pathfinding, bridge/river
   routing, collision resolution, mass, push chains, and every airborne/hover
   interaction. These global dynamics can bias positioning policies even when
   a card's local damage primitive is correct.
2. **Impulse and recoil.** Tornado attraction and Bowler pushback are explicit
   omissions; Firecracker recoil is omitted. Fireball, Giant Snowball, and some
   spawn/death push effects also need direct calibration against game traces.
3. **Visibility and special travel.** Royal Ghost invisibility, Tesla hide/rise,
   Bandit dash, Miner underground travel, and Mega Knight leap phases remain
   simplified or absent.
4. **Abilities and secondary areas.** Archer Queen Cloak is intentionally
   unavailable. Electro Wizard deployment zap, Ice Wizard slow, and Ice Golem
   death slow remain missing.
5. **Heterogeneous summons.** Goblin Gang still deploys only its homogeneous
   primary group rather than both serialized child types.
6. **Real-game calibration.** Serialized mechanics and deterministic tests are
   not sufficient evidence that damage timing, ranges, movement, elixir pace,
   targeting, or outcome distributions match the live game. Promotion should
   still depend on held-out real-state traces and free-running episode metrics.

## Evidence boundary

The 66/66 and 33/33 numbers prove fail-closed admission coverage for the
current public root/deck manifest. They do not prove exact mechanics, policy
quality, real-game calibration, CUDA throughput, or safe promotion of a
trained checkpoint. Those remain separate gates.
