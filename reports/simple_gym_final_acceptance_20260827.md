# Simple PyTorch practical RL Gym — final acceptance 2026-08-27

## Outcome

**Accepted for fresh practical RL training.**

Accepted Simple source:
`504444ea400ff8bf595c0386ff000afe2c1f3490`. Accelerator evidence:
`10b2153a`. Exact newer-main integration:
`b1ff9f1e2e1380071cca62afab68afdbb5dfdef9`, tree
`e734ab7eaa12d201d2edb9679a39f9b886b36993`.

## Requirement matrix

| Original requirement | Result | Exact evidence |
|---|---:|---|
| Preserve `TensorResidentEngine` as exact-debug verifier | pass | Resident engine stays separate and unchanged by the production Simple path |
| Unified dense production engine | pass | `SimpleGymRuntime` owns dense entity/mechanic/effect/action/outcome state at fixed 50 ms ticks |
| Serialized data and practical real-game calibration | bounded pass | 66/66 compiler admission; serialized mechanics; 42-match structural calibration; unavailable combat labels not claimed |
| Public-mask contract v2 | pass | actor-only semantics v2; source/integrated CPU/CUDA tests; selected CUDA policy actions legal |
| `canonical_lane_globals` | pass | required by artifact/setup/adapter and persisted in metadata |
| Typed Hero/Evolution identity | scoped pass | exact 494-token namespaced lookup, fail-closed variants, no base collapse; no variant-root gameplay claim |
| Actor privacy | pass | actor-only mask, separate critic, no labels/simulator-mask/critic inputs |
| Rewards/outcomes/history | pass | reward digest, tower/King/match tests, previous action/reward/reset, recurrent hidden/cell smoke |
| Enabled mechanics close enough for RL | pass | 66/66 roots, 33/33 decks; 406 CPU tests, 222 source CUDA tests, direct contact/jump/hover/tower/ability/spawn coverage |
| Deterministic zero-fallback regulation/OT/tiebreak | pass | tick 6000 tiebreak and tick 3600 crown; two exact CUDA-Graph replays each; native/committed/zero fallback |
| Credible CUDA launch and absolute throughput | pass | median 410.053 row-ticks/s and 820.106 actor transitions/s; 400 floor; 10 launches; zero sync |
| Safe newer-main integration | pass | exact 504 tree at isolated b1ff; 191/191 CUDA tests; real recurrent policy smoke; live main untouched |

## Authoritative evidence

Final aggregator:
`reports/simple_gym_cuda_a6000_contact_final_20260827.json`, SHA-256
`0dc2f070feadf11a15eb55ae43deb410be89759afdf2db7ad0261be820f42b0b`.

```text
source archive SHA-256: 9b0dd8839675c5f5d59e6e7d1174d5c40c8406deb59776b90563de9f27452d4a
integration archive SHA-256: 599686cc4886792f5a2668cc5fc4bfd8474f87493c264aae116ce15b4171966b
Simple blob mismatches: 0 / 196 paths
supported decks SHA-256: c93de9989841743b535fe5fde182abe19e1983c8f67a0a27d0c191ea9ccd212f
support profile SHA-256: 9e8dbfe1edf10835bd2138f237dcc917b65dc1f44f39bc26ff221da4d6aaefab
typed vocabulary SHA-256: 960c1c1d68dea56786b0e196c5fc772b298fa16db168a81ca6c6d36c60c54704
public mask digest: 269eaba783a8c8ef7b11488cd1c1bf7d9ec15b7ab9b91aefeb5ba565565cfd05
reward digest: ef3914ce85d8c820cd02cef18de4dbe52460c7ddee70cfd615ef7538a8d50d66
```

## Final accelerator results

### Mechanics and determinism

- 222/222 exact-source CUDA tests passed.
- No-op: tick 6000, overtime/tiebreak, digest
  `d14d2c7b5d41fed9784b521c9ee31c27b7d9a10903954dbf792abf73cd0c4226`.
- First-legal: tick 3600, regulation crown, winner 1, digest
  `0430c8f45ab028d590bbdb293ff25dd3f936ec172aa6f9bbd7af786e83981fc1`.
- Two exact replays per policy; all rows native/committed; zero fallback.

### Throughput

```text
batch/capacity: 128 / 128 entities / 128 effects
trial row-ticks/s: 410.708235, 410.053050, 409.637215
median row-ticks/s: 410.053050
median actor transitions/s: 820.106099
declared floor: 400 row-ticks/s
CUDA launches: 10
explicit host synchronizations: 0
trial digest: f6f5ed8e3224734aa4f7a76012ebb995ab2c689f5eb59ae57113a3bc8034fc93
```

Dense contact costs about 1.77% versus the certified pre-contact median while
keeping the launch and synchronization boundary.

### Integrated policy

- 191/191 exact integration CUDA tests passed.
- Actual `ClasherPolicy`: 494 typed tokens, 119,095 parameters.
- Recurrent hidden/cell: `[1,2,32]`.
- Training-wrapper shapes, previous actions/rewards, metadata, and public mask
  are preserved.
- Two ticks native, committed, admitted; zero fallback.

## Safety and operational state

- The live dirty main checkout, running training, model/data files, and
  checkpoints were not modified, reset, stashed, or interrupted.
- Integration exists on the isolated branch and is fresh-only; resume requests
  are rejected before model mutation.
- The A6000 pod was terminated after evidence copy; active paid pods: zero.
- The failed `f67ed3a8` capture is preserved as a diagnostic, not rewritten as
  a pass.

## Explicit non-claims

Acceptance does not claim exact Python/live-client parity, complete Evo/Hero
gameplay, independently labelled video combat, exhaustive free-running
visitation of all 66 roots, or compatible checkpoint resume. Bounded card and
navigation approximations are documented in the coverage/fidelity reports.

Within that declared scope, every original production requirement is backed by
exact-current source, terminal, CUDA, recurrent-policy, and isolated-main
evidence.
