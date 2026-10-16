# Public attachment graph repair — ready for lead integration

The original mixed LIVE failure is reproduced at tick 350: one Goblin Giant, two observed riders, only one matched, unsupported row 13. The reproduction retained the original game command hash `869f612af10ff0eb195ecd4a00ea647e2212984c1e29deaf7686e660aaf8cd76`. Its full 21-row public board is in [failing-public-board.json](failing-public-board.json). The rejected rider was 0.148718 tiles from its parent; the old radial admission rule required at least 0.650. Carry runs before subsequent parent movement/object drag, so the final board need not satisfy that annulus. These public rows do not identify a private hook target.

`engine-cards/public_root.py:repair_public_graph` preserves ordinary geometric matching. If an owner still has unmatched riders and its observed population contains exactly two riders per Giant, it recomputes that entire owner's assignment over all compatible observed slots. Geometry sets preferences; owner, body type, two-slot capacity and unique rank constrain admission. Every ID is a fresh public-row ID. The helper reads no private mount, rank, target or phase history and creates no entity rows.

A complete count-balanced remote pair receives a documented public-model default. Balanced truncation can conceal the original pairing, so this does not recover private identity. Incomplete populations retain geometric admission and can still reject transported partial observations. Orphan, wrong-owner, over-capacity, duplicate-ID and invalid static-capability controls remain.

## Actual class coverage

Fresh run03 uses full natural `play_match` games, public sensor packets and three consumers: plain Resources, forced ExactLevelRoot at 11, and LIVE LevelRoot at 10. Both seats actually deploy all four scoped cards in each game. There are no synthetic object spawns, forced deaths, HP edits or elixir refills. Opponent belief uses the declared fixture deck prior and accepted public events.

| Body / graph | Result so far |
|---|---|
| Goblin Giant | Exact original board now reconstructs in both orientations and row orders; natural games include complete same-owner multiple-parent graphs in all three consumers. |
| RamRider | Actual primary Ram body has its declared range/charge template and stays unmounted. The separate rider, bola and snare belong to Batch C2 and are explicitly excluded by CARD LEAD. |
| Three Musketeers | Actual three-body formations and emitted shots are observed; the existing public 700ms default remains intact. Engine 700/650/700 mechanics are unchanged. |
| Skeleton Barrel | Actual body, death container and released Skeleton rows reconstruct. Container timer/damage/radius/freeze behavior is checked. Exported child identity resolves through the frozen public token to the selected template, including LIVE10 payload scaling. |

| Fresh run03 coverage | Base stats | live16402c overlay |
|---|---:|---:|
| Completed natural games | 2 | 2 |
| Game ticks | 3478 / 3548 | 3546 / 3459 |
| Whole-board samples per plain / Exact11 / LIVE10 consumer | 356 each | 362 each |
| Additional reversed-row roots | 274 | 274 |
| Attached rider row checks, all consumers including reversed | 3644 | 3512 |
| Complete same-owner multi-Giant observations per main consumer | 144 | 120 |
| Full-state clone/reload four-step continuations | 414 | 414 |
| Maximum simultaneous 3M bodies | 6 | 6 |
| Primary Ram row checks | 568 | 508 |
| Barrel container row checks | 124 | 134 |
| Released child rows per main consumer | 578 | 568 |

The barrel probe initially compared the exported name `Skeleton` with the selected mechanical name `SkeletonArmy`, causing failed02. That failed attempt is preserved without a PASS claim. The corrected probe resolves ordered exported public identities through `(token, kind)`, then checks the selected payload. Actual token296 witnesses show HP/damage81 for plain/Exact11 and73.72265625 for LIVE10, with exported/token name Skeleton and selected name SkeletonArmy. Local stdlib graph7, existing public-root25 and probe identity3 controls pass; negative controls reject wrong token/kind/payload/level.

## C56 check and receipt identities

The mixed LIVE regression passed both seat cases at2401ticks:224 reconstructed roots, zero root errors, fast-tier errors, panics, native failures or search failures. The new deadline-sensitive trajectories did not trigger structural fallback; that path is directly covered by the preserved full failing public board. No new-card mixed command-hash parity is claimed. Fresh K4L HEADLINE completed12 baseline and12 candidate cases against R3a/v1 (indices0–5). All12 command SHA256s match exactly; all24 game rows succeeded. The standalone optimization-safe validator checks complete unique case keys and actual helper/native/model/vocabulary receipts. See [headline-compare.json](run03/headline-compare.json).

| Fresh phase | Completion UTC | Input hashes before / after |
|---|---|---|
| Real games, base | 20:15:37 | 22 / 22 PASS |
| Real games, overlay | 20:21:56 | 22 / 22 PASS |
| Mixed LIVE, both seats | 20:46:44 | 22 / 22 PASS |
| HEADLINE baseline12 | 21:00:51 | 22 / 22 PASS |
| HEADLINE candidate12 | 21:14:50 | 22 / 22 PASS |

All dates are2026-10-16. Final host verification confirms all recorded jobs exited and all22 inputs remain unchanged. [VALIDATION03.json](VALIDATION03.json), [final host receipt](validation03-final-host-receipt.txt) and [receipt hashes](run03/RECEIPTS.sha256) bind the outputs. No copied CPU admission helper was executed: every job used the shared path. An external admission-lock bug briefly blocked the mixed phase; its owner fixed and deployed the shared tools, after which the same queued job continued. No second job or host04 fallback was launched.

Native/physics/data/vocabulary/models/callers are unchanged. This satisfies the user's Python-only K4L12/12 requirement without duplicating a full native C56 gate. Independent Sol-high final round08 **APPROVED** exact evidence/source checkpoint `e20105c4e3631d601ae06a87186216908ac8f531`, independently checking51/51 raw receipt hashes, all507 source comparisons, real-game coverage, mixed cases and fresh12/12 identity. No blocking correctness, fair-information, evidence or readiness findings remain. [Full final verdict](review-final-08.md). `VALIDATION03.json` records the immutable checkpoint before that final review; this verdict completes readiness. Subsequent changes only preserve the verdict and update these reports.

Measured source/harness commit: `6385207d863a518bd713a1a96b5f1c8763ccbf07`, branch `cards/public-graphs-20261016`, fixed requested base `a156cf5b117cdbc0cd5045ed3a5d00cbbbc5d259`. Production helper SHA256 `1cae9504afd3e7297805a50647b8e7818ace50a70f2844c1f80bcf10ff8b7744`. Unchanged accepted native SHA256 `326ce6f93c4db6a7bd15b667960a2d3ed40a0d48eab3badc9ddd181521996732`; all507 accepted engine-source entries match the fixed base, with only this candidate helper differing. [SOURCE-IDENTITY.json](SOURCE-IDENTITY.json) preserves that audit.

Fresh job `/mpac/sdicks02/jobs/clasher/cards/b1/public-graphs-20261016-03` binds22 actual input targets and exact source commit. Real-game outputs/imports/done receipts are preserved in [run03](run03); detailed UTC commands, PIDs, reviews and rollback are in [PROGRESS.md](PROGRESS.md). Original roots, failed02 and prior gating artifacts are immutable. No active runtime, main merge, pin, model or deployment was changed. Rollback rejects or reverts only the new Python helper against the fixed base.
