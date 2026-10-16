# R24 Fireball bootstrap source audit — Astra

UTC audit date: 2026-10-16. Read-only source/JSON/hash observations began by 11:50:40Z; final audit timestamp below. W = `/mpac/sdicks02/repos/clasher-bot-levels` on05. J = `/mpac/sdicks02/jobs/clasher/bot-levels`. R = `J/runtime/live16402b-r2` on01. C = `J/level-configs/50d22f86b3590abc` on01. W-relative citations identify the failed R21 implementation, before the independently owned Sol repair; R-relative citations identify the actual copied runtime read over SSH01.

**Verdict: the early-builder hypothesis has a concrete, deterministic source chain. The unsafe initialization starts inside `ContractV5ObservationBuilder()` itself, before a public mask needs to run. It materializes the process-global tournament spell registry while Fireball's stale 172-point crown override is still present. Real Runtime subsequently removes the override dictionary entry but never invalidates the already-created spell. Resources therefore exports that cached L11 spell, while the immutable L11 export contains the correct 159-point value. The support manifest's reference mismatch invokes an independent writer that the fixture's export-build guard does not block. Fireball is removed from support, causing both legitimate opposite-owner L4 roots to fail closed.**

This establishes the source defect and explains the exact observed exclusion. It is not a newly executed reproduction: the failed process's complete old/new `R.config` objects were not present in the inspected receipts, so the new full reference digest has not been independently reconstructed from a one-field edit. No test/physics PASS is claimed.

## Established observations

`J/dev/pytest-placement-r21.txt:729–849` records both `test_hidden_state_invariance_and_recorder` failures, at `W/bot/levels/test_placement.py:522`, before `player.act`. `ExactLevelRoot.payload`, `W/bot/levels/root.py:160–175`, rejects Fireball L4 for owner1 when seat0, and owner0 when seat1. Both sampled opponent cycles contain Fireball. `root.py:75–76` applies the opponent estimator independently of the own L11 view; `profile.py:29–32,76–96` gives rare Fireball the fixed estimate L4. The fixture's own cards/towers being L11 does not make this an all11 opponent test. `player.py:46–57` installs that estimate and the fixture's shared LevelConfigs in arm B.

The preserved manifests differ exactly as follows:

- Original candidate `J/dev/supported-restoration-candidate-r24.json`: raw SHA256 `e03491147b6d2da405b3aa81be782c49f782513bfffa7412aaa0a8581f2507bc`; 121 cards, `unsupported={}`, comparison `native-json-v1`, reference `193b6615e3a1b7c13da664243e8d70050a35e5531ef12d2bbe1a92390e97865e`.
- Failed snapshot `J/dev/supported-after-pytest-r21-failed.json`: raw SHA256 `4566bd6a6e59cfd5ed4234d7a0415bfd966e27c7aec0c576167f3fe4714a5d41`; 120 cards; sole removed card Fireball; sole unsupported reason `level-11 export differs from R.config`; reference `f0084f7afc5cff9cb1465f0d46addd2546391b37746a5108c3f88bb4670b9559`.
- Current `C/supported.json` on01 still hashes to the failed snapshot. Nothing was restored.
- The candidate's parsed object equals `J/dev/all11-r12-launch.json` → `identity.level_cache.supported.data`; its byte hash also equals that launch's stored original raw hash.
- All SIX current export files match BOTH raw and compact sorted canonical SHA256 recorded in `J/s27-diagnostic-dev-r20/receipt.json` → `cache.levels`. L11 also matches the R12 launch. Therefore these exports have no net byte change relative to those prior receipts. This does not prove absence of a transient write followed by exact restoration; no write trace was preserved.

Current/export-receipt matching raw SHA256:

```text
L11 1a36f377d55be3ea34e20225aa17eb92bead8e148b216b5b1346f0e7d04c8a94
L4  bd77caea134e469c89dc1d25d60f30474a404feef6b529d26b0e307a8f3a7d95
L5  e88a6e04183f449754775b7f9d999c2ca3982601cb6f35dbbc1aec28d1555dfe
L6  ad4b725b180cb2aa0abf50c13cf378ba2a954233eac43080b248f2f40146dcbb
L7  8fc9633bbd50906d7f95575b7c93ba6a39e540aec2997f67c2d50b8a1477b6f3
L9  88a2472e54b090853bd18016cdafda642aafa1fd00f03ca6e7fa20f3edd638b2
```

L4 contains Fireball with no Fireball export error. L11 has 121 exports; each inspected lower-level file has 118 exports. L4's preserved errors are Clone inheritance, Earthquake crown override reconciliation, and Tornado crown override reconciliation. These existing exclusions must remain intact; retaining the 121-card L11 support mapping does not mean inventing three low-level exports.

## Exact order and cache contracts

1. Failed `W/bot/levels/test_placement.py:18–27` constructs `Runtime.__new__`, assigns root/native_dir, calls only `_bootstrap_paths()`, then immediately constructs `ContractV5ObservationBuilder()`. The integration fixture at `:351–359` explicitly depends on this `builder`, so it cannot initialize actual Runtime first. Earlier lightweight tests also request the same builder.
2. `_bootstrap_paths`, `W/bot/players/runtime.py:142–165`, sets environment defaults and import precedence. It performs no tournament override normalization. Runtime pin `live16402b-r2` explicitly declares Fireball/Poison crown normalization at `:72–75`.
3. Builder initialization, `R/src/clasher/rl/contract_v5.py:403–419`, builds descriptors for named tokens. `v5_card_descriptors`, `:252–264`, calls `SPELL_REGISTRY.get(...)` for a valid card. Thus constructing the builder is already sufficient; blaming only later public-mask calls would miss the earliest trigger. `public_action_mask.py:227–237` is a second lookup path.
4. `R/src/clasher/spells.py:1027–1058` implements a process-global `_LazySpellRegistry`: first lookup stores `_load_dynamic_spell_registry()` in `_registry`; later lookups reuse it. There is no file revision, runtime pin, balance override or level-normalization key. `spells.py:1011–1022` delegates to `dynamic_spells.load_dynamic_spells`; `dynamic_spells.py:765–782` constructs ALL serialized spells at default tournament level. Both Fireball and Poison are materialized, regardless of which valid token causes the first lookup.
5. `R/src/clasher/balance.py:700,707` initially specifies Fireball crown172 and Poison crown21. `dynamic_spells.py:114–120` copies an existing tournament override into each spell's numeric `crown_tower_damage`. This is a stored value, not a live view of the override dictionary.
6. Only later does actual `Runtime.__init__`, `W/bot/players/runtime.py:97–120`, bootstrap, verify pins, then pop the two crown overrides at `:113–116`, before constructing Resources at `:120`. It does not clear/rebuild `_LazySpellRegistry`. Removing the dictionary keys cannot update those spell objects.
7. `R/reports/strategy_council_20260928/engine-speed/stage5/fair_player.py:38–42` builds controller resources then `config(CARDS)`. `R/engine-rs/quickwin_resources.py:69–114` binds private exporters and cached battle/arena helpers; it does not provide an independent spell registry or a cached full Resources result. The exporter namespace still uses the same clasher modules.
8. `R/engine-rs/differential.py:387–389,436–437` resolves each card through the template battle. `R/src/clasher/battle.py:1165–1175` returns `SPELL_REGISTRY.get(resolved)` unchanged when the requested level is11; only a differing level constructs a fresh spell. `differential.py:509–524` serializes `asdict(spell)` into `R.config.cards[card].spell`. Full-scope Resources extension does not cure that shared stale registry.
9. The fixture `test_placement.py:362–371` blocks only `LevelConfigs.build`, preloads six files, and yields. It neither verifies nor freezes `supported`. `W/bot/levels/configs.py:125–139` recomputes the reference from `json.dumps(R.config, sort_keys=True)`, calls exact `check11()` on mismatch, and writes/replaces `supported.json` using a separate temp file. This writer bypasses `build` completely. Its directory tag at `:79–81` depends on pin/native/gamedata identity, not the changed in-memory config.
10. `check11`, `configs.py:103–116`, compares the entire L11 card entry and its exported side tables with exact sorted JSON. `entry`, `:142–150`, returns None when a card is absent from the support set even if its L4 data exists, then caches that None. `root.py:165–175` correctly refuses the playable unsupported card. A support rewrite can occur while `mixed()` first visits a non11 card, before the eventual Fireball check; the trace does not identify the first writer invocation's card.

The definition cache is separate: `R/src/clasher/data.py:15–48,90–104` keys immutable definition snapshots by path/mtime/size and shares definitions across loaders. `factory/card_factory.py:127–135` extracts raw spell metadata; the identified 172-point value is copied by dynamic spell construction, not by this definition-cache key. The concrete sufficient culprit is the lazy spell registry. No evidence requires a second definition-cache corruption explanation.

## Exact Fireball values and units

Directly parsed `C/L11.json` → `cards.Fireball.card.spell` has:

```text
damage                         688.0       hitpoint damage per projectile impact
crown_tower_damage             159.0       hitpoint damage per crown impact
crown_tower_damage_multiplier   0.22999999999999998  dimensionless (23%)
level                          11          unified card level
radius                         2.5         arena tiles
travel_speed                   11.999999999999998  tiles/second
knockback_distance             1.0         arena tiles
```

The source-derived early-registry value is `R.config.cards.Fireball.spell.crown_tower_damage = 172.0`, versus normalized/export `159.0`: **+13 crown hitpoints per hit**, not a percentage or a positional/fixed-point discrepancy. Ordinary damage remains688.0 and the serialized multiplier remains23%; the stale override changes the explicit crown field. The bad full `R.config` was not captured here, so172.0 is a deterministic source inference, not a directly read failed-runtime field.

`R/gamedata.json` Fireball projectile data has raw damage269, `crownTowerDamagePercent=-77`, radius2500, pushback1000 and speed600. `dynamic_spells.py:30–34,539–562` converts the percent to `1 + (-77/100)`, radius/pushback to tiles, and uses the normal level-scaled damage. `R/src/clasher/logic_math.py:37–53` applies integer native ceiling arithmetic: `(688*23+99)//100 =159`. Keeping172 or rounding this to158 would change the prescribed physics. No tolerance is involved.

Directly parsed `C/L4.json` Fireball has damage357.0, crown83.0, multiplier `0.22999999999999998`, level4; `(357*23+99)//100 =83`. Both owner projectile templates carry ordinary `stats.damage=357.0`. The export exists and is not intrinsically unsupported. The failure is the L11 support qualification, not a missing/rejected L4 export or a hidden-information divergence.

Poison explains why the manifest excludes only Fireball: its early override is21.0, while normalized L11 damage92.0 with raw percent−78 gives22% and `(92*22+99)//100 =21`. Both paths are numerically identical. The actual L11 cache contains crown21.0 and multiplier `0.21999999999999997`; its damage is per one-second damage tick, with duration8seconds. Poison is initialized before normalization too, but no differing crown number results for this overlay.

`R/engine-rs/src/lib.rs:853–862` uses the explicit `crown_tower_damage` when present and passes that number to damage application. Thus a tolerance or support override would admit a real crown-physics discrepancy. Fireball carrier `stats.crown_damage` in the preserved export is null; the relevant serialized field is the card's spell field, not that similarly named carrier stat.

## Primary runner assessment and minimal honest fix

**Initialization hazard: demonstrated in the fixture; not demonstrated in a fresh primary invocation.** `W/bot/levels/run.py:635–646` validates the static proof, constructs actual Runtime, then installs masks, loads models/vocabulary and preloads level configs. This puts normalization before builder/spell construction. `W/bot/levels/diagnostics/replay.py:153–167` likewise builds actual Runtime before importing live replay adapters/loading existing configs. The prior s27 receipt/report records23/23 opportunities,23 B roots and zero native failures; its support/raw export identities match the good cache. This is corroboration, not a new run or a guarantee for every entrypoint. An embedding process that already built a builder or touched the registry before Runtime remains vulnerable: Runtime does not enforce/repair that global precondition.

**Cache immutability hazard: shared with the primary runner.** `run.py:321–346` blocks export creation and freezes later level loads, but `:351` still calls the mutating `lc.supported()` before reading/verifying its output. Therefore the primary can silently rewrite an absent/stale support manifest too. With today's bad manifest and a clean normalized Runtime it would likely rewrite it back to good; that is still a forbidden implicit restoration under the existing-only requirement. The verification at `:357–359` occurs after that write and cannot prove immutability. This is a concrete production loader issue, independent of whether the production startup order is correct.

Recommended repair boundaries, for the existing owner/reviewer:

1. In integration mode, have one actual Runtime initialize before ANY builder/game-data/spell construction in the invocation; make both builder and integration fixtures consume that resource without the present cyclic dependency. Reuse `rt.R.builder`. Preserve lightweight optional mode without claiming that a paths-only object is a normalized Runtime. Start validation in a fresh process; clearing one registry late would leave other derived objects/metadata alive.
2. Load only the pre-existing, hash-approved support and export bytes. Verify raw and canonical identities, support comparison/version, exact121-card expected mapping, empty L11 unsupported set, actual normalized `R.config` reference, and exact `check11` agreement before roots. Freeze the loaded support set, levels and build/read paths; reject every unexpected later level read and every receipt/export write. On mismatch, report exact field paths/types/values and hashes before any write.
3. `diagnostics/live.py:65–108` is a useful existing-only pattern: support is read and reference-checked before setting `_supported`; L11 is checked exactly; future reads/builds are blocked. Reuse only with correct independent dependencies/provenance, and add the task's explicit expected raw identities/121-card checks rather than assuming the helper alone enforces them. Do not import diagnostics into the primary merely for convenience. The primary preload call at `run.py:351` also needs an existing-only adapter or a focused read-only option before an immutable-cache primary gate can honestly be claimed.
4. Keep `root.py` fail-closed, level4 stats, qualification rules, scaling, native physics, placement and121-card original support unchanged. No skipping Fireball, fresh export generation, adjusting tolerance, accepting the bad reference, or masking the failure with all11 opponent estimates. Do not reconstruct the support manifest from the polluted runtime.
5. Preserve bad evidence first; only the parent, after fresh review, may perform the already prepared exact-byte restoration and verify original raw SHA. This audit did not restore it. Root and export data require no repair on current evidence. Timed-WAIT diagnosis/implementation remains with its existing owner and is outside this audit.

## Remaining uncertainty and required validation

The source proves an initialization-order defect and the unguarded manifest writer. The preserved manifests prove the reference change and exact Fireball exclusion. We have no failed-process registry snapshot, full bad `R.config` or writer call trace. Consequently do not label the entire `193b…`→`f008…` config difference as empirically proven to be exactly one field, despite the sufficient one-field mechanism and the lack of other L11 exclusions. Full equality over exports does not cover every non-card config field.

After the fresh independent source review and parent-owned byte restoration, required validation is: clean-process integration bootstrap first; assert actual reference193b… and explicit Fireball688/159, Poison92/21 before roots; exact121 support/check11; strict load of L4 Fireball357/83; both opposite-seat hidden-information tests and the full requested five-file suite through real decision paths; before/after raw+canonical equality for all six exports and support; missing/mismatched manifest rejection with no writes; unregistered read/build refusal; then the already required native gates and original all11 cases. A discrepancy must stop with preserved evidence, not generate caches. No tests, models, imports of project code, compilation, native execution, jobs, sync, cache restoration, source edits or descendants were performed for this audit. Only this report was written; local Python used standard-library JSON/hash parsing and read-only SSH output.

Audited source/evidence identity anchors:

```text
W/bot/levels/test_placement.py 372612aef24367b98bbb465bd27aca9668fc3f215f800680810a61db590ce9b1 (also observed on01)
W/bot/players/runtime.py 7de9dd1cf270aba46f31f958c94676139e18dba85ccfb638c7f220e9e736cf2c
W/bot/levels/configs.py 9fc73a910c4ee121a74f79cc53405ed2b93ad4eb3e042c5764ce79fdb3e18da3
W/bot/levels/root.py fb6321a0ce198fdd32de0902280306d4b1eaa11524ad67e322fd96fd88aa91e8
W/bot/levels/run.py 1c9d80e9d2cc5a031a33839b1e54e7a1d19253065affc816453149d96ee8f061
R/src/clasher/spells.py 6214658ec5b0ee6b51a0f62ce10a2531f2488753845911b1ff40165e7ddf0944
R/src/clasher/dynamic_spells.py ca90d41002d0beb41f634aa26578d5158997db2c7b5e1768107edb7a9546ac16
R/src/clasher/data.py ed4ca93fcbc84553725e1dcfc57ce8da4c0dff58bdb01cded5e30fbc98fc332d
R/src/clasher/balance.py 3b05a9439f3ec92cc62982f380e1f14d9fc2d59cd70b49c7a24070f9ed3458cc
R/src/clasher/logic_math.py 810910fd9f7edeab07506340be16116fd6231b50de4849f5e60cd73ab6608ac5
R/engine-rs/differential.py f864ad4b7807da0e8508bf0a368f1fe691cc5c49b12fc0d6ab44697d101eca29
J/dev/pytest-placement-r21.txt 219700e61efcf489939f5377ed02940772f99c2031ff0f050a087705e1e25455
```
Final source-audit timestamp: 2026-10-16T11:55:26Z.
