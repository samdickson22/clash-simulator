# Hog 2.6 stochastic-behavior repair decision

## Decision

Reject unit-temperature and temperature-only PPO collection from the retained
Hog 2.6 parent.  Admit a bounded competence-stage retry only with the model's
recurrent play-hazard gate enforced during stochastic collection and PPO, at
sampling temperature 0.1.

The retained parent is
`/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt`
(SHA-256 `28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`).

## Evidence

The original matched audit found deterministic play competent enough to screen
but ordinary stochastic sampling catastrophic.  The first temperature sweep
then rejected every flattened-temperature arm: all seven stochastic arms went
0-8.  Cooling flattened joint logits either sprayed placements or collapsed to
no-op because it distorted the intended play/card/tile factorization.

A second sweep independently tempered play/wait, card slot, and tile factors.
Every stochastic arm again went 0-8.  This proved that factorization alone was
not the missing behavior contract.

Source audit then found the exact mismatch: the checkpoint has
`play_hazard_enabled=true` and `deterministic_hierarchy=hazard`.  Deterministic
inference integrates a recurrent hazard accumulator and uses it as a hard
play/no-play gate.  The stochastic path computed the same gate but ignored it
when sampling.

The final matched screen sampled only within the recurrent gate:

| arm | W-L | crowns/game | placement rate |
|---|---:|---:|---:|
| deterministic | 4-4 | +0.625 | 7.075% |
| gated T=0.50 | 0-8 | -1.500 | 7.085% |
| gated T=0.25 | 2-6 | -1.000 | 7.082% |
| gated T=0.10 | 4-4 | +0.125 | 7.094% |
| gated T=0.02 | 4-4 | +0.375 | 7.099% |

Temperature 0.1 retains the deterministic win count and cadence while leaving
more conditional card/tile exploration than 0.02.  Eight games are a behavior
admission screen, not a promotion claim.

Raw evidence:

- `reports/hog26_sampling_temperature_seed1192401.json`
- `reports/hog26_hierarchical_sampling_temperature_seed1192501.json`
- `reports/hog26_timing_aligned_sampling_temperature_seed1192601.json`
- `reports/hog26_hazard_gated_sampling_temperature_seed1192701.json`

## Implementation contract

- The selected temperature is persisted in Simple backend metadata.
- Rollout sampling, stored old log probabilities, PPO new log probabilities,
  entropy terms, and anchor-policy KL all use the same tempered distribution.
- When the play-hazard head is enabled, collection and PPO recomputation use the
  same recurrent gate.  A gate-on decision has probability only on legal
  placements; gate-off has probability only on legal wait/ability actions.
- Temperature 1 without a hazard gate preserves the historical joint
  distribution exactly.
- Python backend use of the Simple-only CLI option fails closed.

Focused validation: Ruff clean; 48 selected policy/Simple-backend tests passed,
5 device skips, with the unrelated pre-existing
`test_recurrent_rollout_and_ppo_update_smoke` deselected because
`concatenate_rollouts()` attempts `int(None)` on an optional rollout counter.
Dedicated tests prove exact collector/PPO log-prob agreement for both ordinary
tempered and recurrent hazard-gated sequences.

## Next gate

Run a fresh 64-decision-sequence, minibatch-8 competence stage from the retained
parent at T=0.1.  Do not reuse any unit-temperature learned checkpoint.  Inspect
the first full terminal wave and paired deterministic screen before expanding
the league or runtime.
