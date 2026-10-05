# Fresh full-weight hazard mixed league — seed 1068701

Update 20 is the first current-client lineage to pass both gameplay and human
timing evidence: 13-11 versus random, 5-31 across six strategies, 24-0 direct
versus update 10, replay AP 0.0246 -> 0.0406, ROC-AUC 0.672 -> 0.748, and exact
slot symmetry. An exhaustive disjoint 299-segment complement resolved the only
initial blocker: combined card accuracy improves 38.13% -> 41.32% over all
1,411 plays.

This stage is a bounded development league, not held-out promotion. Twelve
stationary actor workers are allocated as:

- three random opponents;
- six PFSP-weighted public strategy bots from update 20's fixed strategy report;
- one frozen update-10 opponent;
- two frozen update-20 opponents.

The learner resumes update 20 and its optimizer for ten updates / 40,960
transitions at learning rate 5e-5. Full inverse-frequency causal hazard
supervision remains unchanged. Update 20 is the immutable rollback. Advancement
requires broad strategy and direct gains without random, replay AP/card,
activity, calibration, or hand-equivariance regression. Held-out archetype and
promotion evaluation remain forbidden until that gate passes.
