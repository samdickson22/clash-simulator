# Oracle optimizer source handoff (2026-08-09)

This handoff is source-only because the training thread owns a persistent 12-worker
DAgger collector and queued MPS fit. No sustained timing, multi-worker run, or GPU
work was performed.

## Exact planner candidate

`src/clasher/rl/oracle_planner.py` contains three data-independent reductions:

1. Compute the root state key and the two full root legal-action arrays once per
   `select_actions` call. Every simulation still performs the same Thompson sample
   from those arrays, in the same player order, so NumPy RNG consumption is
   unchanged.
2. Replace eager `tree.setdefault(key, _PlannerNode())` with `get` plus conditional
   construction. This avoids allocating and discarding a node and two bandits on
   every revisit.
3. Convert each sampled legal array to a Python list once per bandit selection,
   instead of once in `ensure_actions` and again in the scoring loop.

The fixed defense-v2 trace uses seed 2301, oracle seed 901, depth 2, four
simulations, 16 action samples, a two-tick interval, and three decisions. Before
and after actions are `(233, 107)`, `(2304, 259)`, `(42, 2304)`; the combined
action/state/reward digest is
`2946b87b088a9c6df38de89fed9676329b9d2ce02142e10c564e820a9d374776`.
The regression test also proves that root mask construction is exactly two calls
regardless of simulation count (rather than two calls per simulation plus two at
final selection). No wall-clock speedup is claimed until a clean compute window.

Port the hunks in `_PlayerBandit.sample_action`, `_PlayerBandit.greedy_action`,
`FixedDepthThompsonOracle.select_actions`, and the split
`_legal_actions`/`_sample_actions` methods. The exact tests are in
`tests/test_rl_oracle_planner_exactness.py`.

## Crash-resumable corpus publishing

`src/clasher/rl/oracle_corpus.py` is an isolated utility module. It provides:

- stable fingerprints over every output-affecting collection input;
- atomic, fsync-backed `.npz` shard and JSON manifest replacement;
- deterministic `part-INDEX-of-COUNT.npz` paths beside the requested corpus;
- shard metadata, array/sample validation, legal-action validation, and safe reuse;
- a manifest recording fingerprint, shard count, completed indices, and completion.

The optimizer worktree's untracked `imitation.py` demonstrates the integration:
each worker reuses or atomically publishes its assigned shard and returns only its
path, the parent merges shards in index order, and the final legacy-compatible
corpus is also atomically replaced. Deleting the merged corpus and rerunning with a
collector stub that raises reconstructs the corpus entirely from the completed
shard, proving crash resume without oracle recollection.

When porting onto the training branch's newer behavior-policy collector, include
these additional fingerprint inputs beyond the common planner configuration:

- `behavior_checkpoint_sha256`: SHA-256 of the checkpoint bytes, or `null`;
- `expert_probability`;
- SHA-256 of `decks.json` rather than only its path.

This prevents a shard from being reused across a changed behavior checkpoint,
DAgger mixing probability, deck definition, reward profile, planner configuration,
seed partition, worker count, or observation shape. Keep the training branch's
existing behavior recurrent-state reset and expert/student action selection logic
unchanged inside `_collect_oracle_shard`.

Focused source gates:

```text
Ruff: oracle_planner.py, oracle_corpus.py, imitation.py, and new tests clean
Mypy: oracle_planner.py, oracle_corpus.py, imitation.py clean
Pytest: planner exactness/oracle DAgger 6 passed
Pytest: corpus utility/imitation integration 5 passed
```
