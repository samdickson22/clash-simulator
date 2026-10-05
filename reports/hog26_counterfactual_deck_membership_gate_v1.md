# Hog 2.6 counterfactual deck-membership gate

Source-pool hashes do not by themselves prove that sampled game decks came from
the intended authority. `scripts/audit_counterfactual_deck_membership.py`
checks every recorded game after combination. It resolves the learner deck by
controlled seat, requires both learner and opponent card-set signatures to exist
in their frozen pools, and rejects any opponent signature in the other split.

The strict promotion supervisor runs this for all 500 training games and all 150
validation games before fitting. The report records exact input hashes, sampled
deck diversity, archetype counts, seat counts, and maximum repeats. Passing does
not replace the later archetype-held-out gameplay gates.
