# Identical repeated body snapshots: scorer input normalization

Recorded 2026-10-08 21:17 UTC, before validation body selection or heldout access.

The first independent persisted-record verifier stopped before scoring its first
match: BodyTruth required strictly increasing native ticks. The collector can
observe the same tick repeatedly. The validation-only audit found 65,257 rows,
63,363 unique ticks, 1,893 repeated-tick groups and zero decreasing ticks. Receipt
observation/fence metadata differs across repeats. Eight groups also differ in
the ordinary payload's visibility/deployment hints; the existing amendment03
cleaner replaces those hints from coherent same-tick rich metadata.

BodyTruth now coalesces consecutive equal ticks **only when every cleaned object
value and its order are identical**. Conflicting cleaned object lists still fail
closed; decreasing ticks and duplicate native IDs remain errors. The first row
is retained. Observation/fence metadata is not used by body alignment or scoring.
The latest-past/five-tick alignment, masks, matching and denominators are unchanged.

This fixes a scorer admission bug, not training labels: labels_v4.py, the frozen
registration/split, collector, fitted weights and all inference outputs are
unchanged. Both reference and candidate receive the same scorer normalization;
the independent verifier must still recompute all three complete cells exactly.
The same BodyTruth implementation must be used for eventual heldout scoring.

Failed verifier attempt t7-persisted-equality-20261008-09r1 and its exit1 receipt
are retained. Capture09r4 itself passed all64 matches and three reference cells
for nonclock payloads, persisted decoder payloads, event metrics and bootstrap;
full independent body/event equality remains pending until the recovery succeeds.
