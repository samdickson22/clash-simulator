**Changes requested. Build and affected-test execution are blocked by source-confirmed defects.** No scripts, imports, builds, native tests, SSH, jobs, or edits were performed.

1. **P1 — Removed queue still referenced; combined native cannot compile.** [c56.rs:188](/mpac/sdicks02/repos/clasher-cards-b1/engine-cards/src/c56.rs:188) reads and writes `self.fresh`, but the merged `BattleState` removed that field. Reconcile Skeleton Barrel’s container-release path with synchronous `first_update_now`, preserving initialization/Freeze ordering and exactly one first update per emitted child. Removing only `drain!` leaves this clean-merge dependency unresolved.

2. **P2 — Affected probe’s import disagrees with staging.** [affected.py:24](/mpac/sdicks02/repos/clasher-cards-b1/reports/cards/b1/main-integration/tools/affected.py:24) loads `tools/b1/review_regressions.py`; [HOST-PLAN.md:5](/mpac/sdicks02/repos/clasher-cards-b1/reports/cards/b1/main-integration/HOST-PLAN.md:5) places it at `tools/review_regressions.py`. Following the documented staging produces a startup `FileNotFoundError`.

3. **P2 — Two path families cannot satisfy the new witness requirements.** [affected.py:52](/mpac/sdicks02/repos/clasher-cards-b1/reports/cards/b1/main-integration/tools/affected.py:52) requires a death witness and a later/no-death control:
   - `frozen_tombstone_death` deploys its victim in the script, but the imported helper captures `victims` before scripted deployments and never refreshes it. Its death witness therefore remains `None` in both seats.
   - `tower_shot_drill` has no scripted action or opposing setup entity to remove. The generated control retains the attacking default tower and identical setup, so it cannot establish later death.
   
   Repair victim tracking and construct controls that retain the victim while suppressing the relevant killing effect.

The inspected `lib.rs` carry placement otherwise matches Python: capture original live mount headings, finish synchronous combat callbacks, carry riders, then move original entities. Persistent grid/`RouteCtx`/`in_tick`, hidden-sibling filtering, mounted combat eligibility and movement exclusion remain. Mounted neighbors retain the accepted static-avoidance classification in both engines. Both selector/mount exports and main’s `public_identity`/`public_static` block survive; the compatibility changes remain present. No further actionable integration defect found in the inspected clean merges.

Separate preflight dispositions:

- **Build:** blocked by finding 1. The documented isolated offline build procedure is otherwise acceptable.
- **Tests:** unchanged original 16-case runner is acceptable; execution needs the new build. **Affected phase blocked** by findings 2–3. Its GG adjacency, hidden/Freeze witnesses and exact native clone/reload checks are useful once repaired.
- **Gate:** launcher safety is acceptable for the fixed fresh 04 run, with documented liveness/hash checks, lease ≤4, nice15, serialization and group draining. **Execution remains blocked by preceding phases.** Actual combined 577/577 + 600/600 evidence and final evidence review remain pending; original acceptance does not cover this combination.

Reviewed parents:

```text
HEAD       1dab5bce4a550eb4a99e21558d62ab231db84b5a
MERGE_HEAD ae3f6b0c579c5c817630b92a64089917c6623704
```

All 506 source-manifest entries verify; tracked engine worktree matches the staged resolution. Exact SHA-256 identities:

```text
source.sha256
87289d6f84aeecc6b964b7fbe1b1898e877f5eec9f1c482e9eaee5038cfd247a
jobs.sh
e9cfa7e93e3f6826e8f8526962a1483f1e7d22b5f55dc45b68606d49f862f6dc
affected.py
dd8d508cadd037b685edcb890cc856397f776ccc7ca107d783305cf73adb812d
HOST-PLAN.md
bf79137bc95c31329f211b3d9417ba36d5e8c87cb9936f241e30b2ee00470037
src/lib.rs
47af04cc6c6d6ea7a643842721d243b6e0a49951b3f83deb6af1f8be11cda3f6
src/c56.rs
7d0426bee7a3d480563083b3c263c8be55483dd15bc09d0cccafb2ea8ad05785
original review_regressions.py — unchanged from HEAD
9932be076e02a61e6b2c9cc2b73e8f6334c301155c6127eb5db1eda569f4e897
```

No combined native identity or execution receipt exists in this review.
