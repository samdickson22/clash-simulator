# Full inverse-frequency hazard screen — seed 1068401

The square-root-weight hazard arm (9.0) is rejected: 0-12 random, 0-12 direct
parent, 0.40% deterministic replay play rate, ROC-AUC 0.4710, and AP gain only
0.0011. It preserved all 11,040 audited hand permutations, so the failure is
event discrimination rather than slot geometry.

This is the final hazard-family test. The measured public-legal supervised
corpus has 1,411 plays and 114,278 waits, an exact 80.9907866761:1 imbalance.
The dedicated urgency head therefore uses full inverse-frequency positive
weight 80.9907866761 and subtracts `log(weight)` before accumulating hazard.
Its fresh raw bias is zero and its corrected initial probability is exactly
0.0121964923. Eight recurrent chunks per auxiliary batch produce an initial
raw gradient norm of 1.3278; coefficient 0.125 scales it to about 0.166, the
same order as PPO.

Everything else remains fixed: fresh 494-token F3 architecture, random
opponents, 40,960 PPO transitions, objective-v1, exact public mask contract,
and 0.5 cumulative-hazard threshold. Advancement gates remain the same as the
9.0 arm. If held-out urgency AP does not improve by at least 0.002 while random,
balanced, direct-parent, activity, and symmetry gates pass, cumulative hazard
is discarded rather than further reweighted or threshold-tuned.

## Update-10 decision

Update 10 is not authorized for mixed league because its matched random block
remained 1-11, equal to control. It nevertheless passes the discriminating
architecture gates that prior lineages failed: urgency AP 0.0100 -> 0.0241,
ROC-AUC 0.500 -> 0.688, deterministic replay play 2.05%, conditional card
accuracy 30.08% -> 42.97%, direct parent 7-5, and exact card/tile preservation
over 3,336 hand permutations. Therefore it earns only the remaining matched
random-outcome budget through update 20, equal to the prior F3 screen. It does
not earn league, held-out, reward, or threshold tuning. Update 20 must beat
update 10 directly and on matched random/strategy games while retaining the
timing gains; otherwise this hazard lineage is discarded.
