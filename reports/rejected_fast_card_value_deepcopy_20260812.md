# Rejected: specialized JSON-shaped card value deepcopy

Date: 2026-08-12. Current verified stack: `16a1125`.

The oracle profile attributed 99 ms of 387 ms total clone time to active
`CardStatsCompat` wrapper copies. A candidate recursively copied exact dict/list
JSON-shaped payloads through the existing deepcopy memo while falling back to
generic deepcopy for every other value. It preserved aliases and cycles, kept
the immutable-definition sharing contract, and isolated every mutable wrapper.

The candidate passed 43 card-wrapper, battle clone, NumPy cache, target cache,
Crown membership, and dense-bucket clone-isolation tests. In a matched
single-process screen of 101 alternating pairs, 50 battle clones per variant
per pair (5,050 clones each), the reference median was 0.0120705 seconds and
the candidate median was 0.0120605 seconds: only +0.083%. The graph is dominated
by entity/battle reconstruction rather than JSON container dispatch, so the
candidate was rejected before planner timing. All source and test hunks were
removed; no commit was made.
