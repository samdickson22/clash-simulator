# B2 audit (air + splash) - read-only code+probe audit, 2026-10-03

No consequential gaps found. Shared paths: direct-hit splash entities.py:846-930; projectile creation entities.py:3998-4180
(hit planes gamedata_normalization.py:77); Firecracker shrapnel entities.py:5556-5640; death bombs TimedExplosive entities.py:7017
via mechanics/shared/death_effects.py:116-140; swarm spawn battle.py:1541-1559, 100 ms stagger battle.py:1676.
Per-card files baby_dragon.py/balloon.py/bats.py/minions.py/dart_goblin.py are placeholders; ValkyrieSpin and PrincessLongRange never attached (data path covers both).

| Card | Status | Gap / evidence | Sev | Scenario |
|---|---|---|---|---|
| BabyDragon | implemented (data question) | engine/native gamedata base dmg 66 (168 L11) vs decoded babydragon.toml projectile 63 (~160): version difference | small | one hit on Knight: HP lost |
| Minions | implemented | summon radius fallback = native rule; DeployDelay 400 unread (also on fixture-verified Archer/Musketeer/Hog -> likely no logic effect) | small | deploy offsets/first visible tick |
| Bats | implemented | angle shift 45, dash 150 (balance.py:301) | small | - |
| MinionHorde | implemented | 6 units r0.6, 100 ms stagger | - | deploy offsets |
| Balloon | implemented | building-only; bomb TimedExplosive 3.0 s, r3.0, 94 base, air+ground (matches balloon.toml BalloonBomb) | - | kill Balloon over air+ground units: bomb tick/dmg |
| Wizard | suspected gap (small) | ProjectileStartRadius 0 vs native 550 (Ice Wizard has override balance.py:232); mass formula 8 vs native 5; WalkingSpeedTweakPercentage -10 unread | small | Wizard vs Knight at 5 tiles: launch/impact ticks; collision push |
| Valkyrie | implemented/unknown | r2.0 self-centred, 100 ms finish; TryToFinishAttackAnimation unread | unknown (swarms) | Zap target mid-windup with Skeletons near |
| Princess | implemented/unknown | range 9; projectile splash 2.0 vs character AreaDamageRadius 2500 unconfirmed | small-medium | Knights at 2.2 tiles from impact |
| Firecracker | implemented | carrier no dmg; 5 shrapnel over 5 tiles; recoil 1 tile; deflection fields unmodelled | small | - |
| DartGoblin | implemented | range 6.5, sight 7, start radius 1.2, homing | - | first-hit tick |

Native fixtures: Baby Dragon movement (test_native_target_acquisition.py:47), Minion formation (native_formation_boundary). None cover splash/death-bomb/shrapnel timing.
Candidate engine fixes (need native confirmation first): Wizard projectileStartRadius 550, Wizard mass 5.
