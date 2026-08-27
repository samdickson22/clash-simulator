# Simple PyTorch final isolated main integration (2026-08-27)

Status: CPU-validated isolated integration candidate. The live checkout at
`/Users/sam/Desktop/code/clasher` was read only throughout this assembly; no
source file, process, dataset, or checkpoint there was modified, copied,
stashed, reset, or committed.

## Provenance

- Isolated worktree:
  `/private/tmp/clasher-main-final-integration.lcUnG2`
- Isolated branch: `codex/simple-pytorch-main-final-20260827`
- Committed main base:
  `20cc861b23937ec884fc22335c62d5b03a027f51`
- Exact clean Simple Gym source:
  `1a641bb81ea4d866d8923bd1c841803b24280091`
- Simple Gym `src/clasher/torch_sim` tree:
  `16b5a13077f347249b30abe3824b2d44fa09ab25`
- Integrated code tip before this report-only commit:
  `51ef6a35bdc3efa2d3ff473afdbf631cb89c4329`
- Integrated code tree before this report-only commit:
  `0fbe7edf2decadec166812ef124b7fcca0b92e28`

Logical code commits:

1. `1e438bdcf17c06ba381e8ac140a812b0070257b1` — snapshot the
   current typed training dependency closure.
2. `dc44375e8b344bec438a0f355838f237fbf9eb95` — import the unified
   dense Simple PyTorch Gym from the exact clean Simple Gym tip.
3. `f06b9e8916f82f027baa48285ac64bb9904b9ccb` — route fresh recurrent
   training through the Simple PyTorch Gym.
4. `51ef6a35bdc3efa2d3ff473afdbf631cb89c4329` — refresh the imported
   Gym to the final accelerator-device-canonicalized source tip.

## Current dirty-source closure

The following 19 implementation files and one typed-vocabulary artifact were
overlaid byte-for-byte from the current source checkout before any integration
edits. The SHA-256 values below were rechecked after the assembly:

```text
9881490e7f6d35eff776d8ca61051eb1c432f08a6946002f75dbfe050a8ac5c8 src/clasher/rl/train_recurrent.py
a7ad78b2ab88205a06585aaeaa0414f5c97134929063cffe20a16107556243aa src/clasher/rl/model.py
089db674c16dd2bfeb7a08f28ac5629befd095e604024f1f37e4a950a6f6b1ab src/clasher/rl/structured_obs.py
361695730ba9d16db17ebda7ef3f3a0f23e835d8acf6d107098bb5f89f638739 src/clasher/rl/public_action_mask.py
e81b39bea0107a83b63388d11cae68e6b832958013eea167662080504b155d73 src/clasher/rl/reward_model.py
3a81d6207e738c11794ec01e5b095f97a2e5e38e9a54a5846c198d351d2e004f src/clasher/rl/selfplay_env.py
acc97eeafa6ec0f2c65473d02358c853f4a169d0333a8216ad1c73ce36662c13 src/clasher/rl/parallel_rollout.py
82392818b00a1e7d0995801a94c1f19fb990273cb448beb5126d8cdf1aa21046 src/clasher/data.py
48d5db4b53e2f16467ca3d6e92ece726d42c7cb6a64de704a5faf9d025fe3acf src/clasher/rl/action_space.py
ea16ad0d900d3edf008737ca6d8e926b4ece02462c9e9a91e050d048a42a8d70 src/clasher/rl/deck_pool.py
88507e9bfe6230387a8feb5153ae640429f4539cdd897fe87aa6ea95a872d4dd src/clasher/rl/imitation_objective.py
706522955f31fbed2ad6e88beb01c548d527742fe00db8a4b1b32163bcf615c4 src/clasher/rl/card_semantics.py
75e3a71ac3d0f064c5bc6189c418b4bee9f7bb639515a1c619f377f7eb5d815d src/clasher/rl/causal_rehearsal.py
07225051afcd8af0f6f92b69086f8e0013fc709ac2725a00400fde66fa0ec5b9 src/clasher/rl/causal_vision.py
02bb23040eb3a43dc6c3e69654ec0badcf79a8405576ce3604afd208ae94778c src/clasher/rl/defense_scenarios.py
8de4b550e1027c3295579b9540d184f2a99ad346652e5f23a9b943cc0bcffff3 src/clasher/rl/hierarchical_imitation.py
4695de9782b6060c2848d9bcfb0b132945e2c27743fcfaff154ab10e3d830042 src/clasher/rl/public_observation.py
973bffe88a17fac84c368402930c5bbf8a5d55685ad13941b19677e48a7a53d8 src/clasher/rl/strategy_bots.py
c25222600af2c9cd368db0a1b6fcc72ed9b1298aa3a354049081fd7d937fb39c src/clasher/rl/structured_memory.py
960c1c1d68dea56786b0e196c5fc772b298fa16db168a81ca6c6d36c60c54704 reports/current_client_youtube_stable_vocabulary_v1.json
```

This refresh is materially newer than the 2026-08-26 integration report:
`causal_vision.py`, `public_observation.py`, and `strategy_bots.py` changed.
The current `strategy_bots.py` hash is therefore explicitly part of this gate.

## Fail-closed assembly

The selected additive closure contains 188 paths:

- all 121 files under `src/clasher/torch_sim`;
- `src/clasher/rl/simple_tensor_collector.py`;
- the four Simple Gym builder/calibration/benchmark/full-match scripts;
- 61 focused Simple Gym/collector/builder/benchmark/validator tests; and
- `training_decks/simple_gym_supported_v1.json`.

Every target was required to be absent before restore. The collision count was
zero. Every restored file was first checked against its Git blob at `8e430913`.
When the clean Simple Gym source advanced to `1a641bb8`, its two changed engine
files were overlaid in a separate provenance commit and all 188 selected paths
were rechecked against the final tip. The final mismatch count was zero.

- Sorted path-manifest SHA-256:
  `a995d403e5fa9c672c61d66b475fe56964a91e700c34e53566adc7d41fcfab0f`
- Ordered `blob-id path` manifest SHA-256:
  `10484ca4e1694f1187189486ce3f1515595039f7a923fa81b891ee2c503287d0`

The final refresh changed only the accelerator-device metadata sources:

```text
ea3a659653d7d05ecb3788750fdc9414d2de9e04cfe1ef24f43fad1dfc3df5f0 src/clasher/torch_sim/simple_abilities.py
80666f9f403a16fa7418c7f63a4eaf16129e2a21cd4b40c183364e126c4dd461 src/clasher/torch_sim/simple_triggered_impacts.py
```

The preserved routing patch SHA-256 is
`2f7935a94e2fe79297e3dc98ba1485c95b779dbece990b8e537da613bd9131f5`.
Only its two absent additive paths were applied:

- `src/clasher/rl/simple_pytorch_backend.py`
- `tests/test_rl_simple_pytorch_backend.py`

The current dirty-source `data.py`/`train_recurrent.py` route delta applied
cleanly. Its SHA-256 is
`bb7f9d4a6280c5effe389129ea01a146520931a28538b7db008e3bf6855c7968`.

No special route rebase was required for the newer ability, travel, triggered
impact, or heterogeneous-spawn fields: the route constructs the current
`SimpleStandardSetup` and runtime directly. Focused runtime and route tests
cover all four seams and passed. No alternate one-off field-matching layer was
introduced.

Final integration file SHA-256 values after routing:

```text
2938e456ce5c4238abee985f70cf8b2ab74580fb7949d3a1dee292f35a9b0da2 src/clasher/data.py
d998d498009925d9d55e574e7e244920c460b7f2b58160cfa4785443c75aba62 src/clasher/rl/train_recurrent.py
07d06ff3818523c0717c0946c988ba7e260460fd6061e8e01d95386fe3a1f31e src/clasher/rl/simple_pytorch_backend.py
15a0cfcb9e80dfffa9d036f95fa7a5c6d93562059fd20671b362c05fa9774ae1 tests/test_rl_simple_pytorch_backend.py
```

## CPU verification

Complete Simple Gym/current routing/collector suite:

```text
344 passed, 207 skipped in 71.00s
```

The 207 skips are CUDA-parametrized cases on the Mac. The command covered the
route adapter, actual collector, deck builder, benchmark, full-match validator,
and every `test_torch_simple_*.py` file, including the newest ability, travel,
triggered-impact, and heterogeneous-spawn suites.

The current source checkout's strategy behavior and direct action-geometry
tests were executed against the isolated integration's `PYTHONPATH`:

```text
85 passed in 4.40s
```

The exact external test artifacts were:

```text
7446d158f66bad857e077e09d9055b9dab045e68b25a2083f1951c41a993fead tests/test_rl_strategy_bots.py
341b2e981951b1ca7cc579da8d851c98d4d6cdf6e63070e9196c44bde34a5d69 tests/test_rl_strategy_action_geometry.py
```

`compileall` passed for the full imported tensor engine and its integration
surface. `py_compile`, scoped Ruff, and `git diff --check` passed for the new
backend, collector, route tests, and production Simple Gym scripts. A broad
latest-Ruff scan is not claimed as a repository-wide gate: it reports 64
pre-existing/upstream style findings in the byte-exact imported closure.

The final test-log SHA-256 values are:

```text
c62e6d55938ad8c62fc504e361cbc35618a337d909a3f0ab532e50043fcb9bfe final-simple-tests.log
3726063f9e31c8ebf21d75029edd7b49698ab7d397917a43126249913514ccd3 final-strategy-tests.log
```

## Actual 494-token PPO smoke

A fresh `ClasherPolicy` with an LSTM core ran one real PPO update through
`--simulation-backend simple-pytorch` on CPU:

```text
model parameters: 119,095
typed tokens: 494
Gym rows: 1
actor seats: 2
rollout decisions: 1
transitions: 2
collect_s: 0.45
learn_s: 0.04
saved update: 1
```

The temporary checkpoint was not copied into either repository:

- Path:
  `/private/tmp/clasher-simple-ppo-final-smoke-v2.HXYzJW/policy_v2_update_000001.pt`
- Checkpoint SHA-256:
  `285d1a52f950e16c2b42cbb61909ccb1f7c7e1f36aaa12888eb02ef7323c53d0`
- Smoke stdout SHA-256:
  `e0db1bdf7af5d26c9805982f52594aa218665703ac433f7ec968f02aaa508d85`

Persisted checkpoint contract:

```text
simulation_backend=simple-pytorch
backend_id=simple-pytorch-gym-v1
fresh_only=true
actor_semantics_id=typed-public-structured-canonical-v1
public_action_mask_contract_version=2
canonical_lane_globals=true
actor_observation_domain=simulator-exact
memory_kind=lstm
num_tokens=494
backend_metadata_digest=b057b2169829618fdbe8a7af0eb18938e3e8a08da83e50f59ab91b071d704f65
reward_contract_id=objective-v1-gamma-v1
reward_contract_digest=ef3914ce85d8c820cd02cef18de4dbe52460c7ddee70cfd615ef7538a8d50d66
supported_decks_sha256=c93de9989841743b535fe5fde182abe19e1983c8f67a0a27d0c191ea9ccd212f
typed_vocabulary_sha256=960c1c1d68dea56786b0e196c5fc772b298fa16db168a81ca6c6d36c60c54704
```

The route remains deliberately fresh-only. Resume is rejected until exact
resume compatibility for backend, reward, observation, mask, and artifact
metadata is implemented and gated.

## CUDA status and remaining gate

The existing A6000 full-terminal CUDA-Graph evidence is real, but it was
captured from source commit `5a8cc34e`, before the final ability, travel,
triggered-impact, and heterogeneous-spawn commits imported here. It proves the
earlier engine's zero-fallback terminal CUDA path, not this exact integrated
tip.

Before promotion, rerun on a CUDA host against this integration commit:

1. the tensor public-mask v2 CPU/CUDA equivalence test;
2. the CUDA-Graph eager/state parity suite, including the four newer runtime
   seams;
3. deterministic two-replay noop regulation/overtime/tiebreak and first-legal
   terminal episodes with zero fallback; and
4. the existing absolute-throughput/kernel-launch profiler gate plus one
   `SimplePytorchTrainingCollector` CUDA smoke using the real 494-token model.

Those are current-tip regression gates. They do not invalidate the earlier
A6000 result, but the earlier result cannot certify the newer integrated code.

## Source safety recheck

After all assembly, tests, and smoke work, the source checkout still reported:

```text
branch=codex-enabled-deck-parity-handoff
HEAD=20cc861b23937ec884fc22335c62d5b03a027f51
```

The current `causal_vision.py`, `public_observation.py`, `strategy_bots.py`, and
typed-vocabulary hashes still matched the values recorded above. All commits
exist only on the isolated branch.
