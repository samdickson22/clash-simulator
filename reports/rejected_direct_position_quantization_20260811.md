# Rejected: direct position quantization

Date: 2026-08-11

The candidate inlined the exact
`logic_units_to_tiles(tiles_to_logic_units(value))` round-trip in
`Entity.quantize_logic_position`, avoiding four Python helper calls per entity
publication. Bitwise edge-value tests, fixed off/shadow/on rollout parity, and
all benchmark hashes matched. It was nevertheless removed because the
production-shaped rollout attribution was too small and inconclusive to
justify duplicating fixed-point arithmetic.

Machine/resource conditions matched the accepted optimizer screens: Apple M4
Pro, Python 3.12.13, single process, one math-library thread, `nice -n 15`,
with RoadForge occupying one CPU core and no exclusive window.

## Oracle, depth 6 / 32 simulations

Three fixed snapshots, seed 2301/planner seed 901, 11 alternating pairs:

- helper median: 1.212737 seconds, 2.4737 decisions/s
- direct median: 1.204254 seconds, 2.4912 decisions/s
- paired gain: +0.569% median, +0.970% mean
- mean 95% bootstrap CI: +0.365% to +1.631%
- positive pairs: 9/11
- exact hash:
  `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`

## Stationary rollouts, 8 environments x 32 steps

Seven alternating pairs, one Torch thread, `defense-v2`:

| workload | helper median | direct median | paired median | positive | hash |
| --- | ---: | ---: | ---: | ---: | --- |
| balanced strategy | 1.551195 s | 1.543530 s | +0.208% | 5/7 | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| random | 1.566721 s | 1.560358 s | +0.096% | 5/7 | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

Both rollout mean confidence intervals crossed zero. The first pair in each
screen was a shared-host positive outlier; conservative paired medians were
therefore used for the rejection decision. No candidate source or tests
remain.
