# Tier A re-score with current main (diagnostic only)

**Development estimate only: no ledger writes, no admission.** The ledger was opened read-only (`mode=ro`, `query_only`) to read each attempt's frozen protocol and recorded branches. Each recorded scalar branch's score and HP were replaced by its current-main replay: ep24 fix, King lock and nav-id fixes, plus the four sweep fixes. Recorded native branches were kept unchanged. Scoring used `training_readiness_v2.evaluate`. Unchanged inputs reproduce each attempt's frozen verdict. See `artifacts/rescore.py`.

| attempt | recorded | re-scored | scalar branches changed |
|---|---|---|---|
| v4 | blocked (1 material failure: ep03) | **inconclusive**: 0 material failures, 2 above-floor events need review | 13 |
| v5 | inconclusive (2 native branches missing) | **inconclusive**: same missing branches; the other 30 families show no material failure and no above-floor event | 4 |
| v6 | blocked (1 material failure: ep24) | **passed**: 0 failures, 0 events, 32 informative families | 6 |

## Remaining v4 above-floor events

- **ep04, wait (comparator displaced_placement), margin regret 0.041.**
  - The wait balanced/balanced branch diverges 885 ticks after the root, at a sub-tile Goblin drift on retarget.
  - The earlier review classed this as chaotic amplification. It is not one of the five "found but not landed" cases.
- **ep14, displaced_placement (comparator alternate_card), margin regret 0.008.**
  - The alternate_card balanced/balanced and defense/balanced branches diverge 200 ticks after the root.
  - This is the **same-goal-cell retarget rebuild** case: a found-but-not-landed item.
