# Phase A train/validation body-label audit

2026-10-08, before formal training. Heldout media and labels remain unopened.

## Final513-train/64-validation population, 2026-10-08 15:54 UTC

All577 receipt pins match final cache/source staging. Compact evidence
`receipts/formal-20261008/final-label-audit-summary.json`; raw retained15 with SHA
`4c91e47028ed16c0d4b6aeb1336e045d6c4a13ab05a13d298787c8243da626f4`.

| Population | Object rows | Contradictions | HP-bearing contradictions |
|---|---:|---:|---:|
| Train | 8,424,736 | 1,177,271 | 927,692 |
| Validation | 947,295 | 129,951 | 103,510 |
| Total | 9,372,031 | 1,307,222 | 1,031,202 |

Causes:544,623 catalog-generation disagreements resolved,72,684 legitimate
parent/child hints,276,020 non-HP hints,413,895 unresolved/masked.89,334 rich IDs
and81,586 contradictory same-tick joins have no identity/field changes.
7,525,150 future metadata rows excluded from visibility;272,732 coherent visible/
nondeploying rows. Same cleaner and amendment03; no new label rule. Heldout labels
remain unopened and will pass through the same split-independent cleaner.
The outer preparation job subsequently failed on a missing converter dependency;
that failure does not change these completed checksum-pinned audit results.

## 15:41 UTC pinned559-match audit, unchanged cleaning rule

Lease15 `v4-label-audit-20261008-15r1`, supervisor3649655, exit0 at15:41:42.
Four workers; exact same497 train+62 validation receipt pins as559-cache coverage.
Compact evidence: `receipts/preformal-cache-20261008/label-audit-15r1-summary.json`.
Raw evidence retained15, SHA256
`48ebba8d978b41d3f156cabc50ade8c29d08c05e7af22964a2fcc5d84b17ea33`.

| Population | Object rows | Contradictions | HP-bearing contradictions |
|---|---:|---:|---:|
| Train | 8,132,616 | 1,137,568 | 894,638 |
| Validation | 927,993 | 128,459 | 102,232 |
| Total | 9,060,609 | 1,266,027 | 996,870 |

Causes:528,009 catalog-generation disagreements resolved,70,622 legitimate
parent/child hints,269,157 non-HP hints,398,239 unresolved/masked.86,573 rich IDs
show no identity changes;79,106 contradictory same-tick joins show no ID/field
mismatch.7,273,892 rows with future metadata remain excluded from visibility;
263,561 coherent visible/nondeploying rows. No new cleaning rule or amendment.
Heldout labels remain unopened and will use this same cleaner after authorization.

## 14:52 UTC hub extension, unchanged cleaning rule

Home01 `v4-label-audit-20261008-01r23`, wrapper 3654705, exit 0:
**477 train +59 validation matches**, eight workers. Compact receipt:
`receipts/preformal-cache-20261008/label-audit-01r23-summary.json`.
Raw SHA256: `81df1647c891ba763dc7ce4b93b6fde9bec5ef54d58b1f93753c18da7a4dd410`; raw evidence remains on 01.

| Population | Object rows | Contradictions | HP-bearing contradictions |
|---|---:|---:|---:|
| Train | 7,823,369 | 1,094,231 | 860,553 |
| Validation | 881,916 | 122,810 | 97,920 |
| Total | 8,705,285 | 1,217,041 | 958,473 |

Causes: 507,460 generation disagreements resolved, 69,424 legitimate parent/child
hints, 258,568 non-HP parent hints, 381,589 unresolved/masked. 83,323 rich IDs
have no changes; 76,088 contradictory same-tick joins have no ID/field mismatch.
Future metadata: 6,990,788 rows excluded from visibility; coherent visible/
nondeploying: 253,830. Cleaner/amendment03 unchanged, no new label rule.
This later train/validation audit includes three more train matches than the
14:47 cache admission. No heldout payload access.

## 14:02 UTC hub extension, unchanged cleaning rule

Home01 `v4-label-audit-20261008-01r22`, wrapper 3639403, exit 0 at 14:02:40:
**441 train +55 validation matches**, eight workers. Compact receipt:
`receipts/preformal-cache-20261008/label-audit-01r22-summary.json`.
Raw SHA256: `8c72b63a6ec11db782f410717dc2c34a035a6c359ea050c59354782b7e22752c`; raw evidence retained on 01.

| Population | Object rows | Contradictions | HP-bearing contradictions |
|---|---:|---:|---:|
| Train | 7,247,612 | 1,010,844 | 795,338 |
| Validation | 827,590 | 112,969 | 88,988 |
| Total | 8,075,202 | 1,123,813 | 884,326 |

Causes: 467,877 generation disagreements resolved, 64,495 legitimate parent/child
hints, 239,487 non-HP hints, 351,954 unresolved/masked. 77,519 rich IDs: zero changes.
70,378 contradictory same-tick joins: zero ID/field mismatches. Future metadata:
6,484,093 rows excluded from visibility; coherent visible/nondeploying 236,184.
Same cleaner/amendment03, no additional label change or heldout access.

## 13:31 UTC hub extension, unchanged cleaning rule

Home01 `v4-label-audit-20261008-01r21`, wrapper 3631447, exit 0 at 13:31:05:
**420 train +52 validation matches**. Eight workers, console=0; no lease lock bypass.
Compact receipt: `receipts/preformal-cache-20261008/label-audit-01r21-summary.json`.
Raw audit SHA256: `a1229ece3cf2e970feddb506ef5ae2f3f02782d73cb03828b61f30d4d5c3c06d`; raw evidence stays on 01.

| Population | Object rows | Name/hint contradictions | HP-bearing contradictions |
|---|---:|---:|---:|
| Train | 6,878,992 | 967,682 | 760,393 |
| Validation | 794,309 | 109,842 | 87,304 |
| Total | 7,673,301 | 1,077,524 | 847,697 |

Causes: 451,024 generation disagreements resolved, 62,019 legitimate parent/child
hints, 229,827 non-hitpoint hints, 334,654 unresolved/masked. 74,107 rich IDs with
zero identity changes; 67,608 contradictory same-tick joins with zero ID/field
mismatches. Future metadata 6,157,924 rows excluded from visibility; coherent
visible/nondeploying 225,190. Same cleaner and amendment03, no new label rule,
collector/split edits or heldout access. This snapshot follows the 13:29 cache plan.

## 12:43 UTC hub extension, unchanged cleaning rule

Home 01 `v4-label-audit-20261008-01r20` exit 0 at 12:43:39, wrapper 3618271,
on **385 train + 48 validation**. T11 holds the 16/18 lease locks; no bypass.
Compact receipt: `receipts/preformal-cache-20261008/label-audit-01r20-summary.json`.
Raw SHA256: `0ac10be58a9e02040b298add2ae8bf04beaaf0ed6a70ac8229be6029b93b765d`. Raw evidence remains on 01.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 6,317,482 | 883,583 | 693,285 |
| Validation | 735,244 | 99,296 | 78,096 |
| Total | 7,052,726 | 982,879 | 771,381 |

Causes: 414,390 catalog-generation disagreements resolved, 55,951 legitimate
parent/child hints, 211,498 non-hitpoint hints, 301,040 unresolved/masked.
68,304 rich IDs: zero identity changes. 61,714 contradictory same-tick joins:
zero ID/field mismatches. Future metadata: 5,651,815 rows, excluded from visibility;
coherent visible/nondeploying: 206,470. Same cleaner, no new amendment or heldout
access. This snapshot arrived after the latest receipt-only Phase A check.

## 12:14 UTC extension, unchanged cleaning rule

Lease 16 `v4-label-audit-20261008-r18` PASS on **360 train + 44 validation**
(3536549 / 3536551, exit 0 at 12:14:52; 18 processes, 887,746,560 bytes peak RSS).
Compact receipt: `receipts/preformal-cache-20261008/label-audit-r18-summary.json`.
Raw SHA256: `ee4a2ee3004b2b5f50b59af84260d2f1556bbe27499385096122db44ea7359db`.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 5,924,417 | 828,649 | 649,419 |
| Validation | 675,556 | 92,594 | 73,007 |
| Total | 6,599,973 | 921,243 | 722,426 |

Causes: 388,444 catalog-generation disagreements resolved, 52,613 legitimate
parent/child hints, 198,817 non-hitpoint hints, 281,369 unresolved/masked.
64,165 rich IDs have zero identity changes; 57,896 contradictory same-tick joins
have zero ID/field mismatches. Future metadata: 5,292,994 rows, excluded from
visibility; coherent visible/nondeploying: 193,427. No cleaner change, new
amendment, heldout access or board-quality certification.

## 12:06 UTC extension, unchanged cleaning rule

Lease 16 `v4-label-audit-20261008-r17` PASS on **347 train + 43 validation**
(3534466 / 3534468, exit 0 at 12:06:15; 18 processes, 874,946,560 bytes peak RSS).
Compact receipt: `receipts/preformal-cache-20261008/label-audit-r17-summary.json`.
Raw SHA256: `8d1d50dffa48c01a88017295223a9601a68ff8e6a59beff9746c9165080522ee`.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 5,738,931 | 807,212 | 632,501 |
| Validation | 653,718 | 89,062 | 70,950 |
| Total | 6,392,649 | 896,274 | 703,451 |

Causes: 378,513 catalog-generation disagreements resolved, 52,055 legitimate
parent/child hints, 192,823 non-hitpoint hints, 272,883 unresolved/masked.
62,157 rich native IDs have zero identity changes; 56,170 contradictory same-tick
joins have zero ID/field mismatches. Future metadata: 5,124,560 rows, excluded
from visibility. Coherent visible/nondeploying: 187,151. No cleaner change,
new amendment, heldout access or board-quality certification.

## 11:48 UTC extension, unchanged cleaning rule

Lease 16 `v4-label-audit-20261008-r16` PASS on **333 train + 41 validation**
(3528397 / 3528399, exit 0 at 11:48:14; 18 processes, 873,484,288 bytes peak RSS).
Compact receipt: `receipts/preformal-cache-20261008/label-audit-r16-summary.json`.
Raw SHA256: `61e57d857004d604127a3bf84e9de915899a1daac2926589d6aeeec72f713b25`.
Cleaner SHA on 16 and 05: `80dd456fd3f4491810bb234a2fa9ac33bb99d17c722c9b006a878b22a121ee8a`.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 5,498,172 | 770,025 | 602,518 |
| Validation | 623,873 | 81,697 | 64,279 |
| Total | 6,122,045 | 851,722 | 666,797 |

Causes: 354,099 catalog-generation disagreements resolved, 50,052 legitimate
parent/child hints, 184,925 non-hitpoint hints, 262,646 unresolved/masked.
59,613 rich native IDs have zero identity changes; 53,451 contradictory same-tick
joins have zero ID/field mismatches. Future metadata: 4,906,469 rows, excluded
from visibility. Coherent visible/nondeploying: 179,455. No cleaner change,
new amendment, heldout access or board-quality certification.

## 11:03 UTC extension, unchanged cleaning rule

Lease 18 `v4-label-audit-20261008-r15` PASS on **311 train + 38 validation**
(1035384 / 1035386, exit 0 at 11:03:39; 18 processes, 863,956,992 bytes peak RSS).
Compact receipt: `receipts/preformal-cache-20261008/label-audit-r15-summary.json`.
Raw SHA256: `be91cffd1a6c2a372e103f56962b3dc27e5d6d0c69880ad50ac258f4d7b8eab7`.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 5,165,866 | 728,785 | 571,272 |
| Validation | 594,245 | 75,629 | 59,892 |
| Total | 5,760,111 | 804,414 | 631,164 |

Causes: 336,433 catalog-generation disagreements resolved, 45,108 legitimate
parent/child hints, 173,250 non-hitpoint hints, 249,623 unresolved/masked.
56,172 rich native IDs have zero identity changes; 50,460 contradictory same-tick
joins have zero ID/field mismatches. Future metadata: 4,620,093 rows, excluded
from visibility. Coherent visible/nondeploying: 169,485. No cleaner change,
new amendment, heldout access or board-quality certification.

## 10:37 UTC extension, unchanged cleaning rule

Lease 18 `v4-label-audit-20261008-r14` PASS on **289 train + 36 validation**
(1028858 / 1028874, exit 0 at 10:37:35; 18 processes, 870,932,480 bytes peak RSS).
Compact receipt: `receipts/preformal-cache-20261008/label-audit-r14-summary.json`.
Raw SHA256: `78c4f813dab6aea5db1bfea7ae8f26b3a7e5d407748d252691e7192f8b3187b5`.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 4,790,933 | 677,353 | 531,149 |
| Validation | 562,066 | 73,772 | 58,341 |
| Total | 5,352,999 | 751,125 | 589,490 |

Causes: 312,526 catalog-generation disagreements resolved, 41,541 legitimate
parent/child hints, 161,635 non-hitpoint hints, 235,423 unresolved/masked.
52,483 rich native IDs have zero identity changes; 47,154 contradictory same-tick
joins have zero ID/field mismatches. Future metadata: 4,290,286 rows, excluded
from visibility. Coherent visible/nondeploying: 157,671. No cleaner change or
new amendment; heldout untouched, no board-quality certification.

## 10:16 UTC extension, unchanged cleaning rule

Lease 18 `v4-label-audit-20261008-r13` passed on **278 train + 34 validation**
(1023052 / 1023056, exit 0 at 10:16:19; 18 processes, 865,759,232 bytes peak RSS).
Compact receipt: `receipts/preformal-cache-20261008/label-audit-r13-summary.json`.
Raw SHA256: `5a570254af58653d4c09c2cefaff3a0e8331ba0cb08806ed1dc018d4e9bada5c`.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 4,584,041 | 642,534 | 501,709 |
| Validation | 538,475 | 69,643 | 54,924 |
| Total | 5,122,516 | 712,177 | 556,633 |

Causes: 293,111 catalog-generation disagreements resolved, 40,489 legitimate
parent/child hints, 155,544 non-hitpoint hints, 223,033 unresolved/masked.
50,169 rich native IDs have zero identity changes; 44,835 contradictory same-tick
joins have zero ID/field mismatches. Future metadata: 4,105,591 rows, excluded
from visibility. Coherent visible/nondeploying: 150,645 (135,086 train, 15,559
validation). No cleaning change or new amendment; no board-quality certification.

## 09:47 UTC extension, unchanged cleaning rule

Lease 18 `v4-label-audit-20261008-r12` passed on **256 train + 31 validation**
(1015955 / 1015959, exit 0 at 09:47:22; 18 processes, 865,116,160 bytes peak RSS).
Compact receipt: `receipts/preformal-cache-20261008/label-audit-r12-summary.json`.
Raw SHA256: `8e634b6705a81e8439090baea0d2cc4a0e342ab167f6013c05822a5ce8782d90`.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 4,221,445 | 588,547 | 463,811 |
| Validation | 508,187 | 66,903 | 52,719 |
| Total | 4,729,632 | 655,450 | 516,530 |

Causes: 275,205 catalog-generation disagreements resolved, 36,791 legitimate
parent/child hints, 138,920 non-hitpoint hints, 204,534 unresolved/masked.
46,119 rich native IDs have zero identity changes; 41,058 contradictory same-tick
joins have zero ID/field mismatches. Future metadata: 3,796,034 rows, excluded
from visibility. Coherent visible/nondeploying: 140,031 (125,339 train, 14,692
validation). No cleaning change or new amendment; no board-quality certification.

## 09:23 UTC extension, unchanged cleaning rule

Lease 18 `v4-label-audit-20261008-r11` passed on **239 train + 29 validation**
(1009974 / 1009978, exit 0 at 09:23:37; 18 processes, 849,641,472 bytes peak RSS).
Full raw evidence stays on 18; compact counts and per-match receipt hashes are
in `receipts/preformal-cache-20261008/label-audit-r11-summary.json`, raw SHA256
`fbe13ad42c818623135f04a9a347d9123860b42e238a3f81091390a7d52ed5cf`.

| Population | Object rows | Name/hint contradictions | Hitpoint-bearing contradictions |
|---|---:|---:|---:|
| Train | 3,895,267 | 548,869 | 433,098 |
| Validation | 458,928 | 64,830 | 51,549 |
| Total | 4,354,195 | 613,699 | 484,647 |

Causes: 261,868 catalog-generation disagreements resolved, 34,235 legitimate
parent/child hints, 129,052 non-hitpoint hints, 188,544 unresolved/masked.
42,475 rich native IDs have zero identity changes; 38,299 contradictory same-tick
joins have zero ID/field mismatches. Future metadata occurs in 3,494,319 rows and
remains excluded from visibility. Coherent visible/nondeploying: 128,864
(115,214 train, 13,650 validation). No additional cleaning change or amendment;
heldout later uses the same cleaner after its authorization gates.

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
