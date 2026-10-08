# Phase A train/validation body-label audit

2026-10-08, before formal training. Heldout media and labels remain unopened.

## 09:02 UTC extension, unchanged cleaning rule

Lease 18 `v4-label-audit-20261008-r10` passed on **225 train + 28 validation**
(1004870 / 1004872, exit 0 at 09:02:21; 18 processes, 848,883,712 bytes peak RSS).
Full evidence remains in the host-local r10 JSON; compact counts, match receipt
hashes and its SHA256 are in `receipts/preformal-cache-20261008/label-audit-r10-summary.json`.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 3,669,873 | 515,143 | 407,689 |
| Validation | 437,786 | 61,215 | 48,435 |
| Total | 4,107,659 | 576,358 | 456,124 |

Causes: 247,456 catalog-generation disagreements resolved, 30,548 legitimate
parent/child hints, 120,234 non-hitpoint hints, 178,120 unresolved/masked.
39,863 rich native IDs have zero identity changes; 35,879 contradictory same-tick
joins have zero ID/field mismatches. Future metadata occurs in 3,297,086 rows and
remains excluded from visibility decisions. Coherent visible/nondeploying rows:
121,244 (108,068 train, 13,176 validation). No further label fix or amendment;
board-quality certification remains separate and unmeasured.

## 08:43 UTC extension, unchanged cleaning rule

Lease 18 `v4-label-audit-20261008-r9` passed on **213 train + 26 validation**
matches (1000237 / 1000239, exit 0 at 08:43:58, 18 processes, 849,797,120 bytes
peak RSS). Full per-match evidence remains in the r9 job JSON; the compact
`receipts/preformal-cache-20261008/label-audit-r9-summary.json` pins its SHA256
and admitted receipt hashes. This snapshot includes one train match finalized
after the 08:40 receipt poll.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 3,443,348 | 482,973 | 381,116 |
| Validation | 413,296 | 55,254 | 43,256 |
| Total | 3,856,644 | 538,227 | 424,372 |

Causes: 227,653 catalog-generation disagreements resolved, 27,060 legitimate
parent/child hints, 113,855 non-hitpoint hints, 169,659 unresolved/masked.
37,536 rich native IDs have zero identity changes; all 33,687 contradictory
same-tick joins have zero ID/field mismatches. Future metadata appears in
3,099,562 rows and remains excluded from visibility decisions. Coherent
visible/nondeploying rows: 114,147 (101,661 train, 12,486 validation).
No additional label-generation change or board-quality certification.

## 08:37 UTC extension, unchanged cleaning rule

The same auditor/cleaner passed on **200 train + 25 validation matches** under
lease 18 label `v4-label-audit-20261008-r8` (998522 / 998526, exit 0 at 08:37:42;
18 processes, 850,276,352 bytes peak RSS). The preceding r7 launch was refused
before any child started because the cache gather held the host-wide workload
lock; both receipts are retained. Full evidence remains on 18 in the r8 job JSON;
`receipts/preformal-cache-20261008/label-audit-r8-summary.json` pins its SHA256
and each admitted match receipt.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 3,229,363 | 446,933 | 353,170 |
| Validation | 406,302 | 54,226 | 42,320 |
| Total | 3,635,665 | 501,159 | 395,490 |

Primary causes: **210,896** catalog-generation disagreements resolved by unique
payload/HP, **24,419** legitimate parent/child hints, **105,669** non-hitpoint
parent hints, and **160,175** unresolved/masked contradictions. Across 35,317
rich native IDs there are zero identity changes; among 31,472 contradictory
same-tick joins there are zero ID/field mismatches. Future metadata appears in
2,923,410 rows and remains unusable for same-tick visibility. The cleaner retains
107,612 coherent visible/nondeploying rows (95,442 train, 12,170 validation).
No additional label-generation fix was needed. Amendment 03's downstream cleaner
continues to apply to every split; this audit does not certify board precision.

## 07:36 UTC extension, unchanged cleaning rule

After the coordinator approved derived-cache storage, the same auditor and
cleaner were applied to all **163 train + 20 validation matches** in the 07:32
snapshot. Lease 18 job `v4-label-audit-20261008-r6` passed (supervisor 976542,
child 976544, exit 0; 18 processes, 849,616,896 bytes peak RSS). Full per-match
evidence remains in that host's `clasher-lease/jobs/v4-label-audit-20261008-r6.json`;
compact evidence and its SHA256 are in
`receipts/preformal-cache-20261008/label-audit-r6-summary.json`.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 2,599,498 | 366,706 | 288,115 |
| Validation | 319,049 | 44,920 | 36,484 |
| Total | 2,918,547 | 411,626 | 324,599 |

Primary causes: 169,501 catalog-generation disagreements resolved by unique
payload/HP, 20,938 legitimate parent/child hints, 87,027 non-hitpoint parent
hints, and 134,160 unresolved/masked contradictions. There are 28,824 rich native
IDs, **zero changing identities**, and **zero ID/field mismatches** among 25,949
contradictory same-tick joins. Future metadata occurs in 2,339,470 rows; the
cleaner still requires coherent same-tick visibility/deploy evidence. It retains
86,475 visible/nondeploying rows (76,710 train, 9,765 validation).

No additional label-generation change was needed. Amendment 03's same cleaner
remains the downstream code for every split, including later authorized heldout.
These weak-label checks do not certify a board-precision evaluation gate.

## Original 06:38 UTC audit snapshot

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
