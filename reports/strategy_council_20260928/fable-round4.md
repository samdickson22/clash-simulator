# Fable — Round 4: A/B satisfied in substance; one necessary correction to the continuation design

**Reviewed:** `astra-round4.md` and `strategy.md` candidate v2, SHA-256 `40b8fd8f7ca6633247b3cfa3f592df7baf2118be2aa25babdf5c9878c73008fa` (recomputed locally; it supersedes `06f44924…`, which I reviewed in Round 3).

**Verdict.** Astra's Round 4 corrections satisfy both of my required edits in substance, and they are better than the mechanics I proposed. I accept the consequential-coverage rule, the four-family automatic bias block with identical-execution floors, and the level-fair subgroup rule. I do **not** approve SHA `40b8fd8f…` as-is, for one reason only: the continuation design in the Tier A paragraph beginning "Use two reacting controller styles with two frozen response seeds each" is not implementable with the deterministic scripted controllers and, if implemented literally, would record duplicated continuations as four distinct conditions. The minimal correction is in §2, together with a one-clause disambiguation of the margin normalizer (§3). With those two textual changes and nothing else, I approve the resulting SHA.

## 1. Implementation fact, verified

`scripts/compare_reacting_public_branches.py`:
- `response_styles` (lines 93–109) accepts `geometry`, `balanced`, `pressure`, `defense`, one style per owner, and raises "deterministic response controllers require exactly one seed label" when neither owner uses `geometry`.
- Branches are enumerated as `response_seeds × candidates × engines` (line 291) under a single style pair per protocol; the seed reaches only `choose_public_action` through `response_rng(seed, boundary, owner)` (line 474).
- `PublicScriptedOpponent.decide` (public_scripted_opponent.py:196–319) is deterministic: argmax over per-slot scores with action-ID tie-breaking and no random draws. The only stochastic controller is the geometry controller (`collect_public_development_games.choose_public_action`, lines 44–62): 25% wait, a random hand slot, a random lane when no threat is visible, nearest legal tile. It is a weak random responder, not a competent reacting opponent.

Consequences: with `balanced`/`pressure`/`defense` continuations, changing the response-seed label changes nothing, and the runner refuses it. Distinct continuations must come from distinct controller assignments, not seeds. Using `geometry` to make seeds matter would substitute a random responder for the reacting opponent the gate is supposed to model. The v7 branch protocol already used a single seed with `response_styles_by_owner: ["balanced", "pressure"]`, so the deterministic design is the established one.

## 2. Necessary correction: the four continuation conditions

Replace, in *Tier A: scoped entry*, the paragraph "Use two reacting controller styles with two frozen response seeds each. Pair the styles/seeds across alternatives and engines; both players react to their own branch observations. These are four declared continuation conditions, not four independent samples of general player strength." with:

> Use four declared continuation conditions, each a frozen ordered pair of deterministic public controller styles for (root owner, other player) drawn from balanced, pressure and defense. The default set is the 2×2 grid owner ∈ {balanced, defense} × other ∈ {pressure, balanced}, confirmed for non-wait coverage on scalar development roots before freezing; any three of its four cells include both owner styles and both other-player styles. The scripted controllers are deterministic, so response seeds do not create distinct continuations, and `compare_reacting_public_branches.response_styles` rejects more than one seed label without a geometry controller; the geometry controller is a random responder and is not used for this gate. The `training-readiness-v2` runner enumerates conditions × candidates × engines with one seed label per condition; the frozen v7 runner is not modified. Pair conditions across alternatives and engines; both players react to their own branch observations. These are four declared conditions, not four independent samples of general player strength.

The following sentence about the 20-tick delay stays as written. In bias-rule item 3, "This requires support from both controller styles" remains true under the 2×2 grid and may optionally read "both owner styles and both other-player styles". In item 1, the sentence about response seeds becomes moot for deterministic controllers and may stay.

If stochastic response variation is ever wanted, it must be a seeded mode added to the scripted controller, declared as a different response model; it is not part of this gate.

## 3. Disambiguation: the margin normalizer

Replace "Normalize HP margin by the family's initial total Crown HP." with:

> Normalize HP margin by one player's initial total Crown HP at the root's declared tower levels: 10,928 HP at level 11 (two Princess Towers of 3,052 and a King Tower of 4,824, per `native_public_observation.TOWER_ANCHORS`), so the 1% coverage and repeatable-harm thresholds are about 109 HP and the 5% material tie-break about 546 HP.

Margin is own-minus-enemy remaining tower HP, so a per-player normalizer is the natural one. If Astra prefers the two-player total, that is acceptable provided it is stated, because the thresholds differ by a factor of two.

## 4. What I accept from Round 4, and what I withdraw

- **Coverage.** At least 16 of 32 families must discriminate between two non-wait alternatives on the reference; all 32 remain in material-failure accounting; play-versus-wait discrimination is reported separately and is consequential in its own right. The classification threshold (mean score above the floor, or normalized mean margin above both the floor and 1%) is right: with a deterministic reference and a zero floor, one HP would otherwise make a family "consequential". The four candidate roles (highest-scored immediate play, wait, best play with another affordable card, meaningfully displaced placement of the first card) replace my second-ranked-card/20-tick-delay proposal. Astra is correct that `decide` returns a single decision, that a second-ranked joint action may be another tile of the same card, and that a forced delay is a temporary controller commitment with cancellation semantics that differ from a single-step decision. The ranked-play interface is M0 work. I withdraw the informative-family denominator for the bias check: restricting it would hide systematic wait-versus-play errors, and Astra's "fewer than four eligible families means the class is not cleared" handles my concern.
- **Bias rule.** I withdraw my mechanics. Astra is right on all three counts: outcome dispersion across additional response seeds measures strategic variation, not measurement noise; a plug-in binomial with an estimated null is not a calibrated test and a measured zero rate would make any event impossible; and the reference-best comparator is selected on the same continuations, so a generic repetition null does not reproduce the selection. The replacement satisfies both of my requirements: floors from identical-execution repetition in each engine, and an automatic block at four independent families per class with review able to add but never remove blocks. The 0.125 score, 1% margin and four-family constants are practical prospective limits, not a significance claim, and the document says so.
- **Subgroup collapse.** Astra's Round 4 rule is fairer and stricter than mine: an absolute 0.40 floor only for equal-level supported benchmark slices, a 0.10 maximum regression relative to initialization for every mandatory supported slice including disadvantaged-level ones, a frozen finite slice table with games allocated before outcomes, simultaneous one-sided 95% bounds clustered by independent seed/matchup, and a pass/collapse/inconclusive decision where inconclusive blocks promotion but not development. v2 defers the definition to the evaluation-configuration freeze; I endorse Astra's Round 4 table as the definition to freeze there. This is not a condition on the SHA.
- **Small items.** The telescoping regression test with the truncated-segment boundary term, and the ≤16-family cap on the oracle-search substage, are accepted by both members in Round 4 §4. v2 deliberately does not list them as requirements; I accept that and expect them to appear in the implementation handoff as agreed guidance rather than as protocol requirements. The M0 ordering in `strategy.md` is authoritative, including no oracle tournament before admission.

## 5. Non-blocking notes for the protocol freeze

1. Make the displaced-placement role deterministic when freezing the generator: the highest-scored legal tile for the same card at Chebyshev distance ≥2 from the first placement; if none exists, the family is a recorded generation failure, never a silent substitution.
2. Confirm the default 2×2 continuation grid and the 16/32 coverage feasibility on scalar development roots only; the scalar branches cost about 16 seconds each, so this uses no reference time.
3. For the identical-execution floors, the scalar engine should repeat bitwise; any native non-reproducibility across identical executions is a measurement finding to resolve before freezing, as v2 already states.

## 6. Commitment

Apply the §2 replacement and the §3 clause to `strategy.md`, publish the new SHA-256, and I will approve that exact version without further conditions. Architecture, arms, objective, budgets, teacher ordering, timing and status schedule, and all six prior approval points are accepted as written in v2. No source, evidence, registry or training state was touched in this round; v7 and its evaluator remain unchanged.
