# B2 strict snapshot cache diagnostic — 2026-10-16T10:27:14Z

Bounded read-only codex/gpt-6-astra high diagnostic task
`node:delegated-task:command%3Amcp%3Ac2371be3-b4fc-4c4c-9d4e-c37424334a7c%3Adelegate-task%3Ab2-snapshot-export-diagnostic-astra-20261016-1025`.
No edits/SSH/tests/builds/runs were performed by the diagnostic.

Existing run3422841 evidence remains **FAIL**, never retroactive PASS.

- Native public_speed_base is an optional historical unslowed speed cache; the only explicit read is
  src/leaf.rs128 inside troop public danger ETA. Python differential.entity/live_snapshot never export
  the field, so serde suppliesNone. Native combat/movement fills0/120/60 in observed Tower/Spirit/Dragon
  rows. Python Entity._unslowed_movement_speed() independently exposes the meaningful troop base;
  C56RolloutPlanner.import_root already imports that value through set_public_movement_speeds.
- Preserve every non-null native cache value: move_one caches before advancing charge, so crossing
  progress10000 can legitimately leave normal cached speed. Recomputing solely from charge would
  erase meaningful history. Compare Python base against actual native cache or exact fallback only
  when nativeNone. Negative controls must detect wrong speed, original-speed/slow recovery, charge
  threshold and reset; do not copy native actual values into expected.
- Native combat_one clones source actor into a projectile and changes travel speed, retaining the
  actor's cache; projectile children clone it again. That historical cache is not used for projectile
  travel. Neither current shooter speed nor projectile travel speed reconstructs it reliably.
- The Python live_snapshot aim expression substitutes current primary target position, while actual
  Projectile.target_position stores its independently observable last committed endpoint. Both engines
  defer ordinary homing during launch delay, and new projectiles may wait for a later update. The
  first-failure receipt lacks delay/birth details, so launch delay specifically is not proven for
  those arrows. Reading target_position is justified; apply consistently at initial native construction
  and comparison. Target IDs/homing/delay/hit sets/buffs remain fully compared.
- Under the present strict/no-new-exclusions contract, Tower/projectile native-only cache differences
  remain an explicit blocker. A separate semantic comparison can document these as inapplicable and
  compare actual troop base speed, but it requires an explicit comparison-contract decision/review.
  Blanket removal of non-troop caches would widen the contract; do not silently do it to makePASS.

Recommended narrow boundary: reports/cards/b2/tools/probe_dash_full.py only; preserve shared engine/export
code and C56 outputs. Correct committed-aim projection, add independent meaningful speed/target/hit/buff
negative controls; retain raw failure evidence and request the parent's decision on a separately specified
semantic comparison before any affected reviewed rerun. Current run remains intact; its later valid
first-update/Clone/scenario suites can be inspected independently.
