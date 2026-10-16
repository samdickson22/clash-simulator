**Confirmed: Three Musketeers has a real observation-identity defect. A shared existing-token alias can remove UNK, but cannot preserve all three identities and 700/650/700 ms load times through the inspected public-root interface.** Full correction therefore needs a narrowly scoped public-contract/template owner decision.

Read-only source inspection at `ebab18cc8f7194d22940f4177dec3225b3ddafcc`; no edits, imports, scripts, tests, SSH, jobs or owner messages.

1. **The actual bodies and shots have no existing fallback.**
   [balance.py:988](/mpac/sdicks02/repos/clasher-cards-b1/engine-cards/py/src/clasher/balance.py:988) creates the synthetic projectile and three member names. [battle.py:1592](/mpac/sdicks02/repos/clasher-cards-b1/engine-cards/py/src/clasher/battle.py:1592) builds each member’s stats from its synthetic name without parent provenance. Ordinary shots retain those stats and use that name as `source_name`.

   [structured_obs.py:433](/mpac/sdicks02/repos/clasher-cards-b1/engine-cards/py/src/clasher/rl/structured_obs.py:433) consequently finds only synthetic body/projectile names; neither the frozen vocabulary nor card aliases resolves them. `_runtime_entity_token_id` returns **1**. The parent card’s own `ThreeMusketeers` token does not rescue these detached member stats.

   This is established for the checked-in `ContractV5ObservationBuilder`. I did not locate the specifically named `FrozenContractV5ObservationBuilder` wrapper in inspected sources, so any additional wrapper behavior remains unverified.

2. **Exporter metadata and registration do not close that gap.**
   [affected.py:158](/mpac/sdicks02/repos/clasher-cards-b1/reports/cards/b1/main-integration/tools/affected.py:158) compares exported candidates with the same candidate function; it never requires a known frozen token or exercises `Resources.root`.

   [fair_player.py:45](/mpac/sdicks02/repos/clasher-cards-b1/reports/strategy_council_20260928/engine-speed/stage5/fair_player.py:45) can register a parent-derived template, but that does not change the actual sensor token. `complete()` skips unresolved identities. There is also an important qualification: demonstration registration at line 103 **can register token 1**. Thus an encountered unknown may silently reuse another unknown’s template instead of raising. “Root did not throw” is insufficient evidence.

3. **Aliases alone lose information at root construction.**
   [fair_player.py:127](/mpac/sdicks02/repos/clasher-cards-b1/reports/strategy_council_20260928/engine-speed/stage5/fair_player.py:127) selects one template by `(token, public_kind)`, with registration using first-wins `setdefault`. It reconstructs clocks from that template’s `stats.load`. No rank discriminator or per-row load override exists.

   `public_static` supplies translator columns; it is not applied by this root. [ExactLevelRoot](/mpac/sdicks02/repos/clasher-cards-b1/bot/levels/root.py:177) likewise selects the template first, then applies level deltas using its selected mechanical name. It cannot recover a discarded member identity. Even applying all exported static columns would not distinguish the 650 ms member: load time is absent.

   Keeping mechanical names intact also matters because `apply_character_overrides` is name-selected. Renaming rework members to `Musketeer` risks changing mechanics/stat lookup and conflating ordinary Musketeer templates.

4. **The other scoped carriers are not the same missing-token defect.**
   - **Goblin Giant:** attached bodies resolve `SpearGoblinGiant`; their shots resolve `SpearGoblinGiantProjectile`; released children resolve `SpearGoblin`. All exist in the vocabulary. Separately, exporter `mount` references use engine IDs, while the inspected root renumbers entities without remapping rider mounts. Registration alone cannot certify a valid reconstructed attachment graph.
   - **Battle Healer:** `heal_area_pulse` explicitly sets `spell_name` to `BattleHealerSpawnHeal` or `BattleHealerHeal`; both are frozen tokens. Test actual pulses and healing payloads through root construction.
   - **Giant Skeleton / Skeleton Balloon:** timed carriers retain parent `card_stats`. With the untyped frozen vocabulary, their first known candidate is ordinarily `GiantSkeleton` / `SkeletonBalloon`, paired with public kind `AreaEffect`. These are known-token fallbacks, not necessarily the child bomb name. Require the selected template to be the correct `TimedExplosive` with the appropriate explosion/container payload; do not change longstanding C56 carrier identities merely for naming consistency.

**Recommendation:** preserve synthetic mechanical names, source aliases, selectors, formations and rank-specific loads. Do not append vocabulary or substitute ordinary Musketeer identities within B1.

A reversible, narrowly scoped alias design could put explicit **public identity metadata on the generated payloads**, consumed consistently by sensor and exporter, mapping the rework bodies to `ThreeMusketeers`. A projectile alias must likewise be deliberate and select the rework projectile template—not accidentally reuse ordinary Musketeer’s projectile. This can preserve engine/config mechanics and vocabulary bytes, but it remains a **coarse observation mapping**, not an exact rank-preserving root correction.

If exact reconstructed rank identity is required, the essential dependency is the public-contract/template owner choosing between:

- an explicit additional identity channel/template-selection mechanism, with its public-information contract; or
- appending the four synthetic tokens and updating dependent model vocabulary/configuration.

Appending preserves existing numeric IDs but changes vocabulary size/hash and token-indexed model tensors. [contract_v5.py:701](/mpac/sdicks02/repos/clasher-cards-b1/engine-cards/py/src/clasher/rl/contract_v5.py:701) confirms those dependencies; its existing upgrade helper is specifically v4→v5, not authorization for an unchanged frozen-v5 checkpoint. Assigning unrelated existing tokens to individual ranks would weaken the identity oracle.

B1 can immediately prepare regression coverage requiring actual emitted entities, **exact expected token names greater than 1**, correct template class/mechanics, both seats, all three members, actual projectiles/pulses/carriers, and valid rider relationships. Keep the unresolved root distinction explicit rather than accepting “non-UNK.”

For any Python compatibility change, preserve the running `5c8afc2d7`/`6737…` gate as evidence for that source only. Bind a fresh source manifest and rerun public sensor→Resources→root checks plus the required combined 16/94/4, 39 paired reference and changed-arm 577/600 acceptance evidence. Unchanged Rust/build inputs may justify reusing the exact native binary with documented provenance; they do not justify carrying forward old Python-source acceptance. Review any changed host procedure before execution.
