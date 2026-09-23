# Rejected lazy strategy spatial fits

Date: 2026-08-11

## Candidate

After direct canonical action geometry, every strategy score still computed
both defense and enemy-cluster Gaussian fits before selecting its strategy/card
branch. The candidate evaluated only fits consumed by that branch. It was
card-general and exact for every legal action across all six strategies and
both player perspectives.

## Bounded evidence

All runs used seed 2301, alternating matched order, single-process CPU, and
`nice -n 15` while one RoadForge CPU process shared the host.

Direct balanced-strategy scoring improved 1,160.477 to 1,273.002 selections/s
(+9.70% median rate, +9.21% paired median, 11/11 positive). Both variants
produced action digest
`5356c3fc1ff9b65b14a546c11873ca10a7c7d7f305dce605fbd2274110bbc88e`.

The gain did not survive production-shaped rollouts materially:

| workload | eager decisions/s | lazy decisions/s | median-rate change | paired median | positive pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| 8 envs x 16 decisions | 197.362 | 198.646 | +0.65% | +0.53% | 11/11 |
| 1 env x 64 decisions | 141.196 | 142.031 | +0.59% | +0.50% | 9/11 |

One host-contention pair widened each raw confidence interval through zero.
Both 8-env variants matched digest
`d87bdd871c9bb012c55aff818085f7da385061d83e445c632a601bdb23737590`;
both 1-env variants matched
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

Because the production gain was sub-1% and noisy, the candidate was rejected.
Its source, tests, and benchmark-mode additions were removed, leaving the
separately proven direct action-geometry optimization intact.
