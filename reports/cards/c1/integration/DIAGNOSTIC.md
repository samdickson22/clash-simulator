# B2-first C1 diagnostic integration

User/CARD LEAD supplied the isolated worktree and frozen prerequisite at
`9fa2ea993f5d0d26109b2fc2201db3c83dbf6089`, branch
`cards/b2-c1-integration-20261016`. The immutable base ref
`cards/b2-c1-base-20261016` must not move. Controlling brief:
`/mpac/sdicks02/repos/clasher-cards/reports/cards/reviews/B2-first-C1-diagnostic-integration.md`.
This authorizes a reviewed, fresh diagnostic build and meaningful32/focused
continuations. Final full C1 C56, main/pin/runtime acceptance still await the
later reconciled B1/current-main source freeze. Original cards/c1 and all native,
FAIL, review and capture artifacts remain unchanged.

## Merge and scope

Verified clean tracked state and exact base/ref before running:
`git merge --no-commit --no-ff 11ff9548c25de3d1c079bfa2425faf3955fefd8e`.
The merge is B2 first, C1 second; the two actual conflicts are resolved as follows.

- `src/lib.rs`, movement target revalidation: retain B2 `lock_after()` (the max
  of stealth and target-acquisition delay), then retain C1's ramp-specific
  dash-travel guard. Reverting to only stealth would lose B2's delay correction.
- `src/projectiles.rs`, rolling character hit scan: retain B2's dash exclusion,
  C1's straight-boulder radius/hit sampling and stealth/area-while-invisible
  predicate. Neither a skipped recipient nor its ID becomes a remembered hit.

Clean merges include B2 Clone dispatch and status/effect target guards alongside
C1 Ronin queues, new dash/leap state schema, frozen-route/heading/Spirit helper,
clock/recoil, wizard creation areas, boulder/axe and Dragon chain changes. The
complete engine delta and SHA inventory are review inputs; auto-merging does not
establish semantic correctness. There are28 engine paths changed from B2 (the
full C1 scope), not merely the shared helper's three Rust paths.

Explicit B2 carryovers are preserved without blanket effect filters:
`attacks.rs:secondary_recipients` follows `Entity.can_attack_target`, while new
`c56.rs:chain_release` follows `_can_chain_to` and secondary targetability. The
frozen B2 RESULTS audit373/375/587–593 states that these selectors may reserve
dash-travel recipients and visited IDs; damage/status independently reject
travel. No new selector dash exclusion is added. Their actual paired ID/aim/hit
semantics must be covered on the merged native.

Local stdlib checks: changed Python source parses; no unresolved merge entries;
C1 troop.rs, shared probe/test and approved snapshot comparator are byte-identical
to11ff; AST/mock shared-probe suite PASS. No engine import, native execution or
compiler ran. Staged whitespace initially flagged only the two historical raw
reviews' extra EOF blank lines (REVIEW-candidate-r1.md and
REVIEW-preparation-r3.md). Preserve these identical original bytes; normal checks
exclude only those two paths, each separately checked with blank-at-eof disabled.
All code/other whitespace checks and staged secret scan remain required.

## Execution conditions

Before any host execution, independent Sol-high review must bind the exact
postmerge source, probe, diagnostic procedure and all new/altered host scripts.
Fresh build uses only its frozen source; no copied old native, moving worktree
imports, runtime tree paths, active pin, competing full sweep or full C56.
Liveness/receipt/CPU checks and unique fresh job output precede launch. CPU<=4,
nice15, thread limits, Cargo-j<=4, only04/08; no heavy05 or hosts09–18.

The run must retain build/probe errors, all32 results and partial roots, exact
module/native/data/tool/source identities and before/after inventories. Any
actual external-vector parity failure remains a failure, not a field exemption.
Original C1 focused Ronin/boulder/axe and B2 selector carryovers require meaningful
continuation and negative controls. Full eventual coverage/ordered C56 remains
separate and unaccepted. Fix reproduced routine defects with fresh independent
review; do not infer a32-case PASS from proposal approval.

Explicit CWD is used for every command. Available worktree-handoff tool creates
a new worktree and cannot select this already prepared existing branch; no
replacement worktree or duplicated thread/job was created. Original cards/c1
retains11ff and its approvals. Rollback only new isolated integration commits,
keeping the base ref and every failed receipt/artifact intact. No deployed state
changed. Sam strict silence/direct-owner coordination/one final diagnostic
delivery and no tiny-step delegates remain in force.
