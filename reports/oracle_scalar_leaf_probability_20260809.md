# Exact oracle scalar leaf-probability candidate

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Scope: source inspection and unit-sized fixed-seed tests only. The active
12-worker corpus was not disturbed. No benchmark, corpus run, training, MPS/GPU
work, or sustained process was started.

## Candidate

Each simulation evaluates one leaf probability and currently allocates:

```python
{0: p0, 1: 1.0 - p0}
```

The backup loop immediately reads the two entries and discards the dictionary.
The candidate computes the scalar `p0` internally, backs up player 0 with `p0`,
and backs up player 1 with the same `1.0 - p0` expression. At 32 simulations it
removes exactly 32 two-entry dictionaries per joint label.

The existing `_evaluate_state_prob` method remains unchanged and continues to
return the public/private compatibility mapping wherever it is called directly.
Only the search loop uses the new `_evaluate_state_prob_p0` scalar method.

No other optimization is included. In particular, candidate sampling, direct
backup paths, tree behavior, action ordering, legal masks, Thompson updates, and
joint RNG shuffling are unchanged. There are no card-name branches.

## Exactness evidence

Command:

```bash
PYTHONPATH=src:. uv run pytest -q \
  tests/test_rl_oracle_scalar_leaf.py \
  tests/test_rl_oracle_direct_path.py \
  tests/test_rl_oracle_sampling.py \
  tests/test_rl_oracle_planner_exactness.py
```

Result: `18 passed in 1.34s`.

The scalar-leaf probe records every `_PlayerBandit.update(action,
reward_probability)` call for reference dictionary backup and candidate scalar
backup. With battle seed 2301, planner seed 901, depth 2, four simulations, and
16 sampled actions, both modes have 16 identical ordered updates:

```text
default first label: {0: 233, 1: 107}
backup digest: 227accb8917959f49e8dd316b0511ecbd333dafdbddba1497c6c83b229f50b79

stable-root first label: {0: 193, 1: 839}
backup digest: 9df283e28a176005a2b85e32f0c80967b1b0da03b6bb19bffc634f5c1de8c99d
```

Reference and candidate also compare exact labels, input/output planner state
keys, input battle RNG, and complete final NumPy planner RNG state.

The existing three-decision pinned traces and hashes remain exact:

```text
default: 2946b87b088a9c6df38de89fed9676329b9d2ce02142e10c564e820a9d374776
stable:  7bda01530bd8ed0b55527bddb1d54db86514363faa868901ac0f57239b2a0fee
```

A compatibility test asserts `_evaluate_state_prob` still returns the same
two-entry dictionary, then replaces that method with a raising mock and proves
the candidate search completes without invoking it.

Additional gates:

```text
Ruff: clean for oracle_direct_path.py and test_rl_oracle_scalar_leaf.py
mypy: clean for oracle_direct_path.py
diff-check: clean
```

## Bounded production-shape timing

After the CPU window was released, the candidate was measured with three fixed
states and five alternating repetitions per mode:

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_scalar_leaf.py \
  --states 3 --state-stride 4 --repetitions 5 \
  --planner-depth 6 --planner-simulations 32 \
  --planner-action-samples 64 --decision-interval 8 \
  --engine-fast-path on
```

Machine: Apple M4 Pro, 24 GiB RAM, Darwin arm64, Python 3.12.13. Mapping and
scalar modes alternated first position to reduce ordering bias and shared the
same fixed snapshots, seeds, direct backup path, and allocation-lean sampler.

| mode | median seconds / 3 labels | mean seconds | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| mapping leaf | 2.007365 | 2.024802 | 0.038303 | 1.494497 |
| scalar leaf | 2.002201 | 1.997410 | 0.014113 | 1.498351 |

The median change is +0.258% labels/s. All ten runs produced hash
`72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`.
This confirms no regression, but the effect is too small relative to run
variation to claim material end-to-end throughput on its own.

## Training integration

Cherry-pick the isolated candidate commit, then fold these two changes into the
authoritative planner already containing training commit `c8f2414`:

```python
def _evaluate_state_prob_p0(self, battle: BattleState) -> float:
    return reward_win_prob_p0(battle, self.reward_profile)
```

and inside `select_actions`:

```python
value_prob_p0 = self._evaluate_state_prob_p0(sim)
for node, action0, action1 in path:
    node.by_player[0].update(action0, value_prob_p0)
    node.by_player[1].update(action1, 1.0 - value_prob_p0)
```

Retain the existing dictionary-returning `_evaluate_state_prob` method unchanged
for compatibility. Port `tests/test_rl_oracle_scalar_leaf.py`. Do not alter the
direct path, subset sampler, leaf reward model, action order, or any other planner
logic in this commit.

Continue pinning every backup value, complete planner RNG state,
default/stable hashes, and scalar/shadow/on rollout hashes when composing this
with later engine changes.
