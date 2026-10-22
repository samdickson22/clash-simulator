# Outcome RL for both S100 and M

Registered scope, before launch. Sam explicitly authorizes an RL stage for both sizes regardless of the BC
size-selection outcome. S100 remains the BC default while the M comparison is inconclusive. L stays cancelled.
The BC power extension and both-size data-scaling read have priority. No learner or RL actor has launched.

This amendment supersedes the single-selected-model assumption and any 04 resource handoff in RL-DESIGN.md.
The shared featurizer, public causal inputs, sampled action distribution and terminal-only reward remain fixed.
The actor lineage is the calibrated joint runtime documented in amendment commit
`3bf68f9297ea0d0ba17091572c0f7df5cc1cd67f`, with the bounded caches and original real-level engine calibration.
It does not inherit permission to change HP1 or its evaluation configuration.

## Starts and equal budget

- Use each size's admitted, selected BC checkpoint on the frozen 83-batch follow-up snapshot. This gives both
  sizes the same training data and split. Freeze the two hashes and selection receipts before RL admission.
  If either lacks an admitted checkpoint, report the gate failure; do not substitute another run silently.
- Engineering budget for the first registered stage: 32 updates, each 262,144 acting-seat poll transitions,
  for 8,388,608 environment poll steps per size per seed. Seeds are 2026102101, 2026102102 and 2026102103 for both.
  Forced/busy polls count toward this budget and train value only. Report engine ticks, completed games and actor
  CPU/wall time separately. The budget counts generated environment transitions, including discarded transitions;
  failed generation cannot buy extra attempts or extra learner data. No extra steps for the faster size.
- Polls use the common five-tick grid from tick 90. Rollout chunks may end within a game; bootstrap the critic
  at a nonterminal chunk boundary, preserve the continuing environment and causal memory, and never label that
  boundary a terminal draw. A match contributes terminal +1/0/-1 only when it actually ends. End-of-budget
  unfinished games stay unfinished and their counts are reported. This makes equal poll-step accounting exact.
- Run paired size/seed stages serially on the 08 learner, with size order alternating by seed. Both sizes use
  identical opponents, deck/level draws and per-case environment seeds. A size-dependent self-play policy is
  expected; league schedules and snapshot/reservoir indices remain matched. Never feed one size's RL output
  into the other size's opponent pool.
- Three actor-frozen critic-warmup updates are included in the same 32-update budget for both sizes. The remaining
  29 use PPO. This is a fixed first-stage budget, not a claim that learning has converged. No adaptive extension
  based on the final game result is registered.

## Objective and environment

- Terminal reward only, +1 win, 0 draw, -1 loss. No tower, chip, play, wait, action-quality or teacher reward.
  Gamma 1, GAE lambda 0.95, PPO clip 0.2, AdamW LR 1e-5, value coefficient 0.5, entropy coefficient 0.001,
  gradient clip 1, two optimizer epochs per update. Weight decay is explicitly zero, matching the existing outcome-PPO learner.
- Human KL coefficient 0.05. Each size anchors to a frozen copy of its own BC start. Compute the exact joint
  masked gate/slot plus play-mass-weighted conditional tile KL of the distribution actually sampled by Session.
  Log per-size mean, p95 and per-opponent KL, together with legal-action and cadence checks.
- Same effective optimizer minibatch 2,048 for both sizes, matching the existing outcome-PPO learner. Memory-only implementation adjustment is allowed through
  smaller microbatches and exact gradient accumulation, recorded before launch. Keep both policies in evaluation mode during gradient
  computation so dropout cannot change the sampled distribution or likelihood ratio; gradients still flow. Do not silently change effective
  batch, optimizer-step count, schedule, advantage normalization or entropy/KL reduction when reducing memory.
- Use the own-deck, opponent-level and league mixtures already specified in RL-DESIGN.md, with every distribution,
  checkpoint and environment variable frozen in a launch receipt. Hog 2.6 uses our exact card levels and
  King/Princess 9. Refuse incomplete level maps, and never expose enemy hand, next, elixir or true hidden levels
  to the policy or search opponent.
- Train in our calibrated engine only. Keep native SHA `358cf506031bde59519fbb7ec59f07d3823112311b8d3192dbebd7a8871ef144`,
  gamedata SHA `ccd2a5f18f49e23ad316d8ffecd32278fe9994fcdc74936c7410223b2faef756`, crown rules and bounded caches.
  Pin the complete assembler/runtime manifest and actor source in every rollout and checkpoint.

## Evaluation and collapse

- Primary endpoint is the final update-32 snapshot's game win rate against the frozen current live bot on
  account-level Hog 2.6, independently for each size and seed. Report draws and score as secondary quantities;
  a draw is not a win. Use a fresh fixed bank of 1,600 cases per seed, disjoint from all BC and DEV banks, paired
  across the two RL sizes and their BC starts. Freeze bank seeds, decks, levels, opponents and hashes before RL.
- Use the BC paired-accounting validators and bootstrap code. Preserve all assigned games, attempted counts,
  terminal/provenance validity, complete-pair confidence intervals and all-assigned conservative bounds. Publish
  per-seed sample sizes and estimates, and an equal-seed-weight aggregate with a within-seed paired bootstrap.
  Never select the best seed or snapshot from this primary bank.
- On the same paired cases report RL-S minus BC-S, RL-M minus BC-M, and RL-M minus RL-S. Prefer M only under the
  existing game rule: complete-pair 95% lower bound above zero and conservative all-assigned point above zero.
  An inconclusive interval leaves S100 as the default and is not an M loss.
- Save snapshots every 10 updates plus final update 32. At updates 0, 10, 20 and 30 evaluate fixed, separately
  registered DEV banks of 200 cases and the existing defense/spell audit roots. DEV banks never enter the final
  endpoint. Report spell/defense coverage, actions and errors for each size relative to its BC start.
- Immediate stop for nonfinite tensors, feature/private-state leakage, incorrect sampled log-probabilities,
  mixed runtime/level pins or any contract violation. Stop a seed after three consecutive PPO updates with mean
  human KL above 0.5 nats/poll. Preserve the original design's play-rate kill rule, fewer than 15 or more than
  80 accepted plays per 300 seconds. Report a stopped arm as stopped with its consumed step count; never top it
  up, replace its seed or compare its partial result as an equal-budget completed run.

## Resources and launch gates

- Learners use 08 GPU only, after the BC sweep, larger-snapshot work and extended evaluations release their
  resources. Do not touch the HP1 learner or actors on 04. Reuse the existing GPU admission budget and host
  guards; the learner and anchor must fit inside the admitted cap before a full launch.
- Actors may use genuinely available 05/08 CPU while MemAvailable remains above 28 GiB and load at most 90.
  No HP1 process, core allocation or pool is reduced. Start with a small measurement-only actor job after
  producer parity and hidden-state mutation tests pass. Measure actual games/hour, poll steps/hour, CPU-seconds
  per game, peak RSS and worker-recycle behavior for both sizes on the identical frozen seed/opponent sample.
- Report the actor share needed for a stated completion time from those measurements. If that share overlaps
  CPU currently held by HP1, ask Sam to decide the allocation. Idle capacity does not imply permission to take
  HP1's reserved share. Do not extrapolate provisional forward-pass latency as measured actor throughput.
- Before a training launch: exact engine/live-record producer parity, hidden-state and future-suffix mutation
  checks, real-level own-card/tower microcases, sampled-policy/log-probability/KL parity, bounded memory/queue
  soak, complete rollout/step accounting, fresh-bank registration, and independent Sol high GO for the exact
  harness and launch configuration. Fix findings and re-review. No deployment is part of this authorization.

The next implementation work is the calibrated-engine live-record producer and rollout/PPO harness, followed by
the paired actor-throughput measurement. Their results, resource request and launch-review revision belong in
PROGRESS.md. Missing prerequisites remain visible gates; the approval of both RL arms does not make them passed.

### Resource amendment, 2026-10-22 08:00Z

Sam authorizes 01/02 and leased 09/12/17 for learners once the complete harness/config receives launch GO,
with actors on their spare CPUs and 05. This replaces the earlier 08-only learner allocation and avoids
HP1 CPU on 04/08. All budgets, paired seeds, opponents, levels, metrics and kill rules above are preserved.
Each leased job enforces its lease, process/PSS limit, nice >=10, at least 8 GB GPU free, load <=90 and
MemAvailable >28 GiB, and checkpoints/exits within 30 minutes of reclaim. Hosts 13–16 are excluded.


### Poll-accounting clarification, before launch, 2026-10-22 08:40Z

The deployed reader declares the nominal regulation/overtime deadline decided at tick 3600 with unequal crowns,
or tick 6000, while the pinned calibrated engine resolves the following interval and sets its real terminal flag
at tick 3601/6001. Preserve the existing producer's WAIT at that nominal-deadline poll. Count it as an explicit
`boundary_declined` value-only transition with forced NOOP, actor=false and log probability zero. It does not
call Session.step, sample, submit a command, advance Session RNG or mutate its history. Its critic features use
a copy of causal history. The preceding transition remains nonterminal with zero reward. Only the actual engine
terminal flag supplies the last row's +/-1/0 reward. A second poll without a real terminal flag is a contract
failure. Chunk metadata counts this single boundary row so the learner can validate the exception to the usual
all-masked forced-poll rule. This preserves serving behavior while counting every generated acting-seat poll.


### Operational-rejection amendment, 2026-10-22, before revised fixture review and relaunch

Sam explicitly preserves DECISIONS.md item 8 and the calibrated engine. This supersedes the offline fixture's
extra zero-rejection gate. It changes neither the sampled distribution nor the engine's placement behavior.
The failed first fixture remains failed under its original gate, with all evidence retained. A revised
qualification run uses a new source digest and output directory; it is not replacement registered training data.

- A normal executed tap rejected by the engine has its existing live consequence: no card consumption,
  no elixir spend, and continued play. Retain its sampled action, old log probability, actor mask and poll step.
  Never resample, substitute WAIT, discard the transition, top up the budget or add a reward penalty.
  Session history continues to infer rejection from public records under DECISIONS.md item 6.
- For every RL snapshot, including the BC start, report operational rejections overall and by card in the
  RL logs and evaluation readout. Rate is rejected executed taps divided by executed taps. Report submitted,
  executed, accepted, rejected and pending counts as well. Pending commands at terminal or budget stop are
  not executed rejections and are excluded from that denominator. Separate these counts from engine errors,
  invalid state, unknown identity and all other execution/contract failures.
- Alert without stopping when a snapshot's rejection rate is strictly greater than twice its own size's
  frozen BC-start rate on the matched evaluation exposure. Report the same comparison by card. Compare
  exact counts without pseudocounts. A BC zero rate with positive exposure alerts on any positive current
  rate; absent baseline or zero executed exposure is unavailable, never an invented zero. Pin baseline
  checkpoint, bank, scope and counts; label partial measurements as partial. Training/fixture telemetry
  remains separately labelled when its opponent exposure differs from the paired evaluation baseline.
- All other execution failures keep their existing fail-closed behavior. This amendment grants no broad
  catch-and-continue rule. Existing finite-state, identity, legality, provenance, strict likelihood, reward,
  exact-budget, play-rate and KL gates remain. Rejections above the threshold are alerts only.
- An occupancy-aware public mask is a possible later improvement, explicitly outside this launch.


### M-primary and resource priority amendment, Sam's 2026-10-22 decision

M is now primary, S100 secondary, under the completed fresh-bank registered comparison. Both RL arms remain
required with the same steps, seeds, objective, level/deck/league mixtures and evaluation accounting. M starts
first on own01; S100 starts on own02 after its final gates pass. Local actors permit this path to launch without
waiting for leased-host continuation/reclaim qualification. Existing R37 watcher source is already approved.
The registered recycling, resource, memory-soak and exact integrated-review gates are not silently waived.

In parallel, Sam authorizes a frozen interim approximately 120k-match re-drive snapshot and two or three M-BC
seeds on available GPUs, with08 allocated first so01/02 remain available to RL. Inputs are sealed-only, hash-bound,
and use the unchanged feature contract, R7 leak protection and physical-match split. These retrains are candidates;
no automatic checkpoint promotion or deployment follows from loss selection.

M's approved Mac serving target is FP32 CPU1, whose measured p95 about16.0ms passes. Do not wait for an idle Mac
rerun. Offline training precision and its exact actor/learner parity remain separately recorded launch details;
no serving conversion or deployment is part of this amendment.
