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
moments while explicitly applying the requested run learning rate. The retry used
1e-4 rather than 2.5e-4 before any long league allocation.

At 1e-4, an equal-weight retry improved optimizer coverage and went 19-5 with
+1.458 crowns/game versus update 800, but still went 17-7 with +1.208 versus
random and 11-13 with -0.333 directly against update 1300. A second 20-update
pilot therefore shifted the pool to 50% update 1300, 25% random, and 25% update
800 across all 12 workers. That challenger went 21-3 with +1.833 versus random
and 19-5 with +1.292 versus update 800. Expanded direct evaluation against update
1300 was 34-38 with -0.111 crowns/game over 72 paired games, with its wins exactly
balanced 17/17 by seat. Update 1300 remains champion, but the weighted update-1320
challenger is close enough head-to-head and stronger enough on fixed anchors to
justify an 80-update continuation before another promotion gate.

## Weighted mixed-league continuation

The weighted challenger continued through update 1400 with six of twelve actor
workers assigned to frozen update 1300 and three each assigned to uniform-legal
random and frozen update 800. The full weighted run from update 1300 added 409,600
learner decisions at a fixed 1e-4 learning rate, bringing the checkpoint total to
5,591,040 decisions.

The trainer process and its tmux session closed after writing a loadable
15,430,337-byte update-1400 checkpoint with SHA-256
`6acbf7b4bd1f0dc3de221cb5d69caa5d79389a6171113e9c403cc10bc8f44b60`.
The closed session did not retain a numeric shell exit code, but no trainer or actor
process remained and the final checkpoint restored successfully for every evaluation.

Across the ten saved checkpoints from updates 1310-1400, mean KL was 0.00302
(maximum 0.00480), mean explained variance was 0.940 (minimum 0.910), and mean
throughput was 280 learner decisions/second. KL early stopping activated at only
two saved checkpoints. Conditional no-op remained bounded between 0.658 and 0.800,
and gradient norm remained between 0.221 and 0.360. The final update completed all
32 optimizer steps with KL 0.00143, explained variance 0.949, and 265 decisions/second.
There is no sign of policy, critic, or optimizer instability.

## Update-1400 evaluation

The promotion gate reused three 24-game paired seed blocks per opponent, replaying
each sampled matchup with the candidate on both seats.

| Opponent | Games | W-L | Score | Approx. 95% interval | Crown diff/game | Seat wins P0/P1 | Playable no-op range |
|---|---:|---:|---:|---:|---:|---:|---:|
| Uniform-legal random | 72 | 62-10 | 0.861 | [0.781, 0.941] | +1.583 | 31/31 | 0.818-0.829 |
| Update 300 | 72 | 60-12 | 0.833 | [0.747, 0.919] | +1.514 | 30/30 | 0.831-0.853 |
| Update 800 | 72 | 58-14 | 0.806 | [0.714, 0.897] | +1.403 | 28/30 | 0.834-0.849 |
| Champion update 1300 | 72 | 39-33 | 0.542 | [0.427, 0.657] | +0.278 | 19/20 | 0.839-0.854 |

Against the recorded update-1300 fixed-anchor baselines, update 1400 gained two
wins versus random and two versus update 800. It gave back one win versus update
300, but retained a decisive 60-12 record, +1.514 crowns/game, and exact seat
balance. On the update-1320 matched safety blocks, update 1400 tied its 21-3 random
record with a lower +1.583 rather than +1.833 crown margin, tied its 19-5 update-800
record with a higher +1.458 rather than +1.292 margin, and improved the expanded
direct result from 34-38 and -0.111 crowns/game to 39-33 and +0.278.

The direct interval still includes an even match, so update 1400 is not proven
strictly stronger in a population-level sense. It nevertheless passes the
predeclared promotion gate: positive crown margins against every anchor, nearly
perfect seat balance, no meaningful fixed-anchor regression, and a reversal of the
direct update-1300 deficit.

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

Promote update 1400 and retain update 1300 as the previous-champion anchor. The
candidate met every gate chosen before the continuation, while rollback would ignore
both its fixed-anchor retention and the seat-balanced direct reversal.

The next challenger should run only through update 1500 at 1e-4 against a league
weighted 50% to frozen update 1400, 25% to frozen update 1300, 12.5% to random, and
12.5% to update 800. Eight one-thread actor workers express that mixture exactly and
leave more machine capacity for concurrent work. Update 300 remains evaluation-only.
At update 1500, repeat the same 72-game paired gate against all four historical
anchors plus a direct update-1400 match. Promotion should again require positive
crown margins and seat balance everywhere, no meaningful fixed-anchor regression,
and a positive direct result against the reigning champion. Do not begin that heavy
run until RoadForge confirms its resource window.
