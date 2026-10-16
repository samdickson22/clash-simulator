# B1 integration with fixed main — public correction pending

Original B1 acceptance remains at `1dab5bce4a550eb4a99e21558d62ab231db84b5a` / source `fb7c2895a967d6d7f10a017fc02b3a47c6ff83de` / native `63db3e164e906de1729cd021ec0ddd75188ad71407f19a635fe4768ec7f925bc`. Its16/577/600 receipts were preserved; they do not certify this combination.

Combined source: normal merge `5c8afc2d78cb9160c42cd2536f1588cc0dc98c6e` of fixed main `ae3f6b0c579c5c817630b92a64089917c6623704` into original B1. Full506 source manifest SHA `7d68fdd82b92e62dfb875ba18cac8e10a1e6679cd115d3c8f188ae69a8c19d80`. Native SHA `6737c140a4ab2792df22e53190001c58208f4ea27b9fd4d0cb0862e0e2f8161d`, built04 run `review-r1-main-20261016-01`,11:04:34Z, cpu_job4 nice15.

## Integration corrections

- `src/lib.rs`: retain main persistent grid/lazy insertion, RouteCtx/in_tick, synchronous first updates and hidden-sibling exclusions; retain B1 mounted-neighbor exclusion, immunity stats/default omission. Remove obsolete deferred drain; carry original live mounts after synchronous combat callbacks and before movement using captured headings, matching Python. Do not rebuild fixed grid extents on carry.
- `differential.py:entity`: retain both B1 selector/mount exports and main public_identity/public_static template metadata. Native intentionally ignores exporter-only metadata; no new serialized C56 defaults.
- `src/c56.rs:bomb_tick`: replace clean-merged references to the deleted fresh queue. A container source clone forces shared per-child synchronous first update once after initialization/Freeze. Ordinary C56 bombs retain their existing path.
- `entities.py:TimedExplosive._spawn_death_units`: initialize target priority/cache and inherit Freeze before synchronous first update, matching the corrected shared native path and Batch A DeathSpawn ordering.
- Keep main compatibility/public-template commits and clean-merged spawn/leap/Python changes; no B2/C1 queue/selector or broad snapshot normalization.

## Evidence

| Check | Current result |
|---|---|
| Independent source and execution preflight | Source/build/test/affected approved02; reference procedure approved03; gate safety approved, actual prerequisites still apply |
| Combined native build | PASS; one pre-existing unused_mut warning |
| Original B1 graph, geometry, Mirror, immunity, selector controls and continuations | PASS16/16, run01-regressions.json;11:09:26Z |
| Affected synchronous paths, nested riders/container, scenario locksteps and exporter/config | PASS94/94 corrected run02; failed01 artifacts retained (six harness-assumption errors) |
| Combat carry and observable once-only container supplement | PASS4/4 both seats; exact native continuations |
| RoyaleSim16.402 original/current reference comparison | 39/39 paired regression checks,78 runs, no observable changes or harness gaps; reference22PASS/17DIFF retained |
| Fresh exact-native C56 fixtures/chains577 + roots600 on source5c8/native6737 | PASS577/577 fixture records/chains,429 reference matches,0 errors;600/600 roots300full+300cut,12games/1800selections; completed12:17:48Z; run02-gate-compare.json |
| Final independent implementation/evidence review | Pending exact complete results |

No combined readiness or publication yet. The source5c8 results above precede the explicit public alias candidate c13249919 and pending root consumer repair; they do not certify that new source. CARD LEAD authorized existing ThreeMusketeers body/projectile identity and an explicit700ms public-model load default while engine ranks remain700/650/700ms; frozen vocabulary/model dimensions stay unchanged. Actual emitted-carrier coverage, reviewed root integration, fresh exact-source acceptance and final independent review remain required. Existing partial RoyaleSim fidelity, Rune Giant enchantment coverage gap and raw Python/native snapshot representation differences remain. Full serialized equality applies to native clone/reload continuations; digests and selected cross-engine fields do not prove whole-state equivalence.

Rollback: preserved `cards/b1-before-main-20261016` at exact original1dab plus immutable original receipts/native. No active runtime pins, immutable runtime roots or main/shared checkouts changed. Lead owns main merge; B2→C1 order retained.

## Per-card evidence

All13 cards have3/3 matching native/Python fidelity-scenario locksteps on the raw data. Reference probes use the same scratch stat overlay for original/current Python, with RoyaleSim16.402. All39 original/current measured observables are unchanged. PASS/DIFF below are the reference comparator's actual limited-probe verdicts, not full mechanics certification. Rune Giant enchantment remains unaudited. No new stat rows were added to git or source gamedata.

| Card | Native/Python | Reference alone / knight / minions (buildings: alone / hog / giant) | Regression |
|---|---|---|---|
| RoyalRecruits | 3/3 | PASS / DIFF / PASS | unchanged |
| ThreeMusketeers | 3/3 | DIFF / DIFF / DIFF | unchanged |
| GiantSkeleton | 3/3 | PASS / DIFF / DIFF | unchanged |
| SkeletonBalloon | 3/3 | DIFF / DIFF / DIFF | unchanged |
| Hunter | 3/3 | DIFF / PASS / DIFF | unchanged |
| MiniSparkys | 3/3 | DIFF / DIFF / DIFF | unchanged |
| RoyalGiant | 3/3 | PASS / PASS / PASS | unchanged |
| BattleHealer | 3/3 | PASS / PASS / PASS | unchanged |
| GoblinGiant | 3/3 | DIFF / PASS / PASS | unchanged |
| GiantBuffer | 3/3 | PASS / PASS / PASS | unchanged |
| Tombstone | 3/3 | PASS / DIFF / PASS | unchanged |
| BarbarianHut | 3/3 | PASS / PASS / PASS | unchanged |
| Witch | 3/3 | DIFF / PASS / PASS | unchanged |
