# Public action-mask contract v2 active-sidecar migration — 2026-08-17

## Decision and scope

Only the two label-independent sidecars still named by the fresh-lineage plan
were migrated:

1. the 121,917-row balanced causal pretraining sidecar; and
2. the 12,288-row clean-history three-oracle rehearsal sidecar.

The migration did not rewrite either base corpus, either public-observation
source, any checkpoint, any historical experiment, or the permission-cleared
YouTube semantic artifacts.  The old contract-v1 files remain immutable audit
inputs and now fail closed in the current loader.

Contract v2 changes the accepted-card rule from `confidence >= 0.99` to
`confidence > 0`: a recognizer emits a nonzero card token only after accepting
the identity, while its probability remains a model input rather than a second
legality threshold.  Masks were recomputed from public observations with the
current `PublicActionMaskBuilder`; stored masks and expert labels were not used
to decide legality.

## Published artifacts

| Role | Base corpus SHA-256 | New sidecar | New SHA-256 |
|---|---|---|---|
| Fresh causal pretraining | `c84d5fbe98f9aacbccb218b73cc1f3549bd016ff9ad39187dce6f8290b1230e1` | `datasets/derived/fresh_compact_causal_v2_seed1062401/pretrain_balanced_public_mask_contract_v2.npz` | `967fb71318ade50cddd3da5a911a3d38e3c72ffdabf19e8799eeeec274025e31` |
| Clean-history oracle rehearsal | `690dc0929420a6bcdb8a6f80cfa7ccbdc17d6f3036f82935c7d8e10008695316` | `datasets/derived/structured_oracle_mix_seed1063501/mix_oracle3_12k_public_mask_contract_v2.npz` | `f2745c75cee6713e9b646ed4e1bec511f74fdc3ccab225f3bd5841b165d2db48` |

The atomic publisher manifests are:

- `reports/causal_history_ab_seed1063503/pretrain_balanced_public_mask_contract_v2_manifest.json`
- `reports/fresh_structured_causal_v1_seed1062701/mix_oracle3_12k_public_mask_contract_v2_manifest.json`

## Exact comparison with contract v1

Both legacy training sidecars contained only confidence `1.0` for accepted
nonzero hand identities.  Therefore the semantic correction intentionally
changes no mask bit in these two simulator-derived datasets:

| Check | Pretraining | Oracle rehearsal |
|---|---:|---:|
| Samples | 121,917 | 12,288 |
| Accepted hand confidences below 0.99 | 0 | 0 |
| Action masks byte-equal to v1 | yes | yes |
| `expert_action_masked` byte-equal to v1 | yes | yes |
| Masked expert labels | 2,277 | 230 |
| Every non-contract array byte-equal | yes | yes |

The only array-level difference is the scalar
`action_mask_contract_version`, which is now `2`.  This is important: current
YouTube recognizer outputs can carry accepted identities below 0.99 and do
benefit from v2, but these older simulator-derived confidence values were
binary.

## Causality and loader gates

- The builder computes each action mask before reading the expert action.
- The counterfactual-label unit test proves changing only the expert label does
  not change a mask bit.
- `expert_action_masked` is recomputed after the label-independent mask and
  remains consistent with the base label.
- Neither migration recovers or forces an expert action into the mask;
  `expert_mask_recoveries=0` and `label_conditioned_mask_mutations=0`.
- The current loader accepts both new artifacts at their full row counts.
- It rejects both old artifacts with
  `unsupported public action-mask contract 1`.

Focused validation command:

```text
PYTHONPATH=src:. uv run pytest -q \
  tests/test_rl_public_action_mask.py \
  tests/test_upgrade_public_observation_action_masks.py \
  tests/test_rl_imitation.py
```

Result: 22 passed.

## Consumption rule

All new clean-history, type-head, architecture-factorial, and fresh causal
pretraining jobs must use the two contract-v2 paths above.  Historical reports
retain their original v1 paths and hashes because rewriting completed
experiments would destroy provenance.
