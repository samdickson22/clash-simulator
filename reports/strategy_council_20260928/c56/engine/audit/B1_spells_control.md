# B1 audit (spells/control) - read-only code+probe audit, 2026-10-03

No hard bugs: all nine load as the right spell class at L11; damage matches native or a balance override.
Several depend on balance.py overrides filling fields the compact snapshot drops: Lightning 3 targets/highest HP (:694-695),
Tornado pull (:747-749), Earthquake source-synced ticks/capped slow (:737-743), Royal Delivery 2050 ms + ignore buildings (:754,:634),
Barbarian Barrel distances/hitbox/1000 ms deploy (:431-441), E-Spirit 4-tile chain radius (:447).

| Card | Engine path | Status | Gap / evidence | Sev | Suggested native scenario |
|---|---|---|---|---|---|
| Barbarian Barrel | dynamic_spells.py:691, spells.py:765, entities.py:6738 | implemented | full 232 to crown towers (native barblogprojectile has no crown reduction; consistent but untested); ShakesTargets not modelled | small | cast at bridge with Knight at +2/+4.5: hit tick, Barbarian spawn tick/pos; pocket cast vs King |
| Arrows | dynamic_spells.py:533, spells.py:259 | implemented | 122x3 waves @200 ms, crown 25 | - | 3 Skeletons at 3.5-tile edge + tower: per-wave ticks |
| Tornado | dynamic_spells.py:390, spells.py:825, entities.py:6143/6331 | SUSPECTED GAP | (a) one 84 hit at 0.6 s; native 1050 ms life / 550 ms hit -> 1 vs 2 hits unconfirmed. (b) King activates only on damage (entities.py:576-580) or princess death (battle.py:2369); no "pulled into king range" trigger | consequential (king activation) | Hog -> princess, Tornado 3 tiles from King not touching: king activation tick; Knight in centre: damage ticks |
| E-Spirit | cards/electro_spirit.py:19, entities.py:5803 | implemented/unknown | 9 chain hits, 0.5 s stun; fixed 0.25 s per hop (electro_spirit.py:28) not native (projectile speed 1000) | small | 5 Skeletons in a line 1.5 apart: hit ticks, stun length |
| Lightning | dynamic_spells.py:287, spells.py:62, entities.py:6374 | unknown | strikes instant at 0.46/0.92/1.38 s (native speed-500 bolt flight skipped); ranking ignores shield HP | small | Recruit(shield)+Knight+Musketeer+tower: order, ticks |
| Poison | dynamic_spells.py:315, entities.py:6201 | implemented | 92/tick, 15% move slow, per-target clock; crown 21 override (formula 22); 8 vs 9 ticks untested | small | Golem in Poison 8 s: hit count |
| Earthquake | dynamic_spells.py:315 branch; balance.py:667 | suspected gap (small) | override 84/287/49 vs native-scaled 81/286(294)/49 (version difference likely) | small | Cannon+Knight+tower: per-tick damage |
| Rocket | dynamic_spells.py:533 | implemented | 1484, r2, push 1.8, crown 342 | - | tower+Musketeer: impact tick, push |
| Royal Delivery | dynamic_spells.py:503, spells.py:599 | implemented | 437, impact 2.05 s, ignores buildings, Recruit 547+240 shield; water placement unchecked | small | cast on Knight beside Cannon |

Native-fixture coverage: E-Spirit (native_spirit_object_phase, native_spirit_departing_avoidance), zap-clock freeze buff; Barrel only via Log fixtures; none for Arrows/Tornado/Lightning/Poison/Rocket/Earthquake/Royal Delivery (engine-only tests in test_enabled_spell_interactions.py, test_ranked_strike_spell.py, test_hog26_poison_target_local.py).
Priority: Tornado king activation, Tornado hit count, Lightning timing/shield ranking, Earthquake numbers.
