# Simple PyTorch final contact-semantics main integration refresh (2026-08-27)

Status: CPU- and A6000-validated final isolated integration. The live checkout at
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
  `504444ea400ff8bf595c0386ff000afe2c1f3490`
- Exact source and integrated `src/clasher/torch_sim` tree:
  `cad04dbbc9cd8d4a39c9c79227dcbf65caae38b0`
- Integrated code tip before this report refresh:
  `b1ff9f1e`
- Integrated code tree before this report refresh:
  `e734ab7eaa12d201d2edb9679a39f9b886b36993`

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
7. `f290a495` — overlay the serialized dense river-jump foundation exactly from
   source `83873115`.
8. `b45fcb73` — overlay dense collision, hover, and integrated river movement
   exactly from source `f67ed3a8`.
9. `b1ff9f1e` — overlay capture-safe, owner-mirrored contact plus pending-body
   and kamikaze semantics exactly from source `504444ea`.

The earlier documentation-only commit `1f9d32bb` is superseded by this report.

## Exact additive closure

The selected additive closure now contains 196 paths:

- all 124 files under `src/clasher/torch_sim`;
- `src/clasher/rl/simple_tensor_collector.py`;
- the four Simple Gym builder/calibration/benchmark/full-match scripts;
- 66 focused Simple Gym/collector/builder/benchmark/validator tests; and
- `training_decks/simple_gym_supported_v1.json`.

Every selected path at the integrated code tip has the same Git blob ID as
`504444ea`. The mismatch count is zero.

- Sorted path-manifest SHA-256:
  `20501fd10751cf9b1284a662a3c1396b79d77ced904f3e1f133111cf83647900`
- Ordered `blob-id path` manifest SHA-256:
  `0c72eb05b872a91ca633fdf99655c05e9985675e907bf1fadb63d08e43b3d0f4`

Representative refreshed file SHA-256 values:

```text
9d458adfb5910a123456dd787a506043c7acf31ab2a1592248442ac1fb120ead src/clasher/torch_sim/simple_public_mask.py
1395dc52772eaa6dc23a97709492f59f5ae9966bfdfcdb7f6386e9533ddb3bb2 src/clasher/torch_sim/simple_attack_locks.py
978e33fd6eb65b83783da73033f5f55ee2e77d582d8487c2ca881d34a8d8b17e src/clasher/torch_sim/simple_collision_navigation.py
297621e470ba3af5ac2f7245cbcf1f6baaa419076612ca326e0b5af26ce93648 src/clasher/torch_sim/simple_river_jump.py
c7be4cde72fe63614ca639b125119a3d1c78aeaa636f60805833d0c85028c324 tests/test_torch_simple_public_mask.py
009f429a7dd2c84af96d355ae7a12aa2b48972fb7a02e362104daf87940229b5 tests/test_torch_simple_tower_combat.py
d4a0dfac0fb8e5b2ff59196e878e1d27ceb36d8e3ccfcd603a6c8b0cd22ce653 tests/test_torch_simple_collision_navigation.py
e0754f5ac897e46c76397f51a853bde48c360df0601116060bb7d280746e026d tests/test_torch_simple_river_jump.py
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

Throughout the isolated refresh, the Desktop checkout remained on branch
`codex-enabled-deck-parity-handoff` at committed HEAD
`20cc861b23937ec884fc22335c62d5b03a027f51`. Its tracked binary diff hash and
all checked dependency hashes remained unchanged. Live training independently
changed untracked/checkpoint state during the work, so this report deliberately
does not claim that the porcelain-status hash stayed static.

```text
7fca1024186a26660501a30af31dc87c8e05be776aecd108dc1c8d0c211c8b34  tracked binary diff, initial and final snapshots
```

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

## CPU verification status

The exact `504444ea` integration completed the 67-file Simple Gym/current
routing/collector suite:

```text
409 passed, 251 skipped in 79.56s
```

The skips are CUDA-parametrized cases on the Mac. The command covered every
`test_torch_simple_*.py` file plus the route adapter, actual collector, deck
builder, benchmark, and full-match validator.

The current source checkout's strategy behavior and direct action-geometry
tests were also executed against that isolated predecessor's `PYTHONPATH`:

```text
85 passed in 5.12s
```

The final `f67ed3a8..504444ea` delta changes only `src/clasher/torch_sim` and
its focused tests; it does not change either external strategy test artifact or
the strategy/action-geometry implementation paths they exercise. The result is
therefore retained as unchanged-path evidence rather than rerun against an
actively training shared checkout.

The exact external test artifacts remain:

```text
7446d158f66bad857e077e09d9055b9dab045e68b25a2083f1951c41a993fead tests/test_rl_strategy_bots.py
341b2e981951b1ca7cc579da8d851c98d4d6cdf6e63070e9196c44bde34a5d69 tests/test_rl_strategy_action_geometry.py
```

Test-log SHA-256 values:

```text
c3fd0d3051c8664f5452ef4cdbe79c75522ba439bc6d4fc6faa2d78b7c094069 final-simple-tests-contact-refresh-20260827.log
cb5e946ffb27bd1f4b6bac4c44656702de0de39a83caf83e9f24cda6e772b222 final-strategy-tests-collision-refresh-20260827.log
```

On the final exact overlay, scoped Ruff passed for all 11 files changed by
`504444ea`, the route, collector, and route tests. `compileall` and
`git diff --check` passed across the tensor engine and integration surface. The
byte-exact production scripts retain their previously audited `EXE001` and
`SIM117` exclusions. The imported source was not reformatted.

A final eager-CPU full-match validator was started against the stale
`f67ed3a8` predecessor, then stopped by its owner without an artifact when the
new source superseded it and the protected 12-worker Desktop training job
resumed. The broad final-`504444ea` CPU suite and one-update PPO smoke later ran
in released windows. The resource-heavy eager-CPU terminal replay was not
repeated; the exact CUDA-Graph regulation/overtime/tiebreak gate below provides
the final full-episode evidence without competing with local training.

## Actual final-source 494-token PPO smoke

A fresh `ClasherPolicy` with its LSTM core ran one real PPO update through
`--simulation-backend simple-pytorch` on CPU at exact integration code commit
`b1ff9f1e`:

```text
model parameters: 119,095
typed tokens: 494
Gym rows: 1
actor seats: 2
rollout decisions: 1
transitions: 2
collect_s: 0.51
learn_s: 0.06
saved update: 1
```

The temporary checkpoint was not copied into either repository:

- Path:
  `/private/tmp/clasher-simple-ppo-final-contact.VGSX8Y/policy_v2_update_000001.pt`
- Checkpoint SHA-256:
  `fdd7266d51975979134709f637e56396732f8df9f06b490c48a9432f42583592`
- Smoke stdout SHA-256:
  `b2ff1a50e3511a2319dd2ba248e2edc35b3bebef77c26ecbf7435183398368ca`
- Loaded-metadata assertion SHA-256:
  `a31ee82636d453d1b767c1635284ff7bd90b33b98b69449132d38c035fbc8eee`

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

## Final contact repair closure and remaining limits

The predecessor `f67ed3a8` overlay exposed two hard failures before promotion:
exact-overlap tie directions were not 180-degree owner-mirror equivariant, and
an eight-direction tensor was allocated inside every collision tick, which
made CUDA Graph capture fail. The independent mirror reproduction output has
SHA-256
`b27e0ff9b3ba30bc00fb1b57fb831b28f7e7fa188eb9f7d3940fc1498d6834cf`.

Source `504444ea` repairs both through generalized owner-oriented tensor
selection with no per-tick lookup allocation and adds the direct mirror
regression. The same source delta makes pending deployed bodies occupy contact
space and remain targetable while still unable to act, and models serialized
Skeleton Barrel contact as a stun-pausable kamikaze countdown that self-pops
into the existing payload/death-spawn path without direct tower damage. All 11
changed implementation/test blobs are imported exactly; no integration-local
card-name branch was added.

Collision, hover, river jump, projection privacy, public-mask authority,
reward/outcomes, recurrent collection, and reset still have some compositional
rather than single end-to-end coverage. In particular, the training collector
does not force an active jump/hover contact or a collision-driven terminal
reward. Typed Hero/Evolution identities remain fail-closed and distinct in the
494-token vocabulary, but the current 66-card supported deck artifact has no
`_hero` or `_EV1` runtime root. These are explicit remaining coverage items,
not implicit acceptance.

## Exact-tip CUDA acceptance

The failed `f67ed3a8` capture attempt remains diagnostic evidence only. Exact
source `504444ea` passed 222/222 focused CUDA tests and then completed two
CUDA-Graph replays for each terminal policy at seed `202608263`:

```text
noop:
  final_tick=6000
  terminal=tiebreak
  entered_overtime=true
  digest=d14d2c7b5d41fed9784b521c9ee31c27b7d9a10903954dbf792abf73cd0c4226
first-legal:
  final_tick=3600
  terminal=regulation_crown
  winner=1
  digest=0430c8f45ab028d590bbdb293ff25dd3f936ec172aa6f9bbd7af786e83981fc1
```

Every replay was deterministic, terminal, fully native, fully committed, and
zero-fallback. The no-op episode traversed regulation, overtime, and tiebreak.
The full-validation JSON SHA-256 is
`d40ca2c836ef26184c69e2ddf314d37b5a620824e4354c72e29161d98269bcfc`.

The exact final contact engine then passed the batch-128 CUDA-Graph production
profile with 100 measured ticks across three repetitions:

```text
row-ticks/s: 410.708235, 410.053050, 409.637215
median row-ticks/s: 410.053050
median actor transitions/s: 820.106099
acceptance floor: 400 row-ticks/s
digest: f6f5ed8e3224734aa4f7a76012ebb995ab2c689f5eb59ae57113a3bc8034fc93
CUDA launches: 10
explicit host synchronizations: 0
native/committed rows per trial: 12800/12800
```

This is about 1.8 percent below the accepted pre-contact median of 417.423
row-ticks/s while retaining the same launch count and zero-sync boundary. The
profile JSON SHA-256 is
`aa72fa0e35774a095f7e1aa724197a21e9bce151c03289e021773012d2290794`.

The immutable `b1ff9f1e` integration archive was independently SHA-verified on
the worker, then passed 191/191 CUDA-focused integration tests in 249.67s. The
suite covered the actor-v2 route/mask, Graph replay, collision, river jump,
pending target/lock behavior, Skeleton Barrel contact, tower combat, abilities,
and policy-visible runtime boundaries. Its log SHA-256 is
`70181735526d18161ed69f6a386f2569bf4a38cb782e2fb737d44ada97cc19e2`.

Finally, a real 494-token, 119,095-parameter `ClasherPolicy` ran through both
`SimplePytorchTrainingCollector` and the raw tensor collector on CUDA. Selected
actions were public-mask legal, recurrent hidden/cell outputs were present,
actor-v2/reward metadata was exact, both rows were native/committed/admitted,
and fallback rows were zero. The policy-smoke JSON SHA-256 is
`e918127530d09c464b90da15c54e047e3d6a9b997f3df7bee2f43e4026c04ca4`.

The evidence artifacts are preserved on the final source branch as:

```text
reports/simple_gym_cuda_a6000_504444ea_full_validation_20260827.json
reports/simple_gym_cuda_a6000_504444ea_graph_batch128_20260827.json
reports/simple_gym_cuda_a6000_b1ff9f1e_integrated_tests_20260827.log
reports/simple_gym_cuda_a6000_b1ff9f1e_policy_smoke_20260827.json
```

They are committed by source evidence commit `10b2153a`. The authoritative
aggregator is
`reports/simple_gym_cuda_a6000_contact_final_20260827.json`, SHA-256
`0dc2f070feadf11a15eb55ae43deb410be89759afdf2db7ad0261be820f42b0b`.

The A6000 pod was terminated successfully after evidence copy; the provider
reported zero active pods.

The immutable code archive handed to the CUDA worker is:

```text
commit  b1ff9f1e2e1380071cca62afab68afdbb5dfdef9
tree    e734ab7eaa12d201d2edb9679a39f9b886b36993
archive /private/tmp/clasher-main-final-integration-504444ea-b1ff9f1e.tar
sha256  599686cc4886792f5a2668cc5fc4bfd8474f87493c264aae116ce15b4171966b
```
