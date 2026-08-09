# Exact oracle direct backup-path candidate

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Scope: source inspection and unit-sized fixed-seed tests only. The active
12-worker training corpus was not disturbed. No benchmark, corpus collection,
training, MPS/GPU work, or sustained process was run.

## Candidate

The current oracle stores this for every visited depth:

```python
(state_key, {0: action0, 1: action1})
```

The action dictionary is also passed to joint action application. During backup,
the planner hashes the state key again through `tree[key]` to recover the node it
already had while constructing the path.

The candidate stores:

```python
(node, action0, action1)
```

and passes the two action integers directly to joint application. At depth 6 and
32 simulations, a complete label removes up to 192 per-depth action dictionaries
and 192 backup tree lookups. The existing path tuple allocation remains, as do
all tree nodes and keys.

Sampling still occurs in player order 0 then 1. Joint actions still allocate
`[0, 1]` and call the same `planner.rng.shuffle(order)` exactly once per visited
depth. Legal-action calculation, stable-root candidates, Thompson bandits, leaf
evaluation, and final selection are unchanged. There are no card-name branches.

The scalar leaf-probability candidate is explicitly not included:
`_evaluate_state_prob` still returns `{0: p0, 1: 1 - p0}`, and backup still reads
both dictionary entries.

## Exactness evidence

The executable proof class is
`DirectPathFixedDepthThompsonOracle`. It duplicates only the planner selection and
joint-application methods so the inherited-dirty authoritative planner file does
not enter the isolated commit.

Command:

```bash
PYTHONPATH=src:. uv run pytest -q \
  tests/test_rl_oracle_direct_path.py \
  tests/test_rl_oracle_sampling.py \
  tests/test_rl_oracle_planner_exactness.py
```

Result: `15 passed in 1.68s`.

The direct-path tests install the previously accepted allocation-lean candidate
sampler in both reference and candidate planners. Fixed battle seed 2301, planner
seed 901, depth 2, four simulations, 16 sampled actions, and three consecutive
joint decisions preserve the pinned traces and hashes:

```text
default trace:
[(233, 107, 2, 8), (2304, 259, 4, 8), (42, 2304, 6, 9)]
default hash:
2946b87b088a9c6df38de89fed9676329b9d2ce02142e10c564e820a9d374776

stable-root trace:
[(193, 839, 2, 13), (1846, 247, 4, 14), (2304, 2304, 6, 14)]
stable-root hash:
7bda01530bd8ed0b55527bddb1d54db86514363faa868901ac0f57239b2a0fee
```

Reference and candidate tuples also contain and compare the complete final NumPy
planner RNG state. Before each environment step, the test asserts that planning
leaves the input battle summary, planner state key, and battle RNG state
unchanged. The pinned hashes cover labels, before/after state keys, rewards, and
termination.

Additional gates:

```text
Ruff: clean for oracle_direct_path.py and test_rl_oracle_direct_path.py
mypy: clean for oracle_direct_path.py
diff-check: clean
```

No wall-clock or labels-per-second claim is made. Timing remains deferred until
the active corpus releases the shared CPU window.

## Training integration

Cherry-pick the isolated candidate commit. There are two safe integration forms:

1. Minimal activation: construct `DirectPathFixedDepthThompsonOracle` instead of
   `FixedDepthThompsonOracle` in the authoritative corpus collector. All
   constructor arguments and outputs are compatible.
2. Preferred long-term fold: port the following edits into the authoritative
   base planner and retain its existing class name.

For the preferred fold:

1. Change the simulation path type to
   `list[tuple[_PlannerNode, int, int]]`.
2. Select player 0, then player 1, preserving the current root/non-root legal
   branches and calls to `sample_action` in exactly that order.
3. Append `(node, action0, action1)` and pass the two integers directly to joint
   application.
4. Change `_apply_joint_action` to accept `action0` and `action1`. Keep
   `order = [0, 1]`, `self.rng.shuffle(order)`, and choose the matching scalar
   action inside the loop.
5. Back up with `for node, action0, action1 in path`, updating the same two
   bandits from the unchanged `value_probs` dictionary. Do not access
   `tree[key]` during backup.
6. Update the existing stable-root monkeypatch test to record two scalar actions
   rather than index an action dictionary.

Keep the accepted `sample_action_subset` helper replacement from training commit
`7896f35`. Do not combine the scalar leaf-probability change with this port.

After the corpus releases CPU, run matched repeated production-shape planner
timing while pinning default/stable-root labels, battle-state hashes, complete
planner RNG state, and scalar/shadow/on rollout hashes. Until then, treat the
candidate as exact source evidence rather than a measured throughput gain.
