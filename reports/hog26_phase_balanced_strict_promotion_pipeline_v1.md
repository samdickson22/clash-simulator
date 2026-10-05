# Hog 2.6 phase-balanced strict promotion pipeline

`scripts/supervise_hog26_phase_balanced_strict_promotion.sh` is the resumable
orchestration authority for the current ranker experiment. It does not alter the
frozen corpus, fitter, evaluator, or gameplay contracts. It makes their order and
terminal rejection states explicit:

1. Wait for the fully verified phase-balanced corpus.
2. Require weighted-archetype and supervision audits for exact production game
   IDs 0–99, 0–199, 0–399, and the final 0–499 corpus, plus an exact 0–149
   held-out validation distribution audit.
3. Verify every sampled train/validation deck against its own pool and reject
   cross-split leakage. Pin the free-running screen/quarantine draws and require
   all four wholly held-out archetypes with seat balance and no deck overlap.
4. Fit three CPU seeds and require the aggregate game-clustered holdout gate.
5. Require the selected seed's phase- and Hog-specific holdout gate.
6. Run the paired 48-game screen and 96-game quarantine.
7. Require Hog usage and override-placement diversity.

Any failed stage writes `STRICT_PROMOTION_REJECTED` with its stage. Only all seven
passing stages write `STRICT_PROMOTION_GATES_COMPLETE`. Even that marker does not
claim mid-ladder human ability or authorize broad multi-deck deployment; visual
gameplay review and later human/held-out deck evidence remain required.
