# Storage-only operating amendment, 2026-10-08

Authorized before formal training and before any heldout payload opening.

Coordinator ownership notice, **2026-10-08 15:19 UTC**: roader is rebuilding
its backups on 09/15 (approximately 30 GB per host), with temporary LAN/disk I/O
contention and then idle storage. This is coordinator-reported context, not an
inspection of roader data. **Never read, write, traverse or delete**
`/mpac/sdicks02/repos/roader-mirror*`, `roader-code-127x05-mirror`, or
`roader-mirror-trash`. V4 files on leased hosts stay under the exact
`/mpac/sdicks02/repos/clasher-lease/` footprint. Any future approved cache cleanup
must use explicit, validated per-match paths within its `data/v4-cache/` root;
no repository-parent cleanup glob, symlink traversal or roader path access.
09/15 caps and existing storage reservations remain unchanged. Keep current
transfer concurrency; account for contention in completion estimates rather than
launching duplicate copies. No jobs, Phase A polls or cleanup launched for this
notice; it does not approve the pending duplicate-cache retirement proposal.

The coordinator's 07:22 UTC decision in [COORDINATOR.md](../../../COORDINATOR.md)
clarifies that T1's frozen **40 GB acquisition cap** governs raw collected matches
on the hub. Derived, regenerable training caches have a separate allowance.
The coordinator explicitly approved **300 GB per permitted host**, retaining at
least **200 GB free on /mpac**. The subsequent user response in this implementation
thread additionally approves **up to 1 TB total cache across permitted hosts**.
Both limits apply: 1 TB aggregate and 300 GB on any one host (decimal units).

Current allocation at **15:23 UTC**: increase03 from110 to120 GB, within existing
aggregate approval. **01=291,18=293,16=215,03=120,09=60,15=10 GB**, **989 GB**;
11 GB remaining covers retained legacy caches (01 measured1,014,516,116 bytes)
and headroom.03 operating limit118 GB, including all partial attempts. At15:38,
replace static per-match shares with a locked aggregate byte ledger; no budget
increase, no refund of partial writes, and2 GB metadata/I/O reserve unchanged.
Seven concurrent reservation checks passed. Frozen evaluation/labels unchanged.

Historical allocation at **15:02 UTC**, following the coordinator's direct GPU
reassignment in this thread (T7→09, T6→15): **01=291,18=293,16=215,03=110,
09=60,15=10 GB**, **979 GB total +21 GB legacy/headroom**. 09/15 now explicitly
join the approved leased cache hosts, same lease-local root. Live root metadata
before shrinking:01=289.444,18=291.833,16=213.910,03=89.095 GB. All roots fit;
no deletion. 03 operating cap108 GB,16 helper215 GB. 09 received71 exact copied
shards (53.915 GB payload);15 stages T6 converter inputs and reserves10 GB for its
bounded training cache. Copies preserve all source data and equality evidence.
The existing349-base duplicates on18 could release289.433 GB, but retirement
requires the pending explicit approval and fresh full SHA verification against01;
see `receipts/preformal-cache-20261008/cache-retirement-proposal-18-base-20261008.json`.
No such retirement was executed or assumed authorized.

Historical allocation at **14:15 UTC**: reassign 70 GB of 16's unused reservation
to 03. Reservations are now **01=300 GB, 18=300 GB, 16=230 GB, 03=150 GB**,
unchanged **980 GB total** plus 20 GB aggregate headroom. Live metadata checks:
16 root 213,909,967,016 bytes with 1,233,202,065,408 bytes free; 03 root 56,817,326,570
bytes with 1,731,909,013,504 bytes free. Neither has an active v4 cache builder;
T11 still holds 16/18 workload locks. No data is moved/deleted, and all reservations
remain below 300 GB/host with 200 GB minimum free. New operating caps: 03=148 GB,
16 unique builder=225 GB. Root growth guards enforce the reservations. This uses
the explicit user authorization to reassign within 1 TB before additional growth.

Historical allocation: at 13:23 UTC, allocate 80 GB of the previously unreserved allowance to home
127x03 for new disjoint train/validation shards while T11 owns the 16/18 workload
locks. Reservations are now 300 GB each for 01/16/18 and 80 GB for 03: 980 GB
maximum, leaving 20 GB for the pre-existing T6/shakedown caches and headroom.
No existing cache is moved or deleted. The 03 writer uses a 78 GB operating cap;
all growth guards enforce its smaller reservation. This is an operating allocation
within the user-approved 1 TB aggregate, not an increase in authorization.
Builds default to a lower 280 GB ceiling. At 10:59 UTC, the 18r10 extension
explicitly uses 295 GB within the existing approval, retaining the 2 GB allocation
reserve and 200 GB free-space floor; no host or aggregate cap is increased. Partial and retained failed attempts
inside each cache root count toward that host's budget. The remaining aggregate
headroom also covers the small pre-existing T6/shakedown image caches.

Approved locations are `/mpac/sdicks02/repos/clasher-v4-cache/` on home hosts
01/03/04/08, and `/mpac/sdicks02/repos/clasher-lease/data/v4-cache/` on leased
11/13/14/16/18, subject to live leases/caps and the reservations above. The hub
pilot moved from `clasher-v4-data/cache/` into its approved root at 07:31 UTC,
without deletion. Leased pilots and the failed 18 attempt moved into their
approved cache roots, preserving bytes and evidence.

Leased caches must be moved off or deleted within one day of lease end (currently
2026-10-10 05:30 UTC, following the 2026-10-09 05:30 UTC lease expiry), with earlier
reclaims honored. Preserve evidence by moving it where practical. The console
cap uses `~/.local/bin/fleet-console-users` (physical seats and other users), as
the coordinator's own SSH monitor was the earlier false positive.

This changes storage operations only. Frozen PREREG/split, collection cap,
training populations/initializations/hyperparameters, validation-only selection,
heldout-opening restrictions and all evaluation thresholds are unchanged.
