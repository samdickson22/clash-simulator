# Deployment blocker census and live visibility admission

Follow-up to the gates worker's r2 forensic; checked 2026-10-08. The detailed
`imitation/gates-bc/receipts/rejection-02-r9-replay-with-guards.json` records
`is_deployment_payload_occupied`, `TimedExplosive`, and `blocks_deployment=true`
for **all six** rejected commands. Line 1277 combines building-footprint and
payload tests; reaching that line alone does not identify an ordinary building
as the obstruction. These are deployment blockers, not merely troops whose
deployment animation has not finished.

## Complete current engine inventory

The source scan of `src/clasher` finds `TimedExplosive` as the only class with
`blocks_deployment=True`, and exactly two production construction sites:
`DeathSpawn.on_death` and `MightyMinerSwitch.on_object_tick`. No production
assignment turns this capability on for another class. The former creates an
effect when a serialized death child has `deathDamage` but no hitpoints. The
latter creates the ability bomb directly. `DeathAreaEffectContainer` explicitly
sets the capability false: a delayed Rage bottle or other death-area effect is
not automatically a placement blocker. Ordinary deploying troops, projectiles,
auras, spell containers and combat explosion radii do not reserve a footprint.

The [data census](blocker-census.json) covers **all loaded card definitions**,
including aliases, and pins the capability and construction sources:

| Public source identity | Engine payload | Deployment radius (tiles) | Construction |
| --- | --- | --- | --- |
| Balloon | BalloonBomb | 0.45 | DeathSpawn |
| GiantSkeleton | GiantSkeletonBomb | 0.45 | DeathSpawn |
| BombTower | BombTowerBomb | 0.45 | DeathSpawn |
| SkeletonBalloon (SkeletonBarrel / Skeleton Barrel aliases) | SkeletonContainerNew, then seven Skeletons | 0.50 | DeathSpawn |
| MightyMiner | Ability bomb (source stats remain MightyMiner) | 0.50 | MightyMinerSwitch |

All five identities were already compiled by mask v2; no production geometry
change was needed for this follow-up. Both mask implementations distinguish the
effect from its living source body. Clone death payloads retain the same static
radius and public source identity. Spells ignore payload occupancy; buildings
test circle against their resolved square footprint, troops test inclusive
circle contact and ground relocation candidates. Neither blast radius nor
remaining fuse time enters the public mask.

The Rust engine's equivalent capability is `placement_radius: Option<f64>`:
every live entity with `Some(radius)` participates in `payload_blocked`.
`differential.py` populates it from Python's `blocks_deployment`. The public
Rust mask derives the same radius from reviewed public identities, not this
runtime field. A future new capability owner, nested death-spawn route or
unsupported effect identity requires a new public mapping and visibility
review; the current five-identity census is not permission to ignore it.

**Other equivalent occupancy:** every live Building participates in footprint
and air-collision rules, including Crown Towers, Tesla and Goblin Drill. Crown
Towers also have command exclusion squares. Underground enemy Goblin Drill is
the already measured contract-v5 visibility residual; it is not a sixth timed
payload. Building overlap remains independent of `blocks_deployment`.

## Real-game visibility: evidence and limits

Engine row visibility is **not** proof of official-client visibility. The
following checks distinguish a documented public effect from proof that its
entire engine blocking interval is observable to the opposing player:

| Payload | Public visual evidence | Live qualification status |
| --- | --- | --- |
| BalloonBomb | Supercell names Balloon's death bomb alongside the two ground bombs in its [March 2021 notes](https://supercell.com/en/games/clashroyale/blog/release-notes/new-balance-changes-2/). This establishes the effect, but alone does not prove both-player visibility throughout the blocking interval. | Full opponent-view interval not verified; require captures before admission. |
| GiantSkeletonBomb | Same official notes; a [firsthand defending-player report](https://www.reddit.com/r/ClashRoyale/comments/1f2ah5r/) describes waiting for the enemy bomb to disappear before building placement. | Opponent-observable bomb corroborated; current exact onset/end and radius remain unverified. |
| BombTowerBomb | Same official notes; a [firsthand report](https://www.reddit.com/r/ClashRoyale/comments/ndk5e7/) describes the bomb remaining at the blocked placement spot. | Visible bomb corroborated; report does not establish the full opposing-client interval. |
| SkeletonContainerNew | Supercell's [June 2025 update](https://supercell.com/en/games/clashroyale/blog/release-notes/june-update-2025/) explicitly documents the Skeleton Barrel bounce animation and death-damage VFX. | Falling/opening effect is rendered; animation-to-blocking-interval correspondence requires captures from both seats. |
| Mighty Miner ability bomb | Supercell's [March 2022 update](https://supercell.com/en/games/clashroyale/blog/release-notes/the-miner-update-info-2/) describes leaving the bomb at the origin; a [firsthand visual-interaction report](https://www.reddit.com/r/ClashRoyale/comments/1gzypp2/) discusses its displayed sprite. | Public bomb corroborated; do not use the underground miner's hidden location as its position. Full interval requires both-seat captures. |

No reviewed source identifies one of these five effects as an intentionally
hidden trap. That is **not confirmation of complete visibility**: especially
for Balloon, the available evidence is insufficient to certify the requested
opponent-view interval. Their treatment as observable effects in simulator
contract v5 does not authorize immediate camera-based live deployment. No
current official-client recording was captured in this task; Null's fixtures
are not substitutes. Radii above describe the pinned simulator data, not a
verified current official-client specification.

For live admission, capture each row from both players' ordinary battle views:
parent death/ability activation, first payload pixel, falling/bounce animation,
each accepted/rejected boundary placement, detonation/child release, last
payload pixel and first accepted placement. Include friendly/enemy ownership,
clones where applicable, occlusion and overlapping effects. Confirm whether
the blocker exists before its first visible pixel or after its last one. Keep
this evidence separate from privileged spectator or engine state.

## Required live treatment of hidden or uncertain blockers

- A positively identified, localized public payload supplies a blocker at its
  **observed** location with qualified static geometry. Do not predict the
  location from hidden hand/deck, intended target, RNG or private countdowns.
- Losing a detection does not prove detonation. An occluded, truncated or
  unrecognized effect makes placement certainty incomplete. Reobserve and
  defer affected non-spell placements; only a separately qualified tracker may
  retain a conservative region derived entirely from observed public history.
  If that region cannot be bounded, defer all non-spell placements (wait, or a
  separately legal spell). This is an actuator admission policy, not an
  invented engine-illegal label for training.
- If official captures reveal a genuinely hidden blocking phase with no
  sufficient public cue, do not put its private entity position into v2.
  Declare exact public-mask equality unsupported in that scope; exclude the
  scope from exactness claims, or use the conservative abstention policy above
  under a new live qualification. The same rule applies to the underground
  Drill residual: a visible tunnel trail is not automatically its exact
  private footprint or destination.
- A visible effect that is combat-untargetable is still public information.
  Conversely, a row exposed by a simulator is not necessarily public in the
  official game. Detection, identity, localization and complete temporal
  coverage must all be qualified before the live actuator relies on v2.

These are requirements for future live integration. This follow-up does not
modify the frozen perception workers, actuator or evaluation registrations.
The stateless v2 mask cannot detect a missing camera object itself.

## Verification

`tests/test_public_mask_v2_blockers.py` checks the capability-class census and
all loaded death-source aliases, exercises actual engine construction for each
route, compares all placement bits against Python's guards and the Rust public
mask for both seats, checks effect removal and spell invariance, tests cloned
death payloads, and verifies that a living Mighty Miner is not mistaken for a
bomb. See `blocker-census.log` and `blocker-tests.log`; these follow-up tests
run in the isolated checkout on home 03 via `fleet_run.sh`. The prior 100k-state
audit and its source pins remain unchanged.

Result: **22 passed**, including 14 complete Python/engine/Rust placement-mask
comparisons (seven source spellings/routes, both seats), six clone cases,
the capability census and living-parent negative control. Both production
mask files match the earlier audit's source hashes byte for byte.
