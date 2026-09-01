# Hog 2.6 terminal action reranker: untouched-holdout rejection

Date: 2026-08-31

## Decision

Reject the frozen terminal action reranker and close the retained-policy repair
family.  Do not integrate it into inference, change its threshold, retrain a
different seed on this holdout, or finish the remaining expensive terminal
probes.

The development candidate was frozen before this holdout:

- rank 8;
- epoch 1;
- seed 1236001;
- override probability margin 0.10;
- checkpoint SHA-256
  `a28c41547467d65607ac0befdc0954a381b207fe5076614c97c6615c9c707a4e`;
- retained parent SHA-256
  `28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`.

Six newly generated roots were exact-policy-input-disjoint from the 24 training
and 21 development roots.  Every recorded candidate branch reached a natural
terminal result.  Collection stopped as soon as the zero-regression gate became
impossible to satisfy.

## Untouched result

At the frozen margin, the reranker made three overrides across six roots:

- balanced phase 97: parent placement and selected wait both lost; selected
  dense return was slightly worse;
- slow-push phase 97: selected wait converted a parent loss into a win;
- split-lane phase 97: selected wait converted a parent win into a loss.

Aggregate terminal result:

- outcome improvements: 1;
- outcome regressions: 1;
- equal outcomes: 4;
- correctable roots captured: 1/1;
- best-outcome accuracy: 5/6;
- root-fingerprint overlap across train/development/holdout: 0.

The exact regressed root was
`005_w097_split-lane_1239006`: parent action 1944 won with dense return
0.146899; action 2304 (wait) was selected at predicted probability margin
0.160226 and lost with dense return -0.416499.  This is not a threshold-edge
failure: the bad override cleared the frozen 0.10 margin by a material amount.

Authoritative machine-readable report:
`reports/hog26_terminal_reranker_final_holdout_seed1239001.json`.

## Architecture consequence

The retained parent repeatedly needs opposite timing decisions in superficially
similar states: waiting fixes slow-push but destroys split-lane.  Scalar gates,
localized policy-head repair, factorized play/card/tile repair, and now a small
frozen-feature terminal reranker have all transferred one correction by moving
the error elsewhere.

The next experiment must be a fresh policy/value architecture trained jointly
on diverse trajectories, with action-value structure and outcome-aware targets
built in from the start.  It must not be another adapter, threshold, seed, or
head attached to the retained checkpoint.
