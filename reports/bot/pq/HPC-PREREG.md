# HPC1: the HP1 v2 human policy inside the live search. Pre-registration (play-quality owner, exploration)

Registered before any HPC1 game. Bank drawn on 127x04 at 2026-10-18T03:12:07Z with
`int.from_bytes(os.urandom(6),'big')<<4`: **BASE 3429463361635728** (check_bank: disjoint).

## Change under test

Coordinator 2026-10-18: HP1 S0 found v2 (`best-dev-step-00046459.pt`, sha256 87794378…) @ τ* 0.019753086419753086 the
best standalone policy at L16 (vs R3a .77 vs f1a2 .63; vs K4C-r16 .51 vs .45). Where the live K4L search uses a policy:
- candidate proposals: R3a top-16 (CandidateSearchPlayer). Token `hk16` appends v2's top-16 legal plays
  (bot/search/candidates.py second proposer). Every candidate is still scored by the unchanged rollouts.
- fast tier / cutoff default (f1a2 in this driver): token `fv2` swaps it for v2 @ τ*. With no deadline (serial twin)
  this changes no decision; live it is the default when the 200 ms search is cut off.
- rollout opponent (learned lopp model mk1a1, trained on v1/R3a decisions) and the coarse-scan hint (R3a): unchanged
  in this A/B. A v2-trained rollout model is a separate later arm.

## Design

As RF1 (reports/bot/pq/RF-PREREG.md): driver l16_cadence `--own-deck` live Hog deck, pool v3.2 53 King-9 rows, vocab-full,
opponents LIVE-K4CW-r16-fp (primary) and R3a, 200 paired cases each, rows L16 and account (same account levels).
Arms: `res-lb-wintp` and `res-lb-hk16-fv2-wintp`. 1600 games, hosts 04/08.

## Prediction and ship rule

Prediction: hk16-fv2 − plain > 0 vs LIVE-K4CW-r16-fp. Ship rule, readout and metrics: exactly RF1's, plus CPU-ms per
decision (v2 forward per search decision) and the share of chosen plays that came only from v2 (`from_second`).
