# Specialized exact Entity deepcopy

## Change

`BattleState.clone()` traverses every live combat object. Generic
`copy.deepcopy` reconstructed each `Entity` subclass through the general
reduce protocol and routed every scalar field through recursive dispatch. The
candidate adds one inherited, memo-aware `Entity.__deepcopy__` implementation:
it copies exact Python atomic built-in values by identity, recursively deep
copies every other attribute, and publishes the clone in the memo before
following its `battle_state` cycle.

Every Position, card wrapper, mechanic, list, dict, set, tuple, NumPy value,
pending movement structure, and subclass-owned payload remains recursively
copied. The method is shared by arbitrary Entity subclasses and contains no
card, deck, mechanic-name, or enabled-interaction branch.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- fixed three-snapshot workload, alternating generic/specialized order
- clone microbenchmark: 15 matched pairs, 300 clones per row
- production Oracle: 11 matched pairs, depth 6, 32 simulations, 64 sampled
  actions, three labels per row

| workload | generic entity deepcopy | specialized entity deepcopy | ratio-of-medians | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Three-snapshot clone loop | 0.147866 s / 2028.86 clones/s | 0.108996 s / 2752.40 clones/s | +35.6621% | +35.8988% | 15/15 | +35.0811% to +36.4128% | clone-isolation gate |
| Exact Oracle, 3 labels | 1.127206 s / 2.66145 labels/s | 1.112571 s / 2.69646 labels/s | +1.3154% | +1.1844% | 11/11 | +1.0680% to +3.7312% | `071c1267c25fed5e2446b252d8765db2a1a42f14659db2db27b17bd5dc1a6018` |

The first Oracle pair was a wider +9.43% host/cold outlier. The accepted claim
uses the conservative paired median; the complete confidence interval is
reported rather than treating that first pair as representative.

## Oracle command

```bash
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1 \
  nice -n 15 uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison entity-deepcopy --seed 9003 --planner-seed 2003 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

Raw outputs:

- `/tmp/entity_deepcopy_oracle_11.json`
- `/tmp/entity_deepcopy_clone_15.json`

## Exactness and focused gates

- Generic/specialized Oracle runs in scalar/off, shadow, and optimized/on mode
  all produced
  `071c1267c25fed5e2446b252d8765db2a1a42f14659db2db27b17bd5dc1a6018`.
- Seed 9003, 64-decision generic/specialized scalar/off, shadow, and
  optimized/on rollouts all produced
  `a5197f1ac5bbf9d4517f653f29f793730638e0e497ad459b15cfa629db262172`.
  Shadow recorded one comparison and zero mismatches.
- Seed 8831 repeated the pinned
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`
  digest in all modes, with one shadow comparison and zero mismatches.
- Direct generic/specialized tests compare all entity types/field names and
  public values, then prove Position, wrapper, mechanics list, individual
  mechanic, and BattleState-cycle isolation. Existing clone/cache/planner,
  target, collision, and action-mask gates remain in scope.
- 222 focused clone/cache/planner/targeting/collision/action-mask tests and 736
  enabled troop/spell/projectile/reachable-child interaction tests passed.
- New tests and benchmark code are Ruff-clean; changed Python files compile
  and `git diff --check` is clean. `entities.py` retains its inherited lint
  findings outside candidate lines.
- Combined `entities.py`/`card_types.py` mypy retains 50 inherited findings
  and has no finding at a candidate-changed line.
