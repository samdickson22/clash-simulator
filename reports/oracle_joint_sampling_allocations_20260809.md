# Exact oracle candidate-subset allocation audit

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Scope: source inspection and unit-sized fixed-seed tests only. The active
12-worker training corpus was not disturbed. No benchmark, corpus collection,
model training, MPS/GPU work, or sustained process was run.

## Highest-value exact candidate

`FixedDepthThompsonOracle._sample_actions` constructs every sampled candidate
subset through this allocation chain:

1. allocate a Python `set` containing no-op;
2. allocate the NumPy `other` selection and `rng.choice` result;
3. convert every sampled NumPy scalar to a Python integer through `tolist` and
   set insertion;
4. allocate and sort a Python list from the set; and
5. allocate the returned NumPy array.

At the production depth-6, 32-simulation stable-root configuration, a complete
search can call subset sampling twice at the root plus twice at each of five
non-root depths in every simulation: up to 322 calls per joint label. The costly
branch is entered only when the legal set exceeds the 64-action sample limit,
but playable spatial actions commonly satisfy that condition.

The candidate `sample_action_subset` retains the exact same `rng.choice` call,
arguments, input ordering, no-op inclusion, output dtype, and sorted order. It
places no-op and the sampled values directly into one NumPy result array and
sorts that array in place. It removes the Python set, sampled-value Python integer
objects, and both Python list conversions.

There are no card-name branches or enabled-deck assumptions.

## Exactness evidence

Command:

```bash
PYTHONPATH=src:. uv run pytest -q tests/test_rl_oracle_sampling.py
```

Result: `8 passed in 1.02s`.

Seven boundary cases compare output arrays and complete NumPy bit-generator
state against a local copy of the current reference algorithm. They cover legal
sets below the limit, limits zero/one/two, no-op present/absent, no-op-only input,
and a full-sized sparse 2,306-action domain.

The joint fixed-seed probe uses battle seed 2301, planner seed 901, stable root,
depth 2, four simulations, 16 sampled actions, and three consecutive decisions.
Reference and candidate both produced:

```text
actions: [(193, 839), (1846, 247), (2304, 2304)]
digest:  734fcd2f3a39f6f48914db7d4c92b1032c54ec3d5cbfe2d319b18e1a0df86d62
```

The digest includes actions, before/after planner state keys, rewards,
termination, and full planner RNG state after each label. The test separately
asserts that each input `BattleState` RNG remains unchanged by planning.

Additional gates:

```text
Ruff: clean for oracle_sampling.py and test_rl_oracle_sampling.py
```

No wall-clock or labels-per-second claim is made. Timing is intentionally
deferred until the training collector releases the shared CPU window.

## Audit decisions

- Do not reuse non-root legal masks by `_state_key`. The planner key is
  intentionally quantized and omits legal-set-critical details such as exact
  hand/cycle state and placement geometry; using it as a mask-cache key could
  change legal actions.
- Do not alter or replace `rng.shuffle([0, 1])` in joint action application.
  Even equivalent-looking order selection can consume RNG differently.
- Storing `_PlannerNode` and two integer actions directly in the backup path can
  remove one action dictionary and a tree lookup per visited depth. This appears
  exact, but it is deferred as a separate candidate so its attribution and
  compatibility with existing monkeypatch tests remain isolated.
- Returning a scalar leaf probability instead of a two-entry dictionary removes
  one small allocation per simulation, but is lower value than subset sampling.

## Training-branch integration

The optimizer's `oracle_planner.py` is intentionally inherited-dirty, so it is
not included in the isolated commit. Cherry-pick the candidate commit, then make
this single authoritative method replacement:

```python
from .oracle_sampling import sample_action_subset

def _sample_actions(self, legal: np.ndarray) -> np.ndarray:
    return sample_action_subset(
        legal,
        sample_limit=self.rollout_action_samples,
        no_op_action=self.action_space.no_op_action,
        rng=self.rng,
    )
```

Keep `_legal_actions`, stable-root reuse, Thompson sampling, final greedy choice,
and joint action ordering unchanged. Port `tests/test_rl_oracle_sampling.py` with
the helper.

After the active corpus releases CPU, acceptance should add a matched repeated
planner timing at the production depth/simulation/sample configuration while
pinning actions, state keys, planner RNG state, and scalar/shadow/on hashes. Until
that evidence exists, treat this as a verified exact source candidate rather than
a measured throughput optimization.
