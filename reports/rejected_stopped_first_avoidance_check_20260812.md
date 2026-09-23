# Rejected: stopped-first avoidance check

Date: 2026-08-12

The candidate evaluated the pure stopped-state predicate before normalizing
the retained facing vector. Exact semantics and all hashes matched, but the
oracle gain did not survive production-shaped rollout attribution.

Oracle: seed 9133, planner 2133, two states, depth 6, 32 simulations, 64
action samples, 8-tick steps, 11 alternating pairs, one process/thread,
`nice -n 10`.

- facing-first: 0.678175 seconds, 2.94909 labels/s
- stopped-first: 0.671386 seconds, 2.97891 labels/s
- ratio gain +1.011%; paired median +1.058%; 9/11 positive
- paired mean 95% CI +0.524% to +1.480%
- digest `5e782cf2c72589179728108994154e1bb4d59e8294806106ddcb0e0ca124b527`

Stationary screens used four environments x 24 decisions, four warmup
decisions, 15 alternating pairs, defense-v2, optimized/on, one Torch thread.

| workload | facing-first decisions/s | stopped-first decisions/s | ratio gain | paired median | positive | paired mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| random | 180.4768 | 180.9807 | +0.279% | +0.029% | 8/15 | -0.218% to +0.749% | `6b88d2e45e31829b96a8a45f68bb2ec7d020aabf3449c18bf645bde6c59a7b6f` |
| balanced strategy | 170.9027 | 171.3896 | +0.285% | +0.193% | 11/15 | -0.430% to +1.045% | `1afa9f6d71f3158057e932a2355b6a3927e541745290047eceb71d41d482bc1f` |

Both rollout confidence intervals crossed zero, so all source and driver
hunks were removed and no commit was created.
