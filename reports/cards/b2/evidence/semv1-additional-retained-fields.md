# Additional retained semantic failures, partial completed shards

2026-10-16T12:04Z onward, read-only copies of completed shards1/2 logs from existing
run3586969. These observations do not change any comparison or acceptance rule.

- Fireball, Arrows, Rocket, Snowball, both seats: negative/nonpositive cast offsets
  expose `Projectile.projectile_origin` Python launch point versus native(0,0)
  for newly cast objects. Example Fireball blue lead-4/t4: Python(9,29), native(0,0).
  `live_snapshot.py:158` independently exports actual `Projectile.launch_position`;
  `lib.rs:3880` native spell-template construction changes aim but leaves the
  template origin. The origin has a real native reader in
  `projectiles.rs:projectile_children`, conditional on child damage/range. Source
  inspection alone does not authorize a field exemption. Correcting native birth
  serialization globally would change C56 snapshots/chains; no such fix was made.
- Log/BarbLog both seats: post-root casts expose `RollingProjectile.aim` Python(0,0)
  versus native castpoint, e.g Log blue lead-4/t4 native(9,18.5). The current shared
  exporter only explicitly exports roll_direction for this class; all aim fields
  remain strict. No extra applicability rule or exporter normalization was added.
- Freeze and Vines reproduce Bandit facing/direction/route family after the old
  driver's forced travel, alongside Zap. C1's shared Troop ownership applies to
  supported transition causes; fixture validity remains B2-owned. Exact old Zap
  roots/normal acquisition capture is still required before reachability claims.
- ElectroSpirit shares IceSpirit's mode-derived projectile-slow multiplier field
  disagreement. This remains strict alongside the retained IceSpirit family; it is
  not an approved inert stat or overlay correction.

Completed shard1 meaningful-state match counts vary by source: Lightning80/80,
Zap60/80, Fireball70/80, Arrows22/80, Rocket70/80, Log68/80, BarbLog70/80,
Snowball70/80. Completed shard2: Earthquake80/80, Poison80/80, Freeze10/80,
Tornado80/80, GoblinCurse80/80, Vines46/80, Void80/80, ElectroSpirit8/80.
These are partial-run descriptive counts, never a filtered PASS artifact. All
source-specific guard queries were observed for the critical spell sources in
these shards; mutation, path, Clone and remaining-source evidence is still pending.

Full immutable outputs remain on08 in the exact semv1 job. New actual constructor/
paired roots will be in the separately reviewed bounded capture, not fabricated
from these summary differences. No additional full sweep, engine change or live/
main/runtime/pin action occurred. Final integrated acceptance still requires each
applicable failure fixed or separately reviewed evidence-based fixture disposition.
