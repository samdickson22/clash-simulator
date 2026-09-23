# Rejected: redundant scalar target-kind check

Date: 2026-08-12

The candidate skipped the scalar selector's second entity-kind 2/3 check after
`_is_valid_target` had already called the only `is_targetable_by`
implementation, which rejects the same kinds. It was exact and card-general,
but did not survive production-shaped rollout attribution.

The oracle screen used seed 9049, planner seed 2049, two states, depth 6, 32
simulations, 64 action samples, 8-tick steps, 11 alternating pairs, one CPU
process/thread, and `nice -n 10`.

- reference: 0.303037 seconds, 6.5999 labels/s
- candidate: 0.301946 seconds, 6.6237 labels/s
- ratio-of-medians: +0.361%
- paired median: +0.336%; 8/11 positive
- bootstrap mean 95% CI: +0.023% to +0.731%
- exact digest: `42a9a724fe3a7a65a2cd59514f4ef9c0663cd95e56f751ec1c8c3e1104dde1b9`

Stationary screens used four environments x 24 decisions, 15 alternating
pairs after four warmup decisions, defense-v2, optimized/on, and one Torch
thread.

| workload | reference decisions/s | candidate decisions/s | ratio gain | paired median | positive | paired mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| random | 206.6806 | 207.2357 | +0.269% | +0.011% | 8/15 | -0.694% to +0.317% | `2443509171f24b295b8816482d60478a95aebf528addb254f7693698df77976d` |
| balanced strategy | 193.6869 | 193.3603 | -0.169% | +0.178% | 9/15 | -1.001% to +0.771% | `9e43d35f6b267ba82b514bcaa9e1a16f006b17b946944d2f48c0499fb0318181` |

Thirty-two focused target/planner tests passed. Because strategy medians
regressed and both rollout confidence intervals crossed zero, all candidate
source and benchmark-driver hunks were removed and no commit was created.
