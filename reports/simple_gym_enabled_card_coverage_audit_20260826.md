# Simple Gym enabled-card coverage audit — final refresh 2026-08-27

## Scope

This audit covers the 66 unique public roots and 33 source decks in `decks.json`
at source `504444ea400ff8bf595c0386ff000afe2c1f3490`. The authority is
`compile_standard_simple_setup` with `canonical_lane_globals=true`, not the
bare attack catalog.

The byte-exact artifact check reports:

```text
candidate_decks=33
supported_decks=33
rejected_decks=0
public_cards=66
supported_public_cards=66
unsupported_public_cards=0
support_profile_sha256=9e8dbfe1edf10835bd2138f237dcc917b65dc1f44f39bc26ff221da4d6aaefab
```

The public attack-plane partition is 27 direct, 27 projectile, 8 area, and 4
ordinary-attack-unsupported roots. The latter four are admitted through
rolling/payload owners, not as inert attacks. Required typed children and
atomic heterogeneous groups compile fail-closed.

## Generalized mechanic coverage

The production compiler/runtime covers:

- native action formations, typed private children, and atomic heterogeneous
  spawns;
- death, delayed, periodic, scheduled, rolling-terminal, and payload children;
- direct/projectile/area, multi-target, chain, line, fan, periodic, rolling,
  charge, ramp, and Crown Tower combat;
- first-hit/retarget locks, shields, statuses, buffs, death bursts, recoil,
  push, and attraction;
- tower retaliation and King activation;
- visibility, Archer Queen ability, and public-v2 ability legality;
- Bandit, Mega Knight, and Miner special travel;
- river jumps for Dark Prince, Hog Rider, Mega Knight, Prince, and Royal Hogs;
- Royal Ghost hover on the air body plane while remaining a ground target;
- mass-weighted separation, pending-body contact/targetability, building
  avoidance, bridge/river bounds, and owner-mirrored exact overlaps; and
- Skeleton Barrel's serialized 100 ms first-hit remainder plus stun-paused
  500 ms contact self-pop into its bomb/Skeleton payload.

Legacy fast-catalog omission flags remain set for Bowler displacement, Tornado
displacement, and Firecracker recoil. They are not production gaps: each has a
compiled triggered descriptor consumed by the unified runtime.

## Complete 66-card classification

Every enabled public root appears exactly once. “Useful baseline” means its
defining policy-visible mechanic is represented within the declared shared
practical-Gym limits; it is not a live-client parity claim.

### Useful baseline within the practical Gym (62)

Archer Queen, Archers, Baby Dragon, Balloon, Bandit, Barbarian Barrel, Bats,
Battle Ram, Bomb Tower, Bomber, Bowler, Cannon, Dark Prince, Dart Goblin,
Earthquake, Electro Dragon, Electro Wizard, Fireball, Firecracker, Freeze,
Giant, Giant Snowball, Goblin Barrel, Goblin Gang, Golem, Guards, Hog Rider,
Ice Golem, Ice Wizard, Inferno Dragon, Inferno Tower, Knight, Lava Hound, Log,
Lumberjack, Magic Archer, Mega Knight, Mega Minion, Miner, Mini P.E.K.K.A,
Minions, Musketeer, Night Witch, P.E.K.K.A, Poison, Prince, Princess, Rocket,
Royal Delivery, Royal Ghost, Royal Hogs, Skeleton Barrel, Skeletons, Spear
Goblins, Tesla, Tombstone, Tornado, Valkyrie, Wall Breakers, Witch, X-Bow, Zap.

### Training-supported with bounded card-specific approximations (4)

| Card | Represented | Accepted approximation |
|---|---|---|
| Arrows | travelling air/ground area damage and total/tower scaling | waves collapse into one impact, so between-wave shield/death/spawn timing is absent |
| Electro Spirit | homing source-consuming chained damage plus stun | leap presentation/trajectory uses the homing effect path |
| Graveyard | 12 typed Skeleton waves with serialized deadlines | deterministic bounded geometry replaces live spatial RNG and exact offsets |
| Ice Spirit | homing source-consuming splash freeze | hop presentation/trajectory uses the homing effect path |

These retain decision-relevant damage/status/spawn ownership and timing closely
enough for the accepted Gym. None removes a public action or invokes Python
fallback.

## Typed Hero/Evolution boundary

The 494-token vocabulary has distinct namespaced Hero/Evolution keys, and the
projector/adapter require exact typed lookup. Unknown or ambiguous variants
return no token; there is no base-family collapse.

The 66 admitted roots contain no `_hero` or `_EV1` root, and the source
vocabulary labels those entries representation-only/not exposed by the loader.
This audit therefore proves identity preservation and fail-closed behavior,
not Hero/Evolution gameplay mechanics.

## Shared practical approximations

- deterministic dense contact and tangent building avoidance rather than the
  client's full obstacle graph and avoidance heuristics;
- fixed-step, presentation-free travel;
- bounded fixed-shape capacity with explicit atomic rejection;
- no independent video calibration for exact combat HP/damage/status/contact;
- no claim that terminal policies free-run every mechanic in every card.

These fit the requested practical RL Gym. The Resident engine remains available
when Python/event parity is required.

## Validation evidence

- exact isolated-main CPU suite: **406 passed, 248 CUDA skips**;
- exact-source A6000 mechanics suite: **222/222 passed**;
- exact newer-main CUDA route/mechanics suite: **191/191 passed**;
- two deterministic CUDA-Graph terminal replays per policy, all native and
  committed, zero fallback;
- no-op reaches tick 6000 tiebreak; first-legal reaches tick 3600 crown;
- batch-128 median 410.053 row-ticks/s, 10 launches, zero explicit sync; and
- actual 494-token recurrent policy smoke passes public-mask, metadata,
  recurrent, admission, native, commit, and fallback checks.

The failed `f67ed3a8` CUDA capture and mirror audit are preserved as diagnostic
evidence. Source `504444ea` fixes both and is the only accepted source.

## Final decision

**66/66 enabled base roots and 33/33 source decks are accepted for fresh
practical RL training.** The four card-specific approximations and shared
limits remain explicit; no material enabled-card policy mechanic is knowingly
inert or routed through Python fallback.
