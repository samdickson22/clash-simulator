# Simple Gym imitation-policy initialization gate

Date: 2026-08-28

## Decision

The Simple PyTorch trainer now has a separate, fail-closed
`--initialize-policy-from` path. It copies only a compatible V2 policy's model
configuration, typed vocabulary, and weights into update zero. It deliberately
does not restore optimizer moments, update counters, transition counters,
simulator state, or RNG state. Exact `--resume-from` behavior remains disabled
for the Simple Gym.

This distinction is required for the intended pipeline:

1. causal public-observation imitation pretraining;
2. a fresh Simple-Gym simulator/optimizer run initialized from those weights;
3. short PPO quality comparisons before any long CUDA campaign.

The gate requires the exact current 494-token vocabulary, matching entity
capacity, canonical lane globals, no legacy accumulated-history slots, no
deterministic-resource state, and no play-hazard gate. The Simple collector may
feed its exact public projection to a `causal-frame-v1` policy because the
schema is identical and all confidence values are observed as one. Stabilized
`causal-vision-v1` input remains rejected. Checkpoint metadata records both the
policy input domain and the collector projection domain.

## Exact MPS proof

Source checkpoint:

- path: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_capacity48_f3_seed1156001/candidate.pt`
- file SHA-256: `88096ba2c86f3cbfa956f4c90b20b65c9c2a79706707dc444d0693fbef7e448d`
- architecture: 1,685,460 parameters, 494 tokens, 48 entities, structured
  memory 64, hierarchical mode gate, permutation-equivariant slot choice

The MPS trainer initialized a two-environment 48-entity/64-effect Simple Gym,
saved update zero, and exited before rollout because `--updates 0` was used.
The source and saved state dictionaries had the identical canonical digest
`bf21b87afdd54abae05915df086a1c9c583705cb847c2ceb07d6c6b171d4edf1`.
The saved checkpoint contained:

- `update = 0`
- `total_transitions = 0`
- zero optimizer state entries
- `weights_only = true`
- `optimizer_reset = true`
- `update_reset = true`
- `simulator_state_reset = true`
- policy domain `causal-frame-v1`
- collector domain `simulator-exact-public`

The temporary smoke checkpoints were removed after verification.

## Validation

- `26 passed, 6 skipped` across the Simple backend, tensor collector, and
  training-admission suites
- Ruff clean on all changed files
- `git diff --check` clean

The skipped cases are unavailable CUDA variants on the M4 host. A real CUDA
PPO update initialized from the promoted imitation candidate remains required
before a production training claim.
