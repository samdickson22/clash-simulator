# Scaled LIVE public graph consumer

Source integration of the four-line patch independently approved in B1 review
r4. `LevelRoot.payload` now calls the Resources graph policy after rebuilding
and scaling all public rows, before the existing champion-link pass. Older
Resources without the method retain their exact existing behavior; that legacy
behavior is not accepted as Goblin Giant graph correctness.

Bindings:

- Original levels.py: `822cee2a73d9de27a069e99cc6dd21eb04686aecc552c7a5cd59f826796e00e5`.
- Integrated levels.py: `a3289daf71ef7f1e4270e2b4f56542a31f07c00a86b645ab94c7fbadd3d032bf`.
- B1 patch: `ba392e466fb7a73585f57669b234364d0b37ed492e3a199b02c2d4fb276da37f`.
- Reviewed B1 source: `f89b8acd5f8b1927fef8f56ad4729269dff4fdc6`.
- B1 helper: `0968768f08e930f9b72c1325c5ef33f542f5a7787d93b44d799a40cea4cae3b5`.
- Review: `reports/cards/runtime/receipts/b1-public-root-review-r4.md`
  on branch `cards/b1-public-root-20261016`.

`check_b1_consumer.py` imports the actual integrated module, real scaling table
and reviewed B1 helper without Resources/native/model construction. Twelve cases
cover both seats, levels9/11/13 and reversed row order. Each checks reconstructed
mount IDs/distinct ranks, scaled HP/damage, preservation of other payload fields,
template immutability, parentless-graph refusal, legacy stale-link negative
control and empty-board legacy/new equivalence. All passed; the source receipt
records the exact command and hashes. These are consumer integration checks,
not B1's complete helper geometry suite or native acceptance.

## Adoption gate still pending

No Resources adoption, native execution, host script, runtime root, model,
vocabulary, active pin, Mac action or deployment is part of this change.
B1 owns its sole combined admitted sequence and all its existing denominators;
this source proof neither repeats nor satisfies that sequence. Existing r3
roots and evidence remain unchanged.

When LIVE adopts the newly accepted B1 Resources, its owner must separately
validate the actual scaled `LevelRoot.root` consumer, with freshly bound source,
Resources/config/native/vocabulary hashes: both seats, nontrivial levels9/13,
reordered/multiple/boundary Goblin Giant graphs, missing-parent refusal, scaled
HP/damage, four-step native continuation versus snapshot reload, and existing
C56 parity. Include the actual rework-projectile positive movement and zero-speed
controls through the scaled LIVE consumer. Use admitted fleet CPU, normal leases
and independent prehost review for any new host script; do not start a second
B1 combined sweep. Native acceptance stays pending until that evidence exists.

Rollback this consumer source change only by reverting its four added lines.
It never changes a runtime selection or grants live-play authority.
