# Scorer correction — 2026-10-08 20:29 UTC

Before any selection or heldout opening, the first authenticated real validation
score exposed an incomplete card-kind adapter. CardDataLoader reports champion
card deployments as `champion`; the scorer accepts troop, building, spell and
separate champion-ability strata. The old adapter rejected a champion deployment
with `Unknown canonical event kind` before producing metrics.

`validation_score_v4.card_kinds` now maps champion card deployments to `troop`.
An event whose producer kind is `champion ability` remains `champion_ability`,
reported separately and excluded from ordinary card-play totals as registered.
This implements the existing troop/building placement endpoint; it changes no
training labels, model, checkpoint, frozen split, collector or gate thresholds.
The same adapter must apply to eventual heldout scoring. No heldout payload was
opened to identify or correct this bug.

Evidence: t7-shared-equality-20261008-09r2 exited1 before creating any experiment
output. Its failed receipt and prior scorer source are preserved under
l1/receipts/inference-sharing-20261008/. A real-data-definition test checks
ArcherQueen/Knight/Fireball/Cannon kind mapping and synthetic deployment versus
ability separation (PASS). The existing file-backed scorer regression passes
22 checks. Both ran under home01 fleet wrappers. The corrected scorer is used
for both original reference cells and new candidate cells; no prior successful
formal score or selection has been replaced.

The preceding09r1 failure was a source-staging omission (three scoring modules
absent on09), also retained. Neither failure is an equality result. Identical
checkpoint/input inference comparison is retried as09r4 with the same three-cell
plan after both prior jobs and their owned services were verified exited.

Full64-match reference preflight exited0 at20:29:31; 09r3 was refused by the
lease lock while preflight ran. No child or output was created.09r4 starts only
after verified preflight exit, using the still-active fresh cache services.
