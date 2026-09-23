# Oracle label-quality audit: stable evaluated root candidates

Date: 2026-08-09 (America/Los_Angeles)

Branch/worktree: `codex/simulator-throughput-f872` at base commit
`5ccff6397a5dca782c6ed32d19b4d4f445e86b85`. The worktree was intentionally
dirty before this audit and was not reset, stashed, cleaned, merged, or pushed.

## Machine and scope

- Apple M4 Pro, 12 physical/logical cores, 24 GiB RAM
- Darwin 25.5.0 arm64
- Python 3.12.13 via `uv`
- All new probes were single-process CPU-only. No model fitting, MPS/GPU work,
  or multi-worker corpus collection ran.
- Fixed policy-state seed: 7401
- Behavior checkpoint:
  `/Users/sam/Desktop/code/clasher/checkpoints/fresh_v1_control_type_entropy_anchor_l2_0005_lr1e4/policy_v2_update_000240.pt`
- Planner: depth 6, 32 simulations, 64 sampled actions, 8 ticks per tree step,
  defense-v2 reward, planner seed `7401 + 7919`.

## Corpus diagnosis

The authoritative corpus contains 40,000 labels. Although 37,318 labels
(93.295%) are no-op, 37,176 states (92.940%) have no legal placement or ability.
Those forced-only states have exactly zero masked cross-entropy and zero gradient.
Among the 2,824 states with a playable non-noop action, only 142 oracle labels
(5.0283%) are no-op. The aggregate no-op rate therefore does not diagnose a
planner preference for waiting.

Evaluating the exact update-240 control and rejected three-epoch checkpoint over
the full corpus with the fitter's reset-memory input construction exposes the
nontrivial subset:

| checkpoint | all exact accuracy | playable exact accuracy | playable type accuracy | playable loss |
| --- | ---: | ---: | ---: | ---: |
| update-240 control | 93.1175% | 2.5142% | 27.7266% | 9.43394 |
| three-epoch DAgger | 93.5825% | 9.1006% | 70.6091% | 4.82148 |

The all-state accuracy is dominated by forced actions. Future fit/evaluation
manifests should always publish playable-only count, exact accuracy, hierarchical
action-type accuracy, and loss. Forced-only samples may be retained for schema
completeness, but should not be counted as evidence of expert imitation quality.

## Root-action defect

The baseline resamples a root action subset in every simulation and then samples
another fresh subset for the final greedy decision. Untouched Beta(1,1) arms in
that final subset are eligible to beat evaluated arms. On 20 matched update-240
policy states (25 playable labels), 10 selected labels (40.0%) had never been
simulated at the root. The final subset contained only 4.96 visited candidates on
average out of 64.

The candidate samples one root subset per player, reuses it across all simulations,
and restricts the final greedy choice to arms that received an update. It remains
card-agnostic and uses only the existing legal-action array and bandit evidence.
The legacy/default mode is unchanged unless `stable_root_candidates=True`.

## Matched label-distribution A/B

Forty fixed update-240 policy states yielded 80 labels, of which 47 were playable.

| mode | wall time | states/s | playable no-op | playable action-type distribution |
| --- | ---: | ---: | ---: | --- |
| baseline | 25.2484 s | 1.5843 | 5/47 (10.638%) | slot0 16, slot1 1, slot2 3, slot3 22, no-op 5 |
| stable evaluated root | 22.9962 s | 1.7394 | 0/47 (0%) | slot0 19, slot1 3, slot2 3, slot3 22 |

The modes agreed on action type for 39/47 playable labels (82.98%) and on exact
spatial action for 0/47, which is expected because this is an explicit label
semantic change. The single matched timing observation is an 8.92% wall-time
reduction / 9.79% states-per-second increase, attributable to eliminating repeated
root subset sampling. Treat it as directional rather than a confidence interval.
Both modes left every input `BattleState` key unchanged.

## Delayed tactical consequence A/B

Eight fixed policy states were selected mechanically: a playable action and
defense-v2 incoming tower danger at least 0.02, with at least three decisions
between scenarios for the same player. No card identity was inspected. For each
selected label, the chosen player acted once, the opponent took no action, and no
further actions occurred. The score is the player's defense-v2 win-probability
delta versus the paired no-op clone.

| mode | mean delta after 32 ticks | mean delta after 160 ticks | positive/negative at 160 |
| --- | ---: | ---: | ---: |
| baseline | +0.0036007 | +0.0051069 | 6 / 0 |
| stable evaluated root | +0.0063609 | +0.0088999 | 6 / 0 |
| stable root + 32 leaf-settle ticks | +0.0032681 | +0.0062172 | 5 / 0 |

Stable evaluated-root selection improved the mean 160-tick paired consequence by
74.3% on this bounded tactical set and removed the baseline's one defensive no-op.
Adding 32 no-action leaf ticks reduced that improvement and increased tactical
probe planner wall time from 4.9463 s to 7.0842 s (+43.2%). Leaf settling is
therefore rejected and is not part of the source candidate. Defense-v2 already
provides card-agnostic board-value and ETA-to-tower leaf features; blindly extending
the leaf did not improve this evidence set.

## Exact port guide

The optimizer and authoritative training planner files were identical before this
candidate. Port only these changes from
`src/clasher/rl/oracle_planner.py`:

1. Add `_PlayerBandit.greedy_visited_action`, filtering to arms whose
   `alpha + beta > 2.0` and selecting the highest posterior mean with stable
   action-ID order.
2. Add constructor option `stable_root_candidates: bool = False` and store it.
3. When enabled, call `_sample_actions(root_legal[player_id])` once per player
   before the simulation loop and reuse those arrays at depth zero.
4. At final selection, reuse the same arrays and call `greedy_visited_action`;
   retain the existing random fallback only if no root arm was updated.
5. Keep the default `False` until the collector explicitly opts into the
   label-quality change.

Port the three tests appended to
`tests/test_rl_oracle_planner_exactness.py`. In the authoritative imitation
collector, thread an explicit `stable_root_candidates` field through corpus
metadata, shard configuration, corpus fingerprint, planner construction, and a
`--stable-root-candidates` CLI flag. This prevents legacy and candidate shards
from sharing a resume fingerprint.

Recommended bounded preflight after port (still no fit):

```bash
uv run python run_clasher.py imitation -- collect \
  --output datasets/oracle_probes/dagger_u240_stable_root_seed7801.npz \
  --decisions 240 --workers 1 --seed 7801 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --reward-profile defense-v2 \
  --behavior-checkpoint checkpoints/fresh_v1_control_type_entropy_anchor_l2_0005_lr1e4/policy_v2_update_000240.pt \
  --expert-probability 0 --stable-root-candidates
```

Acceptance should compare playable-only label distributions and repeat the
threatened-state consequence probe before authorizing a long corpus or any fit.

## Verification

```text
PYTHONPATH=src:. uv run pytest -q \
  tests/test_rl_oracle_planner_exactness.py \
  tests/test_rl_oracle_dagger.py \
  tests/test_rl_oracle_corpus.py \
  tests/test_rl_imitation.py
14 passed in 3.57s

uv run ruff check src/clasher/rl/oracle_planner.py \
  tests/test_rl_oracle_planner_exactness.py
All checks passed!

uv run python -m mypy src/clasher/rl/oracle_planner.py
Success: no issues found in 1 source file

git diff --check
clean
```

The existing default fixed-seed action/state hash test remains unchanged and
passes. The opt-in mode intentionally changes oracle labels, but does not mutate
the input battle state.
