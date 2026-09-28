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

## Defense-v2 controlled pilot

The public bot comparison identified a tower-racing weakness in the champion's
objective. A new opt-in `defense-v2` profile adds two card-agnostic, public-state
potentials while preserving the full `objective-v1` tower potential:

```text
defense-v2 = objective-v1
           + 0.08 * remaining board-value differential
           + 0.12 * tower-danger differential
```

Board value combines deployment cost, remaining HP, max HP, DPS, and formation
size. Tower danger combines that remaining value with target eligibility,
time-to-contact, and surviving tower HP. Both are signed state potentials, so their
step deltas telescope and cannot be repeatedly collected from an unchanged threat.
Tests also prove symmetry, remaining-HP sensitivity, card-name independence, and
independence from internal target IDs. `objective-v1` remains the default and its
numeric behavior is unchanged.

After RoadForge attempt 23 released the heavy-compute window, the controlled pilot
resumed accepted update 1400 and changed only the reward profile. It retained the
exact update-1400 weighted pool (six workers on update 1300, three on update 800,
three on random), seed 23, 64 environments, 12 one-thread actors, 64-step sequences,
MPS learner, two PPO epochs, fixed 1e-4 learning rate, and all model settings. The
20 updates added 81,920 learner decisions and exited with status zero at 5,672,960
total decisions.

The 15,430,465-byte checkpoint is
`checkpoints/defense_v2_pilot/policy_v2_update_001420.pt`, SHA-256
`8835f725ac651972f1ae8def3057411bcd3a6461fe461954aad93e829e265cff`.
Across the 20 updates, mean KL was 0.00217 (maximum 0.00795), mean explained
variance was 0.929 (minimum 0.882), mean throughput was 268 learner decisions per
second, and five updates stopped early on KL. Training conditional no-op averaged
0.738, ranged from 0.679 to 0.804, and ended at 0.694. There is no sign of policy,
critic, or optimizer instability, and the passive trend did not reappear.

The safety gate reused the exact historical 24-game paired blocks: random seed
4101 and policy-opponent seed 6101. The new evaluator also records public incoming
tower danger, board-value edge, and action rate while threatened.

| Opponent | Defense-v2 update 1420 | Crown diff | Matched champion-1400 baseline | Incoming danger: challenger / champion | Playable no-op |
|---|---:|---:|---:|---:|---:|
| Uniform-legal random | 21-3 | +1.667 | 21-3, +1.583 | 0.0488 / 0.0354 | 0.815 |
| Update 300 | 19-5 | +1.458 | 18-6, +1.333 | 0.0438 / 0.0506 | 0.831 |
| Update 800 | 19-5 | +1.500 | 19-5, +1.458 | 0.0458 / 0.0453 | 0.832 |
| Update 1300 | 16-8 | +0.667 | 12-12, -0.042 | 0.0462 / 0.0641 | 0.834 |
| Champion update 1400 | 15-9 | +0.500 | direct match | 0.0501 / 0.0785 | 0.828 |

The direct wins split 8/7 by candidate seat. Update 1300 was less balanced at 10/6,
so that row needs expansion, but every matchup retained a positive crown margin.
Most importantly, incoming danger fell 28% versus update 1300 and 36% in the direct
champion matchup. The challenger did not improve the random danger metric, showing
that the new reward is not a generic metric hack.

Because previous reward is a recurrent policy input, both checkpoints were also
cross-evaluated under both reward profiles. Update 1420 produced identical actions,
records, crown margins, and behavior metrics under `objective-v1` and `defense-v2`.
Champion update 1400 under `defense-v2` exactly reproduced its historical outcome
rows, and the reverse direct match was the expected 9-15 and -0.500. The result is
therefore a training effect, not an evaluation-profile artifact.

Update 1420 passes the safety gate and warrants expanded 72-game promotion
evaluation. It is not promoted from 24-game blocks alone; update 1400 remains the
champion until that expanded gate confirms the direct and update-1300 improvements.
Do not allocate more defense-v2 training before that evaluation.

## Fresh-lineage decision

The project is early enough that continuing to patch the original tower-objective
lineage would make the reward and curriculum changes unnecessarily hard to
interpret. The next primary experiment therefore starts a new lineage, while
preserving update 1400 as the frozen incumbent and update 1420 as a defensive
diagnostic anchor. Neither checkpoint is deleted or overwritten.

The restart is a matched A/B experiment. A fixed 5,000-decision oracle corpus is
collected with `defense-v2` at both the environment and search-leaf evaluator. One
copy of the exact update-1400-sized architecture is trained on that corpus, and an
untouched copy made from the same initial weights is retained as the random-control
initialization. Imitation optimizer moments are deliberately not restored into
PPO, so the two arms differ only in model weights when online learning starts.

Each arm receives exactly 100 PPO updates (409,600 learner decisions) against a
beginner pool containing six random workers, three balanced-strategy workers, and
three reactive-defense workers. Both use the same seed, 64 environments, 12
one-thread actors, MPS learner, fixed 2.5e-4 learning rate, and `defense-v2` reward.
The simulator fast path may be enabled only after its equivalence preflight passes.

The two fresh checkpoints are then compared with paired seat-swapped games against
random, all six strategy bots, update 1400, update 1420, and each other. Selection
uses win/score, crown margin, seat balance, incoming danger, and playable no-op
rate; training reward is not a promotion metric. Only the better safe arm continues
into a PFSP league. Update 1400 remains the public champion until a later 72-game
promotion gate is passed. The complete frozen commands and seeds are recorded in
`reports/fresh_lineage_v1_plan.json`.

Before launching the restart, three exact low-risk throughput changes were ported
from the dedicated optimization worktree. Skipping unused stationary-opponent
structured observations improved the fixed one-environment random benchmark by
2.92% and the balanced-strategy benchmark by 1.47%. Reusing the already-computed
legal mask inside the strategy bot raised that strategy workload from 79.085 to
96.205 decisions/second, a 21.65% total gain over the original path, with rollout
SHA-256 unchanged at
`32ecf56d9a213e5bc96df1c60a1c55a728b80258cfbdef9b7f7940391f621c55`.

A bounded cache on the pure simulator trait-name canonicalizer improved a fixed
24-troop crowded workload by 10.59% in scalar mode and 10.06% in fast mode. Both
engines retained the exact final-state SHA-256
`eca1565466bd124dac3063fa70b62e55d42066849bdf4919bb3ae923501e49c7`.
Hoisting the acting troop's collision-plane trait out of each candidate-entity
scan added another 3.24% scalar and 3.00% fast-path gain. Together, the two
crowded-engine changes improved the original probe by 14.17% in scalar mode and
13.37% in fast mode without changing that final-state hash.
Caching the immutable data-derived hover flag at entity construction, while still
checking dynamic flight, river-jump, and leap state on every call, added another
4.35% scalar and 4.40% fast-path gain. Across the three crowded-engine changes,
the original probe improved by 19.14% in scalar mode and 18.35% in fast mode with
the same exact final-state hash.

The standard arena's exact native-grid routes are now cached as immutable tuples
by start cell, goal cell, native lane ID, and jump-height flag. Entity route state
still receives a fresh list, and arbitrary tile-cost callers continue through the
uncached generic pathfinder. In the fixed crowded probe, independently cleared
caches took 0.064876 seconds scalar and 0.068853 seconds fast on the cold battle;
warm medians were 0.024070 and 0.028102 seconds. Relative to the immediately prior
uncached medians, repeated-battle throughput improved by 181.0% scalar and 154.5%
fast, with 84 hits and 28 misses after four battles and the same exact final-state
hash. These warm microbenchmark gains should not be treated as whole-training
speedups until the production multi-worker preflight measures the route mix.

Oracle simulations now use `BattleState.clone()` instead of copying the full card
catalog for every tree simulation. The clone deep-copies player, entity, mechanic,
RNG, array-cache, and mutable card-wrapper state, substitutes an independent lazy
loader, and identity-shares only frozen `CardDefinition` objects. A six-tower
snapshot clone fell from a roughly 9.96 ms deepcopy median to 0.359 ms (27.7x).
A fixed seed-901 oracle probe fell from 114.65 ms to 53.85 ms (2.13x) and selected
the same actions `{0: 51, 1: 52}`. Mutation-isolation tests additionally verify
independent players, entities, card wrappers, mechanic lists, RNG objects, NumPy
caches, and fast-path bucket references.

These gains affect different workload layers and must not be arithmetically added;
the production multi-worker preflight will measure their combined end-to-end
effect after the shared heavy-compute window is released.

## Fresh-lineage anti-plateau continuation

The control lineage improved through update 150, reaching 88 wins in the fixed
216-game external gate, but three bounded continuations failed to exceed it.
The original-rate update 200 scored 85/216, the update-150 low-rate branch scored
82/216, and the update-200 low-rate consolidation scored 86/216. Update 150 remains
the best fresh development checkpoint; update 1400 remains the public incumbent.

The original PPO entropy term was computed over the flattened joint distribution.
For this hierarchical policy, joint entropy is action-type entropy plus expected
conditional placement entropy. Raising its single coefficient therefore encourages
both card/wait/ability exploration and placement-coordinate randomness. The trainer
now exposes separate action-type and location coefficients while keeping the old
joint-loss path unchanged when neither override is supplied. It also logs both
components. A direct construction with three equally likely action types and 100
legal locations under one type verifies type entropy `log(3)`, expected conditional
location entropy `log(100)/3`, and exact reconstruction of joint entropy.

The next bounded pilot restarts from update 150 for 20 updates. It changes only
action-type entropy from 0.01 to 0.02, keeps location entropy at 0.01, and preserves
the original learning rate, PFSP curriculum, PPO settings, seed, and architecture.
On a fixed seed-9301 probe of 16 playable update-150 states, action-type entropy
averaged 0.0955 and conditional placement entropy averaged 3.7936. Their original
coefficient-weighted logit-gradient norms were 0.00085 and 0.00128 respectively;
the proposed 0.02 type coefficient raises only the former to 0.00171. This makes
the intervention material but keeps it in the same scale as placement exploration.
It must pass the same paired external safety gate plus a direct parent match before
receiving any additional training budget.

The update-170 gate passed for continued development. Across the nine external
blocks it scored 90/216 versus update 150's 88/216, while the six-strategy subset
rose from 61/144 to 63/144 and its crown margin improved from -0.340 to -0.215 per
game. The update-1400 anchor improved from 8-16 to 9-15, defense-1420 held 8-16,
and the direct parent match was 12-12 with zero crown margin. Aggregate incoming
tower danger was effectively unchanged (0.04887 versus 0.04896), and deterministic
no-op-when-playable remained zero in every block. This is sufficient for another
bounded continuation, but not for incumbent promotion. PFSP weights are refreshed
from update 170 before continuing to update 200.

Update 200 strengthened the result: external wins rose to 95/216 and strategy wins
to 66/144. Random reached a seat-balanced 12-12, update 1400 held 9-15, defense 1420
held 8-16, and update 200 beat parent 170 by 14-10 with +0.333 crowns/game. Incoming
tower danger improved to 0.04722. External crown margin softened slightly from
-0.343 at update 170 to -0.370, though it remained better than update 150's -0.458.
The update-200 checkpoint is therefore retained as the best fresh development
checkpoint, while update 1400 remains the public champion. A bounded continuation
to update 250 uses the refreshed update-200 PFSP report and must stop for the same
matched gate.

Update 250 failed that gate and is rejected. Its six-strategy result fell from
update 200's 66/144 wins to 57 wins plus one draw; random fell from 12-12 to 11-13,
the update-1400 anchor fell from 9-15 to 8-16, and the direct parent match was only
12-12. Its aggregate external score was 0.3958 versus update 200's 0.4398. Incoming
tower danger did improve from 0.04722 to 0.04575, but crown margin was unchanged and
the outcome regression is too large to accept. Update 200 remains the best fresh
checkpoint, update 250 is preserved only as rejected evidence, and this branch stops.

A post-hoc intermediate sweep checked whether that branch overshot an earlier peak.
On a fresh seed with 12 paired games per strategy, updates 220 and 240 both scored
46/72 and update 230 scored 45/72, versus update 200's 36/72. The larger 24-game
confirmation reversed that ordering: update 220 scored 59/144 and updates 230 and
240 scored 61/144, all below update 200's existing 66/144. Update 200 is therefore
confirmed as the retained checkpoint across both seeds and gate sizes.

The next matched experiment adds frozen-parent parameter anchoring. PPO can apply
`0.5 * coefficient * ||parameters - anchor||^2` against update 200 while retaining
the existing clipped per-update objective. This avoids an invalid second recurrent
forward with mismatched hidden state and adds no simulator cost. The unanchored
update-210 and update-220 distances imply anchor-gradient norms of 0.020 and 0.030
at coefficient 0.01, material but below the observed PPO gradient scale around 0.15.
The bounded pilot restarts from update 200, changes only this coefficient, and gates
at update 220 against both update 200 and the already-recorded unanchored update 220.

At coefficient 0.01, update-220 parameter drift fell from 2.982 L2 unanchored to
0.780. The anchored policy recovered strategy performance from 59/144 to 64/144,
scored 96/216 external wins versus update 200's 95/216, improved external crown
margin from -0.370 to -0.301, and reduced incoming danger from 0.04722 to 0.04496.
Defense-1420 improved from 8-16 to 11-13, while random and update-1400 held their
records. It nevertheless trailed update 200 by two strategy wins and lost the direct
parent match 11-13. This provisionally validates anchoring but suggests coefficient
0.01 is slightly too restrictive; a matched coefficient-0.005 pilot is next.

The coefficient-0.005 pilot is the new best fresh checkpoint. At update 220 it
scores 99/216 externally and 67/144 against strategies, with random 12-12,
update 1400 at 10-14, defense 1420 at 10-14, parent update 200 at 12-12, and the
coefficient-0.01 sibling at 13-11. External crown margin is -0.301 and incoming
danger is 0.04645, both better than retained update 200. It is accepted for
continued development but not promoted over public champion update 1400.

The same-rate continuation to update 240 is rejected. It remained numerically
stable (KL 0.00091, clip fraction 0.0099, explained variance 0.956) but fell to
93/216 external wins and 62/144 strategy wins, versus update 220's 99 and 67.
It also fell from 10-14 to 9-15 against champion update 1400 and lost 11-13 to
both parent update 220 and fixed anchor update 200. Crown margin worsened from
-0.301 to -0.366 per game while incoming tower danger was essentially unchanged.
Update 220 remains the best fresh checkpoint. A matched consolidation branch
restarts from it with learning rate reduced from 2.5e-4 to 1e-4; all other
curriculum, seed, PPO, entropy, and anchor settings remain fixed.

The low-rate update 240 passes confirmation and becomes the best fresh development
checkpoint. On the original seed it scored 100/216 externally and 70/144 against
strategies, versus update 220's 99 and 67. A second matched seed scored 100/216
versus the parent's 97 and improved crown margin from -0.218 to -0.088. Across
both seeds the candidate leads 200-196 externally and 134-132 against strategies;
champion-1400 performance is tied 20-28, while defense-1420 is down only one game
at 19-29 versus 20-28. Aggregate crown margin and incoming danger both improve.
The candidate tied its parent 12-12 directly. It receives another bounded 20-update
phase at 1e-4 with refreshed strategy PFSP weights; update 1400 remains the public
champion.

The same-mixture continuation to update 260 is rejected despite stable optimization
statistics. External wins fell from 100/216 to 96/216, strategy wins fell from
70/144 to 67/144, and champion-1400 regressed from 10-14 to 9-15. Its direct parent
match was only 12-12. Update 240 remains retained. The next matched branch restarts
from update 240 and changes only league allocation: six workers use frozen policies,
including defense-1420 and a second champion-1400 slot, while six use PFSP strategy
bots. This directly tests whether additional policy safety exposure prevents the
observed regression.

The safety-heavy branch is also rejected. Strategy wins rose to 71/144, but the
external total was only 99/216; champion-1400 fell to 9-15 and defense-1420 fell
to 7-17. Direct matches against both retained update 240 and the same-mixture
update 260 were 12-12. Extra frozen-policy sampling therefore did not preserve
the relevant behavior. The next isolated branch restores the successful 4-policy/
8-strategy mixture and moves the frozen parameter anchor from stale update 200 to
accepted update 240. This tests a general rolling-anchor rule for consolidation.

Rolling-anchor update 260 is rejected at 97/216 external wins and 67/144 strategy
wins. It holds champion-1400 at 10-14 and ties both its parent and stale-anchor
sibling 12-12, but does not improve the retained checkpoint. The final isolated
consolidation test keeps the rolling anchor and all rollout settings while resetting
AdamW moments on resume. This removes inherited optimizer momentum without changing
model weights, total-transition accounting, learning rate, or curriculum.

The optimizer-reset endpoint fails decisively: 93/216 external wins, 63/144
strategy wins, champion-1400 at 8-16, and direct losses of 11-13 to both retained
update 240 and rolling-anchor update 260. Update 240 remains retained. Before ending
this PPO continuation family, the saved update-250 intermediates from every branch
are swept on a fresh matched strategy seed to detect any short-lived peak.

Safety-mix update 250 led that small sweep at 37/72 strategy wins versus retained
update 240's 35/72, but failed the full confirmation: 98/216 externally, 68/144
against strategies, champion-1400 at 8-16, and a 12-12 parent match. No saved
intermediate is accepted. The next pipeline uses DAgger rather than another PPO
micro-variant: retained update 240 generates visited states, the defense-v2 oracle
labels them, and the environment executes behavior actions. This targets the old
oracle corpus's expert-self-play distribution mismatch directly.

The imitation fitter now accepts an initial V2 checkpoint. It validates token and
entity schemas, loads the retained architecture and weights, preserves source update
and transition counters, and writes an exact pre-fit control before supervised
updates. The first policy-state DAgger corpus completed with 20,000 environment
decisions, 40,000 legal oracle labels, and 88 episodes across 12 workers. Its SHA-256
is `d36606d87e10a96f5b26e1b7f6854ed65e002fe95e3589ec53a76c421253e150`.
The three-epoch fit at 5e-5 improved held-out oracle-action accuracy from 0.93157 to
0.93517 and loss from 0.66003 to 0.34163. The saved pre-fit control is tensor-exact
to retained update 240, both new checkpoints preserve update 240 and 983,040 source
transitions, and 94 of 148 parameter tensors changed in the fine-tune. A deterministic
200-game paired-seat random gate at seed 9601 is now the acceptance test; no DAgger
checkpoint is retained before that result.

The first DAgger fine-tune is rejected. Exact five-shard execution preserved the
same 100 matchup seeds and both candidate seats while reducing gate wall time. The
fine-tune went 85-115 with -0.120 crowns/game; the untouched update-240 control
went 96-104 with -0.055 on the identical games. The corpus has 93.295% total no-op
labels, but that figure is primarily forced by elixir and deploy legality: only
7.06% of samples have a playable non-no-op action, and the oracle places on 94.97%
of those playable samples. The failure therefore concerns which card and location
the oracle selects, not simple refusal to act. A matched 480-label sweep at depths
6, 12, and 24 kept the exact behavior states fixed and produced playable-state
placement rates of 95.24%, 90.48%, and 92.86%; depth alone does not repair label
quality. At depth 6 and eight ticks per tree step, leaf evaluation still sees only
48 ticks of delayed troop consequences. More epochs on this corpus are ruled out.
Update 240 remains retained while the next iteration changes delayed-consequence
leaf evaluation and random-opponent state coverage before collecting another corpus.

A playable-only fitter was added so single-legal-action rows no longer consume
optimizer steps or dominate metrics; the old behavior remains available explicitly.
On the fixed episode split, update 240 has 3.70% validation exact-action accuracy
over 514 playable samples. The original three-epoch fit reached 8.75%; a ten-epoch
playable-only refit reached only 8.17% and screened 14-26 versus random on the first
40 seed-9601 games, below the control's 16-24. It is rejected without a 200-game
expansion. A direct random-opponent PPO branch now resumes retained update 240 for
100 updates with defense-v2, reset AdamW moments, 1e-4 learning rate, and a weak
0.001 rolling parameter anchor. This tests the actual gate while the independent
optimizer thread develops better delayed-consequence oracle labels.

The oracle audit found a concrete label defect independent of horizon. Legacy
planning sampled a different 64-action root subset in every simulation and then
sampled a new subset for final selection; 40% of sampled playable labels in the
bounded audit had never been simulated. The new opt-in stable-root mode samples
one candidate set per player, reuses it, and permits only posterior-updated arms
as labels. It removed playable no-op labels from 5/47 to 0/47, improved mean
160-tick threatened-state consequence from +0.00511 to +0.00890, and directionally
improved throughput by 9.79%. Blind 32-tick leaf settling was separately tested
and rejected. Legacy and stable fixed-seed hashes are both pinned; the collector
threads the mode through metadata and shard fingerprints so incompatible corpora
cannot resume from one another. Fifteen focused tests pass with clean Ruff/mypy.

The direct random-PPO branch was stopped after checkpoint 280. On the matched
40-game seed-9601 screen, saved updates 250, 260, 270, and 280 scored 14-26,
14-26, 13-27, and 12-28, versus retained update 240's 16-24. Crown margin also
fell from the parent's -0.350 on those games to -0.550 at update 280. No transient
checkpoint passed, so the branch is rejected rather than spending the remaining
60 planned updates. The stable-root main-branch preflight then held every behavior
state exact, removed the legacy two playable no-op labels from 42 choices, and
published a complete fingerprinted four-shard corpus. A full 20,000-decision,
12-worker stable-root corpus is now collecting with an atomic shard manifest;
a five-epoch playable-only MPS fit is queued behind it.

The full stable-root corpus completed atomically across all 12 shards. Its
SHA-256 is `90eeaebf167f35d7bf3026d1d2b620dc509ebbf3054616a26d49c4e7e9d1b538`.
Every non-label array is byte-for-byte equal to the legacy seed-7401 corpus,
including structured observations, masks, recurrent context, episode boundaries,
and behavior actions; only 2,810 of 40,000 oracle labels changed. This isolates
stable-root candidate selection from the behavior-state distribution.

Two five-epoch playable-only fits were screened: the exact objective checkpoint
has SHA-256 `db306ee206c8667d1eceb00fa6eb3e9b156cc6e170a386dedbfd60a1eba5fc35`,
and the mechanics-aware spatial-v1 checkpoint has SHA-256
`08345964047fba1e5c41418577c68b1341f95399f89ba5f0597244c6ff72d2a0`.
On the identical first 40 seed-9601 random games, both scored 16-24 with
-0.075 crowns/game. The untouched update-240 control also scored 16-24 but with
-0.055 crowns/game. Their five shard records and crown outcomes were identical,
so neither earns a 200-game expansion. Stable-root planning fixed the unvisited-arm
label defect and raised held-out type/slot accuracy, but did not improve gameplay
on the self-play behavior-state distribution. The next DAgger iteration therefore
changes the behavior matchup to stationary random opponents while retaining the
accepted stable-root planner and exact parity controls.

The stationary-behavior collector is now implemented through shared actor-only
observations and precomputed legal masks. It alternates the policy-controlled
seat by `(shard_index + episode_id) % 2`, stores only that seat, gives stationary
randomness an independent seeded stream, and fingerprints opponent mode, label
scope, seat schedule, and RNG derivation. Legacy self-play still stores two rows
per decision; stationary collection stores one. A fixed 12-decision legacy A/B
matched every stored array exactly with combined SHA-256
`4aaa6efa1294f5b6f96a227c3f6869df7f02ea74bc6d939dafcacdc3859b9c8c`.
A 24-decision stationary-random preflight resumed to the exact array hash
`7bfb7a307cb5834bf68b93f0bc9016c401af94bcffb1d56e337b3b6d7e86049a`;
changing only the opponent to `strategy:balanced` changed both the corpus hash
and fingerprint. All labels were legal. Nineteen focused tests, Ruff, and mypy
are green. The oracle still plans joint actions for both players because the
opponent action is part of every simulated rollout; omitting it would change
label semantics rather than merely remove duplicate work.

## Random-specialist capacity expansion

The retained random-opponent champion is the one-update seed-26 specialist at
`checkpoints/champion1400_random_specialist_seed26_u1401/policy_v2_update_001401.pt`.
Its fixed seed-9601 gate is 179-21 over 200 games and the disjoint seed-12001 gate
is 160-40. The seed-9601 result remains the acceptance target; none of the work
below replaces it.

A behavior corpus was collected directly from that checkpoint against stationary
random opponents. The first 40,000-row reset-state fit overfit badly. A larger
200,000-row corpus then produced 90.22% held-out exact-action accuracy, but its
reset-state student scored only 34-6 on the first 40 seed-9601 games. This exposed
a recurrent-training defect in the fitter: independently shuffled rows reset the
policy memory for every label.

The fitter now supports episode-contiguous sequence chunks. Forced single-legal-
action steps advance recurrent state while their supervised loss remains masked.
A 192-dimensional, six-head, five-actor-layer, three-critic-layer, 384-memory
student trained with 32-step chunks reached 92.46% held-out exact accuracy and
99.26% action-type accuracy. More importantly, it restored gameplay to 37-3 on
the first 40 games with +2.075 crowns/game. Its expanded contiguous gate was
177-23 with +1.755 crowns/game. That is a material repair over reset-state
distillation, but it remains two wins below the retained champion. One additional
lower-rate imitation epoch regressed to 34-6 and is rejected.

Two five-update PPO pilots tested whether the larger student could cross the
remaining gap. A global stationary-random pilot used defense-v2, 1e-5 learning
rate, and a 0.005 parameter anchor. All updates were stable (maximum KL 0.00023),
but the best saved checkpoint tied 37-3 on the 40-game screen and finished
178-22 over 200 games. A second pilot used 5e-5 and sampled the 21 known
seed-9601 loss matchups half the time. Its first update scored 37-3 with +2.15
crowns/game; later intermediates did not improve the 20-game screen, so the branch
was stopped without a 200-game expansion. The exact-loss curriculum and additional
behavior fitting are therefore rejected, while sequence-aware imitation remains
accepted infrastructure for future architecture work.

Simulator optimization continues independently in worktree `f872`. Training and
evaluation treat that Codex thread as a separate owner: exact optimizations are
integrated only from isolated commits with fixed before/after timings, deterministic
rollout hashes, and zero shadow mismatches. The retained champion stays unchanged
until a single checkpoint exceeds 179/200 on seed 9601 and confirms on held-out
seed 12001; exact 200/200 remains the persistent target.

## Outcome-verified localized policy repair

Broad dense residual fine-tuning did not cross the retained seed-9601 gate. A
128-unit adapter trained with behavior-corpus KL scored only 15-17 wins on the
first 20 games across its saved checkpoints. Adding a factorized parent-action
margin preserved sampled decisions more strongly, but its best early checkpoint
still tied the parent's 19-1 screen while leaving the original loss unchanged.

The accepted repair architecture is instead a state-similarity-gated residual.
It stores normalized actor-global plus recurrent-memory prototypes and adds learned
action-type/location residuals only inside a cosine-equivalent radius controlled
by `repair_prototype_threshold`. The selected threshold is `0.99999`; the adapter
is exactly zero initialized, has zero activation on the sampled preservation set,
and retains card-independent, shared policy logic. Focused tests prove exact
zero-initialized output parity and zero activation for a distant state.

Candidate repairs are accepted only after replay from episode reset to terminal.
This exposed a real validation defect in the earlier clone-based search: a cloned
seed-35835 branch predicted a 3-1 win, while applying the same action in a full
replay lost 1-2. Full replay found a different winning action at tick 4064. The
two remaining losses required verified multi-action plans. A balanced defensive
trajectory repaired seed 10610 with seven actions. For seed 44916, a reactive-
defense then split-lane schedule won; exact delta minimization reduced its trace
from 108 to 52 hand/cycle-dependent opening actions while retaining a 3-2 win.

The resulting single checkpoint is
`checkpoints/parent26_repair_prototype99999_complete_cpu_seed8824/policy_v2_repair_step_0300.pt`
with SHA-256
`7d419f4de77951deb5fa2519b4e9396fc87db2ae1b2426f7e10d7fa5d38e0926`.
It contains 78 CPU-captured prototypes, reached 100% repair accuracy with zero
sampled preservation disagreement, and uses no dense repair adapter.

The authoritative deterministic paired-seat random gate used defense-v2 and ten
20-game shards starting at seeds 9601, 19691, 29781, 39871, 49961, 60051, 70141,
80231, 90321, and 100411. The aggregate is **200-0**, with zero draws, 100 wins
from each candidate seat, 200 unique `(matchup_seed, candidate_player)` records,
and +2.110 crowns/game. Every shard names the same checkpoint and reports random
opposition. This satisfies the persistent fixed seed-9601 200/200 target. It does
not by itself establish held-out random-seed generalization; the earlier parent
remains the broader held-out reference until that separate question is evaluated.

## Held-out continuation from the repaired checkpoint

The 78-prototype checkpoint was evaluated unchanged on the disjoint ten-shard
seed-12001 block. It scored 160-40 with +1.450 crowns/game, exactly matching the
unrepaired parent's recorded held-out outcome. This confirms that the original
localized repairs did not masquerade as broad held-out improvement.

A general dense residual continuation was then tested while the entire base policy,
critic, recurrent representation, and prototype adapter were frozen. The model now
supports simultaneous dense and prototype residuals, and the dense contribution is
suppressed continuously inside verified prototype neighborhoods. A conservative
40,960-transition sweep at an annealed effective rate of 5e-6 preserved the first
20 fixed and held-out games exactly but gained nothing. A further 81,920 transitions
at a constant 5e-5 lost one or two fixed games at several checkpoints without
flipping any of the three held-out losses. Six independent one-update residual runs
at 2e-4 reached the same conclusion: no held-out loss flipped, and five of six
damaged the ten-game fixed screen. Blind residual PPO is therefore rejected rather
than extended.

Outcome-verified continuation found full-from-reset single-action wins for held-out
seed 12001/player 1 and seed 16037/player 0. Seed 13010/player 1 resisted all 24
ranked single-action replays and 496 two-action combinations. The repair fitter was
extended to append prototypes to an existing checkpoint. It copies the prior rows
exactly, gradient-freezes their deltas, and trains only new rows. The retained
checkpoint is
`checkpoints/parent26_repair_prototype99999_plus_heldout2_lr01_seed8841/policy_v2_repair_step_0300.pt`
with SHA-256
`789cd5676622f2d60b4e0247ae096adedea0f29649702876be26542c07e0d0f8`.
It contains 80 prototypes; all first 78 prototype vectors and deltas are tensor-
identical to the 200-0 parent, and every non-adapter tensor is unchanged.

The complete fixed seed-9601 gate remains **200-0**, 100 wins from each seat, at
+2.110 crowns/game. The complete disjoint seed-12001 gate improves from 160-40 to
**162-38**, with zero draws, 79 player-0 wins, 83 player-1 wins, and +1.485
crowns/game. The first held-out shard improves exactly from 17-3 to 19-1 while all
other held-out shard win/loss counts remain unchanged. This is a real deterministic
outcome improvement with no fixed-gate regression, but it is still localized repair
on an observed held-out set rather than evidence of population-level random-seed
generalization.

A second continuation batch audited six more disjoint losses. Five had no verified
single-action win among their 24 best proposals; seed 26127/player 0 had no eligible
captured danger state. Seed 32181/player 0 did have a full-reset verified win, so
exactly one more prototype was appended. The new retained checkpoint is
`checkpoints/parent26_repair_prototype99999_plus_heldout3_lr01_seed8842/policy_v2_repair_step_0200.pt`
with SHA-256
`fc5aa2e613df327d832c5e526f6fe4d70a8484ebbb06c295e11c620a76b5e087`.
It has 81 prototypes, preserves all first 80 prototype vectors and deltas exactly,
and changes no non-adapter tensor. A complete replay again holds the fixed gate at
**200-0** with +2.110 crowns/game, while the held-out gate improves to **163-37**
with +1.505 crowns/game (80 player-0 wins and 83 player-1 wins). Every unaffected
held-out shard retained its exact prior win/loss count; only the seed-32181 shard
improved from 18-2 to 19-1.

## Fresh-block continuation from the 81-prototype checkpoint

The 81-prototype checkpoint was next evaluated on a third, previously untouched
ten-shard random block beginning at seed 200001. It scored **165-35**, with zero
draws, 80 wins as player 0, 85 wins as player 1, and +1.595 crowns/game. This is
slightly stronger than the prior 163-37 held-out block and supplies independent
evidence that the repaired anchor's random-opponent performance was not confined
to the two earlier evaluation ranges.

Six losses spanning both seats and several crown outcomes were mined with temporal,
diverse-action counterfactual search. Two produced interventions that also won when
replayed authoritatively from episode reset: seed 223208/player 1 and seed
251460/player 0. Five and three of their 24 ranked actions respectively passed the
full-reset verifier. The fitter appended exactly two new prototypes while freezing
all 81 existing prototype vectors and deltas and every non-adapter tensor.

The promoted checkpoint is
`checkpoints/parent26_repair_prototype99999_plus_fresh2_lr01_seed8843/policy_v2_repair_step_0200.pt`
with SHA-256
`ed909e137c215ad6981b72ae9c18374c183e96efae8d01f4157290e5a0b9fffc`.
It contains 83 prototypes. Tensor audit confirms the first 81 prototype vectors and
deltas are bit-identical to the source checkpoint and no non-adapter tensor changed.
The fit reached 100% repair accuracy while all sampled preservation actions agreed.

Complete deterministic replay gates show:

- fixed seed-9601 block: **200-0**, zero draws, +2.110 crowns/game (unchanged);
- prior seed-12001 block: **163-37**, zero draws, +1.505 crowns/game (unchanged);
- fresh seed-200001 block: **167-33**, zero draws, +1.620 crowns/game, improving
  exactly the two targeted shards from 16-4 to 17-3 and 14-6 to 15-5.

This checkpoint therefore replaces the 81-prototype checkpoint as the retained
random-opponent policy. As with the earlier append-only repairs, the two-win gain is
localized outcome-verified continuation rather than evidence that broad PPO has
learned a generally new defensive strategy. Further work continues on untouched
losses and on failure modes that require multi-action or representation-level fixes.

The next audit corrected the search eligibility floor for zero-crown losses. Four
previously skipped games (seeds 203028/player 1, 211100/player 0, 241370/player 0,
and 286775/player 1) produced 59, 8, 30, and 3 clone-branch wins. Authoritative
full-reset replay was unusually strong: 24, 8, 24, and 3 of each game's 24 ranked
proposals respectively remained wins. Four new prototypes were appended to the
83-prototype checkpoint with the same frozen-base protocol.

The resulting retained checkpoint is
`checkpoints/parent26_repair_prototype99999_plus_fresh6_lr01_seed8844/policy_v2_repair_step_0200.pt`
with SHA-256
`903d99fb3d20300963e37ff0401f49738e80c3d04ba85f36e8bcf46c07a8347a`.
It contains 87 prototypes. All first 83 vectors and deltas are bit-identical to
the source, no non-adapter tensor changed, repair accuracy reached 100%, and sampled
preservation agreement remained 100%.

The complete gates again preserve seed 9601 at **200-0** and seed 12001 at
**163-37**, with their crown margins unchanged at +2.110 and +1.505. The untouched
fresh block improves from the original 165-35 and the intermediate 167-33 to
**171-29**, zero draws, and +1.690 crowns/game. Each of the four newly targeted
shards gained exactly one win, and every other fresh shard retained its previous
record. The persistent research cycle therefore promotes the 87-prototype checkpoint
and continues from it.

A third continuation cycle sampled six more untouched losses. Four had clone-branch
wins and all four survived full-reset verification: seeds 226235/player 1,
255496/player 0, 258523/player 1, and 280721/player 0. Their verified top-24 counts
were 13, 24, 24, and 16. Seeds 218163/player 1 and 243388/player 0 produced no
single-action branch win and remain candidates for multi-action planning.

Four append-only prototypes produced the next retained checkpoint:
`checkpoints/parent26_repair_prototype99999_plus_fresh10_lr01_seed8845/policy_v2_repair_step_0200.pt`
with SHA-256
`50a1fa9c767cdba2e51e16a2cc4f4533638035c32a1490d12b57cd30499047d7`.
It contains 91 prototypes; all first 87 vectors and deltas are bit-identical and
every non-adapter tensor is unchanged. Complete gates remain **200-0** (+2.110)
on seed 9601 and **163-37** (+1.505) on seed 12001. The fresh seed-200001 block
improves again to **175-25**, zero draws, and +1.745 crowns/game. This is ten
deterministic wins above the original 81-prototype policy on that block, with no
observed regression on either established safety block.

## Context-gated prototype transfer

A fourth untouched 200-game block beginning at seed 400001 scored 175-25 with
+1.785 crowns/game for both the 81-prototype and 91-prototype policies, with zero
changed game records. This matched control proved that the strict `0.99999`
prototype radius preserved behavior but transferred none of the ten later repairs.

Uniform radius sweeps (`0.9999`, `0.999`, and `0.995`) changed no unseen outcome
and regressed fixed games. Actor-context-only similarity had the same failure.
Keeping the original 78 prototypes strict isolated the old seven-action plan from
the sweep, but the safe suffix still changed no unseen game through radius 0.995.
At radius 0.98, widening prototypes 79-90 together improved the first unseen shard
by one win but regressed fixed and prior-heldout screens.

Single-prototype ablation identified prototype 85 as the useful component. It alone
flipped seed 405046/player 0 from a 1-2 loss to a 3-2 win. A full audit found two
safety regressions: seed 40880/player 0 and seed 35208/player 1. Neither radius nor
delta-strength calibration separated the useful state from both counterexamples.
Spherical veto prototypes also failed because their neighborhoods overlapped the
useful state.

The accepted routing architecture adds an optional hard linear contextual gate to
the widened prototype suffix. The gate is backward compatible: checkpoints with
zero gates retain their exact state dictionaries and behavior. Prototype 85 is the
only widened repair; the other 90 remain at 0.99999. Two positive states and three
required-to-match trajectories seeded iterative counterexample fitting. The first
fit exposed three later divergences; adding them as negatives produced action-exact
convergence on the second iteration with six negative examples total.

The retained checkpoint is
`checkpoints/parent26_repair_p85_wide_lineargate_iter_seed8850/policy_v2_repair_step_0200.pt`
with SHA-256
`bdb3491da68ecb3dea917eae25b416ed02e8a73274a93a83475bf51f85e3296d`.
Complete deterministic gates show:

- seed-9601 fixed block: **200-0**, +2.110, zero changed game records;
- seed-12001 prior-heldout block: **163-37**, +1.505, zero changed records;
- seed-200001 repaired block: **175-25**, +1.745, zero changed records;
- seed-400001 routed block: **176-24**, +1.795, exactly one changed record:
  seed 405046/player 0 improves from a 1-2 loss to a 3-2 win.

This is the first routing experiment to retain all three established blocks exactly
while changing an initially unseen outcome. Because the gate subsequently used the
seed-405046 state as a positive example, a new untouched matched-control block is
still required to measure population-level transfer rather than guarded local fit.

The required fifth matched block began at seed 600001. The strict 91-prototype
anchor and the prototype-85 gated candidate both scored **160-40**, zero draws,
and +1.590 crowns/game, with the same 83/77 seat split. The gate changed one game
(seed 652469/player 1) from a 0-2 loss to a 1-3 loss, leaving both the outcome and
crown differential unchanged. Prototype 85 therefore remains safe on the measured
blocks, but its broad population transfer is not established.

To avoid selecting another repair from a small diagnostic shard, prototypes 79-90
were each widened independently to radius 0.98 and evaluated on all 200 exact fifth-
block games. Prototype 82 was the only net winner: **161-39**, +1.605 crowns/game,
changing only seed 670631/player 1 from a 1-2 loss to a 3-1 win. Prototypes 79 and
87 regressed to 157-43 and 159-41; the remaining candidates were outcome-neutral.

A complete raw-prototype-82 audit preserved the fixed block exactly at **200-0**
(+2.110), the prior block at **163-37** (+1.505), and the fourth block at **175-25**
(+1.785). It exposed one repaired-block regression: seed 251460/player 0 changed
from a 3-1 win to a 1-2 loss, reducing that block from 175-25 to 174-26. Raw
prototype 82 was therefore rejected.

The same reusable linear-gate mechanism was then fit to prototype 82. Its positive
set contains the original verified prototype and the transferred seed-670631 state.
Iterative counterexample fitting added four negative states from seed 251460/player
0, moving the first unwanted divergence from tick 176 to 848, 1520, and 2632 before
reaching full action-exact agreement. The useful trajectory remains action-exact to
the raw widened policy and wins 3-1; the guarded safety trajectory remains action-
exact to the 91-prototype anchor and wins 3-1. The candidate checkpoint is
`checkpoints/parent26_repair_p82_wide_lineargate_iter_seed8851/policy_v2_repair_step_0200.pt`
with SHA-256
`dcfb9ccd45827a5b785f9de3e172df4f2974b5e6019befeea86b7ae475899958`.
Full deterministic validation preserved the fixed block at **200-0** (+2.110),
the prior block at **163-37** (+1.505), the repaired block at **175-25** (+1.745),
and the fourth block at **175-25** (+1.785), with zero changed records in all four.
The fifth block improves from 160-40 (+1.590) to **161-39** (+1.605), changing
only the intended seed-670631/player-1 loss into a win.

A sixth untouched matched block beginning at seed 800001 scored **167-33** and
+1.565 crowns/game for both the 91-prototype anchor and the gated prototype-82
candidate, with the same 83/84 seat split and zero changed records. The guarded
checkpoint is therefore retained as a strict measured improvement over the anchor,
but broad population transfer remains unproven. Research continues with independent
full-block screening of the remaining transferable prototypes rather than treating
this sparse guarded win as a general policy solution.

The sixth-block independent screen identified prototype 86 as the strongest raw
transfer candidate. It improved seed 802019/player 1 from a 1-3 loss to a 3-1 win
and seed 888793/player 1 from a 1-2 loss to a 1-0 win, while regressing seed
858523/player 1 from a 3-1 win to a 0-1 loss. Its aggregate was **168-32** and
+1.580 versus the anchor's 167-33 and +1.565. Prototype 81 also netted one win;
prototypes 79, 87, and 89 regressed outcomes; the rest were outcome-neutral.

Raw prototype 86 was already known to regress seed 9601/player 1 and seed
12001/player 1. Its contextual gate was therefore trained with three positive
states (the original verified prototype and both sixth-block transfer states) and
three initial harmful trajectories. Iterative fitting added three later negative
states. After two counterexample rounds, both useful episodes were action-exact to
raw prototype 86 and all three harmful episodes were action-exact to the strict
91-prototype anchor. The candidate checkpoint is
`checkpoints/parent26_repair_p86_wide_lineargate_iter_seed8853/policy_v2_repair_step_0200.pt`
with SHA-256
`88541724feec2ee1064effe9327519e631eafce0303c8c95b8f5c26c339ce17c`.
It remains a candidate until complete six-block replay proves the learned boundary
does not introduce any other regression.

That complete replay rejected the first p86 gate. Although it preserved both sixth-
block wins, it regressed fixed seeds 74177/player 0 and 57024/player 0 and repaired
seed 286775/player 1. It also exposed three favorable crown-margin routes at prior
seeds 74559/player 0 and 97766/player 0 and fifth seed 655496/player 1. Adding these
full-block states made a single widened-row hyperplane nonseparable: the original
verified p86 prototype itself conflicted with later safety states.

The corrected architecture never widens or gates the original verified row. It
keeps all 91 anchor prototypes strict and appends a 92nd duplicate of p86 solely as
a transfer expert. The duplicate's positive set contains the five favorable routes;
its negative set contains the original strict prototype and all harmful routes.
This formulation converged after one counterexample round with five positives and
ten negatives. All five beneficial episodes are action-exact to the successful
first gate, while all six harmful episodes are action-exact to the strict anchor.
The new candidate is
`checkpoints/parent26_repair_p86_transfer_duplicate_lineargate_seed8855/policy_v2_repair_step_0200.pt`
with SHA-256
`3398a4120fdf7eb0f3d58608ccda8f1f6df64099a85effe9676c35d634b22580`.
It remains unpromoted pending complete six-block population replay.

The first 92-row replay preserved all five intended benefits and restored the fixed
block exactly, but still found two new negative routes across 1,200 games: repaired
seed 297874/player 1 changed from a 2-0 win to a 1-2 loss, and fourth-block seed
423208/player 0 lost one crown of winning margin. These were added to the negative
set. Two further later states from seed 423208 were discovered by counterexample
replay. The v2 duplicate gate converged with five positive and thirteen negative
states, retaining all five beneficial trajectories and matching all eight harmful
episodes to the anchor. Its checkpoint is
`checkpoints/parent26_repair_p86_transfer_duplicate_lineargate_v2_seed8856/policy_v2_repair_step_0200.pt`
with SHA-256
`c267f2a63ac5f41f0277fe451a6f2d221efa7d1598269b88301109f0f19506bf`.
Complete six-block replay is repeated from scratch before any promotion.

The repeated v2 replay is clean and strictly nonregressing across 1,200 games:

- fixed: **200-0**, +2.110, zero changed records;
- prior: **163-37**, +1.520, exactly two favorable crown-margin changes;
- repaired: **175-25**, +1.745, zero changed records;
- fourth: **175-25**, +1.785, zero changed records;
- fifth: **160-40**, +1.595, one favorable crown-margin change;
- sixth: **169-31**, +1.595, exactly the two intended loss-to-win changes.

The p86 duplicate expert is therefore validated. A composed candidate combines it
with the separately validated p85 and p82 gates in a single 92-row adapter. Rows
85 and 82 remain the two gated originals; strict p86 remains in the prefix and its
transfer duplicate is the third gated suffix row. No non-adapter tensor changes.
The composed checkpoint is
`checkpoints/parent26_repair_p85_p82_p86_triplegate_seed8857/policy_v2_repair_step_0200.pt`
with SHA-256
`ce21078a1f33e937fb58d6c82c451a59f98d6a2bd87edc5e040c025b13933821`.
It remains unpromoted until a full six-block interference audit completes.

The three-gate interference audit rejected that composition. Fixed, prior,
repaired, fourth, and fifth behaved as intended, including the p85 and p82 wins.
On the sixth block, however, p85 reintroduced seed 876685/player 1 as a win-to-loss
regression and interacted negatively at seed 895856/player 0. The composed score
fell to 168-32 versus the validated p86 expert's 169-31. The three-gate checkpoint
is not promoted.

The next candidate removes p85 entirely and combines only validated p82 with the
validated duplicate-p86 expert. It has 92 rows: all anchor rows except p82 remain
strict, p82 is the first gated suffix row, and a duplicate p86 is the second. The
checkpoint is
`checkpoints/parent26_repair_p82_p86_dualgate_seed8858/policy_v2_repair_step_0200.pt`
with SHA-256
`e9618888e9557588cce8d760419c7f150bb01a23ff72b022bf208f036b4cb225`.
No non-adapter tensor changes. A new complete six-block interference audit is
required; p85 returns to duplicate-expert redesign rather than remaining in this
candidate.

The p82+p86 six-block audit passes without regression:

- fixed: **200-0**, +2.110, zero changes;
- prior: **163-37**, +1.520, exactly two favorable margin changes;
- repaired: **175-25**, +1.745, zero changes;
- fourth: **175-25**, +1.785, zero changes;
- fifth: **161-39**, +1.610, the p82 loss-to-win plus p86 margin gain;
- sixth: **169-31**, +1.595, exactly the two p86 loss-to-win changes.

Every changed record is favorable. The p82+p86 checkpoint therefore replaces the
single p82 gate as the retained policy. A seventh untouched matched block beginning
at seed 1000001 is required to measure fresh population transfer. p85 remains
excluded until its route is rebuilt as a strict-original duplicate expert.

The seventh block revoked that promotion. Anchor and candidate both scored 160-40,
but seed 1095856/player 0 lost two crowns of winning margin (3-0 to 1-0). Component
replay isolated p82: p86 matched the anchor 3-0 exactly, while p82 alone reproduced
the 1-0 result. The p82+p86 checkpoint is therefore not retained.

p82 was rebuilt using the safer transfer-duplicate pattern. The original p82 row
remains strict in the 91-row prefix; a 92nd duplicate is the only widened/gated row.
Its positive trajectory is the fifth-block seed-670631 win. Its negatives include
the original prototype, repaired seed 251460/player 0, and seventh seed
1095856/player 0. Two later negative states were added by counterexample replay.
The resulting checkpoint
`checkpoints/parent26_repair_p82_transfer_duplicate_lineargate_seed8859/policy_v2_repair_step_0200.pt`
has SHA-256
`af3dd392dc0de11597f29dfd0169abf079ea7054fbed5f61374d15ad39ea4904`.
The useful episode is action-exact to routed p82; both harmful episodes are action-
exact to the strict anchor.

The next composed candidate keeps all 91 originals strict and appends two transfer
duplicates, p82 then p86. It has 93 rows, two independent linear gates, and no
non-adapter tensor changes:
`checkpoints/parent26_repair_p82_p86_transfer_duplicates_dualgate_seed8860/policy_v2_repair_step_0200.pt`
with SHA-256
`54a51e5c54da50044617994302c9825e6e62d13d8bab1e18d15e9f3e6c10f4c4`.
A complete seven-block interference audit is required before promotion.

The 93-row duplicate-only candidate passes all seven blocks:

- fixed: **200-0**, +2.110, zero changes;
- prior: **163-37**, +1.520, two favorable margin changes;
- repaired: **175-25**, +1.745, zero changes;
- fourth: **175-25**, +1.785, zero changes;
- fifth: **161-39**, +1.610, p82's loss-to-win plus p86's margin gain;
- sixth: **169-31**, +1.595, exactly two p86 loss-to-win changes;
- seventh: **160-40**, +1.560, zero changes.

All 1,400 replay records are nonregressing and every changed record is favorable.
This checkpoint is the new retained policy. The seventh-block p82 regression is
gone because its original row remains strict and only the appended copy is routed.
Research continues by applying the same duplicate-expert pattern to p85; the prior
three-gate composition remains rejected.

p85 was then rebuilt as a strict-original transfer duplicate. Its sole positive is
the seed-405046/player-0 fourth-block win. Negatives include the original p85
prototype, the three earlier safety trajectories, both sixth-block p85 side effects,
and its fifth-block neutral reshuffle. One linear fit separated the positive from
all seven negative states; the positive trajectory remains a 3-2 win and all six
negative episodes are action-exact to the anchor. The component checkpoint is
`checkpoints/parent26_repair_p85_transfer_duplicate_lineargate_seed8861/policy_v2_repair_step_0200.pt`
with SHA-256
`bf0bb60f9581a06a304d0410c8022f6dbe7c3f7685d1dcc118817192f1abe50e`.

A 94-row candidate appends p82, p86, and p85 transfer duplicates after the same 91
strict originals. Its checkpoint is
`checkpoints/parent26_repair_p82_p86_p85_transfer_duplicates_triplegate_seed8862/policy_v2_repair_step_0200.pt`
with SHA-256
`128581d1f37fd0147d71dd971a999a6605d6f5f7c1841d3cc2ef1c5cf1f8f9a2`.
No non-adapter tensor changes. Seven-block replay must prove the p85 win composes
without disturbing the retained p82/p86 gains.

The first three-duplicate audit again rejected p85 on untouched evidence. It added
the intended fourth-block win, but seventh seed 1014127/player 1 changed from a
1-0 win to a 0-1 loss. All other six blocks composed as intended. The 94-row v1
candidate is not promoted; the retained 93-row p82+p86 policy remains authoritative.

The seventh loss was added as p85's eighth negative state. A v2 duplicate gate
separated the fourth-block positive in one fit and made all seven harmful episodes
action-exact to the anchor. Its component checkpoint is
`checkpoints/parent26_repair_p85_transfer_duplicate_lineargate_v2_seed8863/policy_v2_repair_step_0200.pt`
with SHA-256
`1236f7c3f9af0dc874f439b0d3ddb9f267854242aa4a2b366d3d37eed1208895`.
The revised composition is
`checkpoints/parent26_repair_p82_p86_p85_transfer_duplicates_triplegate_v2_seed8864/policy_v2_repair_step_0200.pt`
with SHA-256
`fcff91fa424a9e35d3c1b0004a14c6a5c23c9573f665136344a472c6a2fcf614`.
A fresh seven-block audit is running; prior v1 results are not reused for promotion.

The v2 94-row policy passes all seven blocks. Fixed, prior, repaired, fifth, and
sixth reproduce the retained p82+p86 results exactly. Fourth improves to **176-24**
and +1.795 through only seed 405046/player 0. Seventh remains **160-40**, +1.560,
with zero changed records; seed 1014127/player 1 is restored to its 1-0 win.

Across 1,400 games the checkpoint adds four wins (p85 one, p82 one, p86 two) and
three favorable crown-margin changes, with no observed regression. It therefore
replaces the 93-row p82+p86 policy as the retained anchor. An eighth untouched
matched block beginning at seed 1200001 is the next population-transfer test.

That eighth block is exactly neutral: the strict anchor and retained 94-row policy
both score **165-35**, +1.540, with the same 82/83 seat split and zero changed game
records. The result extends the observed safety boundary but provides no additional
fresh transfer. Independent full-block screening of prototypes 79-90 continues on
the eighth population; only a net-positive prototype may enter duplicate-expert
fitting.

The complete eighth-block screen found prototype 79 at **167-33**, +1.565,
prototype 85 at **166-34**, +1.550, and the strict anchor at **165-35**,
+1.540. Prototype 79 changed five records: two losses became wins, one crown
margin improved, one crown margin regressed, and one result was outcome/margin
neutral but trajectory-different. Prototype 85 changed only seed 1204037/player
0 from a 1-2 loss to a 2-1 win. Prototypes 88 and 89 improved losing crown
margins without changing outcomes; prototypes 83 and 90 regressed one outcome
each; the remaining screened variants were outcome-neutral.

Prototype 79 was rebuilt as a strict-original transfer duplicate. Its positive
set contains only the two new held-out wins, while its negative set contains the
original verified prototype and all 19 previously observed p79 side-effect
trajectories across fixed, prior, fifth, sixth, and eighth populations. One
linear fit reproduced both positive trajectories and made every negative episode
action-exact to the strict anchor. The component checkpoint is
`checkpoints/parent26_repair_p79_transfer_duplicate_lineargate_seed8865/policy_v2_repair_step_0200.pt`
with SHA-256
`d3f10251c7c2a426d63287c189bf03af3a885d12601013eb18288dcdf37f1a9e`.

A 95-row candidate appends p82, p86, p85, and p79 transfer duplicates after all
91 strict originals. Its checkpoint is
`checkpoints/parent26_repair_p82_p86_p85_p79_transfer_duplicates_quadgate_seed8866/policy_v2_repair_step_0200.pt`
with SHA-256
`4ecf6c91ca4c6e2b9db9b8d8a434ac8ef9f42044d36f818288425f86cbe5aab4`.
No non-adapter tensor changed. On the eighth block it scores **167-33**, +1.565,
with exactly the two targeted losses becoming wins and every other record exact
to the retained 94-row policy. A fresh seven-block, 1,400-game regression audit
is required before promotion.

That audit rejected the first p79 duplicate. It preserved both eighth-block wins,
but four older records regressed: fixed seed 27763/player 0 fell from a 3-0 win
to 1-0, repaired seed 296865/player 1 fell from a 1-0 win to a 1-2 loss, fourth
seed 428253/player 0 fell from a 1-0 win to a zero-crown win, and seventh seed
1027244/player 0 fell from a 1-0 win to a 1-2 loss. The 95-row checkpoint is not
promoted. These four composition-specific trajectories are added as p79 routing
negatives before another candidate is allowed to run the population audit.

The revised p79 v2 gate separates both eighth-block wins from the original p79
prototype, all 19 raw side-effect routes, and all four composition-only failures.
The composed candidate is action-exact to the retained 94-row policy on all 23
negative episodes and action-exact to raw p79 on both positive episodes. The
component checkpoint is
`checkpoints/parent26_repair_p79_transfer_duplicate_lineargate_v2_seed8871/policy_v2_repair_step_0200.pt`
with SHA-256
`79675f0cd6f8e5eae71a2986a4b26ac361e2e3023e4bff3423af2704feecda39`.

In parallel, p85's gate was expanded to include its new eighth-block win while
preserving the original fourth-block win and all seven known harmful episodes;
its v3 component SHA-256 is
`1cd7517aaa1ebd4fbd445793d71cef6b8b31e3c323304acf40ea383557f6806d`.
Prototype 88's sole observed eighth-block crown-margin improvement was also
isolated behind a strict-original duplicate gate; its component SHA-256 is
`3f42d51bb78f0f238d76fb904f0efe54ed911830824a1f8645918e3d995973cc`.

The combined 96-row candidate is
`checkpoints/parent26_repair_transfer_duplicates_p82_p86_p85v3_p79v2_p88_seed8873/policy_v2_repair_step_0200.pt`
with SHA-256
`45c3649c63d7c204ad2bbb25ae7a9e806e3ce4e8b993385a1226040511c82dd2`.
It keeps all 91 originals strict and appends five independently gated transfer
duplicates. A fresh eight-block, 1,600-game audit is running; no intermediate
checkpoint is promoted from episode-level fitting alone.

That five-gate audit found one hidden regression and therefore rejected the
candidate. Prior seed 71532/player 0 remained a loss but fell from 1-2 to 0-2.
Component ablation proved p88 alone caused the change; p79 v2 and p85 v3 were
exact to the retained result. All other changes were favorable: three new eighth-
block wins, one eighth-block losing-margin improvement, and one repaired-block
winning-margin improvement.

Seed 71532/player 0 was added as a p88 composition negative. The v2 p88 gate is
action-exact to raw p88 on its seed-1208073 positive and action-exact to the
retained policy on the new negative. Its component checkpoint SHA-256 is
`f0b785633990f22cc41923cc3b06b0cc0a03fc81c765f16b377e802bfd3b15d9`.
The revised 96-row composition is
`checkpoints/parent26_repair_transfer_duplicates_p82_p86_p85v3_p79v2_p88v2_seed8877/policy_v2_repair_step_0200.pt`
with SHA-256
`567533b3b5f6b29f81dabccefc8b6783665762c814339691b5a4ea1664a2becc`.
A completely fresh eight-block audit is running; no v1 results are reused.

The v2 96-row policy passes all eight blocks. Fixed, prior, repaired, fourth,
fifth, sixth, and seventh are record-exact to the retained 94-row checkpoint.
The eighth block improves from **165-35**, +1.540 to **168-32**, +1.580 through
exactly three loss-to-win changes and one favorable losing-margin change. Across
all 1,600 games there are no other changed records and no regression.

This clears the random-opponent population gate. A matched baseline/candidate
screen against all six deterministic strategy opponents is next; random-only
evidence is not treated as proof of broad policy improvement.

The first strategy screen rejected broad promotion on one changed record. Five
strategies were record-exact across 200 games, but spell-control seed
1414127/player 0 worsened from a 1-1 tiebreak loss to a 1-2 loss. Component
ablation proved p79 v2 caused the regression; p85 v3 and p88 v2 were exact.

That spell-control trajectory was added as p79's 25th routing negative. The p79
v3 component preserves both positive random trajectories, all 23 prior random
safety trajectories, the strict original prototype, and the new strategy
trajectory action-for-action. Its SHA-256 is
`aace5ccca42e7968c4bf796d9e3f85dba8538b62c9ed3a68e13e61a17ca43abb`.
The revised full checkpoint is
`checkpoints/parent26_repair_transfer_duplicates_p82_p86_p85v3_p79v3_p88v2_seed8880/policy_v2_repair_step_0200.pt`
with SHA-256
`d520101ad0f286edb32f079e701c41e5292647adfc16d1f9f528dbaa0c1886b0`.
Both the eight-block random audit and six-strategy audit must be rerun from
scratch before promotion.

The v3 reruns are clean. The eight random blocks again contain only the three
new eighth-block wins and one favorable losing-margin change. The complete
six-strategy matrix is record-exact: bridge-pressure 33-7, slow-push 25-15,
spell-control 28-12, reactive-defense 25-15, split-lane 31-9, and balanced
25-15 for both retained and candidate policies. There are zero changed records
across the 240 strategy games.

The v3 96-row checkpoint is promoted as the retained cross-distribution anchor.
The next bounded experiment adds a zero-initialized dense residual outside the
protected prototype neighborhoods and trains only that residual for one
strategy-league PPO update. The retained checkpoint remains immutable and the
pilot must pass the same random and strategy safety gates before any continuation.

The one-update dense strategy-league pilot trained 4,096 transitions at about 479
transitions/second on MPS. Only `repair_adapter.*` was trainable; PPO remained
stable at KL 0.00000, clip fraction 0, explained variance +0.894, and 32 optimizer
steps. The raw dense checkpoint added two strategy wins and five favorable crown
margins, plus a fixed-block crown gain, but regressed one balanced-strategy win
from 1-0 to a zero-crown tiebreak win. It was not promoted.

A strict zero-delta safety prototype was captured at that harmful divergence.
Because prototype activation already suppresses the dense residual, the guard
restores the retained action sequence locally without altering the shared policy
or any of the seven useful dense trajectories. The guarded checkpoint is
`checkpoints/retained96_strategy_dense64_guarded_seed15001/policy_v2_update_001402.pt`
with SHA-256
`9f62646d7ebad8f413167eafe19e7eb8b0bd31d7211e42faf212cbb4aa673f69`.
Its 280-game fixed/prior/strategy screen retains all seven favorable changes and
contains zero regressions. A full eight-block random audit is required before
promotion.

The full random audit rejected the one-guard dense checkpoint. Across 1,600
games it produced 14 favorable changes but 16 regressions and two fewer net wins.
The sparse v3 policy remains retained. All 16 harmful random trajectories were
then replayed to their first divergence and added as strict zero-residual guards.
Six needed a second later-state guard; the batch converged with 22 new guards.

The resulting checkpoint is
`checkpoints/retained96_strategy_dense64_guarded_v2_seed15001/policy_v2_update_001402.pt`
with SHA-256
`e7289de5d1276029dce68531f6e89647c87ffe1afa8cc052abe5ffc997cab60d`.
All 17 harmful random/strategy episodes are action-exact to the sparse anchor,
and all 20 useful random/strategy episodes are action-exact to the trained dense
policy. A fresh 1,600-game random audit is running; the episode fit alone is not
promotion evidence.

The guarded-v2 checkpoint passes the complete audits. Across the eight random
blocks it makes exactly 14 favorable changes and zero regressions, adding six
wins: the total rises from 1,372/1,600 to 1,378/1,600. Across the six strategy
blocks it makes exactly six favorable changes and zero regressions, adding two
wins: the total rises from 167/240 to 169/240. Every other outcome and crown
count is exact to the sparse v3 anchor.

`checkpoints/retained96_strategy_dense64_guarded_v2_seed15001/policy_v2_update_001402.pt`
is promoted as the new retained policy. Its SHA-256 is
`e7289de5d1276029dce68531f6e89647c87ffe1afa8cc052abe5ffc997cab60d`.
It combines the trained dense residual with 114 strict-prefix prototypes and the
same five gated transfer duplicates. A second one-update strategy-league pilot
will use a lower learning rate and anchor to this exact checkpoint; it remains a
challenger until the same safety gates pass.

The second pilot trained 4,096 additional transitions at 2.5e-5 and about 498
transitions/second. Its quick screen added one slow-push win, but regressed a
fixed crown margin, a split-lane loss margin, and one balanced trajectory. Six
strict zero-residual guards were needed to make all three non-beneficial episodes
action-exact to the retained policy while preserving the slow-push win.

The guarded continuation is
`checkpoints/retained119_strategy_dense64_guarded_seed15002/policy_v2_update_001403.pt`
with SHA-256
`af581ba7a6f07f40e323447a9dc181aa8b247ba65e722836be99ecceb56cf119`.
It remains unpromoted pending complete random and strategy population audits.

The first complete random audit rejected that six-zero-guard candidate. It had
12 favorable changes, but also nine regressions and two fewer wins than update
1402. Recursive zero-delta fitting then exposed a structural limitation: once a
dense residual has already been promoted, suppressing the whole dense adapter
also erases the earlier retained improvement. Seed 205046 therefore repeatedly
fell back to the sparse-policy action instead of update 1402's retained action.

`scripts/fit_residual_safety_guards.py` replaces that incorrect continuation
rule. At each first divergence it stores the complete effective repair residual
from the designated reference policy. The new prototype suppresses the changed
dense adapter, but contributes the prior retained dense output plus any sparse
prototype repair needed at that exact state. This is state-based and shared;
there are no seed, card-name, or runtime episode branches in the policy.

Starting from the raw update-1403 checkpoint, residual-preserving fitting
converged in six recursive passes. It added 31 strict-prefix prototypes, for 150
total prototypes: 145 strict-prefix rows and the same five linearly gated
transfer rows. All 31 retained-policy safety/preservation trajectories and all
12 raw update-1403 beneficial trajectories are action-exact to their respective
references. The resulting checkpoint is
`checkpoints/retained119_strategy_dense64_residual_guarded_seed15002/policy_v2_update_001403.pt`
with SHA-256
`c2489f46cd2af20b78a9ab55cbce225d25bf2daf255787d942865f67285877dd`.
The stale Adam state was removed because prototype expansion changes a trainable
parameter's shape; future continuation therefore starts fresh optimizer moments.

The complete promotion audits pass. Across the eight random blocks, 1,589 of
1,600 records are exact to update 1402 and all 11 changes are favorable; there
are zero regressions and zero neutral crown reshuffles. Random wins rise from
1,378 to 1,379. Across the six strategy blocks, 239 of 240 records are exact.
The only change is slow-push seed 1419172 as player 1, improving from a 1-3 loss
to a 3-2 win. Strategy wins rise from 169 to 170, again with zero regressions or
neutral reshuffles.

The residual-guarded update-1403 checkpoint initially cleared the defined
promotion gate. An unseen ninth 200-game random block then found one added win
but also two one-crown losing-margin regressions. The provisional promotion is
therefore revoked under the zero-regression rule; update 1402 remains retained.
Two additional residual-preserving guards must pass all nine random blocks and
the strategy population before update 1403 can be reconsidered.

The ninth-block repair converged in four recursive passes with five additional
strict prototypes. The final checkpoint is
`checkpoints/retained119_strategy_dense64_residual_guarded_v2_seed15002/policy_v2_update_001403.pt`
with SHA-256
`a7674bf96724671a3734cc2273e0eddcf582c9328372a945f2d6429b6c08080b`.
It has 155 prototypes: 150 strict-prefix rows and the same five gated transfer
rows. Its checkpoint intentionally contains no stale optimizer state.

The expanded promotion audit passes. Across nine random blocks, 1,788 of 1,800
records are exact to update 1402 and all 12 changes are favorable. There are
zero regressions and zero neutral reshuffles; wins rise from 1,544 to 1,546.
Across the six strategy blocks, 239 of 240 records are exact, with only the
slow-push 1-3 loss becoming a 3-2 win. Strategy wins rise from 169 to 170.

The v2 residual-guarded update-1403 checkpoint is promoted as the retained
policy. The next holdout compares it and update 1402 against frozen updates 300,
800, 1300, and 1400 before deciding whether another PPO continuation is justified.

That learned-opponent holdout found four favorable changes and one regression.
The candidate added a win against update 800 and improved one update-1300 and
two update-1400 losing margins, but a separate update-800 win narrowed from 3-1
to 3-2. Promotion is again suspended under the zero-regression rule while a
policy-opponent-aware residual guard is fitted and the complete gate reruns.

The policy-opponent-aware fitter converged in one pass with one additional
strict prototype. The final retained candidate is
`checkpoints/retained119_strategy_dense64_residual_guarded_v3_seed15002/policy_v2_update_001403.pt`
with SHA-256
`2b94a96781cedc0fb995d903ceb872ff5c381d58eeff6460187502e54cbe6879`.
It contains 156 prototypes: 151 strict-prefix rows and five gated transfer rows,
with stale optimizer state removed.

Every complete gate was rerun from scratch. The nine random blocks again contain
1,788 exact records and 12 favorable changes, with wins 1,544 to 1,546. The six
strategy blocks contain 239 exact records and one favorable slow-push win, with
wins 169 to 170. The four frozen-policy holdouts contain 156 exact records and
four favorable changes: one added update-800 win, one improved update-1300 loss,
and two improved update-1400 losses. Frozen-policy wins rise from 107 to 108.
There are zero regressions and zero neutral reshuffles in all three populations.

Update 1403 v3 is promoted as the retained policy. A third PPO continuation, if
attempted, must use a lower learning rate, fresh optimizer moments, and this
exact checkpoint as its anchor; it remains a challenger until the same expanded
gate passes.

A one-update continuation at requested 1.25e-5 used the trainer's end-of-run
annealing floor, for an effective learning rate of 1.25e-6. It trained 4,096
transitions at 484 transitions/second with KL approximately zero, clip fraction
zero, explained variance +0.927, and stable loss components. The resulting
update-1404 checkpoint was record-exact to retained v3 across all 2,200 audited
random, strategy, and frozen-policy games. It is rejected as a behavioral no-op.

The next bounded pilot restarts from retained v3 at requested 2.0e-5, yielding
an effective 2.0e-6: between the inert 1.25e-6 pilot and the productive but
repair-heavy 2.5e-6 update-1403 step.

The midpoint pilot also trained 4,096 transitions, at 480 transitions/second,
with KL and clip fraction approximately zero and explained variance +0.905. It
crossed the behavioral threshold narrowly: one random loss improved from 0-2 to
0-1, with the other 1,799 random records exact. All 240 strategy records and 120
of the first three frozen-policy blocks were exact. Against update 1400, however,
one retained 3-1 win became a 1-3 loss. The raw midpoint checkpoint is not
promoted; a policy-opponent residual guard must preserve the random gain while
restoring that direct regression.

Residual-preserving fitting converged in one pass with four new strict
prototypes. The guarded update-1404 checkpoint is
`checkpoints/retained156_strategy_dense64_midpoint_guarded_seed15004/policy_v2_update_001404.pt`
with SHA-256
`e9c8212493f3d39e40efaef4c7647299dd099fe1616bcb072d74813c738821b0`.
It has 160 prototypes: 155 strict-prefix rows and five gated transfer rows, and
contains no stale optimizer state.

Every promotion population was rerun. Across nine random blocks, 1,799 of 1,800
records are exact to retained update 1403; the sole change improves a 0-2 loss
to 0-1. All 240 strategy and 160 frozen-policy records are exact. There are zero
regressions and zero neutral reshuffles. Guarded update 1404 is promoted as the
new retained policy.

The next bounded continuation uses the same effective 2.0e-6 rate from this
exact checkpoint and fresh optimizer moments. The modest update-1404 gain and
four-guard cost make this a final same-rate probe before reconsidering stacked
residual layers or a different training objective.

That final same-rate probe trained update 1405 from the guarded update-1404
checkpoint on another 4,096 transitions. Training remained numerically stable
at about 473 transitions/second, with KL and clip fraction approximately zero
and explained variance +0.911. Nevertheless, the complete nine-block random
gate was record-exact in all 1,800 games: zero favorable changes, zero
regressions, and zero crown reshuffles. Raw update 1405 is rejected as a
behavioral no-op, and guarded update 1404 remains the retained policy.

Further continuation will use a new zero-initialized residual stage while
freezing the accumulated dense adapter and its safety prototypes. Each stage's
future guards will suppress only that stage, so preserving a retained action no
longer requires reconstructing the complete output of every earlier dense
update. The first stacked-stage pilot remains a challenger until it clears the
same random, strategy, and frozen-policy gates.

The first 64-unit stacked-stage pilot trained one update at an effective 2.5e-6
learning rate. Its six-strategy screen was record-exact across all 240 games,
but the fixed random block exposed one severe regression and no gains: seed
23727/player 0 changed from a 3-1 win to a 1-2 loss. The raw stacked checkpoint
is rejected without fitting a guard because it has no observed benefit to
preserve. The retained guarded update-1404 policy remains unchanged.

Two further defense-v2 stage probes at effective rates 2.5e-6 and 4.0e-6 were
record-exact across matched fixed/slow-push/spell-control/balanced screens. A
1.0e-5 probe finally crossed more boundaries, but both changes were regressions:
it erased the retained slow-push seed-1419172 win and worsened balanced seed
1402019 from a 1-1 tiebreak loss to 1-2. All three are rejected. More learning-
rate search on the same objective is stopped; the next stage probe changes the
reward profile to defense-v3, which strengthens public tower-danger and exposed-
King survival credit without card, deck, lane, or crown-lead special cases.

The one-update and five-update defense-v3 stage experiments are also rejected.
Every saved intermediate had zero favorable changes on the fixed/slow-push/
spell-control/balanced screen. Updates 1405-1407 shared one fixed loss regression;
updates 1408-1409 added a second crown-margin regression. Broad PPO continuation
has therefore exhausted both the defense-v2 learning-rate axis and the defense-v3
objective axis without a promotable checkpoint.

Outcome-verified continuation moved to a previously untouched tenth random block
beginning at seed 1600001. Retained update 1404 scored 163-37. Eight close losses
were searched with full-from-reset counterfactual replay; five had verified
single-action wins. A new stage-local prototype fitter added exactly five strict
0.99999 neighborhoods. It freezes the accumulated dense adapter and all 160 base
prototypes; only the five new stage deltas train. Prototype self-weight was 1.0,
cross-weight was 0.0, and all 512 sampled preservation states had zero activation.

The fitted checkpoint is
`checkpoints/retained160_tenth_stage_repairs_seed15012/policy_v2_repair_step_0200.pt`
with SHA-256
`b99f18dffb74c1b0c7ed7c1b12f5fe9ff7cee3b0f8f06e2f158f2b34d2263b81`.
Every targeted episode wins under full reset replay. On the complete tenth block,
195/200 records are exact and precisely the five targeted losses become wins,
raising the block from 163-37 to 168-32 with zero regressions or neutral crown
reshuffles. It remains a challenger while the nine historical random blocks,
strategy population, and frozen-policy holdouts rerun.

The complete promotion audit passes. All 1,800 historical random records are
exact to retained update 1404. All 240 deterministic-strategy records and all
160 frozen-policy records against updates 300, 800, 1300, and 1400 are also
exact. Combined with the fresh tenth block, the challenger changes exactly five
of 2,400 audited games, and every change is a loss-to-win improvement. There are
zero regressions and zero neutral crown reshuffles.

`checkpoints/retained160_tenth_stage_repairs_seed15012/policy_v2_repair_step_0200.pt`
is promoted as the retained policy. Its base remains the 160-prototype guarded
update-1404 model, plus one zero-dense 64-unit repair stage containing five
strict localized prototypes. It contains no optimizer state. Further work will
continue on untouched population blocks and must preserve this complete gate.

The next outcome-verified pass used a previously untouched eleventh random
block beginning at seed 1800001. The retained stage-one policy scored 160-40.
Eight close losses were searched from full reset; six produced verified winning
single-action interventions. A second isolated 64-unit repair stage was added,
with six strict 0.99999 prototype neighborhoods and no dense residual update.
Only the new stage-local prototype deltas were trainable. The fit reached 100%
repair accuracy, retained 100% agreement on 512 sampled preservation states,
and measured zero cross-prototype activation with self-weight 1.0.

The resulting checkpoint is
`checkpoints/retained165_eleventh_stage_repairs_seed15013/policy_v2_repair_step_0200.pt`
with SHA-256
`dc6e4ea37f7bd72965cbacf360befa787868285fd3fd48663f7ed13b60d4af87`.
All six targeted episodes win under independent full-reset replay. Across the
complete eleventh block, 194/200 records are exact and precisely those six
targeted losses become wins, raising the block from 160-40 to 166-34 with zero
regressions and zero neutral crown reshuffles.

The full promotion gate was rerun against the prior retained checkpoint. All
1,800 games in the nine historical random blocks, all 200 games in the tenth
random block, all 240 deterministic-strategy games, and all 160 frozen-policy
games against updates 300, 800, 1300, and 1400 are record-exact. Across 2,600
audited games, the challenger therefore makes exactly six changes, every one a
loss-to-win improvement. It has two zero-dense 64-unit repair stages containing
five and six localized prototypes respectively, and no optimizer state.

`checkpoints/retained165_eleventh_stage_repairs_seed15013/policy_v2_repair_step_0200.pt`
is promoted as the retained policy. Further outcome-verified work continues on
a new untouched population block and must preserve this expanded gate.

A twelfth untouched random block beginning at seed 2000001 scored 162-38 under
the retained stage-two policy. Eight close losses were searched from full reset.
Four produced winning one-shot counterfactuals, but one of those four did not
survive independent replay after fitting: seed 2032289/player 0 remained a loss
with a changed trajectory. That repair and its four-prototype candidate were
rejected. The stage was refit from the three interventions that remained wins
under complete checkpoint replay.

The accepted challenger is
`checkpoints/retained171_twelfth_stage_repairs3_seed15015/policy_v2_repair_step_0200.pt`
with SHA-256
`bf30c63f13bc4f66b83a829ef53f3ee48fdd232006538ca307a0a1eb99a7cbd3`.
Its third zero-dense 64-unit stage contains three strict 0.99999 prototypes.
The fit reached 100% repair accuracy and 100% sampled preservation agreement,
with prototype self-weight 1.0, cross-weight 0.0, and zero preservation-set
activation. It contains no optimizer state.

On the complete twelfth block, 197/200 records are exact and exactly three
targeted losses become wins, raising the block from 162-38 to 165-35. All 2,200
random games from the first eleven blocks, all 240 deterministic-strategy games,
and all 160 frozen-policy games are record-exact to the prior retained model.
Across the resulting 2,800-game promotion audit there are exactly three changes,
all loss-to-win improvements, with zero regressions and zero neutral crown
reshuffles.

`checkpoints/retained171_twelfth_stage_repairs3_seed15015/policy_v2_repair_step_0200.pt`
is promoted as the retained policy. It now carries three independently gated
repair stages with 5, 6, and 3 localized prototypes. The next pass continues on
another untouched population block and inherits the complete 2,800-game gate.

The thirteenth untouched random block beginning at seed 2200001 scored 168-32.
Eight close losses were searched from full reset and seven had winning
single-action interventions. All seven remained wins under independent
checkpoint replay after fitting a fourth isolated stage. On the complete block,
193/200 records are exact and precisely those seven losses become wins, raising
the result to 175-25 with no other crown changes.

The promoted checkpoint is
`checkpoints/retained174_thirteenth_stage_repairs_seed15016/policy_v2_repair_step_0200.pt`
with SHA-256
`f6f12a8090f3359346b2e1679d277c41dba4345de91593508b1aac5a58ef0753`.
Its fourth zero-dense 64-unit repair stage contains seven strict localized
prototypes. The fit reached 100% repair accuracy and 100% sampled preservation
agreement, with self-weight 1.0, cross-weight 0.0, zero preservation activation,
and no optimizer state.

The expanded promotion audit reran all 2,400 random games from the first twelve
blocks, all 240 deterministic-strategy games, and all 160 frozen-policy games.
Every one of those 2,800 records is exact to the prior retained model. Across
3,000 audited games, stage four therefore changes exactly seven outcomes, all
loss-to-win improvements, with zero regressions and zero neutral reshuffles.
It is promoted as the retained policy; the next untouched population inherits
this complete gate.

The fourteenth untouched random block beginning at seed 2400001 scored 159-41.
Eight close losses were searched from full reset; seven produced winning
single-action interventions, including both player seats of seed 2416145. All
seven remained wins under independent checkpoint replay after fitting a fifth
isolated repair stage. The complete block contains 193 exact records and exactly
seven loss-to-win changes, raising the result to 166-34.

The promoted checkpoint is
`checkpoints/retained181_fourteenth_stage_repairs_seed15017/policy_v2_repair_step_0200.pt`
with SHA-256
`a3e84199856acb2eae395821f41a79d93255b9c09ede5330a50f236a68678dac`.
Its fifth zero-dense 64-unit stage contains seven strict localized prototypes.
The fit reached 100% repair accuracy and 100% sampled preservation agreement,
with self-weight 1.0, cross-weight 0.0, zero preservation activation, and no
optimizer state.

The expanded promotion gate reran all 2,600 random games from the first thirteen
blocks, all 240 deterministic-strategy games, and all 160 frozen-policy games.
All 3,000 inherited records are exact to stage four. Across 3,200 audited games,
stage five changes exactly seven outcomes, all loss-to-win improvements, with
zero regressions and zero neutral crown reshuffles. It is promoted as the
retained policy and the next untouched block inherits this full gate.

The fifteenth untouched random block beginning at seed 2600001 scored 172-28.
Eight close losses were searched from full reset and five produced winning
single-action interventions. All five remained wins under independent replay
after fitting a sixth isolated repair stage. The complete block contains 195
exact records and exactly five loss-to-win changes, raising the result to 177-23.

The promoted checkpoint is
`checkpoints/retained188_fifteenth_stage_repairs_seed15018/policy_v2_repair_step_0200.pt`
with SHA-256
`03c8bef71e9cec315472666a868920cd65c1f710e4a4765593e656dc3fe204f4`.
Its sixth zero-dense 64-unit stage contains five strict localized prototypes.
The fit reached 100% repair accuracy and 100% sampled preservation agreement,
with self-weight 1.0, cross-weight 0.0, zero preservation activation, and no
optimizer state.

The promotion gate reran all 2,800 random games from the first fourteen blocks,
all 240 deterministic-strategy games, and all 160 frozen-policy games. Every one
of the 3,200 inherited records is exact to stage five. Across 3,400 audited games,
stage six changes exactly five outcomes, all loss-to-win improvements, with zero
regressions and zero neutral crown reshuffles. It is promoted as retained and
the next untouched population inherits this expanded gate.

The sixteenth untouched random block beginning at seed 2800001 scored 167-33.
Eight close losses were searched from full reset and six produced winning
single-action interventions. All six remained wins under independent replay
after fitting a seventh isolated repair stage. The complete block contains 194
exact records and exactly six loss-to-win changes, raising the result to 173-27.

The promoted checkpoint is
`checkpoints/retained193_sixteenth_stage_repairs_seed15019/policy_v2_repair_step_0200.pt`
with SHA-256
`f5f2e8b2def34fccb8b6b3a46344e067dcd33e0d66f6f99c21cf7e090556ef4c`.
Its seventh zero-dense 64-unit stage contains six strict localized prototypes.
The fit reached 100% repair accuracy and 100% sampled preservation agreement,
with self-weight 1.0, cross-weight 0.0, zero preservation activation, and no
optimizer state.

The promotion gate reran all 3,000 random games from the first fifteen blocks,
all 240 deterministic-strategy games, and all 160 frozen-policy games. All 3,400
inherited records are exact to stage six. Across 3,600 audited games, stage seven
changes exactly six outcomes, all loss-to-win improvements, with zero regressions
and zero neutral crown reshuffles. It is promoted as retained. Before adding
another stage, the accumulated repair stack is compared against its pre-stack
ancestor on a genuinely untouched block to measure out-of-sample transfer.

The seven strict stages were safe but did not generalize. On the untouched
seventeenth block beginning at seed 3000001, both the stage-seven policy and its
pre-stack update-1404 ancestor scored 172-28, and all 200 terminal records were
exact. Two dense generalization pilots were rejected: the faster pilot disturbed
roughly 8-22% of sampled preservation actions, while the stronger-anchor pilot
preserved 92.6% but reached only 12.8% repair accuracy by step 400.

A broader similarity-kernel pilot at threshold 0.999 was more promising. Its
200-step checkpoint learned 32 of 39 verified repairs, retained 100% sampled
preservation agreement, and changed only one of the 200 untouched games. That
change preserved the 3-0 win at seed 3009082/player 0 and increased own left-
tower HP from 1421 to 1710. It could not replace the retained stack because it
missed seven known repairs.

The accepted architecture combines both behaviors. Per-stage prototype
thresholds keep the first seven stages at 0.99999 and append the broad 0.999
kernel as stage eight. Later broad stages can yield to earlier specific stages.
Hard, zero-delta guard prototypes veto the broad suffix on retained trajectories
where it would otherwise cause a non-dominating change. Guards are selected from
actual repair features and greedily covered at cosine 0.99999; there are no card,
deck, seed, lane, or action-name conditions in the model.

The naive composition was correctly rejected after preserving only 33/39 known
repair wins. Exact activation-state collection found 2,022 broad activations in
18,036 decisions across the 39 retained repair trajectories. A first compact
guard bank exposed seven negative or ambiguous terminal changes in the complete
inherited audit. Those seven trajectories supplied a second guard pass, while
the two favorable inherited transfers remained deliberately unguarded.

The promoted checkpoint is
`checkpoints/hybrid_strict193_kernel999_seed15023/policy_v2_hybrid_guarded_final.pt`
with SHA-256
`2219e9120f3918d13c65bba4cbef832e7fe536717d9cb83548ef02e5bc11d29e`.
It contains eight 64-unit stages with prototype counts
`(5, 6, 3, 7, 7, 5, 6, 1230)`. The last adapter comprises 1,191 hard safety
guards followed by the 39 broad repair prototypes. All retained/base tensors and
all donor-stage tensors were copied exactly, and the checkpoint has no optimizer
state.

All 39 known repair episodes win under independent full-reset replay. The final
inherited gate covers 3,200 random, 240 deterministic-strategy, and 160 frozen-
policy games: 3,598/3,600 records are exact. Seed 1605046/player 1 improves from
a 1-0 win to 2-0; seed 628253/player 1 preserves its 3-1 win, gains 729 own-
tower HP, and ends 270 ticks sooner. There are zero negative or ambiguous
changes. The full untouched seventeenth block remains 172-28 with 199/200 exact
records and only the previously observed +289 own-tower-HP transfer. Across the
3,800-game inherited-plus-untouched gate, exactly three changes are favorable
and there are zero regressions. The full repository suite passes 1,096 tests.

This guarded hybrid is promoted as the retained policy. Further improvement
must use new untouched populations and preserve this expanded 3,800-game gate;
the strict stage-seven checkpoint remains the rollback artifact.

## Eighteenth-block generalized-repair challenger

The promoted guarded hybrid scored 163-37 on the previously untouched
eighteenth random block beginning at seed 3200001. The strict stage-seven
rollback produced all 200 of the same terminal records, confirming that the
existing broad stage was safe but silent there. Full-from-reset counterfactual
search over eight close losses found winning one-action interventions for four
episodes: seeds 3216145/player 0, 3228253/player 1, 3252469/player 1, and
3298883/player 1.

The first broad 0.999 four-prototype fit at learning rate 1e-4 was rejected
after remaining at 0/4 repair accuracy through 200 steps. Its target alternatives
began as deep as rank 646 of 805 legal actions and 29.77 logits behind the
parent action. A 0.1 sweep reached only 3/4. A 0.2 sweep first reached 4/4 at
step 125 while retaining exact diagnostic preservation agreement and zero
preservation-corpus KL drift.

State accuracy alone was insufficient for seed 3216145/player 0. Full-reset
causal tracing found that its prototype first changed an earlier action at tick
1016 with similarity weight 0.649, before correctly selecting the intended
action at tick 1688. One zero-delta hard guard at that exact repair feature
suppresses the broad suffix locally. The resulting checkpoint is
`checkpoints/generalized_eighteenth_kernel999_lr02_seed15026/policy_v2_guarded_tick1016.pt`
with SHA-256
`e59659ab5d7ac292eb66d5d6ca9940d4dca8f13f79bb97d8c0487d104fa4fbc6`.
Its ninth stage contains one hard guard followed by four broad repair
prototypes and yields to all earlier stages.

All four targeted episodes then win under independent full-reset replay. The
complete eighteenth block improves from 163-37 to 167-33: 196/200 terminal
records are exact and exactly the four targeted losses become wins. On a
genuinely untouched nineteenth block beginning at seed 3400001, retained and
challenger both score 172-28 and all 200 records are exact. This demonstrates a
safe targeted repair on the measured population but no new out-of-sample
transfer. All 39 earlier repair episodes still win across 18,036 replayed
decisions, and the full repository suite passes 1,096 tests. The checkpoint
also preserves all 3,800 inherited terminal records exactly: 3,200 historical
random games, 240 games across six deterministic strategy bots, 160 games
against four frozen policies, and the 200-game seventeenth block. Across the
inherited gate, trained eighteenth block, and untouched nineteenth block, it
changes exactly four of 4,200 records, all four from losses to wins, with zero
regressions or neutral reshuffles. It is promoted as the retained policy; the
prior guarded hybrid remains the rollback.

A 192,288-state recurrent scan of the 200k preservation corpus found zero
neighbors and zero deterministic action changes at the deployed 0.999
threshold; the nearest corpus state had cosine similarity 0.998922. A
checkpoint-only threshold sweep preserved all weights and prototypes. At 0.995,
1,818 corpus states entered a repair neighborhood but only one deterministic
action changed; at 0.99, 17,172 states entered and 36 actions changed. Full-reset
replay nevertheless rejected 0.995 immediately: seed 3216145/player 0 regressed
from the repaired 1-0 win to a 0-1 loss. Even two exact causal guards left that
failure unchanged because the widened prototype activated on 390 decisions in
the trajectory. Threshold widening is therefore rejected in favor of adding
diverse outcome-verified prototypes while retaining 0.999 locality.

## Nineteenth-block generalized-repair promotion

The ninth-stage retained policy scored 172-28 on the nineteenth random block
beginning at seed 3400001. Counterfactual search over eight close losses found
at least one full-reset winning branch for five episodes: seeds 3426235/player
1, 3451460/player 0, 3456505/player 0, 3466595/player 1, and 3494847/player 1.
The other three searched losses produced no verified winning branch and were
not used as repair targets.

A five-prototype 0.999 stage was fit from the retained checkpoint with seed
15027, learning rate 0.1, and the 200k recurrent preservation corpus. Repair
accuracy first reached 5/5 at step 60; step 75 was the first saved successful
checkpoint. It retained 64/64 sampled preservation actions with zero measured
KL drift. Full-reset replay then exposed two earlier causal activations: seed
3451460/player 0 diverged at tick 2464 and seed 3466595/player 1 at tick 3000.
Two exact zero-delta hard guards restored both targets, after which all five
repairs won and the complete block improved from 172-28 to 177-23 with exactly
the five intended loss-to-win changes.

The first 4,200-game inherited gate correctly rejected that two-guard candidate
as unsafe. It preserved the five wins and added a favorable 1-0 to 3-0 transfer,
but seed 94739/player 1 dealt less opponent-king damage and seed 1022199/player
0 retained its 1-2 result with own king HP reduced from 1897 to 25. Causal
tracing added one parent-state guard at seed 94739/player 1 tick 2440 and two at
seed 1022199/player 0 ticks 2464 and 2800. These are repair-feature guards only;
the policy contains no seed, deck, card, lane, or action-name conditions.

The promoted checkpoint is
`checkpoints/generalized_nineteenth_kernel999_lr01_seed15027/policy_v2_guarded_safety5.pt`
with SHA-256
`6377e9dcf4cbe9fd419a3b461c92777f4139e2937002e6d1f1f7873605183e1f`.
It contains ten 64-unit repair stages with prototype counts
`(5, 6, 3, 7, 7, 5, 6, 1230, 5, 10)`. The final stage comprises five hard
safety guards and five broad repair prototypes, uses threshold 0.999, and
yields to every earlier stage.

The final 4,200-game promotion replay scores 3530-670 versus the retained
3525-675 baseline. Of 4,200 terminal records, 4,193 are exact. The seven
changes are the five intended loss-to-win repairs, one inherited 1-0 to 3-0
improvement at seed 844397/player 1, and one 3-0 to 3-0 timing-only transfer at
seed 432289/player 1 with identical tower HP. There are zero negative or
ambiguous changes across 3,200 historical random games, 240 deterministic
strategy games, 160 frozen-policy games, and the seventeenth, eighteenth, and
nineteenth 200-game blocks. All 48 known repaired episodes win under independent
full-reset replay.

On the genuinely untouched twentieth block beginning at seed 3600001, parent
and promoted policy both score 167-33. Records are 199/200 exact. The only
transfer, seed 3650451/player 1, preserves a 3-0 win while ending 487 ticks
sooner and retaining 267 additional tower HP. This is favorable out-of-sample
transfer with no observed twentieth-block regression. The eighteenth checkpoint
remains the rollback artifact.

## Twentieth-block generalized-repair promotion

The promoted nineteenth policy scored 167-33 on the untouched twentieth random
block beginning at seed 3600001. Eight close losses were searched from full
reset; five produced verified winning one-action branches: seeds 3614127/player
1, 3623208/player 0, 3635316/player 1, 3645406/player 1, and 3672649/player 0.

A five-prototype 0.999 stage was fit with seed 15028 and learning rate 0.1.
Repair-state accuracy reached 5/5 at step 30 with zero preservation-corpus
activation, zero measured KL drift, and 64/64 sampled action agreement. Step 50
was the first saved fully fitted checkpoint. All five episodes won immediately
under full-reset replay, and the complete twentieth block improved to 172-28
with exactly those five loss-to-win changes.

The unguarded stage preserved 4,198/4,200 inherited records. Its only changes
were two still-winning but ambiguous strategy trajectories at seed 1411100/
player 1. Exact causal tracing against the actual deterministic bots found
reactive-defense divergences at ticks 2608, 2968, and 3336, plus a split-lane
divergence at tick 2608. Four zero-delta hard guards restored both complete
40-game strategy suites exactly while retaining all five repairs.

The promoted checkpoint is
`checkpoints/generalized_twentieth_kernel999_lr01_seed15028/policy_v2_guarded_strategies_v3.pt`
with SHA-256
`33eea600968eb0e5c5f06a9dc18f53fd5450017d2a99eac77ed7a73fbde3a3be`.
It contains eleven 64-unit stages with prototype counts
`(5, 6, 3, 7, 7, 5, 6, 1230, 5, 10, 9)`. The final stage contains four hard
guards followed by five broad repair prototypes, uses threshold 0.999, and
yields to all earlier stages. All 216 parent tensors are bit-identical; exactly
six new stage tensors were added and the checkpoint contains no optimizer state.

The final inherited replay preserves all 4,200 parent records exactly. The
trained twentieth block improves exactly five losses to wins, while the
genuinely untouched twenty-first block beginning at seed 3800001 remains
156-44 with all 200 records exact. Across the 4,600-game promotion gate there
are exactly five changes, all intended loss-to-win repairs, and zero negative,
ambiguous, or neutral changes. All 53 known repair episodes win under
independent full-reset replay, and the full repository suite passes 1,096 tests.
The nineteenth checkpoint remains the rollback artifact.

## Twenty-first-block generalized-repair promotion

The promoted twentieth policy scored 156-44 on the untouched twenty-first
random block beginning at seed 3800001. Eight close losses were searched from
full reset. Four produced verified winning one-action branches: seeds
3836325/player 1, 3839352/player 1, 3870631/player 0, and 3875676/player 1.

A four-prototype 0.999 stage was fit with seed 15029 and learning rate 0.1.
Repair-state accuracy reached 4/4 at step 90; step 100 was the first saved
successful checkpoint. The stage had zero preservation-corpus activation,
64/64 sampled action agreement, and zero measured KL drift. Full-reset replay
then exposed one pre-target activation at tick 1184 and one post-target
activation at tick 2800 for seed 3875676/player 1. Two exact zero-delta guards
restored the intended causal trajectory while retaining all four repairs. The
complete twenty-first block improved from 156-44 to 160-40 with exactly those
four loss-to-win changes and 196/200 exact terminal records.

The first inherited safety replay exposed two additional non-winning
trajectory changes: seed 641370/player 0 retained its 1-3 result but changed
tower damage, while seed 3221190/player 1 regressed from 1-2 at regulation end
to a 0-3 early loss. Causal tracing added guards at ticks 1184 and 1856 for the
first episode and ticks 1712 and 2360 for the second. These guards restored
both complete terminal records exactly. The unrelated seed 3627244/player 1
transfer was retained because it strictly improves an existing 3-2 win: the
battle ends 14 ticks sooner with 336 additional own tower HP.

The promoted checkpoint is
`checkpoints/generalized_twentyfirst_kernel999_lr01_seed15029/policy_v2_guarded_safety6.pt`
with SHA-256
`b7b41185b1a2f59cc7e8a249a58b56d954f7294eb01cc2728498740ef93eae0d`.
It contains twelve 64-unit repair stages with prototype counts
`(5, 6, 3, 7, 7, 5, 6, 1230, 5, 10, 9, 10)`. The final stage contains six
hard guards followed by four broad repair prototypes, uses threshold 0.999,
and yields to all earlier stages. All 222 parent tensors are bit-identical;
exactly six new stage tensors were added and the checkpoint contains no
optimizer state.

The final 4,400-game inherited safety gate scores 3702-698 for both parent and
candidate. Of 4,400 terminal records, 4,399 are exact; the sole change is the
strictly favorable seed 3627244/player 1 transfer described above. The trained
twenty-first block contributes exactly four loss-to-win repairs, while the
genuinely untouched twenty-second block beginning at seed 4000001 remains
163-37 with all 200 terminal records exact. Across the complete 4,800-game
promotion gate, 4,795 records are exact and the five changes are four intended
repairs plus one favorable transfer, with zero negative, ambiguous, or neutral
changes. All 57 known repair episodes win under independent full-reset replay,
and the full repository suite passes 1,096 tests. The twentieth checkpoint
remains the rollback artifact.

## Twenty-second-block generalized-repair promotion

The promoted twenty-first policy scored 163-37 on the untouched twenty-second
random block beginning at seed 4000001. Eight close losses were searched from
full reset. Four produced verified winning one-action branches: seeds
4009082/player 1, 4037334/player 0, 4038343/player 0, and 4069622/player 1.

A four-prototype 0.999 stage was fit with seed 15030 and learning rate 0.1.
Repair-state accuracy reached 4/4 at step 100. The fitted stage had zero
preservation-corpus activation, 64/64 sampled action agreement, and zero
measured KL drift. All four target episodes won immediately under independent
full-reset replay. The complete twenty-second block improved from 163-37 to
167-33 with exactly those four loss-to-win changes and 196/200 exact terminal
records.

The promoted checkpoint is
`checkpoints/generalized_twentysecond_kernel999_lr01_seed15030/policy_v2_repair_step_0100.pt`
with SHA-256
`7dd0053f70d17066d4fb8b3e27c8b27fba2a36c1cdaedfe23f1c99e29a65e415`.
It contains thirteen 64-unit repair stages with prototype counts
`(5, 6, 3, 7, 7, 5, 6, 1230, 5, 10, 9, 10, 4)`. The final stage contains four
broad repair prototypes, uses threshold 0.999, and yields to all earlier stages.
All 228 parent tensors are bit-identical; exactly six new stage tensors were
added and the checkpoint contains no optimizer state.

The final 4,600-game inherited safety gate scores 3862-738 for both parent and
candidate. Of 4,600 terminal records, 4,599 are exact. The sole transfer is a
strict improvement at seed 2016145/player 0: the existing 1-0 regulation win
retains the same opponent HP and end tick while preserving 84 additional own
tower HP. The trained twenty-second block contributes exactly four loss-to-win
repairs. On the genuinely untouched twenty-third block beginning at seed
4200001, parent and candidate both score 174-26 with all 200 records exact.
Across the complete 5,000-game promotion gate, 4,995 records are exact and the
five changes are four intended repairs plus one favorable transfer, with zero
negative, ambiguous, or neutral changes. All 61 known repair episodes win
under independent full-reset replay, and the full repository suite passes
1,096 tests. The twenty-first checkpoint remains the rollback artifact.

## Twenty-third-block generalized-repair promotion

The promoted twenty-second policy scored 174-26 on the untouched twenty-third
random block beginning at seed 4200001. Eight close losses were searched from
full reset. Three produced verified winning one-action branches, but the seed
4201010/player 1 prototype changed its earlier recurrent trajectory and failed
under full-reset policy replay. It was excluded from the promotion candidate.
The two causally robust repairs are seeds 4277694/player 1 and 4286775/player 1.

A two-prototype 0.999 stage was fit with seed 15032 and learning rate 0.1.
Repair-state accuracy reached 2/2 at step 10, the first saved checkpoint. The
stage had zero preservation-corpus activation, 64/64 sampled action agreement,
and zero measured KL drift. Both target episodes won under independent
full-reset replay. The complete twenty-third block improved from 174-26 to
176-24 with exactly those two loss-to-win changes and 198/200 exact records.

The first 4,800-game inherited gate found two non-result transfers. Seed
1604037/player 0 remained a 1-3 loss but survived 36 ticks longer and dealt 292
additional tower damage, a strict improvement. Seed 108865/player 0 retained
the same 1-0 result, end tick, and own tower HP but shifted damage between the
two surviving opponent towers, leaving 78 more total opponent HP. The latter
was treated as ambiguous. The exact retained trajectory produced 25 raw
guard states, reduced during composition to thirteen feature-space guards.
They restored seed 108865 exactly while preserving both intended repairs and
the favorable seed 1604037 transfer.

The promoted checkpoint is
`checkpoints/generalized_twentythird_robust2_kernel999_lr01_seed15032/policy_v2_guarded_seed108865.pt`
with SHA-256
`78db9fc8fef3a265af96c63399f4f1c554d02bc113af63ae2312024f2a1cdd81`.
It contains fourteen 64-unit repair stages with prototype counts
`(5, 6, 3, 7, 7, 5, 6, 1230, 5, 10, 9, 10, 4, 15)`. The final stage contains
thirteen hard guards followed by two broad repair prototypes, uses threshold
0.999, and yields to all earlier stages. All 234 parent tensors are
bit-identical; exactly six new stage tensors were added and the checkpoint
contains no optimizer state.

The final 4,800-game inherited safety gate scores 4029-771 for both parent and
candidate. Of 4,800 terminal records, 4,799 are exact; the sole transfer is the
strictly favorable seed 1604037/player 0 case described above. The trained
twenty-third block contributes exactly two loss-to-win repairs. On the
genuinely untouched twenty-fourth block beginning at seed 4400001, parent and
candidate both score 160-40 with all 200 records exact. Across the complete
5,200-game promotion gate, 5,197 records are exact and the three changes are
two intended repairs plus one favorable transfer, with zero negative,
ambiguous, or neutral changes. All 63 known repair episodes win under
independent full-reset replay, and the full repository suite passes 1,096
tests. The twenty-second checkpoint remains the rollback artifact.

## Twenty-fourth-block generalized-repair promotion

The promoted twenty-third policy scored 160-40 on the untouched twenty-fourth
random block beginning at seed 4400001. Eight close losses were searched from
full reset. Two produced causally robust winning branches: seeds 4403028/player
1 and 4460541/player 1.

A two-prototype 0.999 stage was fit with seed 15033 and learning rate 0.1.
Repair-state accuracy reached 2/2 at step 50. Both target episodes then won
under independent full-reset replay. The complete twenty-fourth block improves
from 160-40 to 162-38 with exactly those two loss-to-win changes and 198/200
exact terminal records.

The complete inherited 5,000-game gate preserves the 4205-795 result record.
Of 5,000 terminal records, 4,997 are exact. The three non-result changes are all
non-regressive: seed 1836325/player 1 preserves the same 3-0 result and tower HP
while ending 29 ticks sooner; seed 3262559/player 1 improves a 3-1 win to 3-0,
ends 510 ticks sooner, and preserves 1,756 additional own tower HP; and seed
3853478/player 0 retains the identical 1-3 terminal crowns and tower HP while
surviving three ticks longer. The genuinely untouched twenty-fifth block
beginning at seed 4600001 remains 163-37 with all 200 records exact.

The promoted checkpoint is
`checkpoints/generalized_twentyfourth_robust2_kernel999_lr01_seed15033/policy_v2_repair_step_0050.pt`
with SHA-256
`4eb4a9025e44ea6929c4f1928ef177373163efd5d73d4e022f4c1ca06bf877ee`.
It is 31,437,063 bytes and contains fifteen 64-unit repair stages with prototype
counts `(5, 6, 3, 7, 7, 5, 6, 1230, 5, 10, 9, 10, 4, 15, 2)`. All 240 parent
tensors are bit-identical; exactly six new stage tensors were added, all 246
candidate tensors have the expected structure, and the checkpoint contains no
optimizer state.

Across the complete 5,400-game promotion gate, the candidate improves the
parent from 4528-872 to 4530-870. Exactly 5,395 terminal records are unchanged;
the five changes are the two intended loss-to-win repairs and the three
non-regressive inherited transfers above. The previous 124-game known-repair
set is record-exact, both new repair episodes win from both evaluated seats,
and all 65 known repair episodes therefore remain winning. The full repository
suite passes 1,100 tests. The twenty-third checkpoint remains the immutable
rollback artifact.

## KataCR recorded-game pretraining experiment

The public `wty-yy/Clash-Royale-Replay-Dataset` repository was pinned at
revision `ce86e10bedcf97762c3d207633f035cd12be8936`. Its 347 compressed KataCR
trajectories contain 221 Hog 2.6 games and 126 Golem games. The local source
snapshot has no explicit data license, so the imported corpus remains a local
research artifact and is not a distributable project asset.

`scripts/import_katacr_replays.py` maps the bottom player's public observation
into Clasher's canonical perspective and native legal action space. Evolution
cards map to their base cards, unknown opponent units remain unknown tokens,
and 889 empty-slot placements were recovered only when a prior observation of
the same hand slot established the card. The 45 remaining ambiguous placements
were retained only as forced-noop recurrent context and never assigned guessed
labels. The resulting `datasets/katacr_hog26_human_v1.npz` has SHA-256
`24cead36df64271cf25896490a61271a2a76f330d5f49c14ce78cc101d7d6ad3` and
contains 383,670 frames, 17,331 genuine placements, and 366,339 forced-noop
context frames from 347 episodes. Exact left-right augmentation removes the
source's 9,861-versus-7,470 placement-side imbalance. A known limitation is
that the current importer does not decode health-bar crops, so detected live
entities use neutral full health.

Matched spatial-v1 recurrent imitation used whole-episode 80/20 splitting,
sequence length 32, seed 15501, and a 96-wide three-actor-layer policy. The
three-epoch mirrored checkpoint reached 26.64% held-out exact action accuracy,
57.93% held-out slot/action-type accuracy, 28.84% mechanic-tolerant accuracy,
and 4.0355 held-out loss. Its SHA-256 is
`29f47e3952efee563e9d067eeac353342fea0765b13eef5caba9ee51018fe6b1`.
The matched random initialization reached only 11.27% exact accuracy at the
one-epoch comparison point. Before PPO, both the one- and three-epoch human
models scored 50-10 over five 12-game screens, versus 29-31 for the random
control; both were 10-2 against reactive defense, and the three-epoch policy
was 12-0 on the Hog random depth-4 screen.

Human and random-control arms then received identical 81,920-decision PPO
pilots: 20 updates, 64 environments, 12 CPU actors, MPS learner, defense-v2,
and a stationary league of two random workers plus balanced and reactive-
defense workers. Update 10 was the best human checkpoint. On the first 72-game
external screen it scored 46-26, versus 20-52 for matched random-init update
10. Both arms weakened by update 20, to 40-32 and 35-37 respectively, so the
later checkpoints were rejected.

The expanded gate added 96 games per arm against bridge-pressure, slow-push,
spell-control, and split-lane. Human update 10 scored 42-54 and control update
10 scored 44-52. Combining all eight external workloads gives 88-80 for the
human arm and 64-104 for control over 168 games each, with mean incoming tower
danger 0.04653 versus 0.06429. The apparent aggregate advantage is specialized:
the human checkpoint scored 23-1 against a Hog 2.6 random mirror where control
scored 1-23. Outside that workload the arms were nearly tied at 65-79 and
63-81. In direct policy play, human beat control 20-4 on the Hog-only deck but
lost 9-15 on broad decks. It lost 4-20 to the sparse-repair safety champion,
while control lost 2-22. Human PPO update 10 also went 10-14 against its own
pre-PPO initialization, showing that the ten PPO updates changed behavior but
did not dominate the demonstrator on the fresh direct seed block.

Conclusion: recorded-game imitation is retained as a useful sample-efficiency
and defensive-behavior warm start, not promoted as the general champion. The
next experimental phase resumes human update 10 at lower learning rate with an
L2 anchor to that checkpoint and a broad league containing all six strategy
bots plus random, fixed-human, and frozen-champion opponents. The exact
twenty-fourth sparse-repair policy remains the safety champion and rollback
artifact. After adding the importer and exact mirror augmentation, the full
repository suite passes 1,101 tests.

### Anchored broad-league continuation

The first anchored continuation resumed human PPO update 10, reset its
optimizer, used learning rate `1e-4`, and trained updates 11-30 with 64
environments, 12 CPU actors, and an MPS learner. Its league allocated three
workers to random, one to each of the six public-information strategies, two to
the frozen update-10 human parent, and one to its architecture-matched random-
init PPO control. An attempted champion worker was rejected before training
because the exact safety champion's repair-stage model config differs; the
champion therefore remains evaluation-only. L2 anchoring to human update 10
used coefficient 0.005. Training stayed finite with final KL 0.00262, explained
variance +0.199, playable no-op 1.0%, and no KL-stop update.

Fresh 48-game checkpoint sweeps selected update 20. External scores for updates
15, 20, 25, and 30 were respectively 21-27, 28-20, 22-26, and 24-24. Update 20
had +0.292 crowns/game and mean incoming danger 0.03056, while later updates
regressed despite stable training statistics. The selected checkpoint is
`checkpoints/katacr_human_v1_ppo_broad_anchor30/policy_v2_update_000020.pt`
with SHA-256
`819354ef04816b2f5d47daea2f174ae5d7c14ff92c1558b0edade6774a91498d`.

The selected checkpoint was replayed on the exact 168-game external matrix used
for its parent. It improves 88-80 to **99-69**, crown margin from -0.143 to
+0.220 per game, and mean incoming tower danger from 0.04653 to 0.03898. Hog
random remains 23-1, while broad random improves 12-12 to 16-8, reactive 6-6 to
7-5, bridge-pressure 9-15 to 10-14, slow-push 8-16 to 11-13, spell-control
13-11 to 16-8, and split-lane changes 12-12 to 11-13. Balanced remains 5-7.
On fresh direct blocks, update 20 beats its update-10 parent 18-6 on broad decks
and 19-5 on Hog-only decks. On the identical champion seed block it improves
the parent's 4-20 to 9-15, but still does not displace the exact sparse-repair
safety champion.

Update 20 is therefore promoted only as the human-data experimental champion.
The next bounded phase resumes it at learning rate `5e-5`, anchors to it with
coefficient 0.01, and gives additional league slots to bridge-pressure,
slow-push, and split-lane. Promotion still requires a fresh paired sweep and
replay of the fixed 168-game matrix; stable optimizer metrics alone are not an
acceptance signal.

### Targeted anchored continuation through update 28

The targeted phase resumed experimental update 20 and trained updates 21-30 at
learning rate `5e-5`. It used two workers each for bridge-pressure, slow-push,
and split-lane, one each for balanced, reactive-defense, and spell-control, two
random workers, and one frozen update-20 worker. L2 anchoring to update 20 used
coefficient 0.01. The final update remained finite with KL 0.00054, explained
variance +0.342, and anchor distance 0.092.

A fresh 72-game sweep selected update 28 over updates 22, 24, 26, and 30. Their
scores were respectively 41-31, 40-32, 39-33, **44-28**, and 40-32. Update 28
also had the best crown margin (+0.264/game) and lowest mean incoming danger
(0.03404) in that sweep. The selected checkpoint is
`checkpoints/katacr_human_v1_ppo_targeted_anchor30/policy_v2_update_000028.pt`
with SHA-256
`5b57992ad6a3cd7b88ee4fd42aa4860d8e5f825914bbffc741af1b42e5205b27`.

On the complete fixed 168-game external matrix, update 28 scores **104-64**,
improving update 20's 99-69 and the original update-10 parent's 88-80. Crown
margin rises from +0.220 to +0.315 per game and mean incoming danger falls from
0.03898 to 0.03618. The per-workload record is broad random 16-8, Hog random
22-2, balanced 6-6, reactive-defense 7-5, bridge-pressure 12-12, slow-push
10-14, spell-control 17-7, and split-lane 14-10. Against the fixed exact safety
champion it improves again from 9-15 to 10-14. On fresh direct blocks it beats
update 20 by 14-10 on broad decks but loses 9-15 on Hog-only decks; because its
external Hog gate remains 22-2, that direct result is recorded as a policy-
interaction weakness rather than concealed as an aggregate success.

Update 28 is promoted as the new human-data experimental champion. The exact
sparse-repair checkpoint remains the global safety champion. Further RL must
continue from update 28 with smaller steps and retain the fixed external matrix,
direct parent blocks, and exact champion match as rollback gates.

### Rejected weak-mix continuation

A follow-up weak-mix phase resumed update 28 at learning rate `2.5e-5`, kept
the 0.01 anchor, and emphasized slow-push, bridge-pressure, and balanced. Its
fresh sweep selected update 34 at 46-26, but the fixed matrix rejected it. On
the authoritative 168 games it fell to **100-68** from update 28's 104-64,
crown margin fell from +0.315 to +0.262, and mean incoming danger rose from
0.03618 to 0.03810. It also lost direct broad play to update 28 by 10-13-1.
Although its fixed-champion result improved from 10-14 to 11-13, that isolated
gain does not offset the external and direct-parent regressions. The entire
weak-mix branch is rolled back; update 28 remains the experimental champion.

The failed branch also exposed growing passivity: later online updates reached
29% playable no-op, and the fresh deterministic sweep measured 46% broad and
41% split-lane playable no-op at update 34. Because the trainer's action-type
entropy term directly rewards probability mass across card slots, no-op, and
ability, the next matched experiment lowers only action-type entropy from 0.02
to 0.005. Location entropy, learning rate, anchor, seeds, and opponent mix stay
fixed so the effect can be attributed rather than guessed.

Lower action-type entropy controlled passivity but did not preserve aggregate
skill. Its best fresh checkpoint scored 45-27, but the fixed matrix fell to
98-70 from update 28's 104-64. It improved balanced while regressing spell,
split, and reactive; the branch was rejected.

The trainer now supports an optional behavior-level anchor through
`--anchor-policy-kl-coef`. For each PPO learner minibatch it computes forward
KL from the frozen accepted policy to the current joint legal-action
distribution on the same recurrent rollout inputs. This complements parameter
L2 and applies globally to any compatible policy; it contains no card, deck,
or opponent-name rule. Ruff and mypy pass, focused recurrent-policy tests pass
27/27, and the complete repository suite passes 1,103 tests.

Matched weak-mix pilots tested behavior-KL coefficients 0.5 and 0.1. Coefficient
0.5 reduced deterministic playable no-op at update 34 from 20.8% to 9.2%, but
its best fixed candidate scored 102-66, tied update 28 directly on broad decks,
and lost 9-15 on Hog. Coefficient 0.1 did not improve the matched mini-gate and
was stopped without an expensive fixed replay. Behavior KL is retained as a
verified anti-drift tool, but neither weak-mix coefficient is promoted. The
next experiment returns to balanced opponent coverage instead of continuing to
over-weight the three weak strategies.

The balanced all-strategy KL continuation also failed its matched parent gate.
On a fresh 72-game block, accepted update 28 scored 44-28; continuation updates
30, 32, and 34 scored 41-31, 40-32, and 41-31. No fixed replay was warranted.

Parallel rollout workers now support architecture-heterogeneous frozen policy
opponents. Each checkpoint is instantiated from its own `PolicyConfig`, while
the loader still requires the shared token vocabulary and actor/critic
observation feature schema. This removes the former false requirement that a
plain learner and a repair-stage opponent have identical parameter topology.
Unit tests cover a compatible repair-stage opponent and an incompatible schema;
a real two-worker integration smoke completed an update from the 96-wide human
policy against the fifteen-stage sparse-repair champion.

A six-update champion-mix pilot then allocated two workers to the exact
champion, two to frozen update 28, two to random, and one to each strategy bot.
On its fresh 84-game matched block, update 28 itself scored 43-29 across the six
external workloads and 8-4 versus champion. Updates 30, 32, and 34 regressed to
41-31, 41-31, and 42-30 externally; champion results were 8-4, 7-5, and 7-5.
The entire continuation is rejected. Architecture-heterogeneous opponents are
retained as general infrastructure, but the evidence does not justify more
PPO from this curriculum. Human experimental update 28 remains the rollback
checkpoint.

### Broad offline champion rehearsal

Further PPO continuations had plateaued, so the next experiment returned to
offline supervision without reusing the old planner labels. That choice is
evidence-driven: the legacy DAgger fine-tune lost its random gate, and the
stable-root correction still did not improve gameplay. Instead, the exact
twenty-fourth sparse-repair champion generated deterministic behavior labels
on broad decks against each of the six stationary strategy opponents. Six
20,000-frame corpora completed with legal labels and complete shard manifests.
The merged 120,000-frame teacher corpus has SHA-256
`ae7bc6357381933913c63fda631ec42c941daa06d6d17dbc4636c87a3e3e7ea1`.

A deterministic whole-episode corpus combiner now records every source path,
SHA-256, label source, opponent, selected episode count, and selected sample
count. The first rehearsal set mixed 121,099 sampled human Hog frames with all
120,000 champion-teacher frames, producing 241,099 frames across 287 episodes
with SHA-256
`f2f7f172c7b6ec20745a00abd1c5d960a5f06ec80715b507f0bb6cda4745b517`.

Uniform spatial imitation was rejected immediately. Although held-out exact
accuracy rose from 4.54% to 69.82%, its fresh screen collapsed to 16-56 versus
the untouched update-28 control's 36-36. Playable no-op reached 93.18% and
incoming danger rose from 0.03982 to 0.12268. The cause is explicit in the
corpus: 78-88% of the teacher's informative playable labels are intentional
waits, and uniform imitation generalized those waits outside their states.

The fitter therefore gained a general placement-only sequence mode. All frames
still advance recurrent state, but only informative expert deployment labels
contribute gradient. This is source- and card-agnostic. The complete repository
suite passes 1,107 tests after the change, with clean focused Ruff and mypy.

One mixed-corpus placement epoch at `1e-5` restored normal activity and screened
43-29 versus the parent's 45-27, with better crown margin (+0.389 versus +0.319)
and lower danger (0.03518 versus 0.03946). It is nevertheless rejected: direct
matches lost 10-14 to the parent on both broad and Hog decks. Its 13-11 result
against the exact champion is retained as evidence that the teacher signal is
useful, but does not override the parent regressions. A half-rate `5e-6` sibling
also failed the win gate at 44-28 versus 47-25, despite again improving crown
margin and danger. A placement-only action-type-head fit reduced parameter
scope further and finished 46-26 versus 47-25; it too is rejected rather than
selected on secondary metrics. Update 28 remains the human-data experimental
champion while teacher-only rehearsal is evaluated separately to isolate the
effect of replaying already-learned human labels.

Teacher-only placement rehearsal improved the fresh screen to 44-28 from the
parent's 41-31 and improved the exact-champion block to 12-12, but the complete
fixed matrix regressed to 98-70. A four-update anchored PPO rescue selected its
first checkpoint on fresh games; that checkpoint recovered to 103-64-1 on the
fixed matrix, but remained below update 28's 104-64, with lower crown margin
(+0.256 versus +0.315) and slightly higher tower danger (0.03657 versus
0.03618). Compatible checkpoint interpolation at weights 0.50 and 0.75 did not
beat the parent in the matched screen. All three branches are rejected.

The trainer next gained a general recurrent placement-rehearsal auxiliary for
PPO. It validates corpus compatibility and legal labels, advances hidden state
through complete episode-contiguous chunks, and supervises only informative
expert placements. The first coefficient, `0.001`, lost its fresh 72-game gate
45-27 to 47-25. Reducing the coefficient to `0.0002` produced a promising
update 29 at 42-30 versus 41-31 on a fresh 72-game block, but its exact fixed
matrix scored 101-67. A targeted online rescue of that checkpoint tied the
parent in its mini-screen and was stopped without another fixed replay.

The auxiliary now also supports a location-only component. It conditions on
the expert card slot and optimizes only the mechanics-aware placement-location
loss, avoiding direct imitation of the teacher's card/no-op distribution. At
coefficient `0.0002`, update 31 passed two fresh gates: 18-6 versus 17-7 in the
mini-screen, then 49-23 versus 46-26 across 72 new games. Crown margin improved
from +0.375 to +0.472 and mean tower danger fell from 0.04010 to 0.03781 on the
larger fresh block. The authoritative matrix nevertheless finished 103-65:
broad random 15-9, Hog random 23-1, balanced 7-5, reactive 7-5, bridge 12-12,
slow 12-12, spell 14-10, and split 13-11. Compared with update 28, gains in Hog,
balanced, and slow were outweighed by broad, spell, and split regressions. A
four-update online-only rescue failed to beat its starting checkpoint. The
location-only method is retained because it is materially closer to parity
than joint rehearsal, but update 31 is not promoted and update 28 remains the
human-data experimental champion.

Halving the location-only coefficient to `0.0001` reduced the offline gradient
but did not produce a promotable checkpoint. Updates 29, 31, and 32 each scored
17-7 versus the parent's 16-8 mini-screen result. On the 72-game expansion,
update 31 tied the parent 46-26 while playable no-op rose from 3.43% to 9.29%;
the earlier update 29 lost 45-27. The branch was stopped without a fixed replay.

### TV Royale empirical placement prior

A second public human source was audited from
`chrisrca/clash-royale-tv-replays`. The repository's preprocessing defines the
same 18-by-32 arena grid used by Clasher, with an explicit 428-by-683 crop and
vertical offsets. Column-selective extraction avoided downloading image bytes.
The retained CSV has SHA-256
`227a37dd81377aa6dc2538ed0e5b111adfca50ff553884f322cdeec981616e1a`.
After excluding a mismatched coordinate shard, evolutions, spells, ambiguous
aliases, opponent-side rows, and globally deployable Miner, 6,302 placements
cover 51 of the 52 enabled non-spell cards; Miner is intentionally the sole
zero-prior card because the replay labels do not identify the acting seat.

The policy now supports an optional zero-initialized card-conditioned tile
prior. It adds only to the four conditional location-logit maps and therefore
cannot directly change card/no-op selection. Old checkpoints are exact when
the table is zero; the trainer can add the table only with fresh optimizer
state, and compatible old anchors instantiate an exact zero table. Focused
Ruff and mypy are clean and 30 tests cover coordinate filtering, checkpoint
augmentation, exact zero behavior, and location-only effects.

Three inference-only empirical priors at scales 0.05, 0.10, and 0.20 were
rejected on a matched 24-game screen. The parent scored 17-7. The candidates
scored 17-7, 15-9, and 16-8 respectively; even the tied 0.05 variant reduced
crown margin from +0.417 to +0.333 and increased mean danger from 0.02938 to
0.03025. The data and isolated mechanism are retained for future
state-conditioned training, but no static prior checkpoint is promoted.

A final isolated PPO pilot froze every original policy parameter and optimized
only the placement-prior table, initialized from the 0.05 empirical variant.
The 89,280-parameter table trained at `1e-3` with update 28 as both zero-prior
L2 and behavior-KL anchor. PPO throughput rose to roughly 371-401 transitions
per second because the base network was frozen. The matched screen remained
negative: the static prior and updates 29-30 scored 15-9 versus the parent's
17-7; updates 31-32 returned to 17-7 with the same +0.417 crown margin as the
parent as the anchor shrank the prior toward zero. Playable no-op was exactly
0.07% for every checkpoint, confirming that the isolation guarantee held, but
no candidate improved gameplay. The prior-only branch is rejected without an
expanded or fixed replay.

### Outcome-verified update-28 repair stage

The next continuation returned to terminal outcomes rather than another broad
teacher coefficient. Update 28 scored 26-22 on a fresh 48-game random block
beginning at seed 30701, with crown differential +0.396 and mean incoming tower
danger 0.06433. Six close losses were searched from full reset. Three episodes
had winning one-action interventions that all survived an independent reset
replay: seed 33728/player 1 at tick 232, seed 38773/player 1 at tick 344, and
seed 47854/player 1 at tick 4120. The middle episode had seven independently
winning alternatives; the fitter retained only its best-ranked earliest action.

A new zero-dense 64-unit repair stage contains exactly those three prototypes
at cosine threshold 0.99999. Every original update-28 parameter is frozen; only
the three stage-local prototype deltas are trained. The fit reached 100% repair
accuracy by step 10 and retained it through step 200. Prototype self-weight is
1.0, cross-weight is 0.0, and all 512 sampled preservation states have zero
activation and 100% parent-action agreement.

Full replay of the 48-game source block changes exactly three records, all from
losses to wins. The result rises from 26-22 to 29-19, crown differential from
+0.396 to +0.521, and mean tower danger falls from 0.06433 to 0.06343. The other
45 terminal records are byte-exact. The complete fixed 168-game matrix remains
104-64 with all records exact across broad random, Hog random, balanced,
reactive-defense, bridge-pressure, slow-push, spell-control, and split-lane.
Another 72 direct-policy games against the update-20 parent and the global exact
safety champion are record-exact, including the 10-14 champion result. A wholly
untouched 72-game random block beginning at seed 60701 is also record-exact at
41-31. Across the resulting 360-game gate, the challenger changes exactly three
records and every change is a loss-to-win improvement.

The promoted weight-only checkpoint is
`checkpoints/katacr_human_u28_fresh30701_repairs3_promoted/policy_v2_repair_step_0200.pt`
with SHA-256
`aa84bb8b54785b6c42aee8797544ee22a46d7d3c6fd4f43fcf78bc50ff1983a3`.
It is bit-exact in every model tensor to the evaluated candidate and differs
only by removing the source checkpoint's stale optimizer payload. The repair
fitter now removes inherited optimizer state automatically because repair-stage
topology is incompatible with the source optimizer. This checkpoint replaces
plain update 28 as the human-data experimental champion; the global exact safety
champion remains unchanged.

### Second outcome-verified human-policy stage

The promoted first-stage policy was then evaluated on 72 new random games
beginning at seed 60701 and scored 41-31. Eight close losses were searched from
full reset. Three episodes produced independently verified winning actions:
seed 61710/player 1, seed 75836/player 1, and seed 96016/player 0. A second
zero-dense 64-unit stage was fit from one best intervention per episode at the
same 0.99999 threshold. All earlier tensors were frozen. It reached 100% repair
accuracy by step 10, with prototype self-weight 1.0, cross-weight 0.0, zero
activation on 512 preservation states, and 100% sampled parent-action agreement.

Complete replay of the 72-game donor block improves exactly those three losses
to wins, raising the result to 44-28 and crown differential from +0.528 to
+0.639; the other 69 records are exact. All 288 inherited records are also
exact: the earlier 48-game repaired block, the fixed 168-game matrix, and 72
direct-policy games against the update-20 parent and global exact champion. A
new untouched 72-game block beginning at seed 110001 is record-exact at 45-27.
Across the stage-two 432-game audit, exactly three records change and all three
are loss-to-win improvements. Relative to plain update 28 across the same unique
blocks, the two stages make six changes and all six are loss-to-win improvements.

The new human-data experimental champion is
`checkpoints/katacr_human_u28_repair3_fresh60701_stage2_seed60702/policy_v2_repair_step_0200.pt`
with SHA-256
`90d7c61aa11f59279b30aa2239cdb8579a837d34c8f6b9ef32952ab7e0da7217`.
It contains two 64-unit stages with three strict prototypes each and no optimizer
state. The global exact safety champion remains unchanged.

### Balanced human-and-safety student

A fresh recurrent student was trained to combine the complementary human-data
and exact-safety lineages before any further online RL. Seven exact-safety
teacher corpora contain 210,000 decisions across random and all six stationary
strategy opponents. These were recurrently interleaved with 210,672 frames
from 190 complete validated KATacr human episodes. The resulting 420,672-frame
corpus is `datasets/human_safety_balanced_v1.npz`, SHA-256
`d26c657343002ed74c084a4cdf69d97c87d358bd15069b94aad7f1f8be72a660`.

The clean student is wider and deeper than the earlier 96-wide line: `d_model`
192, six attention heads, five actor layers, three critic layers, and recurrent
memory 384, for 6,170,628 parameters. One spatial-imitation epoch with sequence
length 32 and left-right augmentation reached 74.09% exact validation accuracy
and 66.20% action-type/slot accuracy. Its checkpoint is
`checkpoints/human_safety_student6m_v1/epoch1.pt`, SHA-256
`68970a0c56644841dde971684c0f47effc527635b702fb4e3286e0724e50b7d8`.

The first matched gameplay screen used the first 60 records of the established
fixed matrix. The student scored 47-13 with +1.350 crowns per game, versus
49-11 for the global safety champion and 43-17 for the human-data champion on
the exact same records. Record comparison found three wins unique to the
student versus five safety-only wins, and seven student-only versus three
human-only wins. The result is close to safety while materially improving over
the human line rather than merely averaging their scores.

Direct paired-seat policy evaluation confirmed the synthesis. In 32 games the
student beat the global safety champion 18-13-1 with +0.219 crowns per game; in
another 32 it beat the human-data champion 23-8-1 with +0.938 crowns per game.
Wins were balanced across seats in both matchups. This is sufficient for a
provisional promotion into online RL, but not a claim of mid-ladder-human
strength: the human corpus is still Hog 2.6 only and all gameplay gates remain
inside Clasher rather than the official client.

A conservative 20-update mixed-league PPO pilot is running from this student
in `checkpoints/human_safety_student6m_v1_ppo_league_seed1012001`. It uses 64
environments, 12 CPU actors, an MPS learner, defense-v2, two random workers, all
six strategy opponents, and two workers for each prior champion. Learning rate
is `1e-5`; the epoch-one student supplies both L2 (`0.005`) and forward-policy
KL (`0.05`) anchors, while the balanced recurrent corpus supplies joint
rehearsal at coefficient `0.05`. No PPO checkpoint is promoted until it clears
the same fixed, direct, and new-seed gates.

The first pilot completed 81,920 online transitions without numerical
instability. Update 10 scored 43-7-10 on the matched 60-game screen (80.0%
score, +1.283 crowns/game), update 14 scored 42-9-9, and update 20 scored
44-6-10 (81.7%, +1.383). The apparent stationary-opponent gain did not survive
the direct-policy gate. Update 20 tied the clean student 16-16, lost to the
global safety champion 14-18, and beat the human-data champion only 17-13-2.
Update 10 then tied both the clean student and safety champion 12-12 on matched
24-game subsets. No checkpoint from this branch is promoted. The joint
rehearsal term contributed roughly 0.13-0.17 to each loss while the PPO policy
term was near zero, so the branch behaved more like additional offline fitting
than the intended league adaptation.

A second pilot therefore restarts from the clean student rather than continuing
update 20. It removes rehearsal entirely, raises learning rate to `2.5e-5`,
doubles the L2 and policy-KL anchor coefficients to `0.01` and `0.1`, and adds
two frozen clean-student workers to a policy-heavier twelve-worker league. This
is the actual post-pretraining RL test: promotion still requires a direct win
over the clean student and no material safety regression.

The pure-PPO calibration completed 65,536 transitions through update 16. It
ran at roughly 106-110 transitions per second after warmup, about 17% faster
than the rehearsal-heavy branch, with final anchor-policy KL 0.00214 and no
numerical instability. Update 8 tied the clean student 8-8 and safety 7-7-2 on
16-game direct screens. Update 16 again tied the clean student 12-12 and scored
11-12-1 versus safety on 24-game screens. This is stable but not a promotion.
Because 65,536 transitions is only a calibration-scale sample, the same
optimizer and policy-heavy league continue to update 64; the clean student
remains the accepted checkpoint during the continuation.

At update 24, a first 16-game direct block appeared positive at 9-7 versus the
clean student and 8-7-1 versus safety. An independent second block reversed the
signal at 7-9 and 6-10. The combined 32-game evidence is 16-16 versus the clean
student and 14-17-1 versus safety, so update 24 is rejected and the update-64
continuation proceeds without changing the accepted checkpoint.

Update 48 failed its direct screen at 7-9 versus the clean student and 6-8-2
versus safety. Final update 64 completed 262,144 PPO transitions and was stable,
with anchor-policy KL 0.00386 and PPO KL 0.00038. Across two independent
24-game blocks it beat the clean student 27-21 with +0.188 crowns per game, but
scored only 22-24-2 with -0.104 crowns versus safety. The parent improvement is
real enough to retain as a research branch, but the safety regression prevents
promotion.

Weight interpolation at 25%, 50%, and 75% of update 64 was screened. Only the
75% blend retained a parent gain, scoring 18-14 across two 16-game blocks, but
it still regressed safety at 14-16-2. All blends are rejected. A targeted
low-rate safety-rescue curriculum now starts from update 64, anchored to update
64 itself, with six safety-champion workers plus clean-parent, human-policy,
and defensive strategy opponents. The clean epoch-one student remains the
accepted checkpoint.

The targeted safety rescue completed at update 80 after 65,536 additional
transitions. Optimization stayed numerically stable: final anchor-policy KL was
`0.00125`, PPO KL was `0.00025`, and clip fraction was `0.003`. Update 72 was
already positive against the clean parent at 9-7 (+0.250 crowns/game), but still
lost 6-8-2 to the safety champion (-0.250 crowns/game). Update 80 improved the
first 24-game screen to 13-11 against the parent and 11-11-2 against safety. An
independent 24-game replication then scored 17-7 against the parent and 11-13
against safety. Combined, update 80 is a real offensive improvement at 30-18
and +0.500 crowns/game versus the clean student, but remains slightly negative
against safety at 22-24-2 and -0.042 crowns/game. It is retained as a useful
challenger but is not promoted. The checkpoint is
`checkpoints/human_safety_student6m_u64_safetyrescue_seed1014001/policy_v2_update_000080.pt`,
SHA-256
`4b992114660a74260cd3fdd9837c151d3cb8ac0593c9bd63c07fb32b3ced8590`.

The next rescue changes the anchor rather than extending the same objective.
It resumes from update 80 but anchors directly to the clean student, whose
direct safety result was positive, with stronger L2 and policy-KL coefficients.
The safety-heavy opponent league is retained. Promotion still requires a
replicated direct gain over the clean parent with no safety regression before
the broader fixed screen runs.

The clean-anchor rescue completed updates 81-96 with learning rate `5e-6`, L2
coefficient `0.02`, and forward-policy KL coefficient `0.2`. It was stable
throughout: update 96 had PPO KL `0.00005`, zero clip fraction at printed
precision, and clean-anchor L2 distance fell from `0.412` at update 81 to
`0.210`. A matched fresh 12-game tournament screened update 80 and every saved
four-update checkpoint. Against the clean parent the records were 5-7, 6-6,
7-5, 7-5, and 7-5 for updates 80/84/88/92/96. Against the safety champion on
the corresponding fixed block they were 3-8-1, 5-7, 4-7-1, 4-7-1, and 5-6-1.
Thus update 96 improved materially over its update-80 initialization on the
difficult safety block while retaining a parent edge, but it has not crossed
the promotion boundary. The unchanged optimizer continues for one final
bounded sweep through update 112; updates 104 and 112 are the planned screens.

The final sweep did not produce a promotable consolidation. Update 104 retained
the 7-5 parent result but fell to 4-7-1 against safety. Update 112 reached 7-5
and 6-6 on the same 12-game blocks, then scored 11-13 against the parent and
12-11-1 against safety on independent 24-game replications. Combined over 36
games, update 112 tied the parent 18-18 with +0.028 crowns/game and edged safety
18-17-1 with +0.028 crowns/game. It removed the measured safety regression but
also surrendered the update-80 offensive gain, so it is not promoted. The
clean-anchor rescue is stopped; the clean epoch-one student remains accepted,
update 80 remains the offensive challenger, and update 112 is retained as a
consolidated research checkpoint.

The next phase restarts from the accepted clean student with a broader frozen
league rather than extending either rescue lineage. Its twelve opponent slots
cover random, all six stationary strategy styles, the exact safety champion,
the human-data champion, the offensive update-80 challenger, the consolidated
update-112 policy, and the clean parent itself. This is a one-million-transition
robustness phase with periodic saved checkpoints; direct parent/safety gates
remain authoritative and no checkpoint is promoted merely for training reward.

The first 131,072 transitions of the diversified league were stable but did
not yet produce a promotable checkpoint. Update 8 scored 7-9 against the clean
parent and 10-6 against safety. Update 16 initially scored 9-7 and 8-8, but an
independent 24-game replication reversed it to 10-14 and 9-14-1; combined
records were 19-21 and 17-22-1. Update 24 tied the parent 8-8 while beating
safety 9-7 and was not expanded. Update 32 initially scored 9-7 and 8-8, then
replicated at 13-11 and 10-13-1. Its combined 40-game records were 22-18 versus
the parent but 18-21-1 versus safety, so it is also rejected. These short
screens show useful but high-variance movement along the strength/safety
frontier. Further evaluation is spaced to update 64 so training capacity is
not consumed by repeatedly screening undertrained eight-update increments.

Update 64 completed 262,144 transitions with stable optimization: PPO KL
`0.00008`, clip fraction `0.001`, and anchor-policy KL `0.00116`. The fresh
24-game direct gate tied both references: 11-11-2 against the clean parent and
12-12 against the safety champion. The exact fixed 60-game screen then scored
42-10-8, or 46.0 points, versus the clean student's 47-13 and 47.0 points.
Component records were broad random 8-0-4 (baseline 9-3), Hog random 12-0
(12-0), balanced 4-1-1 (4-2), reactive-defense 3-2-1 (4-2), bridge-pressure
4-2 (4-2), slow-push 3-3 (5-1), spell-control 3-1-2 (5-1), and split-lane 5-1
(4-2). Gains in broad random, balanced, and split-lane do not offset the
reactive, slow-push, and spell-control regressions. Update 64 is rejected and
the clean student remains accepted. The diversified run continues unchanged
to update 128 so those already-present opponent styles receive a materially
larger sample before any curriculum weighting is changed.

Update 96 completed 393,216 transitions without destabilizing the clean
anchor. Its fresh 24-game direct screens were exact ties: 12-12 against the
clean parent and 12-12 against the safety champion, with zero crown
differential in both matchups. This is evidence that the broader league has
preserved the two primary reference boundaries, but it is not evidence of a
strength improvement. Update 96 is therefore not promoted or expanded to the
fixed 60-game breadth screen. Training continues unchanged to the predeclared
update-128 gate; the clean epoch-one student remains accepted.

Update 128 completed 524,288 transitions and failed the direct promotion gate.
On fresh paired-seat 24-game blocks it scored 10-14 with -0.375 crowns per game
against the clean parent and 12-12 with -0.042 crowns per game against the
safety champion. Safety remained level, but the parent regression rules out
replication and the fixed breadth screen. Update 128 is rejected; the clean
epoch-one student remains accepted while the diversified run continues to the
next spaced checkpoint.

Update 160 completed 655,360 transitions with stable optimization: PPO KL was
`0.00024`, clip fraction `0.002`, clean-anchor policy KL `0.00114`, and
clean-anchor L2 distance `0.196`. Its fresh 24-game direct screens scored
11-13 with -0.208 crowns per game against the clean parent and 12-10-2 with
+0.042 crowns per game against the safety champion. The safety result is
acceptable, but the parent regression repeats the update-128 failure. The
diversified lineage is stopped at update 160 and rejected without replication
or a fixed breadth screen; the clean epoch-one student remains accepted.

### State-conditioned diverse TV Royale placements

The next data improvement replaces the rejected static TV Royale placement
prior with action-time public board state. The MIT-licensed source's current
placement shard provides screenshots, four-card hands, elixir, chosen cards,
coordinates, replay IDs, and frame indices. A pinned pair of KataCR YOLOv8
detectors converts each visible action frame to public entity identities,
ownership, and canonical 18-by-32 positions. The importer retains only original
offset-zero rows with a located enabled card that is present in the observed
hand, applies cross-detector NMS, and emits ordinary Clasher recurrent corpus
arrays. Exact tower health remains unavailable and is represented neutrally,
matching the earlier KataCR replay importer.

This corpus is deliberately for the trainer's location-only rehearsal loss.
It conditions on the demonstrated card slot and teaches only the placement
map, so it cannot directly increase card-play frequency or suppress the
policy's learned no-op choice. The completed artifact is
`datasets/tv_royale_human_placements_v1.npz`, SHA-256
`64ca2e4b5f091ac99b38408b5609098c155b70b5236391ea019e6e2b894bb5f4`.
It initially accepted 1,127 placements from 87 replays across arenas 21 through
24, covers 63 enabled target cards, and has a mean of 9.75 detected entities
per action frame (maximum 28). Detector classes outside Clasher's enabled
public vocabulary account for 1,012 of 10,985 detections (9.21%) and are
deliberately omitted rather than mislabeled.

A two-row real-data smoke passed detector inference, then-current mask validation,
standard corpus loading, and `PlacementRehearsal` loading. The final artifact
also loads against the accepted clean checkpoint with recurrent sequence
length eight, yielding 107 episode-contiguous chunks and 856 supervised rows;
one actual location-only forward loss was finite at 10.152208328. The first
online test therefore starts independently from the accepted clean student,
uses a small `0.0001` location-only coefficient, and retains the clean L2 and
policy-KL anchors. Offline loss is only a plumbing check: direct parent/safety
gameplay gates remain authoritative, and no checkpoint is promoted from
imitation metrics alone.

The first full-parameter pilot stopped at update 8 after 32,768 online
transitions. It was numerically stable (anchor-policy KL `0.00076`, L2 distance
`0.032`) and reduced a matched 32-sequence TV Royale location loss from
8.5443 to 8.1236, but gameplay did not clear the safety boundary: it tied the
clean parent 12-12 and lost 10-14 with -0.375 crowns per game to the safety
champion on fresh 24-game paired-seat blocks. This checkpoint is rejected.
The next experiment freezes every nonspatial parameter and permits updates
only in the tile projection, memory-to-tile modulation, tile cross-attention,
tile key, card query, and location-bias modules. That preserves the recurrent
state encoder and action-type/no-op head exactly while testing whether the
state-conditioned human placement signal itself can improve play.

The guarded spatial-only restart completed eight updates. Exactly 669,504
parameters in the six permitted module families changed, while every
nonspatial tensor remained bit-identical to the clean checkpoint. It reduced
the same matched location loss only from 8.5443 to 8.5122 and then scored
11-13 with -0.167 crowns per game against the clean parent and 12-12 with zero
crown differential against safety on fresh 24-game blocks. It is also
rejected: the small placement shard does not provide enough signal to justify
more coefficient tuning.

Post-pilot auditing found that the initial importer had force-enabled an expert
tile even when the observed card could not legally be deployed there. This
hid 316 ordinary troop/building labels on the opponent side. The converter now
derives legality from shared card data, including the general enemy-side flag,
and rejects rather than mutates illegal labels. Direct tests cover ordinary
troops, Miner, and spells. The trainer also now fails closed before mutation on
non-finite loss, gradients, gradient norm, or post-step parameters; an injected
NaN regression test proves that the checkpoint remains unchanged.

The legality-corrected artifact,
`datasets/tv_royale_human_placements_strict_v2.npz`, has SHA-256
`28ca7b260a0097fe2cdf35fddf83f8aa9e0f917226df3379a001cbe8406ac750`
and contains 811 placements from 85 replays. A spatial-only sequence-four
pilot reduced a matched 64-sequence location loss from 10.8204 to 9.9037, but
failed replicated gameplay gates. Across two fresh 24-game blocks it scored
24-23-1 against the clean parent and 21-25-2 against safety. A 50% weight blend
then tied the parent 12-12 and lost 11-13 to safety. Both are rejected. This
rules out further tuning on the small legacy shard: better labels and broader
replay coverage are required.

The pinned source revision also contains a disjoint larger placement set that
was not represented in the first artifact. `training_offset_1.parquet` is a
10,016,106,287-byte pinned source with SHA-256
`ea734e33a9f8fbb7d1c5d58c2aa52bc4d39539a890e18df4a1b3b2853b10191b`.
It has 10,924 matched before/after action pairs from 317 replays in arenas 28,
29, and 31, with no overlap with the earlier shard. Its coordinate columns are
all missing, but the source notebook establishes that offset zero is the frame
before the play and offset one is the next frame. KataCR's `clock` detector
class is the in-arena deployment countdown marker, so a new importer recovers
exactly one novel lower-player clock cluster and fails closed on old clocks,
multiple clusters, low confidence, spells, incomplete hands, opponent-side
locations, or illegal tiles.

A bounded audit recovered 75 legal placements from 128 eligible disjoint
pairs (58.6%), with mean clock confidence 0.903 and 19 enabled non-spell cards.
A second 256-pair audit on the older coordinate-bearing shard recovered 192
placements. Its direct-label match rate was only 47.8% because that source has
repeated corrupted sentinel coordinates; visual before/after inspection shows
the recovered clock exactly at the newly appearing troop/building while the
disagreeing legacy label often points at an unrelated clock or empty tile. On
the first less-corrupted 32-pair slice, median pixel disagreement was one pixel
and tile agreement was 82.4%.

The full disjoint recovery produced 3,537 legal placements from 310 replays,
with mean confidence 0.905 and 51 enabled non-spell cards. Its artifact is
`datasets/tv_royale_human_clock_expanded_v1.npz`, SHA-256
`09b48fe60d89c7f0a7a3d2faeca9a2a0985875c19d838a93404a9d2000a81314`.
Applying the same method to the older shard produced another 869 placements
from 86 replays, SHA-256
`568013a7ad24773c944b81a0504a5f4c229d4cde2ba93c9a4badccc9352dc539`;
the median disagreement with its direct label was only 1.41 pixels despite the
known corrupted tail. Complete-replay merging yields 4,406 legal finite rows
from 396 replays and 948 sequence-four chunks in
`datasets/tv_royale_human_clock_combined_v1.npz`, SHA-256
`646f935f215533060d750d43f3cbeb1f31cf0ac34155dc07f8deab33b0c709c1`.

An eight-update spatial-only pilot changed exactly the intended 669,504
parameters and no others. It reduced two fixed location losses from
10.6852/10.5140 to 9.9378/9.7649, but its replicated gameplay record was
24-24 versus the clean parent and 22-26 versus safety, so the raw checkpoint
was rejected. A safety-heavy consolidation retained most of that signal at
update 12 (10.0080/9.8400), beating safety 27-21 but losing to the parent
22-26. Neither unblended checkpoint is promoted.

A 50% interpolation of consolidated update 12 back toward the clean student
retains a 3.2% matched human-placement loss improvement. Across two independent
24-game direct blocks it ties the clean parent exactly 24-24 and beats the
safety champion 27-21 with +0.292 crowns per game. On the established fixed
60-game breadth screen it is record-exact to the clean student at 47-13:
broad random 9-3, Hog random 12-0, balanced 4-2, reactive-defense 4-2,
bridge-pressure 4-2, slow-push 5-1, spell-control 5-1, and split-lane 4-2.
The checkpoint is
`checkpoints/human_safety_student6m_tvclock_spatial_rescue_seed1026001/policy_v2_update_000012_alpha050.pt`,
SHA-256
`59dd7f214ee04c3be4cd64642cfa1c5e9ba5ca1e82d1484ff0f1704eb6f679cd`.
It is promoted as the new provisional launch point: it preserves measured
breadth, improves the safety boundary, and adds a real human placement signal.
A low-rate full-policy hard-league calibration now tests whether card choice,
waiting, recurrence, and defense can improve without losing those gates.

That full-policy calibration completed eight updates and 32,768 additional
transitions without instability. Update 20 retains a 6.3% matched human
placement-loss improvement (10.0137/9.8409 versus 10.6852/10.5140). Across
replicated 24-game blocks it ties the promoted blend 24-24 with +0.083 crowns
per game and beats the safety champion 30-18 with +0.438. Fresh direct screens
also beat the original clean student 14-10 and the human-data champion 15-9.
The fixed breadth screen remains 47-13 overall; it exchanges one spell-control
win for one split-lane win while improving the Hog-random and balanced crown
margins. The checkpoint is
`checkpoints/human_safety_tvclock_blend_fullrl_seed1027001/policy_v2_update_000020.pt`,
SHA-256
`2fe7dc475277cd4bcd13d799cd6600cf7f5c9080a79b348b2fcbdaf2d432287d`.
It supersedes the blend as the accepted policy. A half-rate continuation now
uses update 20 itself as the anchor; every later checkpoint must re-clear the
same parent, safety, human, and breadth boundaries.

The half-rate fixed-league continuation completed through update 28 without
optimizer instability (maximum observed anchor policy KL 0.00060 and zero
clipped samples through the saved update-24 boundary). The additional learning
continued to improve the two fixed human-clock location losses: update 24
scored 9.8982/9.7292 and update 28 scored 9.7315/9.5687, versus
10.0137/9.8409 at accepted update 20. Gameplay did not improve monotonically.
Update 28 tied update 20 12-12 but lost 11-13 to safety and is rejected.
Update 24 initially scored 13-11 against each boundary, but independent
replication scored 12-12 against update 20 and 10-14 against safety. Aggregate
records are therefore 25-23 versus update 20 and 23-25 versus safety, which is
insufficient for promotion. A 50% interpolation retains intermediate human
losses of 9.9560/9.7851 and tied both update 20 and safety 12-12 on its first
fresh blocks; it remains only a research candidate because no gameplay gain is
demonstrated. Update 20 remains the accepted checkpoint.

The next isolated phase changes the source of pressure rather than extending
the stagnant fixed league: both seats train under the current policy in
parallel self-play, with update 20 frozen as the L2/KL anchor and the same
human-clock location rehearsal. This tests adaptive counterplay while retaining
the established anti-forgetting boundary. It is a candidate-generating phase,
not promotion evidence; saved checkpoints still require fresh update-20,
safety, human-reference, and fixed-breadth gates.

The bounded self-play phase completed eight updates and 65,536 transitions with
stable optimization (final PPO KL 0.00008, clip fraction 0.001, and anchor
policy KL 0.00099). Update 28 tied update 20 12-12 and beat safety only 13-11,
so update 24 was the sole expanded candidate. Across two independent 24-game
blocks, update 24 scored 25-23 against update 20 with +0.125 crowns per game
and 25-23 against safety with +0.083. It also retained a small human-location
loss improvement at 9.9123/9.7325 and scored 15-9 against the human-data
reference. The exact fixed breadth screen nevertheless fell one broad-random
game: 46-14 overall instead of 47-13, with every other component record
unchanged. The raw checkpoint is rejected.

A 50% interpolation restored the exact broad-random 9-3 result and tied update
20 12-12, but lost 9-15 to safety on its fresh block. It is rejected without
replaying the already-exact remaining breadth components. Adaptive self-play
did produce a transferable but narrow offensive direction; neither its raw nor
interpolated policy preserves the authoritative safety/breadth boundary. The
accepted checkpoint therefore remains update 20.

The expanded clock corpus contains only verified deployment moments, so it can
supervise human card choice without importing the no-op-heavy timing labels
that collapsed earlier mixed imitation. Two isolated fits froze every parameter
except the shared action-type head. A one-epoch fit improved held-out action-
type loss but only tied update 20 and safety 12-12. A three-epoch sibling from
the unchanged update-20 initialization reduced its disjoint held-out action-
type loss from 1.4069 to 1.3362 and reached 47.61% held-out slot accuracy.

The three-epoch candidate cleared replicated gameplay gates. Across two fresh
24-game blocks it ties update 20 exactly 24-24 and beats the safety champion
27-21, with positive safety crown margins in both blocks. Its authoritative
fixed matrix is outcome-exact at 47-13: broad random 9-3, Hog random 12-0,
balanced 4-2, reactive-defense 4-2, bridge-pressure 4-2, slow-push 5-1,
spell-control 4-2, and split-lane 5-1. On a matched human-reference block, both
the candidate and update 20 score 13-11; the candidate's crown margin is
+0.208 per game versus +0.167. The checkpoint is
`checkpoints/human_safety_tvclock_typehead_seed1030002/epoch3.pt`, SHA-256
`35815b78c967cbb8a6cdff4ceac55e0bc9c30c14817c6d6ef2a7ac4cf7c12b8d`.
It supersedes update 20 as the accepted policy because it preserves every
measured parent and breadth outcome, improves the direct safety boundary, and
adds a disjoint human card-choice signal through a globally shared head.

A low-rate hard-league consolidation now starts from this checkpoint with the
accepted policy itself as both L2 and forward-KL anchor. Human rehearsal remains
location-only during PPO, so the new card-choice signal is protected by the
behavior anchor rather than repeatedly optimized without no-op counterexamples.

The hard-league consolidation completed eight updates without numerical
instability but produced no promotable improvement. Update 24 tied the accepted
policy 12-12 and lost 11-13 to the safety champion. Update 28 again tied the
accepted policy 12-12 and tied safety 12-12. Neither checkpoint improves the
accepted boundary, so both are rejected and the action-type-head checkpoint
remains the rollback point.

### Explicit human deployment timing

The placement-only clock corpus cannot distinguish a deliberate wait from an
unobserved action, so the next phase imports the source dataset's explicit
`card=None` frames. The converter accepts only authored `None` labels at offset
zero with a complete four-card hand entirely inside the enabled-deck vocabulary;
all ambiguous, incomplete, or out-of-scope rows fail closed. The same pinned
KataCR detectors produce the public entity table, and the shared action-space
builder supplies the legal no-op target rather than a card-specific rule.

Arena 21 yielded 100 valid waits from nine replays in
`datasets/tv_royale_human_noop_arena21_v1.npz`, SHA-256
`f6ae897b345410ad67d3ce839f7035b041792979cdb428b35a7d6028c2919fc7`.
Arena 23 added 514 waits from 33 replays in
`datasets/tv_royale_human_noop_arena23_v1.npz`, SHA-256
`7057170436763ea532b999cb27f83547ffb404017e736a33010e4825f8570bfb`.
Combining these 614 nonduplicated waits with all 4,406 verified deployment
moments creates 5,020 samples across 438 complete replay episodes in
`datasets/tv_royale_human_timing_expanded_v1.npz`, SHA-256
`d18772d02e91a74e0460bf340195f13bde6a34474f510dd1222ea2a16fb2291a`.

The timing experiment again freezes every parameter except the globally shared
action-type head. Rates `1e-6` and `3e-6` improved held-out loss but remained
behaviorally indistinguishable from the accepted policy on paired gameplay.
A single epoch at `1e-5` reduced its matched held-out type loss from 1.6394 to
1.5679 and produced a small measurable increase in deliberate waiting without
changing card, location, recurrent, value, or strategy parameters.

The resulting checkpoint clears the complete promotion gate. Across two fresh
24-game direct blocks it ties the previous champion exactly 24-24. The fixed
60-game matrix remains exactly 47-13 with the same +1.2667 crowns per game:
broad random 9-3, Hog random 12-0, balanced 4-2, reactive-defense 4-2,
bridge-pressure 4-2, slow-push 5-1, spell-control 4-2, and split-lane 5-1.
Playable no-op rises from 72.20% to 73.75% on that matrix. On the matched
human-reference block it preserves the exact 13-11 record and +0.208 crown
margin while reducing mean incoming danger from 0.0646 to 0.0628, improving
board-value edge from +0.0095 to +0.0146, and raising playable no-op from
73.53% to 73.90%. A matched safety replication also preserves 13-11 while
slightly lowering mean danger and improving board edge.

The promoted checkpoint is
`checkpoints/human_safety_tvclock_timing_expanded_seed1032008/epoch1.pt`,
SHA-256
`cea86f3975a4ce8cc64467a4860ea20447e8089398098777f18048f0615678d4`.
The former action-type checkpoint remains the immediate rollback. This
promotion is narrow: it adds verified human wait/deploy timing while preserving
every authoritative measured outcome; it does not by itself establish
mid-ladder-human playing strength.

The online trainer now supports a third recurrent rehearsal component,
`type`, which supervises deploy/wait/card-slot action type on every informative
expert row while retaining complete episode-contiguous sequences. Unlike the
existing joint and location modes, it includes explicit no-op targets. Direct
tests prove that no-op-only sequences are retained, while joint/location
behavior remains unchanged. The expanded timing corpus supplies 1,086 valid
sequence-four chunks for this objective.

An initial eight-update mixed-league pilot accidentally inherited absolute
resume-update LR annealing, reducing its effective rate from `6.48e-7` to
`2.5e-7`; it tied the parent but regressed from 14-10 to 13-11 on a matched
safety block and is rejected. The corrected constant-rate run used `2.5e-6`,
64 environments, 12 CPU actors, an MPS learner, the accepted checkpoint as
both L2 and forward-KL anchor, and a `0.0005` type-rehearsal coefficient.
Optimization remained stable through update 28: maximum observed anchor KL
was 0.00083, clipping stayed effectively zero, and the weighted rehearsal loss
remained between 0.0008 and 0.0011.

Raw update 24 lost 10-14 to safety and is rejected. Raw update 28 produced a
useful but entangled direction: it scored 25-23 against the accepted parent,
but 27-21 against safety where the parent scored 28-20 on identical seeds.
A 50% interpolation improved fresh gates to 25-23 versus the parent and 27-21
versus safety, compared with the parent's 26-22 safety record. It also improved
the authoritative breadth matrix from 47-13 to 48-12 by moving split-lane from
5-1 to 6-0 while preserving every other component record.

The blend nevertheless fails the human-reference boundary. Across two matched
24-game blocks it totals 27-21, one game below the accepted parent's 28-20.
Safer 25% and 10% interpolations still flip the same first-block game and score
12-12 instead of 13-11. All raw and interpolated PPO candidates are therefore
rejected. The experiment establishes that explicit timing rehearsal prevents
obvious action-type forgetting and can expose a breadth-improving RL direction,
but the current full-policy update remains too coupled to preserve the human
boundary. The accepted checkpoint remains
`checkpoints/human_safety_tvclock_timing_expanded_seed1032008/epoch1.pt`.

A follow-up isolated-policy experiment added a zero-initialized 64-unit repair
adapter and froze the entire 6.17M-parameter accepted backbone. Only 187,078 new
adapter parameters received PPO and timing-rehearsal gradients. This increased
training throughput from about 95 transitions/s for full-policy recurrent
rehearsal to 218-235 transitions/s while preserving exact initialization.

The adapter rate sweep did not produce a promotable policy. Eight updates at
`1e-5` remained behaviorally identical to the parent across two direct and two
matched safety blocks. Continuing four updates at `3e-5` again tied the parent
12-12 and exactly matched its 13-11 safety result on identical seeds. A `1e-4`
continuation crossed the safe boundary: update 32 lost 9-15 to safety and update
36 lost 10-14. All adapter checkpoints are rejected. This closes the simple
dense-residual rate sweep; future isolated strategy work needs a stronger
training signal or state-conditioned gating, not a larger unstructured logit
perturbation.

### Chronological TV Royale timing repair

An exact provenance audit found that the first expanded timing corpus was not
actually nonduplicated or chronological. All 100 accepted arena-21 wait rows
were contained in arena 23, arena 23 itself contained 39 repeated converted
frames, and the deployment-only and wait-only episodes had merely been
concatenated. Exact episode/sample deduplication corrects the old 5,020-row
artifact to 4,881 labels across 429 episodes. The corpus combiner now removes
repeated frames only within a replay and removes cross-source data only when an
entire ordered episode is exactly duplicated, avoiding false matches between
different games.

The larger pinned `Nones_arena_28.parquet` source is 5,131,151,109 bytes with
local SHA-256
`e68053ea3b54b1ae75feeec90fe6850df805254c5cf854137dd78d1bc1a724a0`.
Fail-closed filtering and the pinned KataCR detectors recovered 2,745 unique
in-vocabulary waits from 199 replays in
`datasets/tv_royale_human_noop_arena28_v1.npz`, SHA-256
`7ab458684f4e6c4b2771347f8f04c6089bad39dca85d246c9d31884fc657f15b`.
The overlapping arena-28 deployment rebuild rejected 37 replay/frames carrying
two conflicting card labels before inference, then recovered 1,074 verified
deployment-clock labels from 117 replays in
`datasets/tv_royale_human_clock_arena28_provenance_v1.npz`, SHA-256
`38e3b334a4803f0c7c27943ac516497ed0cf067f39ccf5650cd279a0089401ef`.
Both artifacts retain source replay and frame arrays.

The chronological join found 368 frames where the weak `card=None` source
contradicted a paired before/after frame with a newly detected deployment
clock. A fully fail-closed artifact is retained for audit. The training corpus
uses an explicit `prefer-first` policy with the verified clock source first;
every conflict remains counted in its manifest rather than silently resolved.
It contains 1,357 strictly frame-ordered decisions across 64 genuinely mixed
replays: 730 deployments and 627 waits, with median episode length 18. The
artifact is
`datasets/tv_royale_human_chronological_arena28_clockfirst_v1.npz`, SHA-256
`248e281e1a97d8d624fa4c470dd939316bb896c9b4175bf6c3d6372aa44e789c`.

One sequence-eight epoch again froze every parameter outside the shared
action-type head. The `3e-5` and `1e-4` fits tied the accepted parent 6-6
directly, while raw rates `1e-5`, `3e-5`, and `1e-4` all flipped the same
matched safety block from the parent's 7-5 to 6-6. All raw fits are rejected.
A 50% interpolation of the `1e-5` fit restores the exact parent behavior at
the complete promotion boundary while retaining a small chronological
human-likelihood gain. Its recurrent
full-episode joint NLL improves from 8.67725 to 8.64449, and it changes one of
1,357 deterministic human-corpus decisions. Exactly four tensors differ, all
inside `action_type_head`; every encoder, recurrent, spatial, critic, and value
tensor remains bit-identical.

The blend ties the parent 12-12 in 24 direct games. On the matched 24-game
safety block, candidate and parent are exactly identical at 12-12 with +0.042
crowns/game and identical danger, board edge, and action rates. On the matched
human-reference block, both score 15-9 with +0.708 crowns/game and identical
secondary metrics. The fixed 60-game breadth matrix is also exact at 47-13:
broad random 9-3, Hog random 12-0, balanced 4-2, reactive-defense 4-2,
bridge-pressure 4-2, slow-push 5-1, spell-control 4-2, and split-lane 5-1.

The promoted checkpoint is
`checkpoints/human_safety_tvseq_clockfirst_typehead_lr1e5_seed1035007/epoch1_alpha050.pt`,
SHA-256
`95a61b5f2049c43f59452471621f38ca001ab14ba2afaad6b12f8b08ce71a2cb`.
The former timing checkpoint remains the immediate rollback at SHA-256
`cea86f3975a4ce8cc64467a4860ea20447e8089398098777f18048f0615678d4`.
This is a deliberately narrow promotion: it replaces contaminated homogeneous
timing supervision with independently verified chronological human evidence
without changing any measured gameplay boundary. It is not evidence of
mid-ladder-human strength. The full repository suite passes 1,126 tests.

### Current-champion sequence distillation and recurrent-core promotion

The first recurrent-core PPO probe exposed a useful failure boundary rather
than a promotion. Only `recurrent_input_projection`, `memory`, and
`action_type_head` were trainable at `1e-6`, with the accepted chronological
checkpoint as both L2 and forward-KL anchor. Update 24 tied the established
safety and human-reference blocks but scored 11-13 directly against its
parent. Update 28 then fell from 12-12 to 11-13 on the safety block. Both PPO
checkpoints are rejected.

The initial safety-heavy supervised experiment was also rejected because its
behavior labels came from the older safety champion. Raw, 50%, and 25% blends
all crossed the same matched 12-game safety boundary from 7-5 to 6-6. This
showed that action-label rehearsal alone was not a sufficient preservation
contract for the current policy.

The replacement pipeline collects the current accepted checkpoint's own
recurrent behavior against random and all six deterministic strategy bots.
Each source contains 10,000 decisions at decision interval four. The seven
sources are deterministically combined by complete episode with all 1,357
chronological human rows. Mixed capture intervals are now explicit: every
source record retains its interval and combined metadata uses interval zero
only when the source episodes are heterogeneous. The resulting 18,975-row,
94-episode corpus is
`datasets/tvseq_current_champion_type_rehearsal_v1.npz`, SHA-256
`5c00460757aaea83c05b33a2f8879e8e6b562d0cdfe681fccaaaa0a2d3b6558e`.

The supervised sequence fitter now accepts repeatable trainable parameter
prefixes and an initial-policy forward-KL term. One sequence-eight epoch at
`3e-6`, with KL coefficient 10 and left/right augmentation, improved held-out
action-type accuracy from 83.50% to 89.58% and loss from 0.47755 to 0.45410.
The raw fit and blends through 50% still failed the narrow safety screen. A
12.5% interpolation restored its exact outcome and secondary metrics. On full
recurrent episodes, the safe blend improves chronological human joint NLL
from 8.64449 to 8.62830 and mixed-rehearsal NLL from 0.67655 to 0.67519. It
changes eight deterministic actions in each corpus without changing exact
accuracy.

The safe blend ties its parent 12-12 in 24 direct games. It exactly retains the
24-game safety result at 12-12 with +0.042 crowns/game and the human-reference
result at 15-9 with +0.708 crowns/game, including identical secondary metrics.
The fixed breadth matrix improves from 47-13 to 48-12: broad random 9-3, Hog
random 12-0, balanced 4-2, reactive-defense 4-2, bridge-pressure 5-1 (up from
4-2), slow-push 5-1, spell-control 4-2, and split-lane 5-1.

The promoted checkpoint is
`checkpoints/human_safety_tvseq_currentteacher_strategycore_lr3e6_kl10_seed1036007/epoch1_alpha0125.pt`,
SHA-256
`8f4dbe10b4bba8b90c4b156712c45c413f69b987f183d4119feae758991a6286`.
The prior chronological action-head checkpoint remains the immediate rollback
at SHA-256
`95a61b5f2049c43f59452471621f38ca001ab14ba2afaad6b12f8b08ce71a2cb`.
This is the first accepted recurrent-core change in this lineage and a one-game
breadth improvement, not yet evidence of mid-ladder-human strength. Ruff and
module mypy are clean, and the full repository suite passes 1,127 tests.

### Anchored spatial-strategy PPO continuation

A four-update PPO continuation starts from the promoted recurrent-core blend
and expands the trainable scope only to the recurrent input/memory,
action-type head, action-type embedding, memory-to-tile conditioning, tile
decoder, and tile key. The promoted checkpoint is the L2 and forward-KL anchor.
Joint recurrent rehearsal uses the current-champion/human corpus at sequence
length eight. The run uses `1e-6`, defense-v2, 64 environments, 12 CPU actors,
and an MPS learner. Through update 24, forward KL stays near `1e-5`, clip
fraction stays zero, and no optimizer instability appears.

Update 24 ties its parent 12-12 in the matched 24-game direct block. It exactly
retains the 12-12 safety result at +0.042 crowns/game and the 15-9
human-reference result at +0.708 crowns/game. The fixed breadth matrix remains
48-12 with component records 9-3 broad random, 12-0 Hog random, 4-2 balanced,
4-2 reactive-defense, 5-1 bridge-pressure, 5-1 slow-push, 4-2 spell-control,
and 5-1 split-lane.

The spatial continuation improves full-recurrent chronological human joint NLL
from 8.62830 to 8.59900, changing 14 deterministic actions without changing
human exact accuracy. Mixed-rehearsal joint NLL improves from 0.67519 to
0.67330; exact accuracy changes by one of 18,975 samples while the gameplay
gates remain exact.

The promoted checkpoint is
`checkpoints/human_safety_tvseq_spatialcore_rl_lr1e6_seed1036008/policy_v2_update_000024.pt`,
SHA-256
`f98553a74300421437aaccaba5221563055c25c442b7e33695265b8747667a58`.
The recurrent-core blend at SHA-256
`8f4dbe10b4bba8b90c4b156712c45c413f69b987f183d4119feae758991a6286`
is the immediate rollback. This promotion improves the continuous human and
rehearsal objectives while preserving all established deterministic gameplay
records; it still does not establish mid-ladder-human strength.

Four more updates use update 24 itself as the rolling L2/KL anchor. Update 28
again ties the champion 12-12 directly, exactly retains the 12-12 safety block
and 15-9 human-reference block, and preserves the complete 48-12 breadth
matrix. Within that fixed matrix, its balanced-strategy crown margin returns
from update 24's +0.167 to +0.333 while all component win/loss records remain
unchanged.

Update 28 improves chronological human recurrent joint NLL from 8.59900 to
8.56439 with unchanged exact accuracy and 12 changed deterministic actions.
Mixed-rehearsal NLL improves from 0.67330 to 0.67084; exact accuracy improves
by two samples and 14 deterministic actions change. The new promoted
checkpoint is
`checkpoints/human_safety_tvseq_spatialcore_rl_lr1e6_seed1036008/policy_v2_update_000028.pt`,
SHA-256
`bf9c4d44b015c67c03c56c5a56f657fbb05c9477a86b9515f462e2833c978012`.
Update 24 at SHA-256
`f98553a74300421437aaccaba5221563055c25c442b7e33695265b8747667a58`
is the immediate rollback.

The next rolling-anchor block reaches raw update 32. It improves human joint
NLL to 8.52489 and mixed-rehearsal NLL to 0.66829, but regresses the fixed
bridge-pressure component from 5-1 to 4-2. A 50% interpolation retains that
regression. Both are rejected.

A 25% interpolation of update 32 into update 28 restores bridge-pressure 5-1
and clears the complete promotion boundary: 12-12 directly, 12-12 versus the
safety champion, 15-9 versus the human reference, and 48-12 across the fixed
breadth matrix with every component record retained. Compared with update 28,
the safe blend improves chronological human recurrent joint NLL from 8.56439
to 8.55448 and mixed-rehearsal NLL from 0.67084 to 0.67020. Exact accuracy is
unchanged and only two deterministic actions change in each corpus.

The promoted checkpoint is
`checkpoints/human_safety_tvseq_spatialcore_rl_lr1e6_seed1036008/policy_v2_update_000032_alpha025.pt`,
SHA-256
`a4c3d351cff49a1491da96f730753596b1d02e45794e20c24c78e15038d82b3a`.
Raw update 32 is rejected; update 28 at SHA-256
`bf9c4d44b015c67c03c56c5a56f657fbb05c9477a86b9515f462e2833c978012`
is the immediate rollback.

### Expanded TV Royale chronology and spatial imitation promotion

The next data audit uses the official `new_arena_placement.parquet` shard
(2,063,054,974 bytes, SHA-256
`2baebe75e0ae6ad09c0cdd4ec708a55115b50c5b0bd4004d19167015fedbab4e`).
It contains 2,312 paired before/after moments across 88 replays and arenas
21--24. The existing conservative vocabulary, hand, card-type, conflict, and
legal-placement filters leave 1,227 candidate deployment pairs. A 128-pair
MPS audit recovers 96 deployment clocks with mean confidence 0.910; visual
inspection confirms that the recovered clock identifies the actual new unit
in the after-frame, including cases where the upstream direct coordinate is
wrong.

The full two-detector import retains 806 high-confidence non-spell placements
across 86 replays: 113 from arena 21, 155 from arena 22, 234 from arena 23,
and 304 from arena 24. The artifact is
`datasets/tv_royale_human_clock_arenas21_24_v1.npz`, SHA-256
`b4d26aa72dcf51eab78a5e67e6cbadd14027bf25e82d796ce82b2ec747a605fd`.
Chronological merging with the existing explicit-wait corpus produces 645
decisions (366 waits and 279 deployments) in 46 mixed-action replay episodes;
308 same-frame action conflicts are dropped rather than guessed. This corpus
is `datasets/tv_royale_human_sequence_newarenas_v1.npz`, SHA-256
`dee321c1e2f3e35767b18cc4a5f13acc3a42712ef8eb341b9bd0b3a15c672a7a`.

Combining it with the prior clock-first human sequences expands verified
chronological human coverage from 1,357 to 2,002 decisions across 110 episodes
(+47.5%). The combined human artifact is
`datasets/tv_royale_human_chronological_expanded_v1.npz`, SHA-256
`61e4e08c75ccf5e313a5a09b1ac9bcf24175ab8062b824a568e0cdfc5a8eff2d`.
Adding only these complete episodes to the current-champion rehearsal produces
a 19,620-row, 140-episode mixed-clock corpus at
`datasets/tvseq_current_champion_expanded_human_v1.npz`, SHA-256
`45c9730a824f34682ceaa6aebb48fa4520044a69e07041e1f933e44973f4fb26`.

One spatial-v1 imitation epoch starts from the update-32 safe blend at `3e-6`
with sequence length eight, left/right augmentation, and forward-KL
coefficient 10. The actor encoders and critic remain frozen. Only the
recurrent input/memory, previous-action embeddings, action-type head, and
spatial tile/card decision modules are trainable. Raw held-out factorized loss
improves from 3.0451 to 2.7267, but the raw model changes too many discrete
actions to promote directly. Interpolation screening selects 12.5% of the
supervised delta.

The safe blend improves full-recurrent NLL on the expanded 2,002-decision
human set from 8.5352 to 8.4037, with unchanged exact and action-type accuracy
and 44 changed deterministic actions. On the original 1,357-decision human
set, NLL improves from 8.5545 to 8.4166 with both accuracies unchanged. On the
18,975-row current-policy rehearsal set, NLL improves from 0.67020 to 0.65982;
action-type accuracy is unchanged and exact accuracy changes by only two
samples.

All promotion games were rebaselined under the current simulator code. The
candidate ties the champion 12--12 directly and is exactly identical over the
24-game safety block at 12--12, -0.083 crowns/game, including every non-timing
metric. It retains the 15--9 human-reference block at +0.708 crowns/game. The
current 60-game breadth baseline is 45--15; the candidate improves it to
46--14. Component records are 9--3 broad random, 10--2 Hog-seed random, 4--2
balanced, 4--2 reactive-defense, 5--1 bridge-pressure, 4--2 slow-push, 5--1
spell-control, and 5--1 split-lane. The one-game improvement is slow-push
3--3 to 4--2; all other component records are retained.

The promoted checkpoint is
`checkpoints/human_safety_tvseq_expanded_spatial_imitation_lr3e6_kl10_seed1037006/epoch1_alpha0125.pt`,
SHA-256
`27bda27f8bd0e94e3c5b94bd1772b05d65749e1a6167364d523b81887504e322`.
The previous update-32 safe blend at SHA-256
`a4c3d351cff49a1491da96f730753596b1d02e45794e20c24c78e15038d82b3a`
is the immediate rollback. `scripts/evaluate_recurrent_corpus.py` makes the
full-episode recurrent likelihood gate reproducible. Ruff and module mypy are
clean, `git diff --check` is clean, and the full repository suite passes 1,127
tests. This is a measured human-likelihood and one-game breadth improvement;
it is still not evidence of mid-ladder-human strength.

### Expanded-rehearsal PPO update 36 rejection

A four-update PPO probe resumes from the expanded-human spatial-imitation
champion and uses that checkpoint as both the L2 and forward-KL anchor. The
rehearsal corpus is upgraded to the 19,620-row expanded human/current-policy
mix. The trainable scope, `1e-6` learning rate, 64 environments, 12 CPU
actors, MPS learner, and 12-member strategy/frozen-policy league otherwise
match the accepted spatial PPO recipe. Training is numerically stable through
update 36: rollout forward KL remains at or below `5e-5`, clip fraction is
zero, all 32 optimizer steps run per update, and the checkpoint reaches
147,456 transitions.

Raw update 36 improves expanded-human recurrent NLL from 8.4037 to 8.3593
with unchanged exact accuracy, but it regresses the full human-reference block
from 15--9 to 14--10 and is rejected. A 50% interpolation restores the human
block to 15--9 and retains both 12--12 direct and 12--12 safety results. It
also improves human NLL to 8.3814 with only nine changed deterministic replay
actions. However, the complete breadth matrix falls from 46--14 to 45--15:
slow-push regresses from 4--2 to 3--3. The 25% and 12.5% interpolations cross
the same slow-push boundary and also score 3--3. The entire PPO direction is
therefore rejected rather than promoted for a likelihood-only gain.

Raw update 36 SHA-256 is
`ab4885a4d88479c1c4b8f83308dfd2a192adeeb71a82d5124f02c27633d67439`;
the rejected 50%, 25%, and 12.5% blends are respectively
`b5cf54a1c250851b9e5372279705cb8a26ab78f7b73ecf867ddc70aac52cf25d`,
`cc10a219adc63c0f8edce1e744151bdd1e1d7ec7f5bc9daafa4e5a05c165cbd4`,
and
`6e4339e383146cab4146cda02e3a16e8ac5e66ea837d1cfab77c6b3540e17a94`.
The promoted checkpoint remains the expanded-human spatial-imitation 12.5%
blend at SHA-256
`27bda27f8bd0e94e3c5b94bd1772b05d65749e1a6167364d523b81887504e322`.

### Arena 29 chronology expansion and guarded spatial promotion

The official TV Royale Arena 29 pass adds independently recovered action
timing rather than treating placement screenshots as a homogeneous action
stream. The two-detector deployment-clock import retains 1,376 placements
from 115 replay episodes at mean clock confidence 0.906; its artifact is
`datasets/tv_royale_human_clock_arena29_v1.npz`, SHA-256
`be77c4bfcd6c1d1165c7bdd32c2aa1a1ee0440e4ba78ff80627ce2b864c60c10`.
The matching provenance-preserving no-op import contains 3,983 decisions from
274 replay episodes at
`datasets/tv_royale_human_noop_arena29_provenance_v1.npz`, SHA-256
`ed7215e94394307b539a048c06d8f18e619b3c05ac73381b073555d56782b495`.

Merging only the 74 replays shared by both sources, with verified deployment
clocks taking precedence on the 528 same-frame conflicts, produces 1,766
strictly chronological decisions across 72 genuinely mixed-action episodes:
1,067 deployments and 699 waits. The artifact is
`datasets/tv_royale_human_sequence_arena29_v1.npz`, SHA-256
`fdd440d96c3ea111c529436c121e1065cfea9d654648c37c5a01dfefd4fc7f13`.
Whole-episode deduplication expands the human chronology from 2,002 to 3,768
decisions across 182 episodes at
`datasets/tv_royale_human_chronological_expanded_v2.npz`, SHA-256
`b5e1a7be7683ec5ea171ac2126f9db4d2535c52b096e965c8da2cc957471e4a7`.
The protected current-policy/human rehearsal expands from 19,620 to 21,386
decisions across 212 episodes at
`datasets/tvseq_current_champion_expanded_human_v2.npz`, SHA-256
`2b6e916c1c6785843d5308349ff502f3db5f91b4714c25940d8c7f0603f5b165`.
No duplicate episode is retained in either combined corpus.

The first MPS fit at seed 1,037,013 exposed a fail-open trainer bug: a
non-finite optimizer path made every trainable tensor NaN, but the fitter
still exited zero and wrote a checkpoint. That artifact is rejected. The
fitter now raises before an optimizer step on a non-finite scalar loss or
clipped gradient norm, and a focused regression test forces this boundary.
Eight imitation tests pass; Ruff and module mypy are clean. The guarded rerun
at seed 1,037,014 completes one spatial-v1 epoch at learning rate `3e-6`,
sequence length eight, left/right augmentation, and forward-KL coefficient
10. It starts from the previous promoted checkpoint and trains only the
recurrent input/memory, previous-action embeddings, action-type head, and
spatial tile/card decision modules. Held-out factorized loss improves from
2.86924 to 2.47365. The raw fit remains too large for direct promotion.

Initial interpolation screening used an erroneous 3,000-tick evaluation cap,
half the 6,000-tick regulation match length. Those draw-heavy matrices are
discarded and are not promotion evidence. They nevertheless exposed a
bridge-pressure behavioral boundary at 12.5%, so 6.25% was the largest blend
advanced to the correctly rerun gates. Every promotion game below uses the
full 6,000-tick horizon and rebaselines the parent under the same current code.

At regulation length, the candidate is exactly identical to its parent on the
24-game direct block at 12--12, the 24-game safety block at 12--12, and the
24-game human-reference block at 15--9, including every secondary metric. The
complete 60-game breadth matrix is also outcome-identical at 48--12: broad
random 9--3, Hog random 12--0, balanced 4--2, reactive-defense 4--2,
bridge-pressure 5--1, slow-push 5--1, spell-control 4--2, and split-lane 5--1.
Secondary differences are narrow: four fewer threatened decisions and
marginally lower mean danger in the Hog block, a one-third-tick shorter mean
spell-control game with slightly better board edge, and negligible mean-danger
roundoff in broad random. No gate regresses.

On the expanded 3,768-decision human chronology, recurrent joint NLL improves
from 8.47439 to 8.38777; exact accuracy rises from 0.00292 to 0.00318 and
action-type accuracy rises from 0.27309 to 0.27362, with 19 changed
deterministic actions. On the original 2,002-decision human set, NLL improves
from 8.40370 to 8.31867 and both exact and action-type accuracy rise, with 11
changed actions. On the 18,975-row current-policy rehearsal, NLL improves from
0.65982 to 0.65348 while exact and action-type accuracy are unchanged and only
five deterministic actions change.

The promoted checkpoint is
`checkpoints/human_safety_tvseq_expanded_v2_spatial_imitation_lr3e6_kl10_seed1037014/epoch1_alpha00625.pt`,
SHA-256
`5ae31cd3e1dc302ff7b7f1a5c8178126d02f8b247a2b74eff495fbf4e51f2b47`.
The previous expanded-human spatial checkpoint at SHA-256
`27bda27f8bd0e94e3c5b94bd1772b05d65749e1a6167364d523b81887504e322`
is the immediate rollback. The full repository suite passes 1,127 tests.
This is a guarded human-likelihood promotion with measured behavioral
preservation; it is not evidence of mid-ladder-human playing strength.

### Arena 31 location-only follow-up rejection

Arena 31 has no overlapping verified wait stream, so it is kept strictly out
of deploy-versus-wait timing supervision. The same two-detector clock recovery
retains 952 placements across 77 replays at mean confidence 0.902. The artifact
is `datasets/tv_royale_human_clock_arena31_v1.npz`, SHA-256
`32dd68039efbcce8631feefe49e5196f95baa455103fae5290e34504a9033f6b`.
Whole-episode combination with the protected rehearsal yields 22,338 rows and
289 episodes at
`datasets/tvseq_current_champion_expanded_human_arena31_spatial_v1.npz`,
SHA-256
`edff74f41ffcba4ce50900362a52ece26a153dc7ee2dc325d6b70affed9fb884`.

One guarded placement-only epoch freezes the recurrent input, memory,
previous-action, and action-type pathways. Only `memory_tile_film`,
`tile_decoder`, `tile_key`, `card_query`, and `location_bias` are trainable.
The raw fit improves held-out placement loss from 9.427 to 7.554, but useful
blend sizes trade away current-policy rehearsal exact or action-type labels.
At 3.125%, current-policy exact accuracy loses two rows and action-type
accuracy loses one. Halving to 0.78125% still loses one exact and one
action-type row; 0.390625% restores action-type accuracy but still loses one
exact row. The first blend with completely unchanged rehearsal accuracy is
0.1953125%, but it changes no Arena 31 deterministic action and leaves all
Arena 31 exact and distance accuracies unchanged; only NLL moves from 10.44625
to 10.44125. That is insufficient evidence of an actual placement improvement.
The entire Arena 31 location-only direction is therefore rejected for now,
and the regulation-gated Arena 29 checkpoint remains promoted.

### Lower-step PPO probe and dual-corpus preservation follow-up

A four-update mixed-league probe resumed the Arena 29 champion at learning
rate `5e-7`, with L2 coefficient `0.01`, rollout-state anchor KL coefficient
`0.2`, and recurrent rehearsal coefficient `0.002`. It consumed 16,384 new
transitions through update 36. Optimization remained finite, used every
scheduled optimizer step, kept printed PPO KL at or below `1e-5`, and finished
7--5 over the twelve completed training episodes. Raw update 36 is
`checkpoints/human_safety_tvseq_expanded_v2_rl_lr5e7_reh002_seed1037018/policy_v2_update_000036.pt`,
SHA-256
`908fe14b9d88bdf304f89cd51a8907a107a5b1dba7b549fb9f2649a153005175`.

The raw checkpoint improves expanded-human recurrent NLL from 8.38777 to
8.34992, but its regulation bridge-pressure screen regresses from 5--1 to
4--2. Weight interpolation restores the 5--1 boundary at 25%, 12.5%, and
6.25%. The largest restored blend, SHA-256
`7ebf3cca416c250b1073d64109547793ba6ecaa9a7b3c679ddad1b11433ba444`,
also matches the champion on the direct 6--6, safety 7--5, and human-reference
7--5 twelve-game screens. Its full regulation breadth matrix is exactly
outcome- and crown-margin-identical: broad random 9--3, Hog random 12--0,
balanced 4--2, reactive-defense 4--2, bridge-pressure 5--1, slow-push 5--1,
spell-control 4--2, and split-lane 5--1.

That live preservation is not enough for promotion. On the 18,975-decision
frozen champion rehearsal, the 25% blend improves NLL from 0.653481 to
0.652865 but changes six deterministic actions and loses three exact teacher
labels. Smaller blends retain the same tradeoff until 0.78125%, where all
teacher and expanded-human deterministic actions and accuracies are unchanged.
That blend's human NLL improvement is correspondingly negligible and it has no
demonstrated live behavioral gain. The whole probe is rejected rather than
promoting an action-identical likelihood-only update. The Arena 29 checkpoint
remains the official champion.

The failure identifies a missing constraint in the trainer: human expert
rehearsal and accepted-policy preservation share one mixed corpus, while the
behavior-level anchor sees only fresh rollout states. The trainer now supports
a separate frozen-policy recurrent rehearsal corpus. It applies forward KL
from the accepted checkpoint on sampled episode-contiguous protected states,
independently of the human expert loss. This permits the next PPO phase to use
human chronology as the adaptation target and the 18,975-decision champion
corpus solely as an anti-forgetting constraint. Focused Ruff and mypy are clean
and 35 recurrent-policy/rehearsal tests pass before the first dual-corpus pilot.

The first dual-corpus pilot uses the 3,768-decision human chronology only for
expert adaptation (`0.0005`) and the 18,975-decision frozen champion corpus
only for protected-state forward KL (`0.5`). Rollout-state anchor KL remains
`0.2`, L2 remains `0.01`, and learning rate remains `5e-7`. Doubling learner
sequence batch size from four to eight halves optimizer steps from 32 to 16;
the additional frozen recurrent forward pass keeps measured learner time near
23 seconds per update. Four updates consume another 16,384 transitions and
finish 7--6 over thirteen completed league episodes with finite losses, zero
KL stops, and no printed PPO drift above `1e-5`.

Raw update 36 clears the bridge 5--1, safety 7--5, and human-reference 7--5
screens. Its 50% interpolation is the largest blend with no frozen-teacher
exact-accuracy loss. On the teacher corpus, NLL improves from 0.653481 to
0.653300, exact accuracy remains 92.6324%, action-type accuracy improves from
94.5718% to 94.5771%, and within-two-tile accuracy improves from 64.4515% to
64.4889%; four deterministic actions change. On expanded human chronology,
NLL improves from 8.38777 to 8.38372, exact accuracy remains 0.3185%, and
action-type accuracy improves from 27.3620% to 27.3885%. On the original
2,002-decision human set, NLL improves from 8.31867 to 8.31483, exact accuracy
remains 0.4995%, and action-type accuracy improves from 24.7752% to 24.8252%.

The complete regulation matrix remains 48--12 over breadth, 12--12 against the
direct predecessor, 12--12 against the safety champion, and 15--9 against the
human-data reference. A stricter rerun writes per-game terminal records for
both parent and candidate. All 132 records are exact: zero outcome, crown,
tower-HP, or tick changes on identical seeds and seats. The full repository
suite passes 1,127 tests in 36.36 seconds; focused Ruff and mypy remain clean.

The promoted checkpoint is
`checkpoints/human_safety_tvseq_dualanchor_lr5e7_seed1037019/policy_v2_update_000036_alpha050.pt`,
SHA-256
`3701fc84a40cce912a62b0ff1eccec6c29726b0a1af0595657c5c2dd12c46390`.
The Arena 29 spatial-imitation checkpoint at SHA-256
`5ae31cd3e1dc302ff7b7f1a5c8178126d02f8b247a2b74eff495fbf4e51f2b47`
is the immediate rollback. This is a small but proven human-likelihood/type
promotion with strict gameplay preservation, not evidence of mid-ladder-human
strength. The next online phase continues from the promoted blend with the
same dual-corpus constraint and requires actual record-level gameplay gains,
not another likelihood-only promotion.

The first continuation from that checkpoint is rejected. It trains updates
37--44 at learning rate `1e-6`, rollout-state anchor KL `0.5`, protected-state
KL `1.0`, and the same human coefficient. Optimization is stable through
180,224 total transitions: protected-state KL rises only to `4e-5`, PPO KL
remains below printed `1e-5`, no update clips or stops early, and every saved
checkpoint scores 33--15 on a fresh 48-game sweep. The accepted parent scores
34--14 on the identical games. Broad random, bridge-pressure, slow-push, and
human-reference W/L are unchanged; every update regresses the safety block
from 7--5 to 6--6 and reduces total crown margin from +0.958 to +0.875 per
game. There is no favorable W/L change to retain, so interpolation is not
warranted. All four checkpoints are rejected and the dual-corpus 50% blend
remains champion.

A matched lower-rate branch keeps the dual-corpus losses but allocates three
of twelve workers to the safety champion and trains at `5e-7`. Updates
38/40/42/44 are all exactly aggregate-identical to the accepted parent on the
same fresh block: 34--14, +0.958 crowns/game, with per-workload records broad
10--2, human-reference 8--4, safety 7--5, bridge 5--1, and slow-push 4--2.
The added safety exposure prevents the earlier regression but suppresses every
observable gain. The branch is rejected as a behavioral no-op. One final
matched quadrant retains the three-safety curriculum while restoring learning
rate `1e-6`; if it also fails, broad PPO continuation is stopped in favor of
outcome-grounded target generation.

That final quadrant also fails. With three safety-champion slots and learning
rate restored to `1e-6`, updates 38, 40, 42, and 44 are identical to one
another on the fresh 48-game block: 33--15 with total crown margin +42
(+0.875/game). Each retains broad random 10--2, human-reference 8--4,
bridge-pressure 5--1, and slow-push 4--2, but regresses the safety block from
the accepted parent's 7--5 to 6--6. Optimization itself remains finite and
bounded through 180,224 transitions, with protected recurrent KL reaching
only `4e-5`; the failure is behavioral rather than numerical. This entire
branch is rejected. The completed two-by-two continuation grid shows that the
lower learning rate is a behavioral no-op while the higher rate consistently
loses a safety game, regardless of extra safety-opponent exposure. Broad PPO
continuation is therefore exhausted for this checkpoint.

The next phase derives targets from terminal outcomes instead of another broad
policy-gradient update. On fresh broad-random seed block 36501, both accepted-
champion losses occur in matchup seed 41546, one from each seat. Exact
full-reset counterfactual search captures eight temporal states per loss and
replays every candidate from battle initialization. For player 0, replacing
action 1989 with 1972 at tick 3112 changes the 1--2 loss at tick 4289 into a
1--0 win at regulation tick 3600; six additional winning alternatives exist at
tick 3416. For player 1, replacing action 360 with 936 at tick 2720 changes the
1--2 loss at tick 4037 into a 3--1 win at tick 3608. These are terminally
verified one-decision targets, not local value estimates. A shared dense
repair residual is being fitted to the two earliest/best winning targets with
recurrent teacher preservation; it remains unpromoted pending full source and
unseen-block replay.

The first 64-unit dense residual exposes the selectivity tradeoff directly.
At step 200 it changes 1.59% of a 4,096-decision live preservation reservoir
and deterministically realizes one of the two supervised alternatives; at step
500 it realizes both but changes 1.95% of protected actions. Both raw steps
nonetheless convert the complete 12-game source block from 10--2 to 12--0.
Raw step 500 is rejected after repeating the known 7--5 to 6--6 safety
regression. Raw step 200 preserves safety at 7--5 and improves an untouched
24-game random block from 19--5 to 20--4, but regresses the human-reference
screen from 8--4 to 6--6.

Because the residual output layer is zero-initialized and purely additive, its
logit contribution can be scaled exactly without changing the base policy.
At 12.5% strength the candidate is behaviorally identical on the source loss
pair; at 25% and 50% it converts both losses. The 25% version regresses the
fresh safety screen to 6--6. The 50% version preserves preliminary human 8--4,
safety 7--5, bridge 5--1, and slow-push 4--2 while improving source random to
12--0 and unseen random to 20--4, so it advances to the full matrix.

Across that established 132-game matrix, the 50% residual improves total W/L
from 87--45 to 88--44 and total crown differential from +96 to +104. Breadth
improves from 48--12 to 49--11 through spell-control 4--2 to 5--1; the safety
block improves from 12--12 to 13--11; direct competition remains 12--12.
However, human-reference regresses from 15--9 to 14--10. Record comparison
isolates exactly one material human change: matchup seed 42364, player 0,
changes from a 3--1 win at tick 3097 to a 0--1 loss at regulation. The raw and
scaled dense candidates remain rejected despite their net aggregate gain.
Scalar strengths from 18.75% through 43.75% confirm that this human matchup
flips before both source repairs activate, so no global residual scale can
remove the regression. Full-reset search is therefore extended to deterministic
checkpoint opponents and is deriving a second outcome-verified correction for
the isolated human failure.

Deterministic checkpoint-opponent full-reset search reproduces that human
failure exactly (0--1 at tick 3600) and evaluates 100 continuations from eight
temporal states. Six first-decision alternatives win. Action 1989 is selected
because it restores the prior accepted policy's action and its exact 3--1,
tick-3097 terminal record. The repair fitter now applies independent recurrent
KL and action-margin penalties to both the 18,975-decision frozen corpus and a
4,096-decision live parent-policy reservoir. A new shared 64-unit residual
stage learns the selected action by step 75. Continued preservation training
to step 300 reduces live disagreement to four of 4,096 actions (99.9023%) while
retaining the repair.

Raw stage 300 is still too strong: it restores human-reference to 15--9 and
keeps safety 13--11, source random 12--0, and unseen random 20--4, but regresses
balanced strategy from 4--2 to 3--3. Exact additive stage scaling identifies a
narrow clean interval. At 25% the human repair is inactive; at 75% the balanced
regression is active; at 50% the human game is restored, the balanced game is
preserved, and both source repairs remain active.

The 50% stage passes the complete promotion matrix. Breadth improves from
48--12 to 50--10: balanced 4--2, bridge-pressure 5--1, broad random 9--3, Hog
random 12--0, reactive-defense 4--2, slow-push 5--1, spell-control 6--0, and
split-lane 5--1. Direct competition remains 12--12, safety improves 12--12 to
13--11, and human-reference improves 15--9 to 16--8. Across all 132 regulation
games the aggregate improves from 87--45 to 91--41 and crown differential from
+96 to +110. On the separate source block it improves 10--2 to 12--0 (+22 to
+27 crowns), and on the untouched 24-game random block it improves 19--5 to
20--4 (+35 to +37 crowns).

The strict 168-record audit is stronger than aggregate W/L: there are seven
loss-to-win flips and zero win-to-loss flips. Every named workload has
nondecreasing crown differential. Four improvements occur in the regulation
matrix (one human-reference, one safety, and two spell-control), two in the
source block, and one on unseen random seeds. Ruff and Python compilation are
clean for the repair/search/scaling pipeline, the scaling utility has three
focused tests, and the full repository suite passes 1,130 tests in 36.22
seconds.

The promoted checkpoint is
`checkpoints/human_safety_tvseq_dualanchor_dense64_a050_stage64_human_seed1037024/policy_v2_repair_step_0300_stagealpha050.pt`,
SHA-256
`dc56a65fd79bd4c10f99abcaa241394d3c60d0e0fe7f8362c403ee0994622042`,
26,306,821 bytes. The preceding dual-corpus checkpoint at SHA-256
`3701fc84a40cce912a62b0ff1eccec6c29726b0a1af0595657c5c2dd12c46390`
is the immediate rollback. This is a verified gameplay promotion with no
observed record-level regression, not proof of mid-ladder-human strength. The
next phase should generate new outcome-grounded targets from fresh losses
against stronger policy and strategy mixtures rather than resume broad PPO.

A post-promotion probe immediately tests that claim on 108 entirely fresh
games, then reruns the prior champion on identical seeds and seats. The new
champion scores 78--30 versus 76--32 for the rollback and improves aggregate
crown differential from +118 to +121. Random is tied 18--6 (new +36 crowns,
parent +37); safety-reference improves 13--11 to 14--10 (+3 to +7); human-
reference improves 14--10 to 15--9 while crown differential moves +17 to +14;
and the six strategies remain 31--5 while crown differential improves +61 to
+64. Strategy detail is balanced 6--0, bridge-pressure 5--1, reactive-defense
3--3, slow-push 6--0, spell-control 5--1, and split-lane 6--0.

Fresh record comparison is not one-sided: five rollback losses become wins,
while three rollback wins become losses. This does not undo the fixed 168-game
audit or the aggregate safety/human gains, but it supplies higher-value next
targets. The regressions are bridge-pressure seed 54760/player 0, random seed
63591/player 1, and human-reference seed 54310/player 1. The human regression
is prioritized because it changes a +2-crown rollback win into a three-crown
loss. Deterministic checkpoint-opponent full-reset search is running on that
case before any additional fitting.

### Semantic-v2 restart and held-out deck curriculum

The fresh human regression search found four terminally winning alternatives,
including the rollback champion's opening action 274. A new dense stage learned
that exact opening and its scaled residual selected it deterministically, but
the complete replay still lost 1--3 because collateral changes later in the
episode destroyed the repaired line. This is the stopping criterion for the
globally active dense-residual pipeline: it can fit local actions without
preserving the resulting trajectory. No checkpoint from that stage is promoted.

The next line restarts from supervised pretraining rather than adding another
residual. `card_semantics_version=2` expands the policy's shared public card
descriptor from 16 to 36 normalized features. In addition to cost, card kind,
health, damage, range, speed, deploy time, collision radius, summon count, and
ground/air attack flags, it represents DPS, building-only targeting, flight,
projectiles, area damage, death damage/spawns, charge/dash, shields, duration,
spell payload/radius, stun/freeze, slow, knockback, healing, unit spawning,
building-damage modifiers, and mass. Learned card IDs remain available, but
mechanically related cards now also enter the same explicit metric space. The
schema is versioned: legacy checkpoints continue to build the exact 16-column
table, while semantic-v2 checkpoints build 36 columns. A smoke PPO checkpoint
round-tripped successfully with a `(155, 36)` table, and legacy checkpoints
without the new config field load as version 1.

Deck diversity is also made a first-class training and promotion boundary.
Eight current public decks compatible with the verified 66-card vocabulary
were normalized from live-data deck listings; unsupported modern cards and
evolutions were excluded rather than approximated. Together with the 33 project
seeds, deterministic semantic substitutions produce 688 unique, structurally
valid eight-card decks. The split at
`datasets/deck_curriculum_v2_seed1040001` contains 455 training decks and 82
validation decks across Balloon, Bridge Spam, Giant, Golem, Hog, Log Bait,
Miner, and Wall Breakers. A further 151 decks from Graveyard, Lava Hound,
Royal Hogs, and X-Bow are held out as whole archetypes. Every generated variant
retains its parent win-condition archetype, split deck hashes are disjoint, and
per-deck weights give every archetype equal total sampling mass despite unequal
family sizes. The train pool SHA-256 is
`cb553e3352d5d716646841091052f0bc87a853c62b325d16ff6873fe2111de2f`;
validation is
`8066048a9ee3dfd8ad3556363ece198107d59faf93fc7e26b1f62f6fb70e64f0`;
held-out is
`c9d73f1f4f8c724ed6aa6c8a895f7c196c6c401033d8b1e6bbbecd75a76553b8`.

The evaluation CLI now accepts `--sampling-decks-path`, leaving `decks.json`
as the full observation vocabulary while independently testing validation or
held-out pools. This prevents a common evaluation mistake where narrowing the
matchup pool also changes tokenization. Focused semantic, curriculum, sampling,
imitation, and opponent-league gates pass 40 tests.

A fresh 6.2M-parameter semantic-v2 student is now fitting the existing balanced
420,672-frame human-and-safety corpus with the same 192-wide, 5/3-layer,
384-memory architecture used by the earlier clean student. This isolates the
descriptor change before online RL. If the supervised and gameplay screens do
not improve over the matched semantic-v1 student, the semantic-v2 formulation
will be revised or discarded rather than patched. If it passes, PPO will use
the 455-deck balanced training split, screen on the 82-deck validation split,
and require promotion evidence on all four unseen archetypes.

The replacement-style semantic-v2 restart is rejected before PPO. On its own
seed-1041001 validation split it improves over the matched v1 control from
1.68570 loss / 66.92% exact accuracy to 1.44047 / 72.62%, but that apparent
gain does not transfer to the independent 182-episode, 3,768-decision human
chronology. There v2 regresses matched v1 from 10.73688 to 12.45743 joint NLL
and from 22.29% to 21.79% action-type accuracy. The older clean v1 remains
stronger still at 9.37374 NLL and 26.99% action-type accuracy. V2's only small
independent gain is correct-slot placement accuracy within two tiles (11.45%
versus matched v1's 11.19%), which is insufficient to offset the broader human
regression.

A second, broader independent human screen confirms the conclusion rather than
depending on the smaller chronology. On 7,151 decisions from 595 Arena-28
episodes, the best clean v1 scores 9.76157 NLL and 32.30% action-type accuracy;
matched v1 scores 10.88623 / 27.87%; replacement semantic-v2 scores 12.64380 /
27.24%. The local 420,672-frame pretraining mixture is not equivalent to that
many human decisions: its manifest contains 210,672 sampled frames from 190
KataCR human-replay episodes (Hog 2.6 and Golem sources) plus 210,000 behavior
frames from seven simulator opponents. This provides substantial temporal
coverage but limited human deck breadth, so diversified league play and held-
out archetypes remain required even if semantic-v3 passes imitation gates.

Gameplay does not rescue v2. Against the promoted champion on 16 same-deck
held-out games, v2 and the matched v1 control both score 9--7. V2's crown
differential is +0.0625 per game versus matched v1's +0.25, and the 95% score
interval is too wide to separate either model. The same-deck audit also exposes
a material seat asymmetry that must remain visible in future reports: candidate
wins split 6/3 by seat for v2 and 8/1 for matched v1. These games are useful as
a regression screen, not as evidence of generalization or human-level play.
Against the best clean v1 on the original 24-game held-out block, record-level
comparison finds three loss-to-win changes but also two win-to-loss changes;
the 16-game same-deck block finds two improvements and one regression. V2
therefore fails strict no-regression even where its aggregate score increases.

Semantic-v3 therefore preserves the complete legacy 16-feature projection and
adds only 20 genuinely new mechanics through a separate residual projection.
Its final layer is initialized to zero. Upgrading the best clean v1 checkpoint
adds 82,176 parameters (6,170,628 to 6,252,804) while retaining every old
parameter and descriptor exactly and dropping the incompatible optimizer
state. The upgraded checkpoint is
`checkpoints/semantic_v3_residual_seed1046001/initial_from_clean_v1.pt`, SHA-256
`def6c95d1bf511d5a8c758c499e498f6f1b871a06592ae974cd4c15dcee73b06`.
It reproduces all five independent human metrics exactly, including 9.37374
NLL and 26.99% action-type accuracy. An adapter-only, KL-anchored imitation
pilot may modify only `actor_encoder.semantic_card_projection`; promotion
still requires independent human improvement plus non-regression on held-out
archetypes and record-level gameplay screens.

That adapter-only imitation pilot is rejected. It trains cleanly and improves
its in-mixture validation loss from the frozen control's 0.89140 to 0.88314,
but the independent chronology worsens from 9.37374 to 9.46321 NLL and the
broader Arena-28 screen worsens from 9.76157 to 9.89429. Exact scaling of the
residual final layer at 12.5%, 25%, and 50% finds no safe interval: chronology
NLL is respectively 9.39550, 9.41436, and 9.44312, all worse than the exact-v1
initialization, and placement-tolerance changes are inconsistent. The trained
adapter checkpoint and all scaled variants are not promotion candidates. The
zero-preserving v3 initialization remains the rollback and may expose its new
mechanics during outcome-grounded diversified play, but no semantic adapter is
allowed to inherit these imitation weights.

The bounded outcome-grounded semantic-v3 pilot is also rejected after all 20
updates. It starts from the exact legacy-preserving initialization, trains only
the actor and critic semantic residual projections, and processes 81,920 league
decisions across the 455-deck training split. Optimization is numerically stable:
all 32 optimizer steps run at every update, rollout and rehearsal forward KL stay
at or below `2e-5`, clip fraction remains zero, and throughput stays between
approximately 92 and 99 decisions per second. Aggregate rollout records are
usually positive, but the learned direction does not pass the independent gates.

On the 182-episode, 3,768-decision chronology, update 20 changes 21 deterministic
actions, improves joint NLL only from 9.3737448 to 9.3725397, and introduces one
action-type regression with no action-type improvement. On the independent
595-episode, 7,151-decision Arena-28 screen, it changes 31 actions and improves
NLL only from 9.7615667 to 9.7603053, while producing three action-type
improvements, one action-type regression, one within-one-tile improvement, and
one within-two-tile regression. These discrete regressions fail the strict human
no-regression gate despite the microscopic likelihood gains.

Gameplay provides no countervailing evidence. Update 20 ties its exact
initialization 8--8 with zero crown differential over the same 16 mirrored
validation games used for update 10. Its full game records are identical to
update 10: zero improvements, zero regressions, and all 16 unchanged. The
pilot therefore plateaued between updates 10 and 20 and is not extended. The
rollback remains
`checkpoints/semantic_v3_residual_seed1046001/initial_from_clean_v1.pt`; neither
update 10 nor update 20 is a promotion candidate.

This closes the replacement- and residual-semantic trials under the current
Transformer/LSTM architecture. The next experiment is an architecture ablation,
not another residual patch: compare the current global-attention recurrent model
against active-entity-packed attention, a shared-entity pooled encoder, and an
explicit public opponent cycle/elixir belief with no recurrence or a small GRU.
Card identity and exact mechanics remain separable ablation axes. Every variant
uses the same corpus split, seed, action decoder, parameter-budget disclosure,
independent human screens, validation decks, whole held-out archetypes, and
record-level gameplay gate before any longer league run.

## TV Royale 1,000-game human prior and spatial PPO (2026-08-12)

The 1,000-game raw-cascade extraction is now used as type-and-timing supervision,
not as placement supervision. The source corpus contains 29,830 decisions: 20,847
detected plays and 8,983 exact waits. Its location field is deliberately ignored
because the raw detector has no trustworthy tile label. A leakage-safe split
groups repeated deck signatures before assignment and holds out both chronology
and complete archetypes. It contains 601 training replays (17,471 decisions), 151
validation replays (4,018), 191 unseen-archetype replays (6,166; Graveyard, Lava
Hound, Royal Hogs, and X-Bow), and 57 chronology replays (2,175; arena 31 plus
lower-arena occurrences of the same held-out deck signatures). Replay overlap,
deck-signature overlap, held-out-archetype training overlap, and location
supervision are all zero. The split manifest is
`datasets/derived/tv_royale_raw_cascade_1000_split_seed1044301/split_manifest.json`,
SHA-256 `1bbaad8f35332a96a8c6902d9501ca46602c9f08e774d1078796780b9a23ac44`.

Five epochs updating only `action_type_head` produced a repeatable human signal.
On validation it improved action-type NLL from 3.04456 to 2.26511 and joint
top-one type accuracy from 27.87% to 29.22%; on chronology it improved NLL from
2.73021 to 2.04275 and accuracy from 28.32% to 29.15%; on whole held-out
archetypes it improved NLL from 3.27289 to 2.41711 and accuracy from 25.09% to
27.88%. An independent repeat seed reproduced those results. The full fit was
not gameplay-safe, and a 12.5% interpolation flipped one established safety win
to a loss. A 6.25% interpolation retained the useful likelihood direction while
passing all 168 historical gameplay records. That safe human-prior parent is
`checkpoints/tv_raw1000_headonly_epoch5_blend/alpha00625.pt`, SHA-256
`ad82f5aba01571b4d9b754ab3c818fb286b400c87e53b903a4366a0208585cd3`.

Post-training then froze the actor entity encoder, recurrent memory, action-type
head, repair adapter, and repair stages. Only the tile decoder path and critic
were allowed to learn over the 455-deck procedural training curriculum. Updates
37--40 processed 16,384 outcome-grounded league decisions with numerically stable
PPO: forward KL stayed at or below `2e-5`, clip fraction was zero, and every
optimizer step ran. A state-dict audit confirms that only the nine authorized
prefixes changed. Because the type/timing path is frozen, action-type NLL and
the marginal type distribution remain exactly those of the 6.25% parent on all
three corpus splits. Joint argmax type can still change through conditional
location scores, so it is monitored separately rather than claimed invariant.

Update 40 ties its parent 12--12 on both a fresh 82-deck validation block and a
fresh four-archetype held-out block. More importantly, against the complete fixed
168-game historical matrix it records one loss-to-win improvement, zero
win-to-loss regressions, 167 unchanged outcomes, and a net six-crown gain. The
improvement occurs in the unseen-deck block. The promoted rollback point is
`checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt`,
SHA-256 `460520a6b72eb5bf636cf7859fc36ab59a2205a18a84e7ff36f4e568abaacc6c`.

Training longer immediately demonstrated the stopping boundary. Updates 41--44
were stable numerically and retained all 60 screened historical outcomes, but
update 44 lost 11--13 to update 40 on fresh validation decks while only tying
12--12 on unseen archetypes. Update 44 is rejected and no interpolation is
needed: update 40 already supplies the strict improvement. The next experiment
must branch from update 40, change the matchup distribution or spatial learning
signal, and re-pass the same direct and historical gates rather than extending
this exact league trajectory.

A fresh-seed half-rate branch from update 40 was also screened rather than
assuming that smaller steps would solve the problem. Four updates at `5e-7`
tied update 40 12--12 on validation decks and 12--12 on unseen archetypes, then
left all 60 priority historical outcomes unchanged with no crown gain. It is a
safe plateau, not a promotion, so the remaining 108 historical games were not
spent on it. This rules out immediate same-objective continuation at both
`1e-6` and `5e-7`; the next branch needs a materially different matchup or
placement-learning signal.

### Training-only hard-matchup curriculum rejection

A fresh 144-game audit sampled only the 455-deck training pool and evaluated
update 40 against all six public-information strategy bots. It scored 114--30.
The 30 losses were concentrated against reactive defense (nine) and slow push
(seven), with Miner and Hog decks representing half of the losing learner decks.
Those exact deck pairs were frozen before training and weighted by one plus crown
deficit in
`datasets/deck_curriculum_v2_seed1040001/hard_matchups_u40_seed1045201.json`,
SHA-256 `6a23ff0489d03500c10ee466e0fa033a2963120544896b3cba496483528bef96`.
Validation decks and all held-out archetypes were excluded from discovery.

A four-update spatial/value-only branch mixed the hard pairs with ordinary
training-pool samples at probability 0.5 and oversampled reactive-defense and
slow-push opponents. The raw update 44 direction was useful: it improved the
exact training audit to 117--27 with three loss-to-win changes, zero regressions,
and nine additional crowns; it also beat update 40 14--10 on fresh validation
decks while tying 12--12 on unseen archetypes. The 60 priority historical games
were unchanged.

The complete 168-game matrix nevertheless found two rare regressions: one fixed
spell-control win and one fixed unseen-deck win became losses, with a net four-
crown decline. Raw update 44 is therefore rejected. Interpolation located no safe
useful interval. At 50% and 25%, the unseen-deck regression remained; 18.75% also
failed the same boundary. A 12.5% blend restored both historical wins, but tied
update 40 on validation and held-out decks and reproduced all three previously
improved training-strategy blocks exactly. It is a safe no-op, not a promotion.
The hard-matchup direction is closed rather than tuned around individual seeds.

### Public-board placement lookahead rejection and 2,000-game expansion

The next spatial experiment tested a bounded inference-time counterfactual
instead of changing policy weights. It retained the policy's chosen card and
deployment time, reranked only its top legal locations, cloned the complete
battle for each candidate, advanced the already-visible board for a short
horizon with no new opponent deployment, and scored the result with the
existing defense-v2 win-probability potential. The live battle, RNG, players,
and entities remain unchanged; direct tests also require the returned action to
be legal and to retain the selected hand slot.

An aggressive four-location/64-tick version initially looked useful on fresh
transfer blocks (14--10 on validation and 15--9 on held-out archetypes), but its
60-game priority screen contained four improvements and one regression. The
two-location/32-tick version passed that priority screen with one improvement,
zero regressions, and three additional crowns, then failed the complete
historical screen: two improvements, three regressions, and a net one-crown
decline over 168 games. Neither raw configuration is a candidate.

A single global confidence rule requiring a 0.002 predicted win-probability
gain suppressed all three known regressions while retaining both known
improvements in a five-trajectory development sweep. A fresh full rerun then
recorded three improvements, zero regressions, 165 unchanged outcomes, and ten
additional crowns. That matrix is development evidence because its changed
trajectories selected the threshold, not an independent promotion gate. On
completely new seeds the guarded variant scored 23--25 over 48 validation-deck
games and 25--23 over 48 wholly held-out-archetype games: exactly 48--48 in
aggregate. It changed only about 0.01% to 0.05% of all decisions and increased
summed historical evaluation wall time from 896.2 to 1108.8 seconds. The fresh
result is safe but neutral, so placement lookahead is not promoted and was not
made the viewer default. The evidence also closes the current no-response
counterfactual: a stronger search would need a public opponent-response belief,
not more tuning of the same assumption.

The 1,000-game raw cascade has already supplied its intended signal. Its
type/timing-only behavior clone, safe 6.25% interpolation, and subsequent
spatial/value PPO produced update 40; the location labels remain intentionally
unused because detector centers did not pass the spatial audit. The next data
campaign therefore expands replay identity rather than adding epochs to the
same rows. The resumable raw cascade is continuing from 1,000 to 2,000 unique
TV Royale games across arenas 12--31 in tmux session `clasher-tv2000`, with the
same pinned detectors, per-download SHA verification, bounded one-file
prefetch, visual audits, fail-closed labels, and raw-file deletion. Completion
will rebuild the replay/deck/archetype/chronology-disjoint split, repeat the
head-only type/timing fit, and require the same interpolation plus historical
and whole-archetype gates before another RL branch.

### Explicit public opponent-history ablation

The remaining hidden-information architecture question was tested directly
instead of assuming that the recurrent state would rediscover exact public card
cycle evidence. `BattleState` now records only successful public deployments,
and the structured observation can expose the opponent's four most recent card
identities and elapsed ages, most recent first. Failed actions are excluded and
clones own independent history lists. The policy consumes these entries through
a small card/slot/age residual whose final projection is initialized to exactly
zero. Legacy checkpoints therefore remain bit-exact until this branch is
trained; the default slot count is zero.

The update-40 champion was upgraded to four history slots and trained for 20
history-only league updates (20,480 decisions) against random, balanced,
reactive-defense, and slow-push opponents. Every pre-existing model tensor
remained bit-identical. The new branch became behaviorally active (a fixed
history/no-history probe changed joint logits), while PPO stayed finite, clip
fraction stayed zero, and anchor-policy KL remained at or below approximately
`6e-5`. The complete repository gate passed 1,282 tests; focused model,
observation, clone, rollout, and checkpoint tests plus mypy also passed.

Raw update 60 was directionally positive against update 40 on fresh decks: it
won 13--11 on validation and tied 12--12 on whole held-out archetypes. The
priority historical screen nevertheless rejected it because one established
X-Bow-versus-log-bait seat-swapped win at seed 36310 became a loss. The same
regression is present at updates 50 and 55 but absent at update 45, locating the
failure between updates 45 and 50 rather than concealing it in an aggregate.

Update 45 then passed all 60 priority records exactly and was evaluated on 96
entirely new games. It scored 25--23 on validation decks and 24--24 on whole
held-out archetypes, or 49--47 combined. Its SHA-256 is
`3774292cfe817970e800260fb61eb3fec48c165a1292a322de9c56440788228d`.
That two-game edge is too small to justify promotion or spending the remaining
108 historical records. Update 40 remains the champion. Explicit public history
is retained as a viable, exact-upgrade architectural feature for a future
larger-data branch, while this particular RL trajectory is closed at its safe
rollback point rather than tuned around seed 36310.

The 2,000-game postprocessor now runs two independent 20-epoch type-head fits,
constructs 0.390625% through 75% blend ladders for each repeat, and evaluates
every rung under both legacy slot and hierarchical play-gate deterministic
decoding on disjoint validation, archetype, and chronology splits. Only blends
improving action-type NLL on all three splits and preserving both visible-pressure
contexts enter the development gameplay screen against update 40. The screen
deliberately samples the weakest eligible prior, the rung nearest 25%, and the
strongest-likelihood prior for each decoder instead of equating maximum offline
likelihood with gameplay safety. A winning screen earns a separate 96-game fresh
evaluation, then the 60-game priority matrix, and finally the full 168-game
historical matrix if every earlier boundary is clean. No stage promotes
automatically or bypasses a fixed safety boundary.

### Raw-cascade visual QA and conservative deck grouping

An in-flight audit of the first 74 continuation games found 1,576 accepted plays
and 679 exact waits: 21.3 plays and 9.2 waits per replay on average. The median
play count was 17.5, and arena counts remained balanced across arenas 12--31.
Direct inspection of both ordinary and low-label replays confirmed that the crop
and 18-by-32 grid are registered to the playable arena, accepted type labels are
attached to the pre-play hand state, and detector rectangles are sprite boxes
rather than claimed collision hitboxes or placement labels.

That inspection also found that two uniformly spaced audit frames could miss
every accepted label in a sparse replay. Audit selection now prioritizes accepted
play/no-op frames and uses temporal endpoints only as fallback. A newly extracted
two-label replay consequently rendered both accepted Mini P.E.K.K.A. decisions;
the card was visibly present in the pre-play hand in each audited state. This
changes only QA image selection, not extraction labels or corpus arrays.

The discovered deck union is intentionally permissive enough for strict hand
matching and can contain fewer or more than eight names when a UI template is
missed or duplicated. Using that union as an exact split key can separate a
partial observation from its complete occurrence. The splitter now groups only
conservative recognition-equivalent signatures: subset/superset observations
within two cards, or two over-complete observations sharing at least eight cards.
It explicitly does not merge two complete eight-card decks that differ by one
card. Replaying this rule over the original 1,000 games reduces 942 raw
signatures to 925 components, moves one 19-sample partial bridge-spam replay from
training into the arena-31 chronology group, leaves the validation count
unchanged, preserves all four whole held-out archetypes, and retains zero
cross-split component overlap. The complete repository suite passes 1,287 tests.

### Reserved recurring human-meta gameplay gate

The TV Royale deck detections now support a separate use that does not depend on
the untrusted placement centers: a frozen real-human deck-distribution gate. A
deck is eligible only when its conservatively normalized component appears in at
least two distinct replays, contains exactly eight unique simulator-enabled
cards, and contains no unmapped or over-complete observation. The builder
publishes both a uniform-per-deck view and an observed-replay-frequency-weighted
view. It never guesses which card to remove from a noisy component.

This gate is held out more strictly than the ordinary imitation evaluation
splits. Every replay contributing an eligible deck is removed from all imitation
train, validation, archetype-test, and chronology-test corpora before fitting.
The later gameplay gate receives only the eight card identities; none of the
reserved human action labels can update weights or select a blend by NLL. It is
run only after a candidate wins the development and fresh screens and passes the
complete 168-game historical no-regression matrix. The candidate then plays the
update-40 champion for 64 paired-seat mirror games on each weighting view; it
must win in aggregate and avoid a losing record on either view. This remains an
evaluation result, not an automatic promotion.

A frozen first-1,000-game dry run selected eight decks across seven archetypes,
covering 29 replays and 1,688 samples. Reserving them left 971 replays: 590 train,
149 validation, 182 whole-archetype test, and 50 chronology test. Both replay and
normalized deck-signature overlap between the reserve and all four imitation
splits were exactly zero. The live 2,000-game postprocessor will rebuild and
freeze the larger gate before creating its imitation splits.

The first defensive-context retrospective also explains why the earlier safe
6.25% type-head blend did not visibly change pacing. On the 1,000-game validation
split, update 40 selected a deployment on about 97% of sampled states, versus a
human label rate of 81% under near-tower pressure and 66% when pressure was
remote or absent. The raw five-epoch clone swung to about 64%; the 6.25% blend
changed defensive-context NLL by only roughly `2e-7` and did not change the
argmax rates at all. Along the old ladder, 25% still deployed on 96% of states,
50% on 93%, and 75% on 84% while progressively improving near-tower NLL. The
2,000-game ladder therefore includes 50% and 75% rungs. Gameplay cost remains
bounded: at most six behaviorally spaced blends that improve all three held-out
splits and do not worsen either visible-pressure context on any split advance
to the development match screen.

The historical 50%/75% rungs used for that retrospective were interpolated
from the pre-update-40 dual-anchor ancestor into its raw clone, so their exact
coefficients are directional evidence rather than predictions for the new
update-40-to-clone interpolation. A bounded 12-game paired-seat check of the old
75% rung against update 40 tied 6--6 with zero crown differential. It also waited
on 80% of playable decisions and acted on only 6.6% of threatened decisions.
The matched update-40 self baseline was also 6--6, waited on 78.8%, and acted on
6.8% of threatened decisions; both policies had the same 1/5 split of wins by
seat. The old 75% branch was therefore behaviorally neutral on these simulator
states despite its large offline TV-frame change. That is evidence against
treating globally human-like waiting as defense by itself: offline timing
calibration may not transfer to simulator-state decisions, and the new blends
must still earn gameplay and threat-response results rather than being selected
by NLL alone.
### Rejected near-tower imitation reweighting (2026-08-12)

A matched update-40 action-type-head experiment doubled the loss on 900 training
rows with a visible enemy troop/building in the near-tower quarter. It slightly
improved tower-zone NLL on validation only, but worsened aggregate, remote,
held-out-archetype, chronology, and two of three tower-zone results. The training
knob was removed; the defensive-context evaluator remains a required diagnostic.
See `reports/rejected_visible_pressure_weight_20260812.md`.

### Fail-closed 2,000-game promotion and RL handoff (2026-08-12)

The automated screen now distinguishes a provisional development winner from a
promotion-eligible checkpoint. The 24-game development selection is written to
`reports/tv_raw2000_gameplay_screen_development_selected.txt`; the separate
`reports/tv_raw2000_gameplay_screen_promotion_candidate.txt` is cleared at the
start of every run and remains empty unless the same checkpoint wins the
expanded screen, passes the priority and complete 168-game strict no-regression
matrices, and passes both leakage-free human-meta views. Finalization also
rejects checkpoint mismatches among stage summaries, preventing stale artifacts
from another candidate from satisfying a later gate. The development selector
enumerates only the current explicit candidate list rather than every directory
under the screen root.

A chained bounded PPO pilot waits for that final promotion manifest. If it is
empty, no RL process launches. Otherwise it resumes the exact update-40 blend
for four updates over the 455-deck procedural training pool, freezes the actor
entity encoder, recurrent memory, action-type head, and repair paths, and trains
only the nine established spatial/value prefixes against all six strategy bots
and a frozen historical-policy league. A post-training state-dict audit fails on
any unauthorized parameter change. Update 44 then must beat its imitation
parent over fresh validation plus whole-held-out-archetype games before receiving
the 60-game matched priority no-regression screen. This is a pilot and not an
automatic champion promotion; the complete 168-game and human-meta screens are
required again before any trained descendant can replace its parent.

The first frozen human-meta snapshot exposed an additional deck-identity leak
between stages: five of its eight exact decks also appeared in the 455-deck
procedural RL training pool (Log Bait, Hog cycle, PEKKA bridge spam, Loon Miner,
and Wall Breakers). Replay action labels remained held out, but training PPO on
those exact deck identities would make the later human-meta gameplay result a
training-distribution check rather than a held-out one. The chained PPO stage now
builds its pool only after the final 2,000-game meta gate is frozen, removes every
exact meta signature, proves zero remaining overlap in a hashed manifest, and
renormalizes weights within each archetype so the exclusion does not distort the
eight-archetype curriculum. The update-44 descendant must then pass the complete
168-game matrix and beat its imitation parent across both 64-game human-meta
views before it can be written to the separate RL promotion-candidate manifest.

### Real-human evaluation protocol (2026-08-12)

The improved policy viewer from the dedicated visualizer branch is now integrated
into this training tree, including bottom-oriented player 0, exact sight/lock
overlays, action labels, headless rendering, screenshots, and focused tests. A
new human mode assigns one actual simulator seat to mouse/keyboard input and the
other to the checkpoint. Q/W/E/R or the rendered hand selects a current card,
only exact action-mask-legal tiles are highlighted and accepted, and A exposes a
legal champion ability. Completed games append checkpoint-hashed JSONL containing
seats, decks, crowns, candidate-perspective outcomes, human actions, invalid
inputs, and pseudonymous evaluator/ladder labels.

The accompanying summarizer refuses to treat subjective viewing as proof. Its
default competitive protocol requires 40 completed games from one checkpoint,
balanced candidate seats, recorded ladder metadata, at least eight distinct
human decks, candidate decks, and matchups, an aggregate score of at least 0.5,
and a 95% score-interval lower bound of at least 0.5. This is intentionally a
final external gate: the policy is not called mid-ladder capable merely because
it passes bot, replay, imitation, or held-out simulator screens.

A pacing audit caught that the inherited viewer had advanced one native 50 ms
logic tick per 60 Hz render frame, making nominal 1x play approximately 3x real
time. The viewer now accumulates wall-clock time and advances the simulator at
its native 20 Hz rate while continuing to render at 60 Hz. Human mode is hard
locked to 1x, ignores numeric speed keys, records the pacing mode and tick
duration, and the competitive summarizer rejects legacy or accelerated rows.
Focused viewer/summary gates pass, as does the full 1,306-test suite.

### Complete-hand correction and first-1,000-game behavioral-prior screen (2026-08-12)

An audit of the in-flight raw cascade found a previously hidden label-selection
asymmetry. A play was accepted whenever the played card mapped, even if one or
more other visible hand slots were unknown, while an exact no-op required all
four visible slots to map. In the original first-1,000-game corpus, 52.2% of
accepted play rows had a partial hand and every accepted no-op had a complete
hand. This inflated the published corpus to 29,830 rows with 20,847 plays and
8,983 no-ops and made action-type imitation learn an artificial always-play
prior.

The splitter now applies one symmetric publication rule: retain only rows with
all four current hand slots known. It also rebuilds `previous_action` from the
previous retained expert action, so recurrent history cannot reference a row
that the training sequence discarded. The corrected frozen split contains
18,802 rows from 760 replays: 10,948 training, 2,280 validation, 4,268 whole-
archetype test, and 1,306 chronology test rows. Its validation play/no-op count
is 1,141/1,139; replay, normalized-deck, and held-out-archetype overlaps are all
zero. The schema records zero incomplete-hand rows and the exact retained-action
history contract, and the 2,000-game postprocessor now refuses any manifest
that does not prove those invariants.

A separate evaluator audit found that the recurrent-corpus tool had decoded a
flat argmax over 2,306 joint actions. That systematically disadvantaged plays,
because one slot's probability is distributed across many legal placement
tiles, and did not match the live policy. It now calls the policy's exact live
deterministic hierarchy. Negative log likelihood is unchanged; reported play
rates, selected slots, and paired action changes now describe the deployed
policy rather than the obsolete flat decoder.

Training only `action_type_head` from update 40 for 20 epochs on the corrected
split sharply improved validation action-type NLL from 3.8364 to 1.3904 and
play-probability Brier score from 0.4865 to 0.2447. The same direction held on
whole-archetype and chronology tests. Raw replacement was still decisively
unsafe: legacy slot decoding went 0--24 over the 24-game validation plus held-
out screen, while the opt-in play-gate decoder went 4--20. The endpoint is
therefore a useful behavioral target, not a replacement policy.

Weight-space interpolation located a smooth transition. Through 25%, held-out
NLL improved monotonically while deterministic corpus actions were almost
unchanged. At 37.5%, 50%, 62.5%, and 75%, validation NLL fell to 2.4888, 2.1331,
1.8405, and 1.6145 respectively; only the stronger rungs substantially changed
human-state cadence. A matched 24-game gameplay screen then found both 25% and
50% default-decoder blends at 13--11 with four additional crowns, while 75%
collapsed to 3--21 and minus 53 crowns. The play-gate version did not rescue
the 75% rung. This is direct evidence for a conservative human prior followed
by RL, and against either raw cloning or selecting the largest offline gain.
The 25% and 50% candidates each finished 49--47 over a fresh 96-game expansion;
25% had five additional crowns and 50% had zero. The 25% candidate then failed
the full historical matrix with two regressions and one improvement. Both 12.5%
and 25% reproduced the same direct-policy and bridge-pressure failures, locating
the boundary between 6.25% and 12.5%. The corrected 6.25% blend reproduced all
168 historical outcomes with zero regressions and net-zero crown-margin change,
then went 49--47 with four additional crowns on the fresh 96-game expansion.
It is accepted as an RL initialization seed but not a champion: update 40
remains the deployed checkpoint while a bounded diversified PPO descendant is
trained and independently gated.

The bounded spatial/value PPO pilot trained updates 41--44 from that seed while
freezing the human action-type head, entity encoder, recurrent memory, and repair
paths. Training was numerically stable: anchor-policy KL rose only from about
`1e-5` to `6e-5`, clipping stayed zero, and a state-dict audit found 83 changed
tensors, all within the nine authorized prefixes. Update 44 went 25--23 with six
additional crowns over 48 fresh games and reproduced all 60 priority outcomes,
but failed the complete matrix with two regressions and no improvements: unseen-
random seed 48555 and balanced-strategy seed 20719. Earlier checkpoints did not
provide a safe rollback: update 41 already failed the unseen-random boundary and
updates 42--43 failed balanced strategy.

Interpolating the update-44 PPO delta located its safety boundary below 25%.
At 12.5% of the delta both regressions disappeared, but the fresh screen became
exactly 24--24 with zero crown edge. The part of the PPO update that measured as
useful was unsafe, and the part that was safe measured as neutral, so the entire
pilot is rejected rather than promoted or continued. The automated 2,000-game
development selector now prioritizes a winning candidate nearest the empirically
safe 6.25% imitation strength, preferring the default slot decoder at the same
strength, before spending later gates. A later PPO branch still has to earn new
fresh wins and preserve every historical outcome; this failed trajectory is not
an anchor.

Decision-level traces localized both failures more precisely. On unseen-random
seed 48555, parent and update 44 have effectively identical action-type logits
at the first divergence, but update 44 moves an Ice Spirit from `(11.5, 17.5)`
to `(7.5, 18.5)` at tick 16; that single early placement changes a later 3--1
win into a 1--3 loss. On balanced seed 20719 the first decision already
diverges between two Skeleton placements whose selected location logits differ
by only about 0.03; the parent wins 3--1 and the child loses 1--2. The failure is
therefore not a global always-attack cadence regression. Tiny spatial-logit
changes among near-tied legal tiles cascade into different deterministic games.

An opt-in factorized rehearsal anchor was added to test the general response,
not to patch either seed. It computes forward KL over the legal conditional
tile distribution for every playable hand slot on a frozen 18,975-state,
94-episode strategy corpus. The matched update-41 sweep held all other rollout,
league, optimizer, and seed settings fixed. Coefficients 0.2, 1, 5, and 50 all
reproduced the exact unseen-random regression. A coefficient of 500 restored all
30 tested unseen-random and balanced outcomes and still moved 84 tensors, but
after four updates it went exactly 12--12 with zero crown edge on validation and
12--12 with zero crown edge on wholly held-out archetypes. Strong conditional
KL can suppress the brittle placement drift, but at the measured safe strength
it also suppresses the useful gameplay change. This protected PPO branch is
rejected rather than promoted or coefficient-tuned around a known trajectory.

### Deployment-clock location supervision (2026-08-12)

The raw TV Royale videos contain a better placement signal than troop sprite
boxes: for a short interval after a lower-player troop or building deployment,
the client draws a small deployment clock at the actual placement point. The
extractor now decodes the event frame plus frames `+1` and `+2`, subtracts any
pre-existing clock cluster, requires every recovered adjacent frame to map to
one canonical arena tile, rejects upper-side observations, spells, illegal
placements, incomplete/partly unsupported hands, and all disagreements. The
main type/timing corpus remains unchanged. Accepted positions are written to a
separate `location_corpus.npz` sidecar, so location failures cannot weaken the
existing labels.

The first live audit recovered 154 non-spell positions from 11 instrumented
games across 28 supported troop/building cards. After enforcing the same four-
known-card hand rule as the main split, a subsequent live combine retained 174
positions from 18 replays and removed 72 older partial-hand rows. Newly
extracted games now reject those rows at source. Visual QA covered twelve
examples across arenas 12--31, including backfield, bridge, building, tank, and
crowded defensive placements. The green cross followed plausible deployment
points; detector rectangles remain explicitly labeled as sprite boxes rather
than simulator hitboxes.

Sparse deployment-clock events omit every intervening play and wait. They must
not be stitched into a fictitious recurrent trajectory. The combiner therefore
publishes every accepted location as an independent one-step episode with a
neutral previous action and reward. The final 2,000-game pipeline mirrors the
already frozen replay/deck/archetype/chronology assignments into a separate
location split, proving zero replay overlap and requiring sequence length one.

Location imitation begins only after the card/timing model is selected. It
fine-tunes the spatial decoder prefixes with factorized conditional-location
loss, zero action-type loss, left/right augmentation, and no encoder or memory
updates. Small weight-space blends are evaluated against their own type parent
on location validation, whole-archetype, and chronology splits. Only blends
that repeat the conditional-location NLL improvement across two independent
training seeds on every held-out split while preserving action-type NLL enter
the normal fresh-game and full historical safety screens. An offline location
gain is not itself a promotion.

A provisional 597-label CPU smoke fit validated the exact spatial-only command
before the final corpus froze. One epoch changed 26 tensors, all inside the six
authorized spatial prefixes, reduced full-corpus conditional-location NLL from
11.5811 to 5.6249, and changed action-type NLL by only `4.5e-8`. The owned smoke
checkpoint and corpus were deleted immediately; this is pipeline evidence, not
a candidate or promotion result.

The same audit then tested whether spells could be added without weakening the
contract. Projectile, rolling, and instant spell visuals were absent, moving,
or class-ambiguous at the adjacent frames and remain excluded. Only
mechanics-defined persistent area spells are eligible for a provisional visual
center: the event frame supplies the pre-existing-effect baseline, both `+1`
and `+2` frames must contain exactly one novel spell-effect center, and the two
centers must map to one legal canonical tile. The detector often confuses
Poison and Earthquake as classes but localizes their shared area center
consistently, so class identity still comes exclusively from the UI play event.
Spell-center rows enter the same independent one-step sidecar and the same
held-out/two-seed/gameplay gates; any missing or ambiguous visual fails closed.

At 1,572 of the planned 2,000 games, the live sidecars contain 875 accepted
locations from 80 replays. Six are Earthquake centers from one complete-hand
replay; all other accepted rows are troop/building deployment clocks. The
Earthquake audit cross lies on the stable area center over the targeted
defensive building, and a paired Skeleton example places the deployment-clock
cross at the lower-side spawn point. The renderer now guarantees at least one
saved overlay for every accepted location kind even when the generic audit
sample budget would omit it. The resulting extraction/training changes pass
the full 1,334-test suite. These are still interim collection and data-quality
results, not evidence that spatial imitation improves gameplay.

A provisional replay-disjoint split at 1,576 games exposed an important epoch
choice before the final run. After complete-hand filtering it contained 301
spatial training labels, 101 validation labels, 102 whole-archetype labels, and
44 chronology labels. With the production spatial-only scope and seed 1046001,
epoch 20 had the best validation conditional-location NLL (`5.2670` versus
`5.4078` at epoch 5), but epoch 5 generalized better to both whole archetypes
(`5.3082` versus `5.4171`) and chronology (`4.9933` versus `5.1096`). Both
preserved action-type NLL to numerical precision and greatly improved over the
parent (`11.1059`, `10.7880`, and `9.6240` respectively). A second seed and a
6.25% blend reproduced the ordering: the two epoch-5 runs improved mean held-out
location NLL by `0.7660` and `0.7460`, versus `0.6557` and `0.6434` for epoch 20.

The provisional spatial training subset spans 38 card identities and 125
distinct canonical tiles across 37 source replays; its left/right count is
163/138. It includes 268 troop, 28 building, two Freeze, and three Tornado
labels. The six Earthquake labels remain entirely in the whole-archetype test,
so any Earthquake improvement measures transfer rather than memorized training
examples.

The final location experiment therefore evaluates both 5- and 20-epoch
directions across both frozen seeds instead of assuming the longest fit is best.
A parallel audit tightened the preceding type/timing stage: a blend must now
repeat its all-split NLL improvement and defensive-context safety at the same
decoder hierarchy and alpha under both seeds 1045901 and 1045902 before either
member can seed location training or enter gameplay screening. Merely running
two fits without grouping their evidence is no longer treated as replication.
A standalone selector requires exact two-seed replication at the same parent,
decoder hierarchy, epoch count, and blend strength, improvement on every
held-out split, and absolute action-type NLL drift no larger than `1e-6`.
Only the conservative and strongest repeatable groups advance to gameplay; the
offline epoch result alone remains nonpromotional.

The queued diversified PPO stage now has an explicit numerical-stability gate
before spending any gameplay evaluations. Updates 41--44 must all exist,
advance the parent's transition counter by exactly 4,096 decisions each,
contain only finite model tensors and scalar metrics, perform at least one
optimizer step, avoid a KL early stop, and remain below approximate-KL `0.03`,
anchor-policy-KL `0.01`, and clip-fraction `0.20`. The verifier reproduced the
known earlier update-41--44 phase exactly: 16,384 contiguous transitions, 64
optimizer steps at every update, zero clipping/early-stops, maximum approximate
KL `1.80e-5`, and maximum anchor KL `2.88e-5`. Passing this gate establishes
optimizer stability only; it does not override any outcome or held-out gate.

Reaching the 2,000-game counter is no longer sufficient to begin imitation. A
new integrity gate re-hashes and reloads every accepted per-game corpus and
location sidecar, verifies replay/arena/source identity, sample and accepted-
label counts, one shared token vocabulary, unique replay IDs, all cited audit
images, both combined-corpus manifests, independent location rows, and zero
remaining raw Parquet files. A full historical smoke audit over the original
1,000-game publication passed: 1,000 unique replay corpora, 29,830 per-game and
combined decisions, 2,000 existing audit images, matching digests, and no raw
files. The final 2,000-game report must pass the same gate before split or
training commands run.

After adding the final run-integrity, type-repeatability, spatial-candidate,
and PPO-stability gates, the complete repository suite passed `1,346` tests in
`42.90s` on 2026-08-13. This validates the queued pipeline implementation; it
does not validate the unfinished 2,000-game artifact or promote a policy.

A subsequent source audit found that the troop/building clock extractor did
not fully implement its documented two-follow-up agreement contract: it
accepted an event when either `+1` or `+2` recovered a clock, provided all
recovered clocks mapped to one tile. Persistent-area spells already required
both frames. This made the older spatial sidecars weaker than claimed, so they
are quarantined rather than retroactively trusted. The corrected `strict-v3`
contract requires both clock follow-ups, stamps the corpus label source, and
makes the location combiner/splitter admit only that exact source. Type/timing
rows from the same replays are unaffected. Audit rendering now saves the actual
follow-up evidence frame while retaining the play-event state and label. The
first live strict audit (`event=835`, `evidence=836`) visibly placed the green
cross on the deployment clock. The correction passed 26 focused tests plus
Ruff and mypy, followed by the complete `1,348`-test suite in `42.92s`; final
spatial sample sufficiency and all downstream results remain pending.

The queued handoff was also tightened after the contract correction. A
postprocess success sentinel is cleared before waiting and published only after
integrity, splitting, both type seeds, all offline evaluations, repeatability
annotation, and either a completed or explicitly data-insufficient strict
location stage. Gameplay refuses to start without that exact sentinel and
clears its promotion output first, so an earlier summary/checkpoint cannot be
promoted after a failed rerun. Strict spatial fitting now requires at least
`200/50/50/25` samples and `20/6/6/3` replays in train, validation,
whole-archetype, and arena-31 chronology splits respectively; insufficiency
skips only the optional spatial adapter while preserving type-only screening.
At 1,691 completed games, strict-v3 had accumulated 106 complete-hand samples
from 11 replays. These interim counts do not yet prove the final split minima.

A snapshot through game 1,693 ran the exact final reserve, type-split, and
strict-location split code without touching live artifacts. All leakage and
independent-row invariants passed. The 112 strict samples across 13 replays
assigned as train 56/8 replays, validation 5/1, whole-archetype 41/3, and no
arena-31 chronology locations yet. This correctly fails the new sufficiency
gate and demonstrates why raw label totals are not used as readiness evidence.
The remaining 307 games continue to collect strict evidence; location fitting
will be skipped if the final split still misses any minimum. The owned 5.2 MiB
projection tree was moved to Trash after inspection.

The spatial readiness gate now also audits the deduplicated rows that each
split will actually train or evaluate on. It records distinct target cards,
exact tiles, 3-by-4-tile coarse regions, covered columns/rows/y-bands, canonical
left/right counts, and persistent-area spell coverage. In addition to the
sample/replay minima, train must cover at least 20 cards, 50 exact tiles, 12
coarse regions, three y-bands, and a 20% minority-side fraction; held-out splits
have proportionally smaller but nonzero card/tile/region/y-band and 10%
minority-side requirements. Thus hundreds of duplicated labels on one card or
one lane cannot unlock spatial fitting. The interim strict-v3 pool at 1,699
completed games had 132 samples from 18 replays spanning 37 cards, 81 exact
tiles, and a 78/54 left/right split; those aggregate numbers are encouraging
but do not substitute for the final replay-disjoint per-split gate. The new
coverage accounting passed 17 focused replay/split tests plus Ruff, mypy, and
shell syntax checks. The complete repository suite then passed 1,352 tests in
41.25 seconds while the collector continued at low-priority test load.

A second manual strict-v3 visual audit sampled three different label mechanisms
from newly collected games. Arena-30 Cannon at
`eb0336a9-886f-44e4-b7fb-dbbc636fa13f/audit/001_frame_00513.jpg` places the
green target cross on the new building's deployment clock; arena-30 Earthquake
at the same replay's `audit/002_frame_00554.jpg` centers the cross in the
detected persistent spell area; arena-31 Balloon at
`90eab766-bafd-4a64-9c75-bc857f50945c/audit/001_frame_00888.jpg` centers it on
the bridge deployment clock. The rendered rectangles are explicitly annotated
as sprite/crop boxes rather than collision hitboxes, so tower or troop visual
bounding boxes are not being treated as simulator occupancy geometry. All
three examples use distinct event and evidence frames and were visually
consistent with their canonical grid labels.

An exact read-only projection at 1,727 completed games reran the production
human-meta reserve, replay/deck-disjoint type split, strict-v3 location split,
and location verifier in a private temporary root. All split invariants passed.
The 288 strict labels across 35 replays assigned as train 102/18 replays,
validation 47/4, whole-archetype 56/7, and arena-31 chronology 24/3. The
whole-archetype split already passed every gate. Chronology missed only the
25-sample floor by one while already spanning seven cards, 20 tiles, 15 coarse
regions, five y-bands, and a 45.8% minority lane. Validation missed three
samples and two replays. Train missed 98 samples and two replays but already
spanned 27 cards, 66 tiles, 28 coarse regions, seven y-bands, and a 36.3%
minority lane. Thus current insufficiency is count-only, not semantic or board
collapse, with 273 collection games still pending. The owned 3.4 MiB projection
tree was moved to Trash after inspection and none of its artifacts can enter
training.

The same 1,727-game projection retained 28,714 complete-hand type/timing rows
from 1,258 replay groups after rejecting 19,298 rows whose four visible hand
slots were not all known. The retained objective is balanced rather than
degenerate: train contains 8,638 plays and 8,276 exact no-ops (16,914 rows),
validation 2,196/1,892 (4,088), whole-archetype 3,122/2,902 (6,024), and
chronology 902/786 (1,688). The chronology component includes lower-arena
replays only when their conservative deck-signature component also reaches
arena 31, preserving deck-disjointness instead of leaking the same deck through
another arena. These are interim readiness measurements, not offline evidence
that the resulting policy improves gameplay.

The publication integrity boundary was hardened once more while collection
continued. It no longer accepts a combined manifest merely because it cites
the expected number of sources: the verifier now requires the primary source
paths to be duplicate-free and exactly equal to all completed per-game corpus
paths. For strict-v3 locations, the published `replay_ids` must likewise be
present, duplicate-free, and exactly equal to the replay IDs of every strict
per-game sidecar; a missing replay replaced by an unrelated replay therefore
fails even if counts and sample totals happen to match. The helper's
order-independent acceptance, duplicate rejection, and substitution rejection
are covered directly; Ruff, mypy, and all five focused integrity tests pass.

A second exact read-only projection at 1,754 completed games froze the live run
manifest and reran the production reserve, type split, strict-v3 location split,
and location verifier. The strict pool had grown to 370 samples from 54 replays;
three reserved human-meta replays were ignored and all 51 remaining replays were
assigned with zero overlap. Validation passed at 52 samples/6 replays,
whole-archetype at 60/8, and arena-31 chronology at 42/7. Each also exceeded its
card, tile, coarse-region, y-band, and minority-side requirements. Train spanned
37 cards, 84 tiles, 29 coarse regions, seven y-bands, and both sides at 91/66
across 30 replays, but remained deliberately ineligible at 157/200 samples.
Thus only 43 training labels remain missing; no diversity or replay-count gate
failed, and the threshold remains unchanged. The owned 5.3 MiB projection tree
was moved to Trash and cannot enter the final training artifacts.

The live run's 13 recorded failures were audited before publication rather
than treated as 13 independent missing games. They represent five unique
replays: one transient Hugging Face read timeout and four deterministic invalid
inputs retried across resumptions. One video exposed only three distinct deck
cards, two produced no rows after conservative conversion, and one contained a
broken encoded image stream. The unique failures occur in arenas 12, 13, 15,
and 25; no arena 26--31 replay has failed. The run still requires 2,000 unique
successful replay IDs, so these records consume attempt budget but cannot enter
training or reduce the accepted-game target.

The final integrity verifier was then aligned with the location combiner's
complete-visible-hand contract. It still audits and reports every strict-v3
sidecar, but exact combined replay membership and the pre-deduplication sample
ceiling are now computed from only rows eligible for combination. A strict
sidecar whose every row has an incomplete visible hand can therefore be
excluded safely without either leaking weak supervision or incorrectly
blocking type-only imitation. On a live 1,763-game snapshot, an independent
verifier traversal and the production location-record loader selected the
exact same 60-replay/413-sample map, with no missing or unexpected IDs. Ruff,
mypy, and 19 focused integrity, replay-split, and cascade tests passed.

The optional location stage also no longer recombines over the collector's
integrity-verified location artifact. An isolated 1,768-game A/B proved why:
seeds 1,044,201 and 1,045,801 produced bit-identical training arrays but
different corpus SHA-256 values (`edf8a2bf...b739b` versus
`a57b960c...f7d77b`) because the published metadata seed and creation time
changed. The redundant rewrite would therefore have made the integrity report
refer to bytes no longer on disk. Spatial fitting now consumes only fresh
replay-disjoint split outputs while leaving the verified combined artifact
immutable. Two source-contract tests enforce both non-overwrite and verifier-
before-location ordering; shell syntax, Ruff, mypy, and the expanded 21-test
focused gate pass. The owned A/B tree was moved to Trash.

Gameplay candidate selection now requires an explicit
`two_seed_repeatable: true` annotation. The earlier backward-compatible path
accepted a missing repeatability field, which could allow a legacy single-seed
summary into the expensive gameplay screen if the selector were invoked
outside the intended wrapper. Missing evidence and explicit false are now both
rejected, and metadata is loaded only for fully annotated candidates. Ruff,
mypy, and 14 focused repeatability, location-selection, finalization, and
pipeline-contract tests pass.

The diversified-RL wrapper now refuses to start if any bounded-phase update
41--44 checkpoint already exists in its fixed output directory. Previously, an
early trainer exit could leave an older update 44 available for the later file
existence check; transition and state-dict gates made accidental acceptance
unlikely but did not prove the artifact came from the current invocation. The
first-run directory is currently absent, and the explicit preflight runs before
deck-pool construction or training. Shell syntax, Ruff, and nine focused
stability, exclusion, and pipeline-contract tests pass.

The bounded-RL state-dict audit now proves policy learning rather than merely
some allowed tensor change. It requires at least one actor-side card/location
parameter and at least one critic/value parameter to differ from the parent,
requires exact state schema, and rejects every change outside the declared
prefix groups. The reusable verifier has direct success, value-only rejection,
unauthorized-change rejection, and schema-drift tests; shell syntax, Ruff,
mypy, and 13 focused RL audit/stability/exclusion/pipeline tests pass. The idle
RL waiter was reloaded after this change, without touching collection or other
handoff sessions.

After all publication, repeatability, and bounded-RL hardening above, the
complete repository suite passed 1,363 tests in 44.58 seconds at low priority
while extraction continued. This validates the integrated implementation but
does not constitute corpus completion, gameplay promotion, or human skill
evidence.

A third exact production-code projection at 1,781 games confirmed that strict
spatial readiness is nearly achieved without relaxing any gate. The eligible
pool contained 497 labels from 72 replays; six human-meta replays were reserved
and all 66 others assigned with zero leakage. Validation passed at 54/7,
whole-archetype at 67/11, and chronology at 55/9 samples/replays. Train reached
192/39 and missed only the unchanged 200-sample floor by eight while already
covering 41 cards, 95 tiles, 29 coarse regions, seven y-bands, and a 46.35%
minority side. The verifier correctly returned its typed data-insufficient
status, and the owned 5.5 MiB projection was moved to Trash.

A fresh visual QA sample from the expanded strict-v3 pool checked four recent
arena/card combinations at original resolution. Arena-23 Spear Goblins
(`1354f1e3.../001_frame_00774.jpg`) centers the cross on the lower-side clock
below the left bridge; arena-26 Ice Golem (`cb5e4ef0.../001_frame_01136.jpg`)
centers it on the crowded right-lane defensive clock; arena-29 Wall Breakers
(`298ed8e5.../001_frame_00829.jpg`) centers it on the paired left-bridge
deployment clocks; and arena-31 evolved Cannon
(`ef0f86d7.../001_frame_00835.jpg`) centers it on the lower-side building clock.
None uses tower UI, health bars, or sprite rectangles as placement geometry.
All four show distinct event/evidence frame numbers and remain visually aligned
across arena skins and crowded fights.

The final real-human evidence gate now requires an exact ladder cohort instead
of merely a nonempty self-reported label. `mid-ladder` is the default required
cohort, is explicit in the documented summary command, and every recorded row
must match it; mixing even one `beginner` or other cohort record fails the gate.
This closes a gap where balanced, confident wins against the wrong human skill
cohort could otherwise be misreported as mid-ladder evidence. Ruff, mypy, and
seven human-viewer/summarizer tests pass.

Human evaluation is now paired at the matchup level rather than only balanced
in aggregate. With the same seed, switching `--human-player 0` to
`--human-player 1` preserves the human deck, candidate deck, starting hand, and
cycle queue while swapping only physical arena seats; role-ordered shuffling
prevents RNG assignment from confounding the pair. The summary gate requires
every ordered human/candidate matchup to contain equal candidate-seat counts,
so two globally balanced but unrelated match sets fail. Documentation now
requires the same seed for both blocks. Ruff, direct and import-skipping mypy
checks, and all eight human viewer/summarizer tests pass.

After the human-cohort and paired-seat changes, the complete repository suite
passed 1,365 tests in 42.60 seconds at low priority while extraction continued.
This supersedes the earlier 1,363-test implementation run; it remains software
evidence only, not a substitute for completed policy or human-match results.

At a frozen 1,801-game snapshot, strict spatial readiness crossed the unchanged
gate for the first time. The production verifier passed with 591 eligible
labels from 84 replays, six reserved human-meta replays, and 78 assigned with
zero leakage. Train passed at 201/44 while covering 42 cards, 96 tiles, 29
coarse regions, seven y-bands, and a 46.77% minority side; validation passed at
92/10, whole-archetype at 110/14, and chronology at 59/10, all with broad
diversity. This authorizes location fitting for that snapshot but does not
pre-approve the final run, because newly recurring human-meta deck components
can still shift reservation membership. The final 2,000-game split must pass
again. The owned 5.7 MiB projection was moved to Trash.

### In-flight effective-coverage audit at 1,814 games (2026-08-13)

A streaming audit applied the production complete-visible-hand filter to every
finished per-replay corpus rather than treating raw game count as usable data.
It retained 34,199 of 54,683 rows (62.54%) from 1,388 effective replays. The
retained labels contain 17,960 plays and 16,239 exact no-ops, a 52.52% play
rate, so the earlier partial-hand always-play distortion is absent. All 20
source arenas contribute at least 1,133 retained rows. The played-card labels
cover 67 enabled/evolution-aware token identities; only Dark Prince remains
below ten observations at seven. This is broad enough to justify running the
predeclared two-seed type-imitation experiment, but rare-card held-out metrics
remain mandatory because aggregate loss can still hide that tail.

The same retained observations contain 12,703 public-visible own-half-pressure
rows and 1,921 tower-zone-pressure rows under the conservative detector-based
context definition. Strict-v3 spatial supervision remains much smaller: 625
complete-hand placements from 89 replays, spanning 53 card identities and 177
canonical tiles. Four identities have fewer than three placements (Bomber 1;
Giant, Royal Hogs, and Skeleton Barrel 2 each). That scarcity is why spatial
training remains isolated to the location heads, uses left-right augmentation,
tests both 5- and 20-epoch rungs with two seeds, and must improve conditional
location NLL on validation, whole-held-out-archetype, and chronology splits
without changing action-type NLL. These numbers are an in-flight readiness
snapshot, not final 2,000-game integrity evidence or a promotion result.

The corresponding first-1,814 production split was projected with the actual
human-meta reservation, conservative noisy-deck component grouping, complete
hand filter, whole-archetype holdout, and arena-31 chronology rule. Sixty-three
replays were reserved for human-meta evaluation. Train retained 17,342 rows
from 784 replays and 761 deck components; validation retained 4,187 from 187
replays and 183 components; the whole-archetype test retained 6,996 from 259
replays and 222 components; chronology retained 1,817 from 95 replays and 51
components. The respective tower-zone-pressure counts were 984, 191, 346, and
88, and each split retained 60--67 distinct visible hand tokens. Thus none of
the four evidence partitions is nominally broad but statistically empty. The
owned projection was moved recoverably to
`/Users/sam/.Trash/clasher-type-readiness.xbLunx`; final publication still
rebuilds and rechecks these statistics from exactly the first 2,000 games.

The projection is now enforced by
`scripts/verify_tv_royale_type_split.py` immediately after the final split is
published and before either imitation stage starts. The fail-closed gate checks
the exact source-game count, nonempty final-evaluation reservation, all label
and leakage invariants, sample/replay accounting, and conservative per-split
floors for samples, replays, deck components, arenas, and archetypes. Floors
are intentionally below the 1,814-game projection so they catch structural
collapse without encoding the current counts as targets. The real projection
passes; 29 focused pipeline, publication, selection, human-evidence, and viewer
tests pass in 1.18 seconds, with Ruff, direct mypy, and shell syntax clean.
The complete repository suite then passed 1,368 tests in 42.81 seconds at low
priority while extraction continued. The three idle downstream waiters were
reloaded in dependency order so the live 2,000-game handoff is guaranteed to
execute the current gate; the collector and all completed corpus artifacts were
left untouched.

The recurring-deck reserve now has its own fail-closed verifier before split
publication. `scripts/verify_tv_royale_human_meta_gate.py` requires at least
eight exact decks, six archetypes, 16 disjoint replay observations, and 500
samples; recomputes manifest accounting; rejects duplicate decks or replay
reuse; verifies both artifact digests; and proves the uniform and observed-
frequency artifacts contain exactly the reserved deck rows with the correct
weights. The first-1,814 reserve passes at 15 decks, nine archetypes, 63 replays,
and 3,857 samples. Its owned verification projection was moved recoverably to
`/Users/sam/.Trash/clasher-meta-readiness.rzA3aZ`. The downstream waiter chain
was reloaded without touching collection. Ruff, direct mypy, shell syntax, and
32 focused end-to-end publication/selection/human-viewer tests pass.
The complete repository suite passes 1,371 tests in 42.67 seconds at low
priority while the collector continues.

Final gameplay promotion now independently verifies evidence completeness rather
than trusting stage booleans alone. The selected checkpoint must exist; every
summary must identify that same path; development must contain 24 games,
expanded 96, priority 60, the complete matrix 168, and human-meta 128; and the
human-meta summary must explicitly remain evaluation-only with no training
action labels used. A partial or stale same-path directory therefore cannot
publish a promotion candidate. Ten direct finalizer/meta tests and 39 combined
pipeline, held-out selection, human-evidence, and viewer tests pass, with Ruff
and direct mypy clean.
The complete repository suite passes 1,372 tests in 42.65 seconds at low
priority after the finalizer hardening.

An operational audit at 1,843 games found 50 GiB free on the data volume,
exactly one in-flight raw parquet in scratch, 1,843 matching per-game corpora
and manifests, zero missing artifacts, zero completed rows lacking positive
samples/digests, and every completed raw source marked deleted. The active
extractor was using MPS/CPU normally. With one-at-a-time raw retention, the
remaining games cannot exhaust current disk headroom; no cleanup or collector
restart was needed.

The bounded RL descendant now has an explicit finalizer instead of publishing
from the last human-meta boolean while relying on prior shell control flow.
`scripts/finalize_tv_royale_rl_pilot.py` reopens and cross-checks the candidate
and parent across the 48-game direct screen, 60-game priority screen, complete
168-game matrix, and both 64-game human-meta views; requires the exact four
updates and 16,384 transitions to pass stability; requires both actor and value
tensors (and no unauthorized tensors) to change; and verifies the filtered
training-pool artifact still hashes correctly with nonzero exclusions and zero
held-out overlap. Only all seven gates together can write the RL promotion
candidate. The idle RL waiter was reloaded without touching earlier stages.
Ruff, mypy, shell syntax, seven direct contract tests, and 53 combined pipeline,
stability, deck-exclusion, human-evidence, and viewer tests pass.
The complete repository suite passes 1,376 tests in 43.39 seconds at low
priority after this final integration.

Fresh visual QA was repeated during the live continuation rather than relying
only on manifest checks. Four newest overlays from arenas 25--30 and a fixed
seed cross-arena sample from arenas 12, 14, 16, 18, 20, 22, 23, 25, 27, 29,
and 31 were inspected at rendered resolution. Across distinct arena skins and
early, crowded midgame, overtime, and terminal frames, the 18-by-32 grid stayed
registered to the arena; claimed deployment crosses landed on plausible
playable cells; towers and visible troops were detected inside the battle
viewport; and emotes, spectator text, clocks, crowns, and hand UI did not become
deployment locations. Detector rectangles are explicitly sprite evidence and
were not treated as simulator collision hitboxes. The sample contained valid
no-op, type-only, strict spatial, and candidate-rejected cases, so the audit did
not merely select successful spatial labels. This is direct spot-check evidence,
not a substitute for the exact final 2,000-game integrity and held-out gates.

The 13 failure records at 1,869 completed games were also audited rather than
treated as an unexplained detector loss. They represent five unique source
attempts: one transient Hugging Face read timeout and four repeatedly rejected
replays. Of the four deterministic rejects, one exposed only three distinct
hand cards, two produced zero rows after fail-closed conversion, and one
contained a broken encoded image stream. The apparent concentration in arenas
12, 13, 15, and 25 is repeated retries of those same four corrupt or
insufficient replays, not 13 independent arena-specific failures. None was
silently admitted or converted into a guessed label; the controller continued
to fresh replays to reach the exact 2,000 accepted-game target.

The strict spatial handoff was hardened before final publication. Its verifier
previously checked breadth and declared invariants but did not independently
reopen the artifacts. It now requires the exact 2,000-game target and schema;
rehashes the source run and type-split manifests; proves every assigned and
ignored replay belongs to the correct type split or reserved evaluation set;
rehashes each split corpus and its combining manifest; reconciles replay,
source, and sample counts; reloads every corpus to verify legal expert actions;
and structurally checks that every sparse spatial label is an independent
one-step episode with no invented previous action or reward. The production
location script passes the target explicitly. Tampered-artifact and cross-split
assignment tests were added; 22 combined integrity, type, meta, spatial,
selection, and pipeline tests pass, with Ruff, mypy, and shell syntax clean.
The complete repository suite passes 1,378 tests in 42.81 seconds after the
spatial-publication hardening, while the collector continues independently.

The 24-game development selector was hardened against stale or crossed metric
files before the live screen begins. It now reopens both validation and
held-out records for every candidate and requires the exact candidate,
opponent parent, deck-pool path, seed, deterministic mirror protocol,
defense-v2 reward profile, 12 games per split, and fully reconciled outcomes.
It also rejects duplicate or missing candidates. Previously it took the
checkpoint identity only from the first record and could have summarized a
mismatched second record. Direct stale-heldout evidence coverage and pipeline
coverage pass; Ruff, mypy, and shell syntax are clean. The complete repository
suite passes 1,380 tests in 42.32 seconds while extraction continues.

The 1,900-game operational checkpoint is internally healthy. All 1,900
accepted records have both corpus and log artifacts, positive sample counts,
and deleted raw sources; no artifact is missing. They contain 57,553 labels
(40,388 played-card events and 17,165 exact no-ops). Every arena from 12 through
31 is represented, with 73--115 accepted games per arena. Derived artifacts use
693 MiB, scratch uses 1.0 GiB between one-at-a-time downloads, and the data
volume retains 51 GiB free. This is an inventory/retention audit; exact hashes,
complete-hand eligibility, replay leakage, and combined publication remain the
responsibility of the final 2,000-game verifier.

After the spatial publication and development-evidence guards were hardened,
the three downstream tmux waiters were deliberately reloaded in dependency
order at 1,920 accepted games. This guarantees the postprocess, gameplay
screen, and bounded-RL sessions execute the current scripts rather than relying
on whether a long-sleeping zsh process rereads modified source after its wait
loop. Only the idle waiters were replaced; the collector, raw/corpus artifacts,
logs, and current replay were untouched. All four sessions were then confirmed
live with postprocess waiting on collection, screen waiting on postprocess, and
RL waiting on screen.

The collector reached and exited cleanly at exactly 2,000 accepted games after
2,013 attempts (13 fail-closed records). All 2,000 replay IDs are unique and
all accepted raw files were deleted. The combined type corpus contains 61,140
labels and independently rehashes to
`88970909abeea0b7f35c356d2fcebb6c65a143b5c7276ee95b88558552d95d72`,
exactly matching its manifest. The strict-location corpus contains 1,630 labels
from 219 replays and rehashes to
`cc04d17c0dbb5b0220e4f7e0098f007cbe282a074f852f7138af41d77e148c5d`,
also exactly matching its manifest. The final integrity report passes with
4,279 rendered audit images and zero remaining raw parquets.

The final evaluation reserve is broader than the 1,814-game projection: 18
recurring exact decks, nine archetypes, 71 disjoint replays, and 4,367 samples;
it remains explicitly evaluation-only. The complete-hand type split passes all
leakage and breadth gates with 18,466 rows/850 replays for training, 4,552/201
for validation, 8,117/292 for whole-archetype holdout, and 2,892/126 for
chronology holdout. Seed 1045901 action-type imitation then began on MPS only
after these gates passed.

### Dense TV timing repair and visual-domain adapter rejection (2026-08-13)

The completed 2,000-game corpus exposed two label-construction faults before it
was allowed to drive another policy. First, imported legal masks did not remove
hand cards that exceeded the observed elixir. The affordability repair retained
all but 18 contradictory play rows across the four splits and proved every
remaining expert action legal. Second, the sparse corpus included every detected
play but sampled no-ops roughly every two seconds, while the live policy decides
every 0.4 seconds. The dense-clock reconstruction now emits only decisions backed
by a visual observation at most two seconds old, splits episodes across stale
gaps, advances known elixir and spends, and infers the public next-card preview
only from unambiguous hand transitions. Its train/validation/archetype/chronology
splits contain 71,457/17,374/30,583/10,887 decisions with play rates of
12.995%/13.923%/13.982%/14.678%. The training split has 3,339 contiguous fresh
segments, retains all 9,286 human plays, and knows the next card on 75.66% of
rows. The authoritative manifests are
`reports/tv_royale_raw_cascade_2000_affordability_v1_manifest.json` and
`reports/tv_royale_raw_cascade_2000_dense04_recent2s_v1_manifest.json`.

A matched 1,024-decision visual-versus-live audit then showed why earlier human
fine-tuning failed to transfer. Dense reconstruction reduced mean entity-feature
JS divergence from 0.1026 to 0.0775 bits, speed divergence from 0.4122 to 0.1169,
facing-y divergence from 0.9826 to 0.4494, and recovered next-card visibility
from zero to 76.95%. It did not eliminate the state-domain mismatch: visual masks
still average 922.9 legal actions versus 329.7 live (JS 0.5826), visual states
average 9.46 entities versus 12.89, and 10.08% of detected entities are unknown.
Exact tower HP, entity HP, facing, status clocks, and combat phase remain absent
or unreliable. The audit is
`reports/evaluations/tv_raw2000_dense04_recent2s_v1_observation_domain_gap_seed1047801_1024.json`.

The promoted update-40 champion confirms the mismatch behaviorally. On the dense
visual validation split it predicts a deterministic play on 73.84% of decisions
against a 13.92% human rate, with 30.85% action-type accuracy. A conventional
contextual residual trained for one and three epochs reaches 84.34% and 86.07%
offline action-type accuracy only by collapsing deterministic play to 2.14% and
0.023%. Interpolated candidates at 0.50, 0.625, and 0.75 produce byte-identical
four-game live records to the parent, so that branch learned visual artifacts and
is rejected.

One final controlled screen tested whether a deliberately domain-stable adapter
could salvage the human timing labels without seeing visual-only fields. The new
64-wide residual receives only official mechanics for the four hand cards,
time/elixir, coarse own/enemy troop and non-tower-building geometry, and the
previous public action type. Its zero checkpoint is bit-exact to the champion on
all logits and values; tests prove that HP, tower HP, facing, damage, effects,
combat clocks, and other unreliable fields cannot change its features. One epoch
improves the complete visual validation action-type accuracy from 30.85% to
75.47% and brings deterministic play from 73.84% to 12.51%, but human play recall
is only 9.88%. More importantly, live matched play falls from 5.79% to 2.65%,
playable-state waiting rises from 84.92% to 96.25%, and the endpoint loses 1--3
to the parent with -1.5 crowns/game.

The complete interpolation screen finds no useful transfer interval. Alpha 0.75
is outcome-neutral in all four matched games. Alpha 0.80, 0.90, 0.95, 0.975, and
1.0 score 1--3 and increasingly suppress live placements; alpha 0.85 remains
2--2 but loses 0.25 crowns/game and reduces placement to 4.61%. Therefore no
robust-adapter checkpoint is a promotion candidate and additional epochs are not
run. Evidence is under
`reports/evaluations/tv_raw2000_dense04_robust_adapter_e1_seed1048101_validation*.json`
and
`reports/evaluations/tv_raw2000_dense04_robust_adapter_e1_seed1048101_live_smoke/`.

This closes direct supervised fitting on visual state tensors. The next human
pipeline must retain the observed play time, card choice, cycle, and coarse
placement evidence while generating the learner observation from a simulator
trajectory. That makes training and deployment inputs native to the same domain;
visual frames remain labels and audit evidence rather than policy observations.

### Simulator-native human timing feasibility screen (2026-08-13)

The first replacement pipeline now exists and has passed its bounded feasibility
screen, but it is not a promotion candidate. The reconstructor preserves each
observed public hand, elixir, card cycle, play time, and played slot from the
dense TV corpus while advancing a native Clasher battle against rotating public
strategy opponents. Human play rows force the observed slot at a location chosen
from the update-40 champion's legal spatial logits; intervening 0.4-second human
decisions are no-ops. Consequently every learner observation is produced by the
same simulator encoder used at deployment. The artifact explicitly claims
native-state teacher forcing, not recovery of the unseen source battle state.

An initial strategy-heuristic placement probe was visually rejected after exact
18-by-32 grid overlays exposed implausible arena-edge placements. The corrected
checkpoint-spatial probe was then inspected at early, middle, and late decisions:
troops appeared at plausible bridge and defensive tiles, spells targeted active
combat areas, pocket deployment became available only after its tower condition,
and blocked cells, entity markers, and selected cells remained registered to the
simulator arena. On eight validation replays it retained 457 legal rows and 50
plays with zero illegal forced slots or action failures. Relative to the prior
visual tensor audit, mean entity-feature JS divergence fell from 0.07747 to
0.02412 bits and unknown entities fell from 10.08% to zero. Mask and global-state
distributions still differ because the simulator trajectory is intentionally not
the recorded source trajectory.

A 32-replay training probe retained 2,521 of 3,145 source decisions, including
266 plays, with zero missing decks, illegal labels, unavailable forced slots, or
action failures. One epoch updated only the contextual action-type adapter. On
the independent eight-replay native validation probe, action-type NLL improved
from 1.51495 to 1.42341, play Brier score improved from 0.26673 to 0.25853, and
mean predicted play probability moved from 36.14% to 35.18% against a 10.94%
expert rate. All 457 deterministic actions remained unchanged, including 80%
play recall and 34% played-card-slot accuracy.

The matched four-game live safety smoke is also byte-behavior neutral at the
reported level: both candidate and parent score 2--2 with zero crown
differential, 5.79% placement rate, 84.92% no-op-when-playable, and the same
defense metrics on validation decks and seed 1048001. This is useful evidence
that native observations avoid the catastrophic passivity learned from visual
tensors, but the sample is far too small and the policy did not change a single
held-out deterministic decision. Therefore the result is classified as
feasible but unproven. Scaling to the complete training split is justified only
as the next controlled experiment, followed by independent native held-out and
live no-regression gates before any RL continuation.

### Full simulator-native scaling result (2026-08-13)

The feasibility pipeline was scaled to all usable TV Royale splits with a
diversified, deterministic opponent-deck schedule. The resulting native corpora
contain 56,271 training decisions with 6,593 forced human plays, 12,976
validation decisions with 1,542 plays, 24,419 whole-archetype-holdout decisions,
and 8,641 chronology-holdout decisions. Reconstruction produced no illegal
forced slots or action failures. Sixteen validation trajectories were rendered
against the exact 18-by-32 arena grid and visually audited before training; the
placements remained registered to native tiles and the edge-lane bridge plays
were corroborated by the source label distribution. These artifacts remain
native-state teacher-forcing trajectories, not claims that the unseen source
battle was reconstructed.

Two one-epoch adapters were then screened from the unchanged update-40 parent.
The timing-safe card-choice adapter preserved parent play/no-op timing by
construction, but its LR 1e-4 endpoint regressed deterministic action accuracy
on every untouched split: validation had 50 improvements versus 70 regressions,
whole-archetype holdout 106 versus 114, and chronology holdout 58 versus 78.
Played-card slot accuracy also fell on all three splits, so this endpoint is
rejected without a live promotion gate.

The diversified contextual timing adapter at LR 1e-5 generalized strongly
offline. Relative to the parent it produced 180 improvements versus 14
regressions on validation, 389 versus 32 on whole-archetype holdout, and 113
versus 6 on chronology holdout. Action-type NLL fell from 2.8481 to 2.3399,
3.0564 to 2.5777, and 3.9247 to 3.3337 respectively; play Brier score also
improved on every split. It nevertheless failed the required live no-regression
gate against the exact update-40 parent. On 12 validation-deck mirror games it
scored 5--7 with -0.417 crowns/game, and on 12 held-out-deck mirror games it
scored 6--6 with zero crown differential. The combined result is 11--13 and
-5 crowns. Its placement rate was only 6.20%/5.93%, with 84.79%/73.40%
no-op-when-playable across the two splits.

Therefore neither full-data adapter is promoted, and direct supervised timing
repair is closed as a candidate initialization for now. The evidence is kept as
a representation diagnostic: simulator-native observations make the offline
labels transferable enough to improve three disjoint corpora, but the recorded
human timing is not causally aligned to the synthetic native battle and does
not improve live play. The update-40 policy remains the champion. Any subsequent
human-data path must either restrict supervision to a rigorously validated
timing-invariant target or obtain source-aligned game state; diversified league
RL remains responsible for live strategic improvement.

### Public-history PPO closure and clean challenger restart (2026-08-13)

The first outcome-grounded follow-up deliberately avoided the previously failed
spatial-only PPO direction. It resumed the safe update-45 public-history upgrade
and allowed only the public-history residual, deploy/wait/card-choice head, and
critic to change. All recurrent, entity, and placement-policy tensors remained
frozen. The 12-worker league used 449 training-only decks after removing the
frozen human-meta signatures, emphasized reactive-defense and slow-push, and
included random, the update-40 parent twice, the exact-safety policy, the KATacr
human policy, and two historical league challengers.

The first attempted run exposed an anchor implementation defect and was stopped
after two updates. A zero-output architecture upgrade was considered compatible
with an older anchor for policy KL, but parameter L2 compared the new history
weights against an unrelated random initialization. This produced an anchor L2
near 895 and a weighted loss near 17.9 despite behavior-level KL near 1e-5. The
shared trainer now represents source-absent parameters explicitly and excludes
them from L2 while continuing to anchor every shared parameter. The state-dict
auditor likewise accepts only explicitly declared added prefixes and still
rejects removals or undeclared schema additions. Focused structured-policy and
audit tests pass repeatedly, with clean Ruff and mypy.

The corrected LR 2.5e-6 pilot completed eight updates, 32,768 decisions, and
512 optimizer steps with no early stop, zero clipping at reported precision,
and maximum policy-anchor KL below 8e-6. Exactly 11 authorized actor tensors and
57 critic/value tensors changed. Its predeclared midpoint and endpoint were
then screened against update 40 on 12 validation and 12 whole-held-out-archetype
games each. Both scored 6--6 on both splits with zero crown differential. The
three game-record files for LR 2.5e-6 update 49, update 53, and the subsequent
LR 1e-5 update 49 are byte-identical within each split: validation SHA-256 is
`6bced9a43383159d971eebbc9af68e7fdb544483da0bb19f76c92134b36cfec9`,
and held-out SHA-256 is
`d960ade9fe71aa390a5d0ac41fcfc71bc1765bd40b5afdc4371e383519b461c0`.
The isolated four-times-rate rung processed another 16,384 decisions cleanly,
raised anchor KL to only 0.00013, and remained behaviorally exact. This narrow
history/timing PPO direction is therefore closed as a safe no-op rather than
extended or promoted.

The larger-window response is a separate clean challenger, not another
micro-patch. It starts from exact update 40, adds four zero-output public-history
slots, and allows the complete base actor/critic core to learn while freezing
the accumulated repair paths. It uses the same leakage-free 449-deck pool and
12-opponent diversified league, LR 1e-5, defense-v2, two PPO epochs, a 0.02
forward policy-KL anchor, 64 environments, 12 CPU rollout workers, and an MPS
learner. The predeclared phase is 64 updates/262,144 decisions through update
104. Updates 56, 72, 88, and 104 will receive identical 24-game validation plus
whole-archetype direct screens only after the trainer exits. A separate queued
gate verifies every update, all finite/stability bounds, authorized parameter
scope, and then writes a development candidate only if one checkpoint beats the
parent. This challenger is active training evidence, not a promotion or a
mid-ladder claim; update 40 remains untouched and authoritative.

### Clean-challenger stability correction and half-rate restart

The first full-core clean challenger at LR `1e-5` was stopped deliberately at
update 48. Update 43 tripped the predeclared PPO KL early-stop boundary after
53 of 64 optimizer steps (`kl_stop=1`), so that lineage failed the strict
training-stability contract before any promotion screen. Its artifacts remain
under `checkpoints/midladder_clean_history4_league_seed1048701` and
`reports/midladder_clean_history4_league_seed1048701.log` as rejected evidence;
it was not evaluated or promoted.

A clean half-rate restart is now running from the unchanged update-40 parent
with seed `1048702`, LR `5e-6`, the same 449-deck training-only pool, diversified
12-opponent league, 64 environments, 12 CPU actors, and MPS learner. Its tag is
`midladder_clean_history4_league_lr5e6_seed1048702`. A separate gate waits for
the trainer by exact tmux-session name, verifies every update through 104,
audits the authorized state-dict scope (including the declared zero-output
public-history addition), and only then runs matched validation and whole
held-out-archetype screens at updates 56, 72, 88, and 104. Any KL early stop
rejects this restart as well; update 40 remains the champion unless a candidate
beats it under the declared gates.

### Clean-challenger rejection and persistent public-cycle belief (2026-08-13)

The half-rate full-core challenger completed all 64 requested updates through
104, adding 262,144 decisions. Every update performed all 64 optimizer steps,
with no KL stop, finite tensors and metrics, and endpoint anchor KL 0.00978.
Numerical stability did not translate into strategy. Fixed update-40 mirror
screens scored 9--15 at update 56, 13--11 at update 72, 8--16 at update 88,
and 8--16 at update 104 across the 12-game validation and 12-game
whole-archetype holdout pools. Update 72 therefore entered the frozen 60-game
priority gate. It produced zero improvements, two outcome regressions, 58
unchanged games, and a six-crown loss relative to update 40. One regression
reproduced the known X-Bow versus Log Bait failure at seed 36310; the other was
Graveyard versus X-Bow at seed 42364. The candidate was rejected before the
168-game and human-meta gates. Evidence is under
`reports/evaluations/midladder_clean_history4_league_lr5e6_seed1048702/`.

This closes full-core PPO on the four-play history representation rather than
motivating another lower learning-rate rung. The representation forgets cards
revealed more than four opponent plays ago, even though those identities remain
publicly knowable and determine the opponent's possible cycle. A leakage-free
belief experiment was therefore built from the final 2,000-game TV Royale
train/validation/whole-archetype/chronology split. Its input at each decision is
only prior public plays: the four most recent card IDs and ages, plus the first
eight unique opponent cards in discovery order. Its target is current hidden
four-card-hand membership.

Across three preliminary seeds, persistent seen-card memory improved top-four
hand recall on every untouched split. The actual policy-integrated pretrain at
seed 1049001 improved validation recall by 23.79%, whole-archetype recall by
28.19%, and chronology recall by 67.31% relative to an otherwise matched
recent-four model. Only 254,747 belief parameters were trained. The
policy-facing outputs remained zero, and a 12-step recurrent simulator probe
proved bit-exact joint logits, values, and recurrent state against update 40
with SHA-256
`d9551c3766e9d6a8007588b6a484c08ea1950d18b3e4a20d5a5274854222f1df`.
The checkpoint and report are
`checkpoints/public_cycle_belief_relational_seed1049001/policy_v2_update_000040_belief.pt`
and
`reports/evaluations/public_cycle_belief_relational_seed1049001.json`.

Two zero-safe RL interfaces then tested whether the learned belief could improve
live play. The first sent belief through the existing public-history residual
into the recurrent trunk and trained only its final weight matrix. Eight
updates/32,768 decisions were numerically clean, and the state-dict audit proved
that exactly `public_history_projection.2.weight` changed. Updates 44 and 48
each scored 12--12 with zero crowns across validation plus whole-archetype
holdout. Update 48 was byte-identical to update 44 on all held-out games and
changed only one tower's remaining HP in one validation game. This interface
was rejected as too diluted.

The second interface is explicitly relational and still card-agnostic. A
zero-initialized query from opponent belief is scored against the four current
hand-card representations, while a separate zero-initialized head adjusts only
wait and ability logits. Placement remains under the frozen base policy. At LR
1e-5, only `public_belief_card_query.weight` and
`public_belief_timing_head.weight` changed across 32,768 decisions; peak anchor
KL was 0.00032 with no KL stop or passivity collapse. Updates 44 and 48 again
each scored 12--12 with zero crowns. The endpoint changed two held-out game
trajectories but no outcomes. A fresh 2.5e-5 dose repeated the exact narrow
scope, remained stable with peak anchor KL 0.00036, and also scored 12--12 with
zero crowns. It did not earn the priority gate. Evidence is under
`reports/evaluations/midladder_belief_relational_seed1049002/` and
`reports/evaluations/midladder_belief_relational_lr25e6_seed1049003/`.

The conclusion is deliberately split. Persistent public cycle/deck belief is a
real, held-out-generalizing representation improvement and remains worth
keeping. The tested outcome-only PPO interfaces do not provide evidence that
the policy can exploit it, so neither is promoted or extended indefinitely.
Update 40 remains the champion. The next use of belief should attach to a
source-aligned tactical target with direct consequences--for example opponent
hand-conditioned defense/card-choice values or bounded tactical search--before
another diversified league phase.

### Public-belief counterfactual tactical target closure (2026-08-13)

The proposed direct-consequence target was implemented and audited rather than
assumed. At each threatened state it cloned the exact battle, evaluated one
frozen-policy location for every legal hand slot plus no-op and ability, averaged
both simultaneous-action application orders, and stored the exact pre-forward
recurrent state with public recent/seen-card history. Training and validation
used signature-disjoint deck pools, examples were separated by eight decisions,
and per-episode caps prevented adjacent states from dominating. Exact clone
determinism, root non-mutation, player-one canonical actions, legal candidates,
resource accounting, and zero-output architecture compatibility are covered by
focused tests. The policy-facing fit remained restricted to exactly
`public_belief_card_query.weight` and `public_belief_timing_head.weight`.

The first one-shot target exposed a causal accounting defect before scale-up.
Defense-v2 credited newly deployed material through its board-value term but did
not debit the elixir spent at the root, so only two of 48 training labels were
no-op. Its best belief-plus-board-interaction fit appeared promising on the
24-game direct screen (14--10, +9 crowns), but the frozen priority gate rejected
it with one improvement, seven regressions, and a 29-crown loss over 60 paired
games. A heuristic threat gate removed the apparent gain and scored 11--13 with
-2 crowns on the direct screen. Neither checkpoint was promoted.

The scorer was then corrected to pair board material with remaining elixir on
the same normalization. The resulting 96/48/48 corpus had 50 of 96 training
targets select no-op, spanned 16 learner decks and 15 opponent decks, and no
longer treated deployment as free value. Hard labels failed held-out accuracy.
A predeclared soft-value sweep found one fit that improved both validation and
held-out tactical accuracy offline, but live play rejected it decisively:
validation scored 2--10 and held-out 6--6, for 8--16 and -15 crowns overall.

Finally, the counterfactual rollout was made closed loop. After each root action,
the frozen update-40 policy and the same deterministic strategy opponent made
subsequent decisions every eight ticks, with recurrent state, public card
history, elixir, deployments, and future responses evolving independently in
each clone. A 48/24/24 corpus spanned ten training deck draws; a low-dose soft
fit improved validation and held-out tactical accuracy from 50.0% to 54.2% on
both untouched splits. The live screen nevertheless scored 4--8 on validation
and 4--8 on held-out, losing 17 crowns. It did not enter the priority gate.

This closes short-horizon counterfactual distillation into a globally active
two-matrix card-choice residual. The repeated offline/live inversion is direct
evidence that these local labels are not a promotion proxy, even after resource
balancing and closed-loop continuation. Persistent belief remains valid, but no
counterfactual challenger is promoted and update 40 remains the champion. The
next tactical experiment should be an abstaining inference-time search/value
override with an explicit minimum-gain guard and paired no-regression screens;
if that cannot outperform update 40, this tactical-search family should be
discarded rather than distilled or patched further.

That final abstaining search was also tested and rejected on 2026-08-13. It
activated only when update 40 selected no-op under public incoming danger,
considered one legal frozen-policy location per hand card, assumed no unseen
opponent deployment, paired public board material with the learner's own
remaining elixir, and required a minimum value improvement before overriding.
The first three validation settings (64-tick horizon, danger 0.025, minimum
gains 0.0025/0.005/0.01) were identical in outcome: each scored 1--5 and lost
eight crowns over six games. Overrides occurred on only about 0.16% of policy
decisions, so rare interventions were already harmful; the remaining threshold
sweep was stopped rather than selecting a nearly-always-abstaining no-op. This
closes the heuristic short-horizon tactical-search family as well. The next
step must first validate a long-horizon outcome value estimator on complete
trajectories before using any search or local target again.
# Reactive 489K reward-development baseline (2026-08-13)

The 6.54M-parameter update-40 lineage is no longer the reward-development
baseline. An exact Hog 2.6 mirror audit showed zero Hog plays in 4/12 games,
including long affordable hand locks, even though the human training split
contained 424 Hog placements. Its epoch-5 type-head parent slightly worsened
Hog validation accuracy and the subsequent PPO phase did not train the main
action-type head. That lineage is retained only as a comparison checkpoint.

A clean 488,644-parameter policy keeps global entity attention, an attention
tile decoder, hybrid card mechanics, and a 128-unit LSTM, but uses only two
64-wide actor blocks and one critic block. One broad imitation epoch took about
five minutes including full post-epoch evaluation. A card-balanced complete-
hand TV Royale type fine-tune took under one minute. Card balancing is generic:
clipped inverse-frequency weights are computed from expert-played card IDs in
the training partition, with no Hog or card-name branch.

The fine-tuned checkpoint is
`checkpoints/reactive489k_seed1051101/raw1000_balanced_epoch5.pt`. On the
untouched 37-replay TV holdout, action-type accuracy rose from 24.03% before the
fine-tune to 30.58%, action-type NLL fell from 3.7527 to 1.5684, and wait recall
rose from 0% to 26.63%. On twelve held-out-deck games against the balanced
strategy bot it scored 8-4 with equal four wins from each seat. This bot is not
a human-skill proxy.

The exact Hog utilization gate now passes: 56 Hog plays in 12 mirror games,
zero zero-use games, 54.37% aggregate affordable-window conversion, 53.45% as
player 0, and 55.56% as player 1. The remaining blocker is defensive behavior:
defensive action rate under measured threat is only about 9-10% against both
balanced and reactive-defense bots. This small policy is therefore the fast
reward-development baseline, not a low-human or mid-ladder promotion.

The first matched reward screen used the canonical-lane version of that parent,
32 environments, eight CPU actors, an MPS learner, 24,576 transitions per arm,
and a frozen-policy KL anchor. Each arm finished in roughly 90 seconds at about
300--340 decisions/s. Objective-v1 regressed the reactive-defense held-out
screen from 8-4 to 6-6, lowered defensive response, and weakened Hog-window
conversion; it is rejected. Defense-v3 at `1e-5` raised reactive-defense
response from 10.60% to 11.72% and passed the Hog gate, but also regressed that
screen to 6-6. Across balanced plus reactive-defense screens the parent scored
17-7 and defense-v3 scored 15-9, so that arm is also rejected.

A final isolated defense-v3 arm at `3e-6` preserved the parent's 17-7 aggregate
record but did not produce a consistent defensive-response gain and again had
one zero-Hog game. It is not promoted. The evidence says the current danger
potential can nudge behavior but is too indirect to teach reliable reactive
defense. Keep the 489K imitation parent and redesign the defensive teaching
signal rather than extending either PPO arm.

### Reactive 489K defense-teaching closure (2026-08-13)

The next reward experiment replaced the larger instantaneous danger coefficient
with explicit four-second public threat episodes. An episode began only after
absolute incoming danger crossed 0.05, resolved once below 0.02 or at its
deadline, debited Crown Tower health lost during the episode, and could not
rearm until the original push cleared. Direct tests proved one reward per push,
timeout hysteresis, destroyed-tower failure, mirrored antisymmetry, and no use
of card names, selected actions, target IDs, or hidden state.

That implementation exposed two independent measurement/schema bugs before
training. The evaluator had derived per-player incoming danger from the signed
net danger edge, so simultaneous pushes canceled. It now measures each player's
absolute incoming danger while the legacy signed reward potential remains
bit-for-bit unchanged. Also, resumed checkpoints declaring canonical lane
globals built corrected observations in the learner but did not pass that flag
into every rollout/evaluation environment. The schema flag now reaches local,
parallel, and evaluation environments. The final defense-v2 scalar/shadow/on
digest remains
`9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349`
with zero shadow mismatches.

The stateful reward itself failed both doses. At LR `3e-6`, reactive-defense
remained 8-4 but threat success moved 46.15% to 45.98%; balanced fell 8-4 to
7-5 while crown margin fell +0.417 to +0.167. At LR `1e-5`, reactive fell to
6-6 with 37.50% threat success and balanced fell to 5-7 with 33.33% success.
The failed reward profile was removed from the production choices rather than
left as another tuning axis. Its card-agnostic threat tracker remains only as a
stronger evaluation metric: resolved-event success and mean defensive outcome,
instead of counting every non-noop under threat as a defensive response.

Human defensive-context imitation was then tested as a fast alternative.
Visible enemy troops/buildings in the tower zone were upweighted without
dropping broad rehearsal rows. Five epochs produced misleadingly better NLL
and accuracy by collapsing toward wait: held-out play recall fell to 3-7% and
correct-card recall nearly vanished. Generic six-way action-type balancing was
therefore crossed with and without context weighting. Five epochs still moved
toward wait. A one-epoch type-balanced dose did improve human pressure-state
play and card recall on validation, whole-archetype, and chronology splits; the
extra defense-context weight added no benefit. Live play inverted the offline
gain: reactive-defense fell 8-4 to 6-6, balanced fell 8-4 to 7-5, and the Hog
gate failed with a zero-use game in each seat. All challengers are rejected.

This closes coefficient tuning and passive-corpus weighting for defense on the
489K baseline. The frozen parent remains
`checkpoints/reactive489k_seed1051101/raw1000_balanced_epoch5_canonical_lanes.pt`.
The next defense experiment must isolate causal credit: short, procedurally
varied simulator episodes that begin with an incoming push and terminate on a
clear survival/clearance outcome, with held-out threat compositions and the
same full-game/Hog no-regression gates. No failed checkpoint is promoted.

### Reactive 489K procedural-defense result (2026-08-13)

The causal-credit experiment is now implemented and closed. Procedural episodes
sample only troop cards from the attacker's actual eight-card deck, choose a
Princess Tower and mirrored seat, inject a four-to-seven-elixir push, give the
defender full elixir, and terminate after 240 ticks. The terminal outcome
rewards threat clearance and debits damage to the originally threatened tower.
The default full-game environment remains unchanged. Direct tests cover deck
provenance, determinism, mirrored player 1 behavior, destroyed towers, the
opt-in horizon, zero-sum terminal reward, and default-off behavior.

Calibration proved that this is a useful short task rather than a disguised
full-game benchmark. On 64 training-pool scenarios, no-op failed 90.625% while
the card-agnostic reactive-defense script failed 25.0%. On the held-out deck
pool, no-op failed 78.125% while the script failed 6.25%. The frozen 489K parent
failed 73.4375% of a separate 64-scenario held-out screen with mean outcome
-0.5179 and mean threatened-tower loss 0.4162. Each policy screen takes about
12.5 seconds on CPU.

The initial PPO launch was itself rejected as an experiment configuration: a
256-sequence recurrent minibatch peaked at 28.9 GB on the 24 GB host and
swapped. With one PPO epoch and 32-sequence minibatches, the exact same 489K
model trains 1,024 decisions per update at roughly 450--500 decisions/s. Eight
updates take about 22 seconds and twelve about 31 seconds. The small model is
therefore not the current iteration bottleneck.

At learning rate `3e-6`, deterministic and matched stochastic policy behavior
were unchanged after 12,288 decisions, so the arm was rejected as inert. At
`1e-4`, held-out failure improved only 73.44% to 70.31%. At `3e-4`, the
unrehearsed update-8 checkpoint improved held-out failure to 48.44%, mean
outcome to -0.0798, and tower loss to 0.2556. That isolated gain did not
generalize to full play: reactive-defense fell 8-4 to 5-7, balanced fell 8-4
to 4-8, and Hog 2.6 fell 9-3 to 3-9 with four zero-Hog games. It is rejected.

Frozen-parent KL on ordinary human replay states exposed the preservation
frontier quickly. Coefficient 5 erased the defense change by update 8;
coefficient 1 improved only one of 64 held-out scenarios. A seed-matched 0.1
coefficient at update 4 improved failure to 68.75%, reactive full-game defense
event success from 46.15% to 53.19%, and balanced success from 38.24% to
46.30%. It still regressed the paired screens from 16-8 aggregate to 14-10 and
Hog from 9-3 to 8-4. A 50% parent/candidate interpolation preserved a smaller
scenario gain (71.875% failure) and scored 10-2 on Hog, but still regressed
reactive-defense to 6-6 and balanced to 7-5. Both are rejected.

The conclusion is specific: the procedural terminal signal can teach reactive
defense in seconds, but scenario-only PPO shifts the shared action policy away
from ordinary offense faster than replay KL can preserve it. Do not shrink the
network merely to accelerate reward experiments. The 488,644-parameter model
is the smallest evidence-backed floor: previous raw stateless and cheaper GRU
ablations were independently dominated, while this policy already supports a
sub-minute training/screen loop. Keep the frozen parent. The next training
change must interleave actual ordinary-play rollouts with procedural episodes
inside the same update, rather than approximating the missing state
distribution with a coefficient or post-hoc blend.

That final mixed-state test is also complete. The stationary collector now
supports both episode types in one batch: injected-defense environments force
their attacker to no-op, while non-scenario environments continue to execute
their configured strategy bot. The behavior is directly tested and the legacy
default remains scenario-free. With per-reset scenario probability 0.8,
balanced ordinary games, LR `3e-4`, 32 environments, and eight updates, the
pilot took 20.2 seconds. Because full games are much longer than 240-tick
scenarios, the transition mixture still contains substantial ordinary play.

The mixed update learned the isolated task more conservatively: held-out
failure moved 73.44% to 71.88% at update 4 and 62.50% at update 8. It still
failed every promotion gate. Reactive-defense moved 8-4 to 7-5, balanced moved
8-4 to 5-7, and Hog moved 9-3 to 7-5. Full-game defense-event success did not
improve (46.15% to 45.21% reactive and 38.24% to 37.68% balanced), despite the
large artificial-scenario gain. Reject the checkpoint and close this exact
shared-PPO scenario curriculum. The short scenario remains a useful reward and
architecture diagnostic, but it is not a promotion path until the learner can
localize the update to threat-state behavior without shifting the global
action distribution.

### Reactive 489K localized-defense architecture closure (2026-08-13)

Two bounded frozen-base heads tested whether the procedural task could be used
without shifting ordinary offense. Both used a hard, public-state gate: a
visible enemy troop/building below canonical y=0.45. The gate contains no card
name, selected action, hidden simulator state, or scenario flag. Outside that
gate the frozen parent remained exact. Training only 6.2--6.4K new parameters
reached roughly 600--750 decisions/s after warmup, so learner cost was not the
limitation.

The first head could change all six slot/wait/ability logits. At LR `3e-4` its
weights moved but deterministic behavior was unchanged through 12,288
decisions. At LR `3e-3`, held-out procedural failure improved monotonically
from 73.44% to 71.88%, 57.81%, and 53.13% at updates 4/8/12. Localization
prevented the catastrophic regressions of shared-policy PPO but did not produce
a promotable dose. Update 8 preserved balanced at 8-4 and raised its defensive
success from 38.24% to 47.06%, but reactive-defense fell from 8-4 to 7-5.
Update 12 preserved reactive-defense at 8-4 and raised defensive success to
52.44%, but balanced fell to 7-5. Their midpoint also scored 7-5 against
balanced. This is a dose frontier, not evidence for more coefficient search.

The procedural outcome was then corrected to charge net defensive resource
loss while crediting surviving public troop/building value. On a fresh 64-case
held-out calibration, no-op failed 70.31%, the frozen policy failed 67.19%, and
the card-agnostic reactive-defense script failed 17.19%. The script consumed
0.328 of the normalized response budget on average, while no-op consumed zero,
so the objective still separated competent defense without treating an
expensive clear as free. Direct reward/scenario tests remained green.

With that efficiency-aware target, the six-output update 8 passed the two bot
screens exactly: reactive-defense 8-4 with defensive success 55.17% (parent
46.15%), and balanced 8-4 with defensive success 45.83% (parent 38.24%). It
also preserved the Hog 2.6 match record at 9-3 and made 54 Hog plays with
54.55% affordable-window conversion. The strict utilization gate nevertheless
failed: zero-Hog games increased from one to two, one in each seat. A paired
trace isolated the new failure to game 7, where the parent played Hog twice but
the challenger played it zero times and reduced mean affordable Hog
probability from 0.141 to 0.046. The match remained a 0-1 loss. Thus the head
was substituting cards under a prolonged threat, not merely improving timing.

A final timing-only head made that failure impossible by construction: it
applied one shared delta to all four hand slots relative to wait, plus an
ability delta, preserving conditional hand-card probabilities. It learned the
efficiency task more slowly; update 12 improved held-out failure from 76.56%
to 67.19%. It still regressed reactive-defense from 8-4 to 7-5 despite raising
defensive success to 51.25%. This rejects the capacity-restricted variant as
well.

The localized-defense architecture family is closed. Both failed heads and
their checkpoint-upgrade scripts were removed from production source rather
than retained as dormant options. The calibrated efficiency-aware scenario
remains only as a diagnostic. The result is broader than an optimizer setting:
short defensive survival/clearance objectives do not capture complete-match
elixir timing, counterpush opportunity, and win-condition pressure well enough
to serve as a policy-promotion target. Further progress must return to
complete-game human-distribution or diversified league objectives and judge
defense as one held-out metric, not optimize it as an isolated terminal task.

### Incremental TV Royale imitation closure on the 489K policy (2026-08-13)

The second 1,000 raw-TV batch first exposed a split-integrity bug in the
experimental workflow rather than the splitter itself: independently hashing
the larger combined corpus reassigned historical replay IDs. Eighty-four old
held-out replays entered the proposed new training split, while 93 old training
replays entered new holdouts. The split utility now accepts an explicit prefix
of completed run-manifest replay IDs as a reserve set. Reserving the first
1,000 completed recordings plus the prior human-metadata reserve produced a
strictly disjoint second-batch split: 740 replays and 16,971 samples, with zero
overlap against all 760 first-batch replays. Combining only the two training
partitions yielded 865 complete replay episodes and 19,940 samples. Direct
split tests, Ruff, and mypy pass.

Three compact-policy adaptations tested whether that additional complete-game
data could safely improve the incumbent
`raw1000_balanced_epoch5_canonical_lanes.pt`.

1. A full shared-policy fine-tune improved joint NLL on all six replay-disjoint
   holdouts. At epoch 3 the old validation/archetype/chronology NLLs were
   1.3013/1.3037/1.3008, and the new validation/archetype/chronology NLLs were
   1.2800/1.3385/1.3954. Those aggregate numbers concealed a wait/play
   distribution failure. Played-slot recall regressed, balanced live play fell
   from 9-3 to 6-6, and playable-state no-op rose to 0.857. The same checkpoint
   scored 12-0 on the Hog screen with 73 Hog plays, proving that one
   win-condition screen cannot override the general safety failure.
2. A zero-output 772-parameter conditional slot adapter preserved the parent's
   play/wait/ability mass and improved conditional slot loss on every holdout.
   It changed only eight additional decisions correctly across all six
   partitions and still scored 6-6 against balanced. It is rejected.
3. One simulator-spatial rehearsal epoch improved its in-domain validation
   loss from 2.7447 to 2.0586 and exact accuracy from 0.4771 to 0.5965, but
   catastrophically inverted all six raw-TV holdouts: NLL rose to roughly
   3.3--3.42, play probability approached 100%, and no-op recall approached
   zero. No live gate was warranted.

This independently confirms the earlier visual-state closure at compact scale.
Raw video detections lack the simulator's exact HP, statuses, combat phase,
facing, and legal-action context; an apparently aligned frame label is not a
causally aligned simulator action target. More epochs, a larger adapter, or
interpolating these checkpoints would optimize the mismatch, not human skill.
TV Royale remains useful for deck priors, card-cycle/history statistics,
behavioral diagnostics, and future belief-state supervision, but direct action
imitation is closed for this state representation. The original 488,644-
parameter incumbent remains the promoted compact parent.

### Terminal-outcome league experiment rejection (2026-08-13)

The remaining complete-game reward hypothesis is now isolated as
`outcome-v1`. Its nonterminal public-state potential is exactly zero; normal
matches retain only the terminal +1/-1 outcome, the existing tiny symmetric
elixir-leak term, and the generic invalid-action penalty. This directly tests
whether the offensive race behavior was induced by dense tower-damage
potentials without introducing a defensive card, lane, threat, or scenario
special case. The profile returns before public-state breakdown scans and is
covered by direct zero-potential and terminal-outcome tests. Existing reward
profiles and checkpoint behavior are unchanged.

The first pilot resumes the frozen 489K incumbent, uses full matches from the
diversified procedural deck pool, and retains L2 plus forward-KL anchoring.
Promotion is predeclared rather than selected after viewing results: at minimum
it must preserve balanced at 9-3, reactive-defense at 8-4, and strict Hog
utilization, then survive the broader strategy and held-out-deck suite. A
better training reward curve alone is not evidence of promotion.

The bounded run completed 20 updates and 81,920 transitions over 64 full-game
environments. Twelve actor workers covered random, all six public strategy
families, and four frozen-parent workers. Throughput remained 262--304
decisions/s while RoadForge concurrently occupied one CPU core. PPO itself was
numerically quiet: clipping stayed at or below 0.1%, optimizer KL remained
below 0.0002, and frozen-parent policy KL rose gradually from 0.00013 to
0.00293. The sparse signal was present rather than accidentally disabled; 201
complete episodes emitted terminal outcomes.

Matched deterministic play nevertheless failed immediately. Updates
4/8/12/16/20 each scored 2-10 against balanced on the parent's exact held-out
deck/seed screen, versus 9-3 for the frozen incumbent. Crown margin was -2.25
at update 4 and approximately -2.17 thereafter. Playable-state no-op rose from
the parent's 0.738 to 0.972/0.976/0.980/0.980/0.980, while defensive action
rate under threat fell from 0.0798 to 0.0112 and then 0.0045. The soft KL
average concealed a deterministic argmax boundary crossing toward wait.

No checkpoint earns the reactive-defense or Hog screens. `outcome-v1` and its
tests have been removed from production choices; the checkpoints and matched
reports remain only as audit evidence. This closes the scalar-reward family on
the compact lineage: dense tower potential encourages racing, sparse terminal
outcomes encourage waiting, and stronger defensive potentials or isolated
scenario outcomes damage complete-game offense. The next improvement must
come from a stronger state-aligned action teacher, search, or opponent league,
not another handcrafted reward coefficient.

### Terminal counterfactual action-teacher rejection (2026-08-13)

A public complete-game outcome head first established that observational value
prediction was not sufficient for action selection. Its held-out
player-swap-antisymmetric AUC reached 0.8888 early, 0.9182 midgame, and 0.9547
late, but an exact terminal rollout counterexample chose Balloon while the
unchanged no-op branch was the actual win. The head therefore remained useful
only as a terminal evaluator, never as a direct logit reranker.

The subsequent collector evaluated actual action interventions: at sampled
playable states it rolled no-op and one best legal location per action type to
the end of the game while carrying the frozen policy's recurrent state. A
96-game procedural training split produced 383 states, 36 decisive corrections,
57 strict safe-wait preferences, and 60 distinct candidate cards. A disjoint
48-game validation split produced 187 states, 14 decisive corrections, 16
safe-wait preferences, and 49 distinct candidate cards. Training contained no
Hog Rider correction; validation contained three, making them a genuine
cross-card timing transfer test. The train feature and score hashes were
`104d0431d679e366adf76a18900ddf55ffe3e98696727e8b3ffec39c44ead42d`
and `30da683342f0c29f5b7944c50766f0bdb66e880d46ea05528c9e46826ca78bcb`;
validation hashes were
`6bbfeaf1bb874ed5c4150718e96f1eee152a1655b64550c4cf1947f2a7a5b389`
and `559c2b92d316558dcb5f4bbc474f357e405a2aae198c33240827dece8d2aadfb`.

An unconstrained six-output action adapter fit the small original corpus but
regressed the strict Hog screen from 9-3 to 7-5 and produced three zero-Hog
games, so it was rejected. The corrected disjoint experiment restricted the
adapter to one shared placement-versus-wait delta, preserving all conditional
hand-slot probabilities exactly. The 193-effective-parameter candidate was
selected at epoch 20, before later optimization traded away safe-wait accuracy.
It reached 12/14 validation correction accuracy and 15/16 validation safety
accuracy, including all three unseen Hog corrections.

Those preference metrics did not survive complete gameplay. On the incumbent's
exact held-out balanced deck pool and seed 1051402, the timing candidate scored
6-6 with crown margin -0.1667, versus the frozen incumbent's 9-3 and +0.4167.
Playable-state no-op rose from 0.7381 to 0.8068 and defensive action rate fell
from 0.07976 to 0.07296. This failed the first predeclared no-regression gate,
so reactive-defense, Hog-utilization, and broad screens were intentionally not
run. The adapter is rejected and no alpha, epoch, or coefficient sweep is
warranted. Sparse terminal counterfactual preferences remain too incomplete
to preserve complete-game timing even when they transfer semantically across
cards.

This also sharpens the raw-TV conclusion above: the current sparse extraction
lacks HP/status/combat context; replay video itself does not inherently lack
all of it. The next data gate is therefore a measured public-state perception
pipeline for tower and entity HP, shields, visible statuses, temporal tracking,
and confidence/missingness masks, with simulator observations degraded to the
same public visual domain and every new channel visually audited before scale.

### Confidence-aware public-state adapter gate (2026-08-13)

The public-state work now recovers visible normalized HP, position, causal
motion, supported identity, public hand/history, tower state, battle time, and
per-field confidence. Full matched simulator sidecars cover 56,271 training
rows plus disjoint validation, held-out-archetype, and later-chronology splits.
The 1,000-game multi-arena video collection remains in progress; details and
digests are in `reports/tv_royale_public_state_benchmark_20260813.md`.

The final publication now has a quantitative perception gate in addition to
file integrity and visual contact sheets. It recomputes every public sidecar
from its NPZ arrays, requires all visible bodies to have measured positions,
checks every per-game manifest statistic, and binds each sidecar and game
manifest by SHA-256. The predeclared final thresholds are at least 50% entity
HP coverage overall and 45% in every arena, 45% mean HP confidence, 30% motion
coverage overall and 25% per arena, and three tower-HP readings per sample
overall plus 2.5 per arena. On the in-progress 472-game snapshot, every gate
already passes: entity HP coverage is 56.52% overall (minimum arena 52.74%),
mean HP confidence is 65.10%, motion coverage is 39.10% (minimum arena 36.29%),
and tower HP yields 4.07 readings per sample (minimum arena 3.95). These are
health checks for the extractor, not model-skill evidence; the exact 1,000-game
run must pass again before any split or training handoff is created.

Direct human imitation on degraded state was rejected. Both unweighted and
card/action-balanced arms exploited the dominant no-op labels: validation play
recall collapsed from 19.52% for the frozen control to 0.20% and 1.88%.
Aggregate accuracy was therefore a misleading metric.

Exact-to-public policy distillation was the viable representation step. Only
the new confidence projections train, using the frozen incumbent's exact-state
distribution as the target. An initial adapter improved public KL but altered
fully exact simulator policy and failed gameplay, so it was rejected. The
corrected adapter gates its residual by uncertainty; confidence 1.0 forces a
zero residual for all learned weights and biases. Seed 1055205 reduced joint KL
by 36.3% on disjoint validation, 38.5% on held-out archetypes, and 48.3% on
later chronology, while improving deterministic teacher agreement on all
three. Its exact-state 12-game stochastic balanced record is byte-identical to
the 9-3 incumbent record, SHA-256
`c92c12d4cd3590b058ffe741b3f7af20bf5a09de1f351fbb232f9d1cf3824ff1`.

This adapter is accepted as perception plumbing, not as a stronger policy. No
human-label update is promoted until the 1,000-game corpus finishes, passes
multi-arena visual validation, and a play-conditioned objective avoids the
demonstrated no-op shortcut under held-out replay and gameplay gates.

### Semantic conditional card-choice gate (2026-08-13)

The first timing-safe slot adapters were rejected. Both the global four-slot
residual and a card-semantic residual could lower human conditional NLL while
worsening held-out top-1 card choice. On the frozen 38-game public-state
snapshot, the semantic residual reduced held-out slot accuracy from 19.32% to
15.46% and produced nine action-type regressions against five improvements.
No additional learning-rate or epoch sweep was run.

The replacement experiment removes the incumbent's arbitrary four slot logits
and scores the actual hand cards using a state query against their learned
identity plus data-derived mechanics embeddings. It renormalizes those scores
to the incumbent's original legal-placement mass, so placement versus wait,
ability use, and placement geometry are invariant. A new separate sampling-deck
path retains the full 155-token observation vocabulary while collecting from
disjoint procedural deck splits.

One fixed schedule trained on 1,752 incumbent placements from 455 training
decks. Conditional slot agreement reached 83.86% on 446 placements from 82
unseen decks and 83.85% on 650 placements from 151 decks belonging entirely to
held-out Graveyard, Lava Hound, Royal Hogs, and X-Bow archetypes. The identical
held-out performance is evidence of semantic transfer rather than deck
memorization, but the residual 16% disagreement is too high for direct
replacement of the accepted policy.

The pretrained scorer did show positive zero-shot transfer to public human
replays: full-snapshot slot accuracy rose from 11.17% to 12.82%, with 29
previously wrong action types corrected and 16 regressed, while deterministic
play/wait timing stayed fixed. A single five-epoch human fine-tune failed the
predeclared top-1 gate: held-out slot accuracy fell from 28.50% to 27.05% even
as NLL improved. That human-tuned checkpoint is rejected. The architecture and
simulator pretraining evidence are retained for the final 1,000-game corpus;
promotion remains contingent on disjoint replay, held-out archetype, Hog-use,
defense, and complete-game no-regression gates.

### Mechanics-only card scorer and corrected TV timing prevalence

A smaller follow-up removed card identity from the semantic scorer and exposed
only 16 normalized official mechanics per legal hand card. Three fixed linear
seeds averaged 86.77% conditional agreement on disjoint procedural validation,
84.36% on whole held-out archetypes, and 49.41% on the frozen public human
prefix, compared with the incumbent's 45.05% conditional human slot accuracy.
Richer v3 semantics reduced transfer, and a 64-wide MLP added negligible
simulator accuracy while worsening human NLL from 1.292 to 2.086. Five-epoch
human fine-tuning was not repeatable across seeds and is rejected. The v1
linear mechanics scorer is the current conditional-card candidate for the
final 1,000-game corpus; it is not integrated or promoted yet.

The same audit corrected a misleading property of the retained replay rows.
Every detected play is kept, whereas no-ops are sampled and then filtered, so
the retained 72.43% play ratio is not a natural human rate. Replay duration at
the 4 Hz deployment clock implies 13,283 decisions and a 5.93% human play rate.
Only 27/38 games retained at least one representative no-op; on those games the
duration-weighted target is 6.71%. The accepted public checkpoint predicts
11.52% deterministic play, only 26.88% human-play recall, 89.58% no-op recall,
and 36.52% mean play probability. Thus timing is genuinely miscalibrated, but
the no-op weights span 10.88--547 and 11 episodes provide no no-op state at all.
That evidence does not justify another small-prefix timing adapter, especially
after prior offline timing improvements failed complete-game gates. The next
human-label screen freezes timing, tests mechanics-only card choice, and leaves
timing improvement to outcome-grounded diversified league RL pending the final
corpus audit. Full evidence is
`reports/tv_royale_snapshot38_duration_weighted_timing_seed1055501.json`
(SHA-256
`09cf6c9716597d7d02b2e620e8f443baa7d5a988845556ce0e93aa4ed7cf2ac8`).

A subsequent normalized incumbent/mechanics blend was also rejected. The
predeclared gate required at least a one-point human conditional-slot gain
across all three mechanics seeds with at most 1% disagreement on both unseen
procedural decks and whole held-out archetypes. No alpha passed. Alpha 0.005
changed one human example and no simulator examples, which was treated as noise
rather than a promotion. The first repeatable one-point human gain required
alpha 0.215: only 8--9 net human fixes, but 1.35--1.79% regression on validation
and 1.38--1.85% on held-out archetypes. No policy checkpoint was created. The
full sweep is
`reports/mechanics_slot_blend_sweep_fine_snapshot38_seed1055502.json`
(SHA-256
`ea751c06501f95a45d563c1caa2a435ae9dfaddc25e934558a54c07b63e5337a`).

The same screens were repeated on a collector-safe 120-game snapshot rather
than extrapolated from 38 games. The zero-shot mechanics signal persisted: the
incumbent conditional slot accuracy was 45.56%, while the three independent
linear mechanics seeds reached 46.62%, 48.59%, and 47.69%. It was still not
safe to transplant. The first blend strength giving every seed at least a
one-point human gain exceeded the 1% simulator-disagreement budget on both
disjoint procedural validation and whole held-out archetypes. The 120-game
blend sweep is therefore rejected.

Guarded human fine-tuning was also rejected across seeds. The corrected trainer
checks both simulator guard sets after every epoch and requires at least a
one-point replay-disjoint human-validation improvement. The three selected safe
epochs gained 0.8, 0.2, and 1.8 points on 500 validation placements; only one
of three passed, and full-snapshot gains were just 0.08, 0.12, and 0.45 points.
No seed is cherry-picked and no gameplay policy is modified. At the same
checkpoint, duration weighting estimated a 5.67% natural play rate and only
89/120 games contained any representative retained no-op. The frozen policy's
10.73% deterministic play rate and 21.65% human-play recall confirm that timing
miscalibration persists, but still do not justify fitting against the biased
no-op sample. Full corpus, sidecar, blend, fine-tune, and timing evidence is
recorded in `reports/tv_royale_public_state_benchmark_20260813.md`.

A stronger dry run subsequently used the actual replay/deck/archetype split
rather than an internal episode split. Public HP/confidence sidecars were
mirrored exactly into train, validation, held-out-archetype, and chronology
corpora with zero replay overlap and independent digest/provenance validation.
The three mechanics seeds then gained exactly zero top-1 accuracy on the
separate deck-disjoint human validation set after guarded fine-tuning. Selected
epochs were 3, 0, and 1, and all promotion decisions are false. This supersedes
the weaker internal 120-game split result: the mechanics representation remains
a promising zero-shot prior, but there is no evidence yet that 120 games can
safely adapt it. The final 1,000-game run must repeat this external split gate
before any policy integration.

### Mechanics-only policy integration contract (2026-08-13)

The successful standalone probe now has an exact policy-facing architecture,
without promoting any 120-game result. The compact policy receives one
bias-free 192-to-16 state query and scores the four hand cards only against the
same frozen 16 public mechanics used by the probe. Card identity is excluded.
The shared legal-mass renormalizer makes play versus wait/ability and conditional
placement geometry invariant after training; additive zero initialization is
bit-exact to the parent.

The transplant is explicitly architecture-bound. A real smoke against the
compact confidence-aware parent matched all policy outputs and recurrent state
bit-for-bit at zero, while a deliberate attempt to apply the 16-by-192 probe to
the retired 6.54M policy failed closed on its required 16-by-576 shape. The
focused gate passes 89 tests, including standalone-probe score equivalence and
card-identity isolation. The implementation and the final-corpus promotion
contract are recorded in
`reports/mechanics_slot_policy_adapter_20260813.md`. No policy checkpoint is
promoted until the final disjoint 1,000-game and complete-game gates pass.

The final selection runner is now fail-closed around that contract. It requires
a SHA-bound visual audit of all eight final contact sheets, trains and screens
three fixed seeds, selects on replay/deck-disjoint human validation only, and
uses the median validation seed rather than the best seed. Archetype and
chronology human partitions are evaluated only after the alpha, family, and
checkpoint are frozen. On the existing 120-game disjoint split, the exact
runner rejected both zero-shot and human-fine-tuned families with
`no_cross_seed_safe_alpha` and created no candidate, as required.

The subsequent complete-game handoff is also implemented before seeing the
final result. A development candidate must survive 24 direct parent games and
72 paired random/strategy/Hog games with strict workload-level outcome,
aggregate crown, defense, passivity, Hog-use, and held-out-human no-regression
gates. Checkpoint SHA-256, selected probe/alpha, split roles, metric checkpoints,
opponents, decks, seeds, mirror settings, reward profile, counts, and comparison
inputs are all independently rebound by the finalizer. Only an atomic
`mechanics_rl_initializer_ready_v1` marker can authorize diversified PFSP RL;
it is explicitly not a champion or human-skill promotion. The expanded focused
architecture and pipeline contract passes 123 tests.

The future league training pool has independently expanded from 455 to 1,720
strict training decks. It was generated from structurally valid semantic
variants, then stripped of all exact signatures in the frozen 82-deck
validation and 151-deck whole-archetype holdout pools. Exposure weighting
preserves equal mass across eight training archetypes and is bounded to
`[0.1x, 10x]` per deck. It reduces the weighted training-card inclusion ratio
from 23.51x to 5.83x while leaving four held-out win conditions entirely unseen
by RL. This pool is only a future PFSP input; it does not alter any current
evaluation or constitute training evidence. Full provenance is in
`reports/deck_curriculum_v3_seed1056101.md`.

The corresponding bounded PFSP runner and fail-closed finalizer are ready but
cannot launch before the final mechanics initializer marker. The phase is only
four updates/16,384 decisions and trains the action-type head, mechanics query,
critic, and value head under rollout KL plus recurrent simulator-rehearsal KL.
It uses eight PFSP strategy actor slots plus random, two parent, and update-40
slots. Advancement requires a direct parent win, strict 72-game workload/crown
preservation, a two-point defense-event success gain, Hog and passivity
preservation, no PFSP strategy regression, and nonnegative paired exact/action-
type changes on disjoint human validation, held-out archetype, and chronology
splits. All evidence is path- and SHA-bound. A pass creates only a development
candidate for expanded league/human gates, never a mid-ladder claim.

### Public card-choice scaling screen at 260 games (2026-08-14)

The predeclared mechanics gate was repeated on a leakage-free 260-game
development prefix while the production collector continued. The split retained
1,337 train, 326 external-validation, 626 whole-archetype, and 222 chronology
placement rows with zero replay/deck/archetype leakage. Only one of three guarded
human-fine-tuning seeds promoted, and neither the zero-shot nor fine-tuned family
had a cross-seed-safe blend.

Equal-weight averaging of all three mechanics seeds reduced variance but did not
create a meaningful gain: the best simulator-safe blend improved external human
card choice from 38.34% to 38.96%, only two net examples and below the one-point
gate. A new 38,129-parameter DeepSets scorer then read the confidence-aware public
board directly and scored cards from identity plus official mechanics. Its three
external-validation results were 36.50%, 34.36%, and 32.21%; equal-logit ensembling
fell to 30.37%. The architecture is rejected rather than widened or epoch-tuned.

This evidence changes the dependency graph: diversified outcome-based PFSP should
not be blocked indefinitely on a fragile imitation adapter. The final human corpus
remains valuable as a no-regression gate, while recurrent rehearsal remains a
separate simulator-native corpus. A bounded league pilot from
the accepted confidence-aware parent is now the next causal skill experiment.
Full commands, hashes, split counts, and rejection evidence are in
`reports/public_reactive_slot_scaling260_20260814.md`.

### Exact parent selection for the outcome-grounded pilot (2026-08-14)

Three zero-initialized mechanics adapters were then compared on one matched
72-game matrix rather than selected by parameter count or activity rate. The
522,068-parameter compact parent scored 15--57 with -123 crowns and 96.98%
playable no-op. The 1,285,428-parameter update-28 policy reduced playable no-op
to 0.08% but still scored only 29--43 with -9 crowns. Both are rejected as PFSP
parents. The 6,194,196-parameter human+safety policy scored 51--21 with +78
crowns: random 10--2, balanced 6--6, reactive-defense 5--7, bridge-pressure
5--1, slow-push 6--0, spell-control 5--1, split-lane 4--2, and Hog 10--2.

The 6.17M adapter is bit-exact to its source across all inherited tensors,
policy outputs, recurrent states, and 713 deterministic actions. It is still
not promoted: Hog went unused in 3/12 dedicated games versus an absolute limit
of one. Because it nevertheless converted 69.23% of affordable Hog windows,
assigned Hog 67.32% mean conditional probability, and won 10--2, the v3 parent
selector authorizes only a targeted repair pilot. Updates 20--24 will train the
mechanics card-choice query plus critic/value parameters while freezing timing
and placement. The final 1,000-game public corpus is now a visually audited,
untouched post-260 no-regression gate; recurrent rehearsal remains the separate
simulator-native corpus. It is not permission to fit
another fragile imitation adapter. Full evidence and the unchanged promotion
contract are in `reports/pfsp_parent_selection_20260814.md`.

The three Hog zero-use games were then audited decision by decision rather than
treated as an aggregate symptom. Hog was legal and affordable 8, 2, and 2 times
in those games, and another slot was selected on every one of the 12 decisions;
two games were losses. Across the full matrix, legal-affordable Hog conversion
was 0/23 in slot 0, 18/20 in slot 1, 4/4 in slot 2, and 32/32 in slot 3. This
supports the mechanics-query intervention but exposes a slot-specific failure
that the earlier aggregate gate could hide. The pilot finalizer now requires
coverage, at least one use, and at least 25% conversion in each of the four hand
slots in addition to the existing aggregate, per-seat, zero-use, and outcome
gates.

Utilization arithmetic is now evidence-bound too. The PFSP finalizer recomputes
the complete Hog report directly from the SHA-bound decision and game arrays
and requires exact equality, instead of trusting a derived JSON that merely
points at those files. The real parent recomputation reproduces 12 games, 54
plays, and three zero-use games; a deliberately edited conversion rate is
rejected by the focused gate.

The same diagnostic has been generalized before training rather than waiting
for another missing-win-condition video. A frozen evaluation matrix now covers
all eight validation archetypes plus the four entirely held-out archetypes with
one explicit designated card each: Balloon, Battle Ram, Giant, Golem, Hog
Rider, Goblin Barrel, Miner, Wall Breakers, Graveyard, Lava Hound, Royal Hogs,
and X-Bow. Explicit designation is evaluation metadata, not a simulator or
policy card-name rule, and lets spawn-spell, siege, and unrestricted-deployment
win conditions be measured without misclassifying them as building-target
troops. The source-bound manifest SHA-256 is
`171601791f57f0d21cc443ded12d61a40e0d288252115eea4eafb1343e06e8ae`.
The production PFSP runner evaluates both parent and candidate for two mirrored
balanced-strategy games on every singleton deck and retains metrics, terminal
games, and decision traces. Its finalizer re-derives the selected singleton
from the exact validation or held-out source pool, recomputes each designated
card's utilization from raw traces, validates matched outcome arithmetic, and
rejects the entire candidate if any one of the 12 archetypes fails absolute
use, outcome, zero-use, affordable-window conversion, or conditional
probability preservation. Focused tamper tests prove that an edited utilization
summary and an easier post-selection deck substitution both fail closed.

The pilot evidence contract was tightened before launch. Evaluation reports
now bind checkpoint, opponent-checkpoint, and sampling-deck bytes by SHA-256;
matched game comparisons bind both record files and validate counts plus crown
arithmetic. Direct parent play must be non-losing independently on validation
and whole-archetype holdout decks, so a held-out collapse cannot hide behind a
large validation gain. Likewise every strategy opponent must be individually
preserved; equal mean and improved worst-case scores cannot hide regression
against one bot. Playable no-op is also bounded independently in all eight
matched workloads, rather than only the balanced/reactive defense aggregate. A
real one-game evaluator/comparator smoke confirmed the new digest chain, and
the focused gate rejects deliberate stale-record, held-out-collapse,
strategy-offset, and single-workload-passivity failures.

The future post-260 marker is also chronology-exact rather than count-based.
The final verifier requires the reserve to equal precisely the first 260
successful manifest records and the four post-development partitions to cover
each of games 261--1000 exactly once, with the source-manifest digest and all
three separation invariants intact. The already-idle watcher was restarted
after this verifier was added so it cannot finish through its older weaker
shell image.

The final visual gate is likewise source-exact rather than a human-approved
filename convention. The contact-sheet manifest binds the completed 1,000-game
run manifest by path and SHA-256, requires all 20 arenas and four chronological
quantiles, and binds every rendered sheet plus each of its 20 source frames by
SHA-256. The standalone verifier requires exactly eight phase/quantile sheets,
exact arena ordering, 160 unique reviewed source-frame entries, and an audit
whose reviewed paths are precisely the generated outputs. Consequently a
stale sheet, substituted frame, changed run manifest, omitted arena, duplicate
quantile, or approval copied from an earlier checkpoint cannot authorize the
pilot. The audit file will be created only after the final sheets exist and are
manually inspected; the intermediate 378-game audit is evidence about the live
extractor, not permission to train.

### Post-hoc hand-slot invariance closure (2026-08-14)

The accepted 6.19M-parameter parent has a causal physical-hand-slot defect:
all-24-permutation counterfactuals preserve card plus tile on only 51.07% of
audited decisions, and legal-affordable Hog conversion ranges from 0/23 in
slot 0 to 32/32 in slot 3. A shared semantic/mechanics slot scorer removes the
defect exactly: the best permutation-distilled student preserves card plus tile
on 100% of permutations and gives identical Hog probability in every slot.

The retrofit is nevertheless rejected. On the matched broad screen it falls
from the parent's 51--21/+78 crowns to 41--31/+9, while max-pool and learned
invariant timing repairs score 4--7--1 and 1--11 on the Hog gate. Snapshot
distillation is off-policy after the first changed action alters the recurrent
trajectory, and the accepted policy's useful behavior is entangled with the
slot-biased representation being removed. Further graft repairs are stopped.

The structural architecture will instead be trained from initialization. A
bounded matched A/B can use the intact 420,672-frame human+safety corpus while
the 1,000-game public collector finishes, but the latter remains untouched
until exact integrity, post-260 separation, and manual visual audit complete.
Full checkpoint hashes, target statistics, and gate results are in
`reports/accepted6m_hand_slot_robustness_20260814.md`.

The first matched clean structural checkpoint proved the representation but
failed the policy gate. Relative to its legacy sibling it transferred much
better to a later-arena chronology (14.05% versus 0.10% exact action), and it
preserved card plus tile on all 59,280 hand permutations. But the 72-game
screen was 1--71 with -181 crowns and 99.47% playable no-op. Epoch 1 is rejected.
One lower-rate continuation epoch is the bounded optimization check; persistent
passivity ends offline fitting and triggers on-policy distribution correction.

As a distinct fallback, the imitation fitter can now apply one exact random
hand-slot relabeling per recurrent sequence. Unlike the hard-invariant head,
this leaves the known-capable legacy architecture intact while making physical
slot identity statistically unreliable. It remaps masks, previous actions,
targets, confidence, and privileged cards consistently. The implementation is
gated by `--hand-permutation-augmentation`; 22 focused tests plus Ruff and mypy
are clean. No checkpoint from this arm exists yet.

The matched unaugmented fresh legacy checkpoint remains capable (10--2 on its
Hog audit) but is even more slot-dependent than the accepted parent: only
28.46% card-plus-tile preservation, with Hog destination-slot selection rates
of 8.55%, 63.19%, 39.57%, and 60.87%. This establishes the exact before-arm for
the queued permutation-augmentation experiment.

The same checkpoint scored 55--17 with +84 crowns on the matched 72-game
breadth screen, exceeding the accepted parent's 51--21/+78. Its playable no-op
rate was 71.76%. It is therefore the exact capability baseline for the
augmentation arm, not a clean promotion: the card decision still changes under
most semantically irrelevant hand-slot permutations.

The hard-invariant continuation confirms the stop rule. Its lower-rate second
epoch remained 1--71 with 99.39% playable no-op, while chronology exact action
fell from 14.05% to 9.12% and joint NLL worsened from 7.148 to 8.609. Validation
loss alone improved, demonstrating why it cannot be the promotion signal. The
formulation is rejected and the queued fresh legacy plus exact hand-permutation
augmentation arm is now training.

The matched full-dose permutation arm completed and is also rejected for
promotion. `checkpoints/human_safety_handperm_fresh_seed1011001/epoch1.pt`
(SHA-256
`f69f2ac4796b05271c8a6a0f6e3dc819283ba657e35e3564f4ad3bb30b311448`)
used exactly the legacy arm's corpus, seed, split, model, optimizer, and one
epoch, with sequence-consistent hand relabeling as the only material training
change. It improved all-24 card-plus-tile preservation from 28.46% to 63.15%,
reduced maximum slot-logit equivariance error from 28.63 to 8.80, and narrowed
Hog destination-slot selection from 8.55--63.19% to 62.69--88.56%. This proves
that statistical relabeling attacks the measured shortcut.

The dose was too strong. The broad screen fell from 55--17/+84 crowns to
42--30/+34, weighted playable no-op rose from 71.76% to 90.52%, and balanced
strategy collapsed from 10--2 to 0--12. Later-arena chronology action-type
accuracy also fell from 18.55% to 15.83%, despite joint NLL improving from
10.424 to 7.826. The checkpoint is retained as causal evidence, not an RL
initializer. The next bounded experiment keeps the same matched fresh protocol
but applies permutation relabeling to only 25% of recurrent sequences. Further
doses are contingent on simultaneously retaining gameplay and improving the
slot audit; neither offline loss nor symmetry alone can authorize promotion.

The 25% mixture arm establishes a useful but incomplete Pareto point.
`checkpoints/human_safety_handperm25_fresh_seed1011001/epoch1.pt` (SHA-256
`6e4c26dd08537b8cbdef5a41c29cefaf7fc7138a49bc8858aafaf7700eb33d49`)
recovered 73.35% validation exact and 87.43% action-type accuracy. It cleared
the accepted gameplay floor at 53--19/+66 crowns with 68.67% weighted playable
no-op, but remained behind the unaugmented 55--17/+84 sibling. Exact paired
records versus that sibling contain six improved, eight regressed, and 58
unchanged games, for -18 crowns.

Aggregate Hog-audit card-plus-tile preservation improved from 28.46% to 40.58%
and maximum slot-logit error fell from 28.63 to 20.27. That did not remove the
actual designated-card pathology: Hog selection remained only 9.81% in slot 0
versus 66.20--73.05% in the other slots, a larger spread than the unaugmented
model. A matched six-card extension over Giant, Balloon, Goblin Barrel, Miner,
X-Bow, and Royal Hogs improved card-plus-tile preservation on five cards and
maximum slot-logit error on all six, but improved designated-card slot spread
only inconsistently; the candidate went 17--7 versus the sibling's 20--4 over
the 24 audit games. Simple permutation-dose fitting therefore stops.

The evidence localizes the next architecture ablation. Full hard invariance
replaced conditional card choice and play/wait timing and became inert; partial
augmentation improves the card scorer but leaves physical-slot timing mass.
The next fresh arm makes only conditional slot choice exactly equivariant while
retaining the invariant aggregate of the learned base timing logits. It does
not use the failed learned replacement timing query. This is a causal
factorization test, not another augmentation sweep.

### Equivariant conditional-slot-only ablation (2026-08-14)

The causal factorization test resolves the architecture question but does not
produce a usable policy. Its checkpoint is
`checkpoints/human_safety_equivariant_slotonly_fresh_seed1011001/epoch1.pt`
(SHA-256
`196887397ffa0d349b5685b9206667a6c8091bf491b5392d239f017d3b7c90f3`).
Only conditional current-hand choice is exactly equivariant; play/wait timing
uses the invariant aggregate of the learned base logits, and the failed learned
replacement timing query is disabled.

The structural contract passes decisively. Card identity and card plus tile are
preserved on 100% of 50,520 audited hand permutations, with maximum slot-logit
error `3.82e-6` and maximum location error `2.29e-5`. The independent
later-arena chronology is also the strongest in this family: 41.19% exact
action accuracy, 48.43% action-type accuracy, 5.983 joint NLL, and a 33.12%
predicted play rate versus the human 38.26% rate.

Complete games contradict that offline result. The policy scores **0--72 with
-184 crowns** across the frozen breadth matrix. Random, balanced,
reactive-defense, bridge-pressure, slow-push, spell-control, split-lane, and
Hog workloads all have zero wins; playable-state no-op ranges from 98.48% to
100%. The independent Hog permutation audit is likewise 0--12. It verifies
identical Hog behavior in every destination slot, but that behavior is almost
never selecting Hog: 30 selections in 11,904 legal destination trials per
slot, or 0.252%.

The current 420,672-frame imitation corpus can therefore train an invariant
representation that transfers offline while still leaving the model outside
the live simulator state distribution. The hard-invariant architecture family,
the learned timing repair, and the simple permutation-dose family are closed.
No more offline epochs or architectural patches are justified on this corpus.
The 6.19M human+safety policy remains the bounded diversified-PFSP parent.
Simulator-native teacher trajectories provide recurrent rehearsal; the final
1,000-game public-state partitions remain untouched replay-disjoint
no-regression evidence. On-policy complete-game outcomes must correct card use
without mutating the already capable timing and placement policy.

### Final-public gate closure and query-only PFSP rejection (2026-08-14)

The public-v2 collector completed exactly 1,000 accepted games after 1,028
attempts. Exact integrity reconstruction verifies 29,722 public decision rows,
262,240 visible entity rows, 56.4952% entity-HP coverage, 38.6398% motion
coverage, 4,610 strict visual deployment labels, 2,585 audit images, and zero
retained raw videos. All eight final contact sheets were manually inspected:
they cover early and late frames in four chronological quantiles, one source
from each of arenas 12--31 per sheet. The signed audit binds all 160 source
frames, every rendered sheet, and the final run manifest by SHA-256.

The chronology-exact post-development verifier was corrected after its first
real run exposed an invalid assumption: it demanded that all 740 games after
the frozen 260-game development prefix survive the complete-visible-hand
filter. The split publisher intentionally excludes a replay when no row shows
all four current cards. The verifier now independently hashes and reads every
post-prefix corpus, recomputes the exact four-card eligibility predicate, and
proves that the four disjoint partitions contain precisely the 560 publishable
replays; 180 are excluded for no complete-hand row. It also proves that the
partition source counts cover all 740 post-prefix games and that the declared
exclusion count is exact. The real gate and 17 focused integrity/audit tests
pass.

The bounded query-only outcome pilot then resumed the accepted parent at update
20 and processed 16,384 league transitions through update 24. Optimization was
finite and stable: approximate KL remained within `1.26e-8`, anchor policy KL
within `5.71e-8`, clip fraction was zero, and the state-dict audit found exactly
one changed actor tensor, `mechanics_slot_choice_query.weight`, plus the
authorized critic/value tensors.

The branch is rejected as behaviorally inert. Parent and candidate both scored
75% over the matched six-strategy PFSP baseline. Across the frozen 72-game
random/strategy/Hog breadth screen, all eight workload record sets were
byte-identical. Hog remained at 54 plays, 69.23% affordable-window conversion,
three zero-use games, and zero slot-0 plays over 23 legal-affordable slot-0
decisions. Validation and whole-archetype direct matches were each 6--6 by
seat. Human validation and chronology had zero argmax action changes; the much
larger archetype set had only one action change and no exact or action-type
improvement. The finalizer correctly reports `development_candidate_eligible =
false`, with the absolute Hog, per-slot coverage, direct-improvement, defense-
improvement, and win-condition gates failing.

This closes query-only PPO rather than authorizing more updates on an unchanged
policy. The next bounded branch restarts from the accepted update-20 parent and
adds the shared `action_type_head` to the trainable mechanics query. Placement,
entity encoding, recurrent memory, and every other actor tensor remain frozen.
This is the smallest intervention that can change the aggregate play/wait mass
whose coupling defeated the structural and post-hoc card-choice experiments.
It must produce a measurable matched behavior change while passing the same
Hog, every-win-condition, defense, passivity, held-out deck/archetype,
chronology-human, and strict no-regression gates; otherwise this action-head
branch is rejected before any full-actor continuation.

### Action-type plus mechanics-query PFSP rejection (2026-08-14)

The matched second branch restarted from the accepted update-20 parent and
trained both `action_type_head` and `mechanics_slot_choice_query`, while
freezing placement, entity encoding, recurrent memory, and all other actor
tensors. It processed the same 16,384 league transitions through update 24.
The run exited cleanly and was numerically stable: approximate KL stayed below
`4.38e-6`, anchor policy KL below `2.09e-5`, clip fraction remained zero, and
the state-dict audit found only the five authorized actor tensors plus
critic/value changes.

The larger parameter surface produced only a threshold-level behavioral
perturbation, not a skill improvement. All 60 random, balanced,
reactive-defense, bridge-pressure, slow-push, spell-control, and split-lane
breadth games were byte-identical to the accepted parent. The 12-game Hog set
was also byte-identical: 54 plays, 69.23% affordable-window conversion, three
zero-use games, and zero plays from 23 legal-affordable slot-0 decisions. The
24 mirrored validation and held-out direct games remained exactly 12--12 with
zero crown differential. Aggregate defense outcome, success rate, and
playable-state no-op rate were unchanged.

Across the 24-game win-condition matrix, only two two-game record sets changed.
The candidate gained two crowns against Golem but lost two crowns against Royal
Hogs; every game outcome was unchanged and the aggregate crown change was zero.
All other win-condition records were byte-identical. The finalizer therefore
correctly rejected
`checkpoints/accepted6m_actiontype_query_pfsp_seed1056601/policy_v2_update_000024.pt`
(SHA-256
`2e0f58e2b8525cad6962f8e02eca6f8a948d0d3aa9ddab7962b6d605966bbc62`)
with `development_candidate_eligible = false`.

This closes tiny frozen-head PPO continuation. Both bounded frozen-head arms
were stable and safe, but neither crossed the accepted parent's deterministic
action margins or improved held-out complete-game outcomes. Further updates of
the same kind would spend simulator transitions without addressing the
on-policy distribution mismatch. The next experiment must permit meaningful
behavioral learning while retaining a strict accepted-parent safety anchor;
the leading structural option is student-state DAgger using a teacher averaged
over all 24 hand permutations, followed by bounded full-game gates. A broader
full-actor PPO branch remains a fallback, not the default, because earlier
full-actor continuations repeatedly regressed broad gameplay.
### Hog specialist: hazard-conditioned PPO correction (2026-08-27)

The accepted Hog specialist's PPO collector was not sampling the policy used by
deterministic evaluation.  `ClasherPolicy.act(..., deterministic=False)` sampled
the unconstrained joint distribution even when `deterministic_hierarchy` was
`hazard`.  Historical strategy-PFSP rollouts therefore played on roughly 98% of
playable decisions (`noop_when_playable` near 0.02), while evaluation used the
cumulative hazard and waited on roughly 94-95%.  PPO optimized trajectories the
deployed policy never produced.

An opt-in `--hazard-conditioned-rollouts` path now conditions stochastic rollout
actions on the same cumulative hazard gate and uses the identical conditioned
distribution to recompute PPO log probabilities.  Episode-start resets are
explicit.  The legacy collector remains available for controlled A/B tests.
Focused evidence is 88 passing play-hazard, trainer, league, structured-policy,
and parallel-rollout tests; Ruff and mypy are clean.  Sequential actor and batched
learner log probabilities match exactly in the new test.

A bounded Hog-only outcome experiment resumed update 46 with its timing and
shared representation frozen.  Only card-choice and placement modules were
trainable.  Across updates 47-76, rollout cadence matched evaluation
(`noop_when_playable` about 0.93-0.96), throughput was about 258-315
transitions/s, maximum observed PPO approximate KL was below 0.00022, and both
stability gates passed.

Update 56 initially looked weakly positive across two seed blocks: versus update
46 it changed random 5-7 to 6-6, the historical direct opponent 9-3 to 10-2, and
the six-bot strategy suite 2-22 to 3-21.  Mean board edge improved slightly in
all three groups, but strategy crown margin worsened.  A third disjoint seed
block rejected the apparent gain: update 56 scored 2-4 versus random and 2-4
versus direct; updates 66 and 76 each scored 0-6 versus random and 1-5 versus
direct.  No checkpoint from this lineage is promoted.  Update 46 remains the
champion.

Two related surrogate approaches were also rejected.  A fresh simultaneous
human-timing plus strategy-spatial model improved offline conditional card
accuracy to 61.33% and location NLL to 3.466 but scored 0-12 against strategy
bots.  Copying update 46's hazard head into that representation raised timing
ROC-AUC only from 0.463 to 0.546, showing the head depended on its original
representation.  A frozen-body timing adapter reached ROC-AUC 0.624, but after
gain calibration to healthy cadence it still scored 0-12 against strategies.
Finally, updating only update 46's spatial modules improved offline card accuracy
from 48.74% to 62.05% and location NLL from 5.691 to 3.612 while preserving
timing exactly, yet gameplay fell to 0-6 random, 2-4 direct, and 1-11 strategy.

Decision: preserve the hazard-conditioned collector correction, reject all new
checkpoints, and stop treating one-step imitation accuracy or cadence matching as
sufficient.  The next tactical learner must use outcome-aligned counterfactual
advantages (or another verified intermediate target) while keeping the proven
timing policy fixed; it must clear random/direct screens before a full strategy
gate.

### Hog specialist: clean typed lineage and aligned spatial PPO (2026-08-27)

A typed-vocabulary audit found that `IceSpirit` and `IceGolem` were resolving to
the unknown token even though the current client exposes their canonical aliases
as `IceSpirits` and `IceGolemite`.  The observation builder now canonicalizes an
alias before checking loader availability.  All eight Hog 2.6 cards consequently
have distinct typed action tokens.  This invalidates older Hog corpora as clean
eight-card representation evidence, although it does not by itself invalidate
their observed game outcomes.

Regenerating the strategy context corpus found a second causal-label defect.  In
policy-behavior collection, the strategy teacher had supplied hypothetical card
and tile labels on every behavior wait.  The corrected collector trusts card and
tile supervision only when the behavior policy actually plays and the teacher
also proposes a placement.  The replacement corpus contains 10,484 causal rows,
574 aligned card/tile labels, and zero unknown Hog hand identities; it replaces
an apparent 11,017-label corpus whose spatial supervision was mostly
hypothetical.

A fresh clean-lineage model trained on the aligned corpus through update 10.  At
the calibrated 0.20 hazard threshold it reached human timing ROC-AUC 0.615,
aligned conditional card accuracy 57.59%, and aligned location NLL 3.99.  Its
first six-game safety screen scored 3-3 versus random and 5-1 versus the direct
baseline, but it scored 0-12 against the six strategy bots.  A ten-update
imitation continuation improved aligned location NLL to 3.524 but weakened the
safety screen, so update 10 remained the clean baseline.

The corrected hazard-conditioned PPO implementation also required one further
fix for fresh lineages: after rehearsal changes the hazard head, recomputing the
current gate during PPO can change action support and create enormous false KL.
PPO now reconstructs the rollout gate exactly from whether the recorded action
was a placement.  The resulting aligned outcome-only spatial leg (updates 11-20,
40,960 transitions) passed numerical stability with maximum approximate KL
0.00130 and maximum clip fraction 0.01783.

Gameplay did not improve.  Update 20 scored 1-5 versus random and 3-3 versus the
direct baseline on a fresh safety block.  A matched milestone screen showed all
of updates 10, 12, 14, 16, 18, and 20 at 1-5 versus random; direct results ranged
from 1-5 to 3-3.  Updates 12 and 18 were then screened against every strategy.
Update 12 scored 0-12.  Update 18 scored 1-11, but the update-10 parent won the
same reactive-defense game on the identical seed and also scored 1-11.  Thus the
apparent strategy win is not attributable to PPO.

Decision: reject the entire aligned outcome-only continuation and retain update
10 only as the clean typed research baseline.  The older update-46 specialist
remains the gameplay champion.  The evidence now rules out more global
one-step spatial fitting and short outcome-only spatial PPO as the immediate
path to competence; the next branch needs explicit multi-step tactical credit or
trajectory-level teacher/outcome supervision while preserving the corrected
typed vocabulary, causal labels, and hazard collector.

### Hog specialist: terminal credit and executed-strategy distillation (2026-08-27)

Terminal counterfactual collection tested up to ten legal actions from each
intervention root and completed every branch to the natural game result.  A
12-game canary found four loss-to-win corrections in 36 early roots, but a
second seed produced zero decisive corrections in its first 22 games and a
whole-match stratified canary found only one in 26 roots.  Literal result flips
are therefore too sparse for a scalable training target.  High-margin terminal
credit was substantially denser: the completed replay-disjoint corpus contains
794 train placement/wait comparisons across all 72 games and 451 validation
comparisons across all 36 games, with minimum crown or 1,500-HP terminal-edge
gaps.  Parent-centered hazard fitting reached 60.9% corrective and 52.3% safety
accuracy with negligible global logit drift, but was behaviorally inert until
its delta was extrapolated 16x.  That extrapolation failed confirmation:
against the parent it regressed direct 8-4 to 6-6 and strategy 6-18 to 4-20.
The terminal-hazard branch is rejected.

A separate executed-teacher corpus then let each of the six deterministic
public-information strategies actually control Hog 2.6 against rotating
diverse decks.  This exposed and fixed another corpus contract bug: public token
zero is a normal temporarily empty hand slot during delayed refill, while token
one is the unknown identity.  The prior collector incorrectly rejected both.
The corrected corpus contains 144 train games / 78,693 causal decisions and 48
validation games / 25,470 decisions, with complete behavior-aligned timing,
card, and tile supervision.

Training only the cumulative hazard head selected update 14 on the held-out
teacher games.  Relative to its clean update-10 parent, deterministic
action-type accuracy rose from 90.68% to 91.99% and correctly timed/selected
placements from 926 to 1,296 of 3,131.  Its first gameplay block improved random
5-7 to 6-6 and direct 4-8 to 8-4, although strategy moved 5-19 to 4-20; it was
kept only as a timing parent.  A three-epoch placement-only spatial fit then
raised held-out conditional card-slot accuracy from 92.65% to 94.63% and reduced
location NLL from 5.176 to 4.673.  On a 96-game matched confirmation it improved
random 8-16 to 13-11, direct 12-12 to 15-9, and strategy 9-39 to 12-36, with
better crown differential in every aggregate workload.

The clean spatial model is therefore the current development candidate, but it
does not replace the historical champion: it loses 5-19 head-to-head against
update 46, even though it slightly exceeds update 46 on the matched random
(13-11 versus 12-12) and strategy (12-36 versus 9-39) workloads.  A bounded
full-actor update-46 league repair was stopped after anchor KL exceeded its
0.03 ceiling and its update 18 regressed random play.  A stable spatial-only
repair improved the small update-46 screen at update 19 but regressed strategy
5-7 to 3-9, so it was also rejected.  Further work must improve the clean
candidate's adversarial robustness without trading away its reproduced broad
gain; update 46 remains the project champion until that occurs.

### MPS/CUDA gym certification and second-dose rejection (2026-08-27)

The optimized Simple Gym MPS descendant was certified in an isolated worktree
at `b8f299f87cbe7e4f8b4823549b85188c146a843b`. On the matched batch-128,
100-tick, three-repetition workload, eager Apple MPS sustained a median 84.182
row-ticks/s. A paid Prime RTX A6000 sustained 344.212 row-ticks/s in eager
CUDA and 416.795 row-ticks/s with CUDA Graph execution. CUDA Graph was 4.95x
the MPS rate and 1.211x eager CUDA, with ten recorded kernel launches, zero
explicit host synchronizations, native committed rows, deterministic
within-backend replay, and zero fallback. The paid pod was terminated after
the reports were copied. The operational decision is MPS for local development
and bounded evaluation, CUDA Graph for production-scale tensor-gym collection
and training. Different MPS and CUDA throughput-driver digests are not
overclaimed as cross-device parity; separate CPU/MPS integration traces are the
functional parity evidence.

A second replay-disjoint update-46 behavior corpus increased held-out offline
slot accuracy from 93.58% to 94.65%, reduced location NLL from 4.614 to 4.425,
and produced `hog26_equal_plus_u46x2_spatial_seed1146001`. The behavioral
effect was real but not uniformly beneficial. On the first matched block it
changed random 9-3 to 7-5, direct update-46 play 6-6 to 9-3, and strategy 4-20
to 6-18. The expanded disjoint block confirmed the direct improvement: the
one-dose model's 8-16 and -0.542 crowns/game became 12-12 and +0.333. However,
random slipped 12-12 to 11-13 and the 48-game strategy suite regressed 15-33
to 12-36. Reactive-defense fell 4-4 to 1-7 and slow-push 1-7 to 0-8; mean
board edge also worsened from -0.1063 to -0.1190. The two-dose checkpoint is
therefore rejected despite solving much of the direct update-46 weakness.

Only 28 spatial/card-selection tensors differed between the one- and two-dose
models. A 50% weight-space midpoint was tested to determine whether the tradeoff
was smooth. It retained the 9-3 direct canary but scored 7-5 random and only
3-21 against the six strategies. Interpolation is rejected. The one-dose
checkpoint remains the clean development candidate, while historical update 46
remains the project champion. The next bounded fit should add replay-disjoint
reactive-defense and slow-push trajectories alongside the second update-46
corpus, rather than duplicate rows or interpolate weights; this directly tests
whether targeted rehearsal can preserve breadth while retaining adversarial
robustness.

### Targeted rehearsal seed selection and Hog champion promotion (2026-08-27)

The two-dose update-46 corpus was augmented with 48 new replay-disjoint games
actually controlled by reactive-defense and slow-push. The final training mix
contains 167,631 decisions across 336 episodes; the 26,674 new decisions are
independent trajectories rather than duplicated rows. A three-epoch spatial
fit on MPS completed in 589.1 seconds. Its first optimization seed improved the
strategy canary to 11-13 but regressed direct update-46 play to 5-7, proving
that one fit was not sufficient evidence.

A repeat used the identical episode split and changed only training randomness.
It completed in 588.2 seconds and produced checkpoint SHA-256
`28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372`.
On the original canary it scored 7-5 random, 10-2 against update 46 with
balanced 5/5 seat wins, and 10-14 against the six strategies. The disjoint
expanded block then scored 15-9 random, 15-9 against update 46, and 22-26
strategy. Relative to the one-dose candidate, expanded random improved from
12-12, direct from 8-16, and strategy from 15-33. Crown and board-value
aggregates improved in every group. Slow-push improved from 1-7 to 4-4 and
bridge-pressure from 0-8 to 3-5. Five strategy families improved or held their
match score; split-lane moved from 6-2 to 5-3 while retaining a positive +0.5
crown differential per game.

One further untouched seed block confirmed 7-5 random and 9-3 direct. On its
exact matched 24-game strategy schedule, the new checkpoint scored 8-16, the
one-dose model 6-18, and historical update 46 5-19. The new checkpoint won at
least one game against every strategy, whereas the baselines had two and three
zero-win opponents respectively.

`hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt` is therefore
promoted as the internal Hog 2.6 gameplay champion. This supersedes update 46
for Hog-specialist evaluation, but it is not evidence of mid-ladder human skill
and does not complete the project goal. Its remaining weaknesses are a losing
aggregate record against the deterministic strategy roster, residual
spell-control/bridge-pressure difficulty, and some expanded-seat imbalance.
The next phase should use this checkpoint as the frozen behavioral baseline,
adopt the certified Simple Gym backend, and perform short outcome/PFSP repair
only under strict champion KL and free-running no-regression gates.
