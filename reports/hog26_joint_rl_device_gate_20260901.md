# Hog 2.6 joint-RL local device gate

Date: 2026-09-01

## Decision

Do not run the equal-budget control/action-value RL campaign on the Mac mini.
Use the certified CUDA-graph path on a funded CUDA host.  The local machine
remains useful for behavior pretraining, structural tests, tiny MPS optimizer
smokes, and deterministic evaluation.

## Exact common initializer

Both RL arms start from executed-state factorized checkpoint SHA-256
`3b651bce56b036b8948eefa0f0b85611c19ac558cbd86e64bece399f23ae3cc5`.
The action-value candidate adds 14 state entries behind a zero gate; all 169
shared initial entries are bit-identical.

## MPS actor/simulator measurement

Control configuration:

- 28 Simple Gym environments;
- random plus all six strategy opponents in paired-seat league rows;
- 64 recurrent decisions per rollout, 1,792 transitions/update;
- learner and actor/runtime on MPS;
- sampling temperature 0.1;
- two PPO epochs, sequence minibatch 8, LR 1e-5.

Update 1 completed with:

- collection 198.50 s;
- learning 3.24 s;
- 8.9 transitions/s end-to-end;
- placement rate 14.1%, playable no-op 0%;
- finite KL 0.01006 and three optimizer steps before the configured KL stop;
- zero completed games in this first rollout.

The run was stopped during update 2.  No update checkpoint beyond the immutable
update-0 initializer was published.

## CPU actor / MPS learner measurement

The same control, seed, environment count, rollout length, and opponent schedule
was rerun with CPU actor/runtime and MPS learner.  Collection exceeded the full
198.50-second MPS reference without finishing update 1, so it was stopped.  No
update result or learned checkpoint was published.

RoadForge used roughly one CPU core during both measurements; the host retained
ample idle CPU capacity.  That does not explain either route's order-of-magnitude
shortfall.  Eager small-kernel simulator execution is the bottleneck.

## Required CUDA run

Run control and action-value arms from their exact matched initializers on the
same CUDA host, using default fail-closed CUDA Graph execution.  First require a
single-update throughput screen:

- exact shared pre-update rollout digest;
- zero fallback;
- native/committed execution;
- candidate throughput at least 95% of control;
- finite selected-action Q loss and policy gate;
- no behavior divergence before the initially zero Q gate is optimized.

Only a passing device screen earns the five-update matched league pilot.  Prime
Intellect currently reports no live pod and a wallet balance of -$17.23, while
the authorized school host timed out on SSH.  Those are current external compute
availability facts, not a model blocker; source and run contracts are ready.
