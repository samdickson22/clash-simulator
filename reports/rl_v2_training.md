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

## Frozen-historical curriculum

The historical phase resumed update 800 and trained one balanced learner seat per
environment against frozen update 300 and update 800 policies distributed evenly
across the 12 workers. The frozen opponents kept independent recurrent state,
previous-action/reward carry, and episode boundaries. Only learner decisions entered
PPO.

Configuration:

- updates 801-1300;
- 64 environments across 12 one-thread CPU workers;
- 64 decisions per recurrent sequence;
- MPS learner, sequence batch size 4, two PPO epochs;
- verified simulator fast path enabled;
- 2,048,000 new learner decisions, 5,181,440 total checkpoint decisions.

The trainer exited normally and wrote the 15,430,209-byte update-1300 checkpoint
with SHA-256 `7483ddec1580d0e5c13609e0305c9012cebd3bba248195a249cbe2422e043690`.
Across all 50 saved ten-update checkpoints, mean KL was 0.00637 (maximum 0.02758,
below the 0.03 target), mean explained variance was 0.957, and mean throughput was
305 learner decisions/second. KL early stopping activated on 32 checkpoints. The
last update's explained variance fell to 0.813 and KL rose to 0.0234, but both
remained bounded and the preceding checkpoints did not show a critic or optimizer
trend toward divergence.

Policy behavior changed sharply during this phase. Conditional no-op first exceeded
10% at update 980, exceeded 50% at update 1020, and ended at 75%. This is not an
inactivity collapse: an action-level audit against update 800 found 82% no-op below
4 elixir, 70% at 4-6 elixir, and only 12% at 6-8 elixir. The policy never remained
playable above 8 elixir in that sample. It learned to wait at low elixir and spend
before leaking rather than deploy immediately whenever any card became affordable.

## Update-1300 evaluation

The primary evaluation exactly reused the recorded update-800 paired seed blocks.
Each sampled deck matchup was replayed with the candidate on both seats.

| Opponent | Games | W-L | Score | Approx. 95% interval | Crown diff/game | Seat wins P0/P1 | Playable no-op range |
|---|---:|---:|---:|---:|---:|---:|---:|
| Uniform-legal random | 72 | 60-12 | 0.833 | [0.747, 0.919] | +1.542 | 31/29 | 0.706-0.768 |
| Update 300 | 72 | 61-11 | 0.847 | [0.764, 0.930] | +1.569 | 30/31 | 0.754-0.783 |
| Update 800 | 72 | 56-16 | 0.778 | [0.682, 0.874] | +1.264 | 28/28 | 0.747-0.784 |

Against the two recorded update-800 baselines, update 1300 improved from 42-30 to
60-12 versus random and from 42-30 to 61-11 versus update 300. The corresponding
crown margins rose from +0.417 to +1.542 and from +0.333 to +1.569. Both new score
intervals are entirely above the old upper bound of 0.697. Update 1300 also beats
its immediate update-800 predecessor decisively, with a perfectly balanced 28/28
split of wins by learner seat.

A second contiguous 72-game seed sequence corroborated the result: 60-12 with
+1.431 crowns/game versus random, 62-10 with +1.611 versus update 300, and 57-15
with +1.361 versus update 800. Its seat splits were 30/30, 32/30, and 30/27.
Because the random sequence shares its first 12 matchups with one primary block,
these runs are supporting replication rather than a combined 144-game estimate.

## Mixed-league pilot

A coexistence-safe 20-update pilot resumed update 1300 against equal worker shares
of random, update 800, and update 1300. It used three actor workers while a separate
RoadForge diagnostic retained its CPU allocation. The pilot added 81,920 learner
decisions and remained numerically bounded, ending with KL 0.0059 and explained
variance 0.971, but nearly every update triggered minibatch KL stopping.

Checkpoint 1320 failed the promotion gate on 24-game paired safety blocks. Versus
random it went 17-7 with +1.250 crowns/game, below update 1300's matched 20-4 and
+1.667. Versus update 800 it went 15-9 with +0.750, below update 1300's 16-8 and
+0.958. Most importantly, it lost directly to update 1300 by 9-15 with -0.542
crowns/game. Update 1320 is rejected and update 1300 remains champion.

The pilot also exposed a resume-control bug: loading AdamW state restored the old
learning rate after parsing a new `--learning-rate`. Resume now preserves optimizer
moments while explicitly applying the requested run learning rate. The next pilot
uses 1e-4 rather than 2.5e-4 before any long league allocation.

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

Promote update 1300. The large, seat-balanced fixed-anchor gains and the elixir-bucket
audit outweigh the single noisy final critic batch; rolling back solely because the
policy waits would discard a validated strategic improvement.

The next phase should be a short staged league rather than another 500-update fixed
pool. First rerun a 20-update pilot at 1e-4 against equal worker shares of
uniform-legal random, frozen update 800, and frozen update 1300. Scale to updates
1301-1500 only if the lower-rate pilot clears direct and fixed-anchor safety checks.
Keep update 300 as an evaluation-only regression anchor because update 1300 already
dominates it. At update 1500, rerun the same 72-game paired blocks against random,
updates 300, 800, and 1300. Promote only if the candidate retains positive crown
margins and seat balance against every anchor and demonstrates a clear paired edge
over update 1300. Otherwise retain update 1300 and change the opponent mixture
before spending more transitions.

After promotion, add the new champion to the frozen league and repeat in 100-200
update stages. This mixes an exploratory anchor, a pressure-heavy historical policy,
and the current strategic champion while preventing a long run from silently
specializing to one fixed pair of opponents.
