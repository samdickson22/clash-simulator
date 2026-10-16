# Bounded source diagnostic — no comparison change or acceptance

Task: node:delegated-task:command%3Amcp%3Ac2371be3-b4fc-4c4c-9d4e-c37424334a7c%3Adelegate-task%3Ab2-c56-field-applicability-diagnostic-astra-20261016-1224

Source supports **narrow candidates for a separately versioned comparison**, not new exemptions or confirmed runtime causes. V1 and all **1,033/2,480 FAILs** remain unchanged. No edits, imports, builds, tests, simulations, jobs or delegation were performed.

Paths below are within `/mpac/sdicks02/repos/clasher-cards-b2`; `P` denotes `engine-cards/py/src/clasher`, and `N` denotes `engine-cards/src`.

1. **Spell `projectile_origin`: conditional applicability is defensible only with explicit payload guards.**

   Python initializes immutable launch history from starting position (`P/entities.py:5203–5206`); spell construction supplies the owner’s King launch point (`P/spells.py:39–46,279–300`). [live_snapshot.py:158](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/live_snapshot.py:158) exports it. Config templates use the more limited `entity()` exporter (`differential.py:454–455`), which omits origin; serde defaults it to zero (`N/lib.rs:373–374`). Subsequent native single casts and volleys update aim without origin (`N/lib.rs:3870–3882`; `N/c56.rs:735–742`). This explains a source-level representation mechanism consistent with the observation; it does not establish the captured run’s actual construction provenance.

   **Readers:** native impact calls children only with `child_count>0` (`N/lib.rs:3150`); [projectiles.rs:148](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/src/projectiles.rs:148) additionally requires positive child damage/range, then derives child headings from `aim-origin`. Python’s corresponding reader additionally requires positive count/range/speed/damage (`P/entities.py:5567–5588`). Python also passes launch geometry to source hit callbacks when a source exists (`:5463–5481,5561–5562`). The tensor adapter retains launch geometry for supported **piercing** objects (`P/torch_sim/resident_piercing_projectile.py:350–398`); that is outside a nonpiercing spell-only proposal.

   Children receive fresh endpoint origins in both engines (`N/projectiles.rs:169–184`; `P/entities.py:5624–5646`), but their headings already depend on parental history. Later Python damage-wave areas use endpoint geometry without copying launch history (`:5760–5786`). Knockback fallback uses current projectile position, not launch origin (`:5792–5802`; `N/lib.rs:3081`).

   **Candidate:** restrict to the four source-free, nonpiercing spell projectiles, with independently verified absent Python child payload and native child generation disabled throughout their lifetime. No general Projectile exemption. Source supplies no later child-payload activation for those constructors; actual roots/config still need verification.

   **Minimum witness:** both seats, post-root casts through impact/status completion, independently perturb origin only. Negative control: an existing child-producing projectile must reject wrong origin and expose changed descendant geometry; committed aim, targets, hits and buffs must still fail independently.

2. **Rolling `aim`: strongest class-dispatch applicability candidate, narrowly scoped to Log/BarbLog.**

   Python constructs these rollers at placement without a target-position field (`P/spells.py:831–854`); live export writes direction but not aim, leaving native expected aim at serde zero (`live_snapshot.py:177–180`; `N/lib.rs:521–522`). Native casting writes the castpoint into aim (`N/lib.rs:3874–3880`).

   Neither native rolling branch reads aim: spell rolling uses owner-directed movement, current position, traveled distance and configured range (`N/lib.rs:1091–1118`); character rolling uses `roll_direction` for movement and knockback ([projectiles.rs:44](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/src/projectiles.rs:44), `:54–68`). Python uses explicit direction when present, otherwise owner direction (`P/entities.py:6818–6842`).

   Character-shot creation computes launch geometry/aim before conversion to RollingProjectile and separately installs direction (`N/lib.rs:2380–2424`). This does not make the resulting roller’s aim a movement input. There is no subsequent retyping back to Projectile/Troop. BarbLog offspring come from fresh templates at the roller’s current position (`N/lib.rs:1157–1170`; `P/entities.py:7006–7029`), without parental aim.

   **Candidate:** separately versioned applicability for these exact rolling spell classes/configurations, preserving position, direction, range, timing, hits and child templates strictly. Do not extend it to Projectile/SpawnProjectile, whose aim has active readers.

   **Minimum witness:** both-seat Log/BarbLog continuation with altered aim through terminal hits and Barbarian combat. Negative controls must reject changed position/direction/range/hits and altered child aim/target; an ordinary Projectile aim mutation must remain detectable.

3. **Arrows `damage_group`: nominal identity, but unrestricted alpha-renaming is unsafe.**

   Python shares one mutable hit-set object per wave (`P/spells.py:286–327`). Export names that object by the minimum currently resident member ID ([live_snapshot.py:169](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/live_snapshot.py:169)); cleanup removes dead bodies (`P/battle.py:2480–2482`). Native allocates a fixed group label from `next_id` for each wave (`N/c56.rs:696–739`).

   Native readers use group **equality**, not entity lookup by that number: select the first matching member’s hit history, exclude those targets, then extend every matching member’s history (`N/lib.rs:843–870`). Python checks/adds actual target IDs in the shared set (`P/entities.py:5519–5528`). Consequently, **8→9 can preserve mechanics** when membership and hit histories remain identical; digest equality alone cannot establish those conditions.

   Constructor import preserves supplied labels without validating freshness or group consistency (`N/lib.rs:3615–3625`). Future volleys allocate labels numerically from `next_id`. An arbitrary rename to a future allocation value could therefore merge unrelated groups. Whole-battle clones preserve relationships (`P/battle.py:239–248`; `N/lib.rs:3639–3641`). Generic native projectile children also inherit group labels (`N/projectiles.rs:169`), so a general projectile normalization would require additional descendant proof.

   **Candidate:** independently canonicalize Arrows group partitions by minimum live member ID **for comparison only**. Preserve `None`, every membership relation, each member’s complete hit multiset, entity IDs and `next_id`. Require consistent histories across all resident group carriers, collision-free allocator bounds, and verified templates that cannot inject conflicting labels. Never union differing histories or copy expected labels into actual state.

   **Minimum witness:** representative death, remaining same-wave impacts, later waves and overlapping subsequent casts, including constructor reload and whole-state clone. Controls: merge groups, split one group, alter one hit/duplicate, and introduce a future-allocation collision. Each must fail.

4. **Troop `push_preserve`: inactive-state applicability is supported; “every clone resets it” is false.**

   Python exports the inverse of `_knockback_interrupts_combat` (`live_snapshot.py:108–111`). Completion resets Python’s flag (`P/entities.py:3628–3632`); native clears push/velocity/reset/forced state but retains preserve (`N/lib.rs:2103–2107`). This matches the reported false/true pattern structurally.

   All continuation reads are gated by an active push: Python combat and ordinary-clock logic (`P/entities.py:3754–3756`; `P/ordinary_combat_clock.py:87`), native preload/attack logic ([lib.rs:2252](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/src/lib.rs:2252), `:2268`). Native setup-time reads at `:965,972` follow assignment at `:964`.

   Every successful native push installation writes preserve: radial knockback (`:953–964`) or recoil (`N/projectiles.rs:129–145`). Python routes push/recoil through `begin_knockback`, which assigns the flag before callbacks (`P/entities.py:441–470`; `P/cards/firecracker.py:34–42`). Rejected pushes do not activate stale state.

   Whole-state clones retain the flag. Actor-to-projectile clones can retain it too; their dispatch does not execute Troop combat. Clone-spell children use fresh prototypes (`N/clone.rs:12–19`), and death/production/scope descendants use templates rather than donor push history (`N/lib.rs:3507`; `spawn.rs:88`; `scope.rs:129`). Actual imported templates still require inspection.

   **Candidate:** compare this flag only when push is active; require **both** sides’ push to be `None` for applicability. Keep clocks, speed caches, routes, targets, buffs and all other push history strict.

   **Minimum witness:** observed completion followed by interrupting push, preserving push, recoil and clone/descendant continuation. Active-push flag mutation and poisoned active-push templates must fail.

These proposals require separate review and witnesses. Any activated reader producing meaningful divergence requires an actual correction, not normalization. Global serialized changes remain blocked by C56 bit identity; no Bandit-dependent scope is justified.
