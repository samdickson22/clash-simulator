# Recurrent V2 RL training report

## Architecture

The primary policy is a 1,266,468-parameter entity-spatial recurrent actor-critic:

- public actor observations contain distinct visible entity tokens, own hand/cycle,
  arena state, and no privileged enemy hand or elixir information;
- the actor uses a 96-wide entity Transformer, 192-wide LSTM memory, hierarchical
  action-type masking, and card-conditioned tile cross-attention;
- the critic has a separate privileged entity encoder with full hidden state;
- auxiliary heads predict opponent hand membership and elixir from recurrent
  public-state memory;
- recurrent PPO uses 64-step truncated BPTT, clipped policy/value losses, GAE,
  entropy regularization, KL early stopping, and checkpointed optimizer state.

On Apple Silicon, persistent CPU workers own independent simulators and recurrent
actor state while MPS performs complete PPO sequence updates.

## Pure self-play phase

Pure symmetric self-play trained through update 300, or 1,085,440 decisions.
It learned to act whenever a non-noop action was legal, but fixed-baseline strength
remained statistically flat.

| Checkpoint | Decisions | Random W-L | Score | Crown diff/game | Noop when playable |
|---|---:|---:|---:|---:|---:|
| Update 0 | 0 | 13-11 | 0.542 | +0.208 | 0.463 |
| Update 40 | 20,480 | 11-13 | 0.458 | +0.167 | 0.054 |
| Update 100 | 266,240 | 12-12 | 0.500 | +0.167 | 0.002 |
| Update 300 | 1,085,440 | 13-11 | 0.542 | +0.083 | 0.001 |

All rows use the same 24-game paired seed set beginning at seed 4101. Update 300
also went 12-12 against initialization with -0.042 crowns/game. These results
showed that latest-vs-latest co-adaptation was not producing measurable progress.

## Stationary-random curriculum

The next phase assigned one learner-controlled seat per environment, alternating
seats across environments, against a stationary uniform-legal opponent. PPO stores
only learner-generated decisions; opponent actions never enter the policy loss.

Configuration:

- resumed update 300;
- updates 301-800;
- 64 environments across 12 one-thread CPU workers;
- 64 decisions per recurrent sequence;
- MPS learner, sequence batch size 4, two PPO epochs;
- verified simulator fast path enabled;
- 2,048,000 new learner decisions, 3,133,440 total checkpoint decisions.

Checkpoint 800 completed normally. Its final update had explained variance 0.948,
KL 0.0050, all 32 optimizer steps, 257 transitions/second, and zero conditional
no-op. Across the phase, measured throughput was generally 255-360 decisions/second
depending on KL early stopping.

The 50 saved ten-update checkpoints provide a broader stability audit: mean KL
was 0.00341 (maximum 0.00840), mean explained variance was 0.956 (minimum 0.866),
mean throughput was 287 decisions/second, and 14 checkpoints recorded a safe KL
early stop. Conditional no-op averaged 0.004 and was zero at each of the final six
saved checkpoints. There is no evidence of optimizer divergence or critic collapse.

## Update-800 evaluation

Expanded evaluation used three independent 24-game paired seed blocks, replaying
each deck matchup with the candidate on both seats.

| Opponent | Games | W-L | Score | Approx. 95% interval | Crown diff/game | Seat wins P0/P1 |
|---|---:|---:|---:|---:|---:|---:|
| Uniform-legal random | 72 | 42-30 | 0.583 | [0.469, 0.697] | +0.417 | 21/21 |
| Update 300 | 72 | 42-30 | 0.583 | [0.469, 0.697] | +0.333 | 21/21 |

The intervals still narrowly include 0.5, so this is directional evidence rather
than final statistical proof. However, the identical 42-30 records against two
different opponents, positive crown margins, and exact seat balance show that the
stationary anchor broke the earlier plateau without introducing a seat exploit.

## Throughput experiments

Larger MPS sequence batches were counterproductive because padded entity attention
became memory-bandwidth-heavy:

| Configuration | Optimizer steps | Decisions/sec |
|---|---:|---:|
| Batch 4, three epochs | 48 maximum | about 210-225 |
| Batch 8, three epochs | 24 | 212 |
| Batch 16, three epochs | 12 | 132 |
| Batch 4, two epochs | 32 maximum | about 250-365 |

The chosen batch-4/two-epoch configuration is faster without changing model size
or shortening recurrent context.

## Next curriculum decision

Do not continue training solely against random. The next phase mixes frozen update
300 and update 800 snapshots, keeps learner seats balanced, and evaluates against
both anchors. Frozen V2 opponents have independent recurrent/action/reward carry,
are distributed round-robin across persistent workers, and never enter the learner
PPO loss. A full-size smoke measured 337 decisions/second with safe KL stopping.
This preserves a stationary target while increasing opponent quality and reducing
random-policy overfitting. A later league should mix random, historical, and
current-policy opponents, with promotion based on paired win/crown results rather
than training loss.
