# Simple PyTorch main-stack isolated integration (2026-08-26)

Status: isolated review candidate only. Nothing in `/Users/sam/Desktop/code/clasher`
was modified, committed, stashed, or reset.

## Provenance

- Isolated worktree: `/private/tmp/clasher-simple-main-integration.Vxp0Xq`
- Main committed base: `20cc861b23937ec884fc22335c62d5b03a027f51`
- Simple branch HEAD at refreshed gate: `5a8cc34ecdb6b58fd63abb2c3c2d89111fca8c4b`
- Current Simple Gym source tip: `37e4fff3907a8b812595f95cc9c6bf53b1062488`
- Simple Gym source tree: `src/clasher/torch_sim` tree
  `bfe7134acbf2122006fc1b42daa0cbc02ef5eb67`
- Generic collector source blob: `b8594d3c93599928bb09ecba589fee04081f6b17`
- Supported-deck source blob: `96da8171849f47eb604b8a33d18f7d7e3d70b3d4`
- Typed vocabulary SHA-256:
  `960c1c1d68dea56786b0e196c5fc772b298fa16db168a81ca6c6d36c60c54704`

The following current dirty-main dependency closure was overlaid byte-for-byte
before integration edits:

- `train_recurrent.py` `9881490e7f6d35eff776d8ca61051eb1c432f08a6946002f75dbfe050a8ac5c8`
- `model.py` `a7ad78b2ab88205a06585aaeaa0414f5c97134929063cffe20a16107556243aa`
- `structured_obs.py` `089db674c16dd2bfeb7a08f28ac5629befd095e604024f1f37e4a950a6f6b1ab`
- `public_action_mask.py` `361695730ba9d16db17ebda7ef3f3a0f23e835d8acf6d107098bb5f89f638739`
- `reward_model.py` `e81b39bea0107a83b63388d11cae68e6b832958013eea167662080504b155d73`
- `selfplay_env.py` `3a81d6207e738c11794ec01e5b095f97a2e5e38e9a54a5846c198d351d2e004f`
- `parallel_rollout.py` `acc97eeafa6ec0f2c65473d02358c853f4a169d0333a8216ad1c73ce36662c13`
- `data.py` `82392818b00a1e7d0995801a94c1f19fb990273cb448beb5126d8cdf1aa21046`
- `action_space.py` `48d5db4b53e2f16467ca3d6e92ece726d42c7cb6a64de704a5faf9d025fe3acf`
- `deck_pool.py` `ea16ad0d900d3edf008737ca6d8e926b4ece02462c9e9a91e050d048a42a8d70`
- `imitation_objective.py` `88507e9bfe6230387a8feb5153ae640429f4539cdd897fe87aa6ea95a872d4dd`
- `card_semantics.py` `706522955f31fbed2ad6e88beb01c548d527742fe00db8a4b1b32163bcf615c4`
- `causal_rehearsal.py` `75e3a71ac3d0f064c5bc6189c418b4bee9f7bb639515a1c619f377f7eb5d815d`
- `causal_vision.py` `b2e523991591ce062a95ae2d1d482b6097308c0850c84a2bd4713da6c7ff7c44`
- `defense_scenarios.py` `02bb23040eb3a43dc6c3e69654ec0badcf79a8405576ce3604afd208ae94778c`
- `hierarchical_imitation.py` `8de4b550e1027c3295579b9540d184f2a99ad346652e5f23a9b943cc0bcffff3`
- `public_observation.py` `274c137f62b8d75cdbf148b6e267592d385f91434621a46c2dfb5b5882cd06fa`
- `strategy_bots.py` `146a1cc997038192795de8dff84ae1fe30c5c614bd0ad54bfcff496006213bc0`
- `structured_memory.py` `c25222600af2c9cd368db0a1b6fcc72ed9b1298aa3a354049081fd7d937fb39c`

`data.py` then received only the simple-branch cached Princess-tower data helper
needed by `simple_standard.py`. `train_recurrent.py` then received the isolated
routing patch described below.

## Refreshed final integration gate

The read-only refresh at `2026-08-26T17:00:08-0700` found the active main-tree
training process healthy and unchanged:

- Trainer PID: `72506` (running; it was not signalled or modified).
- Target: update 146.
- Latest completed update: 59, with 241,664 transitions.
- Latest checkpoint:
  `checkpoints/hog26_strategy_majority_seed1075001/policy_v2_update_000059.pt`.
- Main committed HEAD remained
  `20cc861b23937ec884fc22335c62d5b03a027f51`.
- Dirty `data.py` SHA-256 remained
  `82392818b00a1e7d0995801a94c1f19fb990273cb448beb5126d8cdf1aa21046`.
- Dirty `train_recurrent.py` SHA-256 remained
  `9881490e7f6d35eff776d8ca61051eb1c432f08a6946002f75dbfe050a8ac5c8`.
- Typed vocabulary SHA-256 remained
  `960c1c1d68dea56786b0e196c5fc772b298fa16db168a81ca6c6d36c60c54704`.

The preserved routing patch remains byte-identical at
`reports/patches/simple_pytorch_main_routing_20260826.patch`, SHA-256
`2f7935a94e2fe79297e3dc98ba1485c95b779dbece990b8e537da613bd9131f5`.
It still applies cleanly to committed main base `20cc861b`, but must not be
applied whole to the current dirty main tree: its already-overlaid
`src/clasher/data.py` and `src/clasher/rl/train_recurrent.py` hunks conflict.
No other routing-file conflict was found.

The rebased, current-dirty two-file delta is preserved at
`reports/patches/simple_pytorch_main_current_dirty_route_delta_20260826.patch`,
SHA-256
`bb7f9d4a6280c5effe389129ea01a146520931a28538b7db008e3bf6855c7968`.
It passes `git apply --check` against the current dirty main snapshot. The
three new routing/report files from the preserved routing patch also pass a
filtered apply check. All 168 current-simple source, test, script, and deck
artifact paths selected from `37e4fff3` are absent in main, so that portion is
strictly additive.

The exact rebased assembly was reproduced in disposable worktree
`/private/tmp/clasher-current-integration-gate.0QnSg3` from:

1. committed main `20cc861b`;
2. the byte-exact dirty-main training dependency closure;
3. all current-simple additive paths from `37e4fff3`;
4. the filtered new routing files; and
5. the rebased current-dirty `data.py`/`train_recurrent.py` delta.

That assembly passed:

```text
259 passed, 166 skipped in 53.27s
```

The skips were CUDA variants on the Mac. `py_compile`, Ruff, and
`git diff --check` also passed for the assembled source and report changes.

### Exact safe application sequence

Do not apply while PID `72506` or any of its actor children are running.
After it exits naturally:

1. Require the log to end with update 146 and its saved checkpoint; hash the
   final checkpoint before changing source.
2. Reassert main HEAD and the `data.py`, `train_recurrent.py`, and typed-vocab
   hashes above. If any differ, regenerate and re-run the rebased gate.
3. Create a new integration branch/worktree. Do not apply first in the dirty
   training checkout.
4. Overlay the same byte-exact dirty-main dependency closure into that worktree.
5. Restore the 168 additive simple paths from `37e4fff3`; fail if any selected
   target already exists.
6. Apply only these paths from the preserved routing patch:
   `src/clasher/rl/simple_pytorch_backend.py`,
   `tests/test_rl_simple_pytorch_backend.py`, and this report.
7. Apply
   `reports/patches/simple_pytorch_main_current_dirty_route_delta_20260826.patch`.
8. Run the full simple suite and static checks shown below, then the one-update
   CPU smoke. On a CUDA host, also run the tensor public-mask equivalence and
   CUDA-Graph tests. Commit or merge only after all gates pass.

Minimum CPU verification command:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_rl_simple_pytorch_backend.py \
  tests/test_rl_simple_tensor_collector.py \
  tests/test_build_simple_supported_decks.py \
  tests/test_benchmark_simple_gym.py \
  tests/test_validate_simple_full_matches.py \
  tests/test_torch_simple_*.py
```

Minimum CUDA-specific verification:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_rl_simple_pytorch_backend.py \
  tests/test_torch_simple_cuda_graph.py
```

## Route implemented

- New CLI backend: `--simulation-backend simple-pytorch`.
- New supported-deck and typed-vocabulary artifact arguments.
- Fresh-only admission: resume is rejected until exact resume metadata is gated.
- `actor_workers=1`, self-play, standard horizon, exact public projection,
  canonical lane globals, no legacy fast path, and no legacy deck/scenario
  sampling are required.
- The 494-token manifest is reconstructed by explicit numeric token IDs.
- Hero and Evolution variants are required as separate typed keys. Unknown
  variants return no token; there is no base-family collapse.
- Contextual card aliases plus serialized primary body names and blueprint
  visible child names resolve all 66 public actions and every admitted runtime
  troop/building body with zero unknown-token substitutions.
- `SimplePublicMaskV2Adapter` is tensor-native and consumes actor tensors only.
  It never reads the critic, simulator legal mask, or labels. Simulator
  legality remains a separate tensor in the collector. The retained host
  adapter is reference-only and exact trace comparisons gate the tensor path.
- `SimpleTensorCollector` feeds an actual `ClasherPolicy`, preserves recurrent
  hidden/cell state, converts to the existing `RolloutBatch`, and persists
  explicit backend/domain/reward/artifact metadata in checkpoints.
- Reward is fresh-only `objective-v1-gamma-v1`, with gamma persisted, absorbing
  terminal potential, zero invalid-action penalty, and zero elixir-leak penalty.

## Conflicts and resolutions

- Textual merge conflicts: none. All tracked dirty-main overlays applied cleanly
  with three-way `git apply`.
- Initial import conflict: main committed HEAD lacked the current dirty training
  dependency closure and the simple tower-data helper. The bounded closure above
  makes all target imports succeed.
- Initial typed lookup mismatch: 13 public action aliases and 25 troop-body
  labels did not resolve by raw catalog name. Context-aware resolution reduced
  this to zero action, troop, and building misses without using unknown IDs.
- The four vocabulary-declared ambiguous normalized aliases (`clone`,
  `lightning`, `royalrecruits`, `spiritempress`) fail closed unless the exact
  typed stable key is supplied.

## Verification

Focused suite:

```text
12 passed, 2 skipped in 3.72s
```

Command covered the new backend tests, generic collector tests, and supported
deck artifact tests. The two skips were expected local CUDA variants. The
public-mask test is parametrized for CPU and CUDA and proves exact tensor/NumPy
mask equality across four free-running decision boundaries; the CPU trace
passed and the CUDA trace remains pending a CUDA host.

One-update CPU smoke used one Gym row, two seats, one decision, and a 32-wide
fresh policy. It completed one rollout, GAE/PPO update, and checkpoint save:

```text
simulation_backend=simple-pytorch
tokens=494
transitions=2
collect_s=0.14 learn_s=0.12 tps=7.7
```

Checkpoint:

- Path: `/private/tmp/clasher-simple-ppo-tensor-mask-smoke.Vxp0Xq/policy_v2_update_000001.pt`
- SHA-256: `1ae784a96d510b1a7a3357c18f383b488e93f5d071785b6d18e65e81112ea1f4`
- Backend metadata digest:
  `b057b2169829618fdbe8a7af0eb18938e3e8a08da83e50f59ab91b071d704f65`
- Reward digest:
  `ef3914ce85d8c820cd02cef18de4dbe52460c7ddee70cfd615ef7538a8d50d66`
- Supported-deck artifact SHA-256:
  `c93de9989841743b535fe5fde182abe19e1983c8f67a0a27d0c191ea9ccd212f`

Static compile and Ruff checks pass for the new adapter, trainer route, and
focused test.

## Remaining gate

This proves the isolated CPU training seam and tensor-native mask equivalence,
not production CUDA performance. The CUDA-parametrized mask trace and the full
CUDA rollout/throughput gate remain unexecuted on this host. Exact resume remains
rejected rather than silently accepting incompatible backend/reward/domain
metadata.
