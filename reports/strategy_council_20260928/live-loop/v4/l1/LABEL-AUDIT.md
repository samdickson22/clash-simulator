# Phase A train/validation body-label audit

2026-10-08, before formal training. Heldout media and labels remain unopened.
Audited snapshot: **121 training + 15 validation matches**, admitted against the
unchanged frozen split. Eight CPU audit workers ran under the lease wrapper on
127x16. Full evidence remains at
`127x16:/mpac/sdicks02/repos/clasher-lease/jobs/v4-label-audit-20261008-r5.json`.
The compact checked-in receipt is
`receipts/preformal-cache-20261008/v4-label-audit-summary-r5.json`; it records
per-match receipt hashes and the full audit's SHA256.

## Counts

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 1,841,449 | 244,261 | 193,550 |
| Validation | 232,762 | 30,962 | 24,752 |
| Total | 2,074,211 | 275,223 | 218,302 |

These are repeated object-observation rows, not unique bodies or events.
There are 20,152 distinct rich-snapshot native IDs across these matches.

| Primary classification among the 275,223 contradictions | Rows |
|---|---:|
| Catalog-generation disagreement, resolved by unique reachable payload + exact max HP | 114,371 |
| Legitimate parent/child hint difference, resolved by the same rule | 14,321 |
| Projectile/effect or other non-hitpoint object with a parent hint | 56,921 |
| Unresolved/ambiguous; remains masked | 89,610 |

Examples: runtime ID 34000019 was named GiantSkeleton while the GoblinGang or
GoblinHut payload graph and 133 HP uniquely identify SpearGoblin (48,517 rows).
ID 34000021 was named SpearGoblin for a 1,697-HP HogRider (15,400 rows).
ID 34000055 was named SkeletonBalloon for the 261-HP RascalGirl child (8,402).
RoyalDelivery's 547-HP DeliveryRecruit (16,504) is another catalog mismatch.
GoblinBarrel→Goblin and Golem→Golemite are legitimate parent/child differences.

This audit does **not** claim every disagreement is fully diagnosed. For example,
BarbLog's observed 716 HP does not match the reachable pinned payload's expected
HP; this remains unresolved and masked. Variant payloads sharing HP also remain
ambiguous. No names are guessed from visual appearance or hints alone.

## Timing and association checks

Of contradictory rows, 17,608 have a retained same-tick rich snapshot. All
17,608 agree on runtime data ID, owner, card ID, x/y, current HP and maximum HP:
**zero mismatches**. Across 20,152 rich native-ID trajectories, **zero** change
owner/card/runtime-data identity. Thus these inspected contradictions do not
support track-association or receipt-timing mismatch as their primary cause.
Unsampled intervals are not certified by this observation.

There is a separate temporal label-generation problem: the collector's final
rewrite attaches the last per-ID metadata to every earlier row. **1,671,008**
rows have `metadata_tick > row.tick` (train 1,482,642; validation 188,366).
No observed identity changes make this the explanation for the catalog
contradictions, but it cannot justify earlier visibility or deployment flags.
The downstream cleaner uses only a coherent same-tick rich snapshot for those
flags. Repeated snapshots at the same tick must agree on identity, position,
HP, visibility and deploying state; otherwise that object's flags are masked.
Original collector files and payloads are unchanged.

## Downstream repair and remaining masks

`labels_v4.py` replaces the unverified catalog lookup with a conservative,
split-independent card-payload/HP resolver. It traverses the pinned gamedata
graph, follows spawn/morph references, applies the existing level-11 stat rule,
and accepts only a unique body identity. Tower anchors require exact maximum
HP. It never treats an unresolved body as background, and never infers sprite
visibility from identity or HP alone. `data_v4.py` consumes this cleaner.
The same function is required for the future heldout label adapter; there is
no heldout-specific fit or label rule.

Post-cleaning totals: 771,939 tower identities and 835,083 unique payload/HP
identities; 225,249 non-hitpoint objects, 52,545 unresolved payloads, and 189,395
ambiguous payloads stay masked. 597,353 names change or become unknown. Only
**62,697** rows additionally have coherent visible/nondeploying evidence
(55,547 train; 7,150 validation). Compared with simply retaining the original
flags, 364 rows lose those positive flags on this stricter join. Weak boxes and
HP use coherent rows only.

The label change is dated in PREREG-AMENDMENT-03.md before formal training.
Focused regressions pass for catalog disagreement, spell payloads, unknown HP,
same-tick flags, incoherent joins, preservation of original rows, lossless
codec roundtrips and heldout cache rejection. This remains weak supervision;
it does not replace a reviewed annotation audit or pass a board-quality gate.
