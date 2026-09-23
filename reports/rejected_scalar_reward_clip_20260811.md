# Rejected scalar reward clipping

Date: 2026-08-11

The candidate replaced scalar `numpy.clip` calls in the general reward model
with ordered Python comparisons. Boundary, NaN, infinity, and signed-zero
outputs matched bit-for-bit, and all fixed rollout and exact planner digests
matched. It was rejected because exact oracle throughput did not improve.

All commands ran at `nice -n 10` while one RoadForge CPU reconstruction and a
Clasher MPS imitation fit were active. Rollouts used seed 2301, 8 environments,
32 decisions, 8 warmup decisions, 7 alternating pairs, and 2 Torch threads.
The oracle used battle seed 2301, planner seed 901, 3 states, depth 6, 32
simulations, 64 action samples, and 5 alternating pairs.

| workload | NumPy median seconds | scalar median seconds | paired gain median | paired gain stdev |
| --- | ---: | ---: | ---: | ---: |
| stationary random | 1.455250 | 1.436759 | +1.10% | 3.38 points |
| balanced strategy | 1.541913 | 1.523321 | +1.17% | 2.95 points |
| exact stable-root oracle, 3 labels | 1.204685 | 1.197998 | **-0.21%** | 0.76 points |

Four of five oracle pairs regressed; the scalar oracle mean was also slower
(1.201542 versus 1.196542 seconds). The apparent unpaired oracle median-rate
gain of 0.56% was therefore host-order noise and is not accepted.

Both rollout variants retained digests
`8bcf61259509b1f2f80750fa29ccaf695ba9f11e46b46e2967069d2d90fce432`
(random) and
`67faf6c5e975db614868686ead0c2515840dfd02729342a228127e837f22844d`
(strategy). Every oracle row retained complete action/state/planner-RNG digest
`72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`.

All candidate source, test, and benchmark hunks were removed. This uncommitted
report is retained only to prevent repeating the rejected experiment.
