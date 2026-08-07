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

## Champion-weighted follow-up

The next staged challenger resumed update 1400 for 100 updates against a pool
weighted 50% to frozen update 1400, 25% to frozen update 1300, 12.5% to random,
and 12.5% to update 800. Eight one-thread actor workers represented those weights
exactly. The phase added 409,600 learner decisions at 1e-4 and ended at 6,000,640
total decisions.

The trainer recorded exit status zero after writing a loadable 15,430,657-byte
update-1500 checkpoint with SHA-256
`86f5c57e84ecaf217dfa9e2f74e929c2536733b68fba2ac6f2b1899b5d6a44ef`.
Across all 100 updates, mean KL was 0.00384 (maximum 0.01481), mean explained
variance was 0.930 (minimum 0.860), and mean throughput was 278 learner
decisions/second. KL early stopping activated on 42 updates. Conditional no-op in
training stayed between 0.662 and 0.810. The final batch had KL 0.00249 and explained
variance 0.867. These measurements are bounded: the failed gameplay gate is not an
optimizer or critic divergence.

## Update-1500 evaluation

The evaluation reused the same three paired 24-game blocks per opponent as the
update-1400 gate.

| Opponent | Games | W-L | Score | Approx. 95% interval | Crown diff/game | Seat wins P0/P1 | Playable no-op range |
|---|---:|---:|---:|---:|---:|---:|---:|
| Uniform-legal random | 72 | 51-21 | 0.708 | [0.603, 0.813] | +1.000 | 26/25 | 0.916-0.928 |
| Update 300 | 72 | 49-23 | 0.681 | [0.573, 0.788] | +0.833 | 23/26 | 0.921-0.949 |
| Update 800 | 72 | 52-20 | 0.722 | [0.619, 0.826] | +0.958 | 22/30 | 0.921-0.948 |
| Update 1300 | 72 | 36-36 | 0.500 | [0.385, 0.615] | +0.014 | 15/21 | 0.910-0.938 |
| Champion update 1400 | 72 | 36-36 | 0.500 | [0.385, 0.615] | -0.056 | 16/20 | 0.896-0.926 |

Every recorded update-1400 fixed-anchor result regressed. Wins fell from 62 to 51
versus random, 60 to 49 versus update 300, 58 to 52 versus update 800, and 39 to 36
versus update 1300. The corresponding crown margins fell by 0.583, 0.681, 0.445,
and 0.264 crowns/game. Directly against update 1400, the challenger was even on wins
and negative on crowns. Deterministic playable no-op also rose from approximately
82-85% at update 1400 to 90-95% at update 1500.

Update 1500 is rejected. The stable optimization statistics combined with broad
gameplay regression identify behavioral over-specialization toward passive waiting,
not numerical instability. Update 1400 remains champion.

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

Roll back to update 1400. Do not continue training from update 1500 or add it to the
frozen league.

The next experiment should resume update 1400 for only 20 updates with equal 25%
worker shares of update 1400, update 1300, update 800, and random, while holding the
1e-4 learning rate and all PPO settings fixed. Changing only the opponent mixture
tests the passive-specialization diagnosis without confounding it with another
optimizer change. Run the matched 24-game safety blocks at update 1420 before any
longer allocation. If playable no-op or fixed-anchor results regress again, stop and
test entropy regularization separately rather than spending another 100 updates.
Do not begin even that pilot until RoadForge confirms its next resource window.

## Equal-weight mixture diagnostic

After RoadForge cleared the resource window, the diagnostic resumed update 1400
for 20 updates with exactly 16 of 64 environments assigned to each of update 1400,
update 1300, update 800, and random. It added 81,920 learner decisions and exited
normally at 5,672,960 total decisions. The update-1420 checkpoint SHA-256 is
`a69efd75ba615a58c6dddec2df2c4f4a900cb55e33ed122be13516da33f603ae`.

Across all 20 updates, mean KL was 0.00319 (maximum 0.00763), mean explained
variance was 0.937 (minimum 0.893), mean throughput was 276 decisions/second, and
five updates stopped early on KL. Conditional no-op stayed between 0.692 and 0.805.

The matched 24-game safety blocks improved in every comparison:

| Opponent | Update 1420 | Crown diff/game | Matched update-1400 baseline |
|---|---:|---:|---:|
| Uniform-legal random | 23-1 | +2.250 | 21-3, +1.583 |
| Update 300 | 21-3 | +1.792 | 18-6, +1.333 |
| Update 800 | 21-3 | +1.750 | 19-5, +1.458 |
| Update 1300 | 14-10 | +0.375 | 12-12, -0.042 |
| Champion update 1400 | 15-9 | +0.500 | direct match |

Wins were balanced by seat in each block. Deterministic playable no-op ranged from
0.829 to 0.861, close to update 1400 and far below rejected update 1500's 0.896-0.949.
This supports the opponent-mixture diagnosis, but 24 games per opponent are only a
safety gate rather than promotion evidence. Update 1400 remains champion while the
same equal-weight branch continues in another short stage before expanded evaluation.

## Equal-weight confirmation stage

The same branch continued for 20 more updates through update 1440, adding another
81,920 learner decisions and reaching 5,754,880 total. The trainer exited with status
zero and wrote a loadable checkpoint with SHA-256
`ac552b2e9d88245bc751b3cf79ad261a6d4dcb96e958a9e01c986404e22cd441`.

This stage was noisier but bounded. Mean KL was 0.00556, mean explained variance was
0.922, and mean throughput was 308 decisions/second. Twelve of 20 updates stopped
early. One update briefly reached KL 0.03075 and was stopped after 15 optimizer steps;
the final update recovered to KL 0.00643 and explained variance 0.925. Across the full
40-update equal-weight branch, mean KL was 0.00438, mean explained variance was 0.929,
and training-time conditional no-op stayed between 0.692 and 0.811.

The matched safety blocks did not confirm update 1420's gains:

| Opponent | Update 1440 | Crown diff/game | Update 1420 | Champion-1400 baseline |
|---|---:|---:|---:|---:|
| Uniform-legal random | 22-2 | +2.042 | 23-1, +2.250 | 21-3, +1.583 |
| Update 300 | 19-5 | +1.333 | 21-3, +1.792 | 18-6, +1.333 |
| Update 800 | 18-6 | +1.292 | 21-3, +1.750 | 19-5, +1.458 |
| Update 1300 | 10-14 | -0.250 | 14-10, +0.375 | 12-12, -0.042 |
| Champion update 1400 | 12-12 | +0.083 | 15-9, +0.500 | direct match |

Deterministic playable no-op rose to 0.895 and 0.896 against updates 1300 and 1400.
The branch therefore reproduces the passive trend after only 40 updates, despite its
strong random result. Update 1440 fails the confirmation gate, and expanded promotion
evaluation is not warranted. Update 1420 remains an informative diagnostic rather
than a promoted checkpoint because its single safety block did not replicate.

Stop the equal-weight branch and retain update 1400 as champion. The next controlled
experiment, if training resumes, should restart from update 1400 with the equal pool
and change only entropy regularization for a 20-update pilot. Re-check RoadForge
coordination before launching it even while RoadForgeSSD remains disconnected.
