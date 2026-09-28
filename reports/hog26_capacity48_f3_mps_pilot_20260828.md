# Fresh Hog 2.6 capacity-48 F3 pilot

Date: 2026-08-28

## Architecture and data

- 1,685,460 parameters
- 494 current-client tokens
- 48 entity slots
- packed global attention encoder, 128 hidden width, 3 actor layers
- model-owned structured memory, width 64
- mechanics/identity hybrid card inputs
- permutation-equivariant conditional card selector
- learned hierarchical play / wait / ability gate
- canonical lane globals and confidence-aware `causal-frame-v1` actor contract
- Hog 2.6 learner behavior collected against varied strategy/deck opponents

The pretraining corpus contains 163,291 train rows and the completely separate
held-out corpus contains 53,583 rows from 111 episodes. Both use public feature
and action-mask contract v2.

## Three-epoch imitation result

Checkpoint:
`/Users/sam/Desktop/code/clasher/checkpoints/hog26_capacity48_f3_seed1156001/e3/candidate.pt`

SHA-256:
`92c3499d5c9736d6f5a32ae264377aea97186428bff3c002a0232397dec81ed4`

Held-out 111-episode comparison:

| metric | random control | epoch 1 | epoch 3 |
| --- | ---: | ---: | ---: |
| play F1 | 0.0038 | 0.6595 | 0.7120 |
| play ROC-AUC | 0.7078 | 0.9119 | 0.9559 |
| play average precision | 0.1506 | 0.6963 | 0.7819 |
| conditional card accuracy | 0.7500 | 0.9485 | 0.9633 |
| deterministic played-card accuracy | 0.0014 | 0.6827 | 0.6080 |
| within one tile | 0.2857 on only 7 control plays | 0.0662 | 0.2079 |
| within two tiles | 0.2857 on only 7 control plays | 0.1295 | 0.3038 |
| conditional location NLL | 5.3753 | 3.8154 | 3.2310 |

The control's high raw exact accuracy is the degenerate class-imbalance result:
it predicts play on only 49 of 53,583 rows and recalls 0.19% of expert plays.
The epoch-3 policy predicts 3,735 plays, reaches 61.26% play recall at 84.98%
precision, and is therefore the first meaningful fresh candidate in this line.

Placement is still the weakest head. More supervised epochs alone should not be
assumed to solve gameplay; free-running rollout evidence remains mandatory.

## Free-running rejection gate

The original fresh-fit configuration enabled the hierarchical mode head but
left deterministic decoding on the legacy per-slot hierarchy. That produced a
clear failure: six deterministic games against `balanced` selected no action at
all (`noop_rate = 1.0`) and lost 0-6. Fresh hierarchical fits now select the
aggregate `play-gate` hierarchy by construction. A weights-identical transform
of epoch 3 changed zero tensors and left the stochastic distribution unchanged.

The aggregate play gate fixed the decoding deadlock (`placement_rate = 0.106`),
but it did not make the imitation policy competent:

- versus balanced strategy: 0-6, crown differential -1.833
- versus random: 0-6, crown differential -1.500

The stochastic legacy decoder also played cards (`placement_rate = 0.107`) but
lost 0-6 to balanced. Therefore offline imitation metrics are useful only as an
initializer gate. The fresh policy is explicitly rejected as a gameplay
candidate before RL.

## MPS Simple-Gym PPO ingress

The epoch-3 policy was loaded through the weights-only initialization gate into
the exact one-deck Hog 2.6 mirror artifact and trained for one real PPO update:

- 64 parallel battles / 128 agents
- 8 rollout decisions per agent
- 1,024 transitions
- 4 epochs, sequence batch 64, 8 optimizer steps
- 48 entities / 64 effects
- MPS eager simulator and learner
- 11.14 seconds collection, 3.85 seconds learning
- 68.31 end-to-end transitions/second
- approximate KL 0.01133, clip fraction 0.0684, no KL early stop
- play rate 0.1143, no-op rate 0.8857
- zero completed episodes at this deliberately short boundary

Update-one checkpoint SHA-256:
`07e6d1eea0dcb92095622b5756c319c2000555b040d92a30962fb08234e6d7f1`

The held-out corpus after that update remained close to the initializer: play
F1 0.7046, ROC-AUC 0.9546, within-one-tile 0.2118, and within-two-tiles 0.3060.
This is an ingress/no-catastrophic-forgetting smoke, not evidence of improved
gameplay.

## Decision

Use the weights-identical epoch-3 `play-gate` checkpoint only as the initializer
for matched CUDA batch-8 versus batch-64 learning-quality pilots. Keep the
existing Hog champion as the gameplay safety anchor. Neither the imitation
candidate nor its single PPO update is promoted as a gameplay champion.
