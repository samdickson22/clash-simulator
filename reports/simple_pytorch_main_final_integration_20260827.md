# Simple PyTorch final isolated main integration refresh (2026-08-27)

Status: CPU-validated isolated integration candidate. The live checkout at
`/Users/sam/Desktop/code/clasher` was read only throughout this refresh. No
source file, process, dataset, or checkpoint there was modified, copied,
stashed, reset, or committed.

## Provenance

- Isolated worktree:
  `/private/tmp/clasher-main-final-integration.lcUnG2`
- Isolated branch: `codex/simple-pytorch-main-final-20260827`
- Committed main base:
  `20cc861b23937ec884fc22335c62d5b03a027f51`
- Exact clean Simple Gym source:
  `d4e9dd9572408f21bfe4d09966a8553b684981ab`
- Exact source and integrated `src/clasher/torch_sim` tree:
  `29aa9a4429a103968771c9443d782d56ad042c56`
- Integrated code tip before this report refresh:
  `2d2431880f583c13b93c14a298e1980cb79a7074`
- Integrated code tree before this report refresh:
  `4761f58c9043088e134b39da159a7a24547de4b2`

Logical implementation commits, in order:

1. `1e438bdcf17c06ba381e8ac140a812b0070257b1` — snapshot the
   current typed training dependency closure.
2. `dc44375e8b344bec438a0f355838f237fbf9eb95` — import the unified
   dense Simple PyTorch Gym.
3. `f06b9e8916f82f027baa48285ac64bb9904b9ccb` — route fresh recurrent
   training through the Simple PyTorch Gym.
4. `51ef6a35bdc3efa2d3ff473afdbf631cb89c4329` — canonicalize imported
   accelerator device metadata.
5. `d8ee9c36` — refresh every selected additive Simple blob exactly to
   `d4e9dd95`, including actor-v2 public masking, serialized attack locks, and
   Crown Tower combat.
6. `2d243188` — remove the stale route-local public-mask algorithms and route
   training through the committed actor-v2 tensor authority.

The earlier documentation-only commit `1f9d32bb` is superseded by this report.

## Exact additive closure

The selected additive closure now contains 192 paths:

- all 122 files under `src/clasher/torch_sim`;
- `src/clasher/rl/simple_tensor_collector.py`;
- the four Simple Gym builder/calibration/benchmark/full-match scripts;
- 64 focused Simple Gym/collector/builder/benchmark/validator tests; and
- `training_decks/simple_gym_supported_v1.json`.

Every selected path at the integrated code tip has the same Git blob ID as
`d4e9dd95`. The mismatch count is zero.

- Sorted path-manifest SHA-256:
  `35159634d6b62aac81ddd588ce967e7eec1835fdc6c7a3a58b703a5cbec63b97`
- Ordered `blob-id path` manifest SHA-256:
  `234fa320eae572d73cf4ebef7a7eaddfcc2cfa31bf85701162bed8fc34dad51a`

Representative refreshed file SHA-256 values:

```text
9d458adfb5910a123456dd787a506043c7acf31ab2a1592248442ac1fb120ead src/clasher/torch_sim/simple_public_mask.py
1395dc52772eaa6dc23a97709492f59f5ae9966bfdfcdb7f6386e9533ddb3bb2 src/clasher/torch_sim/simple_attack_locks.py
c7be4cde72fe63614ca639b125119a3d1c78aeaa636f60805833d0c85028c324 tests/test_torch_simple_public_mask.py
009f429a7dd2c84af96d355ae7a12aa2b48972fb7a02e362104daf87940229b5 tests/test_torch_simple_tower_combat.py
c93de9989841743b535fe5fde182abe19e1983c8f67a0a27d0c191ea9ccd212f training_decks/simple_gym_supported_v1.json
```

## Newer-main dependency closure and source safety

The 19 implementation files plus the typed-vocabulary artifact captured from
the dirty newer-main checkout remain byte-for-byte unchanged from the original
isolated assembly. The most integration-sensitive hashes are:

```text
9881490e7f6d35eff776d8ca61051eb1c432f08a6946002f75dbfe050a8ac5c8 src/clasher/rl/train_recurrent.py
a7ad78b2ab88205a06585aaeaa0414f5c97134929063cffe20a16107556243aa src/clasher/rl/model.py
089db674c16dd2bfeb7a08f28ac5629befd095e604024f1f37e4a950a6f6b1ab src/clasher/rl/structured_obs.py
361695730ba9d16db17ebda7ef3f3a0f23e835d8acf6d107098bb5f89f638739 src/clasher/rl/public_action_mask.py
82392818b00a1e7d0995801a94c1f19fb990273cb448beb5126d8cdf1aa21046 src/clasher/data.py
973bffe88a17fac84c368402930c5bbf8a5d55685ad13941b19677e48a7a53d8 src/clasher/rl/strategy_bots.py
960c1c1d68dea56786b0e196c5fc772b298fa16db168a81ca6c6d36c60c54704 reports/current_client_youtube_stable_vocabulary_v1.json
```

After the refresh, the Desktop checkout still reports branch
`codex-enabled-deck-parity-handoff` at committed HEAD
`20cc861b23937ec884fc22335c62d5b03a027f51`. Its dirty state and all checked
dependency hashes are unchanged.

Final integration file SHA-256 values:

```text
2938e456ce5c4238abee985f70cf8b2ab74580fb7949d3a1dee292f35a9b0da2 src/clasher/data.py
d998d498009925d9d55e574e7e244920c460b7f2b58160cfa4785443c75aba62 src/clasher/rl/train_recurrent.py
0a7b22445ce15412dfee7d43c8e349ac547ea7626e7b4047ce2c268b5e50c53f src/clasher/rl/simple_pytorch_backend.py
211ddf9a71d6a8b9b664dcdae1acf84637ca39e39cba7218c84a0844523efcda tests/test_rl_simple_pytorch_backend.py
```

## Public-mask-v2 authority refresh

The integration no longer contains its own NumPy reference adapter or its own
hand-written tensor mask implementation. Setup compiles immutable typed tables,
then the production collector delegates directly to the committed
`SimplePublicMaskV2Provider` through `SimpleCollectorPublicMaskV2Provider`.

This materially changes the old candidate:

- semantics ID is now
  `public-action-mask-v2/tensor-actor-projection-v2`;
- the Archer Queen `troop_body` token is compiled from the exact entity lookup
  as ability-supported with serialized elixir cost 1;
- ability legality is derived only from public own-actor state: exact typed
  live entity, deployment readiness, public cooldown/duration planes, and
  elixir;
- multiple plausible owners fail closed without a public stable owner ID;
- simulator legality, critic state, labels, and host round trips remain absent
  from the runtime provider; and
- checkpoint metadata now persists the semantics ID, canonical spec, and
  digest, not only contract version 2.

The integrated route test deploys Archer Queen through the real standard
runtime and proves the actor-v2 ability bit becomes available at the same
boundary as the simulator ability action.

## CPU verification

The complete 65-file Simple Gym/current routing/collector suite passed:

```text
381 passed, 233 skipped in 73.99s
```

The skips are CUDA-parametrized cases on the Mac. The command covered every
`test_torch_simple_*.py` file plus the route adapter, actual collector, deck
builder, benchmark, and full-match validator.

The current source checkout's strategy behavior and direct action-geometry
tests were executed against this isolated integration's `PYTHONPATH`:

```text
85 passed in 3.99s
```

The exact external test artifacts remain:

```text
7446d158f66bad857e077e09d9055b9dab045e68b25a2083f1951c41a993fead tests/test_rl_strategy_bots.py
341b2e981951b1ca7cc579da8d851c98d4d6cdf6e63070e9196c44bde34a5d69 tests/test_rl_strategy_action_geometry.py
```

Test-log SHA-256 values:

```text
98d6a530ee2f4af62d457234bddbb346c0d36692cabc19338313a428feb0a332 final-simple-tests-refresh-20260827.log
3036ff5817eb2a49cac3fa0b670d944590d2c508e7059a34848682c2b11fb735 final-strategy-tests-refresh-20260827.log
```

Scoped Ruff passed for the route, collector, and their tests. The byte-exact
production scripts pass with the two already-audited upstream rules excluded:
`EXE001` (source executable bit) and `SIM117` (nested profiler context).
`compileall`, `py_compile`, and `git diff --check` passed across the full tensor
engine and integration surface. The exact imported source was not reformatted.

## Actual 494-token PPO smoke

A fresh `ClasherPolicy` with its LSTM core ran one real PPO update through
`--simulation-backend simple-pytorch` on CPU:

```text
model parameters: 119,095
typed tokens: 494
Gym rows: 1
actor seats: 2
rollout decisions: 1
transitions: 2
collect_s: 0.55
learn_s: 0.05
saved update: 1
```

The temporary checkpoint was not copied into either repository:

- Path:
  `/private/tmp/clasher-simple-ppo-refresh.j5knrc/policy_v2_update_000001.pt`
- Checkpoint SHA-256:
  `9b351e223c72c48249da9a58245f1db993e4dc07eebddc31759ec109deea486f`
- Smoke stdout SHA-256:
  `cc88811432ae4e89aec261fd9f50425b9699766661080bb605d9cf0b5408128f`

The checkpoint was loaded back and its persisted contract asserted:

```text
simulation_backend=simple-pytorch
backend_id=simple-pytorch-gym-v1
fresh_only=true
actor_semantics_id=typed-public-structured-canonical-v1
public_action_mask_contract_version=2
public_action_mask_semantics_id=public-action-mask-v2/tensor-actor-projection-v2
public_action_mask_semantics_digest=269eaba783a8c8ef7b11488cd1c1bf7d9ec15b7ab9b91aefeb5ba565565cfd05
public_action_mask_ability_policy=actor-visible-supported-champion-v1
canonical_lane_globals=true
actor_observation_domain=simulator-exact
memory_kind=lstm
num_tokens=494
backend_metadata_digest=474c662d9ad97cd099699c7898965c354127ae64f221e686edf6978a3dda7e6a
reward_contract_id=objective-v1-gamma-v1
reward_contract_digest=ef3914ce85d8c820cd02cef18de4dbe52460c7ddee70cfd615ef7538a8d50d66
supported_decks_sha256=c93de9989841743b535fe5fde182abe19e1983c8f67a0a27d0c191ea9ccd212f
typed_vocabulary_sha256=960c1c1d68dea56786b0e196c5fc772b298fa16db168a81ca6c6d36c60c54704
```

The route remains deliberately fresh-only. Resume stays rejected until exact
resume compatibility for backend, reward, observation, mask, and artifact
metadata is implemented and gated.

## Exact-tip CUDA gate still required

Earlier A6000 evidence either predates `d4e9dd95` or used the old isolated
route at `1f9d32bb`; neither certifies this refreshed integration. Promotion
requires these commands against the final report commit descended from
`2d243188`:

```bash
uv run --frozen --python 3.12 pytest -q \
  tests/test_torch_simple_public_mask.py \
  tests/test_rl_simple_pytorch_backend.py \
  tests/test_torch_simple_cuda_graph.py \
  tests/test_torch_simple_attack_lock_runtime.py \
  tests/test_torch_simple_tower_combat.py \
  tests/test_torch_simple_ability_runtime.py \
  tests/test_torch_simple_travel_runtime.py \
  tests/test_torch_simple_triggered_runtime.py \
  tests/test_torch_simple_heterogeneous_spawn_runtime.py

uv run --frozen --python 3.12 python -m scripts.validate_simple_full_matches \
  --device cuda --cuda-graph --replays 2 --seed 20260827 \
  --out reports/simple_gym_cuda_integrated_full_validation_20260827.json

uv run --frozen --python 3.12 python -m scripts.perf.benchmark_simple_gym \
  --preset profile --device cuda --cuda-graph --profile-cuda \
  --batch-size 128 --warmup-ticks 10 --measured-ticks 100 --repetitions 3 \
  --min-row-ticks-per-second 400 \
  --out reports/simple_gym_cuda_integrated_graph_batch128_20260827.json
```

The CUDA collector smoke must additionally instantiate the real 494-token
`ClasherPolicy`, collect at least one recurrent decision with
`SimplePytorchTrainingCollector`, and assert: selected actions are public-mask
legal, recurrent outputs exist, metadata exactly matches the actor-v2 values
above, every row is admitted/committed/native, and fallback rows are zero.

These are exact-current regression gates, not a claim that the prior CUDA
results are invalid. The refreshed branch is being archived for that CUDA run
before the A6000 worker is torn down.
