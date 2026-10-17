# Candidate review r1 repairs

The independent source/probe proposal review **REJECTED** exact
`65fca236e63708c3b1ac1160a00d655f758197d4` for two probe defects. The favorable
uncompiled native-source assessment is retained, without engine acceptance.
`REVIEW-candidate-r1.md` SHA256
`3f369994ebcdce21dec2eeba368900682d51aebdf667e03c409ee05c8d55ed22`
and `review-candidate-r1-receipt.json` SHA256
`15eced664a3436f1aaa3b640381d266b312d4cf59ddd83f005d6f0dfcafa2ad3`
are preserved byte-for-byte. No native source, comparator or captured root changed
for these repairs. A fresh independent exact-commit review is required.

1. **Fresh templates.** The probe now calls the exact frozen contract's
   `fresh_troop_templates` for the raw initial Python root, Python clone, and each
   native uninterrupted/clone/reload root, then for all five arms after every
   step before semantic comparison. It records each root's arm, offset, checked
   template paths and validity. A failed check records its complete root and
   traceback before raising to the case's retained ERROR path. Config equality
   is not inferred from arm equality; the comparator bytes and exclusions stay
   unchanged. Stdlib tests extract the template helper from its SHA-bound source
   without importing the engine, and reject non-fresh config, non-fresh Clone
   template and missing-template controls. Mock full continuations reject a
   poisoned native template on each arm both initially and after stepping, even
   when the semantic-comparison mock reports zero deltas.

2. **Zap transition witnesses.** All five named variants in both seats require
   the constructor actor and every continuation actor, initial travel and the
   named route/stun/frozen guards, and actual transport during the first frame.
   Read-only wrappers installed separately after Python battle cloning call each
   arm's original movement finalizer exactly once, retaining its true entry and
   exit observations even if it raises. These observations identify the
   post-dash/pre-external point, pending vector, retained head/direction, heading,
   current guards and actual post-external point. Witnesses compare the same
   transition with all native arms and require a node pop while the finalizer
   still observes travel, not after ordinary walking takes over. Advancement
   uses the retained direction and signed truncation, consumes exactly one head
   below the strict threshold, and recomputes the next direction. Relevant
   constructor/transition before/after full roots are retained and checked
   against the watched rows. The external vector is now (+250,+1000) logic units
   for blue, (+250,-1000) for red: its first transition must cross from projection
   >=1001 to <1001 and distinguish pre-external from post-external heading.
   Negative controls cover missing actors/observations/paired roots, wrong
   initial and current guards, pop only after travel, excessive node consumption,
   wrong direction/pose/heading, no transport, wrong saved root, heading after
   displacement, advancing before displacement, absent vector and a wrong
   native clone result. Independent observer mocks check unchanged state,
   exactly-once invocation, return/exception forwarding and exit observations.

The external vector remains an explicitly forced robustness fixture, not proof
of normal acquisition. Source inspection additionally shows current native
`collide` returns zero for dash travel before reading a queued controlled vector
(`lib.rs`, `collide`), while Python `begin_movement_tick` reads an already queued
vector after collision accumulation. This is a concrete risk the future strict
fixture must expose, not an executed mismatch or an excuse to weaken the witness.
No additional engine fix is made without a reproduced actual continuation. The
native proposal is unchanged and UNBUILT; failed actual tests must remain FAIL.

The review also resolved an evolving-B2 provenance observation: its earlier
nine-reader match receipt is historical. Current B2 `live_snapshot.py` now has
later WIP too; the reviewer recovered the exact captured exporter read-only from
`7e2f0f165c713c663024198723b62b69551d0f21`, SHA
`c570596018c06241c3215af6b523dac81622a1d3e44b8e2e3c0b9e0224c9a962`.
Neither current B2 source nor old7738 is a frozen integration base. The r1 review
retains its failed provenance assertions and temporary-file disclosure. The
late PROGRESS edit was this owner's dependency audit, not an engine change.

Local verification is only AST/stdlib/mock:
`PYTHONDONTWRITEBYTECODE=1 python3 -B reports/cards/c1/tools/test_shared_troop_probe.py`.
PASS at 2026-10-16T13:16Z; exact refreshed hashes/command output belong to
`candidate-local-receipt-r2.json`. No actual 32-case run, engine import, native
execution, build, host launcher, new job, C56, merge or pin change occurred.

Lead's `B2-C1-base-readiness-20261016.json` explicitly has no frozen base and
blocks dependent build/parity. Stable committed B2 Rage corrections, matching
native/affected evidence, fresh exact-source C56 and reviewed conditional packet
must precede lead's reconciled base, B2-first integration and subsequent C1
build/coverage/C56. All original captures, FAIL denominators, f68/native631ac,
launcher approvals and rollback artifacts remain intact. Roll back only these
new isolated source/probe commits; preserve this rejection and the evidence.
