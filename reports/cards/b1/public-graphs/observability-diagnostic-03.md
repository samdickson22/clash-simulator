**The current hook envelope is insufficient for “normal GG with both riders always reconstructs.” Recommend a structural fallback for complete two-rider populations, with geometry used to choose the approximation.**

The failure itself is confirmed: rider13’s distance ≈0.149 violates the old interior lower bound of0.65, despite an observed same-owner GG with two available slots. [Captured board](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/reports/cards/b1/public-graphs/failing-public-board.json).

Source confirms the mechanism that invalidates the annulus: riders are positioned before movement, Clone slides and object work; Fisherman drag then moves the parent without carrying its riders again. However, the public capture does **not** establish that this particular Fisherman was dragging this particular GG. Describe Fisherman as a source-supported explanation, not a recovered hook event. [Phase ordering](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/engine-cards/py/src/clasher/battle.py:856).

The candidate’s range gate is not a valid completeness bound. Acquisition/windup checks range; flight and drag do not repeat that check. Multiple hooks can also change the final separation from an earlier source. Summing only sources passing a final-position range test can therefore omit relevant displacement. The proposed source-death scenario would likewise invalidate visible-source necessity **if reachable**, but this inspection did not establish that exact death-after-drag sequence. It should not be asserted as an observed counterexample. [Hook implementation](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/engine-cards/src/hook.rs:101).

A genuinely sound displacement bound would need all applicable post-carry movement, source-presence and multiplicity bounds—not just850units from nearby visible hooks. No useful universal bound was established here.

**Concrete narrow policy:**

1. Preserve the existing ordinary geometric matching first.
2. If it cannot match every observed rider, consider each owner independently. Where `parents > 0` and `riders == 2 × parents`, recompute that owner’s assignment using **all observed compatible GG slots**, capacity two per parent and one per rank. Use geometry and deterministic public tie-breaking as preferences, without a hard parent-distance gate.
3. For incomplete populations, retain the existing geometric admission policy. Missing riders remain missing; no fabricated rows.
4. Retain hard guards for wrong owner/type, absent compatible parents, per-owner overcapacity, duplicate reconstructed IDs and invalid static capabilities. Continue excluding ordinary released SpearGoblins and projectiles.
5. Report when structural fallback was used. Call its parent/rank choices public-model defaults, never recovered identities or live ranks. Apply the same helper to both consumers.

This preserves the existing **remote-single-rider and compressed-single-rider negative controls**, while guaranteeing structural reconstruction for complete normal populations, including multiple GGs, independent of hook visibility or distance. Recompute the entire affected owner’s matching; do not greedily attach only the failed row around previously occupied slots. The existing augmenting matcher guarantees cardinality, but preference ordering alone does not prove globally minimum geometric error.

The tradeoff must be explicit: a remote but count-balanced pair will now be accepted. Truncation that happens to leave balanced counts can conceal a missing true parent. Public rows cannot certify the original pairing in those cases. Conversely, retaining strict admission for incomplete populations means **valid transported single-rider observations can still be rejected**. If “always” is intended to include those incomplete observations too, use structural admission for every capacity-feasible population and retire the remote/compressed singleton negatives. Both guarantees cannot honestly coexist without an additional proven invariant.

This is a small reversible change to [the shared routine](/mpac/sdicks02/repos/clasher-cards-public-graphs-20261016/engine-cards/public_root.py:140), rather than a claim that `_post_carry_transport` reconstructs missing history. Update the documented contract accordingly.

Meaningful acceptance coverage should include:

- The exact captured failure, through both consumers. The saved diagnostic rows omit `stats.hook`; any static rehydration must come from the bound public templates.
- Real evolved GG states across carry/drag frames, both seats, multiple/Clone GGs, boundaries, parent death and released children. Include ongoing/out-of-acquisition-range and multiple-hook witnesses where actually reached; record unreached cases honestly.
- Explicit structural, capacity and incomplete-population controls, row reorder, and stale template-link invariance. Artificially removing a Fisherman tests source independence; it does not prove an actual death sequence.
- Actual emitted GG, Ram/RamRider, all three3M members and their projectiles, and SkeletonBalloon/death carriers through frozen sensor → template → both roots → native continuation. Do not generalize GG attachment semantics to RamRider merely because of its name. Assert mechanics and relationships, not just absence of exceptions.
- Fresh required **Python-only K4L HEADLINE12/12** evidence for the final source, separately from new-card lifecycle coverage. The baseline’s66 successful roots and one fallback are reproduction evidence, not acceptance.

Read-only diagnosis at base`a156cf5`; no edits, imports, tests, jobs, SSH or descendants.
