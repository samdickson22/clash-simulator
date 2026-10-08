# Storage-only operating amendment, 2026-10-08

Authorized before formal training and before any heldout payload opening.

The coordinator's 07:22 UTC decision in [COORDINATOR.md](../../../COORDINATOR.md)
clarifies that T1's frozen **40 GB acquisition cap** governs raw collected matches
on the hub. Derived, regenerable training caches have a separate allowance.
The coordinator explicitly approved **300 GB per permitted host**, retaining at
least **200 GB free on /mpac**. The subsequent user response in this implementation
thread additionally approves **up to 1 TB total cache across permitted hosts**.
Both limits apply: 1 TB aggregate and 300 GB on any one host (decimal units).

Current explicit reservations are 300 GB each for 127x01, 127x16 and 127x18:
900 GB maximum, leaving 100 GB unreserved. No fourth cache host is admitted by
the cache writer until reservations are reassigned within the aggregate limit.
Builds currently use a lower 280 GB ceiling. Partial and retained failed attempts
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
