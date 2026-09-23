# Rejected request-local defense reward entity/value reuse

Date: 2026-08-11

This exact candidate collected public combat entities and standing Crown Towers
in one insertion-ordered pass, computed each entity's remaining value once, and
shared those values between defense-v2 board value and tower danger. It added no
card-name, deck, arena, or persistent-cache special case.

Across five fixed seed-2301 oracle snapshots containing 6-12 live entities, the
reference made 24 `_entity_remaining_value` calls and the candidate made 14.
Every `PotentialBreakdown` field was exactly equal. The fixed 32-decision
defense-v2 trace matched reference/candidate and scalar/off, shadow, and
optimized/on at:

`852721d45a01fee27444e613a8c1d7dc1a862d5124747adcb8936dc3dc9e66aa`

Shadow performed one sampled mask comparison per run with zero mismatches. A
focused oracle probe also matched selected actions, root battle state, complete
battle RNG, and complete planner NumPy RNG. Before timing, 20 reward/reuse/oracle
tests and 18 direct-path/scalar-leaf/sampling/batched-tick oracle tests passed;
Ruff, isolated mypy, Python compilation, and `git diff --check` were clean.

## Bounded timing and rejection

All timing ran single-process at `nice -n 15`. One Clasher attention/global MPS
architecture fit and one RoadForge CPU reconstruction were active. The drivers
alternated reference/candidate order and used deterministic 20,000-resample
percentile-bootstrap intervals for the paired mean.

| workload | reference | reused | paired result |
| --- | ---: | ---: | ---: |
| Reward kernel, 5 states x 200 evaluations, 11 pairs | 0.062782 s, 15,928.17 eval/s | 0.046708 s, 21,409.65 eval/s | +33.19% median, +34.01% mean, 95% CI [+31.10%, +37.19%], 11/11 |
| Exact stable-root oracle, 3 labels, depth 6, 32 sims, 7 pairs | 1.282345 s, 2.339 labels/s | 1.280278 s, 2.343 labels/s | +0.27% median, +0.79% mean, 95% CI [+0.006%, +1.78%], 5/7 |
| Stationary random defense-v2 rollout, 8 envs x 32 steps, 7 pairs | 1.438139 s, 178.01 decisions/s | 1.418241 s, 180.51 decisions/s | +0.82% median, +1.79% mean, 95% CI [+0.25%, +4.02%], 5/7 |
| Balanced strategy defense-v2 rollout, 8 envs x 32 steps, 7 pairs | 1.365196 s, 187.52 decisions/s | 1.363458 s, 187.76 decisions/s | **-0.004% median**, +1.22% mean, 95% CI [-1.07%, +4.26%], 3/7 |

The first rollout pair in both screens was a large shared-load outlier. Excluding
it does not rescue the strategy result: its paired median remains negative and
only three of six remaining pairs are positive. The kernel saving therefore did
not translate reliably to the exact oracle and strategy rollout bottlenecks.

Every reference/candidate row matched within its workload:

- reward kernel: `bb220093de6863534b4d35f84264dcc51accdc109c71c9310acdbe3664150e6e`
- oracle action/state/planner RNG: `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`
- stationary random rollout: `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a`
- balanced strategy rollout: `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d`

The candidate source, focused test, and dedicated benchmark drivers were
removed. No optimization commit was created. The stationary rollout driver
retains only its general `--reward-profile` selector so future timing cannot
misattribute an objective-v1 run to defense-v2/v3.
