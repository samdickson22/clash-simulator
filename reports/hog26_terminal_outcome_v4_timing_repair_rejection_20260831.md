# Hog 2.6 terminal-outcome v4 timing repair rejection

Decision: reject the monolithic hazard-head timing repair and close the current
policy-head repair family. Retain the original Hog parent.

## Contract

- train: 18 conclusive timing roots, 3 corrective;
- held-out: 18 conclusive timing roots, 2 corrective;
- only four `play_hazard_head` tensors trainable;
- card, tile, encoder, structured memory, and all other heads frozen;
- selection required at least +0.25 corrective accuracy, no more than 0.01
  safety regression, and at least 99% non-root exact action retention.

The timing corpora have SHA-256 values
`e8c10218b48455ee0ea7b9ac5c72816ef9b19ff8dbcc5c519f48622bd38b3b5c`
and
`228e59bedb0260a33925ba3a5795e3236274aca8f9d61f065c5d1a3ac7504745`.

## Rejection

Every nonzero epoch produced the same held-out behavior:

- corrective wait accuracy: 100%;
- safety play accuracy: 0%;
- predicted play rate on timing roots: 0%;
- non-root exact action retention: 94.01%.

No epoch was eligible and no checkpoint was published.

## Interpretation and next architecture

The scalar hazard accumulator cannot absorb sparse state-specific wait labels
without moving its global event rate across many unrelated states. This agrees
with earlier scalar tuning, localized adapter, and direct play-gate failures.
The complete-action head repair failed for the complementary reason: moving the
shared card/tile heads enough to fit corrections regressed safety and unrelated
actions.

Do not add another hazard coefficient, threshold, adapter, or mode gate to this
lineage. The next bounded architecture is a frozen-policy terminal action-value
reranker. It scores complete candidate actions by win/draw/loss first and dense
terminal return second, and may override the parent only at a held-out-
calibrated value margin. The base policy remains unchanged everywhere else.
If a disjoint reranker cannot generalize, restart the policy architecture and
training lineage rather than repairing this checkpoint again.
