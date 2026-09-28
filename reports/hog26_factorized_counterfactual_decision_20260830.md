# Hog 2.6 factorized counterfactual decision

Decision: retain the distilled factorized timing checkpoint as a research
intermediate, reject both counterfactual correction screens, and do not promote
any new gameplay policy. Scale reward-backed counterfactual roots on CUDA
before another factorized correction attempt.

## Retained gameplay parent

- checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt`
- SHA-256: `28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`

This remains the gameplay and promotion baseline.

## Corpus

The final compiler retains every parent trajectory for behavior distillation,
keeps the parent action at each root, and stores interventions only in a
separate preference table. Direct discounted simulator reward is the
preference authority; checkpoint value can only break exact reward ties and
must not contradict parent/no-op.

| Split | Probes | Behavior rows | Parent plays | Accepted roots | Candidate pairs | Corpus SHA-256 |
|---|---:|---:|---:|---:|---:|---|
| train | 112 | 4,256 | 224 | 48 | 336 | `a5e8c8ab908ab57913355ecddd3311c00c41a739ddeefb7180bdcead38659ae3` |
| held-out | 56 | 2,128 | 112 | 23 | 161 | `3e1a75b38a627b72063a204bfdb5ba2eedc227b16fa613d7561a2c495897862c` |

Both splits cover warmups 8/20/40/80 and all seven stationary opponent styles.
No 80-decision root cleared the direct-reward 0.02 correction margin; those
trajectories remain behavior evidence. Twelve early random probes were
regenerated under common-quantile opponent randomness. The old/new hash audit
is `reports/hog26_random_contract_regeneration_seed1198101.json`.

## Timing distillation

The hazard head was removed and only `hierarchical_mode_gate` was trained to
reproduce parent play/wait decisions. Overall accuracy alone was insufficient:
publication required at least 85% exact action accuracy, 60% play recall, and
90% wait accuracy on the replay-disjoint split.

- selected epoch: 43/48
- exact action accuracy: 94.173%
- play recall: 75.893%
- wait accuracy: 95.188%
- play precision: 46.703%
- checkpoint SHA-256: `f4920a68a58d55df46026e646090fd3affd5889990f037cedfa84e0b35910bc4`
- report SHA-256: `ed5c8c447784867782cbab3371ec80803cac18c93e1663265eee7bd58b5c2d0b`

This checkpoint passed the offline distillation gate. It is not promoted
gameplay evidence because it intentionally disagrees with roughly 5.8% of
held-out parent actions and has not passed a game matrix.

## Counterfactual correction screens

The initial distilled policy had 0/89 corrective preferences, 45/45 safety
preferences, and a mean corrective margin of -10.375 logits.

Screen 1 used counterfactual coefficient 0.1 for 12 epochs. Timing-only,
timing+card, and full timing+card+tile arms all retained 0/89 corrective
accuracy.

Screen 2 used coefficient 1.0 for 40 epochs and reduced root behavior weight to
0.1. All three arms again retained 0/89 held-out corrective accuracy while
safety stayed 45/45. Final corrective margins were approximately -9.85
(timing), -9.75 (card), and -9.53 (full). No checkpoint was published.

The stronger screen reduced training preference loss without transferring to
held-out roots. This is evidence of root-specific overfitting from 48 accepted
training states, not evidence that a still larger coefficient is appropriate.

## Performance correction

The probe originally simulated the identical warmup once per candidate branch.
`SimpleGymRuntime.fanout_from_` now transfers one exact B=1 runtime row into the
candidate batch using the same complete mutable inventory as selective reset.
Actor, critic, legal mask, mutable state, and eight subsequent ticks are exact.
A real 40-decision smoke fell from roughly 4-5 minutes under the old path to
about 2.8 minutes under one-row warmup. Random opponents now use one common
quantile per decision across branches.

## Next gate

Do not continue tuning this 48-root corpus. Generate at least an order of
magnitude more reward-backed roots on the CUDA Simple Gym, stratified by game
phase, opponent, and parent play/wait state. Keep a replay-disjoint root split.
Then rerun the same timing/card/full factorial and unchanged offline gates.
Only an offline winner proceeds to paired gameplay and the full 56-game-per-arm
promotion matrix against the retained parent.
