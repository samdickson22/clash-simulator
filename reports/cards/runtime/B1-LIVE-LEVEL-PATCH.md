# LIVE-owned scaled public-root consumer dependency

Read-only consumer inventory found THREE production template-to-root builders:
plain Resources, ExactLevelRoot (both repaired in approvede0e9f634e), and LIVE
`bot/live/levels.py:LevelRoot.payload`. Nontrivial LIVE levels and level pilotB0
use the latter, which independently copied the old root and retains stale GG
mounts. Its trivial root delegates to Resources; the scaled path needs the same
shared public-only graph repair. No LIVE source was edited by this worker.

Proposed owner patch:
`patches/B1-live-level-public-graph.patch`, SHA
`ba392e466fb7a73585f57669b234364d0b37ed492e3a199b02c2d4fb276da37f`.
Input `bot/live/levels.py` SHA
`822cee2a73d9de27a069e99cc6dd21eb04686aecc552c7a5cd59f826796e00e5`
matches both the B1 base and read-only LIVE owner's current file. Proposed output
SHA `a3289daf71ef7f1e4270e2b4f56542a31f07c00a86b645ab94c7fbadd3d032bf`.

The four-line addition calls `R.repair_public_graph(entities)` at the same point
as the owned consumers, guarded by hasattr for older frozen Resources lacking
the helper. Old runtime behavior stays explicit and is NOT newly accepted as
GG-correct. No stat scaling, payload format, model, vocabulary, default/active
pin or runtime root changes. Integration and actual scaled LIVE/native tests
belong to the LIVE owner; no runtime deployment is implied by this source patch.

Read-only checks: `git apply --check` PASS (patch not applied), AST parse PASS.
`python3 -B reports/cards/runtime/tools/check_b1_live_level_patch.py` executes
the actual source-extracted payload method with the patch IN MEMORY using
stdlib fixtures: legacy and new Resources C56 empty-board payload bytes match;
old stale GG links reproduced as negative control, proposed path supplies valid
new parent IDs/distinct ranks; protected source SHA unchanged. This is source
evidence only, not native or deployed consumer acceptance. All underlying graph
geometry cases remain in the approved helper suite and B1 admitted scoped16.

Independent Sol-high patch correctness/fair-information review pending before
essential owner handoff. Original r3 evidence/roots and B1's sole reviewed
validation sequence remain unchanged. Rollback is omitting/reverting this one
source patch; retain every runtime/old root and active selection unchanged.
