# Direct target-cache entity-kind access

Date: 2026-08-11

## Change

`Entity.entity_kind` is a required dataclass field normalized by
`Entity.__post_init__`. The fast target-cache membership predicate now reads
that field directly rather than using `getattr(entity, "entity_kind", 4)` on
every cache rebuild. A private benchmark switch retains the exact previous
expression.

This is data-driven and applies uniformly to every entity and deck. It does
not alter the set of accepted kinds: live kinds 0, 1, and 4 remain eligible;
projectile/effect kinds 2 and 3 remain excluded.

## Machine and resource conditions

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 (25F84), Darwin arm64
- Python 3.12.13
- base optimizer commit: `d461ae8673f444fc46e4a4cc0275ef9dc49e28e0`
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- RoadForge occupied one CPU core during the measurements; no Clasher trainer
  was visible. Alternating paired order was used to share the host rather than
  request an exclusive window.

## Fixed oracle attribution

Command (output: `/tmp/target_entity_kind_oracle.json`):

```sh
nice -n 15 env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison target-entity-kind --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

| Variant | Median seconds | Median decisions/s |
| --- | ---: | ---: |
| reference `getattr` | 1.066922 | 2.8118 |
| direct field | 1.064487 | 2.8183 |

- paired gain: **+0.309% median, +0.340% mean**
- mean 95% bootstrap CI: **+0.080% to +0.583%**
- positive pairs: 8/11
- every reference/candidate action-state hash:
  `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`

## Production-shaped stationary rollouts

The strategy confirmation used the same process/thread controls and:

```sh
uv run python scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison target-entity-kind --workload strategy --strategy balanced \
  --seed 2301 --num-envs 8 --rollout-steps 32 --repetitions 7 \
  --warmup-steps 8 --torch-threads 1 --engine-fast-path on \
  --reward-profile defense-v2
```

| Variant | Median seconds | Median decisions/s |
| --- | ---: | ---: |
| reference `getattr` | 1.385909 | 184.7163 |
| direct field | 1.380970 | 185.3770 |

- paired gain: **+0.336% median, +1.498% mean**
- mean 95% bootstrap CI: **+0.257% to +3.398%**
- positive pairs: 7/7
- every hash:
  `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d`

The shorter 8-environment x 16-step screens independently retained positive
paired medians:

- strategy, 11 pairs: +0.246% median, 8/11 positive, exact hash
  `688a582b099968f7bb783780f05055e6d3d5f8d3fb6a87b3df3bedc53c498f17`
- random, 11 pairs: +0.248% median, 9/11 positive, exact hash
  `7b30368c51234d9d77efc7ec49d4469a0216c2dc97b72544326d4f64b64829d4`;
  shared-load outliers made its mean CI inconclusive

The claim is therefore the repeatable approximately 0.25-0.34% median gain,
not the outlier-sensitive means.

## Exact parity and focused gates

Seed 8831, 32 decisions, `defense-v2` produced the same digest with the
reference and direct expressions in scalar/off, shadow, and optimized/on:

`996e2fca4b2d631ed02476e1fde80322cf3009cb19a5aacc3d8378c3173ab0a2`

Shadow recorded one check in each variant and zero mismatches. The focused
test additionally exhausts all five normalized entity kinds in live and dead
states. A combined 105 targeting, collision, action-mask, clone, and
fixed-rollout tests passed. Ruff passed for the changed benchmark/test files
with their inherited non-executable-shebang finding excluded, and for the
engine file with only its pre-existing findings excluded. `py_compile` and
`git diff --check` passed.
